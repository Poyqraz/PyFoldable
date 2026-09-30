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
from pathlib import Path

from pyfoldable.application.cmm2_coupled_transient_service import _build_cmm2_request
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


def _source_rejection(exc: BaseException) -> bool:
    if isinstance(exc, (Cmm2DomainExit, CoupledDomainExit)):
        return True
    if not isinstance(exc, Cmm2TransientFailure):
        return False
    text = _cause_chain(exc)
    markers = (
        "PolarInterpolationError",
        "BEMAnnulusError",
        "BEMConvergenceError",
        "BEMRotorElementError",
        "BEMRotorError",
        "FoldableRotorGeometryError",
        "aerodynamic source",
        "motoring",
        "current",
    )
    return any(marker in text for marker in markers)


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
            if isinstance(exc, Cmm2TransientError) or not _source_rejection(exc):
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
        rows.append(row)
        selected = identifier
        status = "CONTRACT BLOCKED"
        break
    record = {
        "policy": "prc_c2v09_ordered_candidates_v1",
        "status": status,
        "selected": selected,
        "trajectory_metrics_computed": False,
        "candidates": rows,
    }
    payload = json.dumps(record, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    record["selection_record_sha256"] = digest
    destination = Path("/opt/cursor/artifacts/c2v09_preflight.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    assert record["trajectory_metrics_computed"] is False
    assert rows[0]["id"] == "C2V09-00"
    assert rows[0]["disposition"] == "CANDIDATE REJECTED: SOURCE DOMAIN"
    assert len(rows) == 28
    assert selected is None
    assert status == "CONTRACT BLOCKED"
    assert digest
