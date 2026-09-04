"""PY-05B active-design to mechanism-transient binding contract."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import unittest
from pathlib import Path

from pyfoldable.application.design_draft import DesignDraftInputs, build_design_draft
from pyfoldable.application.mechanism_binding import (
    ContactPolicy,
    MechanismBindingError,
    RadialMassSample,
    TipMassDistribution,
    bind_mechanism_draft,
    validate_mechanism_binding,
)
from pyfoldable.application.mechanism_transient import (
    MechanismTransientError,
    load_bound_mechanism_json,
    prepare_bound_mechanism_transient,
    run_bound_mechanism_transient,
)
from pyfoldable.core.profile_catalog import load_project_airfoil
from pyfoldable.dynamics.mechanism_transient import DriveHistory, DryFriction, SolverControls


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "configs/designs/TIP_HINGED_250_CANONICAL.toml"


def _draft(*, rpm: str = "7100 rpm"):
    inputs = DesignDraftInputs(
        diameter="250 mm", hub_radius="18 mm", hinge_radius="100 mm",
        blade_count=2, airfoil_id="NACA2412", chord_scale=1.0,
        twist_scale=1.0, preview_fold_angle="-45 deg", angular_speed=rpm,
        forward_speed="0 m/s", air_density="1.225 kg/m^3",
        dynamic_viscosity="1.81e-5 Pa*s", temperature="288.15 K",
        pressure="101325 Pa",
    )
    return build_design_draft(
        SOURCE, inputs, airfoil_definition=load_project_airfoil("NACA2412")
    )


def _drive() -> DriveHistory:
    return DriveHistory((0.0, 0.2, 0.4), (-500.0, 0.0, 900.0), (0.0, 0.0, 0.0))


def _friction() -> DryFriction:
    return DryFriction("regularized_coulomb", 0.003, 0.02, "bench_assumption")


def _distribution(samples: tuple[RadialMassSample, ...] | None = None) -> TipMassDistribution:
    return TipMassDistribution(
        samples or (RadialMassSample(0.025, 0.04, "weighed_piece", 2.0e-6),),
        "caller_supplied_tip_mass_properties", "engineering_assumption",
    )


def _bind(**changes):
    values = {
        "draft": _draft(), "distribution": _distribution(),
        "spring_stiffness_nm_rad": 0.12, "rest_angle_rad": -0.1,
        "viscous_damping_nm_s_rad": 0.002, "initial_angle_rad": -0.7,
        "initial_angular_velocity_rad_s": 0.0, "drive": _drive(),
        "controls": SolverControls(max_step_s=0.001), "dry_friction": _friction(),
        "contact_policy": ContactPolicy("first_contact_terminal"),
        "mechanical_source": "caller_declared_unqualified_mechanism_inputs",
    }
    values.update(changes)
    return bind_mechanism_draft(**values)


def _bound_payload() -> str:
    return json.dumps({
        "mass_distribution": {
            "samples": [{
                "distance_from_hinge_m": 0.01,
                "mass_kg": 0.04,
                "source": "synthetic point",
                "intrinsic_inertia": 1.0e-6,
            }],
            "source": "synthetic mass distribution",
            "classification": "synthetic_test_fixture",
        },
        "mechanical_source": "synthetic mechanism fixture",
        "spring_stiffness_nm_rad": 0.02,
        "rest_angle_rad": 0.0,
        "viscous_damping_nm_s_rad": 0.001,
        "initial_angle_rad": -0.2,
        "initial_angular_velocity_rad_s": 0.0,
        "drive": {
            "time_s": [0.0, 0.01],
            "rpm": [0.0, -10.0],
            "applied_hinge_torque_nm": [0.0, 0.0],
        },
        "dry_friction": {
            "mode": "none",
            "coulomb_torque_nm": 0.0,
            "transition_velocity_rad_s": 0.0,
            "source": "explicit_frictionless_model",
        },
    })


class MechanismBindingTests(unittest.TestCase):
    def test_point_mass_uses_one_tip_and_preserves_drive_and_friction(self):
        binding = _bind()
        self.assertAlmostEqual(binding.parameters.mass_kg, 0.04)
        self.assertAlmostEqual(binding.parameters.cg_distance_m, 0.025)
        self.assertAlmostEqual(
            binding.parameters.hinge_inertia_kg_m2, 0.04 * 0.025**2 + 2.0e-6
        )
        self.assertNotAlmostEqual(binding.parameters.mass_kg, 0.08)
        self.assertAlmostEqual(binding.parameters.hinge_radius_m, 0.1)
        self.assertAlmostEqual(binding.parameters.lower_stop_rad, -math.pi)
        self.assertAlmostEqual(binding.parameters.upper_stop_rad, 0.0)
        self.assertEqual(binding.request.drive, _drive())
        self.assertEqual(binding.request.parameters.dry_friction, _friction())

    def test_uniform_rod_midpoint_quadrature_matches_analytic_properties(self):
        length, mass, count = 0.025, 0.06, 2048
        samples = tuple(
            RadialMassSample(
                (index + 0.5) * length / count,
                mass / count,
                "uniform_rod_quadrature",
            )
            for index in range(count)
        )
        binding = _bind(distribution=_distribution(samples))
        self.assertAlmostEqual(binding.parameters.cg_distance_m, length / 2.0)
        self.assertTrue(math.isclose(
            binding.parameters.hinge_inertia_kg_m2,
            mass * length**2 / 3.0,
            rel_tol=3e-7,
        ))

    def test_exact_tip_edge_and_signed_drive_are_independent_of_draft_rpm(self):
        edge = _distribution((RadialMassSample(0.025, 0.05, "tip_edge"),))
        first = _bind(draft=_draft(rpm="100 rpm"), distribution=edge)
        second = _bind(draft=_draft(rpm="9000 rpm"), distribution=edge)
        self.assertAlmostEqual(first.parameters.cg_distance_m, 0.025)
        self.assertEqual(first.request.drive, second.request.drive)
        self.assertEqual(first.request.drive, _drive())

    def test_context_preserves_exact_identities_and_closed_geometry_gate(self):
        binding = _bind()
        context = json.loads(binding.context_json)
        self.assertEqual(context["draft_toml"], binding.draft.toml)
        self.assertEqual(context["draft_sha256"], binding.draft.draft_sha256)
        self.assertEqual(context["source_sha256"], binding.draft.source_sha256)
        self.assertEqual(
            context["source_identity_scope"],
            "declared_source_hash_not_external_authentication",
        )
        self.assertEqual(
            context["airfoils"][0]["coordinate_sha256"],
            load_project_airfoil("NACA2412").metadata["airfoil_coordinate_sha256"],
        )
        self.assertIs(context["physical_qualification"], False)
        self.assertIs(context["prototype_measurement"], False)
        self.assertIs(context["geometry_gate"]["minimum_requirement_reachable"], False)
        self.assertIn(
            "stowed_requirement_unreachable",
            context["geometry_gate"]["compatibility_reasons"],
        )
        compact = json.dumps(
            context, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        self.assertEqual(compact, binding.context_json)
        self.assertEqual(
            binding.request_sha256, hashlib.sha256(compact.encode()).hexdigest()
        )

    def test_validate_rebuilds_identity_and_rejects_tampering(self):
        binding = _bind()
        self.assertEqual(validate_mechanism_binding(binding), binding)
        tampered = (
            dataclasses.replace(binding, request_sha256="0" * 64),
            dataclasses.replace(binding, mechanical_source="tampered"),
            dataclasses.replace(binding, context_json=binding.context_json + " "),
        )
        for candidate in tampered:
            with self.subTest(candidate=candidate):
                with self.assertRaisesRegex(MechanismBindingError, "identity|changed|match"):
                    validate_mechanism_binding(candidate)

    def test_unsupported_topology_offsets_and_stop_geometry_are_rejected(self):
        replacements = (
            ('axis_elevation = "90.0 deg"', 'axis_elevation = "80 deg"'),
            ('axis_azimuth = "0.0 deg"', 'axis_azimuth = "1 deg"'),
            ('axial_offset = "0.0 mm"', 'axial_offset = "1 mm"'),
            ('tangential_offset = "0.0 mm"', 'tangential_offset = "1 mm"'),
            ('deployed_angle = "0.0 deg"', 'deployed_angle = "1 deg"'),
            ('stop_angle = "0.0 deg"', 'stop_angle = "-1 deg"'),
        )
        draft = _draft()
        for line, replacement in replacements:
            with self.subTest(line=line):
                self.assertIn(line, draft.toml)
                toml = draft.toml.replace(line, replacement)
                changed = dataclasses.replace(
                    draft, toml=toml,
                    draft_sha256=hashlib.sha256(toml.encode()).hexdigest(),
                )
                with self.assertRaisesRegex(
                    MechanismBindingError, "hinge|planar|offset|deployed|stop"
                ):
                    _bind(draft=changed)

    def test_invalid_extent_zero_inertia_and_overflow_fail_closed(self):
        distributions = (
            TipMassDistribution(
                (RadialMassSample(0.026, 0.1, "outside"),),
                "source", "engineering_assumption",
            ),
            TipMassDistribution(
                (RadialMassSample(0.0250000000005, 0.1, "barely_outside"),),
                "source", "engineering_assumption",
            ),
            TipMassDistribution(
                (RadialMassSample(0.0, 0.1, "zero_inertia"),),
                "source", "synthetic_test_fixture",
            ),
            TipMassDistribution(
                (RadialMassSample(1e308, 1e308, "overflow"),),
                "source", "literature_derived_unqualified",
            ),
        )
        for distribution in distributions:
            with self.subTest(distribution=distribution):
                with self.assertRaises(MechanismBindingError):
                    _bind(distribution=distribution)

    def test_only_explicit_unqualified_mass_classes_are_accepted(self):
        for classification in (
            "prototype_measurement", "cad_derived", "measured", "",
            "engineering_assumption_unqualified",
        ):
            with self.subTest(classification=classification):
                with self.assertRaisesRegex(MechanismBindingError, "classification"):
                    TipMassDistribution(
                        (RadialMassSample(0.01, 0.1, "source"),),
                        "source", classification,
                    )

    def test_sources_and_contact_policy_are_explicit_and_strict(self):
        with self.assertRaisesRegex(MechanismBindingError, "source"):
            RadialMassSample(0.01, 0.1, "")
        with self.assertRaisesRegex(MechanismBindingError, "source"):
            TipMassDistribution(
                (RadialMassSample(0.01, 0.1, "x"),), "", "engineering_assumption"
            )
        with self.assertRaisesRegex(ValueError, "first_contact_terminal"):
            ContactPolicy("restitution")
        with self.assertRaisesRegex(MechanismBindingError, "mechanical_source"):
            _bind(mechanical_source="")
        with self.assertRaisesRegex(MechanismBindingError, "mechanical_source"):
            _bind(mechanical_source="x" * 4097)

    def test_bound_json_is_strict_duplicate_safe_and_size_bounded(self):
        binding = load_bound_mechanism_json(_draft(), _bound_payload())
        self.assertAlmostEqual(binding.parameters.mass_kg, 0.04)
        self.assertAlmostEqual(binding.parameters.cg_distance_m, 0.01)
        self.assertEqual(binding.request.drive.rpm, (0.0, -10.0))

        duplicate = _bound_payload().replace(
            '"mechanical_source": "synthetic mechanism fixture",',
            '"mechanical_source": "first", "mechanical_source": "second",',
        )
        with self.assertRaisesRegex(MechanismTransientError, "duplicate"):
            load_bound_mechanism_json(_draft(), duplicate)
        unknown = json.loads(_bound_payload())
        unknown["unexpected"] = 1
        with self.assertRaisesRegex(MechanismTransientError, "fields"):
            load_bound_mechanism_json(_draft(), json.dumps(unknown))
        with self.assertRaisesRegex(MechanismTransientError, "size"):
            load_bound_mechanism_json(_draft(), " " * 300_000)

    def test_bound_prepare_run_preserves_binding_identity_and_limitations(self):
        binding = load_bound_mechanism_json(_draft(), _bound_payload())
        prepared = prepare_bound_mechanism_transient(binding)
        artifact = run_bound_mechanism_transient(
            binding, expected_request_sha256=prepared.request_sha256
        )
        report = json.loads(artifact.report_json)
        reference = report["request"]["provenance"]["references"][0]
        self.assertEqual(reference["binding_sha256"], binding.request_sha256)
        self.assertEqual(reference["binding"], json.loads(binding.context_json))
        self.assertIs(report["physical_qualification"], False)
        self.assertIn("140 mm", " ".join(reference["binding"]["limitations"]))
        self.assertNotIn("No active blade geometry", " ".join(report["limitations"]))
        self.assertIn("identity-bound", " ".join(report["limitations"]))
        self.assertIn(
            "pyfoldable.application.mechanism_binding",
            report["request"]["implementation"]["source_files_sha256"],
        )

    def test_bound_service_revalidates_binding_and_request_hash(self):
        binding = load_bound_mechanism_json(_draft(), _bound_payload())
        with self.assertRaisesRegex(MechanismTransientError, "identity"):
            prepare_bound_mechanism_transient(
                dataclasses.replace(binding, request_sha256="0" * 64)
            )
        prepared = prepare_bound_mechanism_transient(binding)
        with self.assertRaisesRegex(MechanismTransientError, "identity"):
            run_bound_mechanism_transient(
                binding, expected_request_sha256="0" * 64
            )


if __name__ == "__main__":
    unittest.main()
