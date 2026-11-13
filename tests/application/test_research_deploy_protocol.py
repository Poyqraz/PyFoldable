"""Deployment polar protocol: prelaunch checks with fake calls only (no XFOIL constructor or solver)."""
import importlib.util
import json
import math
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from pyfoldable.core.providers import ProviderIdentity

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("research_deploy_operator_test", ROOT / "examples/research_deploy_polar_data.py")
dep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dep)


def test_frozen_grid_order_budget_and_scripts():
    plan, files = dep.make_plan()
    d = plan["declaration"]
    assert dep.PROFILES == ("NACA2412",) and d["profiles_in_order"] == ["NACA2412"]
    requests = dep.request_grid("NACA2412", d)
    assert len(requests) == 20 == d["budget"]["max_provider_calls"]
    assert [(q.mach, q.reynolds) for q in requests] == [(m, r) for m in d["mach"] for r in d["reynolds"]]
    assert len(files) == 40
    for n, q in enumerate(requests):
        script = files[f"NACA2412-{n:02d}.script.txt"].splitlines()
        assert len([line for line in script if line.startswith(b"ALFA ")]) == 8
        assert b"ITER 160" in script and b"PANE" in script and b"INIT" not in script
        assert q.timeout_s == 30 and q.scenario_id == "research_axial_800_deploy_xfoil_v3"
    assert plan["declaration_sha256"] == dep.sha(dep.PROTOCOL.read_bytes())
    assert d["physical_qualification"] is False


def test_same_angles_and_solver_settings_as_v1_and_v1_cells_repeated():
    v1 = json.loads((ROOT / "configs/polars/RESEARCH_AXIAL_800_V1.json").read_bytes())
    d = json.loads(dep.PROTOCOL.read_bytes())
    for key in ("alpha_deg_in_order", "n_crit", "xtr_upper", "xtr_lower", "max_iterations", "timeout_s", "options",
                "provider", "osmap_sha256", "template", "root"):
        assert d[key] == v1[key], key
    assert set(v1["reynolds"]) <= set(d["reynolds"]) and set(v1["mach"]) <= set(d["mach"])
    assert d["executable_sha256"] != v1["executable_sha256"]  # a different build: separate family, never mixed


def test_failed_declarations_stay_recorded_and_v3_changes_only_the_grid():
    load = lambda n: json.loads((ROOT / f"configs/polars/RESEARCH_AXIAL_800_DEPLOY_V{n}.json").read_bytes())  # noqa: E731
    v1, v2, d = load(1), load(2), json.loads(dep.PROTOCOL.read_bytes())
    assert dep.PROTOCOL.name == "RESEARCH_AXIAL_800_DEPLOY_V3.json"
    diff = lambda a, b: {k for k in set(a) | set(b) if a.get(k) != b.get(k)}  # noqa: E731
    assert diff(v2, v1) == {"scenario_id", "max_iterations", "supersedes"} and v2["max_iterations"] == 300
    assert diff(d, v1) == {"scenario_id", "reynolds", "mach", "budget", "supersedes"}
    assert {k for k in d["budget"] if d["budget"][k] != v1["budget"][k]} == {"max_provider_calls"}
    assert [x["protocol"] for x in d["supersedes"]["failed_declarations"]] == [
        "configs/polars/RESEARCH_AXIAL_800_DEPLOY_V1.json", "configs/polars/RESEARCH_AXIAL_800_DEPLOY_V2.json"]
    assert set(d["mach"]) < set(v1["mach"]) | {0.07} and set(d["reynolds"]) < set(v1["reynolds"])


def test_failed_declaration_evidence_still_verifies_against_its_own_grid():
    for n, cells in ((1, 30), (2, 30)):
        failed = json.loads((ROOT / f"configs/polars/RESEARCH_AXIAL_800_DEPLOY_V{n}.json").read_bytes())
        assert len(dep.request_grid("NACA2412", failed)) == cells


def test_rejects_changed_grid():
    d = json.loads(dep.PROTOCOL.read_bytes())
    with pytest.raises(ValueError):
        dep.request_grid("NACA2412", {**d, "mach": d["mach"][:-1]})
    with pytest.raises(ValueError):
        dep.request_grid("NACA0012", d)


def test_grid_covers_declared_deployment_targets():
    """The no-induction states of the declared target cases lie inside the declared rectangle."""
    from pyfoldable.application import coupled_analysis as svc
    from pyfoldable.application import research_design as research
    from pyfoldable.coupled.model import CoupledControls, CoupledMechanics, build_case
    d = json.loads(dep.PROTOCOL.read_bytes())
    env = {"alpha_deg": [min(d["alpha_deg_in_order"]), max(d["alpha_deg_in_order"])],
           "reynolds": [min(d["reynolds"]), max(d["reynolds"])], "mach": [min(d["mach"]), max(d["mach"])]}
    active = research.build_research_design(ROOT, replace(research.defaults(ROOT), profile="NACA2412"))

    def case(fold, rpm0=0.0):
        mech = CoupledMechanics(distal_mass_kg=0.030, distal_cg_from_hinge_m=0.055, distal_inertia_cg_kg_m2=3.0e-5,
                                stop_stiffness_nm_per_rad=500.0, stop_restitution=0.5, initial_fold_rad=math.radians(fold),
                                release_time_s=0.05, source="test", declaration_kind="demonstration_assumption")
        ctl = CoupledControls(azimuth_step_deg=2.5, duration_s=0.125, elements_per_segment=8,
                              drive_profile="ramp" if rpm0 else "constant", ramp_start_rpm=rpm0,
                              ramp_start_s=0.05 if rpm0 else 0.0, ramp_duration_s=0.06 if rpm0 else 0.0)
        return build_case(active, mech, ctl)

    swing = svc.trajectory_applicability(case(-22.5), env)
    assert swing["reynolds_ok"] and swing["mach_ok"] and swing["alpha_ok"]
    assert swing["swing"]["mach_ok"] and swing["swing"]["reynolds_ok"] and swing["swing"]["alpha_ok"]
    ramp = svc.trajectory_applicability(case(-20, 1600.0), env)
    assert ramp["reynolds_ok"] and ramp["mach_ok"] and ramp["alpha_ok"]
    assert ramp["swing"]["mach_ok"]


def test_stop_before_next_call_and_retain_failure(tmp_path):
    plan, _ = dep.make_plan()
    called = []

    def generate(request, *, capture_dir):
        called.append(request)
        capture_dir.mkdir()
        (capture_dir / "inert-raw.bin").write_bytes(b"INERT FAILURE")
        raise RuntimeError("inert stop witness")

    provider = SimpleNamespace(identity=ProviderIdentity(**plan["declaration"]["provider"]), generate=generate)
    rows = dep.capture("NACA2412", tmp_path, plan, provider)
    assert len(called) == 1
    assert [r["status"] for r in rows] == ["STOPPED"] + ["NOT_LAUNCHED"] * 19
    outcome = json.loads((tmp_path / "outcome.json").read_bytes())
    assert outcome["provider_calls"] == 1 and outcome["complete"] is False
    assert (tmp_path / "capture-00/inert-raw.bin").read_bytes() == b"INERT FAILURE"


def test_install_refuses_incomplete_family(tmp_path):
    plan, files = dep.make_plan()
    dep.base.write(tmp_path / "plan.json", plan)
    (tmp_path / "frozen").mkdir()
    for name, data in files.items():
        (tmp_path / "frozen" / name).write_bytes(data)
    folder = tmp_path / "NACA2412"
    folder.mkdir()
    dep.base.write(folder / "outcome.json", {"profile": "NACA2412", "cells": [], "provider_calls": 1, "complete": False})
    dep.base.write(folder / "checksums.json", dep.base.phase_files(folder))
    with pytest.raises(ValueError, match="No complete family"):
        dep.install(tmp_path, "NACA2412", tmp_path / "store")


EVIDENCE = ROOT / "reports/coupled_deploy_polars_20261112"


@pytest.mark.parametrize("folder,version,complete", [("evidence_v1_failed", 1, False), ("evidence_v2_failed", 2, False),
                                                      ("evidence_v3", 3, True)])
def test_retained_operator_evidence_reverifies_against_its_declaration(folder, version, complete, monkeypatch):
    monkeypatch.setattr(dep, "PROTOCOL", ROOT / f"configs/polars/RESEARCH_AXIAL_800_DEPLOY_V{version}.json")
    root = EVIDENCE / folder
    dep.require_plan(root)
    cells = root / "NACA2412"
    assert dep.base.load(cells / "checksums.json") == dep.base.phase_files(cells)
    outcome = dep.base.load(cells / "outcome.json")
    assert outcome["complete"] is complete
    if not complete:
        assert [r["status"] for r in outcome["cells"]][:6] == ["COMPLETE"] * 4 + ["STOPPED", "NOT_LAUNCHED"]


def test_install_requires_the_current_declaration(tmp_path, monkeypatch):
    monkeypatch.setattr(dep, "PROTOCOL", ROOT / "configs/polars/RESEARCH_AXIAL_800_DEPLOY_V1.json")
    with pytest.raises(ValueError, match="only installs"):
        dep.install(EVIDENCE / "evidence_v1_failed", "NACA2412", tmp_path / "store")


def test_committed_store_holds_both_naca2412_families_and_the_deploy_table():
    from pyfoldable.application import research_design as research
    from pyfoldable.application.provider_record_store import ProviderRecordStore
    from pyfoldable.coupled import c81 as c81mod
    with ProviderRecordStore(ROOT / "data/research_reference/axial_800_store") as store:
        repo = store.load_repository()
    by = {f.family_id: f for f in repo.families}
    assert set(by) == {"research_axial_800_attached_xfoil_v1:NACA0012", "research_axial_800_attached_xfoil_v1:NACA2412",
                       "research_axial_800_deploy_xfoil_v3:NACA2412"}
    old, new = by["research_axial_800_attached_xfoil_v1:NACA2412"], by["research_axial_800_deploy_xfoil_v3:NACA2412"]
    assert old.stored_version.content_sha256 == "5841e000f7885350756d73803a9a0506b1f895e2b336c7cad3a831b592ced3f0"
    assert new.stored_version.content_sha256 == "418d7d65d227df9f9bdcd9195f86531dd99fa29e6c23b8804f5223425748c222"
    active = research.build_research_design(ROOT, replace(research.defaults(ROOT), profile="NACA2412"))
    prepared = research.prepare_aero(active, new, repo)
    table = c81mod.build_c81(c81mod.admitted_tables(json.loads(prepared.admission_json)))
    assert table.reynolds == (100000.0, 165000.0, 245000.0, 330000.0, 400000.0)
    assert table.mach == (0.07, 0.1, 0.31, 0.36)
    assert table.envelope["mach"] == [0.07, 0.36] and table.envelope["reynolds"] == [100000.0, 400000.0]
