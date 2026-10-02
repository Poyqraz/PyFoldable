"""C2V-09 declaration pins and the live-eligibility block.

These tests do not select a candidate, seal v2, or enter a trajectory.
A unit-test double is not live execution evidence.
"""

from __future__ import annotations

from pyfoldable.application.c2v09_live_eligibility import (
    assess_live_eligibility,
    load_reviewed_materials,
    run_certificate_dependent,
)
from pyfoldable.application.c2v09_ordered_declaration import (
    CANDIDATE28_MANIFEST_SHA256,
    CANDIDATE29_MANIFEST_SHA256,
    EXTENDED_DECLARATION_SHA256,
    ORIGINAL_MANIFEST_SHA256,
    TECHNICAL_HEAD,
    build_extended_declaration,
)


def _repository():
    from pathlib import Path

    return Path(__file__).resolve().parents[2]


def test_extended_declaration_appends_28_and_29_without_changing_00_27() -> None:
    declaration = build_extended_declaration(_repository())
    assert declaration.order == tuple(f"C2V09-{index:02d}" for index in range(30))
    assert declaration.original_manifest_sha256 == ORIGINAL_MANIFEST_SHA256
    assert declaration.candidate28_manifest_sha256 == CANDIDATE28_MANIFEST_SHA256
    assert declaration.candidate29_manifest_sha256 == CANDIDATE29_MANIFEST_SHA256
    assert declaration.technical_head == TECHNICAL_HEAD
    assert declaration.sha256 == EXTENDED_DECLARATION_SHA256
    assert declaration.candidate28_disposition.startswith("CANDIDATE REJECTED")
    assert declaration.candidate29_disposition == "NOT SELECTED"


def test_tampered_candidate_bytes_are_blocked_before_source_evaluation() -> None:
    root = _repository()
    materials = load_reviewed_materials(root)
    tampered = materials.with_candidate29_bytes(materials.candidate29_bytes + b"\n")
    record = assess_live_eligibility(root, materials=tampered)
    report = run_certificate_dependent(record, source=lambda: None, mapper=lambda: None)
    assert record.status == "CONTRACT BLOCKED"
    assert any("candidate29" in reason for reason in record.mismatches)
    assert report.source_calls == 0
    assert report.mapper_calls == 0
    assert report.selection_calls == 0
    assert report.seal_calls == 0
    assert report.trajectory_calls == 0


def test_incorrect_artifact_identity_is_blocked() -> None:
    root = _repository()
    materials = load_reviewed_materials(root)
    forged = materials.with_artifact_digest(
        "docs/cmm2_c2v09_partition_runtime_certificate.md",
        "0" * 64,
    )
    record = assess_live_eligibility(root, materials=forged)
    assert record.status == "CONTRACT BLOCKED"
    assert any("artifact" in reason for reason in record.mismatches)


def test_claimed_materials_cannot_replace_the_pinned_scale() -> None:
    root = _repository()
    materials = load_reviewed_materials(root).with_theta0(("1/2", "1/3"))
    record = assess_live_eligibility(root, materials=materials)
    assert record.status == "CONTRACT BLOCKED"
    assert any("Theta0" in reason for reason in record.mismatches)


def test_missing_authority_bytes_are_blocked(tmp_path) -> None:
    record = assess_live_eligibility(tmp_path)
    assert record.status == "CONTRACT BLOCKED"
    assert any("unavailable" in reason for reason in record.mismatches)
    report = run_certificate_dependent(record, source=lambda: None)
    assert report.source_calls == 0


def test_changed_scale_or_uncertainty_invalidates_eligibility() -> None:
    root = _repository()
    record = assess_live_eligibility(root, theta0=("1/2", "1/3"))
    assert record.status == "CONTRACT BLOCKED"
    assert any("Theta0" in reason for reason in record.mismatches)
    shifted = assess_live_eligibility(root, uncertainty_hex=("0x1.0p+0",))
    assert shifted.status == "CONTRACT BLOCKED"
    assert any("uncertainty" in reason for reason in shifted.mismatches)


def test_source_hash_mismatch_cannot_be_waived() -> None:
    root = _repository()
    record = assess_live_eligibility(root, source_sha256="ab" * 32, waive_source_mismatch=True)
    assert record.status == "CONTRACT BLOCKED"
    assert any("source" in reason for reason in record.mismatches)
    assert "waive_source_mismatch" not in record.matches


def test_mocked_matching_record_is_not_live_evidence() -> None:
    root = _repository()
    claim = {
        "status": "ELIGIBLE",
        "python_version": "3.12.14",
        "executable_sha256": "fa67443527ed9647f760d807e2a38f26340757123e643c4639cf273ed15d5ea7",
        "libm_sha256": "f06f2ce1f1833df5f41cf13b6447ff07bea993ad9b27297d3428c2f70ab3f0e7",
    }
    record = assess_live_eligibility(root, claimed_record=claim)
    report = run_certificate_dependent(
        record,
        source=lambda: None,
        mapper=lambda: None,
        select=lambda: None,
        seal=lambda: None,
        trajectory=lambda: None,
    )
    assert record.status == "CONTRACT BLOCKED"
    assert any("not live" in reason for reason in record.mismatches)
    assert "python_version" not in record.matches
    assert report.source_calls == report.mapper_calls == report.selection_calls == 0
    assert report.seal_calls == report.trajectory_calls == 0


def test_supplied_dispatch_and_head_claims_cannot_alter_the_live_record() -> None:
    root = _repository()
    live = assess_live_eligibility(root)
    dispatch = load_reviewed_materials(root).certificate_runtime["cos_vaddr"]
    claimed = assess_live_eligibility(
        root,
        caller_claims={"selected_dispatch": dispatch, "executing_head": "a" * 40},
    )
    assert claimed.observations["caller_claims"]["selected_dispatch"] == dispatch
    assert claimed.observations["caller_claims"]["executing_head"] == "a" * 40
    assert claimed.executing_head == live.executing_head
    assert claimed.observations["executing_head"] == live.observations["executing_head"]
    assert claimed.observations["selected_dispatch"] == live.observations.get("selected_dispatch")
    assert claimed.matches == live.matches
    assert claimed.unestablished == live.unestablished
    assert claimed.observations["caller_claims"]["executing_head"] == "a" * 40
    assert claimed.observations["caller_claims"]["selected_dispatch"] == dispatch
    report = run_certificate_dependent(
        claimed,
        source=lambda: None,
        mapper=lambda: None,
        select=lambda: None,
        seal=lambda: None,
        trajectory=lambda: None,
    )
    assert report.source_calls == report.mapper_calls == report.selection_calls == 0
    assert report.seal_calls == report.trajectory_calls == 0


def _patch_runtime(monkeypatch, values: dict[str, object]):
    from pyfoldable.application import c2v09_live_eligibility as gate

    real = gate.observe_execution_context

    def wrapped(root):
        observed = real(root)
        observed.update(values)
        return observed

    monkeypatch.setattr(gate, "observe_execution_context", wrapped)


def test_missing_observation_blocks_without_a_source_call(monkeypatch) -> None:
    root = _repository()
    _patch_runtime(
        monkeypatch,
        {
            "executable_sha256": None,
            "libm_sha256": None,
            "libc_sha256": None,
            "loader_sha256": None,
            "fegetround": None,
            "mxcsr": None,
            "cpu_family_model_stepping": None,
            "selected_dispatch": None,
            "cpu_feature_flags": None,
        },
    )
    monkeypatch.setattr(
        "pyfoldable.application.c2v09_live_eligibility.resolve_loaded_cos_vaddr",
        lambda: None,
    )
    record = assess_live_eligibility(root)
    assert record.status == "CONTRACT BLOCKED"
    assert "returned source object" in record.unestablished
    assert "loaded cosine instruction bytes" in record.unestablished
    assert "cpython executable" in record.unestablished
    assert "cpython executable" not in record.mismatches
    assert "CPU family/model/stepping" in record.unestablished
    assert "CPU features" in record.unestablished
    assert "selected dispatch" in record.unestablished
    assert "MXCSR" in record.unestablished
    report = run_certificate_dependent(record, source=lambda: (_ for _ in ()).throw(AssertionError("called")))
    assert report.source_calls == 0


def test_runtime_mismatch_is_recorded_only_when_the_observed_value_differs(monkeypatch) -> None:
    root = _repository()
    materials = load_reviewed_materials(root)
    executable = materials.certificate_runtime["executable_sha256"]
    observed = {"executable_sha256": executable}
    _patch_runtime(monkeypatch, observed)
    matched = assess_live_eligibility(root)
    observed["executable_sha256"] = "ab" * 32
    differed = assess_live_eligibility(root)
    assert "cpython executable" in matched.matches
    assert "cpython executable" not in matched.mismatches
    assert "cpython executable" in differed.mismatches
    assert matched.status == differed.status == "CONTRACT BLOCKED"
    assert run_certificate_dependent(matched, source=lambda: None).source_calls == 0


def test_stale_context_and_post_call_change_reject_the_record() -> None:
    root = _repository()
    record = assess_live_eligibility(root)
    stale = record.accept(context_id="not-the-observed-context")
    assert stale.accepted is False
    assert stale.reason == "stale eligibility context"
    after = record.check_after(fegetround="1")
    assert after.invalidated
    assert after.status == "CONTRACT BLOCKED"
    assert any("post-call" in reason for reason in after.mismatches)
    report = run_certificate_dependent(after, mapper=lambda: (_ for _ in ()).throw(AssertionError("called")))
    assert report.mapper_calls == 0


def test_actual_context_is_blocked_and_preserves_partial_observations() -> None:
    root = _repository()
    record = assess_live_eligibility(root)
    report = run_certificate_dependent(
        record,
        source=lambda: None,
        mapper=lambda: None,
        select=lambda: None,
        seal=lambda: None,
        trajectory=lambda: None,
    )
    assert record.status == "CONTRACT BLOCKED"
    assert record.observations["technical_head"] == TECHNICAL_HEAD
    assert record.observations["executing_head"] == record.executing_head
    assert "reviewed technical head" not in record.mismatches
    assert not any("executing artifact bytes differ" in reason for reason in record.mismatches)
    assert "Theta0" in record.unestablished
    assert "stored center uncertainty" in record.unestablished
    assert "candidate29 source bytes" in record.unestablished
    assert "Theta0" not in record.matches
    assert "candidate29 source bytes" not in record.matches
    assert "CPU/feature identity" not in record.matches
    if record.observations.get("cpu_feature_flags"):
        assert "CPU features" not in record.unestablished
    else:
        assert "CPU features" in record.unestablished
    if record.observations.get("selected_dispatch") is None:
        assert "selected dispatch" in record.unestablished
    else:
        assert "selected dispatch" in record.matches or "selected dispatch" in record.mismatches
    assert "original 00-27 manifest" in record.matches
    assert "candidate28 manifest" in record.matches
    assert "candidate29 manifest" in record.matches
    assert record.observations["python_version"]
    assert record.observations["executable_sha256"]
    assert report.source_calls == 0
    assert report.mapper_calls == 0
    assert report.selection_calls == 0
    assert report.seal_calls == 0
    assert report.trajectory_calls == 0
    assert record.partial_record["selection"] is None
    assert record.partial_record["sealed"] is False
