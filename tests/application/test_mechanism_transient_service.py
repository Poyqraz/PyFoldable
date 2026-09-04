import json
import hashlib

import pytest

from pyfoldable.application.mechanism_transient import (
    MechanismTransientError,
    build_literature_modal_example,
    prepare_mechanism_transient,
    run_mechanism_transient,
)


def test_modal_example_is_derived_and_never_prototype_evidence():
    example = build_literature_modal_example()
    assert example.provenance["classification"] == "literature_derived_modal_example"
    assert example.provenance["prototype_measurement"] is False
    assert example.parameters.spring_stiffness_nm_rad == pytest.approx(0.0051 * 15.237**2)
    assert example.parameters.viscous_damping_nm_s_rad == pytest.approx(2 * 0.0051 * 15.237 * 0.111)


def test_json_contract_is_source_bound_reproducible_and_complete():
    example = build_literature_modal_example()
    prepared = prepare_mechanism_transient(example)
    again = prepare_mechanism_transient(example)
    assert prepared.request_sha256 == again.request_sha256
    result = run_mechanism_transient(example)
    doc = json.loads(result.report_json)
    assert doc["physical_qualification"] is False
    assert doc["request_sha256"] == prepared.request_sha256
    assert hashlib.sha256(result.report_json.encode()).hexdigest() == result.report_sha256
    assert doc["request"]["provenance"] == example.provenance
    assert doc["request"]["implementation"]["source_files_sha256"]
    assert len(doc["result"]["samples"]) == len(doc["result"]["time_s"])


def test_tampered_or_failed_requests_are_not_published_as_success():
    example = build_literature_modal_example()
    prepared = prepare_mechanism_transient(example)
    with pytest.raises(MechanismTransientError, match="identity"):
        run_mechanism_transient(example, expected_request_sha256="0" * 64)
    assert prepared.report_json is None
