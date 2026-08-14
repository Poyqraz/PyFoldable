"""Optional in-process adapter for NeuralFoil polar generation."""

from __future__ import annotations

import importlib
import math
import time
from importlib import metadata
from types import ModuleType
from typing import Any, Mapping

import numpy as np

from ..core.providers import (
    PolarGenerationRequest,
    PolarGenerationResult,
    PolarPointResult,
    PolarProviderCapabilityError,
    PolarProviderExecutionError,
    PolarProviderUnavailableError,
    ProviderCapabilities,
    ProviderIdentity,
)


_ADAPTER_VERSION = "1"
_MODEL_SIZES = {
    "xxsmall",
    "xsmall",
    "small",
    "medium",
    "large",
    "xlarge",
    "xxlarge",
    "xxxlarge",
}
_ALLOWED_OPTIONS = {"confidence_threshold", "model_size"}
_CAPABILITIES = ProviderCapabilities(
    supports_mach=False,
    supports_n_crit=True,
    supports_forced_transition=True,
    supports_pointwise_confidence=True,
    supports_partial_results=False,
    supports_vectorized_alpha=True,
    supports_iteration_limit=False,
    supports_timeout=False,
)


class NeuralFoilProvider:
    """Generate polars with NeuralFoil's vectorized coordinate API."""

    capabilities = _CAPABILITIES

    def __init__(self) -> None:
        self._backend = _load_backend()
        self._identity = ProviderIdentity(
            name="neuralfoil",
            adapter_version=_ADAPTER_VERSION,
            backend_name="NeuralFoil",
            backend_version=_backend_version(self._backend),
        )

    @property
    def identity(self) -> ProviderIdentity:
        return self._identity

    def generate(self, request: PolarGenerationRequest) -> PolarGenerationResult:
        """Evaluate every requested angle in one validated NeuralFoil call."""
        request.validate_capabilities(self.capabilities)
        options = _validated_options(request.options)
        coordinates = np.asarray(request.airfoil.coordinates, dtype=float)
        alpha_deg = np.degrees(np.asarray(request.alpha_rad, dtype=float))

        started = time.perf_counter()
        try:
            raw_outputs = self._backend.get_aero_from_coordinates(
                coordinates=coordinates,
                alpha=alpha_deg,
                Re=request.reynolds,
                n_crit=request.n_crit,
                xtr_upper=request.xtr_upper,
                xtr_lower=request.xtr_lower,
                model_size=options["model_size"],
            )
        except Exception as error:
            raise PolarProviderExecutionError("NeuralFoil evaluation failed.") from error
        elapsed_s = time.perf_counter() - started

        outputs = _validated_outputs(raw_outputs, len(request.alpha_rad))
        threshold = options["confidence_threshold"]
        points = tuple(
            _point_from_outputs(request, outputs, index, threshold)
            for index in range(len(request.alpha_rad))
        )
        low_confidence_count = sum(point.status == "low_confidence" for point in points)
        warnings: tuple[str, ...] = ()
        if low_confidence_count:
            warnings = (
                "NeuralFoil marked "
                f"{low_confidence_count} requested angle(s) below confidence threshold "
                f"{threshold:g}.",
            )

        return PolarGenerationResult(
            request=request,
            provider=self.identity,
            points=points,
            elapsed_s=elapsed_s,
            warnings=warnings,
            metadata={
                "adapter": "in-process-vectorized",
                "model_size": options["model_size"],
                "confidence_threshold": threshold,
                "top_xtr": tuple(float(value) for value in outputs["Top_Xtr"]),
                "bottom_xtr": tuple(float(value) for value in outputs["Bot_Xtr"]),
            },
        )


def _load_backend() -> ModuleType:
    try:
        backend = importlib.import_module("neuralfoil")
    except ImportError as error:
        raise PolarProviderUnavailableError(
            "NeuralFoil is unavailable; install pyfoldable[neuralfoil]."
        ) from error
    if not callable(getattr(backend, "get_aero_from_coordinates", None)):
        raise PolarProviderUnavailableError(
            "Installed NeuralFoil does not expose get_aero_from_coordinates()."
        )
    return backend


def _backend_version(backend: ModuleType) -> str:
    reported = getattr(backend, "__version__", None)
    if isinstance(reported, str) and reported.strip():
        return reported.strip()
    try:
        return metadata.version("NeuralFoil")
    except metadata.PackageNotFoundError as error:
        raise PolarProviderUnavailableError(
            "NeuralFoil version metadata is unavailable."
        ) from error


def _validated_options(options: Mapping[str, Any]) -> dict[str, Any]:
    unknown = sorted(set(options) - _ALLOWED_OPTIONS)
    if unknown:
        raise PolarProviderCapabilityError(
            "Unsupported NeuralFoil provider options: " + ", ".join(unknown) + "."
        )
    model_size = options.get("model_size", "xlarge")
    if not isinstance(model_size, str) or model_size not in _MODEL_SIZES:
        choices = ", ".join(sorted(_MODEL_SIZES))
        raise PolarProviderCapabilityError(
            f"NeuralFoil option 'model_size' must be one of: {choices}."
        )
    threshold = options.get("confidence_threshold", 0.5)
    if (
        isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or not math.isfinite(threshold)
        or not 0.0 <= threshold <= 1.0
    ):
        raise PolarProviderCapabilityError(
            "NeuralFoil option 'confidence_threshold' must be finite and in [0, 1]."
        )
    return {
        "model_size": model_size,
        "confidence_threshold": float(threshold),
    }


def _validated_outputs(raw_outputs: Any, count: int) -> dict[str, np.ndarray]:
    if not isinstance(raw_outputs, Mapping):
        raise PolarProviderExecutionError("NeuralFoil output must be a mapping.")
    outputs = {
        name: _output_vector(raw_outputs, name, count)
        for name in ("analysis_confidence", "CL", "CD", "CM", "Top_Xtr", "Bot_Xtr")
    }
    if np.any(outputs["CD"] < 0.0):
        raise PolarProviderExecutionError("NeuralFoil output CD must be non-negative.")
    for name in ("analysis_confidence", "Top_Xtr", "Bot_Xtr"):
        if np.any((outputs[name] < 0.0) | (outputs[name] > 1.0)):
            raise PolarProviderExecutionError(
                f"NeuralFoil output {name} must be in [0, 1]."
            )
    return outputs


def _output_vector(raw_outputs: Mapping[str, Any], name: str, count: int) -> np.ndarray:
    if name not in raw_outputs:
        raise PolarProviderExecutionError(f"NeuralFoil output is missing {name}.")
    try:
        values = np.asarray(raw_outputs[name], dtype=float).reshape(-1)
    except (TypeError, ValueError) as error:
        raise PolarProviderExecutionError(
            f"NeuralFoil output {name} is not a numeric vector."
        ) from error
    if values.size != count:
        raise PolarProviderExecutionError(
            f"NeuralFoil output {name} has {values.size} values; expected {count}."
        )
    if not np.all(np.isfinite(values)):
        raise PolarProviderExecutionError(
            f"NeuralFoil output {name} must contain only finite values."
        )
    return values


def _point_from_outputs(
    request: PolarGenerationRequest,
    outputs: Mapping[str, np.ndarray],
    index: int,
    threshold: float,
) -> PolarPointResult:
    confidence = float(outputs["analysis_confidence"][index])
    low_confidence = confidence < threshold
    return PolarPointResult(
        alpha_rad=request.alpha_rad[index],
        status="low_confidence" if low_confidence else "converged",
        cl=float(outputs["CL"][index]),
        cd=float(outputs["CD"][index]),
        cm=float(outputs["CM"][index]),
        confidence=confidence,
        message=(
            f"NeuralFoil confidence {confidence:g} is below threshold {threshold:g}."
            if low_confidence
            else ""
        ),
    )
