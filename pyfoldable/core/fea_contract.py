"""Fail-closed PR-09 preparation and ANSYS FEA result contract."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping


FEA_CONTRACT_SCHEMA_VERSION = 1
MaterialModelKind = Literal["isotropic", "orthotropic"]


def _finite(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number.")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite.")
    return result


def _nonempty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty.")


@dataclass(frozen=True)
class CADRevisionIdentity:
    design_id: str
    revision: str
    filename: str
    file_format: str
    sha256: str
    length_unit: str
    coordinate_frame: str

    def __post_init__(self) -> None:
        for name in (
            "design_id", "revision", "filename", "file_format", "length_unit",
            "coordinate_frame",
        ):
            _nonempty(name, getattr(self, name))
        if re.fullmatch(r"[0-9a-f]{64}", self.sha256) is None:
            raise ValueError("sha256 must contain 64 lowercase hexadecimal characters.")

    def as_mapping(self) -> Mapping[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class FEAMaterialIdentity:
    id: str
    model: MaterialModelKind
    source: str
    property_names: tuple[str, ...]
    qualification: str

    def __post_init__(self) -> None:
        for name in ("id", "source", "qualification"):
            _nonempty(name, getattr(self, name))
        if self.model not in {"isotropic", "orthotropic"}:
            raise ValueError("model must be isotropic or orthotropic.")
        if not self.property_names or len(set(self.property_names)) != len(
            self.property_names
        ):
            raise ValueError("property_names must be non-empty and unique.")
        if self.model == "orthotropic":
            required = {
                "density_kg_m3",
                "elastic_modulus_x_pa",
                "elastic_modulus_y_pa",
                "elastic_modulus_z_pa",
                "poisson_xy",
                "shear_modulus_xy_pa",
                "allowable_x_pa",
                "allowable_y_pa",
            }
            if not required.issubset(self.property_names):
                raise ValueError(
                    "An orthotropic material card requires directional elastic "
                    "and allowable properties."
                )

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "id": self.id,
            "model": self.model,
            "source": self.source,
            "property_names": list(self.property_names),
            "qualification": self.qualification,
        }


@dataclass(frozen=True)
class FEALoadCase:
    id: str
    analysis_type: str
    load_source_id: str
    required_metric_units: Mapping[str, str]

    def __post_init__(self) -> None:
        for name in ("id", "analysis_type", "load_source_id"):
            _nonempty(name, getattr(self, name))
        if not self.required_metric_units:
            raise ValueError("required_metric_units must not be empty.")
        for metric, unit in self.required_metric_units.items():
            _nonempty("metric", metric)
            _nonempty(f"unit for {metric}", unit)

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "id": self.id,
            "analysis_type": self.analysis_type,
            "load_source_id": self.load_source_id,
            "required_metric_units": dict(self.required_metric_units),
        }


@dataclass(frozen=True)
class FEAAcceptancePolicy:
    maximum_mesh_change_percent: float = 5.0
    maximum_force_balance_error_percent: float = 1.0
    metric_limits: Mapping[str, tuple[float | None, float | None]] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        _finite("maximum_mesh_change_percent", self.maximum_mesh_change_percent)
        _finite(
            "maximum_force_balance_error_percent",
            self.maximum_force_balance_error_percent,
        )
        if self.maximum_mesh_change_percent <= 0.0:
            raise ValueError("maximum_mesh_change_percent must be greater than zero.")
        if self.maximum_force_balance_error_percent < 0.0:
            raise ValueError(
                "maximum_force_balance_error_percent must not be negative."
            )
        for metric, limits in self.metric_limits.items():
            _nonempty("metric limit name", metric)
            if len(limits) != 2 or limits == (None, None):
                raise ValueError("Every metric limit needs a minimum or maximum.")
            low, high = limits
            if low is not None:
                _finite(f"{metric}.minimum", low)
            if high is not None:
                _finite(f"{metric}.maximum", high)
            if low is not None and high is not None and low > high:
                raise ValueError("Metric minimum cannot exceed its maximum.")

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "maximum_mesh_change_percent": self.maximum_mesh_change_percent,
            "maximum_force_balance_error_percent": (
                self.maximum_force_balance_error_percent
            ),
            "metric_limits": {
                key: {"minimum": value[0], "maximum": value[1]}
                for key, value in self.metric_limits.items()
            },
        }


@dataclass(frozen=True)
class FEAProjectManifest:
    id: str
    cad: CADRevisionIdentity
    materials: tuple[FEAMaterialIdentity, ...]
    load_cases: tuple[FEALoadCase, ...]
    policy: FEAAcceptancePolicy

    def __post_init__(self) -> None:
        _nonempty("id", self.id)
        if not isinstance(self.cad, CADRevisionIdentity):
            raise TypeError("cad must be CADRevisionIdentity.")
        if not self.materials or not all(
            isinstance(value, FEAMaterialIdentity) for value in self.materials
        ):
            raise TypeError("materials must contain FEAMaterialIdentity values.")
        if len({value.id for value in self.materials}) != len(self.materials):
            raise ValueError("Material ids must be unique.")
        if not self.load_cases or not all(
            isinstance(value, FEALoadCase) for value in self.load_cases
        ):
            raise TypeError("load_cases must contain FEALoadCase values.")
        if len({value.id for value in self.load_cases}) != len(self.load_cases):
            raise ValueError("Load case ids must be unique.")
        if not isinstance(self.policy, FEAAcceptancePolicy):
            raise TypeError("policy must be FEAAcceptancePolicy.")
        declared_metrics = {
            metric
            for case in self.load_cases
            for metric in case.required_metric_units
        }
        unknown_limits = set(self.policy.metric_limits) - declared_metrics
        if unknown_limits:
            raise ValueError(
                "Policy limit references an undeclared metric: "
                f"{sorted(unknown_limits)}"
            )

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "schema_version": FEA_CONTRACT_SCHEMA_VERSION,
            "id": self.id,
            "cad": dict(self.cad.as_mapping()),
            "materials": [dict(value.as_mapping()) for value in self.materials],
            "load_cases": [dict(value.as_mapping()) for value in self.load_cases],
            "policy": dict(self.policy.as_mapping()),
        }


@dataclass(frozen=True)
class FEAMeshLevel:
    id: str
    element_count: int
    convergence_metric_value: float

    def __post_init__(self) -> None:
        _nonempty("id", self.id)
        if not isinstance(self.element_count, int) or isinstance(
            self.element_count, bool
        ) or self.element_count <= 0:
            raise ValueError("element_count must be a positive integer.")
        _finite("convergence_metric_value", self.convergence_metric_value)

    def as_mapping(self) -> Mapping[str, Any]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class FEAResultCase:
    case_id: str
    cad_sha256: str
    material_ids: tuple[str, ...]
    solver_name: str
    solver_version: str
    converged: bool
    mesh_convergence_metric: str
    mesh_levels: tuple[FEAMeshLevel, ...]
    force_balance_error_percent: float
    metrics: Mapping[str, tuple[float, str]]
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("case_id", "solver_name", "solver_version"):
            _nonempty(name, getattr(self, name))
        _nonempty("mesh_convergence_metric", self.mesh_convergence_metric)
        if re.fullmatch(r"[0-9a-f]{64}", self.cad_sha256) is None:
            raise ValueError("cad_sha256 must be a SHA-256 digest.")
        if not self.material_ids or len(set(self.material_ids)) != len(
            self.material_ids
        ):
            raise ValueError("material_ids must be non-empty and unique.")
        if not isinstance(self.converged, bool):
            raise TypeError("converged must be boolean.")
        if not all(isinstance(value, FEAMeshLevel) for value in self.mesh_levels):
            raise TypeError("mesh_levels must contain FEAMeshLevel values.")
        _finite("force_balance_error_percent", self.force_balance_error_percent)
        if self.force_balance_error_percent < 0.0:
            raise ValueError("force_balance_error_percent must not be negative.")
        for metric, value_and_unit in self.metrics.items():
            _nonempty("metric", metric)
            if len(value_and_unit) != 2:
                raise ValueError("Each metric must contain a value and unit.")
            _finite(metric, value_and_unit[0])
            _nonempty(f"unit for {metric}", value_and_unit[1])

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "case_id": self.case_id,
            "cad_sha256": self.cad_sha256,
            "material_ids": list(self.material_ids),
            "solver_name": self.solver_name,
            "solver_version": self.solver_version,
            "converged": self.converged,
            "mesh_convergence_metric": self.mesh_convergence_metric,
            "mesh_levels": [dict(value.as_mapping()) for value in self.mesh_levels],
            "force_balance_error_percent": self.force_balance_error_percent,
            "metrics": {
                key: {"value": value[0], "unit": value[1]}
                for key, value in self.metrics.items()
            },
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class FEACaseDecision:
    case_id: str
    failures: tuple[str, ...]
    mesh_change_percent: float | None

    @property
    def passed(self) -> bool:
        return not self.failures

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "case_id": self.case_id,
            "passed": self.passed,
            "failures": list(self.failures),
            "mesh_change_percent": self.mesh_change_percent,
        }


@dataclass(frozen=True)
class FEABundleDecision:
    manifest_id: str
    cases: tuple[FEACaseDecision, ...]
    missing_case_ids: tuple[str, ...]

    @property
    def software_gate_passed(self) -> bool:
        return not self.missing_case_ids and bool(self.cases) and all(
            case.passed for case in self.cases
        )

    @property
    def physical_qualification(self) -> bool:
        return False

    @property
    def state(self) -> str:
        if self.software_gate_passed:
            return "software_pass_physical_evidence_pending"
        return "blocked_incomplete_or_invalid_fea_evidence"

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "schema_version": FEA_CONTRACT_SCHEMA_VERSION,
            "manifest_id": self.manifest_id,
            "state": self.state,
            "software_gate_passed": self.software_gate_passed,
            "physical_qualification": self.physical_qualification,
            "missing_case_ids": list(self.missing_case_ids),
            "cases": [dict(case.as_mapping()) for case in self.cases],
        }


def assess_fea_result_bundle(
    manifest: FEAProjectManifest,
    results: tuple[FEAResultCase, ...],
) -> FEABundleDecision:
    """Validate an ANSYS result bundle without inventing engineering limits."""
    if not isinstance(manifest, FEAProjectManifest):
        raise TypeError("manifest must be FEAProjectManifest.")
    if not all(isinstance(result, FEAResultCase) for result in results):
        raise TypeError("results must contain FEAResultCase values.")
    result_ids = tuple(result.case_id for result in results)
    if len(set(result_ids)) != len(result_ids):
        raise ValueError("Result case ids must be unique.")
    declared = {case.id: case for case in manifest.load_cases}
    unknown = set(result_ids) - set(declared)
    if unknown:
        raise ValueError(f"Unknown FEA result cases: {sorted(unknown)}")
    material_ids = {material.id for material in manifest.materials}
    decisions: list[FEACaseDecision] = []
    for result in results:
        case = declared[result.case_id]
        failures: list[str] = []
        if result.cad_sha256 != manifest.cad.sha256:
            failures.append("cad_sha256_mismatch")
        if not set(result.material_ids).issubset(material_ids):
            failures.append("material_identity_mismatch")
        if not result.converged:
            failures.append("solver_not_converged")
        if result.warnings:
            failures.append("solver_warnings_present")
        if len(result.mesh_levels) < 3:
            failures.append("mesh_levels_below_three")
            mesh_change = None
        else:
            counts = tuple(level.element_count for level in result.mesh_levels)
            if any(b <= a for a, b in zip(counts, counts[1:])):
                failures.append("mesh_element_counts_not_increasing")
            medium = result.mesh_levels[-2].convergence_metric_value
            fine = result.mesh_levels[-1].convergence_metric_value
            mesh_change = abs(fine - medium) / max(abs(fine), 1.0e-30) * 100.0
            if mesh_change > manifest.policy.maximum_mesh_change_percent:
                failures.append("mesh_change_above_limit")
        if result.mesh_convergence_metric not in case.required_metric_units:
            failures.append("mesh_convergence_metric_not_declared")
        elif result.mesh_convergence_metric not in result.metrics:
            failures.append("mesh_convergence_metric_missing")
        if (
            result.force_balance_error_percent
            > manifest.policy.maximum_force_balance_error_percent
        ):
            failures.append("force_balance_error_above_limit")
        for metric, required_unit in case.required_metric_units.items():
            if metric not in result.metrics:
                failures.append(f"missing_metric:{metric}")
                continue
            value, unit = result.metrics[metric]
            if unit != required_unit:
                failures.append(f"metric_unit_mismatch:{metric}")
                continue
            if metric in manifest.policy.metric_limits:
                low, high = manifest.policy.metric_limits[metric]
                if low is not None and value < low:
                    failures.append(f"metric_below_limit:{metric}")
                if high is not None and value > high:
                    failures.append(f"metric_above_limit:{metric}")
        decisions.append(FEACaseDecision(result.case_id, tuple(failures), mesh_change))
    missing = tuple(sorted(set(declared) - set(result_ids)))
    return FEABundleDecision(manifest.id, tuple(decisions), missing)
