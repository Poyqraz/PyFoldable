"""Analysis results mapped onto the lofted blade: BEM annuli and coupled lifting-line elements as spanwise strips."""
import math
import shutil
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from pyfoldable.application import research_design as research
from pyfoldable.coupled import postprocess
from pyfoldable.visualization import blade_results as br
from pyfoldable.visualization import blade_surface as bs

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "tests/fixtures/coupled"


@pytest.fixture(scope="module")
def mesh():
    active = research.build_research_design(ROOT, replace(research.defaults(ROOT), profile="NACA2412"))
    foil = next(f for f in active.design.airfoils if f.id == "NACA2412")
    return bs.loft(bs.spec_from_design(active, foil), n_side=32, dr=0.004, joint="relief")


def _bem_row():
    def el(i, a, b, dT):
        w = b - a
        return {"index": i, "inner_radius_m": a, "outer_radius_m": b, "width_m": w, "thrust_n": dT * w,
                "torque_nm": 0.1 * dT * w,
                "solution": {"radius_m": 0.5 * (a + b), "angle_of_attack_rad": math.radians(2 + i), "cl": 0.4 + 0.1 * i,
                             "cd": 0.01, "reynolds": 2e5, "mach": 0.2, "differential_thrust_n_m": dT,
                             "differential_torque_nm_m": 0.1 * dT, "axial_induced_velocity_m_s": 3.0,
                             "circulation_m2_s": 1.0, "inflow_angle_rad": 0.3}}
    return {"aerodynamics": {"radial_elements": [el(0, 0.144, 0.25, 100.0), el(1, 0.25, 0.32, 200.0),
                                                 el(2, 0.32, 0.388, 150.0)]}}


@pytest.fixture(scope="module")
def coupled_row(tmp_path_factory):
    run = tmp_path_factory.mktemp("c") / "run"
    shutil.copytree(FIX / "release_30w_rbf", run)
    return postprocess.build_result(run, participant_outcome="finished", exit_codes={}, extraction_ok=True)


def test_bem_fields_distinguish_per_unit_span_element_total_and_section_state():
    f = br.bem_fields(_bem_row())
    assert f["dthrust_per_span"].kind == "per_span" and f["dthrust_per_span"].unit == "N/m"
    assert f["thrust_element"].kind == "element_total" and f["thrust_element"].unit == "N"
    assert f["alpha"].kind == "section_state" and f["alpha"].unit == "°"
    assert [s[2] for s in f["dthrust_per_span"].strips] == [100.0, 200.0, 150.0]
    assert f["thrust_element"].strips[1][2] == pytest.approx(200.0 * 0.07)
    assert f["alpha"].strips[2][2] == pytest.approx(4.0)
    assert "kordal basınç dağılımı değildir" in f["thrust_element"].note


def test_face_values_colour_only_the_analysed_surface(mesh):
    vals = br.face_values(mesh, br.bem_fields(_bem_row())["dthrust_per_span"])
    side = np.isin(mesh.surface, ("upper", "lower", "te_face")) & np.isin(mesh.region, ("aero", "joint"))
    assert np.all(np.isfinite(vals[side]))
    assert np.all(np.isnan(vals[mesh.region == "undefined"]))            # no data -> no colour
    r = mesh.face_radius
    assert np.all(vals[side & (r > 0.26) & (r < 0.31)] == 200.0)


def test_coupled_strips_rebuild_exact_element_widths_from_the_section_intervals(coupled_row):
    f = br.coupled_fields(coupled_row, window=5, blade=0)
    el = f["fz_element"].strips
    assert len(el) == 16
    widths = [b - a for a, b, _ in el]
    assert sum(widths) == pytest.approx(0.388 - 0.144, abs=1e-9)        # strips cover the line, no gaps
    assert widths[0] == pytest.approx(0.016) and widths[-1] == pytest.approx(0.015)
    per = f["fz_per_span"].strips
    ix = {c: i for i, c in enumerate(coupled_row["radial_columns"])}
    rows = [r for r in coupled_row["radial"] if r[ix["window"]] == 5 and r[ix["blade"]] == 0]
    assert [s[2] for s in el] == pytest.approx([r[ix["dFz_n"]] for r in rows])
    assert per[0][2] == pytest.approx(rows[0][ix["dFz_n"]] / 0.016)
    assert f["fz_element"].kind == "element_total" and f["fz_per_span"].kind == "per_span"


def test_coupled_colour_range_is_fixed_over_all_accepted_windows(coupled_row):
    lo, hi = br.coupled_range(coupled_row, "fz_per_span")
    for w in (2, 15, 30):
        vals = [s[2] for b in (0, 1) for s in br.coupled_fields(coupled_row, w, b)["fz_per_span"].strips]
        assert lo <= min(vals) and max(vals) <= hi


def _layout(row, segments):
    from types import SimpleNamespace
    from pyfoldable.coupled import deck
    eps = row["run_definition"]["case"]["controls"]["elements_per_segment"]
    bounds = []
    for radii, total in segments(eps):
        n = deck._allocate_elements(tuple(SimpleNamespace(radius_m=r) for r in radii), total)
        for (a, b), k in zip(zip(radii, radii[1:]), n):
            bounds += [(a + j * (b - a) / k, a + (j + 1) * (b - a) / k) for j in range(k)]
    return bounds


def test_element_widths_follow_the_deck_allocation_for_both_topologies(coupled_row, tmp_path):
    g = coupled_row["run_definition"]["case"]["geometry"]
    st = sorted({s["radius_m"] for s in g["proximal_sections"] + g["distal_sections"] if s["source"] == "station"})
    want = _layout(coupled_row, lambda eps: [(st, 2 * eps)])                  # one continuous line (rbf)
    assert [v for b in br.element_bounds(coupled_row) for v in b] == pytest.approx([v for b in want for v in b])
    assert br.coupled_fields(coupled_row, 5, 0)["fz_per_span"].approximate_widths is False
    run = tmp_path / "split"
    shutil.copytree(FIX / "release_30w", run)
    split = postprocess.build_result(run, participant_outcome="finished", exit_codes={}, extraction_ok=True)
    gs = split["run_definition"]["case"]["geometry"]
    seg = lambda eps: [([s["radius_m"] for s in gs["proximal_sections"]], eps),   # noqa: E731
                       ([s["radius_m"] for s in gs["distal_sections"]], eps)]
    assert [v for b in br.element_bounds(split) for v in b] == pytest.approx([v for b in _layout(split, seg) for v in b])


def test_fallback_widths_are_flagged_as_approximate(coupled_row):
    import copy
    bad = copy.deepcopy(coupled_row)
    ix = {c: i for i, c in enumerate(bad["radial_columns"])}
    for r in bad["radial"]:
        r[ix["span_y_m"]] += 0.003                       # centres no longer match the deck layout
    f = br.coupled_fields(bad, 5, 0)["fz_per_span"]
    assert f.approximate_widths is True and "yaklaşık" in f.note


def test_faces_in_a_gap_between_strips_stay_uncoloured(mesh):
    f = br._field("x", "x", "N/m", "per_span", [(0.144, 0.2, 1.0), (0.25, 0.388, 2.0)], "t")
    vals = br.face_values(mesh, f)
    r = mesh.face_radius
    gap = (r > 0.205) & (r < 0.245) & np.isin(mesh.region, ("aero", "joint"))
    assert gap.any() and np.all(np.isnan(vals[gap]))
