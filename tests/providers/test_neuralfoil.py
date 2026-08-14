"""Optional-backend tests for the NeuralFoil provider."""

from __future__ import annotations

import sys
from dataclasses import replace
from types import ModuleType
from typing import Any

import numpy as np
import pytest

from pyfoldable import NeuralFoilProvider
from pyfoldable.core import (
    AirfoilDefinition,
    PolarGenerationRequest,
    PolarProviderCapabilityError,
    PolarProviderExecutionError,
    PolarProviderUnavailableError,
    generate_polar,
)
from pyfoldable.providers import neuralfoil as adapter_module


@pytest.fixture
def fake_neuralfoil(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    backend = ModuleType("neuralfoil")
    backend.__version__ = "0.3.3-test"
    backend.calls = []
    backend.overrides = {}
    backend.failure = None
    backend.raw_output = None

    def get_aero_from_coordinates(**kwargs: Any) -> dict[str, np.ndarray]:
        backend.calls.append(kwargs)
        if backend.failure is not None:
            raise backend.failure
        if backend.raw_output is not None:
            return backend.raw_output
        alpha = np.asarray(kwargs["alpha"], dtype=float).reshape(-1)
        count = alpha.size
        confidence = np.resize(np.asarray([0.9, 0.4, 0.1]), count)
        outputs = {
            "analysis_confidence": confidence,
            "CL": 0.1 * alpha,
            "CD": 0.01 + 0.0001 * alpha**2,
            "CM": np.full(count, -0.02),
            "Top_Xtr": np.full(count, 0.8),
            "Bot_Xtr": np.full(count, 0.7),
        }
        outputs.update(backend.overrides)
        return outputs

    backend.get_aero_from_coordinates = get_aero_from_coordinates
    monkeypatch.setitem(sys.modules, "neuralfoil", backend)
    return backend


@pytest.fixture
def polar_request() -> PolarGenerationRequest:
    airfoil = AirfoilDefinition(
        id="TEST",
        source="fixture",
        coordinates=(
            (1.0, 0.0),
            (0.5, 0.1),
            (0.0, 0.0),
            (0.5, -0.1),
            (1.0, 0.0),
        ),
    )
    return PolarGenerationRequest(
        airfoil=airfoil,
        alpha_rad=(-0.1, 0.0, 0.1),
        reynolds=150_000.0,
        n_crit=7.0,
        xtr_upper=0.8,
        xtr_lower=0.7,
        scenario_id="clean",
    )


def test_provider_is_lazy_and_reports_backend_identity(
    fake_neuralfoil: ModuleType,
) -> None:
    provider = NeuralFoilProvider()

    assert provider.identity.name == "neuralfoil"
    assert provider.identity.backend_name == "NeuralFoil"
    assert provider.identity.backend_version == "0.3.3-test"
    assert provider.capabilities.supports_vectorized_alpha
    assert provider.capabilities.supports_pointwise_confidence
    assert not provider.capabilities.supports_mach
    assert not provider.capabilities.supports_iteration_limit
    assert not provider.capabilities.supports_timeout


def test_missing_backend_uses_typed_unavailable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_backend(name: str) -> ModuleType:
        raise ModuleNotFoundError(name)

    monkeypatch.setattr(adapter_module.importlib, "import_module", missing_backend)

    with pytest.raises(PolarProviderUnavailableError, match=r"pyfoldable\[neuralfoil\]"):
        NeuralFoilProvider()


def test_vectorized_call_maps_inputs_outputs_and_confidence(
    fake_neuralfoil: ModuleType,
    polar_request: PolarGenerationRequest,
) -> None:
    result = generate_polar(NeuralFoilProvider(), polar_request)

    assert len(fake_neuralfoil.calls) == 1
    call = fake_neuralfoil.calls[0]
    assert call["coordinates"].shape == (5, 2)
    assert call["alpha"] == pytest.approx(np.degrees(polar_request.alpha_rad))
    assert call["Re"] == 150_000.0
    assert call["n_crit"] == 7.0
    assert call["xtr_upper"] == 0.8
    assert call["xtr_lower"] == 0.7
    assert call["model_size"] == "xlarge"

    assert result.complete
    assert result.converged_mask == (True, False, False)
    assert tuple(point.status for point in result.points) == (
        "converged",
        "low_confidence",
        "low_confidence",
    )
    assert result.usable_mask == (True, True, True)
    assert result.warnings == (
        "NeuralFoil marked 2 requested angle(s) below confidence threshold 0.5.",
    )
    assert result.metadata["top_xtr"] == (0.8, 0.8, 0.8)
    assert result.metadata["bottom_xtr"] == (0.7, 0.7, 0.7)
    assert result.to_polar_table().metadata["confidence"] == (0.9, 0.4, 0.1)


def test_options_control_model_and_threshold_and_change_cache_identity(
    fake_neuralfoil: ModuleType,
    polar_request: PolarGenerationRequest,
) -> None:
    configured = replace(
        polar_request,
        options={"model_size": "large", "confidence_threshold": 0.1},
    )

    result = generate_polar(NeuralFoilProvider(), configured)

    assert fake_neuralfoil.calls[0]["model_size"] == "large"
    assert result.converged_mask == (True, True, True)
    assert result.warnings == ()
    assert result.metadata["confidence_threshold"] == 0.1
    assert result.cache_key != polar_request.cache_key(result.provider)


def test_descending_request_order_is_preserved(
    fake_neuralfoil: ModuleType,
    polar_request: PolarGenerationRequest,
) -> None:
    descending = replace(
        polar_request,
        alpha_rad=tuple(reversed(polar_request.alpha_rad)),
        options={"confidence_threshold": 0.0},
    )

    result = generate_polar(NeuralFoilProvider(), descending)

    assert tuple(point.alpha_rad for point in result.points) == descending.alpha_rad
    assert result.to_polar_table().alpha_rad == tuple(sorted(descending.alpha_rad))


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"mach": 0.1}, "mach"),
        ({"max_iterations": 50}, "max_iterations"),
        ({"timeout_s": 1.0}, "timeout_s"),
    ],
)
def test_unsupported_request_capabilities_are_rejected(
    fake_neuralfoil: ModuleType,
    polar_request: PolarGenerationRequest,
    changes: dict[str, Any],
    message: str,
) -> None:
    with pytest.raises(PolarProviderCapabilityError, match=message):
        generate_polar(NeuralFoilProvider(), replace(polar_request, **changes))


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"unknown": True}, "unknown"),
        ({"model_size": "enormous"}, "model_size"),
        ({"confidence_threshold": -0.1}, "confidence_threshold"),
        ({"confidence_threshold": True}, "confidence_threshold"),
    ],
)
def test_provider_options_are_strict(
    fake_neuralfoil: ModuleType,
    polar_request: PolarGenerationRequest,
    options: dict[str, Any],
    message: str,
) -> None:
    with pytest.raises(PolarProviderCapabilityError, match=message):
        generate_polar(NeuralFoilProvider(), replace(polar_request, options=options))


def test_backend_exception_is_wrapped(
    fake_neuralfoil: ModuleType,
    polar_request: PolarGenerationRequest,
) -> None:
    fake_neuralfoil.failure = RuntimeError("backend exploded")

    with pytest.raises(PolarProviderExecutionError, match="evaluation failed") as captured:
        generate_polar(NeuralFoilProvider(), polar_request)

    assert isinstance(captured.value.__cause__, RuntimeError)


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("CL", np.asarray([1.0, 2.0]), "expected 3"),
        ("CD", np.asarray([0.01, -0.01, 0.02]), "non-negative"),
        ("CM", np.asarray([0.0, np.nan, 0.0]), "finite"),
        ("analysis_confidence", np.asarray([0.9, 1.1, 0.5]), "in \\[0, 1\\]"),
        ("Top_Xtr", np.asarray([0.8, -0.1, 0.8]), "in \\[0, 1\\]"),
    ],
)
def test_invalid_backend_vectors_are_rejected(
    fake_neuralfoil: ModuleType,
    polar_request: PolarGenerationRequest,
    key: str,
    value: np.ndarray,
    message: str,
) -> None:
    fake_neuralfoil.overrides[key] = value

    with pytest.raises(PolarProviderExecutionError, match=message):
        generate_polar(NeuralFoilProvider(), polar_request)


def test_missing_key_and_non_mapping_output_are_rejected(
    fake_neuralfoil: ModuleType,
    polar_request: PolarGenerationRequest,
) -> None:
    fake_neuralfoil.raw_output = {"CL": np.zeros(3)}
    with pytest.raises(PolarProviderExecutionError, match="analysis_confidence"):
        generate_polar(NeuralFoilProvider(), polar_request)

    fake_neuralfoil.raw_output = [1.0, 2.0, 3.0]
    with pytest.raises(PolarProviderExecutionError, match="must be a mapping"):
        generate_polar(NeuralFoilProvider(), polar_request)
