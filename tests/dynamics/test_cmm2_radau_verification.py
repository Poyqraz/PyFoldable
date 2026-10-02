"""Radau v2 measurements required by the frozen remediation contract.

These are adapter and trajectory checks. They do not qualify a rotor and they
do not accept the separate PR-C evidence package.
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import json
import math
import struct
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate._ivp.radau import RadauDenseOutput

import pyfoldable.dynamics.cmm2_coupled_transient as cmm2_dynamics
from pyfoldable.dynamics.cmm2_radau_dense import first_radau_contact
from pyfoldable.dynamics.cmm2_coupled_transient import (
    IMPLEMENTATION_ID,
    IMPLEMENTATION_ID_V1,
    Cmm2AeroEvaluation,
    Cmm2DomainExit,
    Cmm2TransientError,
    Cmm2TransientFailure,
    Cmm2TransientRequest,
    solve_cmm2_transient,
)
from pyfoldable.dynamics.coupled_transient import (
    FOLD_LIMIT_RAD,
    OMEGA_MIN,
    CoupledSolverControls,
    MotorEvaluation,
)
def _load_test_module(filename: str):
    path = Path(__file__).resolve().parents[1] / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_helpers = _load_test_module("dynamics/test_cmm2_radau_remediation.py")
_aero = _helpers._aero
_loads = _helpers._loads
_mechanism = _helpers._mechanism
_scales = _helpers._scales
_system = _helpers._system


def _history(end: float, knots=None, values=None):
    from pyfoldable.dynamics.coupled_transient import HingeActuationHistory

    if knots is None:
        knots = (0.0, end)
        values = (0.0, 0.0)
    return HingeActuationHistory(knots, values, "verification")


def _request(system, actuation, theta, rate, omega, motor, aero, controls=None):
    return Cmm2TransientRequest(
        system,
        actuation,
        theta,
        rate,
        omega,
        motor,
        aero,
        CoupledSolverControls() if controls is None else controls,
    )


def test_budget_plus_one_fails_before_the_aero_callback() -> None:
    system = _system()
    calls = {"aero": 0, "motor": 0}

    def motor(*_args):
        calls["motor"] += 1
        return MotorEvaluation(0.04)

    def aero(time, theta, theta_dot, omega):
        calls["aero"] += 1
        return _aero(-0.02, 0.004, 2, 0.08, "budget")(time, theta, theta_dot, omega)

    with pytest.raises(Cmm2TransientFailure, match="CMM-2 work budget exhausted."):
        solve_cmm2_transient(
            _request(
                system,
                _history(0.2),
                -0.3,
                0.1,
                40.0,
                motor,
                aero,
                CoupledSolverControls(max_rhs_evaluations=1),
            )
        )
    assert calls["aero"] == 1
    assert calls["motor"] == 1


def test_radau_callbacks_count_constructor_jacobian_and_samples(monkeypatch) -> None:
    system = _system()
    calls = []
    solvers = []
    real = cmm2_dynamics.Radau

    class Observed(real):
        def __init__(self, fun, t0, y0, t_bound, *args, **kwargs):
            self._rejected = 0
            super().__init__(fun, t0, y0, t_bound, *args, **kwargs)
            solvers.append(self)

        def _step_impl(self):
            rejected_before = self._rejected
            h_before = self.h_abs
            outcome = super()._step_impl()
            if self.h_abs < h_before or getattr(self, "_saw_reject", False):
                self._rejected = rejected_before + 1
            return outcome

    real_step = real._step_impl

    def step_impl(self):
        h_before = self.h_abs
        n_before = self.nfev
        outcome = real_step(self)
        if self.h_abs < h_before and self.nfev > n_before:
            self._saw_reject = True
        return outcome

    monkeypatch.setattr(real, "_step_impl", step_impl)
    monkeypatch.setattr(cmm2_dynamics, "Radau", Observed)

    def aero(time, theta, theta_dot, omega):
        calls.append((time, theta, theta_dot, omega))
        return _aero(0.0, 0.0, 2, 0.08, f"call-{len(calls)}")(time, theta, theta_dot, omega)

    result = solve_cmm2_transient(
        _request(
            system,
            _history(0.02),
            -0.4,
            0.0,
            40.0,
            lambda *_args: MotorEvaluation(0.05),
            aero,
        )
    )
    assert result.status == "completed"
    assert solvers
    assert solvers[0].njev >= 1
    assert result.rhs_evaluations == result.aero_evaluations == len(calls)
    assert result.rhs_evaluations > len(result.samples)
    assert calls[0][0] == pytest.approx(0.0)
    published = {(sample.time_s, sample.theta_rad) for sample in result.samples}
    assert any((time, theta) not in published for time, theta, _rate, _omega in calls)


def test_rejected_radau_trial_is_inside_the_rhs_budget(monkeypatch) -> None:
    events = []
    real_step = cmm2_dynamics.Radau._step_impl

    def step_impl(self):
        width_before = float(self.h_abs)
        evaluations_before = self.nfev
        outcome = real_step(self)
        events.append((width_before, float(self.h_abs), self.nfev - evaluations_before))
        return outcome

    monkeypatch.setattr(cmm2_dynamics.Radau, "_step_impl", step_impl)
    system = _system()

    def aero(time, theta, theta_dot, omega):
        shaft = 2.0 if time >= 0.001 else 0.0
        return _aero(shaft, 0.2, 2, 0.08, "rejected")(time, theta, theta_dot, omega)

    result = solve_cmm2_transient(
        _request(
            system,
            _history(0.02),
            -0.2,
            5.0,
            40.0,
            lambda *_args: MotorEvaluation(0.2),
            aero,
        )
    )
    assert result.status == "completed"
    assert any(after < before for before, after, _delta in events)
    assert any(delta > 7 for _before, _after, delta in events)
    assert result.rhs_evaluations == result.aero_evaluations
    assert result.rhs_evaluations > len(result.samples)


def test_old_v1_result_identity_is_rejected() -> None:
    system = _system()
    result = solve_cmm2_transient(
        _request(
            system,
            _history(0.002),
            -0.4,
            0.0,
            40.0,
            lambda *_args: MotorEvaluation(0.05),
            _aero(0.0, 0.0, 2, 0.08, "v1-reject"),
        )
    )
    assert result.implementation_id == IMPLEMENTATION_ID
    with pytest.raises(Cmm2TransientError, match="identity"):
        dataclasses.replace(result, implementation_id=IMPLEMENTATION_ID_V1)


def test_c2v07_presnap_observer_uses_the_cubic_contact(monkeypatch) -> None:
    from pyfoldable.dynamics.coupled_transient import BaseRotatingAssemblyInertia, CoupledSystem

    system = CoupledSystem(
        _mechanism(-0.50, 0.20),
        2,
        BaseRotatingAssemblyInertia(
            1.0e-4,
            "prc fixture",
            ("motor rotor", "shaft", "hub", "fixed blade roots"),
        ),
    )
    controls = CoupledSolverControls()
    observed = []
    real = cmm2_dynamics.first_radau_contact

    def wrapper(dense, start, end, y0, y1, parameters, controls_arg, **kwargs):
        try:
            hit = real(dense, start, end, y0, y1, parameters, controls_arg, **kwargs)
        except Exception as exc:
            q_matrix = dense.Q
            y_old = dense.y_old
            print(
                "C2V07_CERTIFICATE",
                {
                    "failure": f"{type(exc).__name__}: {exc}",
                    "t_old_hex": float(dense.t_old).hex(),
                    "t_hex": float(dense.t).hex(),
                    "h_hex": float(dense.h).hex(),
                    "start": start,
                    "end": end,
                    "origin": kwargs.get("origin"),
                    "last_published": kwargs.get("last_published"),
                    "y_old_hex": [float(value).hex() for value in y_old],
                    "Q_hex": [[float(value).hex() for value in row] for row in q_matrix],
                },
                file=sys.stderr,
            )
            raise
        if hit is not None:
            observed.append((dense, float(start), float(end), hit, dense(hit[1])))
        return hit

    monkeypatch.setattr(cmm2_dynamics, "first_radau_contact", wrapper)

    def motor(*_args):
        return MotorEvaluation(0.04)

    def aero(time, theta, theta_dot, omega):
        target_theta = -0.20 - 0.40 * time
        q_phi, q_theta = _loads(system, target_theta, -0.40, 40.0, 0.0, 0.0, 0.04, 0.0)
        return _aero(q_phi, q_theta, 2, system.parameters.hinge_radius_m, "c2v07")(
            time, theta, theta_dot, omega
        )

    result = solve_cmm2_transient(
        _request(system, _history(1.0), -0.20, -0.40, 40.0, motor, aero, controls)
    )
    assert result.status == "first_contact_terminal"
    assert result.contact is not None
    assert result.contact.stop == "lower"
    assert observed
    _dense, start, end, hit, pre_snap = observed[0]
    event = hit[1]
    assert result.samples[-1].time_s == pytest.approx(event)
    assert result.samples[-1].theta_rad == pytest.approx(-0.50)
    assert all(sample.time_s <= event + 0.0 for sample in result.samples)
    target_theta = -0.20 - 0.40 * event
    scale = _scales((target_theta, -0.40, 40.0))
    assert abs(float(pre_snap[0]) - target_theta) <= scale[0]
    assert abs(float(pre_snap[1]) + 0.40) <= scale[1]
    assert abs(float(pre_snap[2]) - 40.0) <= scale[2]
    width = end - start
    nodes = (0.0, 0.25, 0.5, 0.75, 1.0)
    angles = [abs(float(_dense(start + width * node)[0])) for node in nodes]
    contact_scale = max(1.0, abs(-0.50), *angles)
    angle_tol = max(8 * controls.angle_atol_rad, 2 * math.ulp(contact_scale))
    assert abs(float(pre_snap[0]) - (-0.50)) <= 4 * angle_tol
    certificate = hit[4]
    assert certificate.selected_relative.hex() == event.hex()
    assert certificate.selected_public.hex() == float(hit[1]).hex()
    assert certificate.q_p == abs(certificate.public_exact - certificate.published_sum)
    assert certificate.root_time <= certificate.allowance
    xi = (event - start) / width
    allowance = Fraction.from_float(width * (1.0e-14 + 1.0e-14 * abs(xi)))
    assert certificate.allowance == allowance
    assert certificate.allowance_width == width
    assert certificate.allowance_xi == xi
    frozen = Fraction.from_float((scale[0] + 4 * angle_tol) / 0.40) + allowance
    assert abs(Fraction.from_float(event) - Fraction(3, 4)) <= frozen + certificate.q_r + certificate.q_p


def test_c2v08_fold_speed_budget_and_hard_failure() -> None:
    from pyfoldable.dynamics.coupled_transient import BaseRotatingAssemblyInertia, CoupledSystem

    system = CoupledSystem(
        _mechanism(-2.0, 0.5),
        2,
        BaseRotatingAssemblyInertia(
            1.0e-4,
            "prc fixture",
            ("motor rotor", "shaft", "hub", "fixed blade roots"),
        ),
    )
    calls = {"aero": 0}

    def aero(time, theta, theta_dot, omega):
        calls["aero"] += 1
        target = -1.20 - 1.00 * time
        q_phi, q_theta = _loads(system, target, -1.0, 40.0, 0.0, 0.0, 0.04, 0.0)
        return _aero(q_phi, q_theta, 2, system.parameters.hinge_radius_m, "fold")(
            time, theta, theta_dot, omega
        )

    with pytest.raises(Cmm2DomainExit):
        solve_cmm2_transient(
            _request(
                system,
                _history(0.5),
                -1.20,
                -1.0,
                40.0,
                lambda *_args: MotorEvaluation(0.04),
                aero,
            )
        )
    assert calls["aero"] > 0

    callback_calls = {"aero": 0}

    def unused_aero(*_args):
        callback_calls["aero"] += 1
        return _aero(0.0, 0.0, 2, 0.08, "unused")(*_args)

    with pytest.raises(Cmm2TransientError, match="100 rpm"):
        _request(
            _system(),
            _history(0.2),
            -0.3,
            0.0,
            10.0,
            lambda *_args: MotorEvaluation(0.04),
            unused_aero,
        )
    assert callback_calls["aero"] == 0

    def hard_aero(*_args):
        raise Cmm2TransientFailure("hard failure")

    with pytest.raises(Cmm2TransientFailure, match="hard failure"):
        solve_cmm2_transient(
            _request(
                _system(),
                _history(0.2),
                -0.3,
                0.1,
                40.0,
                lambda *_args: MotorEvaluation(0.04),
                hard_aero,
            )
        )


def test_c2v10_restarts_radau_at_the_interior_knot(monkeypatch) -> None:
    from pyfoldable.dynamics.coupled_transient import HingeActuationHistory

    system = _system()
    starts = []
    real = cmm2_dynamics.Radau

    class Counting(real):
        def __init__(self, fun, t0, y0, t_bound, *args, **kwargs):
            starts.append(float(t0))
            super().__init__(fun, t0, y0, t_bound, *args, **kwargs)

    monkeypatch.setattr(cmm2_dynamics, "Radau", Counting)
    result = solve_cmm2_transient(
        Cmm2TransientRequest(
            system,
            HingeActuationHistory((0.0, 0.4, 0.8), (0.0, 0.002, -0.001), "c2v10"),
            -0.3,
            0.1,
            40.0,
            lambda *_args: MotorEvaluation(0.04),
            _aero(-0.02, 0.004, 2, 0.08, "c2v10"),
            CoupledSolverControls(),
        )
    )
    assert result.status == "completed"
    assert starts == [0.0, 0.4]
    assert result.segment_boundary_times_s == (0.0, 0.4, 0.8)
    assert result.samples[-1].time_s == pytest.approx(0.8)
    times = [sample.time_s for sample in result.samples]
    assert times[0] == pytest.approx(0.0)
    assert any(math.isclose(time, 0.4) for time in times)
    for earlier, later in zip(result.samples, result.samples[1:]):
        assert later.time_s > earlier.time_s
    by_time = {sample.time_s: sample.hinge_actuation_nm for sample in result.samples}
    assert by_time[0.0] == pytest.approx(0.0)
    knot = next(time for time in by_time if math.isclose(time, 0.4))
    assert by_time[knot] == pytest.approx(0.002)
    assert by_time[result.samples[-1].time_s] == pytest.approx(-0.001)


def test_q4_signed_zero_and_metadata_do_not_change_load_bits() -> None:
    assert struct.pack("!d", 0.0) != struct.pack("!d", -0.0)
    left = Cmm2AeroEvaluation(
        0.0,
        -0.0,
        0.25,
        "planar_projected_material_load_v1",
        "screening_only_projected_rate_independent",
        "radial_cosine_v1",
        "ignored_rate_independent_quasi_steady",
        2,
        0.08,
        -0.2,
        0.0,
        "index-0",
    )
    right = Cmm2AeroEvaluation(
        0.0,
        -0.0,
        0.25,
        "planar_projected_material_load_v1",
        "screening_only_projected_rate_independent",
        "radial_cosine_v1",
        "ignored_rate_independent_quasi_steady",
        2,
        0.08,
        -0.2,
        0.0,
        "index-1",
    )
    assert left.source_id != right.source_id
    for field in (
        "whole_rotor_shaft_generalized_load_nm",
        "one_tip_hinge_generalized_load_nm",
        "thrust_n",
    ):
        assert struct.pack("!d", getattr(left, field)) == struct.pack("!d", getattr(right, field))
    assert struct.pack("!d", left.whole_rotor_shaft_generalized_load_nm) == struct.pack("!d", 0.0)
    assert struct.pack("!d", left.one_tip_hinge_generalized_load_nm) == struct.pack("!d", -0.0)


def test_c2v09_first_candidate_is_rejected_by_the_real_source_domain() -> None:
    """C2V09-00 is the first frozen candidate. Its real BEM call is not replaced."""
    from pyfoldable.application.cmm2_coupled_transient_service import (
        _build_cmm2_request,
        run_cmm2_coupled_transient,
    )
    binding = _load_test_module("application/test_cmm2_coupled_transient_service.py")._binding()
    assert binding.initial_omega_rad_s > OMEGA_MIN
    assert abs(binding.initial_angle_rad) < FOLD_LIMIT_RAD
    fresh = _build_cmm2_request(binding)
    initial = (
        binding.initial_angle_rad,
        binding.initial_angular_velocity_rad_s,
        binding.initial_omega_rad_s,
    )
    with pytest.raises(Cmm2TransientFailure, match="aerodynamic source evaluation failed"):
        fresh.aero_evaluator(0.0, *initial)
    with pytest.raises(Cmm2TransientFailure, match="aerodynamic source evaluation failed"):
        run_cmm2_coupled_transient(binding)


def test_c2v07_certificate_is_conversion_infeasible() -> None:
    """The archived cubic stays a historical old-policy failure.

    The amended converter may publish a timestamp for the same cubic. That
    result does not rewrite the stored certificate.
    """

    def hex_float(text: str) -> float:
        return float.fromhex(text)

    repository = Path(__file__).resolve().parents[2]
    replay_path = repository / "reports" / "c2v07_representability" / "coefficient_replay_inputs.json"
    rational_path = repository / "reports" / "c2v07_representability" / "rational_mathematical_certificate.json"
    replay = json.loads(replay_path.read_text(encoding="utf-8"))
    rational = json.loads(rational_path.read_text(encoding="utf-8"))
    assert replay["record_kind"] == "coefficient_replay_inputs"
    assert rational["record_kind"] == "explicit_rational_mathematical_certificate"
    assert rational["method"] == "fractions.Fraction.from_float"
    assert rational["source_record_sha256"] == hashlib.sha256(replay_path.read_bytes()).hexdigest()
    assert "not an independent algebraic derivation" in rational["proof"]

    def fraction_text(text: str) -> str:
        value = Fraction.from_float(hex_float(text))
        return f"{value.numerator}/{value.denominator}"

    assert rational["t_old"] == fraction_text(replay["t_old_hex"])
    assert rational["Q"] == [[fraction_text(value) for value in row] for row in replay["Q_hex"]]
    y_old = np.array([hex_float(value) for value in replay["y_old_hex"]])
    q_matrix = np.array([[hex_float(value) for value in row] for row in replay["Q_hex"]])
    t_old = hex_float(replay["t_old_hex"])
    step = hex_float(replay["h_hex"])
    dense = RadauDenseOutput(t_old, t_old + step, y_old, q_matrix)
    certificate = replay

    class Parameters:
        lower_stop_rad = -0.5
        upper_stop_rad = 0.2

    class Controls:
        atol = 1.0e-8
        atol_angular_velocity_rad_s = 1.0e-8

    historical_old_policy = "CMM-2 contact time conversion is unresolved."
    hit = first_radau_contact(
        dense,
        certificate["start"],
        certificate["end"],
        dense(certificate["start"]),
        dense(certificate["end"]),
        Parameters(),
        Controls(),
        origin=certificate["origin"],
        last_published=certificate["last_published"],
    )
    assert historical_old_policy == "CMM-2 contact time conversion is unresolved."
    assert hit is not None
    assert hit[0] == "lower"
    certificate = hit[4]
    archived_upper = float.fromhex("0x1.7fffffffff83ap-1")
    assert certificate.selected_relative.hex() == archived_upper.hex()
    assert certificate.selected_public.hex() == archived_upper.hex()
    assert certificate.z == Fraction(52776558117645, 140737488355328)
    assert certificate.radius == Fraction(1, 2**47)
    assert certificate.root_time == Fraction(9007199254741, 2**99)
    assert certificate.q_r == Fraction(30540034973231, 2**99)
    assert certificate.q_p == 0
