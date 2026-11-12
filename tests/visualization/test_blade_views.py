"""3-D blade figure, linked radial plot and exports (geometry from the catalog, results as labelled strips)."""
import math
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
    assert _traces(fig, "Menteşe ekseni")
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
