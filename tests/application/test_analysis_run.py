"""UI-04 allow-listed analysis execution acceptance tests."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
from pathlib import Path

import pytest

import pyfoldable.application.analysis_run as analysis_run
from pyfoldable.application.analysis_run import (
    PR06D_ANALYSIS_ID,
    AnalysisRunError,
    get_analysis_recipe,
    run_analysis,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "tests/fixtures/rotor_benchmark/uiuc_apcsf_10x4.7_v1.json"
ARCHIVE = REPO_ROOT / "reports/pr06d_opening_sensitivity.json"


def _archived_report() -> dict[str, object]:
    return json.loads(ARCHIVE.read_text(encoding="utf-8"))


def _use_archived_report(monkeypatch: pytest.MonkeyPatch, report=None) -> None:
    document = _archived_report() if report is None else report
    monkeypatch.setattr(
        analysis_run,
        "build_pr06d_opening_sensitivity_report",
        lambda fixture_path, **kwargs: copy.deepcopy(document),
    )


def test_recipe_is_fixed_to_the_versioned_screening_fixture() -> None:
    recipe = get_analysis_recipe(REPO_ROOT, PR06D_ANALYSIS_ID)

    assert recipe.id == "pr06d_opening_sensitivity_v1"
    assert recipe.artifact_class == "session_screening_computation"
    assert recipe.fixture_path == FIXTURE
    assert recipe.fixture_sha256 == hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    assert recipe.expected_case_count == 250
    assert recipe.expected_condition_count == 50
    assert recipe.expected_state_count == 5
    assert recipe.annulus_count == 80
    assert recipe.angles_deg == (0, 15, 30, 45, 60)
    assert recipe.hinge_radius_ratio == 0.75
    assert recipe.radial_domain == "station_span"
    assert recipe.include_tip_loss is True
    assert recipe.include_root_loss is False
    assert recipe.loading_branch == "signed_nonreversed"
    assert recipe.polar_representative is False
    assert len(recipe.policy_sha256) == 64


def test_analysis_run_is_deterministic_screening_only_and_archive_equal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_archived_report(monkeypatch)

    artifact = run_analysis(REPO_ROOT, PR06D_ANALYSIS_ID)

    assert artifact.analysis_id == PR06D_ANALYSIS_ID
    assert artifact.artifact_class == "session_screening_computation"
    assert artifact.qualification == "screening_only_until_pr06c_passes"
    assert artifact.physical_qualification is False
    assert artifact.matches_archived_report is True
    assert artifact.case_count == 250
    assert artifact.condition_count == 50
    assert artifact.state_count == 5
    assert len(artifact.rows) == 5
    assert artifact.report_json == ARCHIVE.read_text(encoding="utf-8")
    assert artifact.report_sha256 == hashlib.sha256(
        artifact.report_json.encode("utf-8")
    ).hexdigest()
    assert artifact.report_sha256 == artifact.archived_report_sha256
    assert artifact.fixture_sha256 == hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    assert len(artifact.request_sha256) == 64
    assert len(artifact.policy_sha256) == 64
    manifest = json.loads(artifact.manifest_json)
    assert manifest["artifact_class"] == "session_screening_computation"
    assert manifest["analysis"]["request_sha256"] == artifact.request_sha256
    assert manifest["analysis"]["policy_sha256"] == artifact.policy_sha256
    assert hashlib.sha256(
        json.dumps(
            manifest["analysis"]["policy"],
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest() == artifact.policy_sha256
    assert manifest["physical_qualification"] is False
    assert manifest["archived_report"]["matches"] is True
    assert manifest["session_report"]["sha256"] == artifact.report_sha256
    assert manifest["session_report"]["content"] == _archived_report()
    assert artifact.manifest_sha256 == hashlib.sha256(
        artifact.manifest_json.encode("utf-8")
    ).hexdigest()
    assert artifact.filename == "pr06d_opening_sensitivity_session_manifest.json"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("qualification", "qualified", "screening-only"),
        ("physical_qualification", True, "physical qualification"),
        ("case_count", 249, "case matrix"),
    ],
)
def test_analysis_run_rejects_promoted_or_incomplete_output(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    message: str,
) -> None:
    report = _archived_report()
    report[field] = value
    _use_archived_report(monkeypatch, report)

    with pytest.raises(AnalysisRunError, match=message):
        run_analysis(REPO_ROOT, PR06D_ANALYSIS_ID)


def test_analysis_run_rejects_fixture_identity_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _archived_report()
    report["fixture"]["sha256"] = "0" * 64
    _use_archived_report(monkeypatch, report)

    with pytest.raises(AnalysisRunError, match="fixture SHA-256"):
        run_analysis(REPO_ROOT, PR06D_ANALYSIS_ID)


def test_analysis_run_rejects_resource_policy_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _archived_report()
    report["solver"]["annulus_count"] = 800
    _use_archived_report(monkeypatch, report)

    with pytest.raises(AnalysisRunError, match="annulus_count"):
        run_analysis(REPO_ROOT, PR06D_ANALYSIS_ID)


def test_analysis_run_rejects_semantic_drift_from_the_archived_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _archived_report()
    report["scope"] = "changed"
    _use_archived_report(monkeypatch, report)

    with pytest.raises(AnalysisRunError, match="archived report"):
        run_analysis(REPO_ROOT, PR06D_ANALYSIS_ID)


def test_analysis_catalog_rejects_arbitrary_ids() -> None:
    with pytest.raises(AnalysisRunError, match="allow-listed"):
        get_analysis_recipe(REPO_ROOT, "../../examples/run_anything.py")


def test_analysis_recipe_rejects_missing_assets(tmp_path: Path) -> None:
    with pytest.raises(AnalysisRunError, match="fixture does not exist"):
        get_analysis_recipe(tmp_path, PR06D_ANALYSIS_ID)


@pytest.mark.parametrize("corrupt", ["fixture", "archive"])
def test_analysis_recipe_rejects_corrupt_assets(tmp_path: Path, corrupt: str) -> None:
    fixture = tmp_path / "tests/fixtures/rotor_benchmark/uiuc_apcsf_10x4.7_v1.json"
    archive = tmp_path / "reports/pr06d_opening_sensitivity.json"
    fixture.parent.mkdir(parents=True)
    archive.parent.mkdir(parents=True)
    shutil.copy2(FIXTURE, fixture)
    shutil.copy2(ARCHIVE, archive)
    target = fixture if corrupt == "fixture" else archive
    target.write_text("{}", encoding="utf-8")

    with pytest.raises(AnalysisRunError, match="assets are invalid"):
        get_analysis_recipe(tmp_path, PR06D_ANALYSIS_ID)


def test_analysis_run_normalizes_core_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        analysis_run,
        "build_pr06d_opening_sensitivity_report",
        lambda fixture_path, **kwargs: (_ for _ in ()).throw(ValueError("bad core")),
    )

    with pytest.raises(AnalysisRunError, match="Analysis core failed: bad core"):
        run_analysis(REPO_ROOT, PR06D_ANALYSIS_ID)


def test_analysis_run_detects_archive_change_during_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = tmp_path / "tests/fixtures/rotor_benchmark/uiuc_apcsf_10x4.7_v1.json"
    archive = tmp_path / "reports/pr06d_opening_sensitivity.json"
    fixture.parent.mkdir(parents=True)
    archive.parent.mkdir(parents=True)
    shutil.copy2(FIXTURE, fixture)
    shutil.copy2(ARCHIVE, archive)

    document = _archived_report()

    def mutate_archive(fixture_path: Path, **kwargs):
        changed = copy.deepcopy(document)
        changed["scope"] = "changed during request"
        archive.write_text(json.dumps(changed, indent=2, sort_keys=True) + "\n")
        return changed

    monkeypatch.setattr(
        analysis_run,
        "build_pr06d_opening_sensitivity_report",
        mutate_archive,
    )

    with pytest.raises(AnalysisRunError, match="changed during the analysis request"):
        run_analysis(tmp_path, PR06D_ANALYSIS_ID)
