"""Bounded two-profile BEM screening on one shared planform and condition.

The comparison boundary publishes each fully solved profile separately. It does
not rank a winner, sum profiles, or qualify a rotor. Provider failures, missing
coverage, and solver failures stay in the failure ledger.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import tempfile
from pathlib import Path
from typing import Any, Mapping

from pyfoldable.application.design_analysis import DesignAnalysisError, run_design_analysis
from pyfoldable.application.design_draft import DesignDraftInputs, build_design_draft
from pyfoldable.core.airfoil import airfoil_coordinate_sha256
from pyfoldable.core.bem import (
    BEMAnnulusSettings,
    _AIR_GAMMA,
    _AIR_GAS_CONSTANT_J_KG_K,
)
from pyfoldable.core.bem_rotor import BEMRotorSettings, _interpolate_station, _radial_limits
from pyfoldable.core.config import load_design_config
from pyfoldable.core.models import PropellerDesign
from pyfoldable.core.polar import PolarFamily
from pyfoldable.core.polar_family_generation import (
    PolarFamilyGenerationError,
    PolarFamilyGenerationPlan,
    generate_polar_family,
)
from pyfoldable.core.polar_orchestration import PolarRetryPolicy
from pyfoldable.core.profile_catalog import load_project_airfoil
from pyfoldable.core.providers import (
    PolarGenerationRequest,
    PolarProvider,
    PolarProviderError,
)
from pyfoldable.core.units import normalize_quantity


PROFILE_IDS = ("NACA0012", "NACA2412")
ANNULUS_COUNT = 40
MAX_BEM_CALLS = 4
SOLVES_PER_PROFILE = 2
ALPHA_STEP_RAD = math.radians(2.0)
SOURCE_DESIGN = "configs/designs/TIP_HINGED_250_CANONICAL.toml"
_PROVIDER_NAME = "xfoil-subprocess"
_ADAPTER_VERSION = "2"
_BACKEND_NAME = "XFOIL"
_EXPECTED_BACKEND_VERSION = "6.99"
_SOURCE_URL = "https://web.mit.edu/drela/Public/web/xfoil/xfoil6.99.tgz"
_SOURCE_SHA256 = "5c0250643f52ce0e75d7338ae2504ce7907f2d49a30f921826717b8ac12ebe40"
_FORTRAN_FLAGS = "-O2 -fdefault-real-8 -fallow-argument-mismatch"
_SCENARIO_ID = "two_profile_bem_screening"
_METRIC_KEYS = (
    "thrust_n",
    "torque_nm",
    "shaft_power_w",
    "thrust_coefficient",
    "torque_coefficient",
    "power_coefficient",
)
_CSV_FIELDS = (
    "section",
    "airfoil_id",
    "status",
    "thrust_n",
    "torque_nm",
    "shaft_power_w",
    "thrust_coefficient",
    "torque_coefficient",
    "power_coefficient",
    "propulsive_efficiency",
    "draft_sha256",
    "coordinate_sha256",
    "polar_content_sha256",
    "polar_coordinate_sha256",
    "geometry_sha256",
    "operating_condition_sha256",
    "repeatable",
    "bem_calls",
    "physical_qualification",
    "failure",
)


class ScreeningError(ValueError):
    """The screening contract was violated before a profile result could be kept."""


class _CallBudget:
    def __init__(self, limit: int, label: str) -> None:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ScreeningError(f"{label} budget must be a positive integer.")
        self.limit = limit
        self.label = label
        self.calls = 0

    def charge(self) -> None:
        if self.calls >= self.limit:
            raise ScreeningError(
                f"{self.label} budget of {self.limit} calls was exceeded."
            )
        self.calls += 1


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    """Stable JSON used for declaration and content hashes."""
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ScreeningError("Screening content must be finite JSON-safe data.") from exc


def _sha(value: Any) -> str:
    payload = value if isinstance(value, str) else canonical_json(value)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _source_path(repository_root: str | Path) -> Path:
    path = Path(repository_root) / SOURCE_DESIGN
    if not path.is_file():
        raise ScreeningError(f"Canonical design is missing: {SOURCE_DESIGN}.")
    return path


def _inputs(airfoil_id: str) -> DesignDraftInputs:
    return DesignDraftInputs(
        diameter="250 mm",
        hub_radius="18 mm",
        hinge_radius="100 mm",
        blade_count=2,
        airfoil_id=airfoil_id,
        chord_scale=1.0,
        twist_scale=1.0,
        preview_fold_angle="0 deg",
        angular_speed="7100 rpm",
        forward_speed="0 m/s",
        air_density="1.225 kg/m^3",
        dynamic_viscosity="1.81e-5 Pa*s",
        temperature="288.15 K",
        pressure="101325 Pa",
    )


def _load_draft(draft) -> tuple[PropellerDesign, float]:
    with tempfile.TemporaryDirectory(prefix="pyfoldable-screening-") as directory:
        path = Path(directory) / "draft.toml"
        path.write_text(draft.toml, encoding="utf-8")
        design = load_design_config(path)
    angle = normalize_quantity(
        design.metadata["preview_fold_angle"], "angle", field="preview_fold_angle"
    ).si_value
    return design, angle


def _geometry_document(design: PropellerDesign, preview_fold_angle_rad: float) -> dict[str, Any]:
    hinge = design.hinge
    if hinge is None:
        raise ScreeningError("The shared design has no hinge.")
    radius = design.blade.radius_m
    fully_open = all(
        abs(value) <= 1.0e-12
        for value in (
            preview_fold_angle_rad,
            hinge.deployed_angle_rad,
            hinge.axial_offset_m,
            hinge.tangential_offset_m,
        )
    )
    if not fully_open:
        raise ScreeningError("The shared pose is not fully open and zero-offset.")
    return {
        "diameter_m": design.blade.diameter_m,
        "hub_radius_m": design.blade.hub_radius_m,
        "blade_count": design.blade.blade_count,
        "hinge": {
            "radius_m": hinge.radius_m,
            "axial_offset_m": hinge.axial_offset_m,
            "tangential_offset_m": hinge.tangential_offset_m,
            "axis_azimuth_rad": hinge.axis_azimuth_rad,
            "axis_elevation_rad": hinge.axis_elevation_rad,
            "deployed_angle_rad": hinge.deployed_angle_rad,
            "stowed_angle_rad": hinge.stowed_angle_rad,
            "stop_angle_rad": hinge.stop_angle_rad,
        },
        "preview_fold_angle_rad": preview_fold_angle_rad,
        "fully_open_zero_offset": True,
        "stations": [
            {
                "r_over_R": station.r_over_R,
                "radius_m": station.r_over_R * radius,
                "chord_m": station.chord_m,
                "twist_rad": station.twist_rad,
            }
            for station in design.blade.stations
        ],
    }


def _condition_document(design: PropellerDesign) -> dict[str, Any]:
    if len(design.operating_conditions) != 1:
        raise ScreeningError("The shared design must declare one operating condition.")
    condition = design.operating_conditions[0]
    return {
        "id": condition.id,
        "angular_speed_rad_s": condition.angular_speed_rad_s,
        "forward_speed_m_s": condition.forward_speed_m_s,
        "air_density_kg_m3": condition.air_density_kg_m3,
        "dynamic_viscosity_pa_s": condition.dynamic_viscosity_pa_s,
        "temperature_k": condition.temperature_k,
        "pressure_pa": condition.pressure_pa,
    }


def _query_state(condition, radius: float, chord: float, twist: float, psi: float) -> tuple[float, float, float]:
    axial = condition.forward_speed_m_s
    tangential = condition.angular_speed_rad_s * radius
    external = math.hypot(axial, tangential)
    wa = 0.5 * axial + 0.5 * external * math.sin(psi)
    wt = 0.5 * tangential + 0.5 * external * math.cos(psi)
    relative = math.hypot(wa, wt)
    alpha = twist - math.atan2(wa, wt)
    reynolds = (
        condition.air_density_kg_m3 * relative * chord / condition.dynamic_viscosity_pa_s
    )
    mach = relative / math.sqrt(_AIR_GAMMA * _AIR_GAS_CONSTANT_J_KG_K * condition.temperature_k)
    return alpha, reynolds, mach


def _kinematic_envelope(design: PropellerDesign) -> dict[str, Any]:
    """Bound the positive-only psi search without calling the BEM kernel."""
    controls = BEMAnnulusSettings()
    if controls.loading_branch != "positive_only":
        raise ScreeningError("This screening declares only the positive_only branch.")
    blade = design.blade
    condition = design.operating_conditions[0]
    inner, outer, _extended = _radial_limits(blade, "station_span")
    width = (outer - inner) / ANNULUS_COUNT
    alphas: list[float] = []
    reynolds_values: list[float] = []
    mach_values: list[float] = []
    for index in range(ANNULUS_COUNT):
        midpoint = inner + (index + 0.5) * width
        station, _extrapolated = _interpolate_station(blade, midpoint)
        radius = station.r_over_R * blade.radius_m
        tangential = condition.angular_speed_rad_s * radius
        if tangential <= 0.0:
            raise ScreeningError("Annulus tangential speed must be positive.")
        psi_start = math.atan2(condition.forward_speed_m_s, tangential)
        psi_end = math.pi / 2.0 - controls.angle_tolerance_rad
        endpoint_states = tuple(
            _query_state(condition, radius, station.chord_m, station.twist_rad, psi)
            for psi in (psi_start, psi_end)
        )
        midpoint_state = _query_state(
            condition,
            radius,
            station.chord_m,
            station.twist_rad,
            0.5 * (psi_start + psi_end),
        )
        for sample_index, sample in enumerate(midpoint_state):
            lower = min(state[sample_index] for state in endpoint_states)
            upper = max(state[sample_index] for state in endpoint_states)
            if sample < lower - 1.0e-9 or sample > upper + 1.0e-9:
                raise ScreeningError(
                    "Kinematic query map is not bracketed by the psi endpoints."
                )
        for alpha, reynolds, mach in endpoint_states:
            alphas.append(alpha)
            reynolds_values.append(reynolds)
            mach_values.append(mach)
    alpha_min = min(alphas)
    alpha_max = max(alphas)
    reynolds_min = min(reynolds_values)
    reynolds_max = max(reynolds_values)
    mach_min = min(mach_values)
    mach_max = max(mach_values)
    if reynolds_max <= reynolds_min or mach_max <= 0.0:
        raise ScreeningError("Kinematic Reynolds/Mach envelope is degenerate.")
    alpha_grid = _step_grid(alpha_min, alpha_max, ALPHA_STEP_RAD)
    return {
        "derivation": (
            "positive_only psi endpoints at each station_span annulus midpoint; "
            "no induction solve and no post-failure expansion"
        ),
        "alpha_rad_min": alpha_min,
        "alpha_rad_max": alpha_max,
        "reynolds_min": reynolds_min,
        "reynolds_max": reynolds_max,
        "mach_min": mach_min,
        "mach_max": mach_max,
        "alpha_rad": list(alpha_grid),
        "reynolds_grid": [reynolds_min, reynolds_max],
        "mach_grid": [0.0, mach_max],
        "bracket_samples": controls.bracket_samples,
        "angle_tolerance_rad": controls.angle_tolerance_rad,
    }


def _step_grid(lower: float, upper: float, step: float) -> tuple[float, ...]:
    start = math.floor(lower / step + 1.0e-12) * step
    if start > lower:
        start -= step
    end = math.ceil(upper / step - 1.0e-12) * step
    if end < upper:
        end += step
    count = int(round((end - start) / step))
    values = tuple(start + index * step for index in range(count + 1))
    if not values or values[0] > lower or values[-1] < upper:
        raise ScreeningError("Alpha grid does not cover the kinematic envelope.")
    if any(later <= earlier for earlier, later in zip(values, values[1:])):
        raise ScreeningError("Alpha grid is not strictly increasing.")
    return values


def _materials(repository_root: str | Path):
    source = _source_path(repository_root)
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    loaded = []
    for airfoil_id in PROFILE_IDS:
        foil = load_project_airfoil(airfoil_id)
        if foil.id != airfoil_id:
            raise ScreeningError("Catalog airfoil id does not match the requested profile.")
        draft = build_design_draft(source, _inputs(airfoil_id), airfoil_definition=foil)
        design, angle = _load_draft(draft)
        loaded.append((airfoil_id, foil, draft, design, angle))
    documents = [
        (
            canonical_json(_geometry_document(design, angle)),
            canonical_json(_condition_document(design)),
        )
        for _airfoil_id, _foil, _draft, design, angle in loaded
    ]
    if len({item[0] for item in documents}) != 1 or len({item[1] for item in documents}) != 1:
        raise ScreeningError("Profile drafts do not share one geometry and operating condition.")
    return source_sha, loaded


def profile_bindings(repository_root: str | Path) -> dict[str, dict[str, str]]:
    """Profile-specific draft and coordinate hashes for the shared planform."""
    _source_sha, loaded = _materials(repository_root)
    bindings = {}
    for airfoil_id, foil, draft, design, angle in loaded:
        bindings[airfoil_id] = {
            "draft_sha256": draft.draft_sha256,
            "coordinate_sha256": airfoil_coordinate_sha256(foil),
            "geometry_sha256": _sha(_geometry_document(design, angle)),
            "operating_condition_sha256": _sha(_condition_document(design)),
        }
    return bindings


def build_shared_declaration(repository_root: str | Path) -> dict[str, Any]:
    """Hash the shared planform, condition, provider, envelope, and budget."""
    source_sha, loaded = _materials(repository_root)
    _airfoil_id, _foil, _draft, design, angle = loaded[0]
    geometry = _geometry_document(design, angle)
    condition = _condition_document(design)
    envelope = _kinematic_envelope(design)
    controls = BEMAnnulusSettings()
    cells = len(envelope["mach_grid"]) * len(envelope["reynolds_grid"])
    body = {
        "schema_version": 1,
        "study_id": _SCENARIO_ID,
        "physical_qualification": False,
        "profiles": list(PROFILE_IDS),
        "source_design": {"path": SOURCE_DESIGN, "sha256": source_sha},
        "geometry": geometry,
        "geometry_sha256": _sha(geometry),
        "operating_condition": condition,
        "operating_condition_sha256": _sha(condition),
        "solver": {
            "service_id": "pyfoldable.application.design_analysis",
            "solver": "pyfoldable.core.bem_rotor.solve_bem_rotor",
            "annulus_count": ANNULUS_COUNT,
            "radial_domain": "station_span",
            "bounds": "error",
            "loading_branch": controls.loading_branch,
            "bracket_samples": controls.bracket_samples,
            "angle_tolerance_rad": controls.angle_tolerance_rad,
            "rotational_augmentation": "disabled",
        },
        "provider": {
            "name": _PROVIDER_NAME,
            "adapter_version": _ADAPTER_VERSION,
            "backend_name": _BACKEND_NAME,
            "expected_backend_version": _EXPECTED_BACKEND_VERSION,
            "source_url": _SOURCE_URL,
            "source_sha256": _SOURCE_SHA256,
            "fortran_flags": _FORTRAN_FLAGS,
            "ubuntu_dfsg_package_allowed": False,
            "n_crit": 9.0,
            "xtr_upper": 1.0,
            "xtr_lower": 1.0,
            "repanel": True,
            "max_iterations": 80,
            "timeout_s": 90.0,
            "scenario_id": _SCENARIO_ID,
        },
        "query_envelope": envelope,
        "capture_budget": {
            "profiles": len(PROFILE_IDS),
            "cells_per_profile": cells,
            "max_provider_cells": cells * len(PROFILE_IDS),
            "annulus_count": ANNULUS_COUNT,
            "solves_per_profile": SOLVES_PER_PROFILE,
            "max_bem_calls": MAX_BEM_CALLS,
            "provider_attempts_per_cell": 1,
            "retry_timeouts": False,
            "retry_execution_errors": False,
            "expansion_allowed": False,
            "substitution_allowed": False,
        },
    }
    body["shared_declaration_sha256"] = _sha(
        {key: value for key, value in body.items() if key != "shared_declaration_sha256"}
    )
    text = canonical_json(body)
    parsed = json.loads(text)
    if canonical_json(parsed) != text:
        raise ScreeningError("Shared declaration is not JSON-stable.")
    return parsed


def _limited_provider(provider: PolarProvider, budget: _CallBudget):
    class _Limited:
        @property
        def identity(self):
            return provider.identity

        @property
        def capabilities(self):
            return provider.capabilities

        def generate(self, request):
            budget.charge()
            return provider.generate(request)

    return _Limited()


def _provider_matches(provider: PolarProvider, declaration: Mapping[str, Any]) -> bool:
    identity = provider.identity
    expected = declaration["provider"]
    return (
        identity.name == expected["name"]
        and identity.adapter_version == expected["adapter_version"]
        and identity.backend_name == expected["backend_name"]
        and identity.backend_version == expected["expected_backend_version"]
    )


def _table_document(table) -> dict[str, Any]:
    return json.loads(
        canonical_json(
            _plain(
                {
                    "airfoil_id": table.airfoil_id,
                    "reynolds": table.reynolds,
                    "mach": table.mach,
                    "alpha_rad": table.alpha_rad,
                    "cl": table.cl,
                    "cd": table.cd,
                    "cm": table.cm,
                    "source": table.source,
                    "scenario_id": table.scenario_id,
                    "metadata": table.metadata,
                }
            )
        )
    )


def _json_ready_family(family: PolarFamily) -> PolarFamily:
    return PolarFamily(tuple(type(table)(**_table_document(table)) for table in family.tables))


def _polar_content_sha256(family: PolarFamily) -> str:
    tables = [
        _table_document(table)
        for table in sorted(family.tables, key=lambda item: (item.mach, item.reynolds))
    ]
    return _sha(tables)


def _coordinate_hashes(family: PolarFamily) -> set[str]:
    hashes = set()
    for table in family.tables:
        metadata = table.metadata
        if not isinstance(metadata, Mapping):
            return set()
        value = metadata.get("airfoil_coordinate_sha256")
        if not isinstance(value, str):
            return set()
        hashes.add(value)
    return hashes


def _failure_text(exc: BaseException) -> str:
    parts: list[str] = []
    current: BaseException | None = exc
    while current is not None and len(parts) < 6:
        text = str(current).strip()
        if text and text not in parts:
            parts.append(text)
        current = current.__cause__
    if isinstance(exc, PolarFamilyGenerationError) and exc.failed_result is not None:
        unusable = [
            f"{math.degrees(point.alpha_rad):.6g} deg ({point.status})"
            for point in exc.failed_result.points
            if not point.usable
        ]
        if unusable:
            parts.append("Unusable polar points: " + ", ".join(unusable))
    return " | ".join(parts)


def _failure_record(
    airfoil_id: str,
    *,
    status: str,
    failure: str,
    declaration: Mapping[str, Any],
    bindings: Mapping[str, Mapping[str, str]],
    bem_calls: int = 0,
) -> dict[str, Any]:
    binding = bindings[airfoil_id]
    return {
        "airfoil_id": airfoil_id,
        "coordinate_sha256": binding["coordinate_sha256"],
        "draft_sha256": binding["draft_sha256"],
        "geometry_sha256": declaration["geometry_sha256"],
        "operating_condition_sha256": declaration["operating_condition_sha256"],
        "polar_content_sha256": None,
        "polar_coordinate_sha256": None,
        "status": status,
        "failure": failure,
        "repeatable": None,
        "bem_calls": bem_calls,
        "physical_qualification": False,
        "metrics": None,
        "source_bound_report": None,
    }


def _within_grid(metrics: Mapping[str, Any], envelope: Mapping[str, Any]) -> bool:
    query = metrics["polar_query_envelope"]
    tolerance = 1.0e-8

    def inside(value: float, lower: float, upper: float) -> bool:
        return lower - tolerance <= value <= upper + tolerance

    return (
        inside(query["alpha_rad_min"], envelope["alpha_rad"][0], envelope["alpha_rad"][-1])
        and inside(query["alpha_rad_max"], envelope["alpha_rad"][0], envelope["alpha_rad"][-1])
        and inside(query["reynolds_min"], envelope["reynolds_grid"][0], envelope["reynolds_grid"][-1])
        and inside(query["reynolds_max"], envelope["reynolds_grid"][0], envelope["reynolds_grid"][-1])
        and inside(query["mach_min"], envelope["mach_grid"][0], envelope["mach_grid"][-1])
        and inside(query["mach_max"], envelope["mach_grid"][0], envelope["mach_grid"][-1])
        and not metrics["clamped_dimensions"]
    )


def _metrics_from_report(report_json: str) -> dict[str, Any]:
    document = json.loads(report_json)
    rotor = document["rotor"]
    return {
        "thrust_n": rotor["thrust_n"],
        "torque_nm": rotor["torque_nm"],
        "shaft_power_w": rotor["shaft_power_w"],
        "thrust_coefficient": rotor["thrust_coefficient"],
        "torque_coefficient": rotor["torque_coefficient"],
        "power_coefficient": rotor["power_coefficient"],
        "propulsive_efficiency": rotor["propulsive_efficiency"],
        "polar_query_envelope": rotor["polar_query_envelope"],
        "clamped_dimensions": list(rotor["clamped_dimensions"]),
    }


def _execute_profile(
    declaration: Mapping[str, Any],
    airfoil_id: str,
    *,
    provider: PolarProvider,
    repository_root: Path,
    bindings: Mapping[str, Mapping[str, str]],
    bem_budget: _CallBudget,
    capture_budget: _CallBudget,
) -> dict[str, Any]:
    foil = load_project_airfoil(airfoil_id)
    coordinate = airfoil_coordinate_sha256(foil)
    if coordinate != bindings[airfoil_id]["coordinate_sha256"]:
        raise ScreeningError("Catalog coordinate hash changed while screening.")
    provider_declaration = declaration["provider"]
    envelope = declaration["query_envelope"]
    request = PolarGenerationRequest(
        airfoil=foil,
        alpha_rad=tuple(envelope["alpha_rad"]),
        reynolds=envelope["reynolds_grid"][0],
        mach=envelope["mach_grid"][0],
        n_crit=provider_declaration["n_crit"],
        xtr_upper=provider_declaration["xtr_upper"],
        xtr_lower=provider_declaration["xtr_lower"],
        max_iterations=provider_declaration["max_iterations"],
        timeout_s=provider_declaration["timeout_s"],
        scenario_id=provider_declaration["scenario_id"],
        options={"repanel": provider_declaration["repanel"]},
    )
    plan = PolarFamilyGenerationPlan(
        request,
        reynolds_grid=tuple(envelope["reynolds_grid"]),
        mach_grid=tuple(envelope["mach_grid"]),
    )
    if plan.cell_count != declaration["capture_budget"]["cells_per_profile"]:
        raise ScreeningError("Polar plan does not match the declared capture budget.")
    try:
        generated = generate_polar_family(
            (_limited_provider(provider, capture_budget),),
            plan,
            retry_policy=PolarRetryPolicy(
                max_attempts=declaration["capture_budget"]["provider_attempts_per_cell"],
                retry_timeouts=declaration["capture_budget"]["retry_timeouts"],
                retry_execution_errors=declaration["capture_budget"]["retry_execution_errors"],
            ),
        )
    except (PolarFamilyGenerationError, PolarProviderError) as exc:
        return _failure_record(
            airfoil_id,
            status="polar_generation_failed",
            failure=_failure_text(exc),
            declaration=declaration,
            bindings=bindings,
        )
    family = _json_ready_family(generated.family)
    hashes = _coordinate_hashes(family)
    record = _failure_record(
        airfoil_id,
        status="polar_coordinate_mismatch",
        failure="Every polar table must match the profile coordinate SHA-256.",
        declaration=declaration,
        bindings=bindings,
    )
    record["polar_content_sha256"] = _polar_content_sha256(family)
    record["polar_coordinate_sha256"] = next(iter(hashes)) if len(hashes) == 1 else None
    if hashes != {coordinate}:
        return record
    draft = build_design_draft(
        _source_path(repository_root),
        _inputs(airfoil_id),
        airfoil_definition=foil,
    )
    if draft.draft_sha256 != bindings[airfoil_id]["draft_sha256"]:
        raise ScreeningError("Draft hash changed while screening.")
    settings = BEMRotorSettings(annulus_count=ANNULUS_COUNT)
    try:
        bem_budget.charge()
        record["bem_calls"] = 1
        first = run_design_analysis(draft, {airfoil_id: family}, settings=settings)
    except (DesignAnalysisError, ScreeningError) as exc:
        record["status"] = "bem_failed"
        record["failure"] = str(exc)
        record["polar_coordinate_sha256"] = coordinate
        return record
    try:
        bem_budget.charge()
        record["bem_calls"] = 2
        second = run_design_analysis(draft, {airfoil_id: family}, settings=settings)
    except (DesignAnalysisError, ScreeningError) as exc:
        record["status"] = "bem_failed"
        record["failure"] = str(exc)
        record["polar_coordinate_sha256"] = coordinate
        return record
    metrics = _metrics_from_report(first.report_json)
    record["polar_coordinate_sha256"] = coordinate
    record["repeatable"] = first.report_sha256 == second.report_sha256
    if record["repeatable"] is not True:
        record["status"] = "repeatability_failed"
        record["failure"] = "Repeat BEM report hash differs from the first solve."
        record["metrics"] = None
        return record
    if not _within_grid(metrics, envelope):
        record["status"] = "coverage_failed"
        record["failure"] = "Solver polar queries are outside the declared grid."
        record["metrics"] = None
        return record
    record["status"] = "converged"
    record["failure"] = None
    record["metrics"] = {
        key: metrics[key] for key in (*_METRIC_KEYS, "propulsive_efficiency")
    }
    record["source_bound_report"] = first.report_json
    return record


def block_declared_screening(
    declaration: Mapping[str, Any],
    *,
    repository_root: str | Path,
    status: str,
    failure: str,
) -> dict[str, Any]:
    """Record an explicit pre-solve blockage for both profiles."""
    root = Path(repository_root)
    fresh = build_shared_declaration(root)
    if canonical_json(fresh) != canonical_json(declaration):
        raise ScreeningError(
            "Declaration does not match the shared geometry, condition, envelope, and budget."
        )
    bindings = profile_bindings(root)
    records = [
        _failure_record(
            airfoil_id,
            status=status,
            failure=failure,
            declaration=fresh,
            bindings=bindings,
        )
        for airfoil_id in PROFILE_IDS
    ]
    return {
        "declaration": fresh,
        "records": records,
        "published": publish_screening(records, fresh),
    }


def execute_declared_screening(
    declaration: Mapping[str, Any],
    *,
    provider: PolarProvider,
    repository_root: str | Path,
) -> dict[str, Any]:
    """Run the declared provider grid and at most four active-design BEM solves."""
    root = Path(repository_root)
    fresh = build_shared_declaration(root)
    if canonical_json(fresh) != canonical_json(declaration):
        raise ScreeningError(
            "Declaration does not match the shared geometry, condition, envelope, and budget."
        )
    bindings = profile_bindings(root)
    if not _provider_matches(provider, fresh):
        records = [
            _failure_record(
                airfoil_id,
                status="provider_identity_mismatch",
                failure=(
                    "Provider identity does not match the declared XFOIL adapter, "
                    "version, and backend."
                ),
                declaration=fresh,
                bindings=bindings,
            )
            for airfoil_id in PROFILE_IDS
        ]
        return {
            "declaration": fresh,
            "records": records,
            "published": publish_screening(records, fresh),
        }
    bem_budget = _CallBudget(MAX_BEM_CALLS, "BEM")
    capture_budget = _CallBudget(fresh["capture_budget"]["max_provider_cells"], "Provider capture")
    limited = provider
    records = []
    for airfoil_id in PROFILE_IDS:
        records.append(
            _execute_profile(
                fresh,
                airfoil_id,
                provider=limited,
                repository_root=root,
                bindings=bindings,
                bem_budget=bem_budget,
                capture_budget=capture_budget,
            )
        )
    return {
        "declaration": fresh,
        "records": records,
        "published": publish_screening(records, fresh),
    }


def _accepted(record: Mapping[str, Any], declaration: Mapping[str, Any]) -> bool:
    metrics = record.get("metrics")
    efficiency = None if not isinstance(metrics, Mapping) else metrics.get("propulsive_efficiency")
    efficiency_ok = efficiency is None or (
        isinstance(efficiency, (int, float))
        and not isinstance(efficiency, bool)
        and math.isfinite(float(efficiency))
    )
    return (
        record.get("status") == "converged"
        and record.get("repeatable") is True
        and record.get("physical_qualification") is False
        and record.get("geometry_sha256") == declaration["geometry_sha256"]
        and record.get("operating_condition_sha256") == declaration["operating_condition_sha256"]
        and record.get("polar_coordinate_sha256") == record.get("coordinate_sha256")
        and isinstance(record.get("polar_content_sha256"), str)
        and len(record["polar_content_sha256"]) == 64
        and isinstance(metrics, Mapping)
        and efficiency_ok
        and all(
            isinstance(metrics.get(key), (int, float))
            and not isinstance(metrics.get(key), bool)
            and math.isfinite(float(metrics[key]))
            for key in _METRIC_KEYS
        )
    )


def _ledger_status(record: Mapping[str, Any], declaration: Mapping[str, Any]) -> str:
    if record.get("geometry_sha256") != declaration["geometry_sha256"]:
        return "geometry_mismatch"
    if record.get("operating_condition_sha256") != declaration["operating_condition_sha256"]:
        return "condition_mismatch"
    if record.get("status") == "converged" and record.get("polar_coordinate_sha256") != record.get(
        "coordinate_sha256"
    ):
        return "polar_coordinate_mismatch"
    status = record.get("status")
    return status if isinstance(status, str) and status else "unspecified_failure"


def publish_screening(
    records: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    declaration: Mapping[str, Any],
) -> dict[str, Any]:
    """Publish solved profiles and retain every other profile in the ledger."""
    if [record.get("airfoil_id") for record in records] != list(PROFILE_IDS):
        raise ScreeningError("Screening records must be NACA0012 then NACA2412.")
    for record in records:
        if record.get("physical_qualification") is not False:
            raise ScreeningError("physical_qualification must be false.")
    comparison_rows = []
    failure_ledger = []
    for record in records:
        if _accepted(record, declaration):
            metrics = record["metrics"]
            comparison_rows.append(
                {
                    "airfoil_id": record["airfoil_id"],
                    "status": "converged",
                    "thrust_n": metrics["thrust_n"],
                    "torque_nm": metrics["torque_nm"],
                    "shaft_power_w": metrics["shaft_power_w"],
                    "thrust_coefficient": metrics["thrust_coefficient"],
                    "torque_coefficient": metrics["torque_coefficient"],
                    "power_coefficient": metrics["power_coefficient"],
                    "propulsive_efficiency": metrics["propulsive_efficiency"],
                    "draft_sha256": record["draft_sha256"],
                    "coordinate_sha256": record["coordinate_sha256"],
                    "polar_content_sha256": record["polar_content_sha256"],
                    "polar_coordinate_sha256": record["polar_coordinate_sha256"],
                    "geometry_sha256": record["geometry_sha256"],
                    "operating_condition_sha256": record["operating_condition_sha256"],
                    "repeatable": True,
                    "bem_calls": record["bem_calls"],
                    "physical_qualification": False,
                    "failure": None,
                }
            )
            continue
        failure_ledger.append(
            {
                "airfoil_id": record["airfoil_id"],
                "status": _ledger_status(record, declaration),
                "failure": record.get("failure"),
                "draft_sha256": record.get("draft_sha256"),
                "coordinate_sha256": record.get("coordinate_sha256"),
                "geometry_sha256": record.get("geometry_sha256"),
                "operating_condition_sha256": record.get("operating_condition_sha256"),
                "repeatable": record.get("repeatable"),
                "bem_calls": record.get("bem_calls"),
                "physical_qualification": False,
            }
        )
    return {
        "schema_version": 1,
        "artifact_class": "two_profile_bem_screening_comparison",
        "physical_qualification": False,
        "winner": None,
        "combined_totals": None,
        "shared_geometry_sha256": declaration["geometry_sha256"],
        "shared_operating_condition_sha256": declaration["operating_condition_sha256"],
        "shared_declaration_sha256": declaration["shared_declaration_sha256"],
        "comparison_rows": comparison_rows,
        "failure_ledger": failure_ledger,
        "bem_calls": sum(int(record.get("bem_calls") or 0) for record in records),
    }


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return format(value, ".16g")
    return str(value)


def render_comparison_csv(published: Mapping[str, Any]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=_CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for section, rows in (
        ("comparison", published["comparison_rows"]),
        ("ledger", published["failure_ledger"]),
    ):
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in _CSV_FIELDS} | {"section": section})
    return buffer.getvalue()


def render_report(published: Mapping[str, Any], *, runtime: Mapping[str, Any]) -> str:
    lines = [
        "# Two-profile BEM screening",
        "",
        "This is a screening record. It is not a physical qualification and it is not a design selection.",
        "The declared query envelope and capture budget were not expanded.",
        "",
        "physical_qualification: false",
        "Qualified winner: none",
        "Combined totals: none",
        "",
        f"Shared geometry SHA-256: {published['shared_geometry_sha256']}",
        f"Shared operating-condition SHA-256: {published['shared_operating_condition_sha256']}",
        f"Shared declaration SHA-256: {published['shared_declaration_sha256']}",
        f"BEM calls: {published['bem_calls']}",
        "",
        "## Comparison",
        "",
    ]
    if not published["comparison_rows"]:
        lines.extend(["No profile produced a repeatable, fully covered solve.", ""])
    for row in published["comparison_rows"]:
        lines.extend(
            [
                f"### {row['airfoil_id']}",
                "",
                f"- Status: {row['status']}",
                f"- Thrust N: {row['thrust_n']}",
                f"- Torque N·m: {row['torque_nm']}",
                f"- Shaft power W: {row['shaft_power_w']}",
                f"- Thrust coefficient: {row['thrust_coefficient']}",
                f"- Torque coefficient: {row['torque_coefficient']}",
                f"- Power coefficient: {row['power_coefficient']}",
                "- Propulsive efficiency: unsupported at zero flight speed"
                if row["propulsive_efficiency"] is None
                else f"- Propulsive efficiency: {row['propulsive_efficiency']}",
                f"- Repeatable: {row['repeatable']}",
                f"- Draft SHA-256: {row['draft_sha256']}",
                f"- Coordinate SHA-256: {row['coordinate_sha256']}",
                f"- Polar content SHA-256: {row['polar_content_sha256']}",
                "",
            ]
        )
    lines.extend(["## Failure ledger", ""])
    if not published["failure_ledger"]:
        lines.append("No failed profiles.")
    for row in published["failure_ledger"]:
        lines.extend(
            [
                f"### {row['airfoil_id']}",
                "",
                f"- Status: {row['status']}",
                f"- Failure: {row['failure']}",
                f"- Draft SHA-256: {row['draft_sha256']}",
                f"- Coordinate SHA-256: {row['coordinate_sha256']}",
                "",
            ]
        )
    lines.extend(["## Runtime", ""])
    for key in sorted(runtime):
        lines.append(f"- {key}: {runtime[key]}")
    lines.append("")
    return "\n".join(lines)


def _result_document(
    record: Mapping[str, Any],
    *,
    published_ids: set[str],
    declaration: Mapping[str, Any],
    runtime: Mapping[str, Any],
) -> dict[str, Any]:
    published = record["airfoil_id"] in published_ids
    document = {
        "schema_version": 1,
        "artifact_class": "two_profile_bem_screening_result",
        "physical_qualification": False,
        "comparison_published": published,
        "airfoil_id": record["airfoil_id"],
        "status": record["status"],
        "failure": record.get("failure"),
        "draft_sha256": record.get("draft_sha256"),
        "coordinate_sha256": record.get("coordinate_sha256"),
        "polar_content_sha256": record.get("polar_content_sha256"),
        "polar_coordinate_sha256": record.get("polar_coordinate_sha256"),
        "geometry_sha256": record.get("geometry_sha256"),
        "operating_condition_sha256": record.get("operating_condition_sha256"),
        "shared_declaration_sha256": declaration["shared_declaration_sha256"],
        "repeatable": record.get("repeatable"),
        "bem_calls": record.get("bem_calls"),
        "runtime": dict(runtime),
    }
    if published:
        document.update(record["metrics"])
        report = record.get("source_bound_report")
        if isinstance(report, str):
            document["source_bound_report"] = json.loads(report)
    return document


def write_study_outputs(
    directory: str | Path,
    *,
    declaration: Mapping[str, Any],
    records: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    published: Mapping[str, Any],
    runtime: Mapping[str, Any],
) -> None:
    """Write the declaration, both result JSON files, the CSV, and the report."""
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    (target / "declaration.json").write_text(
        canonical_json(declaration) + "\n", encoding="utf-8"
    )
    published_ids = {row["airfoil_id"] for row in published["comparison_rows"]}
    for record in records:
        document = _result_document(
            record,
            published_ids=published_ids,
            declaration=declaration,
            runtime=runtime,
        )
        (target / f"{record['airfoil_id']}.json").write_text(
            json.dumps(document, sort_keys=True, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    (target / "comparison.csv").write_text(render_comparison_csv(published), encoding="utf-8")
    (target / "report.md").write_text(
        render_report(published, runtime=runtime), encoding="utf-8"
    )
