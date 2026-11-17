"""Gallery figures that no other view draws: polar families, convergence maps, envelope, overlays, archive, legacy."""
import json
import math
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from pyfoldable.application import gallery_figures as gf
from pyfoldable.application import polar_upload, provider_design_analysis as managed, research_design as research
from pyfoldable.coupled import postprocess

ROOT = Path(__file__).resolve().parents[2]
COUPLED = ROOT / "tests/fixtures/coupled"


def _axis_titles(fig):
    return [v["title"]["text"] for k, v in fig.layout.to_plotly_json().items()
            if k[:5] in ("xaxis", "yaxis") and v.get("title", {}).get("text")]


def _units(fig):
    titles = _axis_titles(fig)
    assert titles and all("[" in t and t.endswith("]") for t in titles), titles


@pytest.fixture()
def naca2412(monkeypatch):
    monkeypatch.setenv("PYFOLDABLE_PROVIDER_STORE", str(ROOT / "data/research_reference/axial_800_store"))
    repo = managed.application_provider_repository()
    family = next(f for f in repo.families if f.family_id == "research_axial_800_deploy_xfoil_v3:NACA2412")
    return research.build_research_design(ROOT, research.defaults(ROOT)), family, repo


def test_polar_family_figure_draws_every_admitted_cell(naca2412):
    active, family, repo = naca2412
    tables = polar_upload.inspect_polar_bundle(research.prepare_aero(active, family, repo).polar_run.payload).to_family()
    fig = gf.polar_family_figure(tables)
    assert len(fig.data) == 3 * len(tables.tables) == 60
    first = tables.tables[0]
    assert list(fig.data[0].x) == pytest.approx([math.degrees(a) for a in first.alpha_rad])
    assert list(fig.data[0].y) == pytest.approx(list(first.cl))
    assert list(fig.data[2].y) == pytest.approx([l / d for l, d in zip(first.cl, first.cd)])
    _units(fig)


@pytest.mark.parametrize("path", ["coupled_deploy_polars_20261112/convergence_map.json",
                                  "catalog_polars_20261116/convergence_prescreen.json",
                                  "catalog_polars_20261116/convergence_prescreen_high_camber_shifted.json",
                                  "catalog_polars_20261116/convergence_prescreen_naca0012.json"])
def test_convergence_heatmap_shows_every_failed_cell(path):
    rows = json.loads((ROOT / "reports" / path).read_text())
    fig = gf.convergence_heatmap(rows)
    cells = [z for trace in fig.data for line in trace.z for z in line]
    assert cells.count(0) == sum(not r["complete"] for r in rows)
    assert cells.count(1) == sum(r["complete"] for r in rows)
    _units(fig)


def test_envelope_map_marks_no_induction_coverage(naca2412):
    active, family, _ = naca2412
    fig = gf.envelope_map(active, family, rpms=(2000, 2400, 2800), inflows=(0, 14))
    z = {(y, x): v for y, line in zip(fig.data[0].y, fig.data[0].z) for x, v in zip(fig.data[0].x, line)}
    assert z[2400, 14] == 1 and z[2400, 0] == 0
    assert "indüksiyonsuz" in fig.layout.title.text
    _units(fig)


def test_bem_mechanism_figure_plots_angle_and_torques():
    samples = [{"time_s": t, "angle_rad": -1 + t, "rpm": 1000 + 100 * t, "centrifugal_torque_nm": t,
                "euler_torque_nm": -t, "dry_friction_torque_nm": 0.0} for t in (0.0, 0.1, 0.2)]
    row = {"mechanism": {"status": "computed", "report_text": json.dumps({"result": {"samples": samples}})}}
    fig = gf.bem_mechanism_figure(row)
    assert list(fig.data[0].y) == pytest.approx([math.degrees(s["angle_rad"]) for s in samples])
    assert len(fig.data) == 4
    _units(fig)


def test_bem_overlay_figure_overlays_radial_fields_and_totals(naca2412):
    active, family, repo = naca2412
    first = research.run_research(active, family, repo, None)
    other = research.build_research_design(ROOT, replace(research.defaults(ROOT), rpm=2600.0))
    second = research.run_research(other, family, repo, None)
    fig = gf.bem_overlay_figure([first, second])
    bars = [t for t in fig.data if t.type == "bar"]
    assert [b.y[0] for b in bars if b.xaxis == "x4"] == pytest.approx(
        [r["aerodynamics"]["thrust_n"] for r in (first, second)])
    assert len([t for t in fig.data if t.type == "scatter"]) == 6
    _units(fig)
    assert len([t for t in gf.bem_overlay_figure([first]).data if t.type == "scatter"]) == 3


def _coupled(tmp_path, name):
    run = tmp_path / name
    shutil.copytree(COUPLED / name, run)
    return postprocess.build_result(run, participant_outcome="finished", exit_codes={}, extraction_ok=True)


def test_coupled_overlay_aligns_two_records_on_the_event(tmp_path):
    rows = [_coupled(tmp_path, "release_30w"), _coupled(tmp_path, "release_30w_rbf")]
    fig = gf.coupled_overlay_figure(rows, "first_contact")
    series = rows[0]["series"]
    at = next(i for i, r in enumerate(series) if r["window"] == 13)  # flow.events: first contact of this fixture
    first = fig.data[0]
    assert first.x[at] == pytest.approx(0.0)
    assert first.x[0] == pytest.approx(series[0]["time_s"] - series[at]["time_s"])
    assert len(fig.data) == 6 and rows[1]["result_sha256"][:8] in fig.data[3].name
    _units(fig)
    never = {**rows[1], "series": [{**r, "latch_active": False} for r in rows[1]["series"]]}
    with pytest.raises(ValueError, match="Kilit açılışı"):
        gf.coupled_overlay_figure([rows[0], never], "release")


def test_archived_json_figure_knows_pr06d_and_falls_back_otherwise():
    fig = gf.archived_json_figure(ROOT / "reports/pr06d_opening_sensitivity.json")
    assert len(fig.data) == 4
    _units(fig)
    assert gf.archived_json_figure(ROOT / "reports/coupled_flow_20261112/wake_comparison.json") is None


def _status():
    """Tracked, untracked and ignored files; Python's own bytecode caches are not outputs of the generators."""
    out = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all", "--ignored"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if "__pycache__" not in line]


def test_a_legacy_example_that_exits_raises_an_ordinary_error(tmp_path):
    (tmp_path / "examples").mkdir()
    for part in ("configs", "data"):
        (tmp_path / part).mkdir()
    (tmp_path / "examples/run_prescribed_rpm_physics.py").write_text(
        "def main():\n    raise SystemExit('Reference propeller not found.')\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Reference propeller not found"):
        gf.legacy_pngs("physics", tmp_path)


@pytest.mark.parametrize("name", list(gf.LEGACY))
def test_legacy_pngs_run_in_a_temporary_folder_only(name):
    before = _status()
    pngs = gf.legacy_pngs(name, ROOT)
    assert pngs and all(data[:8] == b"\x89PNG\r\n\x1a\n" for _, data in pngs)
    assert _status() == before
