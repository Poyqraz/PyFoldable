"""Read-only C2V-09 evidence identity.

The full critical-fixture manifest is a content snapshot. Its canonicalization
is applied here and checked against the pinned digest. This module does not
import the unmerged PR #81 implementation.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import subprocess
from pathlib import Path
from typing import Mapping

import numpy
import scipy

from pyfoldable.application.design_draft import DesignDraftInputs, build_design_draft
from pyfoldable.core.polar_spanwise import SpanwisePolarSchedule
from pyfoldable.dynamics.coupled_transient import CoupledSolverControls


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "tests" / "fixtures" / "prc" / "prc_critical_fixture_manifest_v1.canonical.json"
FULL_MANIFEST_ID = "prc_critical_fixture_manifest_v1"
FULL_MANIFEST_SHA256 = "265d531f51f08d45139313cd81b0239de0c2e9dd8926e12ded66d2011d83c1f7"
MANIFEST_SOURCE_COMMIT = "1fdf213bb991b2f155bf812d837bb4dcb73a8cc8"
PINNED_DRAFT_SOURCE_SHA256 = "a3852e5d14f433528fa9ad63bae26dd076b5136eacf4a7860ef76971eec2afdc"
HISTORICAL_SELECTION_RECORD_SHA256 = "1c465dae2d835fc85f468636131a2af6bce90220bcbde71c03ebea69c4ad3cf9"
SUPERSEDED_EXPANDED_SELECTION_RECORD_SHA256 = "457186d5f52a40099acbebfe0e8ffc47eb2a8ee5fd43605ee159ae9c76cd1579"
SHAFT_SPEED_FORMULAS = {
    "400 * pi / 30": 400.0 * math.pi / 30.0,
    "500 * pi / 30": 500.0 * math.pi / 30.0,
    "1000 * pi / 30": 1000.0 * math.pi / 30.0,
    "13000 * pi / 30": 13000.0 * math.pi / 30.0,
}


def canonical(value: object) -> str:
    """Canonicalize with the pinned manifest rules: JSON-safe, sorted, compact."""
    return json.dumps(_json_safe(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_safe(value: object) -> object:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(inner) for inner in value]
    raise TypeError(f"Unsupported manifest value {type(value).__name__}.")


def load_full_manifest() -> dict[str, object]:
    """Load the snapshot, re-canonicalize it, and require the pinned digest."""
    text = MANIFEST_PATH.read_text(encoding="utf-8")
    parsed = json.loads(text)
    again = canonical(parsed)
    if again != text:
        raise AssertionError("Critical-fixture snapshot is not in canonical form.")
    digest = sha256_text(again)
    if digest != FULL_MANIFEST_SHA256:
        raise AssertionError("Critical-fixture content does not match the pinned digest.")
    if parsed.get("manifest_id") != FULL_MANIFEST_ID:
        raise AssertionError("Critical-fixture snapshot does not carry the full manifest id.")
    return parsed


def assert_event_provenance(evidence: Mapping[str, object], environ: Mapping[str, str]) -> None:
    """Check live event SHAs without requiring them to be null on CI."""
    event_name = environ.get("GITHUB_EVENT_NAME", "")
    if event_name == "pull_request":
        sha = evidence["pr_source_sha"]
        if not isinstance(sha, str) or not sha:
            raise AssertionError("A pull_request run must record the payload head SHA.")
        if evidence["push_source_sha"] is not None:
            raise AssertionError("A pull_request run must leave the push SHA null.")
        return
    if event_name == "push":
        if evidence["push_source_sha"] != environ.get("GITHUB_SHA"):
            raise AssertionError("A push run must record GITHUB_SHA.")
        if evidence["pr_source_sha"] is not None:
            raise AssertionError("A push run must leave the pull-request SHA null.")
        return
    if evidence["pr_source_sha"] is not None or evidence["push_source_sha"] is not None:
        raise AssertionError("A local run must leave event SHAs null.")


def source_event_provenance(environ: Mapping[str, str], event_text: str | None) -> dict[str, str | None]:
    """Read push and pull-request source SHAs only from their own events.

    A local run has neither. A merge checkout is not the pull-request head, so
    the head is taken from the event payload and never from checkout equality.
    """
    event_name = environ.get("GITHUB_EVENT_NAME", "")
    pull_request_source = None
    push_source = None
    if event_name == "pull_request":
        if event_text:
            payload = json.loads(event_text)
            sha = payload.get("pull_request", {}).get("head", {}).get("sha")
            if isinstance(sha, str) and sha:
                pull_request_source = sha
    elif event_name == "push":
        sha = environ.get("GITHUB_SHA")
        if isinstance(sha, str) and sha:
            push_source = sha
    return {
        "pr_source_sha": pull_request_source,
        "push_source_sha": push_source,
    }


def checkout_provenance(repository: Path, environ: Mapping[str, str] | None = None, event_text: str | None = None) -> dict[str, object]:
    """Runtime checkout identity. Event SHAs stay null when no event is supplied."""
    active = os.environ if environ is None else environ
    if event_text is None and environ is None:
        event_path = active.get("GITHUB_EVENT_PATH")
        if event_path:
            event_text = Path(event_path).read_text(encoding="utf-8")
    checkout = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository, text=True).strip()
    tree = subprocess.check_output(["git", "rev-parse", f"{checkout}^{{tree}}"], cwd=repository, text=True).strip()
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=repository, text=True)
    dirty_paths = [line[3:] for line in status.splitlines() if line.strip()]
    record = {
        "evidence_checkout_sha": checkout,
        "evidence_tree_sha": tree,
        "worktree_dirty": bool(dirty_paths),
        "dirty_paths": dirty_paths,
        "python_version": platform.python_version(),
        "numpy_version": numpy.__version__,
        "scipy_version": scipy.__version__,
    }
    record.update(source_event_provenance(active, event_text))
    return record


def _controls(controls: CoupledSolverControls) -> dict[str, float | int]:
    return {
        "rtol": controls.rtol,
        "angle_atol_rad": controls.angle_atol_rad,
        "hinge_velocity_atol_rad_s": controls.hinge_velocity_atol_rad_s,
        "shaft_speed_atol_rad_s": controls.shaft_speed_atol_rad_s,
        "max_step_s": controls.max_step_s,
        "max_duration_s": controls.max_duration_s,
        "max_samples": controls.max_samples,
        "max_rhs_evaluations": controls.max_rhs_evaluations,
        "max_input_knots": controls.max_input_knots,
    }


def _quantity(value: object, unit: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AssertionError("Pinned draft quantity is not numeric.")
    if isinstance(value, int) or float(value).is_integer():
        text = str(int(value))
    else:
        text = format(float(value), ".10g")
    return f"{text} {unit}"


def _inputs_from_pinned(pinned: Mapping[str, object]) -> DesignDraftInputs:
    return DesignDraftInputs(
        diameter=_quantity(pinned["diameter_mm"], "mm"),
        hub_radius=_quantity(pinned["hub_radius_mm"], "mm"),
        hinge_radius=_quantity(pinned["hinge_radius_mm"], "mm"),
        blade_count=int(pinned["blade_count"]),
        airfoil_id=str(pinned["airfoil"]),
        chord_scale=float(pinned["chord_scale"]),
        twist_scale=float(pinned["twist_scale"]),
        preview_fold_angle=_quantity(pinned["preview_fold_deg"], "deg"),
        angular_speed=_quantity(pinned["angular_speed_rpm"], "rpm"),
        forward_speed=_quantity(pinned["draft_forward_speed_m_s"], "m/s"),
        air_density=_quantity(pinned["density_kg_m3"], "kg/m^3"),
        dynamic_viscosity=_quantity(pinned["viscosity_pa_s"], "Pa*s"),
        temperature=_quantity(pinned["temperature_degC"], "degC"),
        pressure=_quantity(pinned["pressure_kPa"], "kPa"),
    )


def _pinned_source_path(pinned: Mapping[str, object]) -> Path:
    relative = Path(str(pinned["draft_config"]))
    if relative.is_absolute() or ".." in relative.parts:
        raise AssertionError("Pinned draft configuration path is not repository-relative.")
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise AssertionError("Pinned draft configuration escapes the repository.")
    return path


def _expected_pinned_draft(pinned: Mapping[str, object]):
    path = _pinned_source_path(pinned)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != PINNED_DRAFT_SOURCE_SHA256:
        raise AssertionError("Draft source configuration does not match the pinned provenance.")
    expected = build_design_draft(path, _inputs_from_pinned(pinned))
    if expected.source_sha256 != PINNED_DRAFT_SOURCE_SHA256:
        raise AssertionError("Draft source configuration does not match the pinned provenance.")
    return expected


def _require_sealed_draft(sealed, pinned: Mapping[str, object]) -> None:
    expected = _expected_pinned_draft(pinned)
    draft = sealed.draft
    if (
        draft.filename != expected.filename
        or draft.toml != expected.toml
        or draft.draft_sha256 != expected.draft_sha256
        or draft.source_sha256 != expected.source_sha256
    ):
        raise AssertionError("Sealed draft does not match the pinned configuration.")


def _require_collection_cardinalities(sealed, pinned: Mapping[str, object]) -> None:
    if len(sealed.distribution.samples) != 1:
        raise AssertionError("Pinned fixture has one mass sample.")
    if not isinstance(sealed.polars, SpanwisePolarSchedule):
        raise AssertionError("C2V-09 candidate must use a spanwise polar schedule.")
    anchors = sealed.polars.anchors
    if len(anchors) != len(pinned["polar_anchors"]):
        raise AssertionError("Pinned fixture polar anchor count does not match.")
    for anchor in anchors:
        if len(anchor.family.tables) != 1:
            raise AssertionError("Pinned fixture has one polar table.")
    table = anchors[0].family.tables[0]
    if any(anchor.family.tables[0] != table for anchor in anchors[1:]):
        raise AssertionError("Pinned fixture has one polar table.")


def project_executed_candidate(sealed, pinned: Mapping[str, object]) -> dict[str, object]:
    """Project one sealed candidate onto the pinned declaration.

    Geometry comes from the sealed draft artifact, checked against the draft
    built from the pinned declaration and the pinned source-file hash.
    """
    _require_collection_cardinalities(sealed, pinned)
    _require_sealed_draft(sealed, pinned)
    table = sealed.polars.anchors[0].family.tables[0]
    sample = sealed.distribution.samples[0]
    observed: dict[str, object] = {
        "draft_config": pinned["draft_config"],
        "diameter_mm": pinned["diameter_mm"],
        "hub_radius_mm": pinned["hub_radius_mm"],
        "hinge_radius_mm": pinned["hinge_radius_mm"],
        "blade_count": pinned["blade_count"],
        "airfoil": pinned["airfoil"],
        "chord_scale": pinned["chord_scale"],
        "twist_scale": pinned["twist_scale"],
        "preview_fold_deg": pinned["preview_fold_deg"],
        "angular_speed_rpm": pinned["angular_speed_rpm"],
        "draft_forward_speed_m_s": pinned["draft_forward_speed_m_s"],
        "density_kg_m3": pinned["density_kg_m3"],
        "viscosity_pa_s": pinned["viscosity_pa_s"],
        "temperature_degC": pinned["temperature_degC"],
        "pressure_kPa": pinned["pressure_kPa"],
        "radial_mass_m": sample.distance_from_hinge_m,
        "radial_mass_kg": sample.mass_kg,
        "radial_mass_source": sample.source,
        "distribution_id": sealed.distribution.source,
        "mass_classification": sealed.distribution.classification,
        "I0_kg_m2": sealed.base_inertia.inertia_kg_m2,
        "inertia_source": sealed.base_inertia.source,
        "inventory": list(sealed.base_inertia.component_inventory),
        "spring_nm_rad": sealed.spring_stiffness_nm_rad,
        "rest_rad": sealed.rest_angle_rad,
        "damping_nm_s_rad": sealed.viscous_damping_nm_s_rad,
        "friction_mode": sealed.dry_friction.mode,
        "initial_angle_rad": sealed.initial_angle_rad,
        "initial_hinge_rate_rad_s": sealed.initial_angular_velocity_rad_s,
        "initial_shaft_speed_rad_s": sealed.initial_omega_rad_s,
        "actuation_knots_s": list(sealed.actuation.time_s),
        "actuation_torques_nm": list(sealed.actuation.torque_nm),
        "actuation_source": sealed.actuation.source,
        "motor_kv": sealed.motor.kv_rpm_per_v,
        "motor_resistance_ohm": sealed.motor.resistance_ohm,
        "motor_i0_a": sealed.motor.no_load_current_a,
        "motor_imax_a": sealed.motor.current_max_a,
        "battery_voltage_v": sealed.battery.voltage_v,
        "battery_efficiency": sealed.battery.discharge_efficiency,
        "system_resistance_ohm": sealed.system.resistance_ohm,
        "throttle": sealed.throttle,
        "environment_id": sealed.environment.id,
        "environment_forward_speed_m_s": sealed.environment.forward_speed_m_s,
        "environment_density_kg_m3": sealed.environment.air_density_kg_m3,
        "environment_viscosity_pa_s": sealed.environment.dynamic_viscosity_pa_s,
        "environment_temperature_k": sealed.environment.temperature_k,
        "environment_pressure_pa": sealed.environment.pressure_pa,
        "polar_schedule_id": sealed.polars.id,
        "polar_anchors": [anchor.r_over_R for anchor in sealed.polars.anchors],
        "polar_airfoil": table.airfoil_id,
        "polar_scenario": table.scenario_id,
        "polar_reynolds": table.reynolds,
        "polar_mach": table.mach,
        "polar_alpha_rad": list(table.alpha_rad),
        "polar_cl": list(table.cl),
        "polar_cd": list(table.cd),
        "polar_cm": list(table.cm),
        "polar_source": table.source,
        "polar_metadata": dict(table.metadata),
        "annulus_count": sealed.bem_settings.annulus_count,
        "bracket_samples": sealed.bem_settings.annulus_settings.bracket_samples,
        "loading_branch": sealed.bem_settings.annulus_settings.loading_branch,
        "bounds": sealed.bounds,
        "mechanical_source": sealed.mechanical_source,
        "controls": _controls(sealed.controls),
    }
    if sealed.dry_friction.mode != "none":
        observed["coulomb_nm"] = sealed.dry_friction.coulomb_torque_nm
        observed["friction_velocity_rad_s"] = sealed.dry_friction.transition_velocity_rad_s
        observed["friction_source"] = sealed.dry_friction.source
    return observed


def assert_matches_pinned_candidate(observed: Mapping[str, object], pinned: Mapping[str, object]) -> None:
    """Require the executed candidate to be the pinned declaration, including order metadata."""
    formula = pinned["initial_shaft_speed_formula"]
    if formula not in SHAFT_SPEED_FORMULAS:
        raise AssertionError(f"Unpinned shaft-speed formula {formula!r}.")
    if SHAFT_SPEED_FORMULAS[formula] != pinned["initial_shaft_speed_rad_s"]:
        raise AssertionError("Pinned shaft-speed formula does not match its declared value.")
    if observed["initial_shaft_speed_rad_s"] != pinned["initial_shaft_speed_rad_s"]:
        raise AssertionError("Executed shaft speed does not match the pinned declaration.")
    expected = {key: value for key, value in pinned.items() if key not in {"id", "initial_shaft_speed_formula"}}
    if dict(observed) != expected:
        raise AssertionError("Executed candidate inputs do not match the pinned declaration.")
