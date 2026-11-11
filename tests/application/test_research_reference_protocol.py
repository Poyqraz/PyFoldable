"""Prelaunch checks; fake calls only, no XFOIL constructor or solver."""
import json
from types import SimpleNamespace

from research_reference_loader import ref
from pyfoldable.core.providers import ProviderIdentity


def test_frozen_cells_and_conditional_guard():
    plan, files = ref.make_plan()
    assert len(files) == 24
    assert len(plan["conditional_scan_not_execution"]) == 40
    for profile in ref.PROFILES:
        requests = ref.request_grid(profile, plan["declaration"])
        assert [(q.mach, q.reynolds) for q in requests] == [
            (m, r) for m in (.1, .31) for r in (165000, 245000, 330000)]
        for n, q in enumerate(requests):
            script = files[f"{profile}-{n:02d}.script.txt"].splitlines()
            assert len([line for line in script if line.startswith(b"ALFA ")]) == 8
            assert b"ITER 160" in script and b"PANE" in script and b"INIT" not in script
            assert q.timeout_s == 30


def test_stop_before_next_call_and_retain_failure(tmp_path):
    plan, _ = ref.make_plan()
    called = []

    def generate(request, *, capture_dir):
        called.append(request)
        capture_dir.mkdir()
        (capture_dir / "inert-raw.bin").write_bytes(b"INERT FAILURE")
        raise RuntimeError("inert stop witness")

    provider = SimpleNamespace(identity=ProviderIdentity(**plan["declaration"]["provider"]), generate=generate)
    rows = ref.capture(ref.PROFILES[0], tmp_path, plan, provider)
    assert len(called) == 1
    assert called[0].cache_key(provider.identity) == rows[0]["request_sha256"]
    assert [r["status"] for r in rows] == ["STOPPED"] + ["NOT_LAUNCHED"] * 5
    assert json.loads((tmp_path / "outcome.json").read_bytes())["provider_calls"] == 1
    assert (tmp_path / "capture-00/inert-raw.bin").read_bytes() == b"INERT FAILURE"


def test_phase_two_rejects_empty_or_unrelated_first_result(tmp_path):
    import pytest
    from dataclasses import replace
    from pyfoldable.application import research_design as research
    from pyfoldable.application import provider_design_analysis as managed
    plan, _ = ref.make_plan()
    ref.write(tmp_path / "plan.json", plan)
    first = tmp_path / "first-application-result.json"
    first.write_text("{}")
    with pytest.raises(ValueError):
        ref.require_first_application(tmp_path, plan)
    active = research.build_research_design(ref.ROOT, replace(research.defaults(ref.ROOT), profile="NACA0012"))
    failed = research.run_research(active, None, managed.ManagedProviderRepository(), None)
    first.write_text(research.saved_result_json(failed))
    with pytest.raises(ValueError, match="not the frozen"):
        ref.require_first_application(tmp_path, plan)
