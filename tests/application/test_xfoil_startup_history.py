"""Inert startup/history protocol checks; no genuine provider or BEM."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from pyfoldable.application import design_analysis, xfoil_startup_history as diagnostic
from pyfoldable.application.provider_design_analysis import _result
from pyfoldable.providers import xfoil
from test_provider_design_analysis import encoded, inert_cell


@pytest.fixture(autouse=True)
def no_genuine_calls(monkeypatch):
    def forbidden(*a, **k):
        pytest.fail("Genuine provider/banner/BEM prohibited in software checks")
    monkeypatch.setattr(xfoil.XfoilProvider, "generate", forbidden)
    monkeypatch.setattr(xfoil, "_discover_backend_version", forbidden)
    monkeypatch.setattr(design_analysis, "solve_bem_rotor", forbidden)


@pytest.fixture
def plan(tmp_path):
    path = tmp_path / "frozen"
    key = diagnostic.freeze_plan(path)
    return diagnostic.load_plan(path, key)


def test_nodes_and_replicate_identity_are_exact(plan):
    prior = json.loads((diagnostic.PREVIOUS / "cell-00-request-preimage.json").read_bytes())
    nodes = dict(zip(range(32, -41, -1), prior["alpha_rad"]))
    for slot, request in zip(plan.document["invocations"], plan.requests):
        degrees = list(range(13)) if slot["label"].startswith("P") else list(range(0, -13, -1))
        assert [a.hex() for a in request.alpha_rad] == [nodes[a].hex() for a in degrees]
        assert request.alpha_rad[0].hex() == nodes[0].hex()
        assert request.max_iterations == 160 and request.timeout_s == 90
        assert request.reynolds == prior["reynolds"] and request.mach == prior["mach"]
        script = xfoil._build_command_script(request, {"repanel": True}).splitlines()
        assert [int(float(l.split()[1])) for l in script if l.startswith("ALFA ")] == degrees
        assert not any(l.startswith(("INIT", "VACCEL")) for l in script)
    keys = [r.cache_key(plan.provider) for r in plan.requests]
    assert keys[0] == keys[1] != keys[2] == keys[3]
    assert len({s["invocation_sha256"] for s in plan.document["invocations"]}) == 4


@pytest.mark.parametrize("name", ["plan.json", "P-script.txt", "N-request-preimage.json"])
def test_tampered_frozen_bytes_rejected(tmp_path, name):
    path = tmp_path / "plan"
    key = diagnostic.freeze_plan(path)
    (path / name).write_bytes((path / name).read_bytes() + b" ")
    with pytest.raises(ValueError, match=name):
        diagnostic.load_plan(path, key)


def retained_launch(plan, request, capture_dir, invocation, fault=None):
    used = replace(request, scenario_id="INERT-foreign-request") if fault == "foreign" else request
    record = inert_cell(used, plan.provider)
    data = json.loads(record.result_json)
    files = dict(record.capture_files)
    receipt = json.loads(files["capture.json"])
    for phase in ("prelaunch", "postlaunch"):
        receipt["executable_identity"][phase]["sha256"] = "f" * 64 if fault == "executable" else plan.executable_sha256
    if fault == "incomplete":
        files["polar.bin"] = b"\n".join(files["polar.bin"].splitlines()[:-1]) + b"\n"
        rows, _ = xfoil._parse_polar(files["polar.bin"].decode())
        points, warnings = xfoil._reconcile_rows(used, rows)
        data.update(points=[p.__dict__ for p in points], complete=False, warnings=list(warnings))
        data["metadata"]["capture_evidence_ready"] = False
        receipt.update(points=[{k: v for k, v in p.__dict__.items() if k not in {"confidence", "iterations"}} for p in points],
                       evidence_ready=False, solver_output_usable=False, polar_file=xfoil._byte_receipt(files["polar.bin"], partial=False))
    if fault == "malformed":
        files["polar.bin"] = b"malformed INERT output\n"
    files["capture.json"] = encoded(receipt)
    capture_dir.mkdir()
    for name, raw in files.items():
        (capture_dir / name).write_bytes(raw)
    event = {"event": "subprocess.Popen_before_spawn", "invocation_sha256": invocation["invocation_sha256"],
             "request_sha256": request.cache_key(plan.provider), "cwd": str(capture_dir / "INERT-NO-PROCESS"),
             "argv": [receipt["executable_identity"]["prelaunch"]["path"]],
             "airfoil_input_sha256": receipt["airfoil_input_sha256"],
             "executable_sha256": plan.executable_sha256, "only_expected_airfoil_present": True}
    if fault == "replay":
        event["invocation_sha256"] = plan.document["invocations"][0]["invocation_sha256"]
    if fault == "event_airfoil":
        event["airfoil_input_sha256"] = "f" * 64
    if fault == "event_argv":
        event["argv"].append("unexpected-command-line-airfoil.dat")
    if fault == "event_bool":
        event["only_expected_airfoil_present"] = 1
    if fault != "no_launch":
        (capture_dir.parent / "subprocess-prelaunch.json").write_bytes(encoded(event))
    return _result(data)


def test_four_independent_complete_records_with_two_scientific_keys(plan, tmp_path):
    called = []
    output = tmp_path / "run"
    output.mkdir()
    def launch(request, *, capture_dir, invocation):
        if called:
            assert (output / called[-1] / "outcome.json").is_file()
        called.append(invocation["label"])
        return retained_launch(plan, request, capture_dir, invocation)
    result = diagnostic.run_records(plan, output, launch, lambda: None)
    assert called == ["P1", "P2", "N1", "N2"]
    assert result["status"] == "DIAGNOSTIC_COMPLETED" and result["bem_calls"] == 0
    assert result["provider_api_attempts"] == 4 and result["retries"] == 0
    assert all(x["status"] == "COMPLETE_CAPTURED" for x in result["invocations"])
    with pytest.raises(FileExistsError):
        diagnostic.run_records(plan, output, launch, lambda: None)
    assert len(called) == 4


@pytest.mark.parametrize("fault", ["incomplete", "timeout", "foreign", "malformed", "executable", "persistence", "replay", "no_launch",
                                 "event_airfoil", "event_argv", "event_bool"])
def test_first_problem_stops_even_predeclared_replicates(plan, tmp_path, monkeypatch, fault):
    called = []
    output = tmp_path / "run"
    output.mkdir()
    def launch(request, *, capture_dir, invocation):
        called.append(invocation["label"])
        if len(called) == 2 and fault == "timeout":
            raise xfoil.PolarProviderTimeoutError("INERT timeout")
        return retained_launch(plan, request, capture_dir, invocation, fault if len(called) == 2 else None)
    if fault == "persistence":
        original = diagnostic.infra._sync_capture
        def fail(directory):
            if directory.parent.name == "P2":
                raise OSError("INERT capture persistence failure")
            original(directory)
        monkeypatch.setattr(diagnostic.infra, "_sync_capture", fail)
    result = diagnostic.run_records(plan, output, launch, lambda: None)
    assert called == ["P1", "P2"]
    assert [x["attempts"] for x in result["invocations"]] == [1, 1, 0, 0]
    assert [x["status"] for x in result["invocations"]] == ["COMPLETE_CAPTURED", "FAILED", "NOT_LAUNCHED", "NOT_LAUNCHED"]
    assert result["bem_calls"] == 0 and not (output / "N1").exists()
    if fault == "incomplete":
        assert result["invocations"][1]["usable_points"] == 12
        assert result["invocations"][1]["unavailable_angles_deg"] == [12]


def test_failed_first_invocation_does_not_turn_replicate_into_retry(plan, tmp_path):
    output = tmp_path / "run"
    output.mkdir()
    called = []
    def launch(request, *, capture_dir, invocation):
        called.append(invocation["label"])
        return retained_launch(plan, request, capture_dir, invocation, "incomplete")
    result = diagnostic.run_records(plan, output, launch, lambda: None)
    assert called == ["P1"]
    assert [s["status"] for s in result["invocations"]] == ["FAILED"] + ["NOT_LAUNCHED"] * 3


def test_prelaunch_failure_has_zero_calls(plan, tmp_path):
    output = tmp_path / "run"
    output.mkdir()
    def fail():
        raise ValueError("INERT changed executable")
    result = diagnostic.run_records(plan, output, lambda *a, **k: pytest.fail("Launch forbidden"), fail)
    assert result["provider_api_attempts"] == 0
    assert [x["status"] for x in result["invocations"]] == ["NOT_LAUNCHED"] * 4


def test_silently_refused_observer_installation_blocks_before_provider(plan, monkeypatch, tmp_path):
    provider = SimpleNamespace(executable=str(tmp_path / "INERT"), generate=lambda *a, **k: pytest.fail("Must not launch"))
    observer = diagnostic.FreshProcessLaunch(provider, plan.executable_sha256, plan.provider)
    monkeypatch.setattr(diagnostic.sys, "addaudithook", lambda hook: None)
    with pytest.raises(RuntimeError, match="observer"):
        observer.install()
    with pytest.raises(RuntimeError, match="observer"):
        observer(plan.requests[0], capture_dir=tmp_path / "capture", invocation=plan.document["invocations"][0])


def test_observer_handshake_requires_its_own_token(plan, tmp_path):
    observer = diagnostic.FreshProcessLaunch(SimpleNamespace(executable=str(tmp_path / "INERT")), plan.executable_sha256, plan.provider)
    observer.audit(diagnostic.OBSERVER_EVENT, (object(),))
    assert not observer.verified
    observer.audit(diagnostic.OBSERVER_EVENT, (observer.token,))
    assert observer.verified


@pytest.mark.parametrize("extra", [False, True])
def test_fresh_directory_guard_and_double_spawn_ceiling(plan, tmp_path, extra):
    binary = tmp_path / "inert-binary"
    binary.write_bytes(b"INERT")
    request = plan.requests[0]
    slot = plan.document["invocations"][0]
    cwd = tmp_path / "fresh"
    cwd.mkdir()
    xfoil._write_airfoil(cwd / "airfoil.dat", request)
    if extra:
        (cwd / "xfoil.def").write_text("UNINTENDED INERT DEFAULTS")
    directory = tmp_path / "P1"
    directory.mkdir()
    observer = diagnostic.FreshProcessLaunch(SimpleNamespace(executable=str(binary)), hashlib.sha256(b"INERT").hexdigest(), plan.provider)
    observer.active = (request, directory / "capture", slot)
    if extra:
        with pytest.raises(ValueError, match="directory"):
            observer.audit("subprocess.Popen", (str(binary), [str(binary)], str(cwd), None))
        assert not (directory / "subprocess-prelaunch.json").exists()
    else:
        observer.audit("subprocess.Popen", (str(binary), [str(binary)], str(cwd), None))
        assert json.loads((directory / "subprocess-prelaunch.json").read_bytes())["only_expected_airfoil_present"]
        with pytest.raises(ValueError, match="reused|one subprocess"):
            observer.audit("subprocess.Popen", (str(binary), [str(binary)], str(cwd), None))
