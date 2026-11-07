"""One-degree experiment controls; the only launch seam writes inert bytes."""

from dataclasses import replace
import json
import math
from pathlib import Path

import pytest

from pyfoldable.application import design_analysis, xfoil_one_degree_continuation as experiment
from pyfoldable.application.provider_design_analysis import _result
from pyfoldable.providers import xfoil
from test_provider_design_analysis import encoded, inert_cell


@pytest.fixture(autouse=True)
def block_real_calls(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Unexpected genuine provider, banner or BEM call")

    monkeypatch.setattr(xfoil.XfoilProvider, "generate", forbidden)
    monkeypatch.setattr(xfoil, "_discover_backend_version", forbidden)
    monkeypatch.setattr(design_analysis, "solve_bem_rotor", forbidden)


@pytest.fixture
def frozen(tmp_path):
    directory = tmp_path / "plan"
    key = experiment.freeze_plan(directory)
    return directory, key, experiment.load_plan(directory, key)


def test_frozen_requests_interleave_without_recomputing_old_nodes(frozen):
    directory, _, plan = frozen
    previous = Path(experiment.PREVIOUS_PLAN)
    old = json.loads((previous / "request-preimage.json").read_bytes())
    prior_plan = json.loads((previous / "proposal.json").read_bytes())
    expected_states = [(p["mach"], p["reynolds"]) for p in prior_plan["future_family_plan"]["requests"]]
    assert [(r.mach, r.reynolds) for r in plan.requests] == expected_states == sorted(expected_states)
    for index, request in enumerate(plan.requests):
        new = json.loads((directory / f"cell-{index:02d}-request-preimage.json").read_bytes())
        assert [a.hex() for a in new["alpha_rad"][::2]] == [a.hex() for a in old["alpha_rad"]]
        assert new["alpha_rad"][1::2] == [math.radians(a) for a in range(31, -40, -2)]
        assert {k: v for k, v in new.items() if k not in {"alpha_rad", "mach", "reynolds", "scenario_id"}} == {
            k: v for k, v in old.items() if k not in {"alpha_rad", "mach", "reynolds", "scenario_id"}
        }
        script = (directory / f"cell-{index:02d}-script.txt").read_text().splitlines()
        assert [int(float(line.split()[1])) for line in script if line.startswith("ALFA ")] == list(range(32, -41, -1))
        assert "ITER 160" in script and script.count("PANE") == 1
        assert not any(line.startswith(("INIT", "VACCEL")) for line in script)
        assert request.timeout_s == 90.0


@pytest.mark.parametrize("name", ["plan.json", "cell-01-script.txt", "cell-03-request-preimage.json"])
def test_frozen_plan_rejects_changed_bytes(frozen, name):
    directory, key, _ = frozen
    path = directory / name
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match=name):
        experiment.load_plan(directory, key)


def fake_launch(request, provider, directory, pinned, *, missing=False, foreign=False, wrong_binary=False):
    # An explicitly inert result and inert receipt; the path never names a process.
    used = replace(request, scenario_id="INERT-foreign") if foreign else request
    cell = inert_cell(used, provider)
    files = dict(cell.capture_files)
    result = json.loads(cell.result_json)
    receipt = json.loads(files["capture.json"])
    for stage in ("prelaunch", "postlaunch"):
        receipt["executable_identity"][stage]["sha256"] = "a" * 64 if wrong_binary else pinned
    if missing:
        files["polar.bin"] = b"\n".join(line for line in files["polar.bin"].split(b"\n")
                                         if not line.startswith(b"-38.00000000 "))
        parsed, _ = xfoil._parse_polar(files["polar.bin"].decode())
        points, warnings = xfoil._reconcile_rows(used, parsed)
        result.update(complete=False, points=[p.__dict__ for p in points], warnings=list(warnings))
        result["metadata"]["capture_evidence_ready"] = False
        receipt.update(polar_file=xfoil._byte_receipt(files["polar.bin"], partial=False),
                       points=[{k: v for k, v in p.__dict__.items() if k not in ("confidence", "iterations")} for p in points],
                       evidence_ready=False, solver_output_usable=False)
    files["capture.json"] = encoded(receipt)
    directory.mkdir()
    for name, data in files.items():
        (directory / name).write_bytes(data)
    return _result(result)


def test_all_complete_calls_once_in_order_and_never_a_fifth(frozen, tmp_path):
    _, _, plan = frozen
    called = []
    output = tmp_path / "run"
    output.mkdir()

    def launch(request, *, capture_dir):
        index = len(called)
        if index:
            assert json.loads((output / f"cell-{index - 1:02d}" / "outcome.json").read_bytes())["status"] == "COMPLETE_CAPTURED"
        called.append(request.cache_key(plan.provider))
        return fake_launch(request, plan.provider, capture_dir, plan.executable_sha256)

    outcome = experiment.run_cells(plan, output, launch, lambda: None)
    assert called == [r.cache_key(plan.provider) for r in plan.requests]
    assert outcome["provider_api_attempts"] == 4 and outcome["bem_calls"] == 0
    assert outcome["status"] == "COMPLETE_CAPTURED_FAMILY_PENDING_REVIEW"
    assert outcome["physical_qualification"] is False
    assert [c["status"] for c in outcome["cells"]] == ["COMPLETE_CAPTURED"] * 4


@pytest.mark.parametrize("fault,stage", [
    ("missing", "completeness"), ("foreign", "attribution"), ("wrong_binary", "attribution"),
    ("timeout", "provider_call"), ("persistence", "capture_persistence"),
])
def test_stops_before_next_cell_after_second_cell_failure(frozen, tmp_path, monkeypatch, fault, stage):
    _, _, plan = frozen
    called = []
    output = tmp_path / "run"
    output.mkdir()

    def launch(request, *, capture_dir):
        called.append(request.cache_key(plan.provider))
        if len(called) == 2 and fault == "timeout":
            raise xfoil.PolarProviderTimeoutError("INERT timeout; no process")
        return fake_launch(request, plan.provider, capture_dir, plan.executable_sha256,
                           **({fault: True} if len(called) == 2 and fault in {"missing", "foreign", "wrong_binary"} else {}))

    if fault == "persistence":
        sync = experiment._sync_capture

        def failed_sync(directory):
            if directory.parent.name == "cell-01":
                raise OSError("INERT capture persistence failure")
            sync(directory)

        monkeypatch.setattr(experiment, "_sync_capture", failed_sync)

    outcome = experiment.run_cells(plan, output, launch, lambda: None)
    assert called == [r.cache_key(plan.provider) for r in plan.requests[:2]]
    assert outcome["bem_calls"] == 0 and outcome["provider_api_attempts"] == 2
    first, failed, *unlaunched = outcome["cells"]
    assert first["status"] == "COMPLETE_CAPTURED"
    assert failed["failure_stage"] == stage and failed["status"] == "FAILED"
    assert [c["attempts"] for c in outcome["cells"]] == [1, 1, 0, 0]
    assert [c["status"] for c in unlaunched] == ["NOT_LAUNCHED"] * 2
    assert not (output / "cell-02").exists()
    if fault == "missing":
        assert failed["usable_points"] == 72 and failed["unavailable_angles_deg"] == [-38]
    if fault != "timeout":
        assert (output / "cell-01" / "result.json").is_file()
        assert (output / "cell-01" / "capture" / "polar.bin").is_file()
