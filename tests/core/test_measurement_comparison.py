"""PY-06A matched experiment comparison and uncertainty contract."""

from __future__ import annotations

import dataclasses
import math
import unittest

import pyfoldable.core as core
from pyfoldable.core.experiment_contract import (
    CalibrationIdentity,
    ExperimentBundleDecision,
    ExperimentPolicy,
    ExperimentRunDecision,
    ExperimentSummary,
    TestStandManifest,
    UncertaintyMetric,
    canonical_experiment_summary_sha256,
    canonical_test_stand_manifest_sha256,
)
from pyfoldable.core.measurement_comparison import (
    ComparisonPolicy,
    MeasurementComparisonError,
    RunComparisonContext,
    build_matched_experiment_comparison,
)


UNITS = {
    "thrust": "N", "torque": "N*m", "rpm": "rpm", "voltage": "V",
    "current": "A", "temperature": "K", "pressure": "Pa",
}


def _metric(mean: float, uncertainty: float, unit: str,
            coverage_factor: float = 2.0,
            calibration: float | None = None) -> UncertaintyMetric:
    if calibration is None:
        calibration = {
            "N": 0.01, "N*m": 0.01, "rpm": 0.1, "V": 0.1,
            "A": 0.1, "K": 0.1, "Pa": 0.1,
        }.get(unit, 0.0)
    variance = uncertainty * uncertainty - calibration * calibration
    type_a = math.sqrt(max(0.0, variance))
    return UncertaintyMetric(
        mean, type_a, calibration, 0.0, uncertainty,
        coverage_factor * uncertainty, unit,
    )


def _summary(run_id: str, role: str, *, thrust: float, thrust_u: float,
             torque: float = 0.2, torque_u: float = 0.01,
             power: float = 100.0, power_u: float = 2.0,
             rpm: float = 7000.0, temperature: float = 295.0,
             pressure: float = 101000.0,
             coverage_factor: float = 2.0) -> ExperimentSummary:
    voltage = _metric(10.0, 0.1, "V", coverage_factor)
    current_mean = power / voltage.mean
    power_calibration = math.hypot(
        current_mean * voltage.standard_uncertainty_calibration,
        voltage.mean * 0.1,
    )
    power_type_a = math.sqrt(max(0.0, power_u * power_u - power_calibration**2))
    current_type_a = power_type_a / voltage.mean
    current_uncertainty = math.hypot(current_type_a, 0.1)
    current = _metric(
        current_mean, current_uncertainty, "A", coverage_factor
    )
    return ExperimentSummary(run_id, role, 3, {
        "thrust": _metric(thrust, thrust_u, "N", coverage_factor),
        "torque": _metric(torque, torque_u, "N*m", coverage_factor),
        "rpm": _metric(rpm, 1.0, "rpm", coverage_factor),
        "temperature": _metric(temperature, 0.1, "K", coverage_factor),
        "pressure": _metric(pressure, 10.0, "Pa", coverage_factor),
        "voltage": voltage,
        "current": current,
        "electrical_power": UncertaintyMetric(
            power, power_type_a, power_calibration, 0.0, power_u,
            coverage_factor * power_u, "W",
        ),
    })


def _manifest(*, coverage_factor: float = 2.0) -> TestStandManifest:
    return TestStandManifest(
        "stand-v1",
        tuple(
            CalibrationIdentity(
                f"sensor-{name}", name, unit, f"cert-{name}", "c" * 64,
                "2026-01-01", "2027-01-01",
                0.01 if name in {"thrust", "torque"} else 0.1,
                "software_fixture_not_calibration_evidence",
            )
            for name, unit in UNITS.items()
        ),
        ExperimentPolicy(3, {"thrust": 0.05, "torque": 0.01}, coverage_factor),
    )


def _decision(*, foldable_thrust: float = 9.0, fixed_u: float = 0.2,
              foldable_u: float = 0.18,
              coverage_factor: float = 2.0) -> ExperimentBundleDecision:
    summaries = (
        _summary(
            "fixed", "fixed_reference", thrust=10.0, thrust_u=fixed_u,
            coverage_factor=coverage_factor,
        ),
        _summary(
            "foldable", "foldable", thrust=foldable_thrust,
            thrust_u=foldable_u, torque=0.18, power=95.0,
            coverage_factor=coverage_factor,
        ),
    )
    return ExperimentBundleDecision(
        "stand-v1",
        (
            ExperimentRunDecision(
                "fixed", (), "a" * 64, "design-fixed", "2026-08-24",
                canonical_experiment_summary_sha256(summaries[0]),
            ),
            ExperimentRunDecision(
                "foldable", (), "b" * 64, "design-foldable", "2026-08-24",
                canonical_experiment_summary_sha256(summaries[1]),
            ),
        ),
        summaries,
        (),
        canonical_test_stand_manifest_sha256(
            _manifest(coverage_factor=coverage_factor)
        ),
    )


def _with_summaries(
    decision: ExperimentBundleDecision,
    summaries: tuple[ExperimentSummary, ...],
) -> ExperimentBundleDecision:
    by_run_id = {summary.run_id: summary for summary in summaries}
    runs = tuple(
        dataclasses.replace(
            run,
            summary_sha256=canonical_experiment_summary_sha256(
                by_run_id[run.run_id]
            ),
        )
        for run in decision.runs
    )
    return dataclasses.replace(decision, runs=runs, summaries=summaries)


def _context(run_id: str, **changes) -> RunComparisonContext:
    values = {
        "run_id": run_id,
        "open_diameter_m": 0.25,
        "forward_speed_m_s": 0.0,
        "torque_channel": "rotor_shaft_torque",
        "electrical_power_channel": "dc_electrical_input_power",
        "source": "synthetic software fixture",
        "classification": "software_fixture",
    }
    values.update(changes)
    return RunComparisonContext(**values)


def _policy(**changes) -> ComparisonPolicy:
    values = {
        "maximum_diameter_delta_m": 1e-6,
        "maximum_rpm_relative_delta": 0.01,
        "maximum_forward_speed_delta_m_s": 0.1,
        "maximum_temperature_delta_k": 2.0,
        "maximum_pressure_delta_pa": 1000.0,
        "thrust_uncertainty_correlation": 0.0,
        "rotor_shaft_torque_uncertainty_correlation": 0.0,
        "dc_electrical_input_power_uncertainty_correlation": 0.0,
        "target_thrust_ratio": 0.85,
    }
    values.update(changes)
    return ComparisonPolicy(**values)


class MeasurementComparisonTests(unittest.TestCase):
    def test_analytic_ratio_difference_and_semantic_labels(self):
        result = build_matched_experiment_comparison(
            _manifest(), _decision(), _context("fixed"),
            _context("foldable"), _policy(),
        )
        self.assertEqual(result.state, "screening_comparison_complete_physical_evidence_pending")
        self.assertFalse(result.physical_qualification)
        self.assertFalse(result.target_fitting_performed)
        self.assertTrue(all(result.condition_matches.values()))
        thrust = result.metrics["thrust"]
        self.assertAlmostEqual(thrust.difference, -1.0)
        self.assertAlmostEqual(thrust.ratio, 0.9)
        expected_ratio_u = math.hypot(0.18 / 10.0, 9.0 * 0.2 / 10.0**2)
        self.assertAlmostEqual(thrust.standard_uncertainty_ratio, expected_ratio_u)
        self.assertAlmostEqual(
            thrust.standard_uncertainty_difference, math.hypot(0.18, 0.2)
        )
        self.assertEqual(result.target_decision, "screening_target_indeterminate")
        self.assertEqual(result.metrics["rotor_shaft_torque"].unit, "N*m")
        self.assertEqual(result.metrics["dc_electrical_input_power"].unit, "W")
        self.assertNotIn("hinge", result.metrics)

    def test_target_uses_expanded_interval_not_point_estimate(self):
        met = build_matched_experiment_comparison(
            _manifest(), _decision(foldable_thrust=9.5, fixed_u=0.05, foldable_u=0.05),
            _context("fixed"), _context("foldable"), _policy(),
        )
        self.assertEqual(met.target_decision, "screening_target_met")
        not_met = build_matched_experiment_comparison(
            _manifest(), _decision(foldable_thrust=8.0, fixed_u=0.05, foldable_u=0.05),
            _context("fixed"), _context("foldable"), _policy(),
        )
        self.assertEqual(not_met.target_decision, "screening_target_not_met")

    def test_target_interval_boundaries_are_inclusive_and_indeterminate(self):
        arguments = (
            _manifest(), _decision(), _context("fixed"), _context("foldable")
        )
        baseline = build_matched_experiment_comparison(
            *arguments, _policy(target_thrust_ratio=0.5)
        )
        thrust = baseline.metrics["thrust"]
        at_lower = build_matched_experiment_comparison(
            *arguments, _policy(target_thrust_ratio=thrust.ratio_interval_lower)
        )
        at_upper = build_matched_experiment_comparison(
            *arguments, _policy(target_thrust_ratio=thrust.ratio_interval_upper)
        )
        self.assertEqual(
            at_lower.metrics["thrust"].ratio_interval_lower,
            at_lower.policy.target_thrust_ratio,
        )
        self.assertEqual(at_lower.target_decision, "screening_target_met")
        self.assertEqual(
            at_upper.metrics["thrust"].ratio_interval_upper,
            at_upper.policy.target_thrust_ratio,
        )
        self.assertEqual(
            at_upper.target_decision, "screening_target_indeterminate"
        )

    def test_coverage_factor_comes_from_pr10_manifest(self):
        first = build_matched_experiment_comparison(
            _manifest(coverage_factor=1.0), _decision(coverage_factor=1.0), _context("fixed"),
            _context("foldable"), _policy(),
        )
        second = build_matched_experiment_comparison(
            _manifest(coverage_factor=3.0), _decision(coverage_factor=3.0), _context("fixed"),
            _context("foldable"), _policy(),
        )
        self.assertAlmostEqual(
            second.metrics["thrust"].expanded_uncertainty_ratio,
            3 * first.metrics["thrust"].expanded_uncertainty_ratio,
        )

    def test_explicit_correlation_controls_ratio_and_difference_uncertainty(self):
        independent = build_matched_experiment_comparison(
            _manifest(), _decision(), _context("fixed"),
            _context("foldable"), _policy(),
        ).metrics["thrust"]
        correlated = build_matched_experiment_comparison(
            _manifest(), _decision(), _context("fixed"),
            _context("foldable"),
            _policy(thrust_uncertainty_correlation=1.0),
        ).metrics["thrust"]
        anticorrelated = build_matched_experiment_comparison(
            _manifest(), _decision(), _context("fixed"),
            _context("foldable"),
            _policy(thrust_uncertainty_correlation=-1.0),
        ).metrics["thrust"]
        self.assertAlmostEqual(correlated.standard_uncertainty_ratio, 0.0)
        self.assertAlmostEqual(correlated.standard_uncertainty_difference, 0.02)
        self.assertLess(correlated.standard_uncertainty_ratio,
                        independent.standard_uncertainty_ratio)
        self.assertGreater(anticorrelated.standard_uncertainty_ratio,
                           independent.standard_uncertainty_ratio)
        with self.assertRaisesRegex(ValueError, "correlation"):
            _policy(thrust_uncertainty_correlation=1.01)

    def test_each_unmatched_condition_blocks_without_ratio(self):
        cases = (
            (_context("foldable", open_diameter_m=0.24), "diameter"),
            (_context("foldable"), "rpm"),
            (_context("foldable", forward_speed_m_s=1.0), "forward_speed"),
        )
        for context, failed_gate in cases:
            decision = _decision()
            if failed_gate == "rpm":
                summaries = list(decision.summaries)
                summaries[1] = dataclasses.replace(
                    summaries[1],
                    metrics={**summaries[1].metrics, "rpm": _metric(7200.0, 1.0, "rpm")},
                )
                decision = _with_summaries(decision, tuple(summaries))
            with self.subTest(failed_gate=failed_gate):
                result = build_matched_experiment_comparison(
                    _manifest(), decision, _context("fixed"), context, _policy()
                )
                self.assertEqual(result.state, "blocked_unmatched_or_invalid_experiment_evidence")
                self.assertFalse(result.condition_matches[failed_gate])
                self.assertEqual(result.metrics, {})
                self.assertEqual(result.target_decision, "blocked")

    def test_temperature_pressure_and_bundle_failures_block(self):
        decision = _decision()
        summaries = list(decision.summaries)
        summaries[1] = _summary(
            "foldable", "foldable", thrust=9.0, thrust_u=0.18,
            temperature=300.0, pressure=104000.0,
        )
        blocked = build_matched_experiment_comparison(
            _manifest(), _with_summaries(decision, tuple(summaries)),
            _context("fixed"), _context("foldable"), _policy(),
        )
        self.assertFalse(blocked.condition_matches["temperature"])
        self.assertFalse(blocked.condition_matches["pressure"])
        failed_bundle = dataclasses.replace(
            decision,
            runs=(
                dataclasses.replace(decision.runs[0], failures=("failed",)),
                decision.runs[1],
            ),
        )
        with self.assertRaisesRegex(MeasurementComparisonError, "software gate"):
            build_matched_experiment_comparison(
                _manifest(), failed_bundle, _context("fixed"),
                _context("foldable"), _policy(),
            )

    def test_wrong_roles_ids_units_and_nonfinite_metrics_fail_closed(self):
        decision = _decision()
        swapped = dataclasses.replace(
            decision,
            summaries=(
                dataclasses.replace(decision.summaries[0], role="foldable"),
                decision.summaries[1],
            ),
        )
        malformed = []
        malformed.append((swapped, "role"))
        wrong_unit_summary = dataclasses.replace(
            decision.summaries[0],
            metrics={**decision.summaries[0].metrics, "thrust": _metric(10.0, 0.2, "kgf")},
        )
        malformed.append((dataclasses.replace(
            decision, summaries=(wrong_unit_summary, decision.summaries[1])
        ), "unit"))
        nan_summary = dataclasses.replace(
            decision.summaries[0],
            metrics={**decision.summaries[0].metrics, "thrust": _metric(float("nan"), 0.2, "N")},
        )
        malformed.append((dataclasses.replace(
            decision, summaries=(nan_summary, decision.summaries[1])
        ), "finite"))
        for candidate, message in malformed:
            with self.subTest(message=message):
                with self.assertRaisesRegex(MeasurementComparisonError, message):
                    build_matched_experiment_comparison(
                        _manifest(), candidate, _context("fixed"),
                        _context("foldable"), _policy(),
                    )
        with self.assertRaisesRegex(MeasurementComparisonError, "run id"):
            build_matched_experiment_comparison(
                _manifest(), decision, _context("missing"),
                _context("foldable"), _policy(),
            )

    def test_torque_and_power_semantics_are_not_interchangeable(self):
        for changes in (
            {"torque_channel": "hinge_axis_torque"},
            {"torque_channel": "generic_torque"},
            {"electrical_power_channel": "motor_shaft_power"},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    _context("fixed", **changes)

    def test_mapping_is_explicitly_unqualified_and_target_not_fitted(self):
        result = build_matched_experiment_comparison(
            _manifest(), _decision(), _context("fixed"),
            _context("foldable"), _policy(),
        ).as_mapping()
        self.assertIs(result["physical_qualification"], False)
        self.assertIs(result["target_fitting_performed"], False)
        self.assertEqual(result["qualification"], "screening_only")
        self.assertEqual(result["fixed_context"]["run_id"], "fixed")
        self.assertEqual(result["foldable_context"]["run_id"], "foldable")
        self.assertEqual(
            result["test_stand_manifest_sha256"],
            canonical_test_stand_manifest_sha256(_manifest()),
        )
        self.assertEqual(
            result["selected_run_identities"]["fixed"]["raw_data_sha256"],
            "a" * 64,
        )
        self.assertEqual(
            result["selected_run_identities"]["foldable"]["raw_data_sha256"],
            "b" * 64,
        )

    def test_public_api_and_result_maps_are_immutable(self):
        self.assertIs(core.ComparisonPolicy, ComparisonPolicy)
        result = build_matched_experiment_comparison(
            _manifest(), _decision(), _context("fixed"),
            _context("foldable"), _policy(),
        )
        with self.assertRaises(TypeError):
            result.metrics["x"] = result.metrics["thrust"]
        with self.assertRaises(TypeError):
            result.condition_matches["rpm"] = False

    def test_inconsistent_or_overflowing_uncertainty_fails_controlled(self):
        decision = _decision()
        bad_metric = dataclasses.replace(
            decision.summaries[0].metrics["thrust"],
            combined_standard_uncertainty=0.3,
        )
        huge_metric = _metric(10.0, 1.0e308, "N")
        for metric, message in ((bad_metric, "combined"), (huge_metric, "finite|overflow")):
            summary = dataclasses.replace(
                decision.summaries[0],
                metrics={**decision.summaries[0].metrics, "thrust": metric},
            )
            candidate = dataclasses.replace(
                decision, summaries=(summary, decision.summaries[1])
            )
            with self.subTest(message=message):
                with self.assertRaisesRegex(MeasurementComparisonError, message):
                    build_matched_experiment_comparison(
                        _manifest(), candidate, _context("fixed"),
                        _context("foldable"), _policy(),
                    )

    def test_nonphysical_condition_means_and_manifest_identity_fail_closed(self):
        decision = _decision()
        invalid_summary = dataclasses.replace(
            decision.summaries[0],
            metrics={
                **decision.summaries[0].metrics,
                "temperature": _metric(0.0, 0.1, "K"),
            },
        )
        with self.assertRaisesRegex(MeasurementComparisonError, "positive"):
            build_matched_experiment_comparison(
                _manifest(),
                _with_summaries(
                    decision, (invalid_summary, decision.summaries[1])
                ),
                _context("fixed"), _context("foldable"), _policy(),
            )
        with self.assertRaisesRegex(MeasurementComparisonError, "identity"):
            build_matched_experiment_comparison(
                dataclasses.replace(_manifest(), id="other-stand"), decision,
                _context("fixed"), _context("foldable"), _policy(),
            )

    def test_same_stand_id_with_different_manifest_digest_fails_closed(self):
        manifest = _manifest()
        changed_calibration = dataclasses.replace(
            manifest.calibrations[0],
            certificate_id="replacement-certificate",
            certificate_sha256="0" * 64,
        )
        changed_manifest = dataclasses.replace(
            manifest,
            calibrations=(changed_calibration,) + manifest.calibrations[1:],
        )
        self.assertEqual(manifest.id, changed_manifest.id)
        with self.assertRaisesRegex(MeasurementComparisonError, "manifest digest"):
            build_matched_experiment_comparison(
                changed_manifest, _decision(),
                _context("fixed"), _context("foldable"), _policy(),
            )

    def test_selected_run_date_must_be_inside_every_calibration_window(self):
        decision = _decision()
        expired = dataclasses.replace(
            decision,
            runs=(
                dataclasses.replace(
                    decision.runs[0], experiment_date="2030-01-01"
                ),
                decision.runs[1],
            ),
        )
        with self.assertRaisesRegex(MeasurementComparisonError, "calibration.*date"):
            build_matched_experiment_comparison(
                _manifest(), expired, _context("fixed"),
                _context("foldable"), _policy(),
            )

    def test_power_and_calibration_semantics_fail_closed_when_tampered(self):
        decision = _decision()
        fixed = decision.summaries[0]
        candidates = (
            dataclasses.replace(
                fixed,
                metrics={
                    **fixed.metrics,
                    "electrical_power": _metric(123.0, 2.0, "W"),
                },
            ),
            dataclasses.replace(
                fixed,
                metrics={
                    **fixed.metrics,
                    "thrust": _metric(10.0, 0.3, "N", calibration=0.02),
                },
            ),
        )
        for summary, message in zip(candidates, ("electrical power", "calibration")):
            with self.subTest(message=message):
                with self.assertRaisesRegex(MeasurementComparisonError, message):
                    build_matched_experiment_comparison(
                        _manifest(),
                        _with_summaries(
                            decision, (summary, decision.summaries[1])
                        ),
                        _context("fixed"), _context("foldable"), _policy(),
                    )

    def test_forged_bundle_collections_fail_as_controlled_contract_errors(self):
        decision = _decision()
        candidates = (
            dataclasses.replace(decision, runs=(object(),)),
            dataclasses.replace(decision, missing_roles=[]),
            dataclasses.replace(decision, missing_roles=([],)),
            dataclasses.replace(
                decision,
                runs=(
                    dataclasses.replace(decision.runs[0], failures=[]),
                    decision.runs[1],
                ),
            ),
            dataclasses.replace(
                decision,
                summaries=(
                    dataclasses.replace(decision.summaries[0], run_id=[]),
                    decision.summaries[1],
                ),
            ),
            dataclasses.replace(
                decision,
                summaries=(
                    dataclasses.replace(
                        decision.summaries[0],
                        metrics={**decision.summaries[0].metrics, "junk": object()},
                    ),
                    decision.summaries[1],
                ),
            ),
        )
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                with self.assertRaisesRegex(
                    MeasurementComparisonError,
                    "run decisions|missing roles|failures|summary|metric",
                ):
                    build_matched_experiment_comparison(
                        _manifest(), candidate, _context("fixed"),
                        _context("foldable"), _policy(),
                    )

    def test_overflowing_condition_delta_fails_closed(self):
        decision = _decision()
        fixed = dataclasses.replace(
            decision.summaries[0],
            metrics={
                **decision.summaries[0].metrics,
                "rpm": _metric(1e-308, 0.1, "rpm"),
            },
        )
        foldable = dataclasses.replace(
            decision.summaries[1],
            metrics={
                **decision.summaries[1].metrics,
                "rpm": _metric(1e308, 0.1, "rpm"),
            },
        )
        with self.assertRaisesRegex(MeasurementComparisonError, "condition delta"):
            build_matched_experiment_comparison(
                _manifest(),
                _with_summaries(decision, (fixed, foldable)),
                _context("fixed"), _context("foldable"), _policy(),
            )

    def test_public_api_wildcard_exports_py06a_contract(self):
        namespace = {}
        exec("from pyfoldable.core import *", {}, namespace)
        expected = {
            "ComparisonMetric", "ComparisonPolicy",
            "MEASUREMENT_COMPARISON_SCHEMA_VERSION",
            "MatchedExperimentComparison", "MeasurementComparisonError",
            "RunComparisonContext", "build_matched_experiment_comparison",
        }
        self.assertTrue(expected.issubset(namespace))


if __name__ == "__main__":
    unittest.main()
