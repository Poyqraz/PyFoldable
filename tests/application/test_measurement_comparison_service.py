import dataclasses
import hashlib
import json
from pathlib import Path

import pytest

import pyfoldable.application as application
from pyfoldable.application.measurement_comparison import (
    MAX_COMPARISON_JSON_BYTES,
    MeasurementComparisonServiceError,
    load_measurement_comparison_json,
    prepare_measurement_comparison_report,
    run_measurement_comparison_report,
)
from pyfoldable.core import build_matched_experiment_comparison


ROOT = Path(__file__).resolve().parents[2]
PR10_REPORT = ROOT / "reports" / "pr10_experiment_contract_evidence.json"


def _document() -> dict:
    evidence = json.loads(PR10_REPORT.read_text(encoding="utf-8"))
    policy = {
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
    return {
        "schema_version": 1,
        "artifact_class": "measurement_comparison_request",
        "physical_qualification": False,
        "manifest": evidence["manifest"],
        "decision": evidence["software_fixture_decision"],
        "fixed_context": {
            "run_id": "fixed-fixture-1",
            "open_diameter_m": 0.25,
            "forward_speed_m_s": 0.0,
            "torque_channel": "rotor_shaft_torque",
            "electrical_power_channel": "dc_electrical_input_power",
            "source": "synthetic software fixture",
            "classification": "software_fixture",
        },
        "foldable_context": {
            "run_id": "foldable-fixture-1",
            "open_diameter_m": 0.25,
            "forward_speed_m_s": 0.0,
            "torque_channel": "rotor_shaft_torque",
            "electrical_power_channel": "dc_electrical_input_power",
            "source": "synthetic software fixture",
            "classification": "software_fixture",
        },
        "policy": policy,
        "policy_sources": {
            key: "explicit PY-06 software-fixture policy" for key in policy
        },
    }


def _payload(document: dict | None = None) -> bytes:
    return json.dumps(
        _document() if document is None else document,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def test_service_matches_core_and_produces_deterministic_exact_hashes():
    request = load_measurement_comparison_json(_payload())
    prepared = prepare_measurement_comparison_report(request)
    artifact = run_measurement_comparison_report(
        request, expected_request_sha256=prepared.request_sha256
    )
    repeated = run_measurement_comparison_report(
        request, expected_request_sha256=prepared.request_sha256
    )
    report = json.loads(artifact.report_json)
    direct = build_matched_experiment_comparison(
        request.manifest,
        request.decision,
        request.fixed_context,
        request.foldable_context,
        request.policy,
    )

    assert report["result"] == direct.as_mapping()
    assert artifact == repeated
    assert artifact.input_sha256 == hashlib.sha256(_payload()).hexdigest()
    assert artifact.report_sha256 == hashlib.sha256(
        artifact.report_json.encode("utf-8")
    ).hexdigest()
    assert report["request_sha256"] == prepared.request_sha256
    assert report["input_sha256"] == request.input_sha256
    assert report["physical_qualification"] is False
    assert report["target_fitting_performed"] is False
    assert report["qualification"] == "screening_only"


def test_byte_identity_is_distinct_from_canonical_input_identity():
    compact = _payload()
    spaced = json.dumps(_document(), sort_keys=True, indent=2).encode("utf-8")
    first = load_measurement_comparison_json(compact)
    second = load_measurement_comparison_json(spaced)
    assert first.manifest.as_mapping() == second.manifest.as_mapping()
    assert first.input_sha256 != second.input_sha256
    assert (
        prepare_measurement_comparison_report(first).request_sha256
        != prepare_measurement_comparison_report(second).request_sha256
    )
    assert (
        run_measurement_comparison_report(first).report_sha256
        != run_measurement_comparison_report(second).report_sha256
    )


def test_every_policy_source_is_preserved_and_required():
    request = load_measurement_comparison_json(_payload())
    report = json.loads(run_measurement_comparison_report(request).report_json)
    assert report["request"]["input"]["policy_sources"] == _document()[
        "policy_sources"
    ]

    for mutation in ("missing", "extra", "empty"):
        document = _document()
        if mutation == "missing":
            document["policy_sources"].pop("thrust_uncertainty_correlation")
        elif mutation == "extra":
            document["policy_sources"]["assumed_efficiency"] = "unsupported"
        else:
            document["policy_sources"]["target_thrust_ratio"] = ""
        with pytest.raises(MeasurementComparisonServiceError, match="policy source"):
            load_measurement_comparison_json(_payload(document))


def test_strict_json_rejects_nested_duplicates_unknown_and_missing_fields():
    payload = _payload().decode("utf-8")
    duplicate = payload.replace(
        '"run_id":"fixed-fixture-1"',
        '"run_id":"duplicate","run_id":"fixed-fixture-1"',
        1,
    )
    with pytest.raises(MeasurementComparisonServiceError, match="duplicate"):
        load_measurement_comparison_json(duplicate)

    mutations = []
    root_unknown = _document()
    root_unknown["unexpected"] = 1
    mutations.append(root_unknown)
    nested_unknown = _document()
    nested_unknown["manifest"]["calibrations"][0]["unexpected"] = 1
    mutations.append(nested_unknown)
    nested_missing = _document()
    del nested_missing["decision"]["summaries"][0]["repeat_count"]
    mutations.append(nested_missing)
    for document in mutations:
        with pytest.raises(MeasurementComparisonServiceError, match="fields"):
            load_measurement_comparison_json(_payload(document))


@pytest.mark.parametrize("location", ["root", "manifest", "decision"])
def test_schema_versions_require_json_integers(location):
    document = _document()
    target = document if location == "root" else document[location]
    target["schema_version"] = float(target["schema_version"])
    with pytest.raises(MeasurementComparisonServiceError, match="schema_version"):
        load_measurement_comparison_json(_payload(document))


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "1e999"])
def test_nonfinite_json_numbers_fail_closed(value):
    payload = _payload().decode("utf-8").replace(
        '"target_thrust_ratio":0.85', f'"target_thrust_ratio":{value}'
    )
    with pytest.raises(MeasurementComparisonServiceError, match="finite|JSON"):
        load_measurement_comparison_json(payload)


@pytest.mark.parametrize("value", [True, "0.85"])
def test_bool_and_string_numeric_fields_are_rejected(value):
    document = _document()
    document["policy"]["target_thrust_ratio"] = value
    with pytest.raises(MeasurementComparisonServiceError, match="finite|validation"):
        load_measurement_comparison_json(_payload(document))


def test_invalid_utf8_nesting_and_size_limits_are_controlled():
    with pytest.raises(MeasurementComparisonServiceError, match="UTF-8"):
        load_measurement_comparison_json(b"\xff")
    with pytest.raises(MeasurementComparisonServiceError, match="nesting|malformed"):
        load_measurement_comparison_json(("[" * 1100 + "]" * 1100).encode())
    with pytest.raises(MeasurementComparisonServiceError, match="size"):
        load_measurement_comparison_json(b" " * (MAX_COMPARISON_JSON_BYTES + 1))


def test_escaped_lone_unicode_surrogate_is_rejected_before_hashing():
    document = _document()
    document["policy_sources"]["target_thrust_ratio"] = "\ud800"
    payload = json.dumps(document, ensure_ascii=True).encode("utf-8")
    with pytest.raises(
        MeasurementComparisonServiceError, match="Unicode|surrogate|UTF-8"
    ):
        load_measurement_comparison_json(payload)


@pytest.mark.parametrize(
    "mutation",
    ["run_passed", "decision_state", "software_gate", "summary_digest", "manifest_digest"],
)
def test_forged_decision_and_provenance_are_rejected(mutation):
    document = _document()
    decision = document["decision"]
    if mutation == "run_passed":
        decision["runs"][0]["passed"] = False
    elif mutation == "decision_state":
        decision["state"] = "physically_qualified"
    elif mutation == "software_gate":
        decision["software_gate_passed"] = False
    elif mutation == "summary_digest":
        decision["runs"][0]["summary_sha256"] = "0" * 64
    else:
        decision["test_stand_manifest_sha256"] = "0" * 64
    with pytest.raises(
        MeasurementComparisonServiceError,
        match="derived|digest|manifest|summary|comparison",
    ):
        request = load_measurement_comparison_json(_payload(document))
        prepare_measurement_comparison_report(request)


def test_stale_request_rejects_without_publishing_report():
    first = load_measurement_comparison_json(_payload())
    prepared = prepare_measurement_comparison_report(first)
    changed = _document()
    changed["policy_sources"]["target_thrust_ratio"] = "changed source identity"
    second = load_measurement_comparison_json(_payload(changed))
    with pytest.raises(MeasurementComparisonServiceError, match="stale|identity"):
        run_measurement_comparison_report(
            second, expected_request_sha256=prepared.request_sha256
        )


def test_unmatched_conditions_produce_a_hashed_blocked_report():
    document = _document()
    document["foldable_context"]["open_diameter_m"] = 0.24
    request = load_measurement_comparison_json(_payload(document))
    artifact = run_measurement_comparison_report(request)
    report = json.loads(artifact.report_json)
    assert report["state"] == "blocked_unmatched_or_invalid_experiment_evidence"
    assert report["result"]["metrics"] == {}
    assert report["result"]["target_decision"] == "blocked"
    assert artifact.report_sha256


def test_software_fixture_and_nested_promotion_claims_cannot_promote():
    document = _document()
    document["physical_qualification"] = True
    with pytest.raises(MeasurementComparisonServiceError, match="physical"):
        load_measurement_comparison_json(_payload(document))

    nested = _document()
    nested["policy_sources"]["target_thrust_ratio"] = {
        "physical_qualification": True
    }
    with pytest.raises(MeasurementComparisonServiceError, match="physical|policy source"):
        load_measurement_comparison_json(_payload(nested))


def test_request_collections_and_artifact_are_immutable():
    request = load_measurement_comparison_json(_payload())
    with pytest.raises(TypeError):
        request.policy_sources["target_thrust_ratio"] = "changed"
    with pytest.raises(TypeError):
        request.manifest.policy.maximum_zero_drift["thrust"] = 9.0
    with pytest.raises(TypeError):
        request.decision.summaries[0].metrics["thrust"] = object()
    artifact = prepare_measurement_comparison_report(request)
    with pytest.raises(dataclasses.FrozenInstanceError):
        artifact.request_sha256 = "0" * 64


def test_forged_loaded_request_objects_fail_as_controlled_service_errors():
    request = load_measurement_comparison_json(_payload())
    candidates = (
        dataclasses.replace(request, manifest=object()),
        dataclasses.replace(request, policy_sources={"unexpected": "source"}),
        dataclasses.replace(request, input_sha256="0" * 64),
        dataclasses.replace(request, source_json_bytes=b"{}"),
    )
    for candidate in candidates:
        with pytest.raises(MeasurementComparisonServiceError, match="identity"):
            prepare_measurement_comparison_report(candidate)


def test_implementation_hashes_bind_real_service_and_core_sources():
    request = load_measurement_comparison_json(_payload())
    report = json.loads(run_measurement_comparison_report(request).report_json)
    hashes = report["request"]["implementation"]["source_files_sha256"]
    expected = {
        "pyfoldable.application.measurement_comparison": ROOT
        / "pyfoldable/application/measurement_comparison.py",
        "pyfoldable.core.measurement_comparison": ROOT
        / "pyfoldable/core/measurement_comparison.py",
        "pyfoldable.core.experiment_contract": ROOT
        / "pyfoldable/core/experiment_contract.py",
    }
    assert set(hashes) == set(expected)
    for name, path in expected.items():
        assert hashes[name] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_application_public_api_exports_py06b_service():
    namespace = {}
    exec("from pyfoldable.application import *", {}, namespace)
    expected = {
        "MAX_COMPARISON_JSON_BYTES",
        "MeasurementComparisonReportArtifact",
        "MeasurementComparisonRequest",
        "MeasurementComparisonServiceError",
        "load_measurement_comparison_json",
        "prepare_measurement_comparison_report",
        "run_measurement_comparison_report",
    }
    assert expected.issubset(namespace)
    assert application.run_measurement_comparison_report is run_measurement_comparison_report
