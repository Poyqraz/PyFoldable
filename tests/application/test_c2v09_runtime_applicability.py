"""Actual-runtime applicability delta. Historical proofs are not this process."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from pyfoldable.application.c2v09_ordered_declaration import (
    TECHNICAL_HEAD,
    canonical_bytes,
    load_reviewed_materials,
    sha256_bytes,
)
from pyfoldable.application.c2v09_runtime_applicability import (
    CERTIFICATE_FILE_SHA256,
    CERTIFICATE_PATH,
    PARTIAL_RECORD_FILE_SHA256,
    prepare_applicability_delta,
)


def _repository() -> Path:
    return Path(__file__).resolve().parents[2]


def _payload(record: dict) -> dict:
    payload = record["canonical_payload"]
    assert "canonical_sha256" not in payload
    assert "digest_scope" not in payload
    return payload


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def _fake_binding(symbol: str | None = "0x7bad0") -> dict:
    payload = {
        "checkout_sha": "c" * 40,
        "tree_sha": "d" * 40,
        "runtime": {"python_version": "3.12.14", "platform": "test", "executable": "/tmp/python"},
        "executing_dependencies": {
            "executable": {"path": "/tmp/python", "file_sha256": "ab" * 32},
            "libm": {"path": "/libm", "file_sha256": "cd" * 32},
            "libc": {"path": "/libc", "file_sha256": "ef" * 32},
            "loader": {"path": "/ld", "file_sha256": "12" * 32},
        },
        "observations": {
            "resolved_libm_cos_symbol_vaddr": symbol,
            "wrapper_selected_call_dispatch": symbol,
            "loaded_cos_body": "MATCH",
            "fegetround": "0",
            "mxcsr": "0x1fa0",
            "x87_control": "0x37f",
            "cpu_feature_flags": ["avx", "fma"],
        },
        "python_dependency_inventory": {
            "certificate_sources": [
                {
                    "path": "pyfoldable/application/cmm2_coupled_transient_service.py",
                    "historical_sha256": "11" * 32,
                    "current_file_sha256": "22" * 32,
                    "file_identity": "MISMATCH",
                    "loaded_code_identity": "NOT ESTABLISHED",
                    "operation_graph_applicability": "NOT ESTABLISHED",
                },
                {
                    "path": "pyfoldable/dynamics/cmm2_coupled_transient.py",
                    "historical_sha256": "33" * 32,
                    "current_file_sha256": "44" * 32,
                    "file_identity": "MISMATCH",
                    "loaded_code_identity": "NOT ESTABLISHED",
                    "operation_graph_applicability": "NOT ESTABLISHED",
                },
                {
                    "path": "pyfoldable/core/units.py",
                    "historical_sha256": "55" * 32,
                    "current_file_sha256": "55" * 32,
                    "file_identity": "MATCH",
                    "loaded_code_identity": "NOT ESTABLISHED",
                    "operation_graph_applicability": "NOT ESTABLISHED",
                },
            ],
            "modules_without_historical_record": [
                {
                    "role": "dense",
                    "path": "pyfoldable/dynamics/cmm2_radau_dense.py",
                    "historical_sha256": None,
                    "current_file_sha256": "66" * 32,
                    "file_identity": "NO HISTORICAL RECORD",
                    "loaded_code_identity": "NOT ESTABLISHED",
                    "operation_graph_applicability": "NOT ESTABLISHED",
                }
            ],
        },
        "eligibility_evidence": False,
        "source_callbacks": 0,
    }
    return {
        "digest_scope": "test fixture",
        "canonical_payload": payload,
        "canonical_sha256": "a" * 64,
    }


def test_historical_certificate_and_partial_record_stay_byte_identical() -> None:
    root = _repository()
    certificate = root / "docs/cmm2_c2v09_partition_runtime_certificate.md"
    partial = root / "reports/c2v09_binding_observation/partial_record.json"
    assert sha256_bytes(certificate.read_bytes()) == CERTIFICATE_FILE_SHA256
    assert sha256_bytes(partial.read_bytes()) == PARTIAL_RECORD_FILE_SHA256


def test_identities_and_symbol_stay_separate(monkeypatch) -> None:
    root = _repository()
    monkeypatch.setattr(
        "pyfoldable.application.c2v09_runtime_applicability.collect_binding_record",
        lambda _root: _fake_binding(),
    )
    payload = _payload(
        prepare_applicability_delta(
            root,
            caller_claims={"selected_call_target": "0x7bad0", "status": "ELIGIBLE"},
        )
    )
    identities = payload["identities"]
    assert identities["technical_authority"]["head"] == TECHNICAL_HEAD
    assert identities["technical_authority"]["pinned_artifact_sha256"][CERTIFICATE_PATH] == CERTIFICATE_FILE_SHA256
    assert identities["executing_implementation"]["checkout_sha"] == _git(root, "rev-parse", "HEAD")
    assert identities["executing_implementation"]["tree_sha"] == _git(root, "rev-parse", "HEAD^{tree}")
    assert identities["technical_authority"]["head"] != identities["executing_implementation"]["checkout_sha"]
    assert identities["observation"]["collector_canonical_sha256"] == "a" * 64
    assert identities["observation"]["collector_checkout_sha"] == "c" * 40
    assert identities["observation"]["preserved_partial_record"]["file_sha256"] == PARTIAL_RECORD_FILE_SHA256
    assert set(identities) == {"technical_authority", "executing_implementation", "observation"}
    separation = payload["dispatch_separation"]
    assert separation["resolved_libm_cos_symbol_vaddr"] == "0x7bad0"
    assert separation["python_math_wrapper_target"] is None
    assert separation["selected_call_target"] is None
    assert separation["symbol_establishes_wrapper"] is False
    assert separation["symbol_establishes_selected_call"] is False
    assert payload["caller_claims"]["selected_call_target"] == "0x7bad0"
    assert payload["status"] == "CONTRACT BLOCKED"
    assert payload["eligibility_evidence"] is False
    assert payload["physical_qualification"] is False
    assert payload["baseline_ci_is_eligibility"] is False
    assert payload["source_callbacks"] == 0


def test_matching_symbol_does_not_transfer_scope_a_or_clear_fresh_certification(monkeypatch) -> None:
    root = _repository()
    monkeypatch.setattr(
        "pyfoldable.application.c2v09_runtime_applicability.collect_binding_record",
        lambda _root: _fake_binding("0x7bad0"),
    )
    payload = _payload(prepare_applicability_delta(root))
    transferred = {row["name"]: row for row in payload["transferred_historical_results"]}
    assert transferred["original v1 partition"]["result"] == "FAIL"
    assert transferred["historical v2"]["result"] == "BLOCKED"
    assert transferred["candidate28"]["result"].startswith("CANDIDATE REJECTED")
    assert transferred["candidate29"]["result"] == "NOT SELECTED"
    blocked = {row["name"]: row for row in payload["not_transferred_to_this_execution"]}
    assert blocked["scope A geometric certificate"]["live_applicability"] == "NOT TRANSFERRED"
    assert blocked["cosine arithmetic path"]["live_applicability"] == "NOT TRANSFERRED"
    fresh = {row["name"]: row for row in payload["fresh_certification_required"]}
    assert fresh["Python math wrapper target"]["classification"] == "NOT ESTABLISHED"
    assert fresh["selected call target"]["classification"] == "NOT ESTABLISHED"
    assert fresh["CPU feature and CPUID/XCR0 identity"]["classification"] == "NOT ESTABLISHED"
    assert fresh["returned source object"]["classification"] == "NOT ESTABLISHED"
    assert fresh["CPython executable identity"]["classification"] == "MISMATCH"
    assert fresh["libm file identity"]["classification"] == "MISMATCH"
    assert all(row["certification"] == "FRESH CERTIFICATION REQUIRED" for row in fresh.values())


def test_equal_file_hash_still_requires_fresh_certification(monkeypatch) -> None:
    root = _repository()
    binding = _fake_binding("0x7bad0")
    runtime = load_reviewed_materials(root).certificate_runtime
    dependencies = binding["canonical_payload"]["executing_dependencies"]
    dependencies["executable"]["file_sha256"] = runtime["executable_sha256"]
    dependencies["libm"]["file_sha256"] = runtime["libm_sha256"]
    monkeypatch.setattr(
        "pyfoldable.application.c2v09_runtime_applicability.collect_binding_record",
        lambda _root: binding,
    )
    payload = _payload(prepare_applicability_delta(root))
    fresh = {row["name"]: row for row in payload["fresh_certification_required"]}
    assert fresh["CPython executable identity"]["classification"] == "OBSERVED EQUAL"
    assert fresh["libm file identity"]["classification"] == "OBSERVED EQUAL"
    assert fresh["CPython executable identity"]["certification"] == "FRESH CERTIFICATION REQUIRED"
    assert fresh["Python math wrapper target"]["classification"] == "NOT ESTABLISHED"
    assert payload["status"] == "CONTRACT BLOCKED"
    assert payload["eligibility_evidence"] is False
    binding["canonical_payload"]["observations"]["mxcsr"] = "0x01fa0"
    payload = _payload(prepare_applicability_delta(root))
    fresh = {row["name"]: row for row in payload["fresh_certification_required"]}
    assert fresh["MXCSR"]["classification"] == "OBSERVED EQUAL"
    assert fresh["MXCSR"]["certification"] == "FRESH CERTIFICATION REQUIRED"


def test_changed_and_new_dependencies_require_explicit_binding(monkeypatch) -> None:
    root = _repository()
    binding = _fake_binding()
    monkeypatch.setattr(
        "pyfoldable.application.c2v09_runtime_applicability.collect_binding_record",
        lambda _root: binding,
    )
    payload = _payload(prepare_applicability_delta(root))
    changed = {row["path"]: row for row in payload["explicit_binding_required"]["changed_certificate_sources"]}
    assert "pyfoldable/application/cmm2_coupled_transient_service.py" in changed
    assert "pyfoldable/dynamics/cmm2_coupled_transient.py" in changed
    assert changed["pyfoldable/application/cmm2_coupled_transient_service.py"]["file_identity"] == "MISMATCH"
    assert "pyfoldable/core/units.py" not in changed
    new_modules = {row["role"]: row for row in payload["explicit_binding_required"]["new_modules"]}
    assert new_modules["dense"]["historical_sha256"] is None
    assert new_modules["dense"]["file_identity"] == "NO HISTORICAL RECORD"
    unbound = {row["path"]: row for row in payload["explicit_binding_required"]["unchanged_file_hash_still_unbound"]}
    assert unbound["pyfoldable/core/units.py"]["loaded_code_identity"] == "NOT ESTABLISHED"
    assert unbound["pyfoldable/core/units.py"]["operation_graph_applicability"] == "NOT ESTABLISHED"
    binding["canonical_payload"]["python_dependency_inventory"]["certificate_sources"].append(
        {
            "path": "pyfoldable/core/missing.py",
            "historical_sha256": "77" * 32,
            "current_file_sha256": None,
            "file_identity": "NOT ESTABLISHED",
            "loaded_code_identity": "NOT ESTABLISHED",
            "operation_graph_applicability": "NOT ESTABLISHED",
        }
    )
    payload = _payload(prepare_applicability_delta(root))
    changed = {row["path"] for row in payload["explicit_binding_required"]["changed_certificate_sources"]}
    unresolved = {row["path"] for row in payload["explicit_binding_required"]["unresolved_certificate_sources"]}
    assert "pyfoldable/core/missing.py" not in changed
    assert "pyfoldable/core/missing.py" in unresolved


def test_live_environment_is_blocked_without_rewriting_preserved_records() -> None:
    root = _repository()
    before_certificate = sha256_bytes((root / "docs/cmm2_c2v09_partition_runtime_certificate.md").read_bytes())
    before_partial = sha256_bytes((root / "reports/c2v09_binding_observation/partial_record.json").read_bytes())
    payload = _payload(prepare_applicability_delta(root))
    assert payload["status"] == "CONTRACT BLOCKED"
    assert payload["dispatch_separation"]["python_math_wrapper_target"] is None
    assert payload["dispatch_separation"]["selected_call_target"] is None
    assert payload["dispatch_separation"]["symbol_establishes_wrapper"] is False
    changed = {row["path"] for row in payload["explicit_binding_required"]["changed_certificate_sources"]}
    assert "pyfoldable/application/cmm2_coupled_transient_service.py" in changed
    assert "pyfoldable/dynamics/cmm2_coupled_transient.py" in changed
    roles = {row["role"]: row for row in payload["explicit_binding_required"]["new_modules"]}
    assert set(roles) == {"dense", "declaration", "eligibility", "collector", "applicability"}
    applicability = roles["applicability"]
    assert applicability["path"] == "pyfoldable/application/c2v09_runtime_applicability.py"
    assert applicability["historical_sha256"] is None
    assert applicability["current_file_sha256"] == sha256_bytes(
        (root / applicability["path"]).read_bytes()
    )
    assert applicability["file_identity"] == "NO HISTORICAL RECORD"
    assert "thread id" in " ".join(payload["observation_limitations"])
    assert sha256_bytes((root / "docs/cmm2_c2v09_partition_runtime_certificate.md").read_bytes()) == before_certificate
    assert sha256_bytes((root / "reports/c2v09_binding_observation/partial_record.json").read_bytes()) == before_partial
    record = prepare_applicability_delta(root)
    assert record["canonical_sha256"] == sha256_bytes(canonical_bytes(record["canonical_payload"]))
    assert sha256_bytes(canonical_bytes(record)) != record["canonical_sha256"]


def _assert_recorded_checkout(root: Path, checkout: str, tree_sha: str) -> None:
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


def test_absent_delta_checkout_does_not_reject_the_record(monkeypatch) -> None:
    def absent(*_args, **_kwargs) -> int:
        return 1

    def must_not_resolve(*_args, **_kwargs) -> str:
        raise AssertionError("rev-parse must not run when the commit object is absent")

    monkeypatch.setattr(subprocess, "call", absent)
    monkeypatch.setattr(subprocess, "check_output", must_not_resolve)
    _assert_recorded_checkout(_repository(), "a" * 40, "b" * 40)


def test_persisted_delta_recomputes_and_stays_blocked() -> None:
    root = _repository()
    document = json.loads((root / "reports/c2v09_runtime_applicability/delta_record.json").read_text(encoding="utf-8"))
    payload = _payload(document)
    assert document["canonical_sha256"] == sha256_bytes(canonical_bytes(payload))
    assert sha256_bytes(canonical_bytes(document)) != document["canonical_sha256"]
    assert payload["status"] == "CONTRACT BLOCKED"
    assert payload["eligibility_evidence"] is False
    assert payload["physical_qualification"] is False
    assert payload["baseline_ci_is_eligibility"] is False
    assert payload["source_callbacks"] == 0
    identities = payload["identities"]
    assert identities["technical_authority"]["head"] == TECHNICAL_HEAD
    assert identities["technical_authority"]["pinned_artifact_sha256"][CERTIFICATE_PATH] == CERTIFICATE_FILE_SHA256
    assert identities["technical_authority"]["head"] != identities["executing_implementation"]["checkout_sha"]
    assert identities["observation"]["preserved_partial_record"]["file_sha256"] == PARTIAL_RECORD_FILE_SHA256
    assert identities["observation"]["preserved_partial_record"]["canonical_sha256"] == "dff8108fe30854b8647d8e022dcf1c9521ee3a4d824e5d292ae0fd8eaa07d820"
    _assert_recorded_checkout(
        root,
        identities["executing_implementation"]["checkout_sha"],
        identities["executing_implementation"]["tree_sha"],
    )
    assert payload["dispatch_separation"]["python_math_wrapper_target"] is None
    assert payload["dispatch_separation"]["selected_call_target"] is None
    assert payload["dispatch_separation"]["symbol_establishes_wrapper"] is False
    changed = {row["path"] for row in payload["explicit_binding_required"]["changed_certificate_sources"]}
    assert "pyfoldable/application/cmm2_coupled_transient_service.py" in changed
    assert "pyfoldable/dynamics/cmm2_coupled_transient.py" in changed
    roles = {row["role"] for row in payload["explicit_binding_required"]["new_modules"]}
    assert {"dense", "declaration", "eligibility", "collector", "applicability"} <= roles
    assert payload["identities"]["observation"]["collector_thread_id"]
    assert "thread id" in " ".join(payload["observation_limitations"])


def test_delta_text_does_not_call_source_mapper_or_trajectory() -> None:
    source = _repository() / "pyfoldable/application/c2v09_runtime_applicability.py"
    text = source.read_text(encoding="utf-8")
    assert "bem" not in text
    assert "mapper" not in text
    assert "trajectory" not in text
    document = (_repository() / "docs/cmm2_c2v09_actual_runtime_applicability_delta.md").read_text(encoding="utf-8")
    assert "CONTRACT BLOCKED" in document
    assert "physical_qualification=false" in document
    assert "not eligibility evidence" in document
    assert "Baseline CI" in document
