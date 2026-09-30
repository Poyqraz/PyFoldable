"""Frozen PR-C fixture manifest and finite evidence records.

The manifest is hashed when this module is imported, before any production
measurement. The amended technical head is the reviewed contract text. The
checkout that executes the evidence is recorded separately at runtime.
"""

from __future__ import annotations

from contextvars import ContextVar
from copy import deepcopy
from functools import wraps

import hashlib
import json
import math
import os
import platform
import subprocess
from fractions import Fraction
from pathlib import Path

import numpy
import scipy

from pyfoldable.dynamics.coupled_transient import CoupledSolverControls
from pyfoldable.dynamics.cmm2_coupled_transient import IMPLEMENTATION_ID, MODEL_CLASS


ROOT = Path(__file__).resolve().parents[2]
AMENDED_REVIEWED_TECHNICAL_HEAD = "b840ec55b4d1dd57197b97e91e1a48a7fbe7da0d"
ORIGINAL_REVIEWED_PROVENANCE = "613072514f793f2a1bc65704f9158f536210707f"
MERGED_CONTRACT_SOURCE = "64eea154f72365b647a1cff4d3fc768e45578d0c"
UNMEASURED_CASES = ("C2V-09", "C2V-10", "C2V-11", "C2V-12")
EVIDENCE: dict[str, object] = {}

CONTRACT_CONTROLS = {
    "rtol": 1.0e-6,
    "angle_atol_rad": 1.0e-8,
    "hinge_velocity_atol_rad_s": 1.0e-8,
    "shaft_speed_atol_rad_s": 1.0e-6,
    "max_step_s": 0.002,
    "max_duration_s": 2.0,
    "max_samples": 5000,
    "max_rhs_evaluations": 12000,
    "max_input_knots": 256,
}


def canonical(value: object) -> str:
    cleaned, _reasons = json_safe(value)
    return json.dumps(cleaned, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def json_safe(value: object) -> tuple[object, list[dict[str, str]]]:
    reasons: list[dict[str, str]] = []

    def walk(item: object, path: str) -> object:
        if isinstance(item, bool) or item is None or isinstance(item, str):
            return item
        if isinstance(item, int) and not isinstance(item, bool):
            return item
        if isinstance(item, float):
            if math.isfinite(item):
                return item
            reasons.append({"path": path or "$", "reason": "nonfinite"})
            return None
        if isinstance(item, Fraction):
            return walk(float(item), path)
        if isinstance(item, dict):
            return {
                str(key): walk(inner, f"{path}.{key}" if path else str(key))
                for key, inner in item.items()
            }
        if isinstance(item, (list, tuple)):
            return [walk(inner, f"{path}[{index}]") for index, inner in enumerate(item)]
        reasons.append({"path": path or "$", "reason": f"unsupported {type(item).__name__}"})
        return None

    return walk(value, ""), reasons


def git_rev_parse_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def pr_source_head() -> str | None:
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if event_name == "pull_request" and event_path:
        payload = json.loads(Path(event_path).read_text(encoding="utf-8"))
        sha = payload.get("pull_request", {}).get("head", {}).get("sha")
        if isinstance(sha, str) and sha:
            return sha
    if event_name == "push":
        sha = os.environ.get("GITHUB_SHA")
        if isinstance(sha, str) and sha:
            return sha
    return None


def worktree_status() -> tuple[bool, list[str]]:
    output = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=ROOT, text=True
    )
    paths = [line[3:] for line in output.splitlines() if line.strip()]
    return bool(paths), paths


def provenance_record() -> dict[str, object]:
    checkout = git_rev_parse_head()
    dirty, paths = worktree_status()
    return {
        "pr_source_head": pr_source_head(),
        "git_rev_parse_head": checkout,
        "evidence_checkout_head": checkout,
        "worktree_dirty": dirty,
        "dirty_paths": paths,
        "python_version": platform.python_version(),
        "numpy_version": numpy.__version__,
        "scipy_version": scipy.__version__,
    }


def _rad_s_from_rpm_number(rpm_number: float) -> float:
    return rpm_number * math.pi / 30.0


def _control_record(controls: CoupledSolverControls | None = None) -> dict[str, float | int]:
    controls = controls or CoupledSolverControls()
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


def repository_controls_match_contract() -> bool:
    return _control_record() == CONTRACT_CONTROLS


def _c2v09_base() -> dict[str, object]:
    return {
        "draft_config": "configs/designs/TIP_HINGED_250_CANONICAL.toml",
        "diameter_mm": 220,
        "hub_radius_mm": 16,
        "hinge_radius_mm": 85,
        "blade_count": 3,
        "airfoil": "NACA0012",
        "chord_scale": 1.0,
        "twist_scale": 1.0,
        "preview_fold_deg": -60,
        "angular_speed_rpm": 4000,
        "draft_forward_speed_m_s": 4.0,
        "density_kg_m3": 1.18,
        "viscosity_pa_s": 1.79e-5,
        "temperature_degC": 20,
        "pressure_kPa": 100,
        "radial_mass_m": 0.01,
        "radial_mass_kg": 0.01,
        "radial_mass_source": "synthetic tip mass",
        "distribution_id": "synthetic-tip",
        "mass_classification": "synthetic_test_fixture",
        "I0_kg_m2": 1.0e-4,
        "inertia_source": "fixture inertia",
        "inventory": ["motor rotor", "shaft", "hub", "fixed blade roots"],
        "spring_nm_rad": 0.0,
        "rest_rad": -0.2,
        "damping_nm_s_rad": 0.0,
        "friction_mode": "none",
        "initial_angle_rad": -0.2,
        "initial_hinge_rate_rad_s": 0.0,
        "initial_shaft_speed_rad_s": _rad_s_from_rpm_number(400.0),
        "initial_shaft_speed_formula": "400 * pi / 30",
        "actuation_knots_s": [0.0, 0.004],
        "actuation_torques_nm": [0.0, 0.0],
        "actuation_source": "no actuation",
        "motor_kv": 1000.0,
        "motor_resistance_ohm": 0.05,
        "motor_i0_a": 1.0,
        "motor_imax_a": 80.0,
        "battery_voltage_v": 12.0,
        "battery_efficiency": 0.98,
        "system_resistance_ohm": 0.01,
        "throttle": 0.1,
        "environment_id": "screen",
        "environment_forward_speed_m_s": 4.0,
        "environment_density_kg_m3": 1.18,
        "environment_viscosity_pa_s": 1.79e-5,
        "environment_temperature_k": 293.15,
        "environment_pressure_pa": 100000.0,
        "polar_schedule_id": "cmm2-span",
        "polar_anchors": [0.2, 1.0],
        "polar_airfoil": "NACA0012",
        "polar_scenario": "cmm2",
        "polar_reynolds": 1.0e5,
        "polar_mach": 0.0,
        "polar_alpha_rad": [-0.5, 0.5],
        "polar_cl": [0.6, 0.6],
        "polar_cd": [0.02, 0.02],
        "polar_cm": [0.0, 0.0],
        "polar_source": "cmm2-fixture",
        "polar_metadata": {},
        "annulus_count": 4,
        "bracket_samples": 16,
        "loading_branch": "positive_only",
        "bounds": "error",
        "mechanical_source": "explicit fixture",
        "controls": dict(CONTRACT_CONTROLS),
    }


def _c2v09_candidates() -> list[dict[str, object]]:
    base = _c2v09_base()
    changes: list[tuple[str, dict[str, object]]] = [
        ("C2V09-01", {"I0_kg_m2": 2.0e-4}),
        ("C2V09-02", {"inertia_source": "other inertia"}),
        ("C2V09-03", {"inventory": ["motor rotor", "shaft", "hub"]}),
        ("C2V09-04", {"motor_kv": 1100.0}),
        ("C2V09-05", {"battery_voltage_v": 14.8}),
        ("C2V09-06", {"battery_efficiency": 0.97}),
        ("C2V09-07", {"system_resistance_ohm": 0.02}),
        ("C2V09-08", {"throttle": 0.2}),
        ("C2V09-09", {"environment_forward_speed_m_s": 5.0}),
        ("C2V09-10", {"polar_cl": [0.7, 0.7]}),
        ("C2V09-11", {"polar_source": "other-fixture"}),
        ("C2V09-12", {"polar_metadata": {"tag": "b"}}),
        ("C2V09-13", {"annulus_count": 6}),
        ("C2V09-14", {"loading_branch": "signed_nonreversed"}),
        ("C2V09-15", {"radial_mass_kg": 0.02}),
        ("C2V09-16", {"spring_nm_rad": 0.001}),
        ("C2V09-17", {"rest_rad": -0.1}),
        ("C2V09-18", {"damping_nm_s_rad": 0.0001}),
        (
            "C2V09-19",
            {
                "friction_mode": "regularized_coulomb",
                "coulomb_nm": 0.001,
                "friction_velocity_rad_s": 0.04,
                "friction_source": "fixture friction",
            },
        ),
        ("C2V09-20", {"mechanical_source": "other fixture"}),
        ("C2V09-21", {"actuation_torques_nm": [0.0, 0.001]}),
        ("C2V09-22", {"initial_angle_rad": -0.15}),
        ("C2V09-23", {"initial_hinge_rate_rad_s": 0.01}),
        (
            "C2V09-24",
            {
                "initial_shaft_speed_rad_s": _rad_s_from_rpm_number(500.0),
                "initial_shaft_speed_formula": "500 * pi / 30",
            },
        ),
        ("C2V09-25", {"controls": {**CONTRACT_CONTROLS, "rtol": 1.0e-7}}),
        (
            "C2V09-26",
            {
                "initial_shaft_speed_rad_s": _rad_s_from_rpm_number(13000.0),
                "initial_shaft_speed_formula": "13000 * pi / 30",
            },
        ),
        (
            "C2V09-27",
            {
                "motor_imax_a": 5.0,
                "throttle": 1.0,
                "initial_shaft_speed_rad_s": _rad_s_from_rpm_number(1000.0),
                "initial_shaft_speed_formula": "1000 * pi / 30",
            },
        ),
    ]
    rows = [{"id": "C2V09-00", **base}]
    for candidate_id, change in changes:
        row = {"id": candidate_id, **base, **change}
        if "controls" in change:
            row["controls"] = change["controls"]
        rows.append(row)
    return rows


def _shared_mechanism() -> dict[str, float]:
    return {
        "m_kg": 0.02,
        "hinge_radius_m": 0.08,
        "cg_distance_m": 0.03,
        "hinge_inertia_kg_m2": 2.0e-5,
        "base_inertia_kg_m2": 1.0e-4,
        "spring_nm_rad": 0.01,
        "rest_rad": -0.2,
        "damping_nm_s_rad": 0.002,
        "coulomb_nm": 0.001,
        "friction_velocity_rad_s": 0.05,
        "friction_mode": "regularized_coulomb",
        "lower_stop_rad": -1.2,
        "upper_stop_rad": 0.2,
    }


def _cases() -> dict[str, object]:
    shared = _shared_mechanism()
    controls = dict(CONTRACT_CONTROLS)
    return {
        "C2V-01": {
            "duration_s": None,
            "state_rad": [-0.4, 0.2, 40.0],
            "Qm_nm": 0.05,
            "Qh_nm": 0.001,
            "load_pairs_nm": [[-0.02, 0.004], [0.015, -0.003]],
            "blade_counts": [1, 2, 4],
            "mutants": ["A_Q_phi_times_N", "B_q_theta_missing_N", "C_N_q_theta_as_one_tip", "D_q_theta_sign"],
            "raw_bem_torque": False,
            "mechanism": shared,
            "controls": controls,
        },
        "C2V-02": {
            "blade_count": 2,
            "theta_rad": -0.4,
            "theta_dot_rad_s": 0.0,
            "omega_rad_s": 40.0,
            "Qm_nm": 0.05,
            "Qh_nm": 0.001,
            "Q_phi_formula": "Q_phi = -Qm",
            "q_theta_formula": "unique value that zeros the hinge bracket after spring and centrifugal terms",
            "duration_s": 0.02,
            "loads_constant": True,
            "damping_and_friction_torque": "identically zero because theta_dot = 0",
            "trajectory_reference": "exact constant state",
            "max_e_j_limit": 1.0,
            "mechanism": shared,
            "controls": controls,
        },
        "C2V-03": {
            "blade_count": 2,
            "duration_s": 0.2,
            "theta_formula": "theta*(t) = -0.30 + 0.05 * sin(2 * pi * t / 0.2)",
            "omega_formula": "omega*(t) = 40 + 2 * t",
            "omega_dot_rad_s2": 2.0,
            "Qm_nm": 0.04,
            "Qh_nm": 0.001,
            "load_formula": "Q_phi*(t) and q_theta*(t) solve the target equations at the target state and accelerations",
            "mechanism": shared,
            "controls": controls,
        },
        "C2V-04": {
            "shares_target": "C2V-03",
            "power_formula": "P = Qm*omega + Q_phi*omega + N*q_theta*theta_dot + N*Qh*theta_dot - N*b*theta_dot^2 - N*tau_c*theta_dot*tanh(theta_dot/v)",
            "quad_A_epsrel": 1.0e-10,
            "quad_B_epsrel": 1.0e-12,
            "quad_epsabs": 0.0,
            "mechanism": shared,
            "controls": controls,
        },
        "C2V-05": {
            "shares_target": "C2V-03",
            "reference": "DOP853 Reference A and Reference B on the independent C2V-03 right-hand side",
            "stabilization_limit_abs_A_minus_B_over_S": 0.1,
            "stabilization_limit_abs_A_minus_B_over_0_1_S": 1.0,
            "mechanism": shared,
            "controls": controls,
        },
        "C2V-06": {
            "blade_count": 2,
            "theta_rad": -0.3,
            "theta_dot_rad_s": 0.1,
            "omega_rad_s": 40.0,
            "Qa_nm": 0.02,
            "q_theta_nm": 0.0,
            "Q_phi_formula": "Q_phi = -Qa",
            "Qm_nm": 0.04,
            "Qh_nm": 0.001,
            "optional_duration_s": 0.05,
            "state_sweep": False,
            "mechanism": shared,
            "controls": controls,
        },
        "C2V-07": {
            "blade_count": 2,
            "lower_stop_rad": -0.50,
            "upper_stop_rad": 0.20,
            "duration_s": 1.0,
            "max_step_prod_s": 0.002,
            "theta_formula": "theta*(t) = -0.20 - 0.40 t",
            "theta_dot_rad_s": -0.40,
            "theta_ddot_rad_s2": 0.0,
            "omega_rad_s": 40.0,
            "omega_dot_rad_s2": 0.0,
            "Qm_nm": 0.04,
            "Qh_nm": 0.0,
            "t_c_s": 0.75,
            "load_formula": "section 8 zero-acceleration target formulas",
            "mechanism": {**shared, "lower_stop_rad": -0.50, "upper_stop_rad": 0.20},
            "controls": controls,
        },
        "C2V-08": {
            "blade_count": 2,
            "zero_actuation": "two knots spanning the subcase duration",
            "fold": {
                "theta_formula": "theta*(t) = -1.20 - 1.00 t",
                "theta_dot_rad_s": -1.0,
                "theta_ddot_rad_s2": 0.0,
                "omega_rad_s": 40.0,
                "omega_dot_rad_s2": 0.0,
                "lower_stop_rad": -2.0,
                "upper_stop_rad": 0.5,
                "duration_s": 0.5,
                "Qm_nm": 0.04,
                "Qh_nm": 0.0,
                "expected_layer": "Cmm2DomainExit",
            },
            "speed": {
                "omega0_rad_s": 10.0,
                "theta0_rad": -0.3,
                "theta_dot0_rad_s": 0.0,
                "expected_layer": "Cmm2TransientError",
            },
            "budget": {
                "theta0_rad": -0.3,
                "theta_dot0_rad_s": 0.1,
                "omega0_rad_s": 40.0,
                "duration_s": 0.2,
                "Qm_nm": 0.04,
                "Q_phi_nm": -0.02,
                "q_theta_nm": 0.004,
                "max_rhs_evaluations": 1,
                "expected_message": "CMM-2 work budget exhausted.",
                "expected_layer": "Cmm2TransientFailure",
            },
            "hard_failure": {
                "message": "hard failure",
                "expected_layer": "Cmm2TransientFailure",
            },
            "mechanism": shared,
            "controls": controls,
        },
        "C2V-09": {
            "inputs": "ordered C2V09-00 through C2V09-27",
            "measured_in_this_repair": False,
        },
        "C2V-10": {
            "blade_count": 2,
            "duration_s": 0.8,
            "knots_s": [0.0, 0.4, 0.8],
            "torques_nm": [0.0, 0.002, -0.001],
            "theta_rad": -0.3,
            "theta_dot_rad_s": 0.1,
            "omega_rad_s": 40.0,
            "Q_phi_nm": -0.02,
            "q_theta_nm": 0.004,
            "Qm_nm": 0.04,
            "probe_formula": "delta = 0.25 * min(t_k - t_(k-1), t_(k+1) - t_k)",
            "probe_offset_s": 0.1,
            "measured_in_this_repair": False,
            "mechanism": shared,
            "controls": controls,
        },
    }


def build_manifest() -> dict[str, object]:
    return {
        "manifest_id": "prc_critical_fixture_manifest_v1",
        "amended_reviewed_technical_head": AMENDED_REVIEWED_TECHNICAL_HEAD,
        "original_reviewed_provenance": ORIGINAL_REVIEWED_PROVENANCE,
        "merged_contract_source": MERGED_CONTRACT_SOURCE,
        "shared": {
            "mechanism": _shared_mechanism(),
            "controls": dict(CONTRACT_CONTROLS),
            "inventory": ["motor rotor", "shaft", "hub", "fixed blade roots"],
        },
        "policy_ids": {
            "threshold": "prc_state_scale_v1",
            "reference": "prc_dop853_ab_v1",
            "conditioning": "prc_represented_forward_v1",
            "selection": "prc_c2v09_ordered_candidates_v1",
            "manifest": "prc_critical_fixture_manifest_v1",
        },
        "cases": _cases(),
        "c2v09_candidates": _c2v09_candidates(),
        "c2v09_order_identity": "prc_c2v09_ordered_candidates_v1",
    }


MANIFEST = build_manifest()
MANIFEST_SHA = sha256(canonical(MANIFEST))


def executed_fixture(case_id: str, executed_inputs: dict[str, object]) -> dict[str, object]:
    case = MANIFEST["cases"][case_id]
    return {
        "case_id": case_id,
        "manifest_case": case,
        "executed_inputs": executed_inputs,
        "manifest_duration_s": case.get("duration_s"),
        "controls": case.get("controls", MANIFEST["shared"]["controls"]),
    }


def fixture_digest(payload: dict[str, object]) -> str:
    return sha256(canonical(payload))


def _mechanism_snapshot(system: object) -> dict[str, object]:
    parameters = system.parameters
    friction = parameters.dry_friction
    return {
        "m_kg": parameters.mass_kg,
        "hinge_radius_m": parameters.hinge_radius_m,
        "cg_distance_m": parameters.cg_distance_m,
        "hinge_inertia_kg_m2": parameters.hinge_inertia_kg_m2,
        "base_inertia_kg_m2": system.base_inertia.inertia_kg_m2,
        "spring_nm_rad": parameters.spring_stiffness_nm_rad,
        "rest_rad": parameters.rest_angle_rad,
        "damping_nm_s_rad": parameters.viscous_damping_nm_s_rad,
        "coulomb_nm": friction.coulomb_torque_nm,
        "friction_velocity_rad_s": friction.transition_velocity_rad_s,
        "friction_mode": friction.mode,
        "lower_stop_rad": parameters.lower_stop_rad,
        "upper_stop_rad": parameters.upper_stop_rad,
        "blade_count": system.blade_count,
    }


def _expected_mechanism(case: dict[str, object], subcase: str | None) -> dict[str, object]:
    expected = dict(MANIFEST["shared"]["mechanism"])
    nested = case.get("mechanism")
    if isinstance(nested, dict):
        expected.update(nested)
    if subcase is not None:
        details = case.get(subcase)
        if isinstance(details, dict):
            for key in ("lower_stop_rad", "upper_stop_rad"):
                if key in details:
                    expected[key] = details[key]
    return expected


def _expected_controls(case: dict[str, object], subcase: str | None) -> dict[str, object]:
    expected = dict(MANIFEST["shared"]["controls"])
    nested = case.get("controls")
    if isinstance(nested, dict):
        expected.update(nested)
    if subcase is not None:
        details = case.get(subcase)
        if isinstance(details, dict) and "max_rhs_evaluations" in details:
            expected["max_rhs_evaluations"] = details["max_rhs_evaluations"]
    return expected


def _expected_inputs(case_id: str, subcase: str | None) -> dict[str, object]:
    """Actual scalar/target inputs authorized by the unchanged fixture manifest."""
    case = MANIFEST["cases"][case_id]
    if case_id == "C2V-01":
        return {"state_rad": case["state_rad"], "Qm_nm": case["Qm_nm"], "Qh_nm": case["Qh_nm"]}
    if case_id in {"C2V-03", "C2V-04", "C2V-05"}:
        target = MANIFEST["cases"]["C2V-03"]
        initial = [-.30, .05 * (2.0 * math.pi / .2), 40.0]
        inputs = {"duration_s": target["duration_s"], "Qm_nm": target["Qm_nm"], "Qh_nm": target["Qh_nm"],
                  "initial_state_rad": initial, "theta_formula": target["theta_formula"], "omega_formula": target["omega_formula"],
                  "load_formula": target["load_formula"], "omega_dot_rad_s2": target["omega_dot_rad_s2"]}
        if case_id == "C2V-04":
            inputs.update({"quad_A_epsrel": case["quad_A_epsrel"], "quad_B_epsrel": case["quad_B_epsrel"], "quad_epsabs": case["quad_epsabs"], "power_sample_times_s": [i / 20.0 for i in range(5)]})
        else:
            inputs.update({"actuation_knots_s": [0.0, .2], "actuation_torques_nm": [.001, .001]})
        return inputs
    if case_id == "C2V-08":
        common = {"duration_s": .2, "theta_rad": -.3, "theta_dot_rad_s": .1, "omega_rad_s": 40., "Qm_nm": .04, "Qh_nm": 0.}
        if subcase == "fold":
            common.update(duration_s=.5, theta_rad=-1.2, theta_dot_rad_s=-1., theta_rate_rad_s=-1., theta_ddot_rad_s2=0., omega_dot_rad_s2=0., load_formula="zero_acceleration_target")
        elif subcase == "speed":
            common.update(theta_dot_rad_s=0., omega_rad_s=10., load_formula="unreachable_counting_callback")
        elif subcase == "budget":
            common.update(Q_phi_nm=-.02, q_theta_nm=.004)
        elif subcase == "hard":
            common.update(load_formula="raises_Cmm2TransientFailure", failure_message="hard failure")
        else:
            raise AssertionError("fixture drifted before measurement: subcase")
        common.update(actuation_knots_s=[0., common["duration_s"]], actuation_torques_nm=[0., 0.])
        return common
    inputs = {key: case[key] for key in ("duration_s", "theta_rad", "theta_dot_rad_s", "omega_rad_s", "Qm_nm", "Qh_nm", "Qa_nm", "q_theta_nm") if key in case}
    if case_id == "C2V-02":
        # Independently assemble the frozen equilibrium load, preserving binary64
        # operation order; this does not use a production acceleration/residual.
        m = case["mechanism"]
        theta = case["theta_rad"]
        spring = -m["spring_nm_rad"] * (theta - m["rest_rad"])
        centrifugal = -(m["m_kg"] * m["hinge_radius_m"] * m["cg_distance_m"]) * case["omega_rad_s"]**2 * math.sin(theta)
        inputs.update(Q_phi_nm=-case["Qm_nm"], q_theta_nm=-case["Qh_nm"] - spring - centrifugal,
                      actuation_knots_s=[0., .02], actuation_torques_nm=[.001, .001])
    elif case_id == "C2V-06":
        inputs.update(Q_phi_nm=-case["Qa_nm"])
    elif case_id == "C2V-07":
        inputs.update(theta_rad=-.20, theta_dot_rad_s=-.40, theta_ddot_rad_s2=0., omega_dot_rad_s2=0.,
                      theta_rate_rad_s=-.40, load_formula="zero_acceleration_target", actuation_knots_s=[0., 1.], actuation_torques_nm=[0., 0.])
    return inputs


_ACTIVE_PARTIAL: ContextVar[dict[str, object] | None] = ContextVar("prc_partial", default=None)


def measurement_partial() -> dict[str, object]:
    partial = _ACTIVE_PARTIAL.get()
    if partial is None:
        raise AssertionError("measured case has no recording boundary")
    return partial


def recorded_case(case_id: str):
    """Capture setup through final assertions, not only the production call."""
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            def measure(partial):
                token = _ACTIVE_PARTIAL.set(partial)
                try:
                    function(*args, **kwargs)
                    return dict(partial)
                finally:
                    _ACTIVE_PARTIAL.reset(token)
            execute_measured_case(case_id, measure)
        return wrapped
    return decorate


def freeze_case_before_measurement(
    case_id: str,
    *,
    system: object,
    controls: CoupledSolverControls,
    executed_inputs: dict[str, object],
    production_call=None,
    subcase: str | None = None,
) -> dict[str, object]:
    case = MANIFEST["cases"][case_id]
    if not isinstance(case, dict):
        raise AssertionError("fixture drifted before measurement: missing case")
    mismatches: list[str] = []
    actual_mechanism = _mechanism_snapshot(system)
    for key, expected in _expected_mechanism(case, subcase).items():
        if key in actual_mechanism and actual_mechanism[key] != expected:
            mismatches.append(f"mechanism.{key}")
    expected_count = case.get("blade_count", 2 if case_id in {"C2V-04", "C2V-05"} else None)
    if expected_count is not None and actual_mechanism["blade_count"] != expected_count:
        mismatches.append("blade_count")
    if "blade_counts" in case and actual_mechanism["blade_count"] not in case["blade_counts"]:
        mismatches.append("blade_count")
    actual_controls = _control_record(controls)
    for key, expected in _expected_controls(case, subcase).items():
        if actual_controls.get(key) != expected:
            mismatches.append(f"controls.{key}")
    if "duration_s" in case and case["duration_s"] is not None:
        if executed_inputs.get("duration_s") != case["duration_s"]:
            mismatches.append("duration_s")
    for key in ("theta_rad", "theta_dot_rad_s", "omega_rad_s", "Qm_nm", "Qh_nm"):
        if key in case and executed_inputs.get(key) != case[key]:
            mismatches.append(key)
    if case_id in {"C2V-03", "C2V-04", "C2V-05"} or case.get("shares_target") == "C2V-03":
        target = MANIFEST["cases"]["C2V-03"]
        for key in ("duration_s", "Qm_nm", "Qh_nm"):
            if executed_inputs.get(key) != target[key]:
                mismatches.append(f"shared_target.{key}")
    expected_inputs = _expected_inputs(case_id, subcase)
    for key, expected in expected_inputs.items():
        if executed_inputs.get(key) != expected:
            mismatches.append(key)
    if case_id == "C2V-01":
        if executed_inputs.get("load_pair_nm") not in case["load_pairs_nm"]:
            mismatches.append("load_pair_nm")
    if mismatches:
        raise AssertionError(
            "fixture drifted before measurement: " + ", ".join(mismatches)
        )
    snapshot = {
        "case_id": case_id,
        "subcase": subcase,
        "mechanism": actual_mechanism,
        "controls": actual_controls,
        "executed_inputs": deepcopy(executed_inputs),
        "manifest_case": deepcopy(case),
    }
    snapshot["premeasurement_digest"] = sha256(canonical(snapshot))
    partial = _ACTIVE_PARTIAL.get()
    if partial is not None:
        snapshots = partial.setdefault("premeasurement_snapshots", [])
        snapshots.append(snapshot)
        partial["premeasurement_digest"] = fixture_digest({"case_id": case_id, "snapshots": snapshots})
        partial["executed_inputs"] = {"snapshots": snapshots}
        partial["controls"] = actual_controls
    if production_call is not None:
        production_call()
    return snapshot


def execute_measured_case(case_id: str, measure, checks=()) -> dict[str, object]:
    partial: dict[str, object] = {}
    EVIDENCE.pop(case_id, None)
    try:
        payload = measure(partial)
        if not isinstance(payload, dict):
            raise AssertionError("measured case did not return a record")
        payload = {**partial, **payload}
        if payload.get("premeasurement_digest") is None and partial.get("premeasurement_digest"):
            payload["premeasurement_digest"] = partial["premeasurement_digest"]
        if payload.get("fixture_digest") is None and payload.get("premeasurement_digest"):
            payload["fixture_digest"] = payload["premeasurement_digest"]
        if partial.get("metrics") and not payload.get("metrics"):
            payload["metrics"] = partial["metrics"]
        partial.update(payload)
        commit_case(case_id, payload)
        for check in checks:
            check(payload)
        if payload.get("classification") != "PASS":
            raise AssertionError(str(payload.get("pass_blocked_reason") or "case gate failed"))
        return payload
    except Exception as exc:
        # Always replace this invocation's provisional record. Never use an old
        # run's record/digest to claim this failed setup was frozen.
        fail = dict(partial)
        reason = f"{type(exc).__name__}: {exc}"
        cause = exc.__cause__
        while cause is not None:
            reason += f"; cause {type(cause).__name__}: {cause}"
            cause = cause.__cause__
        fail.update(classification="FAIL", record_reason=reason, pass_blocked_reason=reason)
        fail.setdefault("purpose", case_id)
        fail.setdefault("oracle_method", "execution boundary")
        fail.setdefault("limitations", "partial metrics from failed execution")
        fail.setdefault("premeasurement_digest", None)
        fail.setdefault("fixture_digest", fail.get("premeasurement_digest"))
        fail.setdefault("executed_inputs", {})
        commit_case(case_id, fail)
        raise


def _blank_case(case_id: str, reason: str) -> dict[str, object]:
    return {
        "primary_evidence_class": None,
        "purpose": None,
        "fixture_identity": f"prc_critical_fixture_manifest_v1:{case_id}",
        "fixture_digest": None,
        "selection_record_sha256": None,
        "selection_record_reason": "no C2V-09 selection in this repair",
        "oracle_method": None,
        "independence_limit": None,
        "controls": MANIFEST["shared"]["controls"],
        "metrics": None,
        "units": None,
        "reference_stabilization": None,
        "acceptance_rule": None,
        "threshold_basis": None,
        "classification": "FAIL",
        "limitations": reason,
        "record_reason": reason,
    }


def commit_case(case_id: str, payload: dict[str, object]) -> dict[str, object]:
    if case_id in UNMEASURED_CASES and payload.get("classification") in {
        "PASS",
        "CHARACTERIZATION ONLY",
    }:
        raise AssertionError(f"{case_id} is not measured in this repair")
    body = _blank_case(case_id, "measured")
    body.update(payload)
    provenance = provenance_record()
    body.update(
        {
            "repository_head": provenance["git_rev_parse_head"],
            "pr_source_head": provenance["pr_source_head"],
            "git_rev_parse_head": provenance["git_rev_parse_head"],
            "evidence_checkout_head": provenance["evidence_checkout_head"],
            "worktree_dirty": provenance["worktree_dirty"],
            "dirty_paths": provenance["dirty_paths"],
            "python_version": provenance["python_version"],
            "numpy_version": provenance["numpy_version"],
            "scipy_version": provenance["scipy_version"],
            "contract_head": AMENDED_REVIEWED_TECHNICAL_HEAD,
            "amended_reviewed_technical_head": AMENDED_REVIEWED_TECHNICAL_HEAD,
            "original_reviewed_provenance": ORIGINAL_REVIEWED_PROVENANCE,
            "merged_contract_source": MERGED_CONTRACT_SOURCE,
            "case_id": case_id,
            "critical_fixture_manifest_sha256": MANIFEST_SHA,
            "pre_result_freeze_status": "frozen_before_measurement" if body.get("freeze_complete") is True else "PARTIALLY_FROZEN" if body.get("premeasurement_snapshots") else "NOT_FROZEN",
            "threshold_policy_id": "prc_state_scale_v1",
            "reference_policy_id": "prc_dop853_ab_v1",
            "conditioning_policy_id": "prc_represented_forward_v1",
            "fixture_selection_policy_id": "prc_c2v09_ordered_candidates_v1",
            "model_identifiers": {
                "model_class": MODEL_CLASS,
                "implementation_id": IMPLEMENTATION_ID,
            },
            "dependency_identifiers": [
                "pyfoldable.dynamics.cmm2_coupled_transient",
                "pyfoldable.dynamics.coupled_transient",
                "scipy.integrate.solve_ivp:DOP853",
                "scipy.integrate.quad",
            ],
            "component_order": ["theta", "theta_dot", "omega"],
            "physical_qualification": False,
        }
    )
    cleaned, reasons = json_safe(body)
    if not isinstance(cleaned, dict):
        raise AssertionError("evidence record is not an object")
    if reasons:
        cleaned["nonfinite_reasons"] = reasons
        if cleaned.get("classification") == "PASS":
            cleaned["classification"] = "FAIL"
            cleaned["pass_blocked_reason"] = "nonfinite metric"
    json.dumps(cleaned, sort_keys=True, allow_nan=False)
    EVIDENCE[case_id] = cleaned
    return cleaned


def coverage_record() -> dict[str, dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    for index in range(1, 13):
        case_id = f"C2V-{index:02d}"
        if case_id in UNMEASURED_CASES:
            recorded = EVIDENCE.get(case_id)
            if isinstance(recorded, dict) and recorded.get("classification") in {
                "PASS",
                "CHARACTERIZATION ONLY",
            }:
                raise AssertionError(f"{case_id} cannot be marked measured evidence")
            rows[case_id] = {
                "coverage": "NOT_MEASURED",
                "classification": None,
                "reason": "numerical implementation was not extended in this repair",
            }
            continue
        recorded = EVIDENCE.get(case_id)
        if isinstance(recorded, dict):
            rows[case_id] = {
                "coverage": "MEASURED",
                "classification": recorded.get("classification"),
            }
        else:
            rows[case_id] = {
                "coverage": "NOT_RECORDED",
                "classification": None,
                "reason": "the case did not commit a record",
            }
    return rows


def evidence_document() -> dict[str, object]:
    provenance = provenance_record()
    return {
        "amended_reviewed_technical_head": AMENDED_REVIEWED_TECHNICAL_HEAD,
        "original_reviewed_provenance": ORIGINAL_REVIEWED_PROVENANCE,
        "merged_contract_source": MERGED_CONTRACT_SOURCE,
        "pr_source_head": provenance["pr_source_head"],
        "git_rev_parse_head": provenance["git_rev_parse_head"],
        "evidence_checkout_head": provenance["evidence_checkout_head"],
        "worktree_dirty": provenance["worktree_dirty"],
        "dirty_paths": provenance["dirty_paths"],
        "python_version": provenance["python_version"],
        "numpy_version": provenance["numpy_version"],
        "scipy_version": provenance["scipy_version"],
        "critical_fixture_manifest_sha256": MANIFEST_SHA,
        "pre_result_freeze_status": "manifest_hashed_before_measurement; see individual case freeze status",
        "physical_qualification": False,
        "adr_009": "NOT CREATED / NOT ACCEPTED",
        "cases": EVIDENCE,
        "coverage": coverage_record(),
    }


def write_evidence(path: Path) -> None:
    document, reasons = json_safe(evidence_document())
    if reasons:
        if isinstance(document, dict):
            document["document_nonfinite_reasons"] = reasons
    path.write_text(
        json.dumps(document, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )
