"""Fold-cycle figures: contributions stay visible, events are numbered, every axis has units, blades are selectable."""
import csv
import io
import math
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from pyfoldable.application import figure_style
from pyfoldable.application import fold_cycle_views as views
from pyfoldable.application import research_design as research
from pyfoldable.dynamics import fold_cycle as fc
from pyfoldable.visualization import blade_surface as bs

ROOT = Path(__file__).resolve().parents[2]
STATIONS = ((0.144, 0.060, math.radians(20.0)), (0.27, 0.050, math.radians(14.0)), (0.388, 0.035, math.radians(11.0)))
FAST = fc.ShaftSchedule(operating_rpm=2400, rest_s=0.05, spinup_s=0.15, hold_s=0.5, spindown_s=0.4, end_rest_s=0.15)
PASSIVE = replace(fc.FoldMechanism(), spring_nm_per_rad=0.0, spring_preload_nm=0.0)


@pytest.fixture(scope="module")
def aero():
    aero = fc.AeroModel(strips=fc.strips_from_stations(STATIONS, 0.27))
    return fc.run_cycle(fc.CycleCase(0.27, 2, FAST, fc.FoldMechanism(), aero), sensitivity=False)


@pytest.fixture(scope="module")
def horiz():
    return fc.run_cycle(fc.CycleCase(0.27, 3, FAST, PASSIVE, fc.AeroModel(model="off"), gravity="shaft_horizontal"),
                        sensitivity=False)


def test_total_is_drawn_last_as_a_thin_dashed_text_line_over_the_contributions(aero):
    for fig in (views.contribution_figure(aero, "N_tension", 0), views.element_figure(aero, 0)):
        *parts, total = fig.data
        assert parts and total.line.dash == "dash" and total.line.color == figure_style.TEXT and total.line.width <= 2
        assert all(p.line.dash is None for p in parts)


def test_a_single_contribution_gives_a_note_instead_of_two_identical_traces(aero):
    fig = views.contribution_figure(aero, "V_axial", 0)
    assert len(fig.data) == 1
    assert any(views.CONTRIB_LABEL["aerodynamic"] in a.text for a in fig.layout.annotations)


def test_operating_focus_excludes_the_stop_impact_from_the_y_range(aero):
    a = views.arrays(aero)
    peak = float(np.abs(a["load_M_pin"][:, 0]).max())
    assert views.contribution_figure(aero, "M_pin", 0).layout.yaxis.range is None
    lo, hi = views.contribution_figure(aero, "M_pin", 0, focus="operating").layout.yaxis.range
    assert max(abs(lo), abs(hi)) < 0.5 * peak


def test_timeline_numbers_events_clusters_close_ones_and_labels_every_axis_with_units(aero):
    fig = views.timeline_figure(aero, 0)
    assert not any(a.textangle == -90 for a in fig.layout.annotations)
    marks = next(t for t in fig.data if t.name == "Olaylar")
    assert sum(marks.customdata) == len(aero["events"]) and len(marks.x) <= len(aero["events"])
    assert [str(n) for n in range(1, len(marks.x) + 1)] == list(marks.text)
    by = {t.name: t for t in fig.data}
    assert by["Aero pim momenti"].yaxis != by["Dış parça itkisi"].yaxis
    assert by["θ̈"].yaxis != by["θ̇"].yaxis
    assert not any(t.name and "/ 100" in t.name for t in fig.data)
    axes = [k for k in fig.layout.to_plotly_json() if k.startswith("yaxis")]
    assert len(axes) == 8 and all(fig.layout[k].title.text for k in axes)


def test_timeline_cursor_moves_without_rebuilding(aero):
    first = views.timeline_figure(aero, 0)
    cursor = views.timeline_figure(aero, 5).layout.shapes[-1]
    assert views.timeline_figure(aero, 5) is first and cursor.x0 == cursor.x1 == views.arrays(aero)["time_s"][5]


def test_blade_argument_reads_that_blades_column(horiz):
    a = views.arrays(horiz)
    th = next(t for t in views.timeline_figure(horiz, 0, blade=1).data if t.name == "θ")
    assert np.allclose(th.y, a["theta_deg"][:, 1]) and not np.allclose(th.y, a["theta_deg"][:, 0])
    fig = views.contribution_figure(horiz, "M_pin", 0, blade=1)
    grav = next(t for t in fig.data if t.name == views.CONTRIB_LABEL["gravity"])
    assert np.allclose(grav.y, a["contrib_gravity_M_pin_by_blade"][:, 1])
    assert np.allclose(fig.data[-1].y, a["load_M_pin"][:, 1])
    assert np.allclose(views.element_figure(horiz, 0, blade=2).data[-1].y, a["load_M_pin"][:, 2])
    res = next(t for t in views.energy_figure(horiz, blade=2).data if t.name == "Denge artığı")
    assert np.allclose(res.y, a["energy_residual_j_by_blade"][:, 2])


def test_series_csv_writes_every_blade(horiz):
    header = next(csv.reader(io.StringIO(views.series_csv(horiz))))
    assert {"theta_deg_blade1", "theta_deg_blade3", "load_M_pin_blade2"} <= set(header)
    assert "theta_deg_blade4" not in header


def test_unit_of_load_keys():
    assert views.unit_of("M_pin") == "N·m" and views.unit_of("V_axial") == "N"


def test_playback_draws_the_blades_translucent_so_the_connection_arrows_show(aero):
    active = research.build_research_design(ROOT, replace(research.defaults(ROOT), profile="NACA2412"))
    spec = bs.spec_from_design(active, next(f for f in active.design.airfoils if f.id == "NACA2412"))
    fig = views.playback(aero, spec, n_frames=3)
    assert fig.data[0].opacity == 0.45 and all(f.data[0].opacity == 0.45 for f in fig.frames)
