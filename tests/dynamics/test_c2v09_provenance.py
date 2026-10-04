"""Checkout provenance is not inferred from a pull-request merge commit."""

from __future__ import annotations

import importlib.util
import json
import os
import platform
from pathlib import Path


def _load_evidence():
    path = Path(__file__).resolve().parents[1] / "c2v09_evidence.py"
    spec = importlib.util.spec_from_file_location("c2v09_evidence", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_evidence = _load_evidence()
FULL_MANIFEST_ID = _evidence.FULL_MANIFEST_ID
FULL_MANIFEST_SHA256 = _evidence.FULL_MANIFEST_SHA256
ROOT = _evidence.ROOT
assert_event_provenance = _evidence.assert_event_provenance
canonical = _evidence.canonical
checkout_provenance = _evidence.checkout_provenance
load_full_manifest = _evidence.load_full_manifest
sha256_text = _evidence.sha256_text
source_event_provenance = _evidence.source_event_provenance


def test_local_event_provenance_stays_null() -> None:
    record = source_event_provenance(
        {"GITHUB_SHA": "d" * 40, "GITHUB_EVENT_NAME": ""},
        json.dumps({"pull_request": {"head": {"sha": "e" * 40}}}),
    )
    assert record == {"pr_source_sha": None, "push_source_sha": None}


def test_push_event_records_only_the_push_sha() -> None:
    record = source_event_provenance(
        {"GITHUB_EVENT_NAME": "push", "GITHUB_SHA": "c" * 40},
        None,
    )
    assert record == {"pr_source_sha": None, "push_source_sha": "c" * 40}


def test_pull_request_merge_checkout_uses_the_payload_head() -> None:
    source = "a" * 40
    merge_checkout = "b" * 40
    payload = json.dumps({"pull_request": {"head": {"sha": source}}})
    record = checkout_provenance(
        ROOT,
        {"GITHUB_EVENT_NAME": "pull_request", "GITHUB_SHA": merge_checkout},
        payload,
    )
    assert record["pr_source_sha"] == source
    assert record["pr_source_sha"] != merge_checkout
    assert record["pr_source_sha"] != record["evidence_checkout_sha"]
    assert record["push_source_sha"] is None
    assert record["python_version"] == platform.python_version()
    assert record["numpy_version"]
    assert record["scipy_version"]
    assert isinstance(record["dirty_paths"], list)


def test_pull_request_without_a_payload_does_not_reuse_github_sha() -> None:
    record = source_event_provenance(
        {"GITHUB_EVENT_NAME": "pull_request", "GITHUB_SHA": "b" * 40},
        None,
    )
    assert record == {"pr_source_sha": None, "push_source_sha": None}


def test_checkout_provenance_reads_the_pull_request_payload(tmp_path, monkeypatch) -> None:
    source = "a" * 40
    merge_checkout = "b" * 40
    payload = tmp_path / "event.json"
    payload.write_text(json.dumps({"pull_request": {"head": {"sha": source}}}), encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("GITHUB_SHA", merge_checkout)
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(payload))
    record = checkout_provenance(ROOT)
    assert record["pr_source_sha"] == source
    assert record["push_source_sha"] is None
    assert record["pr_source_sha"] != merge_checkout
    assert_event_provenance(record, os.environ)


def test_live_rule_keeps_a_pull_request_head_distinct_from_a_merge_checkout() -> None:
    source = "a" * 40
    merge_checkout = "b" * 40
    assert_event_provenance(
        {
            "pr_source_sha": source,
            "push_source_sha": None,
            "evidence_checkout_sha": merge_checkout,
        },
        {"GITHUB_EVENT_NAME": "pull_request", "GITHUB_SHA": merge_checkout},
    )


def test_live_rule_allows_a_push_sha_to_equal_the_checkout() -> None:
    sha = "c" * 40
    assert_event_provenance(
        {
            "pr_source_sha": None,
            "push_source_sha": sha,
            "evidence_checkout_sha": sha,
        },
        {"GITHUB_EVENT_NAME": "push", "GITHUB_SHA": sha},
    )


def test_partial_mechanism_subset_is_not_the_full_manifest() -> None:
    subset = {
        "id": FULL_MANIFEST_ID,
        "shared_mechanism": {
            "mass_kg": 0.02,
            "hinge_radius_m": 0.08,
            "cg_distance_m": 0.03,
            "hinge_inertia_kg_m2": 2.0e-5,
            "base_inertia_kg_m2": 1.0e-4,
            "spring_stiffness_nm_rad": 0.01,
            "rest_angle_rad": -0.2,
            "viscous_damping_nm_s_rad": 0.002,
            "coulomb_torque_nm": 0.001,
            "transition_velocity_rad_s": 0.05,
            "lower_stop_rad": -1.2,
            "upper_stop_rad": 0.2,
        },
    }
    subset_digest = sha256_text(canonical(subset))
    assert subset_digest == "ca64ca282261702b81b6b2e5730ebb95d7db9ea39041d8d83a3d948223195090"
    assert subset_digest != FULL_MANIFEST_SHA256
    manifest = load_full_manifest()
    assert manifest["manifest_id"] == FULL_MANIFEST_ID
    assert len(manifest["cases"]) == 10
    assert len(manifest["c2v09_candidates"]) == 28
    assert sha256_text(canonical(manifest)) == FULL_MANIFEST_SHA256
