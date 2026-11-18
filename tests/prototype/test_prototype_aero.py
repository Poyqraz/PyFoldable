"""Aerodynamic screening of the printable prototype: geometry conversion, the chord-dependent section family, polar
identity/provenance, the XFOIL trust boundary and a smoke BEM comparison (synthetic polars, never reported)."""
from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from pyfoldable.core import PolarFamily, PolarTable
from pyfoldable.core.airfoil import airfoil_coordinate_sha256
from pyfoldable.core.providers import PolarProviderUnavailableError
from pyfoldable.prototype import aero

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def ds():
    return aero.designs(ROOT)


def synthetic_family(d, chord_mm, alpha_deg=range(-12, 31, 2)):
    """Thin-airfoil-like coefficients over a wide grid: a test fixture only, not a polar of any real section."""
    foil = aero.section_airfoil(d, chord_mm)
    sha = airfoil_coordinate_sha256(foil)
    alpha = tuple(math.radians(a) for a in alpha_deg)
    tables = tuple(PolarTable(foil.id, re, m, alpha, tuple(2 * math.pi * (a + math.radians(2.0)) for a in alpha),
                              tuple(0.012 + 0.6 * a * a for a in alpha), tuple(-0.05 for _ in alpha),
                              "synthetic-test", "synthetic", {"airfoil_coordinate_sha256": sha})
                   for m in (0.0, 0.6) for re in (1e4, 1e6))
    return PolarFamily(tables)


@pytest.fixture(scope="module")
def schedules(ds):
    chords = aero.family_chords(ds.values())
    return {k: aero.schedule(d, {c: synthetic_family(d, c) for c in chords}) for k, d in ds.items()}


def test_geometries_follow_the_study_and_differ_only_inside_the_hinge_zone(ds):
    E, ref = ds["E"], ds["reference"]
    assert E.connection.axial_offset_mm == ref.connection.axial_offset_mm == 6.0
    assert E.section_identity == ref.section_identity == "NACA2412-te0.80mm-x0.50"
    for r in (33.02, 45.0, 150.0, 161.798):                           # outside 99 ± 45 mm: identical sections
        assert E.section(r) == pytest.approx(ref.section(r))
    (ce, te), (cr, tr) = E.section(99.0), ref.section(99.0)
    assert ce / cr == pytest.approx(0.85, rel=1e-3) and te / tr == pytest.approx(0.45, rel=1e-3)
    assert all(E.section(r)[1] < ref.section(r)[1] for r in (60.0, 80.0, 120.0, 140.0))


def test_blade_geometry_converts_mm_and_degrees_to_si(ds):
    d = ds["E"]
    b = aero.blade_geometry(d)
    assert b.diameter_m == pytest.approx(0.3302) and b.blade_count == 2 and b.hub_radius_m == pytest.approx(0.015)
    assert len(b.stations) == len(d.planform.stations)
    for s, (r, c, t) in zip(b.stations, d.planform.stations):
        assert s.r_over_R * b.radius_m * 1000 == pytest.approx(r)
        assert s.chord_m * 1000 == pytest.approx(c) and math.degrees(s.twist_rad) == pytest.approx(t)
        assert s.airfoil_id == d.section_identity


def test_printable_section_is_a_chord_dependent_family(ds):
    d = ds["reference"]
    a, b = aero.section_airfoil(d, 12.0), aero.section_airfoil(d, 30.0)
    for foil, chord in ((a, 12.0), (b, 30.0)):
        x = [p[0] for p in foil.coordinates]
        assert min(x) == pytest.approx(0.0, abs=1e-12) and max(x) == pytest.approx(1.0)
        te = foil.coordinates[0][1] - foil.coordinates[-1][1]
        assert te * chord == pytest.approx(0.8, rel=1e-6)                # fixed physical trailing edge, mm
    assert a.id != b.id and airfoil_coordinate_sha256(a) != airfoil_coordinate_sha256(b)
    assert a.id.startswith(d.section_identity)


def test_polar_grid_covers_the_what_if_envelope_without_induction(ds):
    rows = [r for d in ds.values() for r in aero.envelope_rows(d, d.operating.what_if_rpm, (0.0, max(aero.ADVANCE_RATIOS)))]
    assert min(r["reynolds"] for r in rows) > aero.REYNOLDS[0]
    assert max(r["reynolds"] for r in rows) < aero.REYNOLDS[-1]
    assert max(r["mach"] for r in rows) < aero.MACH[-1]


def test_schedule_places_each_chord_family_where_the_local_chord_equals_its_chord(ds, schedules):
    R = ds["E"].planform.tip_radius_mm
    for key, sch in schedules.items():
        d = ds[key]
        assert sch.anchors[0].r_over_R == pytest.approx(d.planform.stations[0][0] / R)
        assert sch.anchors[-1].r_over_R == pytest.approx(d.planform.stations[-1][0] / R)
        for anchor in sch.anchors:
            chord = float(anchor.family.airfoil_id.split("@c")[1].removesuffix("mm"))
            assert d.section(anchor.r_over_R * R)[0] == pytest.approx(chord, abs=0.01)
    by = {k: {a.family.airfoil_id: a.r_over_R for a in s.anchors} for k, s in schedules.items()}
    narrow = next(i for i in by["E"] if "@c23.00mm" in i)
    assert by["E"][narrow] < by["reference"][narrow]                   # E's chord ×0.85 reaches 23 mm further inboard


def test_family_identity_and_coordinate_provenance_are_enforced(ds):
    d = ds["E"]
    good = synthetic_family(d, 23.0)
    aero.check_family(d, 23.0, good)
    with pytest.raises(ValueError, match="does not belong"):
        aero.check_family(d, 30.0, good)                               # another chord: another section
    foreign = PolarFamily(tuple(replace(t, metadata={"airfoil_coordinate_sha256": "0" * 64}) for t in good.tables))
    with pytest.raises(ValueError, match="does not belong"):
        aero.check_family(d, 23.0, foreign)


def test_polar_record_round_trip_rejects_stale_coordinates(ds, tmp_path):
    d = ds["E"]
    record = {"families": [{"chord_mm": 23.0, "airfoil_id": aero.section_airfoil(d, 23.0).id,
                            "tables": [json.loads(json.dumps(asdict(t))) for t in synthetic_family(d, 23.0).tables]}]}
    assert set(aero.families_from_record(d, record)) == {23.0}
    stale = aero.designs(ROOT)["E"]
    stale = replace(stale, print_model=replace(stale.print_model, min_te_thickness_mm=0.6))
    with pytest.raises(ValueError, match="does not belong"):
        aero.families_from_record(stale, record)


def test_xfoil_route_refuses_an_unpinned_bundle(tmp_path):
    for name in ("bin/xfoil", "runtime/osmapDP.dat", "build/build-record.json"):
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_bytes(b"not the pinned bytes")
    for folder in (tmp_path, tmp_path / "missing"):
        with pytest.raises(PolarProviderUnavailableError, match="Pinned XFOIL"):
            with aero.xfoil_provider(ROOT, folder):
                pass


SAVED = ROOT / "reports/prototype_13in_20261118/aero/polars_printable_section.json"


@pytest.mark.skipif(not SAVED.is_file(), reason="report polars not generated")
def test_saved_polar_record_matches_the_route_and_foreign_records_are_refused(ds):
    record = json.loads(SAVED.read_text(encoding="utf-8"))
    aero.check_record(ROOT, record)
    assert set(aero.families_from_record(ds["E"], record)) == set(aero.family_chords(ds.values()))
    table = record["families"][0]["tables"][0]
    for change in ({"source": "synthetic-test"}, {"scenario_id": "other"}, {"reynolds": 12345.0}):
        forged = json.loads(json.dumps(record))
        forged["families"][0]["tables"][0] = {**table, **change}
        with pytest.raises(ValueError, match="does not match the current XFOIL route"):
            aero.check_record(ROOT, forged)
    stale = json.loads(json.dumps(record))
    stale["settings"]["n_crit"] = 5.0
    with pytest.raises(ValueError, match="settings"):
        aero.check_record(ROOT, stale)


def test_smoke_bem_comparison_keeps_failures_visible(ds, schedules):
    rows = aero.compare(ds, schedules, (6000.0,), (0.3, 3.0))
    assert len(rows) == 4                                              # every requested point stays in the table
    ok = {r["design"]: r for r in rows if r["J"] == 0.3}
    assert all(r["status"] == "ok" for r in ok.values())
    assert ok["E"]["thrust_n"] < ok["reference"]["thrust_n"]             # lower pitch in 0.33R–0.87R
    assert 0 < ok["E"]["ct"] and ok["E"]["eta"] is not None
    spans = {k: {round(e["r_mm"]): e for e in r["elements"]} for k, r in ok.items()}
    near = min(spans["E"], key=lambda r: abs(r - 99))
    assert spans["E"][near]["dT_dr_n_per_m"] < spans["reference"][near]["dT_dr_n_per_m"]
    far = [r for r in rows if r["J"] == 3.0]
    assert all(r["status"] == "failed" and r["reason"] and r["failure_kind"] and "elements" not in r for r in far)
    assert [d["both_usable"] for d in aero.deltas(rows)] == [True, False]


def test_clamped_converged_states_are_not_usable_and_signs_are_not_ratioed(ds):
    d = ds["reference"]
    narrow = aero.schedule(d, {c: synthetic_family(d, c, range(-2, 5, 2)) for c in aero.family_chords(ds.values())})
    failed = aero.run_point(d, narrow, 6000.0, 0.0)                     # fail-closed: the scan leaves −2…4°
    assert failed["status"] == "failed" and failed["failure_kind"] == "alpha outside polar data"
    clamped = aero.run_point(d, narrow, 6000.0, 0.0, bounds="clamp")
    assert clamped["status"] == "ok" and clamped["solution_clamped_elements"] > 0 and not aero.usable(clamped)
    base = {"rpm": 1.0, "J": 0.4, "bounds": "error", "status": "ok", "solution_clamped_elements": 0,
            "figure_of_merit": None, "zone_thrust_n": 0.0}
    rows = [{**base, "design": "E", "thrust_n": -0.5, "power_w": 4.0, "eta": None},
            {**base, "design": "reference", "thrust_n": -0.1, "power_w": 0.0, "eta": None}]
    (row,) = aero.deltas(rows)
    assert row["both_usable"] and row["d_thrust_pct"] is None and row["d_power_pct"] is None and row["d_eta"] is None


@pytest.mark.skipif(not (aero.PREFLIGHT / "bin/xfoil").is_file(), reason="operator XFOIL bundle not installed")
def test_pinned_xfoil_generates_one_printable_section_cell_with_provenance(ds):
    before = os.environ.get("OSMAP")
    d = ds["E"]
    with aero.xfoil_provider(ROOT) as (provider, decl):
        assert os.environ["OSMAP"].endswith("runtime/osmapDP.dat")
        (batch,) = aero.generate_family(provider, decl, d, 23.0, reynolds=(60e3,), mach=(0.15,))
    assert os.environ.get("OSMAP") == before                           # the pinned runtime does not leak
    assert not batch.failures
    family = aero.merged_family((batch,))
    table = family.tables[0]
    assert table.metadata["airfoil_coordinate_sha256"] == airfoil_coordinate_sha256(aero.section_airfoil(d, 23.0))
    assert table.source == "xfoil-subprocess:6.99" and (table.reynolds, table.mach) == (60e3, 0.15)
    aero.check_family(d, 23.0, family)
