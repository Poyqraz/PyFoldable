"""Zero-source-call binding collector. Doubles do not become live matches."""

from __future__ import annotations

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


def _repository() -> Path:
    return Path(__file__).resolve().parents[2]


def test_collector_separates_capsules_dependencies_and_graph() -> None:
    record = collect_binding_record(_repository())
    assert record["historical_capsules"]["runtime_binding_sha256"]
    assert "file_sha256" not in record["historical_capsules"]
    assert record["executing_dependencies"]["libm"]["file_sha256"]
    assert record["reviewed_conditional_graph"]["cos_body_vaddr"] == "0x7bad0"
    assert record["checkout_sha"]
    assert record["tree_sha"]
    assert "file hashes do not establish loaded instructions" in record["limitations"]
    assert "CPU feature labels do not establish dispatch" in record["limitations"]
    assert record["source_callbacks"] == 0


def test_unreadable_instruction_range_is_not_established(monkeypatch) -> None:
    monkeypatch.setattr(
        "pyfoldable.application.c2v09_binding_collector.read_loaded_vaddr",
        lambda *_args, **_kwargs: None,
    )
    record = collect_binding_record(_repository())
    assert record["observations"]["loaded_cos_body"] == "NOT ESTABLISHED"
    assert "loaded certificate cos body" not in record["classifications"]["matches"]
    assert "loaded certificate cos body" in record["classifications"]["not_established"]


def test_different_loaded_bytes_are_a_mismatch(monkeypatch) -> None:
    monkeypatch.setattr(
        "pyfoldable.application.c2v09_binding_collector.read_loaded_vaddr",
        lambda *_args, **_kwargs: b"\x00",
    )
    record = collect_binding_record(_repository())
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
    record = collect_binding_record(_repository())
    assert record["observations"]["cpu_feature_flags"] == ["avx", "fma"]
    assert record["observations"]["resolved_cos_vaddr"] is None
    assert record["observations"]["loaded_dispatch_inferred_from_cpu"] is False
    assert "resolved cos dispatch" in record["classifications"]["not_established"]


def test_collector_does_not_call_source_mapper_or_trajectory() -> None:
    source = Path(__file__).resolve().parents[2] / "pyfoldable" / "application" / "c2v09_binding_collector.py"
    text = source.read_text(encoding="utf-8")
    assert "bem" not in text
    assert "mapper" not in text
    assert "trajectory" not in text
    record = collect_binding_record(_repository())
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
