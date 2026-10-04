"""C2V-07 execution diagnostic. It does not change the converter or the acceptance test.

Run one fresh process with::

    PYTHONPATH=. python tests/dynamics/c2v07_execution_diagnostic.py --label isolated
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import sys
from pathlib import Path

import numpy
import scipy
from scipy.integrate._ivp.radau import RadauDenseOutput

import pyfoldable.dynamics.cmm2_coupled_transient as cmm2_dynamics
from pyfoldable.dynamics.cmm2_radau_dense import first_radau_contact
from pyfoldable.dynamics.coupled_transient import CoupledSolverControls, MotorEvaluation


ROOT = Path(__file__).resolve().parents[2]
ARCHIVED_REPLAY = ROOT / "reports" / "c2v07_representability" / "coefficient_replay_inputs.json"
PUSH_RUN = "36888456607"
PR_RUN = "36888462991"
PUSH_CHECKOUT = "3fff759a75573e2c888d11ce99b372847568d957"
PR_MERGE_CHECKOUT = "31c0d4c0ebe37736fadd918e945dba705876d609"
PR_SOURCE_HEAD = PUSH_CHECKOUT
SHARED_TREE = "5f615822180f935b395b3cadd2ec2ad3979c08f0"


def _load_verification():
    path = Path(__file__).resolve().parent / "test_cmm2_radau_verification.py"
    spec = importlib.util.spec_from_file_location("c2v07_verification_helpers", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _hex_float(text: str) -> float:
    return float.fromhex(text)


def _blas_summary() -> dict[str, object]:
    summary: dict[str, object] = {"numpy": numpy.__version__, "scipy": scipy.__version__}
    show = getattr(numpy, "show_config", None)
    if show is not None:
        try:
            summary["numpy_config"] = show(mode="dicts")
        except TypeError:
            summary["numpy_config"] = "show_config does not accept mode='dicts'"
    return summary


def environment_record() -> dict[str, object]:
    keys = (
        "OPENBLAS_NUM_THREADS",
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "OPENBLAS_MAIN_FREE",
        "MKL_DYNAMIC",
        "VECLIB_MAXIMUM_THREADS",
    )
    return {
        "python": sys.version,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "thread_environment": {key: os.environ.get(key) for key in keys},
        "packages": _blas_summary(),
    }


def fixture_payload(controls: CoupledSolverControls) -> dict[str, object]:
    return {
        "case": "C2V-07",
        "blade_count": 2,
        "lower_stop_rad": -0.50,
        "upper_stop_rad": 0.20,
        "duration_s": 1.0,
        "initial_angle_rad": -0.20,
        "initial_rate_rad_s": -0.40,
        "initial_omega_rad_s": 40.0,
        "motor_torque_nm": 0.04,
        "theta_formula": "theta*(t) = -0.20 - 0.40 t",
        "controls": {
            "rtol": controls.rtol,
            "angle_atol_rad": controls.angle_atol_rad,
            "hinge_velocity_atol_rad_s": controls.hinge_velocity_atol_rad_s,
            "shaft_speed_atol_rad_s": controls.shaft_speed_atol_rad_s,
            "max_step_s": controls.max_step_s,
            "max_rhs_evaluations": controls.max_rhs_evaluations,
        },
    }


def fixture_digest(controls: CoupledSolverControls) -> str:
    payload = json.dumps(fixture_payload(controls), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _interval_record(dense, start, end, parameters, controls, kwargs, call_index: int) -> dict[str, object]:
    q_matrix = dense.Q
    y_old = dense.y_old
    return {
        "call_index": call_index,
        "t_old_hex": float(dense.t_old).hex(),
        "t_hex": float(dense.t).hex(),
        "h_hex": float(dense.h).hex(),
        "start": start,
        "end": end,
        "origin": kwargs.get("origin"),
        "last_published": kwargs.get("last_published"),
        "lower_stop_rad": parameters.lower_stop_rad,
        "upper_stop_rad": parameters.upper_stop_rad,
        "atol": controls.atol,
        "atol_angular_velocity_rad_s": controls.atol_angular_velocity_rad_s,
        "y_old_hex": [float(value).hex() for value in y_old],
        "Q_hex": [[float(value).hex() for value in row] for row in q_matrix],
    }


def replay_interval(interval: dict[str, object]) -> str:
    """Classify one captured cubic with the unchanged public converter."""
    y_old = numpy.array([_hex_float(value) for value in interval["y_old_hex"]])
    q_matrix = numpy.array([[_hex_float(value) for value in row] for row in interval["Q_hex"]])
    t_old = _hex_float(interval["t_old_hex"])
    step = _hex_float(interval["h_hex"])
    dense = RadauDenseOutput(t_old, t_old + step, y_old, q_matrix)

    class Parameters:
        lower_stop_rad = interval["lower_stop_rad"]
        upper_stop_rad = interval["upper_stop_rad"]

    class Controls:
        atol = interval["atol"]
        atol_angular_velocity_rad_s = interval["atol_angular_velocity_rad_s"]

    try:
        hit = first_radau_contact(
            dense,
            interval["start"],
            interval["end"],
            dense(interval["start"]),
            dense(interval["end"]),
            Parameters(),
            Controls(),
            origin=interval["origin"],
            last_published=interval["last_published"],
        )
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    if hit is None:
        return "no_contact"
    return "contact"


def archived_failure_interval() -> dict[str, object]:
    replay = json.loads(ARCHIVED_REPLAY.read_text(encoding="utf-8"))
    return {
        "call_index": None,
        "t_old_hex": replay["t_old_hex"],
        "t_hex": replay["t_hex"],
        "h_hex": replay["h_hex"],
        "start": replay["start"],
        "end": replay["end"],
        "origin": replay["origin"],
        "last_published": replay["last_published"],
        "lower_stop_rad": -0.50,
        "upper_stop_rad": 0.20,
        "atol": 1.0e-8,
        "atol_angular_velocity_rad_s": 1.0e-8,
        "y_old_hex": replay["y_old_hex"],
        "Q_hex": replay["Q_hex"],
        "source": "reports/c2v07_representability/coefficient_replay_inputs.json",
    }


def capture_c2v07(label: str) -> dict[str, object]:
    """Run the C2V-07 analytic fixture once and record every contact call."""
    verification = _load_verification()
    mechanism = verification._mechanism(-0.50, 0.20)
    from pyfoldable.dynamics.coupled_transient import BaseRotatingAssemblyInertia, CoupledSystem

    assembly = CoupledSystem(
        mechanism,
        2,
        BaseRotatingAssemblyInertia(
            1.0e-4,
            "prc fixture",
            ("motor rotor", "shaft", "hub", "fixed blade roots"),
        ),
    )
    controls = CoupledSolverControls()
    contacts: list[dict[str, object]] = []
    real = cmm2_dynamics.first_radau_contact

    def wrapper(dense, start, end, y0, y1, parameters, controls_arg, **kwargs):
        record = _interval_record(dense, start, end, parameters, controls_arg, kwargs, len(contacts))
        try:
            hit = real(dense, start, end, y0, y1, parameters, controls_arg, **kwargs)
        except Exception as exc:
            record["event"] = "failure"
            record["classification"] = f"{type(exc).__name__}: {exc}"
            contacts.append(record)
            raise
        record["event"] = "no_contact" if hit is None else "contact"
        record["classification"] = record["event"]
        contacts.append(record)
        return hit

    cmm2_dynamics.first_radau_contact = wrapper
    outcome = "completed"
    failure = None
    try:
        def motor(*_args):
            return MotorEvaluation(0.04)

        def aero(time, theta, theta_dot, omega):
            target_theta = -0.20 - 0.40 * time
            q_phi, q_theta = verification._loads(
                assembly, target_theta, -0.40, 40.0, 0.0, 0.0, 0.04, 0.0
            )
            return verification._aero(q_phi, q_theta, 2, assembly.parameters.hinge_radius_m, "c2v07-diagnostic")(
                time, theta, theta_dot, omega
            )

        result = verification.solve_cmm2_transient(
            verification._request(
                assembly,
                verification._history(1.0),
                -0.20,
                -0.40,
                40.0,
                motor,
                aero,
                controls,
            )
        )
        status = result.status
    except Exception as exc:
        outcome = "exception"
        failure = f"{type(exc).__name__}: {exc}"
        status = None
    finally:
        cmm2_dynamics.first_radau_contact = real
    digest = fixture_digest(controls)
    lineage = [
        {
            "call_index": row["call_index"],
            "event": row["event"],
            "classification": row["classification"],
            "t_old_hex": row["t_old_hex"],
            "h_hex": row["h_hex"],
            "start": row["start"],
            "end": row["end"],
        }
        for row in contacts
    ]
    return {
        "label": label,
        "outcome": outcome,
        "status": status,
        "failure": failure,
        "fixture_digest": digest,
        "fixture": fixture_payload(controls),
        "environment": environment_record(),
        "provenance": {
            "pr_source_head": PR_SOURCE_HEAD,
            "push_checkout": PUSH_CHECKOUT,
            "pr_merge_checkout": PR_MERGE_CHECKOUT,
            "shared_tree": SHARED_TREE,
            "push_run": PUSH_RUN,
            "pull_request_run": PR_RUN,
            "note": (
                "Push checkout and PR merge checkout are different commits with the "
                "same tree. Workflow head SHA is the PR source head, not the merge checkout."
            ),
        },
        "contacts": contacts,
        "lineage": lineage,
    }


def compare_inputs(left: dict[str, object], right: dict[str, object]) -> bool:
    keys = ("t_old_hex", "h_hex", "y_old_hex", "Q_hex", "start", "end", "origin", "last_published")
    return all(left.get(key) == right.get(key) for key in keys)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="isolated")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    captured = capture_c2v07(args.label)
    archived = archived_failure_interval()
    archived_class = replay_interval(archived)
    archived_repeat = replay_interval(archived)
    replays = []
    for row in captured["contacts"]:
        replays.append(
            {
                "call_index": row["call_index"],
                "live": row["classification"],
                "replay": replay_interval(row),
                "same_as_archived_failure": compare_inputs(row, archived),
            }
        )
    captured["archived_failure_replay"] = archived_class
    captured["archived_failure_replay_repeat"] = archived_repeat
    captured["replays"] = replays
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(captured, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.label, captured["outcome"], captured["failure"], "contacts", len(captured["contacts"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
