"""C2V-09 declaration pins and the live-eligibility block.

These tests do not select a candidate, seal v2, or enter a trajectory.
A unit-test double is not live execution evidence.
"""

from __future__ import annotations

import json
import subprocess

from pyfoldable.application.c2v09_binding_collector import collect_binding_record
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
    canonical_bytes,
    sha256_bytes,
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


_CHANGED = (
    "pyfoldable/application/cmm2_coupled_transient_service.py",
    "pyfoldable/dynamics/cmm2_coupled_transient.py",
)
_NEW_NODES = (
    "pyfoldable/dynamics/cmm2_radau_dense.py",
    "pyfoldable/application/c2v09_ordered_declaration.py",
    "pyfoldable/application/c2v09_live_eligibility.py",
    "pyfoldable/application/c2v09_binding_collector.py",
    "pyfoldable/application/c2v09_runtime_applicability.py",
    "pyfoldable/application/c2v09_cosine_path_certificate.py",
    "pyfoldable/application/c2v09_cosine_path_probe.c",
)


def _refused(record):
    report = run_certificate_dependent(
        record,
        source=lambda: None,
        mapper=lambda: None,
        select=lambda: None,
        seal=lambda: None,
        trajectory=lambda: None,
    )
    assert record.accept(context_id=record.context_id).accepted is False
    assert report.source_calls == report.mapper_calls == report.selection_calls == 0
    assert report.seal_calls == report.trajectory_calls == 0
    assert record.status == "CONTRACT BLOCKED"


def test_changed_cmm2_files_reach_the_gate_mismatch_record() -> None:
    record = assess_live_eligibility(_repository())
    for path in _CHANGED:
        assert f"historical source file {path}" in record.mismatches
        assert f"historical source file identity {path}" not in record.matches
        assert f"loaded-code identity {path}" in record.unestablished
        assert f"operation-graph applicability {path}" in record.unestablished
    _refused(record)


def test_matching_file_hash_does_not_clear_loaded_code_or_graph() -> None:
    path = "pyfoldable/core/units.py"
    record = assess_live_eligibility(_repository())
    assert f"historical source file identity {path}" in record.matches
    assert f"loaded-code identity {path}" in record.unestablished
    assert f"operation-graph applicability {path}" in record.unestablished
    assert f"loaded-code identity {path}" not in record.matches
    assert f"operation-graph applicability {path}" not in record.matches
    assert record.status == "CONTRACT BLOCKED"
    _refused(record)


def test_seven_new_nodes_have_no_historical_clearance() -> None:
    record = assess_live_eligibility(_repository())
    prefix = "no historical applicability clearance "
    paths = [item[len(prefix):] for item in record.unestablished if item.startswith(prefix)]
    assert paths == list(_NEW_NODES)
    assert f"compiled loaded native identity {_NEW_NODES[-1]}" in record.unestablished
    assert f"compiled loaded native identity {_NEW_NODES[-1]}" not in record.matches
    _refused(record)


def test_malformed_inventory_stays_unestablished(monkeypatch) -> None:
    monkeypatch.setattr(
        "pyfoldable.application.c2v09_live_eligibility.collect_binding_record",
        lambda _root: {
            "canonical_payload": {
                "observations": {"mxcsr": None, "cpu_feature_flags": None},
                "python_dependency_inventory": {"certificate_sources": "broken"},
            }
        },
    )
    record = assess_live_eligibility(_repository())
    assert "python dependency inventory" in record.unestablished
    assert record.status == "CONTRACT BLOCKED"
    _refused(record)


def test_inventory_observation_is_a_separate_blocked_record() -> None:
    root = _repository()
    document = json.loads(
        (root / "reports/c2v09_source_inventory_enforcement/observation.json").read_text(encoding="utf-8")
    )
    payload = document["canonical_payload"]
    assert "canonical_sha256" not in payload
    assert document["canonical_sha256"] == sha256_bytes(canonical_bytes(payload))
    assert payload["eligibility_evidence"] is False
    assert payload["physical_qualification"] is False
    assert payload["status"] == "CONTRACT BLOCKED"
    assert payload["source_callbacks"] == payload["mapper_callbacks"] == payload["trajectory_callbacks"] == 0
    assert payload["historical_source_file_mismatches"] == [
        f"historical source file {path}" for path in _CHANGED
    ]
    assert payload["new_nodes_without_historical_clearance"] == list(_NEW_NODES)
    assert payload["loaded_code_unestablished_for_units"] is True
    checkout = payload["checkout_sha"]
    present = subprocess.call(
        ["git", "cat-file", "-e", f"{checkout}^{{commit}}"],
        cwd=root,
        stderr=subprocess.DEVNULL,
    ) == 0
    if present:
        tree = subprocess.check_output(["git", "rev-parse", f"{checkout}^{{tree}}"], cwd=root, text=True).strip()
        assert payload["tree_sha"] == tree


def _replace_sources(monkeypatch, sources) -> None:
    def wrapped(root):
        record = collect_binding_record(root)
        record["canonical_payload"]["python_dependency_inventory"]["certificate_sources"] = sources
        return record

    monkeypatch.setattr("pyfoldable.application.c2v09_live_eligibility.collect_binding_record", wrapped)


def _copied_sources():
    record = collect_binding_record(_repository())
    return [dict(row) for row in record["canonical_payload"]["python_dependency_inventory"]["certificate_sources"]]


def test_empty_truncated_extra_substituted_and_duplicate_inventories_fail_closed(monkeypatch) -> None:
    root = _repository()
    real = _copied_sources()
    invented = {
        "path": "not-a-certificate-path.py",
        "historical_sha256": None,
        "current_file_sha256": None,
        "file_identity": "MATCH",
    }
    cases = (
        [],
        real[:20],
        real + [invented],
        real[1:] + [invented],
        real[:-1] + [dict(real[0])],
    )
    for sources in cases:
        _replace_sources(monkeypatch, sources)
        record = assess_live_eligibility(root)
        assert "python dependency inventory" in record.unestablished
        assert "historical source file identity not-a-certificate-path.py" not in record.matches
        assert record.status == "CONTRACT BLOCKED"
        _refused(record)


def test_missing_hashes_and_contradictory_labels_are_not_trusted_matches(monkeypatch) -> None:
    root = _repository()
    sources = _copied_sources()
    units = next(row for row in sources if row["path"] == "pyfoldable/core/units.py")
    service = next(row for row in sources if row["path"] == _CHANGED[0])
    units["file_identity"] = "MATCH"
    units["historical_sha256"] = None
    units["current_file_sha256"] = None
    service["file_identity"] = "MATCH"
    _replace_sources(monkeypatch, sources)
    missing = assess_live_eligibility(root)
    assert "historical source file identity pyfoldable/core/units.py" not in missing.matches
    assert "historical source file identity pyfoldable/core/units.py" in missing.unestablished
    assert f"historical source file {_CHANGED[0]}" in missing.mismatches
    assert f"historical source file identity {_CHANGED[0]}" not in missing.matches

    sources = _copied_sources()
    units = next(row for row in sources if row["path"] == "pyfoldable/core/units.py")
    units["file_identity"] = "MISMATCH"
    _replace_sources(monkeypatch, sources)
    contradictory = assess_live_eligibility(root)
    assert "historical source file identity pyfoldable/core/units.py" in contradictory.matches
    assert "historical source file pyfoldable/core/units.py" not in contradictory.mismatches
    _refused(missing)
    _refused(contradictory)


def test_claims_replay_and_waiver_cannot_clear_source_obligations() -> None:
    root = _repository()
    claims = {
        "waive_source_mismatch": True,
        "historical source file pyfoldable/application/cmm2_coupled_transient_service.py": "MATCH",
        "loaded-code identity pyfoldable/core/units.py": "MATCH",
    }
    record = assess_live_eligibility(
        root,
        caller_claims=claims,
        claimed_record={"status": "ELIGIBLE"},
        waive_source_mismatch=True,
    )
    for path in _CHANGED:
        assert f"historical source file {path}" in record.mismatches
    assert "loaded-code identity pyfoldable/core/units.py" in record.unestablished
    assert "caller-supplied record is not live execution evidence" in record.mismatches
    assert record.observations["caller_claims"]["waive_source_mismatch"] is True
    assert record.status == "CONTRACT BLOCKED"
    _refused(record)
