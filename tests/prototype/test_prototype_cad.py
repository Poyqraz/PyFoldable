"""Solid model, mass properties, full-travel clearance and exports of the printable prototype (needs the [cad] extra)."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

b3d = pytest.importorskip("build123d")

from pyfoldable.prototype import cad, checks, export, mass  # noqa: E402
from pyfoldable.prototype import design as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def base():
    return pd.default_design(ROOT)


@pytest.fixture(scope="module")
def parts(base):
    return cad.build(base)


def test_parts_are_single_valid_solids_with_the_joint_features(parts, base):
    for shape in (parts.proximal, parts.distal, *parts.hardware.values()):
        assert len(shape.solids()) == 1 and shape.is_valid() and shape.volume > 0
    c = base.connection
    (p0, p1), (q0, q1) = base.lug_bands_mm
    bb = parts.distal.bounding_box()
    assert bb.min.Y == pytest.approx(c.hinge_radius_mm - c.boss_radius_mm, abs=0.05)   # distal lug reaches inboard
    assert bb.max.Y == pytest.approx(base.planform.tip_radius_mm, abs=1e-3)
    # the pin hole: a point on the axis inside each lug band is outside both solids, one at the boss rim inside
    px, py = parts.pin_axis
    inside = lambda s, p: s.is_inside(b3d.Vector(*p))  # noqa: E731
    assert not inside(parts.proximal, (px, py, 0.5 * (p0 + p1)))
    assert not inside(parts.distal, (px, py, 0.5 * (q0 + q1)))
    r_mid = 0.5 * (base.hole_diameter_mm / 2 + c.boss_radius_mm)
    assert inside(parts.proximal, (px, py + r_mid, 0.5 * (p0 + p1)))
    assert inside(parts.distal, (px, py - r_mid, 0.5 * (q0 + q1)))
    # swept reliefs: nothing of the proximal above its band and nothing of the distal below its band near the pin
    assert not inside(parts.proximal, (px - r_mid, py - r_mid, p1 + 0.2))
    assert not inside(parts.distal, (px + r_mid, py + r_mid, q0 - 0.2))
    # stop: nose (distal) and pad (proximal) share the seat plane y = r_j ahead of the pin
    x0, x1 = parts.meta["stop_x_mm"]
    xm, zm = 0.5 * (x0 + x1), 0.5 * (p0 + p1)
    assert inside(parts.proximal, (xm, py - 0.5, zm)) and inside(parts.distal, (xm, py + 0.5, zm))
    assert x1 < px - base.relief_radius_mm + 1e-9


def test_trailing_edge_is_thickened_to_the_printable_minimum(base):
    chord = base.planform.stations[-1][1]
    prof = cad.printable_profile(base, chord)
    assert (prof[0, 1] - prof[-1, 1]) * chord == pytest.approx(base.print_model.min_te_thickness_mm, rel=1e-6)
    le = int(np.argmin(prof[:, 0]))
    raw = cad.printable_profile(pd.with_changes(base, **{"print_model.min_te_thickness_mm": 0.0}), chord)
    assert np.allclose(prof[:le + 1][prof[:le + 1, 0] < base.print_model.te_blend_start],
                       raw[:le + 1][raw[:le + 1, 0] < base.print_model.te_blend_start])     # untouched ahead of the blend


def test_inertia_follows_the_tensor_convention_used_by_the_loads():
    box = b3d.Box(10, 20, 30).rotate(b3d.Axis.Z, 30)
    V, _, c, I = mass.solid_props(box)
    a = math.radians(30)
    R = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
    Ib = np.diag([(20 ** 2 + 30 ** 2) / 12, (10 ** 2 + 30 ** 2) / 12, (10 ** 2 + 20 ** 2) / 12]) * V
    assert np.allclose(I, R @ Ib @ R.T, rtol=1e-6)
    p = mass.MassProps(2.0, (1.0, 2.0, 3.0), tuple(map(tuple, I / V)), V, "t")
    J = p.second_moments()                                    # ∫ r rᵀ dm from the tensor about the CG
    assert J[0, 1] == pytest.approx(2.0 * 1.0 * 2.0 - (I / V)[0, 1])


def test_mass_properties_seat_the_distal_on_the_stop(parts, base):
    mp = mass.properties(parts)
    rho = 1.24e-3
    assert mp["distal"].mass_g == pytest.approx(rho * parts.distal.volume)          # solid infill: exact
    assert mp["fold"]["chordwise_cg_offset_mm"] > 0                                 # CG aft of the pin
    assert mp["blade"].mass_g == pytest.approx(mp["proximal"].mass_g + mp["distal"].mass_g + mp["pin_set"].mass_g)
    half = pd.with_changes(base, **{"print_model.infill_fraction": 0.5})
    # the thin blade is all perimeter walls (infill has no effect); the hub sector has a core
    assert mass.printed(parts.distal, half).mass_g == pytest.approx(mp["distal"].mass_g)
    assert mass.printed(parts.proximal, half).mass_g < mp["proximal"].mass_g


def test_backward_fold_moves_the_tip_to_the_trailing_edge_and_forward_rotation_hits_the_stop(parts):
    tip = lambda s: s.bounding_box().max.Y  # noqa: E731
    folded = parts.distal_at(-30.0)
    c = folded.center()
    assert c.X > parts.distal.center().X + 5.0                     # toward +x: the trailing edge
    assert tip(folded) < tip(parts.distal)
    assert checks.exact_distance(parts, 2.0)["proximal"] == 0.0     # past the open stop: nose into the pad
    assert parts.distal_at(2.0).intersect(parts.proximal).volume > 0


def test_column_clearance_agrees_with_exact_distances(parts):
    sw = checks.sweep(parts)
    ang = np.array(sw["angles_deg"])
    gap = np.array(sw["gap_mm"])
    # where the column method says clear, the exact 3-D distance is positive and not larger than the vertical gap
    k = int(np.argmin(abs(ang + 30)))
    assert gap[k] > 0
    exact = checks.exact_distance(parts, ang[k])["proximal"]
    assert 0 < exact <= gap[k] + 0.3
    # where it reports interference, the solids really intersect
    k = int(np.argmin(gap))
    assert gap[k] < 0 and checks.exact_distance(parts, ang[k])["proximal"] == 0.0
    # designed contact at the open stop, off the pad by 2°
    assert checks.exact_distance(parts, 0.0)["proximal"] == 0.0
    assert checks.exact_distance(parts, -2.0)["proximal"] > 0.0


def test_5_5_mm_offset_does_not_clear_the_template_twist_and_reports_the_needed_offset(parts, base):
    """Owner target δ ≈ 5–6 mm on the 13-inch template planform: the backward fold sweeps the distal across the
    proximal, so the offset must exceed the overlapping twisted sections' height; the check says how much."""
    sw = checks.sweep(parts)
    assert not sw["full_travel_clear"] and 0 < sw["clear_travel_deg"] < 180
    assert sw["required_offset_mm"] > base.connection.axial_offset_mm + 3.0
    assert sw["required_offset_with_play_mm"] >= sw["required_offset_mm"]


def test_raising_the_offset_to_the_reported_value_clears_the_travel(base):
    first = checks.sweep(cad.build(base))
    need = math.ceil(first["required_offset_mm"] * 2) / 2
    again = checks.sweep(cad.build(pd.with_changes(base, **{"connection.axial_offset_mm": need})))
    assert again["body_clear"] and again["min_gap_mm"] >= base.connection.body_clearance_mm - 0.05


def test_the_stop_nose_is_the_folded_stop_and_a_shallower_nose_folds_further(parts, base):
    """Points ahead of the pin sweep the outboard half-plane while folding back and return over the proximal near
    180°: the nose meets the proximal there, which bounds the travel unless the nose is made shallower."""
    sw = checks.sweep(parts)
    assert sw["folded_stop_deg"] is not None and 120 < sw["folded_stop_deg"] < 180
    shallow = checks.sweep(cad.build(pd.with_changes(base, **{"connection.nose_depth_mm": 2.0})))
    assert shallow["folded_stop_deg"] is None or shallow["folded_stop_deg"] > sw["folded_stop_deg"]


def test_full_depth_lugs_engage_their_blades_and_thin_mid_lugs_are_flagged(base):
    """Default lugs span from each blade's far surface over the boss to the interface; at a large offset, 4 mm lugs
    placed mid-way only graze the distal blade (thin eccentric neck) and the printability check says so."""
    for delta in (5.5, 9.5):
        d = pd.with_changes(base, **{"connection.axial_offset_mm": delta})
        eng = checks.lug_engagement(d)
        assert min(eng.values()) == pytest.approx(1.0)
        assert d.lug_bands_mm[0][0] == pytest.approx(d.body_band_at_pin_mm("proximal")[0])
        assert d.lug_bands_mm[1][1] == pytest.approx(d.body_band_at_pin_mm("distal")[1])
    thin = pd.with_changes(base, **{"connection.axial_offset_mm": 9.5, "connection.lug_thickness_proximal_mm": 4.0,
                                    "connection.lug_thickness_distal_mm": 4.0})
    assert checks.lug_engagement(thin)["distal"] < 0.6
    rows = [r for r in checks.printability(thin, {}) if r["check"].startswith("Lug–kanat")]
    assert any(not r["ok"] for r in rows)
    assert any("Lug kalınlığı" in e for e in pd.validate(pd.with_changes(base, **{"connection.lug_interface_z_mm": -2.5})))


def test_export_load_table_uses_the_owner_case_with_aero_at_the_maximum_speed(parts, base):
    """At the owner's maximum speed the table carries the owner's aero forces; enough drag unseats the distal."""
    mp = mass.properties(parts)
    d = pd.with_changes(base, **{"operating.max_rpm": 4000.0, "operating.distal_drag_n": 40.0,
                                 "operating.distal_aero_radius_mm": 140.0})
    p2 = cad.Parts(d, parts.proximal, parts.distal, parts.hardware, parts.pin_axis, parts.meta)
    ev = {"parts": p2, "mass": mp, "sweep": checks.sweep(parts), "alignment": checks.alignment(d, parts),
          "printability": [{"check": "—", "value": "", "ok": True, "note": ""}]}
    rep = export.evaluate_for_export(p2, {}, ev)
    owner = [r for r in rep["load_table"] if r["owner"]]
    assert len(owner) == 1 and owner[0]["rpm"] == 4000.0 and owner[0]["aero"] and not owner[0]["seated"]
    assert all(r["seated"] for r in rep["load_table"] if not r["owner"])
    assert "owner max + aero" in export.summary(d, rep)


def test_joint_play_model(base):
    p = checks.joint_play(base)
    c = base.connection
    tp, td = base.lug_thicknesses_mm
    assert p["tilt_rad"] == pytest.approx(min(c.hole_clearance_mm / td + c.hole_clearance_mm / tp,
                                              c.lug_gap_mm / c.boss_radius_mm))
    tight = pd.with_changes(base, **{"connection.lug_gap_mm": 0.1})
    assert checks.joint_play(tight)["tip_droop_mm"] < p["tip_droop_mm"]


def test_export_writes_millimetre_step_and_meshes_that_read_back(parts, tmp_path):
    out = export.export_candidate(parts, tmp_path)
    for name in export.PRINTABLE:
        assert (tmp_path / "step" / f"{name}.step").stat().st_size > 0
        assert (tmp_path / "stl" / f"{name}.stl").stat().st_size > 0
        assert (tmp_path / "3mf" / f"{name}.3mf").stat().st_size > 0
    step = (tmp_path / "step" / "distal.step").read_text(errors="ignore")
    assert "MILLI" in step.upper()
    back = b3d.import_step(str(tmp_path / "step" / "distal.step"))
    assert back.volume == pytest.approx(parts.distal.volume, rel=1e-4)
    y_max = parts.distal.bounding_box().max.Y
    raw = (tmp_path / "stl" / "distal.stl").read_bytes()               # binary STL: 80 + 4 + 50 per triangle
    n = int(np.frombuffer(raw[80:84], "<u4")[0])
    tri = np.frombuffer(raw[84:84 + 50 * n], np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]))
    assert len(raw) == 84 + 50 * n and tri["v"][:, :, 1].max() == pytest.approx(y_max, abs=0.05)   # mm, not m
    import re
    import zipfile
    with zipfile.ZipFile(tmp_path / "3mf" / "distal.3mf") as z:
        model = next(z.read(nm).decode() for nm in z.namelist() if nm.endswith(".model"))
    assert re.search(r'unit="millimeter"', model)
    ys = [float(v) for v in re.findall(r'<vertex[^>]* y="([-0-9.eE+]+)"', model)]
    assert max(ys) == pytest.approx(y_max, abs=0.05)
    for f in ("assembly_drawing.pdf", "summary.md", "assembly_instructions.md", "hardware_list.csv", "design.json",
              "report.json", "README.md", "SHA256SUMS", "step/assembly_deployed.step"):
        assert (tmp_path / f).exists(), f
    assert len(out["files"]) == len((tmp_path / "SHA256SUMS").read_text().splitlines())
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "Physical qualification: **false**" in text and "azami devir" in text
