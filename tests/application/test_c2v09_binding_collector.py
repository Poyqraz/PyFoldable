"""Zero-source-call binding collector. Doubles do not become live matches."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from pyfoldable.application.c2v09_binding_collector import (
    collect_binding_record,
    read_loaded_vaddr,
    resolve_loaded_cos_vaddr,
)
from pyfoldable.application.c2v09_live_eligibility import (
    assess_live_eligibility,
    run_certificate_dependent,
)
from pyfoldable.application.c2v09_ordered_declaration import canonical_bytes, sha256_bytes


def _repository() -> Path:
    return Path(__file__).resolve().parents[2]


def _body(record: dict) -> dict:
    payload = record["canonical_payload"]
    assert isinstance(payload, dict)
    assert "canonical_sha256" not in payload
    return payload


def _assert_recorded_checkout(root: Path, payload: dict) -> None:
    """Check the named tree when that commit is present. A shallow clone is not a mismatch."""
    checkout = payload["checkout_sha"]
    tree_sha = payload["tree_sha"]
    assert isinstance(checkout, str) and len(checkout) == 40
    assert isinstance(tree_sha, str) and len(tree_sha) == 40
    present = subprocess.call(
        ["git", "cat-file", "-e", f"{checkout}^{{commit}}"],
        cwd=root,
        stderr=subprocess.DEVNULL,
    ) == 0
    if not present:
        return
    tree = subprocess.check_output(["git", "rev-parse", f"{checkout}^{{tree}}"], cwd=root, text=True).strip()
    assert tree_sha == tree


CHANGED_CMM2_SOURCES = (
    "pyfoldable/application/cmm2_coupled_transient_service.py",
    "pyfoldable/dynamics/cmm2_coupled_transient.py",
)
UNHISTORICAL_MODULES = {
    "dense": "pyfoldable/dynamics/cmm2_radau_dense.py",
    "declaration": "pyfoldable/application/c2v09_ordered_declaration.py",
    "eligibility": "pyfoldable/application/c2v09_live_eligibility.py",
    "collector": "pyfoldable/application/c2v09_binding_collector.py",
}


def test_collector_separates_capsules_dependencies_and_graph() -> None:
    record = _body(collect_binding_record(_repository()))
    assert record["historical_capsules"]["runtime_binding_sha256"]
    assert "file_sha256" not in record["historical_capsules"]
    assert record["executing_dependencies"]["libm"]["file_sha256"]
    assert record["reviewed_conditional_graph"]["cos_body_vaddr"] == "0x7bad0"
    assert record["checkout_sha"]
    assert record["tree_sha"]
    assert "file hashes do not establish loaded instructions" in record["limitations"]
    assert "CPU feature labels do not establish dispatch" in record["limitations"]
    assert record["source_callbacks"] == 0
    assert record["eligibility_evidence"] is False
    assert record["physical_qualification"] is False
    assert record["outcome"] == "recorded partial observation"
    assert record["runtime"]["python_version"]
    assert record["runtime"]["executable"]
    assert "not eligibility evidence" in " ".join(record["limitations"])


def test_unreadable_instruction_range_is_not_established(monkeypatch) -> None:
    monkeypatch.setattr(
        "pyfoldable.application.c2v09_binding_collector.read_loaded_vaddr",
        lambda *_args, **_kwargs: None,
    )
    record = _body(collect_binding_record(_repository()))
    assert record["observations"]["loaded_cos_body"] == "NOT ESTABLISHED"
    assert "loaded certificate cos body" not in record["classifications"]["matches"]
    assert "loaded certificate cos body" in record["classifications"]["not_established"]


def test_different_loaded_bytes_are_a_mismatch(monkeypatch) -> None:
    monkeypatch.setattr(
        "pyfoldable.application.c2v09_binding_collector.read_loaded_vaddr",
        lambda *_args, **_kwargs: b"\x00",
    )
    record = _body(collect_binding_record(_repository()))
    assert record["observations"]["loaded_cos_body"] == "MISMATCH"
    assert "loaded certificate cos body" in record["classifications"]["mismatches"]


def test_cpu_flags_do_not_invent_dispatch(monkeypatch) -> None:
    monkeypatch.setattr(
        "pyfoldable.application.c2v09_binding_collector.resolve_loaded_cos_vaddr",
        lambda: None,
    )
    monkeypatch.setattr(
        "pyfoldable.application.c2v09_binding_collector._cpu_feature_flags",
        lambda: ["avx", "fma"],
    )
    record = _body(collect_binding_record(_repository()))
    assert record["observations"]["cpu_feature_flags"] == ["avx", "fma"]
    assert record["observations"]["resolved_libm_cos_symbol_vaddr"] is None
    assert record["observations"]["wrapper_selected_call_dispatch"] is None
    assert record["observations"]["loaded_dispatch_inferred_from_cpu"] is False
    assert "resolved libm cos symbol" in record["classifications"]["not_established"]
    assert "wrapper/selected-call dispatch" in record["classifications"]["not_established"]
    assert "resolved cos dispatch" not in record["classifications"]["not_established"]


def test_matching_libm_symbol_does_not_establish_wrapper_dispatch(monkeypatch) -> None:
    monkeypatch.setattr(
        "pyfoldable.application.c2v09_binding_collector.resolve_loaded_cos_vaddr",
        lambda: "0x7bad0",
    )
    record = _body(collect_binding_record(_repository()))
    classes = record["classifications"]
    assert record["observations"]["resolved_libm_cos_symbol_vaddr"] == "0x7bad0"
    assert record["observations"]["wrapper_selected_call_dispatch"] is None
    assert "resolved libm cos symbol" in classes["matches"]
    assert "resolved cos dispatch" not in classes["matches"]
    assert "wrapper/selected-call dispatch" in classes["not_established"]
    assert "wrapper/selected-call dispatch" not in classes["matches"]
    assert "wrapper/selected-call dispatch" not in classes["mismatches"]


def test_matching_lookup_does_not_clear_the_eligibility_blocker(monkeypatch) -> None:
    monkeypatch.setattr(
        "pyfoldable.application.c2v09_live_eligibility.resolve_loaded_cos_vaddr",
        lambda: "0x7bad0",
    )
    monkeypatch.setattr(
        "pyfoldable.application.c2v09_binding_collector.resolve_loaded_cos_vaddr",
        lambda: "0x7bad0",
    )
    record = assess_live_eligibility(_repository())
    assert "selected dispatch" in record.unestablished
    assert "selected dispatch" not in record.matches
    assert "selected dispatch" not in record.mismatches
    assert record.observations.get("selected_dispatch") is None
    report = run_certificate_dependent(record, source=lambda: None, trajectory=lambda: None)
    assert report.source_calls == report.trajectory_calls == 0


def test_certificate_sources_keep_file_identity_apart_from_loaded_code() -> None:
    root = _repository()
    inventory = _body(collect_binding_record(root))["python_dependency_inventory"]
    sources = inventory["certificate_sources"]
    assert len(sources) == 21
    by_path = {row["path"]: row for row in sources}
    assert len(by_path) == 21
    for path in CHANGED_CMM2_SOURCES:
        assert path in by_path
    for path, row in by_path.items():
        current = sha256_bytes((root / path).read_bytes())
        assert row["historical_sha256"]
        assert row["current_file_sha256"] == current
        assert row["file_identity"] == ("MATCH" if row["historical_sha256"] == current else "MISMATCH")
        assert row["loaded_code_identity"] == "NOT ESTABLISHED"
        assert row["operation_graph_applicability"] == "NOT ESTABLISHED"
        assert row["file_identity"] != row["loaded_code_identity"]
    for path in CHANGED_CMM2_SOURCES:
        assert by_path[path]["file_identity"] == "MISMATCH"


def test_new_modules_have_no_invented_historical_match() -> None:
    root = _repository()
    record = _body(collect_binding_record(root))
    certificate_paths = {row["path"] for row in record["python_dependency_inventory"]["certificate_sources"]}
    rows = {row["role"]: row for row in record["python_dependency_inventory"]["modules_without_historical_record"]}
    assert set(rows) == set(UNHISTORICAL_MODULES)
    for role, path in UNHISTORICAL_MODULES.items():
        row = rows[role]
        current = sha256_bytes((root / path).read_bytes())
        assert row["path"] == path
        assert path not in certificate_paths
        assert row["historical_sha256"] is None
        assert row["current_file_sha256"] == current
        assert row["historical_sha256"] != current
        assert row["file_identity"] == "NO HISTORICAL RECORD"
        assert row["loaded_code_identity"] == "NOT ESTABLISHED"
        assert row["operation_graph_applicability"] == "NOT ESTABLISHED"


def test_digest_covers_only_the_canonical_payload() -> None:
    record = collect_binding_record(_repository())
    payload = record["canonical_payload"]
    assert "canonical_sha256" not in payload
    assert "digest_scope" not in payload
    assert "canonical_payload" in record["digest_scope"]
    assert record["canonical_sha256"] == sha256_bytes(canonical_bytes(payload))
    assert sha256_bytes(canonical_bytes(record)) != record["canonical_sha256"]
    assert payload["eligibility_evidence"] is False
    assert payload["physical_qualification"] is False


def test_absent_checkout_object_does_not_reject_the_record(monkeypatch) -> None:
    payload = {"checkout_sha": "a" * 40, "tree_sha": "b" * 40}

    def absent(*_args, **_kwargs) -> int:
        return 1

    def must_not_resolve(*_args, **_kwargs) -> str:
        raise AssertionError("rev-parse must not run when the commit object is absent")

    monkeypatch.setattr(subprocess, "call", absent)
    monkeypatch.setattr(subprocess, "check_output", must_not_resolve)
    _assert_recorded_checkout(_repository(), payload)


def test_persisted_partial_record_recomputes_and_is_not_eligibility() -> None:
    root = _repository()
    document = json.loads((root / "reports/c2v09_binding_observation/partial_record.json").read_text(encoding="utf-8"))
    payload = document["canonical_payload"]
    assert "canonical_sha256" not in payload
    assert "digest_scope" not in payload
    assert "canonical_payload" in document["digest_scope"]
    assert document["canonical_sha256"] == sha256_bytes(canonical_bytes(payload))
    assert sha256_bytes(canonical_bytes(document)) != document["canonical_sha256"]
    assert payload["outcome"] == "recorded partial observation"
    assert payload["eligibility_evidence"] is False
    assert payload["physical_qualification"] is False
    assert payload["source_callbacks"] == 0
    assert payload["runtime"]["python_version"]
    assert payload["runtime"]["executable"]
    assert payload["observations"]["wrapper_selected_call_dispatch"] is None
    assert "wrapper/selected-call dispatch" in payload["classifications"]["not_established"]
    assert "not eligibility evidence" in " ".join(payload["limitations"])
    _assert_recorded_checkout(root, payload)
    by_path = {row["path"]: row for row in payload["python_dependency_inventory"]["certificate_sources"]}
    assert len(by_path) == 21
    for path in CHANGED_CMM2_SOURCES:
        assert by_path[path]["file_identity"] == "MISMATCH"
        assert by_path[path]["loaded_code_identity"] == "NOT ESTABLISHED"
        assert by_path[path]["operation_graph_applicability"] == "NOT ESTABLISHED"
    roles = {row["role"]: row for row in payload["python_dependency_inventory"]["modules_without_historical_record"]}
    assert set(roles) == set(UNHISTORICAL_MODULES)
    for role, path in UNHISTORICAL_MODULES.items():
        assert roles[role]["path"] == path
        assert roles[role]["historical_sha256"] is None
        assert roles[role]["file_identity"] == "NO HISTORICAL RECORD"


def test_collector_does_not_call_source_mapper_or_trajectory() -> None:
    source = Path(__file__).resolve().parents[2] / "pyfoldable" / "application" / "c2v09_binding_collector.py"
    text = source.read_text(encoding="utf-8")
    assert "bem" not in text
    assert "mapper" not in text
    assert "trajectory" not in text
    record = _body(collect_binding_record(_repository()))
    report = run_certificate_dependent(
        assess_live_eligibility(_repository()),
        source=lambda: None,
        mapper=lambda: None,
        select=lambda: None,
        seal=lambda: None,
        trajectory=lambda: None,
    )
    assert record["source_callbacks"] == 0
    assert report.source_calls == report.mapper_calls == report.selection_calls == 0
    assert report.seal_calls == report.trajectory_calls == 0
    assert read_loaded_vaddr is not None
    assert resolve_loaded_cos_vaddr is not None
