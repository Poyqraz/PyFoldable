"""Strict, versioned configuration binding for provider-backed polar families."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

try:  # pragma: no cover - exercised by Python 3.10 CI
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

from .airfoil import load_airfoil_coordinates
from .polar_acceptance import (
    PolarAcceptanceCriteria,
    PolarErrorTolerance,
)
from .polar_cache import FilesystemPolarCache
from .polar_cache_lock import PolarCacheLockPolicy
from .polar_family_generation import (
    PolarFamilyBatchPolicy,
    PolarFamilyBatchResult,
    PolarFamilyGenerationPlan,
    generate_polar_family_batch,
)
from .polar_health import PolarProviderHealthPolicy, PolarProviderHealthRegistry
from .polar_orchestration import PolarRetryPolicy
from .polar_qualification import PolarResultQualificationPolicy
from .providers import (
    PolarGenerationRequest,
    PolarProvider,
    PolarProviderCapabilityError,
)
from .units import normalize_quantity


POLAR_CONFIG_SCHEMA_VERSION = 1

_ROOT_FIELDS = {
    "schema_version",
    "request",
    "grid",
    "providers",
    "retry",
    "cache",
    "health",
    "qualification",
    "batch",
    "acceptance",
}
_REQUEST_FIELDS = {
    "airfoil_file",
    "airfoil_id",
    "airfoil_format",
    "scenario_id",
    "alpha",
    "n_crit",
    "xtr_upper",
    "xtr_lower",
    "max_iterations",
    "timeout",
}
_GRID_FIELDS = {"reynolds", "mach"}
_RETRY_FIELDS = {
    "max_attempts",
    "initial_backoff",
    "max_backoff",
    "backoff_factor",
    "retry_timeouts",
    "retry_execution_errors",
}
_CACHE_FIELDS = {"enabled", "root", "lock"}
_LOCK_FIELDS = {
    "wait_timeout",
    "initial_poll_interval",
    "max_poll_interval",
    "backoff_factor",
}
_HEALTH_FIELDS = {
    "enabled",
    "failure_threshold",
    "recovery_timeout",
    "count_unavailable_errors",
    "count_timeout_errors",
    "count_execution_errors",
    "count_provider_errors",
    "isolate_unexpected_errors",
    "count_unexpected_errors",
}
_QUALIFICATION_FIELDS = {
    "minimum_usable_fraction",
    "minimum_usable_points",
    "allow_low_confidence",
}
_BATCH_FIELDS = {"failure_mode", "subgrid_policy"}
_ACCEPTANCE_FIELDS = {
    "cl",
    "cd",
    "cm",
    "minimum_coverage",
    "require_usable_match",
}
_TOLERANCE_FIELDS = {"absolute", "relative"}
_PROVIDER_FIELDS = {
    "xfoil": {"kind", "executable", "backend_version", "version_timeout"},
    "neuralfoil": {"kind"},
}


class PolarConfigError(ValueError):
    """Raised when a polar-family configuration is invalid or ambiguous."""


def _read_document(path: Path) -> tuple[Mapping[str, Any], str]:
    try:
        payload = path.read_bytes()
        if path.suffix.casefold() == ".toml":
            document = tomllib.loads(payload.decode("utf-8"))
        elif path.suffix.casefold() == ".json":
            document = json.loads(payload.decode("utf-8"))
        else:
            raise PolarConfigError("Polar config files must use .toml or .json.")
    except PolarConfigError:
        raise
    except (OSError, UnicodeError, ValueError) as error:
        raise PolarConfigError(f"Could not read polar config {path}.") from error
    if not isinstance(document, Mapping):
        raise PolarConfigError("Polar config root must be a table/object.")
    return document, hashlib.sha256(payload).hexdigest()


def _reject_unknown(
    value: Mapping[str, Any],
    allowed: set[str],
    path: str,
) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise PolarConfigError(
            f"Unknown config field(s) in {path}: {', '.join(unknown)}."
        )


def _table(
    parent: Mapping[str, Any],
    key: str,
    *,
    required: bool = False,
) -> Mapping[str, Any]:
    value = parent.get(key)
    if value is None and not required:
        return {}
    if not isinstance(value, Mapping):
        raise PolarConfigError(f"Config field {key!r} must be a table/object.")
    return value


def _required(parent: Mapping[str, Any], key: str, path: str) -> Any:
    if key not in parent:
        raise PolarConfigError(f"Missing required config field {path}.{key}.")
    return parent[key]


def _bool(parent: Mapping[str, Any], key: str, path: str, default: bool) -> bool:
    value = parent.get(key, default)
    if not isinstance(value, bool):
        raise PolarConfigError(f"Config field {path}.{key} must be bool.")
    return value


def _integer(
    parent: Mapping[str, Any],
    key: str,
    path: str,
    default: int | None,
    *,
    minimum: int,
) -> int | None:
    value = parent.get(key, default)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise PolarConfigError(
            f"Config field {path}.{key} must be an integer of at least {minimum}."
        )
    return value


def _number(
    parent: Mapping[str, Any],
    key: str,
    path: str,
    default: float,
) -> float:
    value = parent.get(key, default)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        raise PolarConfigError(f"Config field {path}.{key} must be finite numeric.")
    return float(value)


def _time(
    parent: Mapping[str, Any],
    key: str,
    path: str,
    default: str,
) -> float:
    try:
        return normalize_quantity(
            parent.get(key, default),
            "time",
            field=f"{path}.{key}",
        ).si_value
    except ValueError as error:
        raise PolarConfigError(str(error)) from error


def _angles(request: Mapping[str, Any]) -> tuple[float, ...]:
    raw = _required(request, "alpha", "request")
    if not isinstance(raw, list) or len(raw) < 2:
        raise PolarConfigError("Config field request.alpha must be an array of angles.")
    values: list[float] = []
    for index, value in enumerate(raw):
        try:
            values.append(
                normalize_quantity(
                    value,
                    "angle",
                    field=f"request.alpha[{index}]",
                ).si_value
            )
        except ValueError as error:
            raise PolarConfigError(str(error)) from error
    if len(set(values)) != len(values):
        raise PolarConfigError("Config field request.alpha must be unique.")
    return tuple(values)


def _numeric_grid(
    grid: Mapping[str, Any],
    key: str,
    *,
    positive: bool,
) -> tuple[float, ...]:
    raw = _required(grid, key, "grid")
    if not isinstance(raw, list) or not raw:
        raise PolarConfigError(f"Config field grid.{key} must be a non-empty array.")
    values: list[float] = []
    for index, value in enumerate(raw):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            raise PolarConfigError(f"Config field grid.{key}[{index}] must be finite.")
        numeric = float(value)
        if (positive and numeric <= 0.0) or (not positive and numeric < 0.0):
            qualifier = "positive" if positive else "non-negative"
            raise PolarConfigError(
                f"Config field grid.{key}[{index}] must be {qualifier}."
            )
        values.append(numeric)
    if any(upper <= lower for lower, upper in zip(values, values[1:])):
        raise PolarConfigError(f"Config field grid.{key} must be strictly increasing.")
    return tuple(values)


@dataclass(frozen=True)
class PolarProviderConfig:
    """One ordered provider adapter declaration without eager backend loading."""

    kind: str
    executable: str | None = None
    backend_version: str | None = None
    version_timeout_s: float = 5.0

    def __post_init__(self) -> None:
        if self.kind not in _PROVIDER_FIELDS:
            raise ValueError(f"Unsupported polar provider kind {self.kind!r}.")
        if self.kind == "neuralfoil" and (
            self.executable is not None or self.backend_version is not None
        ):
            raise ValueError("NeuralFoil does not accept executable/backend_version.")
        if self.kind == "xfoil" and (
            not isinstance(self.executable, str) or not self.executable
        ):
            raise ValueError("XFOIL provider requires a non-empty executable.")
        if self.backend_version is not None and (
            not isinstance(self.backend_version, str) or not self.backend_version
        ):
            raise ValueError("backend_version must be a non-empty string or None.")
        if (
            isinstance(self.version_timeout_s, bool)
            or not isinstance(self.version_timeout_s, (int, float))
            or not math.isfinite(float(self.version_timeout_s))
            or self.version_timeout_s <= 0.0
        ):
            raise ValueError("version_timeout_s must be positive and finite.")

    def as_mapping(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "executable": self.executable,
            "backend_version": self.backend_version,
            "version_timeout_s": self.version_timeout_s,
        }


@dataclass(frozen=True)
class PolarCacheConfig:
    """Optional cache location and process-lock policy."""

    enabled: bool = False
    root: Path | None = None
    lock_policy: PolarCacheLockPolicy = PolarCacheLockPolicy()

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be bool.")
        if self.enabled and not isinstance(self.root, Path):
            raise ValueError("Enabled cache requires a root path.")
        if not self.enabled and self.root is not None:
            raise ValueError("Disabled cache cannot declare a root path.")
        if not isinstance(self.lock_policy, PolarCacheLockPolicy):
            raise TypeError("lock_policy must be a PolarCacheLockPolicy.")

    def build(self) -> FilesystemPolarCache | None:
        if not self.enabled:
            return None
        return FilesystemPolarCache(self.root, lock_policy=self.lock_policy)

    def as_mapping(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "root": str(self.root) if self.root is not None else None,
            "lock_policy": {
                "wait_timeout_s": self.lock_policy.wait_timeout_s,
                "initial_poll_interval_s": self.lock_policy.initial_poll_interval_s,
                "max_poll_interval_s": self.lock_policy.max_poll_interval_s,
                "backoff_factor": self.lock_policy.backoff_factor,
            },
        }


@dataclass(frozen=True)
class PolarHealthConfig:
    """Optional process-local health registry and its circuit policy."""

    enabled: bool = False
    policy: PolarProviderHealthPolicy = PolarProviderHealthPolicy()

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be bool.")
        if not isinstance(self.policy, PolarProviderHealthPolicy):
            raise TypeError("policy must be a PolarProviderHealthPolicy.")

    def build(self) -> PolarProviderHealthRegistry | None:
        if not self.enabled:
            return None
        return PolarProviderHealthRegistry(self.policy)

    def as_mapping(self) -> dict[str, object]:
        return {"enabled": self.enabled, "policy": self.policy.__dict__}


PolarProviderFactory = Callable[[PolarProviderConfig], PolarProvider]


@dataclass(frozen=True)
class PolarFamilyConfig:
    """Validated static config from which one runtime can be constructed."""

    source_path: Path
    source_sha256: str
    plan: PolarFamilyGenerationPlan
    providers: tuple[PolarProviderConfig, ...]
    retry_policy: PolarRetryPolicy
    cache: PolarCacheConfig
    health: PolarHealthConfig
    result_policy: PolarResultQualificationPolicy
    batch_policy: PolarFamilyBatchPolicy
    acceptance_criteria: PolarAcceptanceCriteria

    def __post_init__(self) -> None:
        if not isinstance(self.source_path, Path) or not self.source_path.is_absolute():
            raise ValueError("source_path must be an absolute Path.")
        if (
            not isinstance(self.source_sha256, str)
            or len(self.source_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.source_sha256
            )
        ):
            raise ValueError("source_sha256 must be a lowercase SHA-256 digest.")
        if not isinstance(self.plan, PolarFamilyGenerationPlan):
            raise TypeError("plan must be a PolarFamilyGenerationPlan.")
        if not self.providers or not all(
            isinstance(provider, PolarProviderConfig) for provider in self.providers
        ):
            raise TypeError("providers must contain PolarProviderConfig values.")
        kinds = tuple(provider.kind for provider in self.providers)
        if len(set(kinds)) != len(kinds):
            raise ValueError("providers must not repeat a provider kind.")
        expected = (
            (self.retry_policy, PolarRetryPolicy, "retry_policy"),
            (self.cache, PolarCacheConfig, "cache"),
            (self.health, PolarHealthConfig, "health"),
            (
                self.result_policy,
                PolarResultQualificationPolicy,
                "result_policy",
            ),
            (self.batch_policy, PolarFamilyBatchPolicy, "batch_policy"),
            (
                self.acceptance_criteria,
                PolarAcceptanceCriteria,
                "acceptance_criteria",
            ),
        )
        for value, expected_type, name in expected:
            if not isinstance(value, expected_type):
                raise TypeError(f"{name} must be a {expected_type.__name__}.")
        if self.result_policy.minimum_usable_fraction != 1.0:
            raise ValueError("Polar family config requires full usable alpha coverage.")
        if self.result_policy.minimum_usable_points > len(
            self.plan.request_template.alpha_rad
        ):
            raise ValueError(
                "minimum_usable_points cannot exceed the configured alpha count."
            )
        unsupported = tuple(
            request
            for request in self.plan.requests
            if not any(
                _provider_supports(provider.kind, request)
                for provider in self.providers
            )
        )
        if unsupported:
            first = unsupported[0]
            raise ValueError(
                "No configured provider can satisfy grid request "
                f"Mach={first.mach:g}, Reynolds={first.reynolds:g}."
            )

    def build_runtime(
        self,
        provider_factories: Mapping[str, PolarProviderFactory] | None = None,
    ) -> "PolarFamilyRuntime":
        factories = dict(
            _default_provider_factories()
            if provider_factories is None
            else provider_factories
        )
        unknown = sorted(set(factories) - set(_PROVIDER_FIELDS))
        if unknown:
            raise PolarConfigError(
                "Unknown provider factory kind(s): " + ", ".join(unknown) + "."
            )
        built: list[PolarProvider] = []
        for index, provider in enumerate(self.providers):
            factory = factories.get(provider.kind)
            if factory is None:
                raise PolarConfigError(
                    f"No provider factory configured for providers[{index}] "
                    f"kind {provider.kind!r}."
                )
            built.append(factory(provider))
        return _build(
            PolarFamilyRuntime,
            "runtime",
            config=self,
            providers=tuple(built),
            cache=self.cache.build(),
            health_registry=self.health.build(),
        )

    def as_mapping(self) -> dict[str, object]:
        return {
            "schema_version": POLAR_CONFIG_SCHEMA_VERSION,
            "source_path": str(self.source_path),
            "source_sha256": self.source_sha256,
            "plan": self.plan.as_mapping(),
            "providers": tuple(provider.as_mapping() for provider in self.providers),
            "retry_policy": self.retry_policy.__dict__,
            "cache": self.cache.as_mapping(),
            "health": self.health.as_mapping(),
            "result_policy": self.result_policy.as_mapping(),
            "batch_policy": self.batch_policy.as_mapping(),
            "acceptance_criteria": self.acceptance_criteria.as_mapping(),
        }


@dataclass(frozen=True)
class PolarFamilyRuntime:
    """Instantiated providers and stateful services bound from one config."""

    config: PolarFamilyConfig
    providers: tuple[PolarProvider, ...]
    cache: FilesystemPolarCache | None
    health_registry: PolarProviderHealthRegistry | None

    def __post_init__(self) -> None:
        if not isinstance(self.config, PolarFamilyConfig):
            raise TypeError("config must be a PolarFamilyConfig.")
        if len(self.providers) != len(self.config.providers):
            raise ValueError("Runtime providers must match configured provider count.")
        if not all(isinstance(provider, PolarProvider) for provider in self.providers):
            raise TypeError("Runtime providers must satisfy the PolarProvider contract.")
        identities = tuple(provider.identity for provider in self.providers)
        if len(set(identities)) != len(identities):
            raise ValueError("Runtime providers must have unique identities.")
        if self.health_registry is not None and not isinstance(
            self.health_registry, PolarProviderHealthRegistry
        ):
            raise TypeError(
                "health_registry must be a PolarProviderHealthRegistry or None."
            )
        if self.config.cache.enabled != (self.cache is not None):
            raise ValueError("Runtime cache must match configured cache enablement.")
        if self.config.health.enabled != (self.health_registry is not None):
            raise ValueError("Runtime health registry must match configured enablement.")

    def generate(self) -> PolarFamilyBatchResult:
        return generate_polar_family_batch(
            self.providers,
            self.config.plan,
            policy=self.config.batch_policy,
            retry_policy=self.config.retry_policy,
            cache=self.cache,
            health_registry=self.health_registry,
            result_policy=self.config.result_policy,
        )


def load_polar_family_config(path: str | Path) -> PolarFamilyConfig:
    """Load and bind one strict version-1 polar-family TOML/JSON document."""
    source_path = Path(path).resolve()
    document, source_sha256 = _read_document(source_path)
    _reject_unknown(document, _ROOT_FIELDS, "root")
    if document.get("schema_version") != POLAR_CONFIG_SCHEMA_VERSION:
        raise PolarConfigError(
            "Unsupported schema_version "
            f"{document.get('schema_version')!r}; expected "
            f"{POLAR_CONFIG_SCHEMA_VERSION}."
        )

    request_raw = _table(document, "request", required=True)
    grid_raw = _table(document, "grid", required=True)
    _reject_unknown(request_raw, _REQUEST_FIELDS, "request")
    _reject_unknown(grid_raw, _GRID_FIELDS, "grid")
    airfoil_file = _required(request_raw, "airfoil_file", "request")
    if not isinstance(airfoil_file, str) or not airfoil_file:
        raise PolarConfigError("Config field request.airfoil_file must be non-empty.")
    airfoil_path = (source_path.parent / airfoil_file).resolve()
    airfoil_id = request_raw.get("airfoil_id")
    if airfoil_id is not None and (
        not isinstance(airfoil_id, str) or not airfoil_id
    ):
        raise PolarConfigError("Config field request.airfoil_id must be non-empty.")
    file_format = request_raw.get("airfoil_format", "auto")
    if not isinstance(file_format, str) or file_format not in {
        "auto",
        "selig",
        "lednicer",
        "csv",
    }:
        raise PolarConfigError(
            f"Unsupported request.airfoil_format {file_format!r}."
        )
    try:
        airfoil = load_airfoil_coordinates(
            airfoil_path,
            airfoil_id=airfoil_id,
            file_format=file_format,
        )
    except ValueError as error:
        raise PolarConfigError(str(error)) from error

    reynolds_grid = _numeric_grid(grid_raw, "reynolds", positive=True)
    mach_grid = _numeric_grid(grid_raw, "mach", positive=False)
    scenario_id = request_raw.get("scenario_id", "default")
    if not isinstance(scenario_id, str) or not scenario_id:
        raise PolarConfigError("Config field request.scenario_id must be non-empty.")
    request = _build(
        PolarGenerationRequest,
        "request",
        airfoil=airfoil,
        alpha_rad=_angles(request_raw),
        reynolds=reynolds_grid[0],
        mach=mach_grid[0],
        n_crit=_number(request_raw, "n_crit", "request", 9.0),
        xtr_upper=_number(request_raw, "xtr_upper", "request", 1.0),
        xtr_lower=_number(request_raw, "xtr_lower", "request", 1.0),
        max_iterations=_integer(
            request_raw, "max_iterations", "request", None, minimum=1
        ),
        timeout_s=_time(request_raw, "timeout", "request", "30 s"),
        scenario_id=scenario_id,
    )
    plan = _build(
        PolarFamilyGenerationPlan,
        "grid",
        request_template=request,
        reynolds_grid=reynolds_grid,
        mach_grid=mach_grid,
    )

    providers = _parse_providers(document)
    retry_policy = _parse_retry(document)
    cache = _parse_cache(document, source_path)
    health = _parse_health(document)
    result_policy = _parse_qualification(document)
    batch_policy = _parse_batch(document)
    acceptance = _parse_acceptance(document)
    return _build(
        PolarFamilyConfig,
        "root",
        source_path=source_path,
        source_sha256=source_sha256,
        plan=plan,
        providers=providers,
        retry_policy=retry_policy,
        cache=cache,
        health=health,
        result_policy=result_policy,
        batch_policy=batch_policy,
        acceptance_criteria=acceptance,
    )


def _parse_providers(document: Mapping[str, Any]) -> tuple[PolarProviderConfig, ...]:
    raw = _required(document, "providers", "root")
    if not isinstance(raw, list) or not raw or not all(
        isinstance(item, Mapping) for item in raw
    ):
        raise PolarConfigError("Config field providers must be a non-empty array.")
    providers: list[PolarProviderConfig] = []
    for index, item in enumerate(raw):
        kind = item.get("kind")
        if not isinstance(kind, str) or kind not in _PROVIDER_FIELDS:
            raise PolarConfigError(
                f"Unsupported providers[{index}].kind {kind!r}."
            )
        _reject_unknown(item, _PROVIDER_FIELDS[kind], f"providers[{index}]")
        executable = item.get("executable", "xfoil") if kind == "xfoil" else None
        backend_version = item.get("backend_version")
        if backend_version is not None and not isinstance(backend_version, str):
            raise PolarConfigError(
                f"Config field providers[{index}].backend_version must be a string."
            )
        providers.append(
            _build(
                PolarProviderConfig,
                f"providers[{index}]",
                kind=kind,
                executable=executable,
                backend_version=backend_version,
                version_timeout_s=(
                    _time(item, "version_timeout", f"providers[{index}]", "5 s")
                    if kind == "xfoil"
                    else 5.0
                ),
            )
        )
    return tuple(providers)


def _parse_retry(document: Mapping[str, Any]) -> PolarRetryPolicy:
    raw = _table(document, "retry")
    _reject_unknown(raw, _RETRY_FIELDS, "retry")
    return _build(
        PolarRetryPolicy,
        "retry",
        max_attempts=_integer(raw, "max_attempts", "retry", 2, minimum=1),
        initial_backoff_s=_time(raw, "initial_backoff", "retry", "50 ms"),
        max_backoff_s=_time(raw, "max_backoff", "retry", "500 ms"),
        backoff_factor=_number(raw, "backoff_factor", "retry", 2.0),
        retry_timeouts=_bool(raw, "retry_timeouts", "retry", True),
        retry_execution_errors=_bool(
            raw, "retry_execution_errors", "retry", False
        ),
    )


def _parse_cache(document: Mapping[str, Any], source_path: Path) -> PolarCacheConfig:
    raw = _table(document, "cache")
    _reject_unknown(raw, _CACHE_FIELDS, "cache")
    enabled = _bool(raw, "enabled", "cache", False)
    root_value = raw.get("root")
    if root_value is not None and (
        not isinstance(root_value, str) or not root_value
    ):
        raise PolarConfigError("Config field cache.root must be a non-empty string.")
    root = (
        (source_path.parent / root_value).resolve()
        if enabled and root_value is not None
        else None
    )
    if enabled and root is None:
        raise PolarConfigError("Enabled cache requires config field cache.root.")
    if not enabled and root_value is not None:
        raise PolarConfigError("Disabled cache cannot declare cache.root.")
    lock = _table(raw, "lock")
    _reject_unknown(lock, _LOCK_FIELDS, "cache.lock")
    if not enabled and lock:
        raise PolarConfigError("Disabled cache cannot declare cache.lock settings.")
    lock_policy = _build(
        PolarCacheLockPolicy,
        "cache.lock",
        wait_timeout_s=_time(lock, "wait_timeout", "cache.lock", "60 s"),
        initial_poll_interval_s=_time(
            lock, "initial_poll_interval", "cache.lock", "10 ms"
        ),
        max_poll_interval_s=_time(
            lock, "max_poll_interval", "cache.lock", "250 ms"
        ),
        backoff_factor=_number(lock, "backoff_factor", "cache.lock", 1.5),
    )
    return _build(
        PolarCacheConfig,
        "cache",
        enabled=enabled,
        root=root,
        lock_policy=lock_policy,
    )


def _parse_health(document: Mapping[str, Any]) -> PolarHealthConfig:
    raw = _table(document, "health")
    _reject_unknown(raw, _HEALTH_FIELDS, "health")
    enabled = _bool(raw, "enabled", "health", False)
    if not enabled and set(raw) - {"enabled"}:
        raise PolarConfigError(
            "Disabled health cannot declare circuit policy settings."
        )
    policy = _build(
        PolarProviderHealthPolicy,
        "health",
        failure_threshold=_integer(
            raw, "failure_threshold", "health", 3, minimum=1
        ),
        recovery_timeout_s=_time(
            raw, "recovery_timeout", "health", "30 s"
        ),
        count_unavailable_errors=_bool(
            raw, "count_unavailable_errors", "health", True
        ),
        count_timeout_errors=_bool(raw, "count_timeout_errors", "health", True),
        count_execution_errors=_bool(
            raw, "count_execution_errors", "health", True
        ),
        count_provider_errors=_bool(
            raw, "count_provider_errors", "health", True
        ),
        isolate_unexpected_errors=_bool(
            raw, "isolate_unexpected_errors", "health", True
        ),
        count_unexpected_errors=_bool(
            raw, "count_unexpected_errors", "health", True
        ),
    )
    return _build(
        PolarHealthConfig,
        "health",
        enabled=enabled,
        policy=policy,
    )


def _parse_qualification(
    document: Mapping[str, Any],
) -> PolarResultQualificationPolicy:
    raw = _table(document, "qualification")
    _reject_unknown(raw, _QUALIFICATION_FIELDS, "qualification")
    fraction = _number(
        raw, "minimum_usable_fraction", "qualification", 1.0
    )
    if fraction != 1.0:
        raise PolarConfigError(
            "Config field qualification.minimum_usable_fraction must be 1.0 "
            "for PolarFamily generation."
        )
    return _build(
        PolarResultQualificationPolicy,
        "qualification",
        minimum_usable_fraction=fraction,
        minimum_usable_points=_integer(
            raw, "minimum_usable_points", "qualification", 2, minimum=2
        ),
        allow_low_confidence=_bool(
            raw, "allow_low_confidence", "qualification", True
        ),
    )


def _parse_batch(document: Mapping[str, Any]) -> PolarFamilyBatchPolicy:
    raw = _table(document, "batch")
    _reject_unknown(raw, _BATCH_FIELDS, "batch")
    return _build(
        PolarFamilyBatchPolicy,
        "batch",
        failure_mode=raw.get("failure_mode", "fail_fast"),
        subgrid_policy=raw.get("subgrid_policy", "none"),
    )


def _parse_acceptance(document: Mapping[str, Any]) -> PolarAcceptanceCriteria:
    raw = _table(document, "acceptance")
    _reject_unknown(raw, _ACCEPTANCE_FIELDS, "acceptance")
    defaults = PolarAcceptanceCriteria()
    tolerances = {}
    for name in ("cl", "cd", "cm"):
        value = _table(raw, name)
        _reject_unknown(value, _TOLERANCE_FIELDS, f"acceptance.{name}")
        default = getattr(defaults, name)
        tolerances[name] = _build(
            PolarErrorTolerance,
            f"acceptance.{name}",
            absolute=_number(value, "absolute", f"acceptance.{name}", default.absolute),
            relative=_number(value, "relative", f"acceptance.{name}", default.relative),
        )
    return _build(
        PolarAcceptanceCriteria,
        "acceptance",
        **tolerances,
        minimum_coverage=_number(
            raw, "minimum_coverage", "acceptance", defaults.minimum_coverage
        ),
        require_usable_match=_bool(
            raw,
            "require_usable_match",
            "acceptance",
            defaults.require_usable_match,
        ),
    )


def _default_provider_factories() -> Mapping[str, PolarProviderFactory]:
    def xfoil(config: PolarProviderConfig) -> PolarProvider:
        from ..providers import XfoilProvider

        return XfoilProvider(
            executable=config.executable,
            backend_version=config.backend_version,
            version_timeout_s=config.version_timeout_s,
        )

    def neuralfoil(config: PolarProviderConfig) -> PolarProvider:
        from ..providers import NeuralFoilProvider

        return NeuralFoilProvider()

    return {"xfoil": xfoil, "neuralfoil": neuralfoil}


def _provider_supports(kind: str, request: PolarGenerationRequest) -> bool:
    from ..providers import NeuralFoilProvider, XfoilProvider

    capabilities = {
        "xfoil": XfoilProvider.capabilities,
        "neuralfoil": NeuralFoilProvider.capabilities,
    }[kind]
    try:
        request.validate_capabilities(capabilities)
    except PolarProviderCapabilityError:
        return False
    return True


def _build(factory: Callable[..., Any], path: str, **kwargs: Any) -> Any:
    try:
        return factory(**kwargs)
    except PolarConfigError:
        raise
    except (TypeError, ValueError) as error:
        raise PolarConfigError(f"Invalid {path} configuration: {error}") from error
