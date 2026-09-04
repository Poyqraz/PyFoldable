import unittest

from pyfoldable.dynamics.mechanism_contracts import ContactPolicy, DryFriction


class MechanismContractTests(unittest.TestCase):
    def test_dry_friction_is_explicit_and_fail_closed(self):
        self.assertEqual(DryFriction().mode, "none")
        with self.assertRaisesRegex(ValueError, "zero"):
            DryFriction(mode="none", coulomb_torque_nm=0.1)
        friction = DryFriction(
            mode="regularized_coulomb",
            coulomb_torque_nm=0.2,
            transition_velocity_rad_s=0.01,
            source="bench_estimate_not_prototype_measurement",
        )
        self.assertEqual(friction.source, "bench_estimate_not_prototype_measurement")
        with self.assertRaisesRegex(ValueError, "model"):
            DryFriction(mode="stiction")
        with self.assertRaisesRegex(ValueError, "source"):
            DryFriction(source="x" * 4097)

    def test_only_terminal_first_contact_policy_is_supported(self):
        self.assertEqual(ContactPolicy().mode, "first_contact_terminal")
        with self.assertRaisesRegex(ValueError, "first_contact_terminal"):
            ContactPolicy(mode="bounce")


if __name__ == "__main__":
    unittest.main()
