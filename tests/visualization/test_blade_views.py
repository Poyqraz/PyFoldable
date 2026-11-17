"""3-D blade figure, linked radial plot and exports (geometry from the catalog, results as labelled strips)."""
import math
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from pyfoldable.application import blade_views as bv
from pyfoldable.application import research_design as research
from pyfoldable.visualization import blade_results as br
from pyfoldable.visualization import blade_surface as bs
from pyfoldable.visualization import fold_interference as fi

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "application"))
from test_figure_style import _contrast, _luminance  # noqa: E402


@pytest.fixture(scope="module")
def mesh():
    active = research.build_research_design(ROOT, replace(research.defaults(ROOT), profile="NACA2412"))
    foil = next(f for f in active.design.airfoils if f.id == "NACA2412")
    return bs.loft(bs.spec_from_design(active, foil), n_side=24, dr=0.008, joint="relief")


def _field():
    return br._field("dthrust_per_span", "İtki / birim yarıçap dT/dr", "N/m", "per_span",
                     [(0.144, 0.25, 100.0), (0.25, 0.32, 200.0), (0.32, 0.388, 150.0)], "test")


def _traces(fig, name):
    return [t for t in fig.data if (t.name or "").startswith(name)]


def test_geometry_only_view_shows_parts_placeholders_hub_and_hinge(mesh):
    fig = bv.blade_figure(mesh, fold_deg=-20.0)
    assert _traces(fig, "Sabit iç parça") and _traces(fig, "Hareketli dış parça")
    ph = _traces(fig, "Yüzey verisi yok")
    assert ph and all(t.opacity < 0.5 for t in ph)
    hub = _traces(fig, "Göbek")
    assert hub and "yalnız yarıçap" in hub[0].hovertemplate
    hinge = _traces(fig, "Menteşe ekseni")
    assert hinge and hinge[0].line.color != bv.JOINT            # stays distinct from the joint region it crosses
    assert fig.layout.scene.aspectmode == "data"


def test_result_colouring_uses_the_given_fixed_range_and_names_the_kind(mesh):
    fig = bv.blade_figure(mesh, fold_deg=0.0, field=_field(), crange=(0.0, 300.0))
    col = _traces(fig, "Sonuç")
    assert col and col[0].intensitymode == "cell"
    assert (col[0].cmin, col[0].cmax) == (0.0, 300.0)
    assert "N/m" in col[0].colorbar.title.text and "birim açıklık" in col[0].colorbar.title.text.lower()
    assert np.all(np.isfinite(np.asarray(col[0].intensity)))           # uncoloured faces live in another trace
    hover = _traces(fig, "Şerit değerleri")[0]
    assert len(hover.x) == 3 * mesh.spec.blade_count and "N/m" in hover.hovertemplate


def test_rotor_relative_view_rotates_everything_by_minus_psi(mesh):
    psi = math.radians(40.0)
    rot = bv.blade_figure(mesh, rotor_azimuth_rad=psi)
    fixed = bv.blade_figure(mesh, rotor_azimuth_rad=psi, view_rotation_rad=-psi)
    ref = bv.blade_figure(mesh)
    a, b, c = (np.array([f.data[0].x, f.data[0].y]) for f in (rot, fixed, ref))
    assert not np.allclose(a, c) and np.allclose(b, c, atol=1e-9)


def test_contact_points_are_marked(mesh):
    rep = fi.fold_contacts(mesh.spec, joint="relief", fold_min_deg=-90.0, step_deg=3.0)
    fig = bv.blade_figure(mesh, fold_deg=rep.interference_free_deg, contacts=rep)
    marks = _traces(fig, "Temas noktası")
    assert marks and len(marks[0].x) >= 1 and "distal_1" in marks[0].hovertext[0]
    # only contacts of the shown pose are marked (a later possible contact would float in space)
    later = fi.fold_contacts(mesh.spec, joint="relief", fold_min_deg=-180.0, step_deg=3.0)
    shown = bv.blade_figure(mesh, fold_deg=later.interference_free_deg, contacts=later,
                            contact_angle_deg=later.interference_free_deg)
    texts = _traces(shown, "Temas noktası")[0].hovertext
    assert all(f"{later.interference_free_deg:.1f}°" in s for s in texts)


def test_radial_link_figure_marks_the_selected_radius_and_uses_strip_steps():
    fig = bv.radial_link_figure(_field(), selected_radius_m=0.30, crange=(0.0, 300.0), hinge_radius_m=0.27)
    step = fig.data[0]
    assert list(step.x[:2]) == pytest.approx([144.0, 250.0]) and list(step.y[:2]) == [100.0, 100.0]
    assert any(abs(s.x0 - 300.0) < 1e-9 for s in fig.layout.shapes)


def test_exports_carry_geometry_and_the_selected_field(mesh):
    stl = bv.stl_bytes(mesh, fold_deg=-10.0).decode()
    n_aero = int(np.isin(mesh.region, ("aero", "joint")).sum())
    assert stl.startswith("solid") and stl.count("facet normal") == n_aero * mesh.spec.blade_count
    vtk = bv.vtk_bytes(mesh, fold_deg=-10.0, field=_field()).decode()
    assert "POLYGONS" in vtk and "CELL_DATA" in vtk and "dthrust_per_span" in vtk and "region_id" in vtk


def test_exports_from_explicit_transforms_equal_the_direct_exports(mesh):
    from pyfoldable.application import blade_ui
    tf = bv.default_transforms(mesh, -10.0)
    assert blade_ui._stl_from_transforms(mesh, tf) == bv.stl_bytes(mesh, fold_deg=-10.0)
    assert blade_ui._vtk_from_transforms(mesh, tf, _field()) == bv.vtk_bytes(mesh, fold_deg=-10.0, field=_field())


def test_bem_rotation_playback_turns_with_plus_omega_and_says_it_is_explanatory(mesh):
    fig = bv.bem_rotation_figure(mesh, field=_field(), crange=(0.0, 300.0), rpm=2400.0, thrust_n=43.6,
                                 torque_nm=3.28, power_w=824.0, n_frames=24)
    assert len(fig.frames) == 24
    tips = [next(t for t in f.data if t.name == "Kanat 1 ucu") for f in fig.frames]
    angles = [math.atan2(-t.x[0], t.y[0]) for t in tips]            # psi measured from +Y toward -X (+Omega about +Z)
    assert angles[1] > angles[0] and 0.0 < angles[6] - angles[0] < math.pi
    text = fig.frames[6].layout.annotations[0].text
    assert "açıklayıcı" in text and "RPM" in text and "ψ" in text and "ms" in text and "yavaş" in text
    labels = [b.label for m in fig.layout.updatemenus for b in m.buttons]
    assert {"▶", "❚❚", "0,25×", "1×", "2×"} <= set(labels)
    assert len(fig.layout.sliders[0].steps) == 24
    arrow = next(t for t in fig.data if t.name == "İtki (rotor toplamı)")
    assert "43,6" in arrow.hovertext and "+z" in arrow.hovertext
    spin = next(t for t in fig.data if (t.name or "").startswith("Dönüş yönü"))
    assert "3,28" in spin.hovertext and "824" in spin.hovertext


def test_playback_event_buttons_jump_to_named_frames(mesh):
    frames = [{"name": str(k), "label": f"{k}", "text": f"f{k}", "transforms": bv.default_transforms(mesh, 0.0, 0.1 * k),
               "field": None} for k in range(5)]
    fig = bv.playback_figure(mesh, frames, events={"İlk temas": "3"})
    jump = next(b for m in fig.layout.updatemenus for b in m.buttons if b.label == "İlk temas")
    assert list(jump.args[0]) == ["3"]


def _hex(colour):
    return "#" + "".join(c * 2 for c in colour[1:]) if len(colour) == 4 else colour


def _drawn_colours(fig):
    """Fixed line/marker colours (colour-scaled values are arrays and skipped) and cone colourscale stops."""
    out = []
    for t in list(fig.data) + [t for f in fig.frames for t in f.data]:
        line, marker = getattr(t, "line", None), getattr(t, "marker", None)
        out += [c for c in (line and line.color, marker and marker.color, marker and marker.line and marker.line.color)
                if isinstance(c, str)]
        if t.type == "cone":
            out += [stop for _, stop in t.colorscale]
    return out + [s.line.color for s in fig.layout.shapes if s.line.color]


def test_markers_and_lines_stay_visible_on_the_dark_app_background(mesh):
    figs = (bv.blade_figure(mesh, field=_field(), crange=(0.0, 300.0), selected_radius_m=0.30),
            bv.radial_link_figure(_field(), selected_radius_m=0.30, crange=(0.0, 300.0), hinge_radius_m=0.27),
            bv.bem_rotation_figure(mesh, field=_field(), crange=(0.0, 300.0), rpm=2400.0, thrust_n=43.6, n_frames=4))
    dim = {c: round(_contrast(_hex(c)), 2) for fig in figs for c in _drawn_colours(fig) if _contrast(_hex(c)) < 3.0}
    assert not dim


def _frames(mesh, n=5, **extra):
    return [{"name": str(k), "label": f"{k}", "transforms": bv.default_transforms(mesh, 0.0, 0.1 * k), "field": None,
             "text": "Öngörülen hareket (mekanik model) · t = 0,1234 s · 2400 RPM · θ = -12,3° · θ̇ = 4,5 rad/s · "
                     "N = 120 N · V_t = 3,4 N · M_z = 0,12 N·m · M_t = -0,075 N·m", **extra} for k in range(n)]


def test_many_playback_events_wrap_into_rows_and_the_long_note_wraps(mesh):
    events = {f"Olay {k}": str(k % 5) for k in range(13)}
    fig = bv.playback_figure(mesh, _frames(mesh), events=events)
    rows = [m for m in fig.layout.updatemenus if any(b.label.startswith("Olay") for b in m.buttons)]
    assert len(rows) == math.ceil(13 / 5) and all(len(m.buttons) <= 5 for m in rows)
    assert [b.label for m in rows for b in m.buttons] == list(events)          # time order kept
    assert len({m.y for m in rows}) == len(rows) and all(m.y < -0.02 for m in rows)   # stacked below the slider
    note = fig.layout.annotations[0].text
    assert "<br>" in note and "M_t = -0,075 N·m" in note
    assert "<br>" in fig.frames[2].layout.annotations[0].text


# Rendered extents below each control's y anchor, measured in headless Edge (Plotly default font and pads):
# the slider reaches 104 px; a button row is drawn from 9 to 42 px.
SLIDER_PX, BUTTON_TOP_PX, BUTTON_PX = 104, 9, 42


@pytest.mark.parametrize("styled", [False, True])
@pytest.mark.parametrize("n_events", [0, 4, 13])
def test_event_rows_clear_the_slider_and_each_other_in_pixels(mesh, n_events, styled):
    events = {f"Olay {k}": str(k % 5) for k in range(n_events)}
    fig = bv.playback_figure(mesh, _frames(mesh), events=events, height=580,
                             static_traces=bv._scene_arrows(mesh.spec) if styled else ())
    if styled:   # the app shows playbacks through figure_style.apply (research_ui._plot)
        from pyfoldable.application import figure_style
        margin_b = fig.layout.margin.b
        fig = figure_style.apply(fig)
        assert fig.layout.margin.b == margin_b
    m = fig.layout.margin
    plot_h = fig.layout.height - m.t - m.b
    slider_bottom = -fig.layout.sliders[0].y * plot_h + SLIDER_PX
    tops = sorted(-u.y * plot_h for u in fig.layout.updatemenus if any(b.label.startswith("Olay") for b in u.buttons))
    assert len(tops) == math.ceil(n_events / 5)
    assert all(t + BUTTON_TOP_PX >= slider_bottom for t in tops)
    assert all(b - a >= BUTTON_PX - BUTTON_TOP_PX for a, b in zip(tops, tops[1:]))
    assert max([slider_bottom] + [t + BUTTON_PX for t in tops]) <= m.b       # nothing cut off at the bottom
    bare = bv.playback_figure(mesh, _frames(mesh), height=580).layout
    assert plot_h == bare.height - bare.margin.t - bare.margin.b              # rows add height, not squeeze the scene


def test_tip_marker_stays_visible_in_the_light_html_export(mesh):
    tip = next(t for t in bv.playback_figure(mesh, _frames(mesh)).data if t.name == "Kanat 1 ucu").marker.color
    for bg in ("#07111F", "#E5ECF6", "#FFFFFF"):      # app page, Plotly default scene wall and paper
        hi, lo = sorted((_luminance(tip), _luminance(bg)), reverse=True)
        assert (hi + 0.05) / (lo + 0.05) >= 3.0, bg


def test_frame_mesh_opacity_is_applied_and_defaults_to_opaque(mesh):
    see_through = bv.playback_figure(mesh, _frames(mesh, mesh_opacity=0.45))
    assert see_through.data[0].opacity == 0.45 and all(f.data[0].opacity == 0.45 for f in see_through.frames)
    assert bv.playback_figure(mesh, _frames(mesh)).data[0].opacity is None
