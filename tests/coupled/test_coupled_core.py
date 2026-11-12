"""Inert tests of the coupled route's pure functions (no solver is executed)."""
from dataclasses import replace
import json
import math
import os
from pathlib import Path

import pytest

from pyfoldable.application import research_design as research
from pyfoldable.coupled import c81 as c81mod, deck as deckmod
from pyfoldable.coupled.frames import (matrix_to_rotvec, relative_angle_about_z, rot_z, rotvec_to_matrix, matmul)
from pyfoldable.coupled.model import (CoupledCaseError, CoupledControls, CoupledMechanics, build_case, case_geometry)

ROOT = Path(__file__).resolve().parents[2]


def _tables():
    alpha = tuple(math.radians(a) for a in (-6, -4, -2, 0, 2, 4, 6, 8))
    out = []
    for re_value in (165000.0, 245000.0, 330000.0):
        for mach in (0.1, 0.31):
            out.append({"airfoil_id": "NACA2412", "reynolds": re_value, "mach": mach, "alpha_rad": alpha,
                        "cl": tuple(0.1 * i + re_value * 1e-7 + mach for i in range(8)),
                        "cd": tuple(0.01 + 0.001 * i for i in range(8)),
                        "cm": tuple(-0.05 + 0.001 * i for i in range(8))})
    return out


def test_c81_round_trip_is_exact_at_table_nodes():
    tables = _tables()
    table = c81mod.build_c81(tables)
    parsed = c81mod.parse_c81(table.text)
    for t in tables:
        for i, a in enumerate(t["alpha_rad"]):
            cl, cd, cm = c81mod.dust_interpolate(parsed, math.degrees(a), t["mach"], t["reynolds"])
            assert cl == pytest.approx(t["cl"][i], abs=1e-14)
            assert cd == pytest.approx(t["cd"][i], abs=1e-14)
            assert cm == pytest.approx(t["cm"][i], abs=1e-14)
    assert table.envelope["alpha_deg"] == [pytest.approx(-6.0), pytest.approx(8.0)]
    assert table.envelope["reynolds"] == [165000.0, 330000.0]


def test_dust_semantics_abort_outside_alpha_mach_but_extrapolate_reynolds():
    parsed = c81mod.parse_c81(c81mod.build_c81(_tables()).text)
    with pytest.raises(ValueError):
        c81mod.dust_interpolate(parsed, 8.5, 0.2, 200000.0)
    with pytest.raises(ValueError):
        c81mod.dust_interpolate(parsed, 0.0, 0.32, 200000.0)
    inside = c81mod.dust_interpolate(parsed, 0.0, 0.2, 330000.0)
    outside = c81mod.dust_interpolate(parsed, 0.0, 0.2, 400000.0)
    assert outside[0] > inside[0]  # linear extrapolation, not clamping: hence PyFoldable's audit


def test_c81_rejects_incomplete_or_regridded_input():
    tables = _tables()
    with pytest.raises(ValueError):
        c81mod.build_c81(tables[:-1])
    bad = [dict(t) for t in tables]
    bad[0]["alpha_rad"] = bad[0]["alpha_rad"][:-1]
    with pytest.raises(ValueError):
        c81mod.build_c81(bad)


def test_rotation_utilities():
    phi = (0.1, -0.2, 0.3)
    assert matrix_to_rotvec(rotvec_to_matrix(phi)) == pytest.approx(phi)
    assert relative_angle_about_z(rot_z(0.4), matmul(rot_z(-0.1), rot_z(0.4))) == pytest.approx(-0.1)


@pytest.fixture(scope="module")
def active():
    return research.build_research_design(ROOT, replace(research.defaults(ROOT), profile="NACA2412"))


def _mech(**kw):
    base = dict(distal_mass_kg=0.03, distal_cg_from_hinge_m=0.055, distal_inertia_cg_kg_m2=3e-5,
                source="unit-test demonstration assumption", declaration_kind="demonstration_assumption")
    base.update(kw)
    return CoupledMechanics(**base)


def test_geometry_keeps_hub_root_station_and_hinge_distinct(active):
    g = case_geometry(active)
    assert (g.hub_radius_m, g.root_radius_m, g.first_aero_radius_m, g.hinge_radius_m) == pytest.approx((0.09, 0.1, 0.144, 0.27))
    assert g.proximal_sections[0].radius_m == pytest.approx(0.144)
    assert g.proximal_sections[-1].radius_m == g.distal_sections[0].radius_m == pytest.approx(0.27)
    assert g.proximal_sections[-1].source == "hinge_interpolated"
    assert g.distal_sections[-1].radius_m == pytest.approx(0.388)


def test_case_validation_is_explicit(active):
    with pytest.raises(CoupledCaseError):
        build_case(active, _mech(source=""), CoupledControls())
    with pytest.raises(CoupledCaseError):
        build_case(active, _mech(initial_fold_rad=0.1), CoupledControls())
    with pytest.raises(CoupledCaseError):
        build_case(active, _mech(stop_angle_rad=0.05), CoupledControls())
    case = build_case(active, _mech(), CoupledControls())
    assert case.mechanics.hinge_inertia_kg_m2 == pytest.approx(3e-5 + 0.03 * 0.055 ** 2)
    assert case.dt_s == pytest.approx(math.radians(5.0) / case.omega_rad_s)


def test_deck_is_deterministic_and_uses_verified_conventions(active):
    case = build_case(active, _mech(initial_fold_rad=math.radians(-5), release_time_s=0.05), CoupledControls(duration_s=0.01))
    text = c81mod.build_c81(_tables()).text
    a = deckmod.generate_deck(case, text)
    b = deckmod.generate_deck(case, text)
    assert a == b and deckmod.deck_manifest(a) == deckmod.deck_manifest(b)
    mbd = a["structure/rotor.mbd"]
    assert "axial rotation" in mbd and "coupling, tight" in mbd and "double linear viscoelastic" in mbd
    assert "driven: 600, string, \"Time < 0.05\"" in mbd
    assert "method: ms, 0.6, 0.6;" in mbd
    dust_in = a["dust/dust.in"]
    assert "u_inf = (/ 0.0, 0.0, -14.0 /)" in dust_in and "ll_stall_regularisation = F" in dust_in
    assert "coupling_type = rbf" in a["dust/comps/blade1.in"]
    legacy = build_case(active, case.mechanics, CoupledControls(duration_s=0.01, aero_topology="split_rigid"))
    comp = deckmod.generate_deck(legacy, text)["dust/comps/blade1_distal.in"]
    assert "coupling_type = rigid" in comp and "coupling_node = (/ 0.0, 0.27, 0.0 /)" in comp
    vertices = json.loads(a["structure/adapter_config.json"])["vertices"]
    assert len({tuple(v) for v in vertices}) == len(vertices)  # one-to-one nearest-neighbour mapping
    xml = a["precice-config.xml"]
    assert "serial-implicit" in xml and "<acceleration:aitken>" in xml


def test_no_coupled_imports_in_application_without_toolchain(monkeypatch, tmp_path):
    monkeypatch.setenv("PYFOLDABLE_COUPLED_TOOLCHAIN", str(tmp_path / "missing.json"))
    from pyfoldable.coupled import toolchain
    r = toolchain.readiness()
    assert r.status == "invalid" or r.status == "not_installed"
    monkeypatch.delenv("PYFOLDABLE_COUPLED_TOOLCHAIN")
    monkeypatch.setattr(toolchain, "DEFAULT", tmp_path / "absent.json")
    assert toolchain.readiness().status == "not_installed"


def test_continuous_lifting_line_has_no_free_vortices_at_the_hinge(active):
    """Two separate lifting lines meeting at the hinge leave free end vortices that cancel only when
    exactly coincident; a static -0.5 deg fold alone raised thrust by ~25 % (spurious vortex pair).
    The default topology is one continuous DUST lifting line per blade with RBF coupling to static
    MBDyn nodes on each rigid segment; only one node spacing straddles the hinge."""
    case = build_case(active, _mech(initial_fold_rad=math.radians(-5)), CoupledControls())
    assert case.controls.aero_topology == "continuous_rbf"
    deck = deckmod.generate_deck(case, c81mod.build_c81(_tables()).text)
    comps = sorted(k for k in deck if k.startswith("dust/comps/") and k.endswith(".in") and "_nodes" not in k)
    assert comps == ["dust/comps/blade1.in", "dust/comps/blade2.in"]
    comp = deck["dust/comps/blade1.in"]
    assert "coupling_type = rbf" in comp and "coupling_node_file = ./comps/blade1_nodes.in" in comp
    spans = [float(line.split("=")[1]) for line in comp.splitlines() if line.startswith("span =")]
    assert min(spans) > 0.03 and abs(sum(spans) - (0.388 - 0.144)) < 1e-12   # stations only, no hinge section
    nodes = deckmod.coupling_nodes(case)
    blade = [n for n in nodes if n["blade"] == 0]
    radii = sorted(n["local"][1] for n in blade)
    gaps = [b - a for a, b in zip(radii, radii[1:])]
    assert max(gaps) - min(gaps) < 1e-12                                   # uniform grid
    inner = max(r for r in radii if r < 0.27); outer = min(r for r in radii if r > 0.27)
    assert abs((inner + outer) / 2 - 0.27) < 1e-12                         # hinge mid-way between nodes
    assert all((n["segment"] == "proximal") == (n["local"][1] < 0.27) for n in blade)
    files = deck["dust/comps/blade1_nodes.in"].split()
    assert len(files) == 3 * len(blade)
    mbd = deck["structure/rotor.mbd"]
    n_b = case.geometry.blade_count
    assert f"structural nodes: {2 + 2 * n_b + len(nodes)};" in mbd and f"rigid bodies: {1 + 2 * n_b};" in mbd
    for nd in nodes:  # no added mass: every coupling node is fully constrained to its segment body node
        assert f"joint: {nd['mbdyn_label']}, total joint,\n    {nd['body_label']}, position" in mbd                         # ground + coupling nodes
    vertices = json.loads(deck["structure/adapter_config.json"])["vertices"]
    assert len({tuple(v) for v in vertices}) == len(vertices) == len(nodes)


def test_rbf_weights_follow_dust_semantics():
    from pyfoldable.coupled.postprocess import rbf_weights
    nodes = [(0.0, 0.10, 0.0), (0.0, 0.12, 0.0), (0.0, 0.14, 0.0)]
    idx, w = rbf_weights(nodes, (0.02, 0.125, 0.001))       # chordwise/normal offsets scaled by 1e-3
    assert sorted(idx) == [1, 2] and abs(sum(w) - 1) < 1e-15
    assert w[idx.index(1)] == pytest.approx(0.015 / 0.02, rel=5e-3)   # inverse distance: nearer node heavier
