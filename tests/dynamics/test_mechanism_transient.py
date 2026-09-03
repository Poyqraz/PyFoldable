import math

import numpy as np
import pytest

from pyfoldable.dynamics.mechanism_transient import (
    DriveHistory,
    MechanismParameters,
    SolverControls,
    TransientRequest,
    solve_mechanism_transient,
)


def parameters(**changes):
    values = dict(mass_kg=0.2, cg_distance_m=0.1, hinge_inertia_kg_m2=0.003,
                  hinge_radius_m=0.08, spring_stiffness_nm_rad=0.3,
                  rest_angle_rad=0.0, viscous_damping_nm_s_rad=0.02,
                  lower_stop_rad=-1.2, upper_stop_rad=1.2)
    values.update(changes)
    return MechanismParameters(**values)


def request(params, drive, **changes):
    values = dict(parameters=params, drive=drive, initial_angle_rad=0.4,
                  initial_angular_velocity_rad_s=0.0,
                  controls=SolverControls(rtol=1e-9, atol=1e-11, max_step_s=0.002,
                                          max_samples=20_000))
    values.update(changes)
    return TransientRequest(**values)


def test_explicit_si_validation_and_budgets_fail_closed():
    with pytest.raises(ValueError, match="J >= m c²"):
        parameters(hinge_inertia_kg_m2=0.001)
    with pytest.raises(ValueError, match="strictly increasing"):
        DriveHistory((0.0, 0.0), (0.0, 100.0), (0.0, 0.0))
    with pytest.raises(ValueError, match="strictly inside"):
        request(parameters(), DriveHistory((0.0, 1.0), (0.0, 0.0), (0.0, 0.0)),
                initial_angle_rad=1.2)
    with pytest.raises(ValueError, match="budget"):
        SolverControls(max_samples=99)


def test_zero_rpm_undamped_oscillator_matches_analytic_solution_and_energy():
    p = parameters(viscous_damping_nm_s_rad=0.0, lower_stop_rad=-2.0, upper_stop_rad=2.0)
    drive = DriveHistory((0.0, 0.4), (0.0, 0.0), (0.0, 0.0))
    result = solve_mechanism_transient(request(p, drive))
    omega_n = math.sqrt(p.spring_stiffness_nm_rad / p.hinge_inertia_kg_m2)
    expected = 0.4 * np.cos(omega_n * np.asarray(result.time_s))
    assert np.max(np.abs(np.asarray(result.angle_rad) - expected)) < 2e-7
    assert max(result.effective_energy_j) - min(result.effective_energy_j) < 2e-9


def test_viscous_oscillator_decays_and_dissipated_energy_has_right_sign():
    p = parameters(lower_stop_rad=-2.0, upper_stop_rad=2.0)
    result = solve_mechanism_transient(request(p, DriveHistory((0.0, 1.0), (0.0, 0.0), (0.0, 0.0))))
    assert result.effective_energy_j[-1] < result.effective_energy_j[0]
    assert all(value >= -1e-12 for value in result.damping_power_w)


def test_r_zero_torque_free_preserves_inertial_angle_during_ramp():
    p = parameters(hinge_radius_m=0.0, spring_stiffness_nm_rad=0.0,
                   viscous_damping_nm_s_rad=0.0, lower_stop_rad=-3.0, upper_stop_rad=3.0)
    drive = DriveHistory((0.0, 0.3, 0.7), (0.0, 1200.0, 600.0), (0.0, 0.0, 0.0))
    result = solve_mechanism_transient(request(p, drive, initial_angle_rad=0.1,
                                               initial_angular_velocity_rad_s=2.0))
    inertial_rate = np.asarray(result.angular_velocity_rad_s) + np.asarray(result.omega_rad_s)
    assert np.max(np.abs(inertial_rate - 2.0)) < 2e-7


def test_constant_rpm_centrifugal_moment_and_euler_sign():
    p = parameters(spring_stiffness_nm_rad=0.0, viscous_damping_nm_s_rad=0.0)
    const = solve_mechanism_transient(request(p, DriveHistory((0.0, 0.01), (600.0, 600.0), (0.0, 0.0)),
                                              initial_angle_rad=-0.3))
    expected = -p.mass_kg * p.hinge_radius_m * p.cg_distance_m * const.omega_rad_s[0] ** 2 * math.sin(-0.3)
    assert const.centrifugal_torque_nm[0] == pytest.approx(expected)
    ramp = solve_mechanism_transient(request(p, DriveHistory((0.0, 0.01), (0.0, 60.0), (0.0, 0.0)),
                                             initial_angle_rad=0.0))
    assert ramp.angular_acceleration_rad_s2[0] < 0.0
    assert ramp.euler_torque_nm[0] < 0.0


def test_first_stop_is_terminal_and_reports_preimpact_velocity():
    p = parameters(spring_stiffness_nm_rad=0.0, viscous_damping_nm_s_rad=0.0,
                   lower_stop_rad=-0.5, upper_stop_rad=0.5)
    result = solve_mechanism_transient(request(p, DriveHistory((0.0, 1.0), (0.0, 0.0), (0.0, 0.0)),
                                              initial_angle_rad=0.0, initial_angular_velocity_rad_s=2.0))
    assert result.status == "stop_contact"
    assert result.contact.stop == "upper"
    assert result.contact.time_s == pytest.approx(0.25, abs=2e-7)
    assert result.contact.preimpact_angular_velocity_rad_s == pytest.approx(2.0)
    assert result.time_s[-1] == result.contact.time_s


def test_integration_restarts_at_drive_knots_and_is_continuous():
    drive = DriveHistory((0.0, 0.2, 0.5), (0.0, 1000.0, 500.0), (0.0, 0.1, 0.0))
    result = solve_mechanism_transient(request(parameters(lower_stop_rad=-2, upper_stop_rad=2), drive))
    assert 0.2 in result.time_s
    index = result.time_s.index(0.2)
    assert result.rpm[index] == pytest.approx(1000.0)
    assert result.segment_start_indices == (0, index)
    assert result.omega_dot_rad_s2[index] < 0  # right-limit/new-segment convention
