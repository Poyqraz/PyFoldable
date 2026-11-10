"""Prelaunch checks; fake calls only, no XFOIL constructor or solver."""
import json
from types import SimpleNamespace

from examples import research_reference_data as ref
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
