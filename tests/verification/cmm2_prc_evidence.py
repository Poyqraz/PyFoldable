"""Frozen PR-C fixture manifest and finite evidence records.

The manifest is hashed when this module is imported, before any production
measurement. The amended technical head is the reviewed contract text. The
checkout that executes the evidence is recorded separately at runtime.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
from fractions import Fraction
from pathlib import Path

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


def repository_head() -> str:
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if event_name == "pull_request" and event_path:
        payload = json.loads(Path(event_path).read_text(encoding="utf-8"))
        sha = payload.get("pull_request", {}).get("head", {}).get("sha")
        if isinstance(sha, str) and sha:
            return sha
    if event_name == "push" and os.environ.get("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"]
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


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
    body.update(
        {
            "repository_head": repository_head(),
            "evidence_checkout_head": repository_head(),
            "contract_head": AMENDED_REVIEWED_TECHNICAL_HEAD,
            "amended_reviewed_technical_head": AMENDED_REVIEWED_TECHNICAL_HEAD,
            "original_reviewed_provenance": ORIGINAL_REVIEWED_PROVENANCE,
            "merged_contract_source": MERGED_CONTRACT_SOURCE,
            "case_id": case_id,
            "critical_fixture_manifest_sha256": MANIFEST_SHA,
            "pre_result_freeze_status": "frozen_before_measurement",
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
    return {
        "amended_reviewed_technical_head": AMENDED_REVIEWED_TECHNICAL_HEAD,
        "original_reviewed_provenance": ORIGINAL_REVIEWED_PROVENANCE,
        "merged_contract_source": MERGED_CONTRACT_SOURCE,
        "evidence_checkout_head": repository_head(),
        "critical_fixture_manifest_sha256": MANIFEST_SHA,
        "pre_result_freeze_status": "frozen_before_measurement",
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
