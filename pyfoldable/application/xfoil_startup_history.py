"""Finite operator-only startup/history diagnostic; never a BEM family builder."""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import sys

from pyfoldable.providers import xfoil
from . import xfoil_one_degree_continuation as infra


ROOT = Path(__file__).resolve().parents[2]
PREVIOUS = ROOT / "docs/decisions/xfoil-one-degree-continuation-v1"
PREVIOUS_PLAN_SHA = "0e082cea4e485f664d259f669cd75f5f17615550553d984de4b41a854569d342"
PREVIOUS_ARCHIVE_SHA = "7cc5d67d9f265e10d27e203fb630e99c56ff4eb9d231b959fde5664fd1ab75e1"
EXPERIMENT = "xfoil_naca0012_startup_history_repeatability_v1"
SCENARIO = "baseline_250mm_7100rpm_iter160_startup_history_v1"
LABELS = ("P1", "P2", "N1", "N2")
OBSERVER_EVENT = "pyfoldable.xfoil_startup_history.observer"


def _make_plan() -> infra.FrozenPlan:
    previous = infra.load_plan(PREVIOUS, PREVIOUS_PLAN_SHA)
    seed = previous.requests[0]
    retained = dict(zip(previous.document["alpha_degrees"], seed.alpha_rad))
    files, requests, slots = {}, [], []
    for index, label in enumerate(LABELS):
        direction = label[0]
        degrees = tuple(range(13)) if direction == "P" else tuple(range(0, -13, -1))
        request = replace(seed, alpha_rad=tuple(retained[a] for a in degrees), scenario_id=SCENARIO)
        requests.append(request)
        preimage = xfoil._request_preimage(request, previous.provider)
        script = xfoil._build_command_script(request, xfoil._validated_options(request.options)).encode()
        files[f"{direction}-request-preimage.json"] = preimage
        files[f"{direction}-script.txt"] = script
        attribution = {"experiment_id": EXPERIMENT, "index": index, "label": label,
                       "request_sha256": request.cache_key(previous.provider)}
        slots.append({**attribution, "invocation_sha256": infra._sha(infra._json(attribution)),
                      "alpha_degrees": degrees, "request_file": f"{direction}-request-preimage.json",
                      "script_file": f"{direction}-script.txt", "script_sha256": infra._sha(script)})
    prior = previous.document
    plan = {
        "schema_version": 1, "experiment_id": EXPERIMENT, "scenario_id": SCENARIO,
        "base": {"pr": 110, "head": "ccf91375221a9a31c51bf83b5c579858f9a23927", "tree": "10336a520f5a19e06fb31255ce3ebbcab77d4836"},
        "inherited_plan_sha256": PREVIOUS_PLAN_SHA, "one_degree_archive_sha256": PREVIOUS_ARCHIVE_SHA,
        "historical_archive_sha256": prior["historical_archive_sha256"],
        "baseline": prior["baseline"], "provider": prior["provider"], "provider_build": prior["provider_build"],
        "provider_policy": prior["provider_policy"], "provider_policy_sha256": prior["provider_policy_sha256"],
        "source_files_sha256": prior["source_files_sha256"],
        "infrastructure_source_sha256": prior["operator_source_sha256"],
        "operator_source_sha256": infra._file_sha(Path(__file__)),
        "reynolds": seed.reynolds, "mach": seed.mach, "invocations": slots,
        "limits": {"provider_launches_max": 4, "attempts_per_invocation": 1, "timeout_s": 90.0, "retries": 0, "bem_calls": 0},
        "replicates": "P1/P2 have identical scientific request preimages; N1/N2 likewise. Invocation labels are not request fields.",
        "initialization": "Each call uses the reviewed adapter's fresh isolated subprocess. Pre-spawn directory must contain only the exact airfoil.dat; no inherited solution/default file.",
        "continue_only_after": "13 usable finite points, exact request/provider/capture/executable and own invocation binding, acknowledged evidence persistence",
        "failure": "Stop all later invocations on incomplete output, timeout, exception, discrepancy or persistence failure; no replacement attempts.",
        "domain": "Diagnostic 0..+12 and 0..-12 only. Does not replace baseline -40..+32, cover the conditional first BEM query, or authorize stitching/extrapolation/symmetry substitution.",
        "physical_qualification": False,
    }
    files["plan.json"] = infra._json(plan)
    return infra.FrozenPlan(previous.provider, tuple(requests), previous.executable_sha256, tuple(files.items()))


def freeze_plan(directory: Path) -> str:
    plan = _make_plan()
    directory.mkdir(exist_ok=False)
    infra._sync_dir(directory.parent)
    for name, raw in plan.files:
        infra._write(directory / name, raw)
    return infra._sha(dict(plan.files)["plan.json"])


def load_plan(directory: Path, digest: str) -> infra.FrozenPlan:
    infra._pinned(directory / "plan.json", digest)
    plan = _make_plan()
    for name, raw in plan.files:
        if (directory / name).read_bytes() != raw:
            raise ValueError(f"Frozen {name} differs from the declared diagnostic")
    return plan


class FreshProcessLaunch:
    """Observe the real adapter's pre-spawn audit event; do not replace Popen.

    The event is intent, not proof of process creation or process-image
    attestation. Each actual capture supplies the subsequent process outcome.
    Install only in the single-purpose operator process, after static checks.
    """
    def __init__(self, provider, executable_sha256: str, identity):
        self.provider = provider
        self.binary = Path(provider.executable).resolve()
        self.executable_sha256 = executable_sha256
        self.identity = identity
        self.active = None
        self.seen_directories: set[str] = set()
        self.token = object()
        self.verified = False

    def install(self) -> None:
        sys.addaudithook(self.audit)
        sys.audit(OBSERVER_EVENT, self.token)
        if not self.verified:
            raise RuntimeError("Required pre-spawn observer was not installed")

    def audit(self, event: str, args) -> None:
        if event == OBSERVER_EVENT:
            if len(args) == 1 and args[0] is self.token:
                self.verified = True
            return
        if event != "subprocess.Popen":
            return
        if self.active is None:
            raise ValueError("No subprocess is permitted outside a declared invocation")
        request, capture_dir, invocation = self.active
        executable, argv, cwd, env = args
        if Path(executable).resolve() != self.binary or list(argv) != [str(self.binary)] or env is not None:
            raise ValueError("Unexpected executable, arguments or environment override")
        directory = Path(cwd).resolve(strict=True)
        if str(directory) in self.seen_directories or (capture_dir.parent / "subprocess-prelaunch.json").exists():
            raise ValueError("Reused directory or more than one subprocess in this invocation")
        if {p.name for p in directory.iterdir()} != {"airfoil.dat"} or (directory / "airfoil.dat").is_symlink():
            raise ValueError("Fresh subprocess directory contains unexpected defaults/solution files")
        expected = ("_PyFoldable_NACA0012\n" + "\n".join(f"{x:.17g} {y:.17g}" for x, y in request.airfoil.coordinates) + "\n").encode()
        if (directory / "airfoil.dat").read_bytes() != expected:
            raise ValueError("Pre-spawn airfoil bytes differ from this request")
        infra._pinned(self.binary, self.executable_sha256)
        infra._emit(capture_dir.parent / "subprocess-prelaunch.json", {
            "event": "subprocess.Popen_before_spawn", "utc": infra._now(),
            "invocation_sha256": invocation["invocation_sha256"], "request_sha256": request.cache_key(self.identity),
            "argv": argv, "cwd": str(directory), "airfoil_input_sha256": infra._sha(expected),
            "executable_sha256": self.executable_sha256, "only_expected_airfoil_present": True,
            "process_image_attestation": False,
        })
        self.seen_directories.add(str(directory))

    def __call__(self, request, *, capture_dir, invocation):
        if not self.verified:
            raise RuntimeError("Required pre-spawn observer is unverified")
        if self.active is not None:
            raise ValueError("An invocation is already active")
        self.active = request, capture_dir, invocation
        try:
            return self.provider.generate(request, capture_dir=capture_dir)
        finally:
            self.active = None


def run_records(plan: infra.FrozenPlan, output: Path, launch, check_executable) -> dict:
    slots = [dict(s, status="NOT_LAUNCHED", attempts=0, usable_points=None,
                  unavailable_angles_deg=None, process_observation=None) for s in plan.document["invocations"]]
    if tuple(s["label"] for s in slots) != LABELS or len(plan.requests) != 4:
        raise ValueError("Only P1, P2, N1, N2 in their declared order are permitted")
    infra._emit(output / "before-launch.json", {"experiment_id": EXPERIMENT, "invocations": slots, "utc": infra._now()})
    stop = None
    directories = set()
    for slot, request in zip(slots, plan.requests):
        directory = output / slot["label"]
        capture = directory / "capture"
        stage = "prelaunch"
        try:
            if request.cache_key(plan.provider) != slot["request_sha256"] or len(request.alpha_rad) != 13:
                raise ValueError("Caller request differs from its frozen invocation")
            directory.mkdir(exist_ok=False)
            infra._sync_dir(output)
            check_executable()
            infra._emit(directory / "started.json", {"utc": infra._now(), "invocation": slot,
                                                     "phase": "provider_call_intent_not_process_attestation"})
            slot.update(status="CALL_ATTEMPTED", attempts=1)
            stage = "provider_call"
            returned = launch(request, capture_dir=capture, invocation=slot)
            stage = "result_persistence"
            if not isinstance(returned, infra.PolarGenerationResult):
                raise TypeError("Provider did not return a PolarGenerationResult")
            infra._emit(directory / "result.json", {
                "request": returned.request.cache_payload(returned.provider), "provider": returned.provider.as_mapping(),
                "request_sha256": returned.cache_key, "complete": returned.complete, "elapsed_s": returned.elapsed_s,
                "points": [asdict(p) for p in returned.points], "warnings": returned.warnings, "metadata": returned.metadata,
            })
            stage = "capture_persistence"
            infra._sync_capture(capture)
            stage = "attribution"
            cell = infra.read_retained_cell(directory / "result.json", capture)
            result = infra._result(json.loads(cell.result_json))
            binding = infra._bind_returned_result(request, result, plan.provider)
            infra._emit(directory / "binding.json", binding)
            if binding["identity_mismatch"] or binding["capture_request_sha256"] != slot["request_sha256"]:
                raise ValueError("Returned request/provider/capture identity differs from the attempted request")
            observations: dict = {}
            try:
                checked = infra._capture(request, plan.provider, result, cell, observations)
                executable = checked["receipt"]["executable_identity"]
                if any(executable[phase]["sha256"] != plan.executable_sha256 for phase in ("prelaunch", "postlaunch")):
                    raise ValueError("Capture executable observations differ from the pinned binary")
                event = json.loads((directory / "subprocess-prelaunch.json").read_bytes())
                for key, expected in {"event": "subprocess.Popen_before_spawn", "invocation_sha256": slot["invocation_sha256"],
                                      "request_sha256": slot["request_sha256"], "executable_sha256": plan.executable_sha256,
                                      "airfoil_input_sha256": checked["receipt"]["airfoil_input_sha256"],
                                      "argv": [executable["prelaunch"]["path"]]}.items():
                    if event.get(key) != expected:
                        raise ValueError(f"Launch observation {key} differs from its own invocation")
                if event.get("only_expected_airfoil_present") is not True:
                    raise ValueError("Launch observation lacks the strict clean-directory acknowledgment")
                if not isinstance(event.get("cwd"), str) or event["cwd"] in directories:
                    raise ValueError("Missing or reused process directory")
                directories.add(event["cwd"])
                observations["own_invocation"] = event
            finally:
                infra._emit(directory / "capture-assessment.json", observations)
            slot.update(capture_binding_passed=True, usable_points=sum(result.usable_mask), elapsed_s=result.elapsed_s,
                        unavailable_angles_deg=[a for a, p in zip(slot["alpha_degrees"], result.points) if not p.usable],
                        process_observation=infra._process_observation(capture))
            stage = "completeness"
            if not result.complete or len(result.points) != 13 or result.metadata.get("capture_evidence_ready") is not True:
                raise ValueError(f"{slot['usable_points']}/13 usable; unavailable: {slot['unavailable_angles_deg']}")
            result.to_polar_table(require_complete=True)  # pure validation only; never BEM
            stage = "outcome_persistence"
            slot.update(status="COMPLETE_CAPTURED", finished_at_utc=infra._now())
            infra._emit(directory / "outcome.json", slot)
        except BaseException as error:
            slot.update(status="FAILED" if slot["attempts"] else "NOT_LAUNCHED", failure_stage=stage,
                        reason=str(error), error_type=type(error).__name__, finished_at_utc=infra._now(),
                        process_observation=infra._process_observation(capture))
            stop = {"label": slot["label"], "stage": stage, "reason": str(error)}
            try:
                infra._sync_capture(capture)
            except OSError as sync_error:
                slot["capture_sync_error"] = str(sync_error)
            break
    for slot in slots:
        if slot["status"] == "NOT_LAUNCHED":
            slot.setdefault("reason", f"Stopped at {stop['label']}; no attempt")
    outcome = {"experiment_id": EXPERIMENT, "status": "STOPPED" if stop else "DIAGNOSTIC_COMPLETED", "stop": stop,
               "invocations": slots, "provider_api_attempts": sum(s["attempts"] for s in slots), "retries": 0,
               "bem_calls": 0, "physical_qualification": False, "finished_at_utc": infra._now()}
    infra._emit(output / "outcome.json", outcome)
    return outcome


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("freeze").add_argument("directory", type=Path)
    for action in ("check", "run"):
        command = sub.add_parser(action)
        for name in ("plan", "package", "iter80", "iter160", "one-degree", "preflight", "output"):
            command.add_argument("--" + name, type=Path, required=True)
        command.add_argument("--plan-sha256", required=True)
    args = parser.parse_args()
    if args.action == "freeze":
        print(freeze_plan(args.directory))
        return 0
    output = args.output.resolve()
    output.mkdir(mode=0o700, exist_ok=False)
    infra._sync_dir(output.parent)
    try:
        plan = load_plan(args.plan, args.plan_sha256)
        for name, raw in plan.files:
            infra._write(output / name, raw)
        infra._write(output / "operator-source.py.txt", Path(__file__).read_bytes())
        infra._pinned(args.one_degree, PREVIOUS_ARCHIVE_SHA)
        old_runtime = infra._archive_json(args.one_degree, "/run/runtime.json")
        old_request = infra._archive_json(args.one_degree, "/run/cell-00/capture/request_preimage.json")
        if infra._sha(xfoil._request_preimage(infra.load_plan(PREVIOUS, PREVIOUS_PLAN_SHA).requests[0], plan.provider)) != infra._sha(
            json.dumps(old_request, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
        ):
            raise ValueError("Historical captured one-degree request differs from the retained source nodes")
        binary, osmap = infra._runtime_preflight(plan, args, output)
        current = json.loads((output / "runtime.json").read_bytes())
        keys = ("python", "python_executable_file_sha256", "platform", "dependencies", "resolved_library_file_sha256")
        infra._emit(output / "runtime-one-degree-comparison.json", {
            "archive_sha256": PREVIOUS_ARCHIVE_SHA,
            "identity_differences": {k: {"previous": old_runtime[k], "current": current[k]} for k in keys if old_runtime[k] != current[k]},
            "environment_differences": {k: {"previous": v, "current": current["environment_allowlist"].get(k)}
                                        for k, v in old_runtime["environment_allowlist"].items() if v != current["environment_allowlist"].get(k)},
        })
        if args.action == "check":
            infra._emit(output / "check.json", {"status": "STATIC_CHECKS_PASSED", "provider_api_attempts": 0, "bem_calls": 0})
            return 0
        os.environ["OSMAP"] = str(osmap)
        provider = xfoil.XfoilProvider(binary, backend_version="6.99")
        if provider.identity != plan.provider or Path(provider.executable).resolve() != binary.resolve():
            raise ValueError("Provider identity differs from the frozen plan")
        launcher = FreshProcessLaunch(provider, plan.executable_sha256, plan.provider)
        launcher.install()
        infra._emit(output / "observer-registration.json", {"verified": launcher.verified, "event": OBSERVER_EVENT,
                                                            "utc": infra._now(), "provider_api_attempts": 0})
    except BaseException as error:
        infra._emit(output / "preflight-failure.json", {"status": "BLOCKED", "reason": str(error), "provider_api_attempts": 0, "bem_calls": 0})
        print(f"BLOCKED: {error}", file=sys.stderr)
        return 2
    def check_executable():
        infra._pinned(binary, plan.executable_sha256)
        infra._pinned(osmap, plan.document["provider_build"]["osmap_sha256"])
    outcome = run_records(plan, output, launcher, check_executable)
    print(json.dumps(outcome, indent=2))
    return 1 if outcome["stop"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
