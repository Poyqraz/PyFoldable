"""Operator-only: freeze, capture and install the declared NACA2412 deployment polar family.

Widens the attached-flow grid of research_axial_800_attached_xfoil_v1 in Reynolds and Mach for
coupled deployment cases (configs/polars/RESEARCH_AXIAL_800_DEPLOY_V3.json). Same angle grid and
solver settings; a separately built XFOIL 6.99 executable pinned by its own hashes, so this is a
separate family and no v1 cell is reused. DEPLOY_V1 and DEPLOY_V2 stopped on a non-converged point
and stay recorded as failed declarations (--protocol re-verifies their evidence).
Normal application runs never import/call this launcher. No retries, fallback, cell
substitution or re-gridding.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import importlib.util
import json
import math
import os
from pathlib import Path

from pyfoldable.application import provider_design_analysis as admission
from pyfoldable.application.provider_record_store import ProviderRecordStore
from pyfoldable.core import BEMRotorSettings, load_design_config
from pyfoldable.core.profile_catalog import load_project_airfoil
from pyfoldable.core.providers import PolarGenerationRequest, ProviderIdentity
from pyfoldable.providers import xfoil

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "configs/polars/RESEARCH_AXIAL_800_DEPLOY_V3.json"
PROFILES = ("NACA2412",)
VERSION = "2026-11-12-deploy-v3"
INSTALL_SCENARIO = "research_axial_800_deploy_xfoil_v3"  # the only declaration this launcher installs under VERSION

_spec = importlib.util.spec_from_file_location("research_reference_operator_base", Path(__file__).with_name("research_reference_data.py"))
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
sha = base.sha


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
    if (len(requests) != declaration["budget"]["max_provider_calls"]
            or any(r.timeout_s != 30 or len(r.alpha_rad) != 8 for r in requests)):
        raise ValueError("Declared cell, angle or timeout budget changed")
    return requests


def make_plan():
    declaration = base.load(PROTOCOL)
    template = ROOT / declaration["template"]
    settings = BEMRotorSettings(annulus_count=40)
    guard = base.scan_guard(load_design_config(template), settings)
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
    if base.load(path / "plan.json") != plan:
        raise ValueError("Frozen plan differs from the executable declaration")
    for name, content in artifacts.items():
        if (path / "frozen" / name).read_bytes() != content:
            raise ValueError(f"Frozen request/script changed: {name}")
    return plan


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
        row.update(status="ATTEMPTED", started_utc=base.utc())
        base.write(folder / f"started-{index:02d}.json", row)
        result_path = folder / f"result-{index:02d}.json"
        raw = folder / f"capture-{index:02d}"
        try:
            result = provider.generate(request, capture_dir=raw)
            base.retain_result(result, result_path)
            base.check_cell(request, identity, admission.read_retained_cell(result_path, raw), declaration["executable_sha256"])
        except (ValueError, KeyError, TypeError, RuntimeError, OSError) as exc:
            row.update(status="STOPPED", reason=f"{type(exc).__name__}: {exc}", ended_utc=base.utc())
            break
        row.update(status="COMPLETE", usable=len(request.alpha_rad), ended_utc=base.utc())
    base.write(folder / "outcome.json", {"profile": profile, "cells": rows,
        "provider_calls": sum(r["status"] != "NOT_LAUNCHED" for r in rows),
        "complete": all(r["status"] == "COMPLETE" for r in rows), "bem_calls": 0})
    return rows


def install(root, profile, store_root):
    if base.load(PROTOCOL)["scenario_id"] != INSTALL_SCENARIO:
        raise ValueError(f"This launcher only installs {INSTALL_SCENARIO} as {VERSION}; other declarations are verify-only")
    plan = require_plan(root)
    folder = root / profile
    if base.load(folder / "checksums.json") != base.phase_files(folder):
        raise ValueError("Retained acquisition byte hashes differ")
    status = base.load(folder / "outcome.json")
    declaration = plan["declaration"]
    identity = ProviderIdentity(**declaration["provider"])
    requests = request_grid(profile, declaration)
    if not status["complete"] or status["provider_calls"] != len(requests):
        raise ValueError("No complete family to install")
    cells = tuple(admission.read_retained_cell(folder / f"result-{i:02d}.json", folder / f"capture-{i:02d}")
                  for i in range(len(requests)))
    for request, cell in zip(requests, cells):
        base.check_cell(request, identity, cell, declaration["executable_sha256"])
    provenance = (("plan.json", (root / "plan.json").read_bytes()),) + tuple(
        (n, (folder / n).read_bytes()) for n in ("runtime.json", "build-record.json", "outcome.json", "checksums.json"))
    family = admission.ManagedProviderFamily(
        f'{declaration["scenario_id"]}:{profile}', identity, requests, cells, "caller_supplied_unqualified",
        f'operator-captured numerical records; plan_sha256:{sha(provenance[0][1])}', provenance)
    with ProviderRecordStore(store_root) as store:
        return store.register_family(family, version_label=VERSION)


def main():
    global PROTOCOL
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "capture", "install"))
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--profile", choices=PROFILES)
    parser.add_argument("--preflight", type=Path)
    parser.add_argument("--store", type=Path)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL,
                        help="declaration to verify against (default: the current version)")
    args = parser.parse_args()
    PROTOCOL = args.protocol.resolve()
    root = args.evidence.resolve()
    if args.action == "freeze":
        plan, artifacts = make_plan()
        root.mkdir(exist_ok=False)
        (root / "frozen").mkdir()
        base.write(root / "plan.json", plan)
        for name, data in artifacts.items():
            (root / "frozen" / name).write_bytes(data)
        print(sha((root / "plan.json").read_bytes()))
    elif args.action == "capture":
        if args.profile is None or args.preflight is None:
            parser.error("capture requires --profile and --preflight")
        plan = require_plan(root)
        exe, osmap, runtime = base.observed_runtime(args.preflight.resolve(), plan)
        runtime["caller_sha256"] = sha(Path(__file__).read_bytes())
        folder = root / args.profile
        folder.mkdir(exist_ok=False)
        base.write(folder / "runtime.json", runtime)
        (folder / "build-record.json").write_bytes((args.preflight / "build/build-record.json").read_bytes())
        os.environ["OSMAP"] = str(osmap)
        provider = xfoil.XfoilProvider(exe, backend_version="6.99")
        rows = capture(args.profile, folder, plan, provider)
        base.write(folder / "checksums.json", base.phase_files(folder))
        print(json.dumps(rows, indent=2))
        return 0 if all(r["status"] == "COMPLETE" for r in rows) else 2
    else:
        if args.profile is None or args.store is None:
            parser.error("install requires --profile and --store")
        print(json.dumps(asdict(install(root, args.profile, args.store)), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
