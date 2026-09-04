from __future__ import annotations

import json
from pathlib import Path

import pytest

from pyfoldable.application.evidence_import import (
    EvidenceImportError,
    inspect_evidence_upload,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CFD = REPO_ROOT / "tests/fixtures/cfd_reference/apcsf_10x4.7_published_v1.json"
FEA = REPO_ROOT / "reports/pr09_fea_contract_evidence.json"
EXPERIMENT = REPO_ROOT / "reports/pr10_experiment_contract_evidence.json"


@pytest.mark.parametrize(
    ("kind", "path", "identity", "classification"),
    [
        (
            "cfd_reference",
            CFD,
            "apcsf-10x4.7-published-cfd-v1",
            "published_cfd_model_form_context_only",
        ),
        (
            "fea_contract_report",
            FEA,
            "pr09-fea-contract-software-fixture-v1",
            "fea_software_contract_physical_evidence_pending",
        ),
        (
            "experiment_contract_report",
            EXPERIMENT,
            "pr10-synthetic-test-stand-v1",
            "experiment_software_contract_measurements_pending",
        ),
    ],
)
def test_evidence_upload_accepts_versioned_contract_examples(
    kind,
    path,
    identity,
    classification,
):
    artifact = inspect_evidence_upload(path.read_bytes(), path.name, kind)

    assert artifact.kind == kind
    assert artifact.identity == identity
    assert artifact.classification == classification
    assert artifact.physical_qualification is False
    assert artifact.schema_version == 1
    assert artifact.size_bytes == len(path.read_bytes())
    assert len(artifact.source_sha256) == 64
    assert artifact.summary


@pytest.mark.parametrize(
    "payload",
    [b"", b"[]", b'{"value": NaN}', b'{"value": 1, "value": 2}', b"not-json"],
)
def test_evidence_upload_rejects_invalid_json(payload):
    with pytest.raises(EvidenceImportError):
        inspect_evidence_upload(payload, "evidence.json", "fea_contract_report")


def test_evidence_upload_rejects_kind_mismatch():
    with pytest.raises(EvidenceImportError, match="FEA"):
        inspect_evidence_upload(CFD.read_bytes(), CFD.name, "fea_contract_report")


@pytest.mark.parametrize("path", [FEA, EXPERIMENT])
def test_evidence_upload_rejects_physical_qualification_promotion(path):
    document = json.loads(path.read_text(encoding="utf-8"))
    document["project_readiness"]["physical_qualification"] = True

    with pytest.raises(EvidenceImportError, match="physical qualification"):
        inspect_evidence_upload(
            json.dumps(document).encode("utf-8"),
            path.name,
            "fea_contract_report" if path == FEA else "experiment_contract_report",
        )


def test_evidence_upload_rejects_fea_unit_contract_drift():
    document = json.loads(FEA.read_text(encoding="utf-8"))
    document["manifest"]["load_cases"][0]["required_metric_units"][
        "maximum_total_deformation"
    ] = "mm"

    with pytest.raises(EvidenceImportError, match="unit"):
        inspect_evidence_upload(
            json.dumps(document).encode("utf-8"),
            FEA.name,
            "fea_contract_report",
        )


def test_evidence_upload_rejects_experiment_calibration_unit_drift():
    document = json.loads(EXPERIMENT.read_text(encoding="utf-8"))
    document["manifest"]["calibrations"][0]["unit"] = "kgf"

    with pytest.raises(EvidenceImportError, match="Calibration unit"):
        inspect_evidence_upload(
            json.dumps(document).encode("utf-8"),
            EXPERIMENT.name,
            "experiment_contract_report",
        )


def test_evidence_upload_rejects_oversized_or_unsafe_names():
    with pytest.raises(EvidenceImportError, match="maximum size"):
        inspect_evidence_upload(
            b"{" + b" " * (5 * 1024 * 1024) + b"}",
            "large.json",
            "cfd_reference",
        )
    with pytest.raises(EvidenceImportError, match="plain JSON filename"):
        inspect_evidence_upload(CFD.read_bytes(), "../fixture.json", "cfd_reference")
    with pytest.raises(EvidenceImportError, match="plain JSON filename"):
        inspect_evidence_upload(CFD.read_bytes(), "..\\fixture.json", "cfd_reference")


@pytest.mark.parametrize(
    ("path", "kind"),
    [(FEA, "fea_contract_report"), (EXPERIMENT, "experiment_contract_report")],
)
@pytest.mark.parametrize("section", ["software_fixture_decision", "project_readiness"])
def test_evidence_upload_requires_explicit_false_physical_qualification(
    path, kind, section
):
    document = json.loads(path.read_text(encoding="utf-8"))
    del document[section]["physical_qualification"]

    with pytest.raises(EvidenceImportError, match="physical_qualification"):
        inspect_evidence_upload(json.dumps(document).encode(), path.name, kind)


@pytest.mark.parametrize(
    ("field", "value"),
    [("cases", []), ("missing_case_ids", ["steady_max_rpm"])],
)
def test_evidence_upload_rejects_inconsistent_fea_fixture_decision(field, value):
    document = json.loads(FEA.read_text(encoding="utf-8"))
    document["software_fixture_decision"][field] = value

    with pytest.raises(EvidenceImportError, match="FEA"):
        inspect_evidence_upload(json.dumps(document).encode(), FEA.name, "fea_contract_report")


@pytest.mark.parametrize(
    ("field", "value"),
    [("runs", []), ("summaries", []), ("missing_roles", ["foldable"])],
)
def test_evidence_upload_rejects_inconsistent_experiment_fixture_decision(field, value):
    document = json.loads(EXPERIMENT.read_text(encoding="utf-8"))
    document["software_fixture_decision"][field] = value

    with pytest.raises(EvidenceImportError, match="Experiment"):
        inspect_evidence_upload(
            json.dumps(document).encode(), EXPERIMENT.name, "experiment_contract_report"
        )


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("test_stand_manifest_sha256",), "0" * 64, "manifest digest"),
        (("runs", 0, "raw_data_sha256"), "G" * 64, "raw_data_sha256"),
        (("runs", 0, "summary_sha256"), "0" * 64, "summary digest"),
        (("runs", 0, "experiment_date"), "not-a-date", "experiment_date"),
    ],
)
def test_evidence_upload_rejects_experiment_provenance_tampering(
    path, value, message
):
    document = json.loads(EXPERIMENT.read_text(encoding="utf-8"))
    target = document["software_fixture_decision"]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(EvidenceImportError, match=message):
        inspect_evidence_upload(
            json.dumps(document).encode(), EXPERIMENT.name,
            "experiment_contract_report",
        )


@pytest.mark.parametrize(
    ("path", "kind", "field"),
    [
        (FEA, "fea_contract_report", "maximum_mesh_change_percent"),
        (FEA, "fea_contract_report", "maximum_force_balance_error_percent"),
        (EXPERIMENT, "experiment_contract_report", "minimum_repeats"),
        (EXPERIMENT, "experiment_contract_report", "coverage_factor"),
        (EXPERIMENT, "experiment_contract_report", "maximum_zero_drift"),
    ],
)
def test_evidence_upload_rejects_missing_policy_fields(path, kind, field):
    document = json.loads(path.read_text(encoding="utf-8"))
    del document["manifest"]["policy"][field]

    with pytest.raises(EvidenceImportError):
        inspect_evidence_upload(json.dumps(document).encode(), path.name, kind)


@pytest.mark.parametrize(
    ("path", "kind", "collection"),
    [
        (FEA, "fea_contract_report", "materials"),
        (EXPERIMENT, "experiment_contract_report", "calibrations"),
    ],
)
def test_evidence_upload_rejects_promoted_component_qualification(
    path, kind, collection
):
    document = json.loads(path.read_text(encoding="utf-8"))
    document["manifest"][collection][0]["qualification"] = "physical_qualified"

    with pytest.raises(EvidenceImportError, match="qualification"):
        inspect_evidence_upload(json.dumps(document).encode(), path.name, kind)


def test_evidence_upload_rejects_non_array_fea_property_names():
    document = json.loads(FEA.read_text(encoding="utf-8"))
    document["manifest"]["materials"][0]["property_names"] = "abcdefgh"

    with pytest.raises(EvidenceImportError, match="property_names"):
        inspect_evidence_upload(json.dumps(document).encode(), FEA.name, "fea_contract_report")


def test_evidence_upload_rejects_overflowing_json_number():
    payload = FEA.read_text(encoding="utf-8").replace(
        '"maximum_mesh_change_percent": 5.0',
        '"maximum_mesh_change_percent": 1e999',
    )

    with pytest.raises(EvidenceImportError, match="finite"):
        inspect_evidence_upload(payload.encode(), FEA.name, "fea_contract_report")


def test_evidence_upload_normalizes_excessive_json_nesting():
    payload = ('{"extra":' + "[" * 2000 + "0" + "]" * 2000 + "}").encode()

    with pytest.raises(EvidenceImportError, match="nesting"):
        inspect_evidence_upload(payload, "nested.json", "fea_contract_report")


@pytest.mark.parametrize(
    ("path", "kind", "identity_path"),
    [
        (CFD, "cfd_reference", ("id",)),
        (FEA, "fea_contract_report", ("manifest", "id")),
        (EXPERIMENT, "experiment_contract_report", ("manifest", "id")),
    ],
)
def test_evidence_upload_rejects_noncanonical_identity(path, kind, identity_path):
    document = json.loads(path.read_text(encoding="utf-8"))
    target = document
    for key in identity_path[:-1]:
        target = target[key]
    target[identity_path[-1]] = "attacker-controlled-v1"
    if kind == "fea_contract_report":
        document["software_fixture_decision"]["manifest_id"] = "attacker-controlled-v1"
    elif kind == "experiment_contract_report":
        document["software_fixture_decision"]["stand_id"] = "attacker-controlled-v1"

    with pytest.raises(EvidenceImportError, match="canonical|identity"):
        inspect_evidence_upload(json.dumps(document).encode(), path.name, kind)


@pytest.mark.parametrize("value", [0, "", None])
def test_evidence_upload_requires_literal_false_cfd_point_eligibility(value):
    document = json.loads(CFD.read_text(encoding="utf-8"))
    document["points"][0]["qualification_eligible"] = value

    with pytest.raises(EvidenceImportError, match="qualification_eligible"):
        inspect_evidence_upload(json.dumps(document).encode(), CFD.name, "cfd_reference")


def test_evidence_upload_normalizes_invalid_kind_type():
    with pytest.raises(EvidenceImportError, match="Unsupported evidence kind"):
        inspect_evidence_upload(CFD.read_bytes(), CFD.name, [])
