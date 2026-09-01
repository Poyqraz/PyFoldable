"""Dependency-free contracts for external polar-generation providers."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal, Mapping, Protocol, runtime_checkable

from .models import AirfoilDefinition, PolarTable
from .airfoil import airfoil_coordinate_sha256


PolarPointStatus = Literal[
    "converged",
    "not_converged",
    "low_confidence",
    "invalid",
]
_POLAR_POINT_STATUSES = {
    "converged",
    "not_converged",
    "low_confidence",
    "invalid",
}


class PolarProviderError(RuntimeError):
    """Base class for provider failures that prevent a complete result."""


class PolarProviderUnavailableError(PolarProviderError):
    """Raised when an optional backend or executable is not available."""


class PolarProviderTimeoutError(PolarProviderError):
    """Raised when a provider exceeds the declared request timeout."""


class PolarProviderExecutionError(PolarProviderError):
    """Raised when a provider starts but cannot produce a valid result envelope."""


class PolarProviderCapabilityError(PolarProviderError):
    """Raised when a request uses an unsupported provider capability."""


def _finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite.")


def _canonical_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Cache inputs must not contain non-finite floats.")
        return value
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("Cache mapping keys must be strings.")
        return {
            key: _canonical_value(item)
            for key, item in sorted(value.items(), key=lambda pair: pair[0])
        }
    if isinstance(value, (tuple, list)):
        return [_canonical_value(item) for item in value]
    raise TypeError(f"Unsupported cache input type {type(value).__name__}.")


def _freeze_value(value: Any) -> Any:
    """Recursively snapshot JSON-like values used by frozen contract objects."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_value(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_value(item) for item in value)
    return value


@dataclass(frozen=True)
class ProviderIdentity:
    """Stable provider and backend identity recorded in every generated polar."""

    name: str
    adapter_version: str
    backend_name: str
    backend_version: str

    def __post_init__(self) -> None:
        if not all((self.name, self.adapter_version, self.backend_name, self.backend_version)):
            raise ValueError("Provider identity fields must not be empty.")

    def as_mapping(self) -> dict[str, str]:
        return {
            "name": self.name,
            "adapter_version": self.adapter_version,
            "backend_name": self.backend_name,
            "backend_version": self.backend_version,
        }


@dataclass(frozen=True)
class ProviderCapabilities:
    """Features a provider can honor without silently ignoring request fields."""

    supports_mach: bool
    supports_n_crit: bool
    supports_forced_transition: bool
    supports_pointwise_confidence: bool
    supports_partial_results: bool
    supports_vectorized_alpha: bool
    supports_iteration_limit: bool
    supports_timeout: bool = False

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"Provider capability {name} must be bool.")


@dataclass(frozen=True)
class PolarGenerationRequest:
    """Solver-neutral request for one Reynolds/Mach polar sweep."""

    airfoil: AirfoilDefinition
    alpha_rad: tuple[float, ...]
    reynolds: float
    mach: float = 0.0
    n_crit: float = 9.0
    xtr_upper: float = 1.0
    xtr_lower: float = 1.0
    max_iterations: int | None = None
    timeout_s: float = 30.0
    scenario_id: str = "default"
    options: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.airfoil.coordinates:
            raise ValueError("Polar generation requires airfoil coordinates.")
        x_coordinates = tuple(point[0] for point in self.airfoil.coordinates)
        if (
            not math.isclose(min(x_coordinates), 0.0, rel_tol=0.0, abs_tol=1.0e-7)
            or not math.isclose(max(x_coordinates), 1.0, rel_tol=0.0, abs_tol=1.0e-7)
            or any(x < -1.0e-7 or x > 1.0 + 1.0e-7 for x in x_coordinates)
        ):
            raise ValueError("Provider airfoil coordinates must use normalized unit chord.")
        if len(self.alpha_rad) < 2:
            raise ValueError("Polar generation requires at least two alpha points.")
        for index, alpha in enumerate(self.alpha_rad):
            _finite(f"alpha_rad[{index}]", alpha)
        if len(set(self.alpha_rad)) != len(self.alpha_rad):
            raise ValueError("alpha_rad must not contain duplicate points.")
        _finite("reynolds", self.reynolds)
        if self.reynolds <= 0.0:
            raise ValueError("reynolds must be greater than zero.")
        _finite("mach", self.mach)
        if self.mach < 0.0:
            raise ValueError("mach must be non-negative.")
        _finite("n_crit", self.n_crit)
        if self.n_crit <= 0.0:
            raise ValueError("n_crit must be greater than zero.")
        for name in ("xtr_upper", "xtr_lower"):
            value = getattr(self, name)
            _finite(name, value)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1].")
        if self.max_iterations is not None:
            if (
                isinstance(self.max_iterations, bool)
                or not isinstance(self.max_iterations, int)
                or self.max_iterations < 1
            ):
                raise ValueError("max_iterations must be a positive integer or None.")
        _finite("timeout_s", self.timeout_s)
        if self.timeout_s <= 0.0:
            raise ValueError("timeout_s must be greater than zero.")
        if not self.scenario_id:
            raise ValueError("scenario_id must not be empty.")
        _canonical_value(self.options)
        object.__setattr__(self, "options", _freeze_value(self.options))

    def validate_capabilities(self, capabilities: ProviderCapabilities) -> None:
        """Reject fields that a provider would otherwise have to ignore."""
        unsupported: list[str] = []
        if self.mach != 0.0 and not capabilities.supports_mach:
            unsupported.append("mach")
        if self.n_crit != 9.0 and not capabilities.supports_n_crit:
            unsupported.append("n_crit")
        if (
            (self.xtr_upper != 1.0 or self.xtr_lower != 1.0)
            and not capabilities.supports_forced_transition
        ):
            unsupported.append("forced_transition")
        if self.max_iterations is not None and not capabilities.supports_iteration_limit:
            unsupported.append("max_iterations")
        if self.timeout_s != 30.0 and not capabilities.supports_timeout:
            unsupported.append("timeout_s")
        if unsupported:
            joined = ", ".join(unsupported)
            raise PolarProviderCapabilityError(
                f"Provider does not support requested capabilities: {joined}."
            )

    def cache_payload(self, provider: ProviderIdentity) -> dict[str, Any]:
        """Return the canonical, versioned cache identity document."""
        return {
            "cache_schema_version": 1,
            "provider": provider.as_mapping(),
            "airfoil": {
                "id": self.airfoil.id,
                "coordinates": self.airfoil.coordinates,
            },
            "alpha_rad": self.alpha_rad,
            "reynolds": self.reynolds,
            "mach": self.mach,
            "n_crit": self.n_crit,
            "xtr_upper": self.xtr_upper,
            "xtr_lower": self.xtr_lower,
            "max_iterations": self.max_iterations,
            "timeout_s": self.timeout_s,
            "scenario_id": self.scenario_id,
            "options": self.options,
        }

    def cache_key(self, provider: ProviderIdentity) -> str:
        """Hash every physical, numerical, geometry, and backend cache input."""
        document = json.dumps(
            _canonical_value(self.cache_payload(provider)),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(document).hexdigest()


@dataclass(frozen=True)
class PolarPointResult:
    """One requested operating point, including convergence/confidence state."""

    alpha_rad: float
    status: PolarPointStatus
    cl: float | None = None
    cd: float | None = None
    cm: float | None = None
    confidence: float | None = None
    iterations: int | None = None
    message: str = ""

    def __post_init__(self) -> None:
        _finite("alpha_rad", self.alpha_rad)
        if self.status not in _POLAR_POINT_STATUSES:
            raise ValueError(f"Unsupported polar point status {self.status!r}.")
        coefficients = (self.cl, self.cd, self.cm)
        has_all = all(value is not None for value in coefficients)
        has_none = all(value is None for value in coefficients)
        if not has_all and not has_none:
            raise ValueError("cl, cd, and cm must be present or absent together.")
        if self.status in {"converged", "low_confidence"} and not has_all:
            raise ValueError(f"Status {self.status!r} requires aerodynamic coefficients.")
        if self.status in {"not_converged", "invalid"} and not has_none:
            raise ValueError(f"Status {self.status!r} cannot contain coefficients.")
        for name in ("cl", "cd", "cm"):
            value = getattr(self, name)
            if value is not None:
                _finite(name, value)
        if self.cd is not None and self.cd < 0.0:
            raise ValueError("cd must be non-negative.")
        if self.confidence is not None:
            _finite("confidence", self.confidence)
            if not 0.0 <= self.confidence <= 1.0:
                raise ValueError("confidence must be in [0, 1].")
        if self.status == "low_confidence" and self.confidence is None:
            raise ValueError("Status 'low_confidence' requires a confidence value.")
        if self.iterations is not None:
            if (
                isinstance(self.iterations, bool)
                or not isinstance(self.iterations, int)
                or self.iterations < 0
            ):
                raise ValueError("iterations must be a non-negative integer.")

    @property
    def usable(self) -> bool:
        return self.status in {"converged", "low_confidence"}


@dataclass(frozen=True)
class PolarGenerationResult:
    """Provider result envelope that preserves partial point failures."""

    request: PolarGenerationRequest
    provider: ProviderIdentity
    points: tuple[PolarPointResult, ...]
    elapsed_s: float
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _finite("elapsed_s", self.elapsed_s)
        if self.elapsed_s < 0.0:
            raise ValueError("elapsed_s must be non-negative.")
        if len(self.points) != len(self.request.alpha_rad):
            raise ValueError("Provider result must contain one point per requested alpha.")
        for expected, point in zip(self.request.alpha_rad, self.points):
            if not math.isclose(expected, point.alpha_rad, rel_tol=0.0, abs_tol=1.0e-12):
                raise ValueError("Provider result alpha order must match the request.")
        _canonical_value(self.metadata)
        object.__setattr__(self, "metadata", _freeze_value(self.metadata))

    @property
    def converged_mask(self) -> tuple[bool, ...]:
        return tuple(point.status == "converged" for point in self.points)

    @property
    def usable_mask(self) -> tuple[bool, ...]:
        return tuple(point.usable for point in self.points)

    @property
    def complete(self) -> bool:
        return all(self.usable_mask)

    @property
    def cache_key(self) -> str:
        return self.request.cache_key(self.provider)

    def to_polar_table(self, *, require_complete: bool = True) -> PolarTable:
        """Convert usable points into a canonical table without inventing failures."""
        if require_complete and not self.complete:
            failed = [
                f"{math.degrees(point.alpha_rad):g} deg ({point.status})"
                for point in self.points
                if not point.usable
            ]
            raise PolarProviderExecutionError(
                "Cannot build a complete polar; failed points: " + ", ".join(failed)
            )
        usable = tuple(
            sorted(
                (point for point in self.points if point.usable),
                key=lambda point: point.alpha_rad,
            )
        )
        if len(usable) < 2:
            raise PolarProviderExecutionError(
                "At least two usable points are required to build a polar table."
            )
        confidence = tuple(point.confidence for point in usable)
        return PolarTable(
            airfoil_id=self.request.airfoil.id,
            reynolds=self.request.reynolds,
            mach=self.request.mach,
            alpha_rad=tuple(point.alpha_rad for point in usable),
            cl=tuple(float(point.cl) for point in usable),
            cd=tuple(float(point.cd) for point in usable),
            cm=tuple(float(point.cm) for point in usable),
            source=f"{self.provider.name}:{self.provider.backend_version}",
            scenario_id=self.request.scenario_id,
            metadata={
                **dict(self.metadata),
                "provider": self.provider.as_mapping(),
                "evidence_class": "provider_generated_polar",
                "airfoil_source": self.request.airfoil.source,
                "airfoil_coordinate_sha256": airfoil_coordinate_sha256(self.request.airfoil),
                "cache_key": self.cache_key,
                "complete": self.complete,
                "requested_point_count": len(self.points),
                "usable_point_count": len(usable),
                "confidence": confidence,
                "warnings": self.warnings,
            },
        )


@runtime_checkable
class PolarProvider(Protocol):
    """Interface implemented by XFOIL, NeuralFoil, and test providers."""

    @property
    def identity(self) -> ProviderIdentity:
        ...

    @property
    def capabilities(self) -> ProviderCapabilities:
        ...

    def generate(self, request: PolarGenerationRequest) -> PolarGenerationResult:
        ...


def generate_polar(
    provider: PolarProvider,
    request: PolarGenerationRequest,
) -> PolarGenerationResult:
    """Validate capabilities and enforce the result/provider identity boundary."""
    request.validate_capabilities(provider.capabilities)
    result = provider.generate(request)
    return _validate_polar_result(provider, request, result)


def _validate_polar_result(
    provider: PolarProvider,
    request: PolarGenerationRequest,
    result: Any,
) -> PolarGenerationResult:
    """Enforce the provider boundary for generated and cached result envelopes."""
    if not isinstance(result, PolarGenerationResult):
        raise PolarProviderExecutionError(
            "Provider did not return a PolarGenerationResult."
        )
    if result.request != request:
        raise PolarProviderExecutionError("Provider returned a result for another request.")
    if result.provider != provider.identity:
        raise PolarProviderExecutionError(
            "Provider result identity does not match adapter identity."
        )
    if not provider.capabilities.supports_partial_results and not result.complete:
        raise PolarProviderExecutionError(
            "Provider returned partial results contrary to its capability declaration."
        )
    has_confidence = any(point.confidence is not None for point in result.points)
    if has_confidence and not provider.capabilities.supports_pointwise_confidence:
        raise PolarProviderExecutionError(
            "Provider returned confidence contrary to its capability declaration."
        )
    return result
