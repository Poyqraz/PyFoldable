"""Actual-runtime applicability delta for the preserved C2V-09 certificate.

This inspection reads the executing process and classifies transfer. It does
not rewrite the historical certificate or the preserved partial observation,
and it does not establish live eligibility.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Mapping

from pyfoldable.application.c2v09_binding_collector import collect_binding_record
from pyfoldable.application.c2v09_ordered_declaration import (
    CANDIDATE28_DISPOSITION,
    CANDIDATE29_DISPOSITION,
    CONNECTION_RECORD_SHA256,
    COSINE_RECORD_SHA256,
    PRIOR_GEOMETRIC_RECORD_SHA256,
    RUNTIME_BINDING_SHA256,
    TECHNICAL_HEAD,
    canonical_bytes,
    load_reviewed_materials,
    sha256_bytes,
)


CERTIFICATE_PATH = "docs/cmm2_c2v09_partition_runtime_certificate.md"
CERTIFICATE_FILE_SHA256 = "d0c9196a747ad2e49f94bb264e33bca95eec0a20e1bc900dc1bd5442d0ef5b35"
PARTIAL_RECORD_PATH = "reports/c2v09_binding_observation/partial_record.json"
PARTIAL_RECORD_FILE_SHA256 = "11808a792b95cc3dec44e3d906cecba37ba8650336237438df81d60454992d4f"
PARTIAL_RECORD_CANONICAL_SHA256 = "dff8108fe30854b8647d8e022dcf1c9521ee3a4d824e5d292ae0fd8eaa07d820"
CONTRACT_BLOCKED = "CONTRACT BLOCKED"
FRESH = "FRESH CERTIFICATION REQUIRED"
DIGEST_SCOPE = (
    "SHA-256 of the section 7.3 canonical bytes of canonical_payload only. "
    "canonical_sha256 and digest_scope are outside that payload."
)


def _git_text(root: Path, *args: str) -> str | None:
    try:
        return subprocess.check_output(["git", *args], cwd=root, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _read_preserved(root: Path, relative: str, expected: str) -> bytes:
    data = (root / relative).read_bytes()
    if sha256_bytes(data) != expected:
        raise RuntimeError(f"Preserved artifact changed: {relative}")
    return data


def _file_classification(observed: object, expected: str) -> str:
    if not isinstance(observed, str) or not observed:
        return "NOT ESTABLISHED"
    if observed == expected:
        return "OBSERVED EQUAL"
    return "MISMATCH"


def _fresh(name: str, observed: object, certificate_value: object, classification: str) -> dict[str, object]:
    return {
        "name": name,
        "observed": observed,
        "certificate_value": certificate_value,
        "classification": classification,
        "certification": FRESH,
    }


def prepare_applicability_delta(root: Path, *, caller_claims: Mapping[str, object] | None = None) -> dict[str, object]:
    """Classify this execution without a motor, load, or integration call."""
    _read_preserved(root, CERTIFICATE_PATH, CERTIFICATE_FILE_SHA256)
    partial_bytes = _read_preserved(root, PARTIAL_RECORD_PATH, PARTIAL_RECORD_FILE_SHA256)
    preserved = json.loads(partial_bytes)
    if preserved.get("canonical_sha256") != PARTIAL_RECORD_CANONICAL_SHA256:
        raise RuntimeError("Preserved partial observation digest changed.")
    preserved_payload = preserved["canonical_payload"]
    materials = load_reviewed_materials(root)
    binding = collect_binding_record(root)
    collected = binding["canonical_payload"]
    runtime = materials.certificate_runtime
    dependencies = collected["executing_dependencies"]
    observations = collected["observations"]
    symbol = observations.get("resolved_libm_cos_symbol_vaddr")
    claims = dict(caller_claims or {})

    changed = []
    unchanged = []
    for row in collected["python_dependency_inventory"]["certificate_sources"]:
        if row["file_identity"] == "MISMATCH":
            changed.append(dict(row))
        elif row["file_identity"] == "MATCH":
            unchanged.append(dict(row))
        else:
            changed.append(dict(row))
    new_modules = [dict(row) for row in collected["python_dependency_inventory"]["modules_without_historical_record"]]

    executable = dependencies["executable"]["file_sha256"]
    libm = dependencies["libm"]["file_sha256"]
    libc = dependencies["libc"]["file_sha256"]
    loader = dependencies["loader"]["file_sha256"]
    fresh = [
        _fresh(
            "CPython executable identity",
            executable,
            runtime["executable_sha256"],
            _file_classification(executable, runtime["executable_sha256"]),
        ),
        _fresh(
            "libm file identity",
            libm,
            runtime["libm_sha256"],
            _file_classification(libm, runtime["libm_sha256"]),
        ),
        _fresh(
            "libc file identity",
            libc,
            runtime["libc_sha256"],
            _file_classification(libc, runtime["libc_sha256"]),
        ),
        _fresh(
            "loader file identity",
            loader,
            runtime["loader_sha256"],
            _file_classification(loader, runtime["loader_sha256"]),
        ),
        _fresh("Python math wrapper target", None, runtime["cos_vaddr"], "NOT ESTABLISHED"),
        _fresh("selected call target", None, runtime["cos_vaddr"], "NOT ESTABLISHED"),
        _fresh(
            "CPU feature and CPUID/XCR0 identity",
            observations.get("cpu_feature_flags"),
            "certificate CPUID/XCR0 binding",
            "NOT ESTABLISHED",
        ),
        _fresh("returned source object", None, "valid returned source object", "NOT ESTABLISHED"),
        _fresh("operation-graph applicability", None, "certified represented operation graph", "NOT ESTABLISHED"),
        _fresh(
            "fegetround",
            observations.get("fegetround"),
            runtime["fegetround"],
            _file_classification(observations.get("fegetround"), runtime["fegetround"]),
        ),
        _fresh(
            "MXCSR",
            observations.get("mxcsr"),
            runtime["mxcsr_hex"],
            _file_classification(str(observations.get("mxcsr")).lower(), str(runtime["mxcsr_hex"]).lower())
            if observations.get("mxcsr")
            else "NOT ESTABLISHED",
        ),
    ]
    payload = {
        "status": CONTRACT_BLOCKED,
        "eligibility_evidence": False,
        "physical_qualification": False,
        "baseline_ci_is_eligibility": False,
        "outcome": "actual-runtime applicability delta",
        "identities": {
            "technical_authority": {
                "role": "technical authority",
                "head": TECHNICAL_HEAD,
            },
            "executing_implementation": {
                "role": "executing implementation",
                "checkout_sha": _git_text(root, "rev-parse", "HEAD"),
                "tree_sha": _git_text(root, "rev-parse", "HEAD^{tree}"),
            },
            "observation": {
                "role": "observation",
                "collector_canonical_sha256": binding["canonical_sha256"],
                "collector_checkout_sha": collected["checkout_sha"],
                "collector_tree_sha": collected["tree_sha"],
                "runtime": collected["runtime"],
                "preserved_partial_record": {
                    "path": PARTIAL_RECORD_PATH,
                    "file_sha256": PARTIAL_RECORD_FILE_SHA256,
                    "canonical_sha256": preserved["canonical_sha256"],
                    "checkout_sha": preserved_payload["checkout_sha"],
                    "tree_sha": preserved_payload["tree_sha"],
                },
            },
        },
        "dispatch_separation": {
            "resolved_libm_cos_symbol_vaddr": symbol,
            "python_math_wrapper_target": None,
            "selected_call_target": None,
            "symbol_matches_certificate_vaddr": symbol == runtime["cos_vaddr"],
            "symbol_establishes_wrapper": False,
            "symbol_establishes_selected_call": False,
        },
        "transferred_historical_results": [
            {"name": "original v1 partition", "result": "FAIL", "live_applicability": "TRANSFERRED AS HISTORICAL RESULT"},
            {"name": "historical v2", "result": "BLOCKED", "live_applicability": "TRANSFERRED AS HISTORICAL RESULT"},
            {
                "name": "candidate28",
                "result": CANDIDATE28_DISPOSITION,
                "live_applicability": "TRANSFERRED AS HISTORICAL RESULT",
            },
            {
                "name": "candidate29",
                "result": CANDIDATE29_DISPOSITION,
                "live_applicability": "TRANSFERRED AS HISTORICAL RESULT",
            },
            {
                "name": "runtime binding record",
                "sha256": RUNTIME_BINDING_SHA256,
                "live_applicability": "HISTORICAL IDENTITY ONLY",
            },
            {
                "name": "cosine record",
                "sha256": COSINE_RECORD_SHA256,
                "live_applicability": "HISTORICAL IDENTITY ONLY",
            },
            {
                "name": "prior geometric record",
                "sha256": PRIOR_GEOMETRIC_RECORD_SHA256,
                "live_applicability": "HISTORICAL IDENTITY ONLY",
            },
            {
                "name": "connection record",
                "sha256": CONNECTION_RECORD_SHA256,
                "live_applicability": "HISTORICAL IDENTITY ONLY",
            },
        ],
        "not_transferred_to_this_execution": [
            {
                "name": "scope A geometric certificate",
                "live_applicability": "NOT TRANSFERRED",
                "reason": "the archived geometric result remains conditional on its original runtime and a valid returned source object",
            },
            {
                "name": "cosine arithmetic path",
                "live_applicability": "NOT TRANSFERRED",
                "reason": "a resolved libm symbol is not the Python wrapper or the selected call target",
            },
        ],
        "explicit_binding_required": {
            "changed_certificate_sources": changed,
            "new_modules": new_modules,
            "unchanged_file_hash_still_unbound": unchanged,
        },
        "fresh_certification_required": fresh,
        "byte_comparisons_are_not_certification": {
            "loaded_cos_body": observations.get("loaded_cos_body"),
            "reason": "a byte comparison at a historical virtual address does not certify this runtime",
        },
        "caller_claims": claims,
        "source_callbacks": 0,
    }
    return {
        "digest_scope": DIGEST_SCOPE,
        "canonical_payload": payload,
        "canonical_sha256": sha256_bytes(canonical_bytes(payload)),
    }
