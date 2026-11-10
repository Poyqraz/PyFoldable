"""Operator-only: freeze, capture and install the declared axial research family.

Normal application runs never import/call this launcher. No retries or fallback.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys

from pyfoldable.application import provider_design_analysis as admission
from pyfoldable.application.polar_query_feasibility import _bind_returned_result
from pyfoldable.application.provider_record_store import ProviderRecordStore
from pyfoldable.core import BEMRotorSettings, load_design_config
from pyfoldable.core.bem_rotor import _interpolate_station
from pyfoldable.core.profile_catalog import load_project_airfoil
from pyfoldable.core.providers import PolarGenerationRequest, ProviderIdentity
from pyfoldable.providers import xfoil

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "configs/polars/RESEARCH_AXIAL_800_V1.json"
PROFILES = ("NACA0012", "NACA2412")
VERSION = "2026-11-11-v1"
sha = admission._sha


def utc():
    return datetime.now(timezone.utc).isoformat()


def write(path, doc):
    with path.open("xb") as stream:
        stream.write((admission._json(doc) + "\n").encode())
        stream.flush()
        os.fsync(stream.fileno())


def load(path):
    return admission._document(path.read_bytes())


def request_grid(profile, declaration):
    if profile not in PROFILES:
        raise ValueError("Profile is outside the frozen protocol")
    foil = load_project_airfoil(profile)
    requests = tuple(PolarGenerationRequest(
        airfoil=foil, alpha_rad=tuple(math.radians(x) for x in declaration["alpha_deg_in_order"]),
        reynolds=re, mach=m, n_crit=declaration["n_crit"], xtr_upper=declaration["xtr_upper"],
        xtr_lower=declaration["xtr_lower"], max_iterations=declaration["max_iterations"],
        timeout_s=declaration["timeout_s"], scenario_id=declaration["scenario_id"],
        options=declaration["options"],
    ) for m in declaration["mach"] for re in declaration["reynolds"])
    if len(requests) != 6 or any(r.timeout_s != 30 or len(r.alpha_rad) != 8 for r in requests):
        raise ValueError("Declared cell, angle or timeout budget changed")
    return requests


def scan_guard(design, policy):
    """Bound the positive scan up to its first alpha <= -4 deg sample.

    On the existing positive psi branch phi=(psi+psi0)/2 and
    W=W0*cos((psi-psi0)/2). If CL(-6,-4) is negative at all corners
    and initial CL positive, a bracket is found by that sample.
    This is a conditional preflight, not observed solver queries.
    """
    blade, condition = design.blade, design.operating_conditions[0]
    lower, upper = (blade.stations[i].r_over_R * blade.radius_m for i in (0, -1))
    guard = []
    for i in range(policy.annulus_count):
        radius = lower + (i + .5) * (upper - lower) / policy.annulus_count
        station, _ = _interpolate_station(blade, radius)
        axial = condition.forward_speed_m_s
        tangential = condition.angular_speed_rad_s * radius
        psi0 = math.atan2(axial, tangential)
        alpha0 = station.twist_rad - psi0
        dpsi = (math.pi / 2 - policy.annulus_settings.angle_tolerance_rad - psi0) / policy.annulus_settings.bracket_samples
        steps = math.ceil(2 * (alpha0 + math.radians(4)) / dpsi)
        alpha_last = alpha0 - steps * dpsi / 2
        speed0 = math.hypot(axial, tangential)
        speed_last = speed0 * math.cos(steps * dpsi / 2)
        a = math.sqrt(1.4 * 287.05 * condition.temperature_k)
        re_scale = condition.air_density_kg_m3 * station.chord_m / condition.dynamic_viscosity_pa_s
        guard.append({"r_m": radius, "scan_samples_to_negative_lift_guard": steps,
            "alpha_rad": [alpha_last, alpha0], "reynolds": [speed_last * re_scale, speed0 * re_scale],
            "mach": [speed_last / a, speed0 / a]})
    return guard


def make_plan():
    declaration = load(PROTOCOL)
    template = ROOT / declaration["template"]
    settings = BEMRotorSettings(annulus_count=40)
    guard = scan_guard(load_design_config(template), settings)
    for axis, values in (("alpha_rad", list(map(math.radians, declaration["alpha_deg_in_order"]))),
                         ("reynolds", declaration["reynolds"]), ("mach", declaration["mach"])):
        if not all(min(values) <= row[axis][0] <= row[axis][1] <= max(values) for row in guard):
            raise ValueError(f"Declared rectangle does not cover conditional scan: {axis}")
    provider = ProviderIdentity(**declaration["provider"])
    artifacts = {}
    for profile in PROFILES:
        for index, request in enumerate(request_grid(profile, declaration)):
            key = f"{profile}-{index:02d}"
            artifacts[key + ".request.json"] = xfoil._request_preimage(request, provider)
            artifacts[key + ".script.txt"] = xfoil._build_command_script(request, xfoil._validated_options(request.options)).encode()
    plan = {"declaration": declaration, "declaration_sha256": sha(PROTOCOL.read_bytes()),
            "template_sha256": sha(template.read_bytes()), "bem_settings": settings.as_mapping(),
            "bounds": "error", "conditional_scan_not_execution": guard,
            "adapter_sha256": sha(Path(xfoil.__file__).read_bytes()),
            "frozen_files": {k: sha(v) for k, v in artifacts.items()}}
    return plan, artifacts


def require_plan(path):
    plan, artifacts = make_plan()
    if load(path / "plan.json") != plan:
        raise ValueError("Frozen plan differs from the executable declaration")
    for name, content in artifacts.items():
        if (path / "frozen" / name).read_bytes() != content:
            raise ValueError(f"Frozen request/script changed: {name}")
    return plan


def retain_result(result, path):
    write(path, {"request": result.request.cache_payload(result.provider), "provider": result.provider.as_mapping(),
        "request_sha256": result.cache_key, "complete": result.complete, "elapsed_s": result.elapsed_s,
        "warnings": list(result.warnings), "metadata": result.metadata,
        "points": [asdict(p) for p in result.points]})


def check_cell(request, identity, cell, executable_sha):
    result = admission._result(admission._document(cell.result_json))
    binding = _bind_returned_result(request, result, identity)
    if binding["identity_mismatch"]:
        raise ValueError(binding["identity_mismatch"])
    capture = admission._capture(request, identity, result, cell, {})
    executable = capture["receipt"]["executable_identity"]
    if any(executable[k]["sha256"] != executable_sha for k in ("prelaunch", "postlaunch")):
        raise ValueError("Pinned executable file observations differ")
    if not result.complete:
        raise ValueError(f"Incomplete cell: {sum(p.usable for p in result.points)}/{len(request.alpha_rad)} usable")
    points = {p.alpha_rad: p.cl for p in result.points}
    if not all(points[math.radians(x)] < 0 for x in (-6.0, -4.0)) or not all(points[math.radians(x)] > 0 for x in (4.0, 6.0, 8.0)):
        raise ValueError("Retained lift signs do not support the predeclared conditional scan")
    return result


def capture(profile, folder, plan, provider):
    declaration = plan["declaration"]
    identity = ProviderIdentity(**declaration["provider"])
    if provider.identity != identity:
        raise ValueError("Wrong provider identity")
    requests = request_grid(profile, declaration)
    rows = [{"index": i, "status": "NOT_LAUNCHED", "request_sha256": r.cache_key(identity)}
            for i, r in enumerate(requests)]
    for row, request in zip(rows, requests):
        index = row["index"]
        row.update(status="ATTEMPTED", started_utc=utc())
        write(folder / f"started-{index:02d}.json", row)
        result_path = folder / f"result-{index:02d}.json"
        raw = folder / f"capture-{index:02d}"
        try:
            result = provider.generate(request, capture_dir=raw)
            retain_result(result, result_path)
            check_cell(request, identity, admission.read_retained_cell(result_path, raw), declaration["executable_sha256"])
        except (ValueError, KeyError, TypeError, RuntimeError, OSError) as exc:
            row.update(status="STOPPED", reason=f"{type(exc).__name__}: {exc}", ended_utc=utc())
            break
        row.update(status="COMPLETE", usable=len(request.alpha_rad), ended_utc=utc())
    write(folder / "outcome.json", {"profile": profile, "cells": rows,
        "provider_calls": sum(r["status"] != "NOT_LAUNCHED" for r in rows),
        "complete": all(r["status"] == "COMPLETE" for r in rows), "bem_calls": 0})
    return rows


def observed_runtime(preflight, plan):
    d = plan["declaration"]
    exe = preflight / "bin/xfoil"
    osmap = preflight / "runtime/osmapDP.dat"
    records = {"build/build-record.json": d["build_record_sha256"],
               "runtime/osmapDP.dat": d["osmap_sha256"], "bin/xfoil": d["executable_sha256"]}
    for name, expected in records.items():
        if sha((preflight / name).read_bytes()) != expected:
            raise ValueError(f"Pinned bytes changed: {name}")
    if platform.system() != "Linux" or platform.machine() != "x86_64" or any(os.environ.get(k) for k in ("LD_PRELOAD", "LD_LIBRARY_PATH")):
        raise ValueError("Unsupported runtime or loader overrides")
    linked = subprocess.check_output(["ldd", str(exe)], text=True)
    if "not found" in linked:
        raise ValueError("Pinned XFOIL runtime dependencies unavailable")
    paths = {token for token in linked.split() if token.startswith("/") and Path(token).is_file()}
    return exe, osmap, {"command": [sys.executable, *sys.argv], "cwd": os.getcwd(),
        "platform": platform.platform(), "python": sys.version,
        "numpy": version("numpy"), "scipy": version("scipy"),
        "executable_sha256": d["executable_sha256"], "osmap_sha256": d["osmap_sha256"],
        "ldd": linked, "library_hashes": {x: sha(Path(x).read_bytes()) for x in sorted(paths)},
        "adapter_sha256": plan["adapter_sha256"], "caller_sha256": sha(Path(__file__).read_bytes()),
        "started_utc": utc(), "initialization": "new adapter cwd per cell; no copied defaults; explicit OSMAP; no banner call"}


def phase_files(folder):
    return {str(p.relative_to(folder)): sha(p.read_bytes()) for p in sorted(folder.rglob("*"))
            if p.is_file() and p != folder / "checksums.json"}


def install(root, profile, store_root):
    plan = require_plan(root)
    folder = root / profile
    if load(folder / "checksums.json") != phase_files(folder):
        raise ValueError("Retained acquisition byte hashes differ")
    status = load(folder / "outcome.json")
    if not status["complete"] or status["provider_calls"] != 6:
        raise ValueError("No complete family to install")
    declaration = plan["declaration"]
    identity = ProviderIdentity(**declaration["provider"])
    requests = request_grid(profile, declaration)
    cells = tuple(admission.read_retained_cell(folder / f"result-{i:02d}.json", folder / f"capture-{i:02d}")
                  for i in range(6))
    for request, cell in zip(requests, cells):
        check_cell(request, identity, cell, declaration["executable_sha256"])
    provenance = (("plan.json", (root / "plan.json").read_bytes()),) + tuple(
        (n, (folder / n).read_bytes()) for n in ("runtime.json", "build-record.json", "outcome.json", "checksums.json"))
    family = admission.ManagedProviderFamily(
        f'{declaration["scenario_id"]}:{profile}', identity, requests, cells, "caller_supplied_unqualified",
        f'operator-captured numerical records; plan_sha256:{sha(provenance[0][1])}', provenance)
    with ProviderRecordStore(store_root) as store:
        return store.register_family(family, version_label=VERSION)


def require_first_application(root, plan):
    from dataclasses import replace
    from pyfoldable.application import research_design as research
    first = research.read_saved_result((root / "first-application-result.json").read_bytes())
    active = research.build_research_design(ROOT, replace(research.defaults(ROOT), profile=PROFILES[0]))
    snapshot = first["aerodynamics"]
    if (first["inputs"] != asdict(active.inputs) or first["draft_sha256"] != active.draft.draft_sha256
            or snapshot["status"] != "success" or snapshot["airfoil_id"] != PROFILES[0]):
        raise ValueError("First application result is not the frozen NACA0012 reference success")
    report = json.loads(snapshot["report_text"])
    context = report["request"]["provider_design_admission"]
    provenance = {x["name"]: x for x in context["provenance"]}
    if (report["rotor"]["settings"] != plan["bem_settings"] or report["rotor"]["polar_bounds"] != "error"
            or context["complete_family_admitted"] is not True
            or provenance["plan.json"]["sha256"] != sha((root / "plan.json").read_bytes())):
        raise ValueError("First application result is not bound to the frozen family/BEM policy")
    return first


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "capture", "install"))
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--profile", choices=PROFILES)
    parser.add_argument("--preflight", type=Path)
    parser.add_argument("--store", type=Path)
    args = parser.parse_args()
    root = args.evidence.resolve()
    if args.action == "freeze":
        plan, artifacts = make_plan()
        root.mkdir(exist_ok=False)
        (root / "frozen").mkdir()
        write(root / "plan.json", plan)
        for name, data in artifacts.items():
            (root / "frozen" / name).write_bytes(data)
        print(sha((root / "plan.json").read_bytes()))
    elif args.action == "capture":
        if args.profile is None or args.preflight is None:
            parser.error("capture requires --profile and --preflight")
        plan = require_plan(root)
        if args.profile == PROFILES[1]:
            require_first_application(root, plan)
        exe, osmap, runtime = observed_runtime(args.preflight.resolve(), plan)
        folder = root / args.profile
        folder.mkdir(exist_ok=False)
        write(folder / "runtime.json", runtime)
        (folder / "build-record.json").write_bytes((args.preflight / "build/build-record.json").read_bytes())
        os.environ["OSMAP"] = str(osmap)
        provider = xfoil.XfoilProvider(exe, backend_version="6.99")
        rows = capture(args.profile, folder, plan, provider)
        write(folder / "checksums.json", phase_files(folder))
        print(json.dumps(rows, indent=2))
        return 0 if all(r["status"] == "COMPLETE" for r in rows) else 2
    else:
        if args.profile is None or args.store is None:
            parser.error("install requires --profile and --store")
        print(json.dumps(asdict(install(root, args.profile, args.store)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
