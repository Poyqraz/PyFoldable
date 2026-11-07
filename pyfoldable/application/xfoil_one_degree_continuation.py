"""Operator-only runner for the separately declared NACA0012 1° experiment.

No acquisition on import, freeze or check. No scheduler, admission into the
store, BEM, or extension of either earlier XFOIL experiment's contract.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tarfile

from pyfoldable.core.airfoil import airfoil_coordinate_sha256
from pyfoldable.core.profile_catalog import load_project_airfoil
from pyfoldable.core.providers import PolarGenerationRequest, PolarGenerationResult, ProviderIdentity, _canonical_value
from pyfoldable.providers import xfoil

from .polar_query_feasibility import _bind_returned_result
from .provider_design_analysis import _capture, _result, read_retained_cell, request_policy


ROOT = Path(__file__).resolve().parents[2]
PREVIOUS_PLAN = ROOT / "docs/decisions/xfoil-cell00-iter160-v1"
EXPERIMENT = "xfoil_naca0012_one_degree_continuation_v1"
SCENARIO = "baseline_250mm_7100rpm_iter160_one_degree_v1"
MAX_CELLS = 4
ANGLE_DEGREES = tuple(range(32, -41, -1))
PREVIOUS_PINS = {
    "proposal.json": "cbc78390576b9273db8ef5221f3cde4c664cc3df8e630c127718ba0773a2fc18",
    "request-preimage.json": "bf1af202aeec9030456de270cfa3e8753bdb587e564843e076d61a6a824706b7",
    "script.txt": "e8f9b71f806d08139139c64362e4befeb25d67400d11d75334ae5ece0ea92cc1",
    "operator-recipe.py.txt": "475fafd26551909a4ebd34ac32d97081999b6c9609991bdae0fb814d457bb78c",
}
HISTORY = {
    "iter80": "e779bb00158571541a10419ecccb011fc1c8a5ea32cad40a59e005c59f9082e9",
    "iter160": "78de64539024d9b146400618f70dbdc3469e8b0be882f83553427aa6cd22c7e6",
    "preflight": "058a91997442d42df0859a373df1bbb00005fcd882c86616ef5707590f45331a",
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pinned(path: Path, expected: str) -> None:
    if _file_sha(path) != expected:
        raise ValueError(f"{path} differs from its pinned SHA-256")


def _json(value) -> bytes:
    return (json.dumps(_canonical_value(value), indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sync_dir(directory: Path) -> None:
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write(path: Path, data: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    _sync_dir(path.parent)


def _emit(path: Path, value) -> None:
    _write(path, _json(value))


@dataclass(frozen=True)
class FrozenPlan:
    provider: ProviderIdentity
    requests: tuple[PolarGenerationRequest, ...]
    executable_sha256: str
    files: tuple[tuple[str, bytes], ...]

    @property
    def document(self) -> dict:
        return json.loads(dict(self.files)["plan.json"])


def _make_plan() -> FrozenPlan:
    for name, expected in PREVIOUS_PINS.items():
        _pinned(PREVIOUS_PLAN / name, expected)
    prior = json.loads((PREVIOUS_PLAN / "proposal.json").read_bytes())
    old_raw = (PREVIOUS_PLAN / "request-preimage.json").read_bytes()
    old = json.loads(old_raw)
    provider = ProviderIdentity(**prior["provider"])
    seed = PolarGenerationRequest(
        load_project_airfoil("NACA0012"), tuple(old["alpha_rad"]),
        **{k: old[k] for k in ("reynolds", "mach", "n_crit", "xtr_upper", "xtr_lower", "max_iterations", "timeout_s", "scenario_id", "options")},
    )
    if (xfoil._request_preimage(seed, provider) != old_raw
            or airfoil_coordinate_sha256(seed.airfoil) != prior["allowed_request"]["coordinate_sha256"]
            or request_policy(seed, provider) != prior["provider_policy"]
            or xfoil._build_command_script(seed, xfoil._validated_options(seed.options)).encode()
            != (PREVIOUS_PLAN / "script.txt").read_bytes()):
        raise ValueError("The pinned ITER160 request, catalog and declared policy disagree")
    angles = tuple(seed.alpha_rad[i // 2] if i % 2 == 0 else math.radians(a)
                   for i, a in enumerate(ANGLE_DEGREES))
    files = {}
    cells = []
    requests = []
    corners = prior["future_family_plan"]["requests"]
    states = [(c["mach"], c["reynolds"]) for c in corners]
    if len(states) != MAX_CELLS or len(set(states)) != MAX_CELLS or states != sorted(states):
        raise ValueError("Expected the four pinned Mach/Re corners in ascending Mach then Re order")
    for index, (mach, reynolds) in enumerate(states):
        old_corner = replace(seed, mach=mach, reynolds=reynolds)
        if old_corner.cache_key(provider) != corners[index]["request_sha256"]:
            raise ValueError(f"Pinned ITER160 corner {index} no longer reproduces its request identity")
        request = replace(old_corner, alpha_rad=angles, scenario_id=SCENARIO)
        preimage = xfoil._request_preimage(request, provider)
        script = xfoil._build_command_script(request, xfoil._validated_options(request.options)).encode()
        # Deleting only the interleaved commands must recover the prior script.
        odd = {f"ALFA {a}".encode() for a in ANGLE_DEGREES[1::2]}
        if b"\n".join(line for line in script.split(b"\n") if line not in odd) != xfoil._build_command_script(
            old_corner, xfoil._validated_options(old_corner.options)
        ).encode():
            raise ValueError("The new command script changes more than the interleaved angles")
        preimage_name, script_name = f"cell-{index:02d}-request-preimage.json", f"cell-{index:02d}-script.txt"
        files.update({preimage_name: preimage, script_name: script})
        requests.append(request)
        cells.append({"index": index, "profile": seed.airfoil.id, "mach": mach, "reynolds": reynolds,
                      "angle_count": len(angles), "request_sha256": _sha(preimage), "script_sha256": _sha(script),
                      "request_file": preimage_name, "script_file": script_name})
    sources = dict(prior["source_files_sha256"])
    sources["pyfoldable/application/polar_query_feasibility.py"] = _file_sha(ROOT / "pyfoldable/application/polar_query_feasibility.py")
    for name, expected in sources.items():
        _pinned(ROOT / name, expected)
        module = sys.modules.get(name[:-3].replace("/", ".")) if name.endswith(".py") else None
        if module is not None and Path(module.__file__).resolve() != ROOT / name:
            raise ValueError(f"Imported source is outside the declared checkout: {name}")
    build = dict(prior["provider_build"])
    build.pop("current_runtime_compatibility")
    plan = {
        "schema_version": 1, "artifact_class": "declared_xfoil_numerical_experiment",
        "experiment_id": EXPERIMENT, "scenario_id": SCENARIO, "baseline": prior["baseline"],
        "base": {"pr": 109, "head": "a83afb642001c17c58c660e12ce9f1d530b639ae", "tree": "bbcb687e9ebf914d17cbedf7e21e69ef7123c4b8"},
        "historical_archive_sha256": HISTORY, "iter160_plan_file_sha256": PREVIOUS_PINS,
        "reviewed_cause_map": prior["reviewed_cause_map"],
        "provider": provider.as_mapping(), "provider_build": build, "provider_policy": prior["provider_policy"],
        "provider_policy_sha256": prior["provider_policy_sha256"], "source_files_sha256": sources,
        "operator_source_sha256": _file_sha(Path(__file__)), "cells": cells,
        "cell_order": "Mach ascending, then Reynolds ascending; NACA0012 only",
        "alpha_degrees": ANGLE_DEGREES, "alpha_rad": angles, "old_nodes": "exact ITER160 preimage at even indices",
        "initialization": "fresh subprocess per cell; PANE; no INIT, VACCEL or panel-setting change",
        "limits": {"provider_launches_max": MAX_CELLS, "attempts_per_cell_max": 1, "retries": 0,
                   "timeout_s_per_subprocess": seed.timeout_s, "bem_calls": 0},
        "continue_only_after": "73 usable finite triplets, exact request/provider/raw-capture/binary binding and successful local persistence",
        "otherwise": "stop before the next cell; no retries, fallback, budget escalation, narrowing or stitching",
        "physical_qualification": False,
    }
    files["plan.json"] = _json(plan)
    return FrozenPlan(provider, tuple(requests), build["executable_sha256"], tuple(files.items()))


def freeze_plan(directory: Path) -> str:
    plan = _make_plan()
    directory.mkdir(exist_ok=False)
    _sync_dir(directory.parent)
    for name, data in plan.files:
        _write(directory / name, data)
    return _sha(dict(plan.files)["plan.json"])


def load_plan(directory: Path, expected_sha256: str) -> FrozenPlan:
    _pinned(directory / "plan.json", expected_sha256)
    plan = _make_plan()
    for name, data in plan.files:
        if (directory / name).read_bytes() != data:
            raise ValueError(f"Frozen {name} differs from the independently reproduced declaration")
    return plan


def _ledger(plan: FrozenPlan) -> list[dict]:
    return [dict(cell, status="NOT_LAUNCHED", attempts=0, usable_points=None, unavailable_angles_deg=None,
                 process_observation=None, reason="No provider call made") for cell in plan.document["cells"]]


def _sync_capture(directory: Path) -> None:
    if directory.is_dir():
        for file in directory.iterdir():
            with file.open("rb") as stream:
                os.fsync(stream.fileno())
        _sync_dir(directory)
        _sync_dir(directory.parent)


def _process_observation(directory: Path) -> dict | None:
    try:
        receipt = json.loads((directory / "capture.json").read_bytes())
        return {k: receipt[k] for k in ("process_status", "returncode")}
    except (OSError, ValueError, KeyError, TypeError):
        return None  # no native start/exit inferred from a provider API attempt


def run_cells(plan: FrozenPlan, output: Path, launch, check_executable) -> dict:
    """Run the fixed ordered plan through an injected one-cell launch seam."""
    cells = _ledger(plan)
    if len(cells) != MAX_CELLS or len(plan.requests) != MAX_CELLS:
        raise ValueError("Only the four declared cells may be attempted")
    _emit(output / "before-launch.json", {"experiment_id": EXPERIMENT, "cells": cells, "utc": _now()})
    stop = None
    for entry, request in zip(cells, plan.requests):
        directory = output / f"cell-{entry['index']:02d}"
        capture = directory / "capture"
        stage = "prelaunch"
        try:
            if request.cache_key(plan.provider) != entry["request_sha256"]:
                raise ValueError("Caller request differs from the frozen slot")
            directory.mkdir(exist_ok=False)
            _sync_dir(output)
            check_executable()
            _emit(directory / "started.json", {"utc": _now(), "experiment_id": EXPERIMENT, "cell": entry,
                                               "phase": "call_intent_not_process_attestation"})
            entry.update(attempts=1, status="CALL_ATTEMPTED", reason=None)
            stage = "provider_call"
            returned = launch(request, capture_dir=capture)
            stage = "result_persistence"
            if not isinstance(returned, PolarGenerationResult):
                raise TypeError("Provider did not return a PolarGenerationResult")
            _emit(directory / "result.json", {
                "request": returned.request.cache_payload(returned.provider), "provider": returned.provider.as_mapping(),
                "request_sha256": returned.cache_key, "complete": returned.complete, "elapsed_s": returned.elapsed_s,
                "points": [asdict(p) for p in returned.points], "warnings": returned.warnings, "metadata": returned.metadata,
            })
            stage = "capture_persistence"
            _sync_capture(capture)
            stage = "attribution"
            retained = read_retained_cell(directory / "result.json", capture)
            result = _result(json.loads(retained.result_json))
            binding = _bind_returned_result(request, result, plan.provider)
            _emit(directory / "binding.json", binding)
            if binding["identity_mismatch"] is not None or binding["capture_request_sha256"] != entry["request_sha256"]:
                raise ValueError(binding["identity_mismatch"] or "Returned capture request digest differs from the frozen slot")
            observations: dict = {}
            try:
                assessment = _capture(request, plan.provider, result, retained, observations)
                receipt = assessment["receipt"]
                exe = receipt["executable_identity"]
                observed = {k: exe[k]["sha256"] for k in ("prelaunch", "postlaunch")}
                observations["pinned_executable_check"] = {
                    "expected_sha256": plan.executable_sha256, "observed_file_sha256": observed,
                    "process_image_attestation": False,
                }
                if any(value != plan.executable_sha256 for value in observed.values()):
                    raise ValueError("Capture executable file observations differ from the pinned binary")
            finally:
                _emit(directory / "capture-assessment.json", observations)
            entry.update(capture_binding_passed=True, process_observation=_process_observation(capture),
                         usable_points=sum(result.usable_mask), elapsed_s=result.elapsed_s,
                         unavailable_angles_deg=[a for a, p in zip(ANGLE_DEGREES, result.points) if not p.usable])
            stage = "completeness"
            if (len(result.points) != len(ANGLE_DEGREES) or not result.complete
                    or result.metadata.get("capture_evidence_ready") is not True):
                raise ValueError(f"{entry['usable_points']}/{len(ANGLE_DEGREES)} usable points; unavailable angles: {entry['unavailable_angles_deg']}")
            result.to_polar_table(require_complete=True)  # pure validation, never BEM
            stage = "outcome_persistence"
            entry.update(status="COMPLETE_CAPTURED", finished_at_utc=_now())
            _emit(directory / "outcome.json", entry)
        except BaseException as error:
            entry.update(status="FAILED" if entry["attempts"] else "NOT_LAUNCHED", failure_stage=stage,
                         error_type=type(error).__name__, reason=str(error), finished_at_utc=_now(),
                         process_observation=_process_observation(capture))
            stop = {"cell_index": entry["index"], "stage": stage, "reason": str(error)}
            try:
                _sync_capture(capture)  # also retain available timeout/error bytes
            except OSError as sync_error:
                entry["capture_sync_error"] = str(sync_error)
            break
    if stop is not None:
        for entry in cells[stop["cell_index"] + 1:]:
            entry["reason"] = f"Stopped at cell {stop['cell_index']:02d}; no later attempt"
    outcome = {"experiment_id": EXPERIMENT, "status": "STOPPED" if stop else "COMPLETE_CAPTURED_FAMILY_PENDING_REVIEW",
               "cells": cells, "stop": stop, "provider_api_attempts": sum(c["attempts"] for c in cells),
               "retries": 0, "bem_calls": 0, "physical_qualification": False, "finished_at_utc": _now()}
    _emit(output / "outcome.json", outcome)
    return outcome


def _archive_json(path: Path, suffix: str) -> dict:
    with tarfile.open(path, "r:gz") as archive:
        member, = (m for m in archive.getmembers() if m.isfile() and m.name.endswith(suffix))
        with archive.extractfile(member) as stream:
            return json.load(stream)


def _runtime_preflight(plan: FrozenPlan, args, output: Path) -> tuple[Path, Path]:
    import numpy
    import scipy

    archives = {key: getattr(args, key).resolve(strict=True) for key in HISTORY}
    for key, path in archives.items():
        _pinned(path, HISTORY[key])
    old80 = _archive_json(archives["iter80"], "/prelaunch/runtime.json")
    old160 = _archive_json(archives["iter160"], "/run/runtime.json")
    package = args.package.resolve(strict=True)
    binary, osmap = package / "bin/xfoil", package / "runtime/osmapDP.dat"
    build = plan.document["provider_build"]
    _pinned(binary, plan.executable_sha256)
    _pinned(osmap, build["osmap_sha256"])
    _pinned(package / "build/xfoil6.99.tgz", build["source_archive_sha256"])
    for name, expected in build["build_records_sha256"].items():
        _pinned(package / name, expected)
        _write(output / name.replace("/", "_"), (package / name).read_bytes())
    if platform.system() != "Linux" or platform.machine() != "x86_64" or not os.access(binary, os.X_OK):
        raise ValueError("Pinned executable requires executable permissions on Linux x86_64")
    if any(os.environ.get(k) for k in ("LD_PRELOAD", "LD_AUDIT", "LD_LIBRARY_PATH")):
        raise ValueError("Loader override environment is incompatible with this pinned run")
    commands = []

    def observe(argv: list[str]) -> bytes:
        proc = subprocess.run(argv, capture_output=True, timeout=10, check=False)
        _write(output / f"{argv[0]}.stdout.bin", proc.stdout)
        _write(output / f"{argv[0]}.stderr.bin", proc.stderr)
        commands.append({"argv": argv, "returncode": proc.returncode})
        if proc.returncode != 0 or b"not found" in proc.stdout + proc.stderr:
            raise ValueError(f"Static {argv[0]} inspection failed")
        return proc.stdout

    elf = observe(["readelf", "-h", "-l", "-d", "-V", str(binary)])
    if not all(token in elf for token in (b"ELF64", b"Advanced Micro Devices X86-64", b"interpreter: /lib64/ld-linux-x86-64.so.2]")):
        raise ValueError("Unexpected pinned executable class/machine/interpreter")
    trace = observe(["ldd", str(binary)])  # trusted standard ELF; loader trace, no solver startup
    libraries = {}
    for match in re.findall(rb"(/[^\s()]+)", trace):
        path = Path(os.fsdecode(match)).resolve(strict=True)
        libraries[str(path)] = _file_sha(path)
    if not libraries:
        raise ValueError("Pinned executable dependencies did not resolve")
    environment = {k: os.environ.get(k) for k in (
        "PATH", "LANG", "LC_ALL", "LD_PRELOAD", "LD_AUDIT", "LD_LIBRARY_PATH", "PYTHONPATH", "PYTHONDONTWRITEBYTECODE",
        "PYTHONHASHSEED", "PYTHONOPTIMIZE", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "GFORTRAN_UNBUFFERED_ALL",
    )}
    identity = {
        "python": sys.version, "python_executable_file_sha256": _file_sha(Path(sys.executable).resolve()),
        "platform": platform.platform(), "dependencies": {"numpy": numpy.__version__, "scipy": scipy.__version__},
        "resolved_library_file_sha256": libraries,
    }
    historical = {
        "iter80": {"python": old80["python"]["version"], "python_executable_file_sha256": old80["python"]["sha256"],
                   "platform": old80["platform"], "dependencies": old80["packages"],
                   "resolved_library_file_sha256": {e["path"]: e["sha256"] for e in old80["resolved_library_files"]}},
        "iter160": {key: old160[key] for key in identity},
    }
    drift = {label: {key: {"previous": values[key], "current": value} for key, value in identity.items() if value != values[key]}
             for label, values in historical.items()}
    for label, old_env in (("iter80", old80["environment"]), ("iter160", old160["environment_allowlist"])):
        drift[label]["environment_differences_on_shared_keys"] = {
            k: {"previous": v, "current": environment[k]} for k, v in old_env.items() if k in environment and v != environment[k]
        }
        drift[label]["environment_keys_not_retained_previously"] = sorted(set(environment) - set(old_env))
    _emit(output / "runtime.json", {
        **identity, "utc": _now(), "argv": [sys.executable, *sys.orig_argv[1:]], "cwd": str(Path.cwd()),
        "python_executable": str(Path(sys.executable).resolve()), "libc": platform.libc_ver(),
        "import_paths": {"numpy": numpy.__file__, "scipy": scipy.__file__, "xfoil_adapter": xfoil.__file__},
        "source_checkout": str(ROOT), "environment_allowlist": environment, "static_commands": commands,
        "binary": {"path": str(binary), "sha256": plan.executable_sha256}, "OSMAP": str(osmap), "osmap_sha256": build["osmap_sha256"],
        "verified_archives": {key: {"path": str(path), "sha256": HISTORY[key]} for key, path in archives.items()},
        "runtime_differences_vs_history": drift, "process_image_attestation": False,
    })
    return binary, osmap


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    freeze = sub.add_parser("freeze", help="write a new plan; no solver")
    freeze.add_argument("directory", type=Path)
    for action in ("check", "run"):
        command = sub.add_parser(action, help="static checks only" if action == "check" else "execute the authorized frozen plan once")
        for arg in ("plan", "package", "iter80", "iter160", "preflight", "output"):
            command.add_argument("--" + arg, type=Path, required=True)
        command.add_argument("--plan-sha256", required=True)
    args = parser.parse_args()
    if args.action == "freeze":
        print(freeze_plan(args.directory))
        return 0
    output = args.output.resolve()
    output.mkdir(mode=0o700, exist_ok=False)
    _sync_dir(output.parent)
    try:
        plan = load_plan(args.plan, args.plan_sha256)
        for name, data in plan.files:
            _write(output / name, data)
        _write(output / "operator-source.py.txt", Path(__file__).read_bytes())
        binary, osmap = _runtime_preflight(plan, args, output)
        if args.action == "check":
            _emit(output / "check.json", {"status": "STATIC_CHECKS_PASSED", "provider_api_attempts": 0, "bem_calls": 0})
            return 0
        os.environ["OSMAP"] = str(osmap)
        provider = xfoil.XfoilProvider(binary, backend_version="6.99")  # no banner probe
        if provider.identity != plan.provider or Path(provider.executable).resolve() != binary.resolve():
            raise ValueError("Provider runtime identity differs from the frozen declaration")
    except BaseException as error:
        _emit(output / "preflight-failure.json", {"utc": _now(), "status": "BLOCKED", "reason": str(error),
                                                  "provider_api_attempts": 0, "bem_calls": 0, "physical_qualification": False})
        print(f"BLOCKED: {error}", file=sys.stderr)
        return 2

    def check_executable() -> None:
        _pinned(binary, plan.executable_sha256)
        _pinned(osmap, plan.document["provider_build"]["osmap_sha256"])

    outcome = run_cells(plan, output, provider.generate, check_executable)
    print(json.dumps(outcome, indent=2))
    return 1 if outcome["stop"] is not None else 0


if __name__ == "__main__":
    raise SystemExit(main())
