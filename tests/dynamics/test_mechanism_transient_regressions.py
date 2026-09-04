import math
import unittest

from pyfoldable.dynamics.mechanism_contracts import DryFriction
from pyfoldable.dynamics.mechanism_transient import (
    DriveHistory,
    MechanismParameters,
    SolverControls,
    TransientRequest,
    solve_mechanism_transient,
)


def params(**changes):
    values = dict(
        mass_kg=1.0,
        cg_distance_m=0.0,
        hinge_inertia_kg_m2=1.0,
        hinge_radius_m=0.0,
        spring_stiffness_nm_rad=0.0,
        rest_angle_rad=0.0,
        viscous_damping_nm_s_rad=0.0,
        lower_stop_rad=-10.0,
        upper_stop_rad=10.0,
    )
    values.update(changes)
    return MechanismParameters(**values)


def request(parameters, drive, **changes):
    values = dict(
        parameters=parameters,
        drive=drive,
        initial_angle_rad=0.0,
        initial_angular_velocity_rad_s=0.0,
        controls=SolverControls(rtol=1e-8, atol=1e-10,
                                atol_angular_velocity_rad_s=1e-9,
                                max_step_s=1.0, max_samples=1000),
    )
    values.update(changes)
    return TransientRequest(**values)


class MechanismTransientRegressionTests(unittest.TestCase):
    def test_hidden_out_and_back_contact_is_the_earliest_crossing(self):
        # theta = 13.5*t^2 - 13.5*t^3 has endpoints at zero but exceeds 1.
        drive = DriveHistory((0.0, 1.0), (0.0, 0.0), (27.0, -54.0))
        result = solve_mechanism_transient(
            request(params(upper_stop_rad=1.0), drive)
        )
        self.assertEqual(result.status, "stop_contact")
        self.assertEqual(result.contact.stop, "upper")
        self.assertLess(result.contact.time_s, 2.0 / 3.0)
        self.assertAlmostEqual(result.contact.angle_rad, 1.0, places=8)
        self.assertGreater(result.contact.preimpact_angular_velocity_rad_s, 0.0)

        mirrored = solve_mechanism_transient(
            request(
                params(lower_stop_rad=-1.0),
                DriveHistory((0.0, 1.0), (0.0, 0.0), (-27.0, 54.0)),
            )
        )
        self.assertEqual(mirrored.status, "stop_contact")
        self.assertEqual(mirrored.contact.stop, "lower")
        self.assertAlmostEqual(mirrored.contact.time_s, result.contact.time_s, places=9)
        self.assertLess(mirrored.contact.preimpact_angular_velocity_rad_s, 0.0)

    def test_tangent_contact_is_not_published_as_no_contact(self):
        drive = DriveHistory((0.0, 1.0), (0.0, 0.0), (27.0, -54.0))
        result = solve_mechanism_transient(
            request(params(upper_stop_rad=2.0), drive)
        )
        self.assertEqual(result.status, "stop_contact")
        self.assertAlmostEqual(result.contact.time_s, 2.0 / 3.0, places=7)
        self.assertAlmostEqual(result.contact.preimpact_angular_velocity_rad_s, 0.0, places=6)

    def test_nearby_noncontact_and_large_angle_are_not_false_contacts(self):
        drive = DriveHistory((0.0, 1.0), (0.0, 0.0), (27.0, -54.0))
        no_hit = solve_mechanism_transient(
            request(params(upper_stop_rad=2.01), drive)
        )
        self.assertEqual(no_hit.status, "completed")
        large = solve_mechanism_transient(request(
            params(lower_stop_rad=99.0, upper_stop_rad=103.0),
            DriveHistory((0.0, 0.1), (0.0, 0.0), (0.0, 0.0)),
            initial_angle_rad=100.0,
        ))
        self.assertEqual(large.status, "completed")

        # Absolute angle magnitude must not turn the solver tolerance into a
        # false stop hit when the trajectory is stationary and still inside.
        base = 1.0e10
        large_near_stop = solve_mechanism_transient(request(
            params(lower_stop_rad=base - 1.0, upper_stop_rad=base + 0.1),
            DriveHistory((0.0, 0.1), (0.0, 0.0), (0.0, 0.0)),
            initial_angle_rad=base + 0.1 - 1.0e-5,
        ))
        self.assertEqual(large_near_stop.status, "completed")

    def test_signed_rpm_preserves_inertial_rate_and_sign_symmetry(self):
        p = params(lower_stop_rad=-100.0, upper_stop_rad=100.0)
        positive = solve_mechanism_transient(request(
            p, DriveHistory((0.0, 0.3), (0.0, 600.0), (0.0, 0.0)),
            initial_angle_rad=0.1,
        ))
        negative = solve_mechanism_transient(request(
            p, DriveHistory((0.0, 0.3), (0.0, -600.0), (0.0, 0.0)),
            initial_angle_rad=-0.1,
        ))
        self.assertAlmostEqual(
            positive.angular_velocity_rad_s[-1] + positive.omega_rad_s[-1],
            0.0, places=7,
        )
        self.assertAlmostEqual(
            negative.angular_velocity_rad_s[-1] + negative.omega_rad_s[-1],
            0.0, places=7,
        )
        self.assertAlmostEqual(positive.angle_rad[-1], -negative.angle_rad[-1], places=7)

    def test_inertia_boundary_is_scale_tolerant_but_not_relaxed(self):
        boundary = MechanismParameters(
            mass_kg=0.2, cg_distance_m=0.1, hinge_inertia_kg_m2=0.002,
            hinge_radius_m=0.0, spring_stiffness_nm_rad=0.0,
            rest_angle_rad=0.0, viscous_damping_nm_s_rad=0.0,
            lower_stop_rad=-1.0, upper_stop_rad=1.0,
        )
        self.assertEqual(boundary.hinge_inertia_kg_m2, 0.002)
        with self.assertRaisesRegex(ValueError, "J >= m c²"):
            params(mass_kg=0.2, cg_distance_m=0.1,
                   hinge_inertia_kg_m2=0.001999)
        with self.assertRaisesRegex(ValueError, "J >= m c²"):
            params(
                mass_kg=1.0e-160,
                cg_distance_m=1.0e-80,
                hinge_inertia_kg_m2=1.0e-321,
            )

    def test_component_velocity_tolerance_and_sample_preflight(self):
        controls = SolverControls(atol=1e-11,
                                  atol_angular_velocity_rad_s=2e-8)
        self.assertEqual(controls.atol_angular_velocity_rad_s, 2e-8)
        with self.assertRaisesRegex(ValueError, "sample budget"):
            request(
                params(), DriveHistory((0.0, 1.0), (0.0, 0.0), (0.0, 0.0)),
                controls=SolverControls(max_step_s=0.001, max_samples=100),
            )

    def test_legacy_solver_control_positionals_remain_compatible(self):
        controls = SolverControls(1e-8, 1e-10, 0.002, 20_000, 256, 60.0)
        self.assertEqual(controls.max_step_s, 0.002)
        self.assertEqual(controls.max_samples, 20_000)
        self.assertEqual(controls.atol_angular_velocity_rad_s, 1e-10)

    def test_terminal_contact_cannot_append_past_sample_budget(self):
        with self.assertRaisesRegex(RuntimeError, "sample budget"):
            solve_mechanism_transient(request(
                params(lower_stop_rad=-100.0, upper_stop_rad=97.5),
                DriveHistory((0.0, 0.099), (0.0, 0.0), (0.0, 0.0)),
                initial_angular_velocity_rad_s=1000.0,
                controls=SolverControls(max_step_s=0.001, max_samples=100),
            ))

    def test_coarse_absolute_time_origin_is_rejected_and_safe_origin_is_invariant(self):
        p = params()
        base = solve_mechanism_transient(request(
            p, DriveHistory((0.0, 0.2), (0.0, 0.0), (1.0, 1.0))))
        shifted = solve_mechanism_transient(request(
            p, DriveHistory((10.0, 10.2), (0.0, 0.0), (1.0, 1.0))))
        self.assertAlmostEqual(base.angle_rad[-1], shifted.angle_rad[-1], places=10)
        with self.assertRaisesRegex(ValueError, "timestamp resolution"):
            request(
                p, DriveHistory((1e12, 1e12 + 0.125), (0.0, 0.0), (0.0, 0.0)),
                controls=SolverControls(max_step_s=1e-6, max_samples=200_000),
            )
        with self.assertRaisesRegex(ValueError, "timestamp resolution"):
            request(
                p,
                DriveHistory(
                    (1.0e12, 1.0e12 + 0.01),
                    (0.0, 0.0),
                    (0.0, 0.0),
                ),
                controls=SolverControls(max_step_s=0.002),
            )

    def test_unrepresentable_inertia_boundary_fails_as_validation_error(self):
        with self.assertRaisesRegex(ValueError, "overflowed"):
            params(
                mass_kg=1.0e200,
                cg_distance_m=1.0e200,
                hinge_inertia_kg_m2=1.0e300,
            )

    def test_regularized_friction_reports_torque_and_dissipation(self):
        result = solve_mechanism_transient(request(
            params(dry_friction=DryFriction(mode="regularized_coulomb",
                                            coulomb_torque_nm=0.5,
                                            transition_velocity_rad_s=1e-3,
                                            source="illustrative_not_measured")),
            DriveHistory((0.0, 0.2), (0.0, 0.0), (0.0, 0.0)),
            initial_angular_velocity_rad_s=2.0,
        ))
        self.assertAlmostEqual(result.angular_velocity_rad_s[-1], 1.9, places=5)
        self.assertTrue(all(value <= 0.0 for value in result.dry_friction_torque_nm))
        self.assertGreater(result.dry_friction_dissipated_energy_j[-1], 0.0)
        self.assertGreater(result.total_dissipated_energy_j[-1], 0.0)

    def test_extreme_finite_input_fails_closed(self):
        huge = params(mass_kg=1e300, hinge_inertia_kg_m2=1e300,
                      hinge_radius_m=1e100, cg_distance_m=0.0)
        with self.assertRaisesRegex((ValueError, RuntimeError), "finite|overflow|numerical"):
            solve_mechanism_transient(request(
                huge,
                DriveHistory((0.0, 1.0), (1e300, 1e300), (0.0, 0.0)),
            ))


if __name__ == "__main__":
    unittest.main()
