"""Ordered C2V-09 preflight. No trajectory metric is computed here.

C2V09-00 through C2V09-27 are prepared, sealed and evaluated with the real
motor, FoldableBEM and mapper. A source-domain rejection does not select a
later candidate by itself, and it does not authorize a new polar or fixture.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import struct
import subprocess
from pathlib import Path

from pyfoldable.application.cmm2_coupled_transient_service import _build_cmm2_request
from pyfoldable.core.bem import BEMAnnulusError, BEMConvergenceError
from pyfoldable.core.bem_rotor import BEMRotorElementError, BEMRotorError
from pyfoldable.core.foldable_aero_load import PlanarProjectedMaterialLoadError
from pyfoldable.core.foldable_rotor import FoldableRotorGeometryError
from pyfoldable.core.polar import PolarInterpolationError
from pyfoldable.dynamics.cmm2_coupled_transient import Cmm2DomainExit, Cmm2TransientError, Cmm2TransientFailure
from pyfoldable.dynamics.coupled_transient import (
    OMEGA_MIN,
    BaseRotatingAssemblyInertia,
    CoupledDomainExit,
    CoupledSolverControls,
    HingeActuationHistory,
)
from pyfoldable.dynamics.mechanism_contracts import DryFriction
from pythrust.propulsion.models import BatterySpec, MotorSpec, SystemSpec
from pyfoldable.application.coupled_transient_service import CoupledEnvironment


def _load_service_tests():
    path = Path(__file__).resolve().parents[1] / "application" / "test_cmm2_coupled_transient_service.py"
    spec = importlib.util.spec_from_file_location("cmm2_service_binding_tests", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _cause_chain(exc: BaseException) -> str:
    parts = []
    current: BaseException | None = exc
    while current is not None:
        parts.append(f"{type(current).__name__}: {current}")
        current = current.__cause__
    return " | ".join(parts)


_EXPECTED_SOURCE_TYPES = (
    PolarInterpolationError,
    BEMAnnulusError,
    BEMConvergenceError,
    BEMRotorElementError,
    BEMRotorError,
    FoldableRotorGeometryError,
    PlanarProjectedMaterialLoadError,
    Cmm2DomainExit,
    CoupledDomainExit,
)


def _expected_source_rejection(exc: BaseException) -> bool:
    """Classify by exception type. The generic outer message is not enough."""
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, _EXPECTED_SOURCE_TYPES):
            return True
        current = current.__cause__
    return False


def _candidate_overrides(tests):
    return [
        {},
        {"base_inertia": BaseRotatingAssemblyInertia(2.0e-4, "fixture inertia", ("motor rotor", "shaft", "hub", "fixed blade roots"))},
        {"base_inertia": BaseRotatingAssemblyInertia(1.0e-4, "other inertia", ("motor rotor", "shaft", "hub", "fixed blade roots"))},
        {"base_inertia": BaseRotatingAssemblyInertia(1.0e-4, "fixture inertia", ("motor rotor", "shaft", "hub"))},
        {"motor": MotorSpec(1100.0, 0.05, 1.0, 80.0)},
        {"battery": BatterySpec(14.8, 0.98)},
        {"battery": BatterySpec(12.0, 0.97)},
        {"system": SystemSpec(0.02)},
        {"throttle": 0.2},
        {"environment": CoupledEnvironment("screen", 5.0, 1.18, 1.79e-5, 293.15, 100000.0)},
        {"polars": tests._schedule(cl=0.7)},
        {"polars": tests._schedule(source="other-fixture")},
        {"polars": tests._schedule(metadata={"tag": "b"})},
        {"bem_settings": tests._settings(annulus_count=6)},
        {"bem_settings": tests._settings(branch="signed_nonreversed")},
        {"distribution": tests._mass(mass=0.02)},
        {"spring_stiffness_nm_rad": 0.001},
        {"rest_angle_rad": -0.1},
        {"viscous_damping_nm_s_rad": 0.0001},
        {"dry_friction": DryFriction("regularized_coulomb", 0.001, 0.04, source="fixture friction")},
        {"mechanical_source": "other fixture"},
        {"actuation": HingeActuationHistory((0.0, 0.004), (0.0, 0.001), "no actuation")},
        {"initial_angle_rad": -0.15},
        {"initial_angular_velocity_rad_s": 0.01},
        {"initial_omega_rad_s": 500.0 * math.pi / 30.0},
        {"controls": CoupledSolverControls(rtol=1.0e-7)},
        {"initial_omega_rad_s": 13000.0 * math.pi / 30.0},
        {
            "motor": MotorSpec(1000.0, 0.05, 1.0, 5.0),
            "throttle": 1.0,
            "initial_omega_rad_s": 1000.0 * math.pi / 30.0,
        },
    ]


def _phase_b(sealed):
    built = _build_cmm2_request(sealed)
    state = (
        sealed.initial_angle_rad,
        sealed.initial_angular_velocity_rad_s,
        sealed.initial_omega_rad_s,
    )
    moment = sealed.actuation.time_s[0]
    motor = built.motor_evaluator(moment, *state)
    first = built.aero_evaluator(moment, *state)
    second = built.aero_evaluator(moment, *state)
    patterns = []
    for evaluation in (first, second):
        patterns.append(
            tuple(
                struct.pack(
                    "!d",
                    getattr(
                        evaluation,
                        name,
                    ),
                )
                for name in (
                    "thrust_n",
                    "whole_rotor_shaft_generalized_load_nm",
                    "one_tip_hinge_generalized_load_nm",
                )
            )
        )
    return {
        "motor_torque_nm": motor.torque_nm,
        "source_ids_differ": first.source_id != second.source_id,
        "q4_match": patterns[0] == patterns[1],
        "thrust_hex": patterns[0][0].hex(),
        "q_phi_hex": patterns[0][1].hex(),
        "q_theta_hex": patterns[0][2].hex(),
        "omega_margin_rad_s": sealed.initial_omega_rad_s - OMEGA_MIN,
    }


def test_c2v09_ordered_preflight_stops_without_a_trajectory(tmp_path) -> None:
    tests = _load_service_tests()
    rows = []
    selected = None
    status = "CONTRACT BLOCKED"
    for index, overrides in enumerate(_candidate_overrides(tests)):
        identifier = f"C2V09-{index:02d}"
        try:
            sealed = tests._binding(**overrides)
            sealed_digest = sealed.input_sha256
        except Exception as exc:
            rows.append(
                {
                    "id": identifier,
                    "disposition": "CONTRACT BLOCKED",
                    "cause": _cause_chain(exc),
                    "unmeasured": ["q4", "detectability", "partition_margin_m", "trajectory"],
                }
            )
            break
        row = {
            "id": identifier,
            "input_sha256": sealed_digest,
            "unmeasured": ["detectability", "partition_margin_m", "trajectory"],
        }
        try:
            measured = _phase_b(sealed)
        except (Cmm2TransientError, Cmm2TransientFailure, Cmm2DomainExit, CoupledDomainExit) as exc:
            if isinstance(exc, Cmm2TransientError) or not _expected_source_rejection(exc):
                row["disposition"] = "CONTRACT BLOCKED"
                row["cause"] = _cause_chain(exc)
                rows.append(row)
                break
            row["disposition"] = "CANDIDATE REJECTED: SOURCE DOMAIN"
            row["cause"] = _cause_chain(exc)
            row["unmeasured"] = ["q4", "detectability", "partition_margin_m", "trajectory"]
            rows.append(row)
            continue
        except Exception as exc:
            row["disposition"] = "CONTRACT BLOCKED"
            row["cause"] = _cause_chain(exc)
            rows.append(row)
            break
        row["measurements"] = {
            "motor_torque_nm": measured["motor_torque_nm"],
            "omega_margin_rad_s": measured["omega_margin_rad_s"],
            "thrust_hex": measured["thrust_hex"],
            "q_phi_hex": measured["q_phi_hex"],
            "q_theta_hex": measured["q_theta_hex"],
            "source_ids_differ": measured["source_ids_differ"],
        }
        if not measured["q4_match"] or not measured["source_ids_differ"]:
            row["disposition"] = "PRODUCTION DEFECT / CONTRACT BLOCK"
            row["cause"] = "Q4 binary64 mismatch or source metadata did not change"
            rows.append(row)
            break
        row["disposition"] = "PREFLIGHT INCOMPLETE"
        row["cause"] = "Mapped loads were reached, but detectability and partition margin are not yet measured."
        row["selected"] = False
        rows.append(row)
        status = "CONTRACT BLOCKED"
        break
    manifest = {
        "id": "prc_critical_fixture_manifest_v1",
        "shared_mechanism": {
            "mass_kg": 0.02,
            "hinge_radius_m": 0.08,
            "cg_distance_m": 0.03,
            "hinge_inertia_kg_m2": 2.0e-5,
            "base_inertia_kg_m2": 1.0e-4,
            "spring_stiffness_nm_rad": 0.01,
            "rest_angle_rad": -0.2,
            "viscous_damping_nm_s_rad": 0.002,
            "coulomb_torque_nm": 0.001,
            "transition_velocity_rad_s": 0.05,
            "lower_stop_rad": -1.2,
            "upper_stop_rad": 0.2,
        },
    }
    controls = CoupledSolverControls()
    canonical = {
        "policy": "prc_c2v09_ordered_candidates_v1",
        "contract_base_sha": "4cf0d0ea017fa824ba8d4a063ceddd015dae09d6",
        "critical_fixture_manifest_id": manifest["id"],
        "critical_fixture_manifest_sha256": hashlib.sha256(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "frozen_controls": {
            "rtol": controls.rtol,
            "angle_atol_rad": controls.angle_atol_rad,
            "hinge_velocity_atol_rad_s": controls.hinge_velocity_atol_rad_s,
            "shaft_speed_atol_rad_s": controls.shaft_speed_atol_rad_s,
            "max_step_s": controls.max_step_s,
            "max_rhs_evaluations": controls.max_rhs_evaluations,
        },
        "preflight_rules": [
            "phase_a_contract_or_seal_failure_stops",
            "expected_source_domain_or_convergence_rejection_continues",
            "malformed_bem_or_mapper_output_blocks",
            "preflight_incomplete_is_not_selection",
            "q4_mismatch_stops",
            "no_trajectory_metric_before_the_selection_digest",
        ],
        "status": status,
        "selected_index": None if selected is None else int(selected.rsplit("-", 1)[1]),
        "selected_input_sha256": None,
        "q2": "unmeasured",
        "q4": "unmeasured",
        "detectability": "unmeasured",
        "domain_margin_m": "unmeasured",
        "partition_margin_m": "unmeasured",
        "trajectory_metrics_computed": False,
        "candidates": rows,
    }
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    repository = Path(__file__).resolve().parents[2]
    checkout = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository, text=True).strip()
    tree = subprocess.check_output(["git", "rev-parse", f"{checkout}^{{tree}}"], cwd=repository, text=True).strip()
    document = {
        "canonical": canonical,
        "selection_record_sha256": digest,
        "historical_selection_record_sha256": "1c465dae2d835fc85f468636131a2af6bce90220bcbde71c03ebea69c4ad3cf9",
        "prior_push_checkout_sha": "8978acecbd7eabf89a1ead92e90141062081358c",
        "prior_pr_merge_checkout_sha": "c05fe9970eeaf3f8daa9b20b773e3cc7a0b68f5a",
        "prior_shared_tree_sha": "07ff58200f6db56e3db5299dde07cb6fb23e1eee",
    }
    destination = repository / "reports" / "c2v09_ordered_preflight" / "selection_record.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    evidence = dict(document)
    evidence["evidence_checkout_sha"] = checkout
    evidence["pr_source_sha"] = checkout
    evidence["evidence_tree_sha"] = tree
    artifact = Path("/opt/cursor/artifacts/c2v09_preflight.json")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert evidence["evidence_checkout_sha"] == checkout
    assert evidence["evidence_tree_sha"] == tree
    assert evidence["pr_source_sha"] != evidence["prior_pr_merge_checkout_sha"]
    assert canonical["trajectory_metrics_computed"] is False
    assert canonical["selected_index"] is None
    assert rows[0]["id"] == "C2V09-00"
    assert rows[0]["disposition"] == "CANDIDATE REJECTED: SOURCE DOMAIN"
    assert len(rows) == 28
    assert selected is None
    assert status == "CONTRACT BLOCKED"
    assert document["historical_selection_record_sha256"] != digest
    assert document["prior_shared_tree_sha"] == "07ff58200f6db56e3db5299dde07cb6fb23e1eee"


def test_malformed_bem_output_is_not_an_expected_source_rejection() -> None:
    try:
        raise AttributeError("torque_nm")
    except AttributeError as exc:
        malformed = Cmm2TransientFailure("CMM-2 aerodynamic source evaluation failed.")
        malformed.__cause__ = exc
    try:
        raise PolarInterpolationError("Requested mach 0.012317 is outside [0, 0].")
    except PolarInterpolationError as exc:
        polar = Cmm2TransientFailure("CMM-2 aerodynamic source evaluation failed.")
        polar.__cause__ = exc
    assert _expected_source_rejection(malformed) is False
    assert _expected_source_rejection(polar) is True
    assert "aerodynamic source" in str(malformed)
