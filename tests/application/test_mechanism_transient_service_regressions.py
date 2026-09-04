import dataclasses
import json
import unittest

from pyfoldable.application.mechanism_transient import (
    MechanismTransientError,
    SERVICE_VERSION,
    build_literature_modal_example,
    load_drive_history_json,
    prepare_mechanism_transient,
    run_mechanism_transient,
)


class MechanismServiceRegressionTests(unittest.TestCase):
    def test_v2_drive_json_is_strict_bounded_and_duplicate_safe(self):
        drive = load_drive_history_json(
            '{"time_s":[0,1],"rpm":[-100,100],"applied_hinge_torque_nm":[0,0]}'
        )
        self.assertEqual(drive.rpm, (-100.0, 100.0))
        with self.assertRaisesRegex(MechanismTransientError, "duplicate"):
            load_drive_history_json(
                '{"time_s":[0,1],"rpm":[0,0],"rpm":[1,1],'
                '"applied_hinge_torque_nm":[0,0]}'
            )
        with self.assertRaisesRegex(MechanismTransientError, "fields"):
            load_drive_history_json(
                '{"time_s":[0,1],"rpm":[0,0],"applied_hinge_torque_nm":[0,0],"x":1}'
            )
        with self.assertRaisesRegex(MechanismTransientError, "size"):
            load_drive_history_json(" " * 200_000)

    def test_provenance_references_must_be_structured_and_finite(self):
        example = build_literature_modal_example()
        broken = dataclasses.replace(
            example,
            provenance={**example.provenance, "references": ["bare citation"]},
        )
        with self.assertRaisesRegex(MechanismTransientError, "References"):
            prepare_mechanism_transient(broken)
        nan_source = dataclasses.replace(
            example,
            provenance={**example.provenance, "unrequested": float("nan")},
        )
        with self.assertRaises(MechanismTransientError):
            prepare_mechanism_transient(nan_source)
        forged_binding = dataclasses.replace(
            example,
            provenance={
                **example.provenance,
                "references": [{"binding_sha256": "x" * 64, "binding": {}}],
            },
        )
        with self.assertRaisesRegex(MechanismTransientError, "References"):
            prepare_mechanism_transient(forged_binding)
        hybrid = dataclasses.replace(
            example,
            provenance={
                **example.provenance,
                "references": [{
                    "title": "dummy",
                    "doi": "dummy",
                    "binding_sha256": "0" * 64,
                    "binding": {"tampered": True},
                }],
            },
        )
        with self.assertRaisesRegex(MechanismTransientError, "References"):
            prepare_mechanism_transient(hybrid)

    def test_service_catches_arithmetic_and_never_publishes_partial_success(self):
        example = build_literature_modal_example()
        p = dataclasses.replace(
            example.transient.parameters,
            mass_kg=1e300,
            cg_distance_m=0.0,
            hinge_inertia_kg_m2=1e300,
            hinge_radius_m=1e100,
        )
        drive = dataclasses.replace(example.transient.drive,
                                    rpm=(1e300, 1e300))
        request = dataclasses.replace(
            example,
            transient=dataclasses.replace(example.transient,
                                           parameters=p, drive=drive),
        )
        with self.assertRaisesRegex(MechanismTransientError, "failed"):
            run_mechanism_transient(request)

    def test_contract_source_participates_in_request_hash(self):
        example = build_literature_modal_example()
        prepared = prepare_mechanism_transient(example)
        document = json.loads(run_mechanism_transient(example).report_json)
        hashes = document["request"]["implementation"]["source_files_sha256"]
        self.assertIn("pyfoldable.dynamics.mechanism_contracts", hashes)
        self.assertEqual(SERVICE_VERSION, 2)
        self.assertEqual(prepared.request_sha256, document["request_sha256"])


if __name__ == "__main__":
    unittest.main()
