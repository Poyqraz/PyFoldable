"""GEOM-02 station contracts use synthetic geometry, never measured evidence."""
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path

import pytest

from pyfoldable.application.blade_stations import (
    MAX_STATION_UPLOAD_BYTES, StationBundleError, audit_station_bundle,
    export_station_bundle, parse_station_bundle,
)
from pyfoldable.application.design_draft import DesignDraftInputs, build_design_draft
from pyfoldable.core.airfoil import airfoil_coordinate_sha256
from pyfoldable.core.config import load_design_config
from pyfoldable.core.profile_catalog import load_project_airfoil

SOURCE = Path(__file__).resolve().parents[2] / "configs/designs/TIP_HINGED_250_CANONICAL.toml"


def document():
    return {"schema_version": 1, "units": {"length": "mm", "angle": "deg"},
        "diameter": 250., "hub_radius": 18., "airfoil_id": "NACA2412",
        "airfoil_coordinate_sha256": airfoil_coordinate_sha256(load_project_airfoil("NACA2412")),
        "provenance": {"kind": "declared_design", "reference": "synthetic test",
            "locator": "station table", "revision": "1"},
        "stations": [{"radius": 18., "chord": 28., "twist": 31.},
            {"radius": 100., "chord": 17., "twist": 10.},
            {"radius": 125., "chord": 8., "twist": 5.}]}


def raw(doc=None):
    return json.dumps(document() if doc is None else doc).encode("utf-8")


def inputs(**changes):
    return replace(DesignDraftInputs(diameter="250 mm", hub_radius="18 mm",
        hinge_radius="100 mm", blade_count=2, airfoil_id="NACA2412", chord_scale=1.,
        twist_scale=1., preview_fold_angle="0 deg", angular_speed="7100 rpm",
        forward_speed="0 m/s", air_density="1.225 kg/m^3", dynamic_viscosity="1.81e-5 Pa*s",
        temperature="288.15 K", pressure="101325 Pa"), **changes)


def audit(bundle, **changes):
    args = dict(diameter_m=.25, hub_radius_m=.018, hinge_radius_m=.1, airfoil_id="NACA2412")
    args.update(changes)
    return audit_station_bundle(bundle, **args)


def test_units_roundtrip_and_distinct_raw_and_canonical_identity():
    original = raw()
    bundle = parse_station_bundle(original)
    assert bundle.stations[0].radius_m == pytest.approx(.018)
    assert bundle.stations[0].twist_rad == pytest.approx(math.radians(31))
    assert bundle.raw_sha256 == hashlib.sha256(original).hexdigest()
    exported = export_station_bundle(bundle)
    assert bundle.canonical_sha256 == hashlib.sha256(exported.encode("utf-8")).hexdigest()
    roundtrip = parse_station_bundle(exported.encode("utf-8"))
    assert roundtrip.stations == bundle.stations
    assert roundtrip.canonical_sha256 == bundle.canonical_sha256
    assert roundtrip.raw_sha256 != bundle.raw_sha256
    compact = parse_station_bundle(json.dumps(document(), separators=(",", ":")).encode())
    assert compact.raw_sha256 != bundle.raw_sha256
    assert compact.canonical_sha256 == bundle.canonical_sha256


def test_complete_and_partial_span_preserve_unknown_collision_checks():
    complete = audit(parse_station_bundle(raw()))
    assert complete.span_complete and complete.hinge_covered
    assert complete.root_gap_m == complete.tip_gap_m == 0.
    assert complete.surface_path_clearance is None and complete.interblade_clearance is None
    doc = document()
    doc["stations"][0]["radius"] = 25.
    doc["stations"][-1]["radius"] = 122.5
    incomplete = audit(parse_station_bundle(raw(doc)))
    assert not incomplete.span_complete
    assert incomplete.root_gap_m == pytest.approx(.007)
    assert incomplete.tip_gap_m == pytest.approx(.0025)
    assert not audit(parse_station_bundle(raw(doc)), hinge_radius_m=.02).hinge_covered


@pytest.mark.parametrize("data", [b"", b"[]", b"null", b"\xff", b'{"x":NaN}',
    b'{"schema_version":1,"schema_version":1}', b"[" * 1100 + b"]" * 1100,
    b" " * (MAX_STATION_UPLOAD_BYTES + 1)])
def test_bad_json_is_controlled(data):
    with pytest.raises(StationBundleError):
        parse_station_bundle(data)


@pytest.mark.parametrize("change", [
    lambda d: d.update(schema_version=True), lambda d: d.update(unexpected=1),
    lambda d: d.update(diameter=True), lambda d: d.update(diameter=0),
    lambda d: d.update(hub_radius=-1), lambda d: d.update(hub_radius=126),
    lambda d: d["units"].update(length="ft"), lambda d: d["units"].update(angle="turn"),
    lambda d: d["stations"][0].update(radius=0),
    lambda d: d["stations"][0].update(radius=17.999999999),
    lambda d: d["stations"][-1].update(radius=126),
    lambda d: d["stations"][1].update(radius=18),
    lambda d: d["stations"][0].update(chord=-1),
    lambda d: d["stations"][0].update(chord=True),
    lambda d: d["stations"][0].update(twist=float("inf")),
    lambda d: d["stations"][0].update(twist="31"),
    lambda d: d["stations"][0].update(profile="other"),
    lambda d: d.update(stations=d["stations"][:1]),
    lambda d: d.update(stations=d["stations"] * 22),
    lambda d: d.update(airfoil_coordinate_sha256="bad"),
    lambda d: d["provenance"].update(kind="qualified"),
    lambda d: d["provenance"].update(reference=""),
    lambda d: d["provenance"].update(reference="bad\ud800"),
    lambda d: d["provenance"].update(kind="derived_geometry"),
])
def test_invalid_contract_and_actual_penetration_rejected(change):
    doc = document()
    change(doc)
    with pytest.raises(StationBundleError):
        parse_station_bundle(raw(doc))


def test_forged_bundle_and_changed_envelope_rejected():
    bundle = parse_station_bundle(raw())
    for forged in [replace(bundle, canonical_sha256="0" * 64),
        replace(bundle, stations=bundle.stations[1:]), replace(bundle, diameter_m=.3)]:
        with pytest.raises(StationBundleError, match="identity"):
            audit(forged)
    for change in ({"diameter_m": .3}, {"hub_radius_m": .019}, {"airfoil_id": "NACA0012"}):
        with pytest.raises(StationBundleError, match="bound|match"):
            audit(bundle, **change)


def test_station_override_preserves_si_values_profile_hash_and_source(tmp_path):
    before = SOURCE.read_bytes()
    bundle = parse_station_bundle(raw())
    result = build_design_draft(SOURCE, inputs(), station_bundle=bundle,
        airfoil_definition=load_project_airfoil("NACA2412"))
    path = tmp_path / "draft.toml"
    path.write_text(result.toml)
    model = load_design_config(path)
    assert SOURCE.read_bytes() == before
    assert [s.r_over_R for s in model.blade.stations] == pytest.approx([.144, .8, 1.])
    assert [s.chord_m for s in model.blade.stations] == pytest.approx([.028, .017, .008])
    assert model.metadata["station_bundle_sha256"] == bundle.canonical_sha256
    assert model.metadata["station_source_sha256"] == bundle.raw_sha256
    assert model.metadata["station_span_complete"] is True
    assert model.metadata["artifact_class"] == "unqualified_design_draft"


@pytest.mark.parametrize("changes", [{"chord_scale": 1.1}, {"twist_scale": .9},
    {"diameter": "300 mm"}, {"hub_radius": "19 mm"}, {"hinge_radius": "18 mm"},
    {"airfoil_id": "NACA0012"}])
def test_override_never_silently_scales_or_rebinds(changes):
    with pytest.raises(ValueError):
        build_design_draft(SOURCE, inputs(**changes), station_bundle=parse_station_bundle(raw()),
            airfoil_definition=load_project_airfoil("NACA2412"))


def test_override_requires_explicit_matching_profile():
    bundle = parse_station_bundle(raw())
    with pytest.raises(ValueError, match="explicit"):
        build_design_draft(SOURCE, inputs(), station_bundle=bundle)
    doc = document()
    doc["airfoil_coordinate_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="coordinate"):
        build_design_draft(SOURCE, inputs(), station_bundle=parse_station_bundle(raw(doc)),
            airfoil_definition=load_project_airfoil("NACA2412"))


def test_tolerances_allow_roundoff_but_not_small_physical_gaps_or_overlap():
    doc = json.loads(export_station_bundle(parse_station_bundle(raw())))
    hub = doc["hub_radius"]
    doc["stations"][0]["radius"] = math.nextafter(hub, 0.)
    assert audit(parse_station_bundle(raw(doc))).span_complete
    doc["stations"][0]["radius"] = hub - 1e-12
    with pytest.raises(StationBundleError, match="hub"):
        parse_station_bundle(raw(doc))
    doc["stations"][0]["radius"] = hub + 1e-12
    report = audit(parse_station_bundle(raw(doc)))
    assert not report.span_complete and report.root_gap_m > 0


def test_derived_source_preserves_parent_identity_without_promoting_evidence(tmp_path):
    original = parse_station_bundle(raw())
    doc = document()
    doc["stations"][1]["chord"] = 20
    doc["provenance"].update(kind="derived_geometry", parent_sha256=original.canonical_sha256)
    edited = parse_station_bundle(raw(doc))
    assert edited.canonical_sha256 != original.canonical_sha256
    assert edited.provenance.parent_sha256 == original.canonical_sha256
    result = build_design_draft(SOURCE, inputs(), station_bundle=edited,
        airfoil_definition=load_project_airfoil("NACA2412"))
    path = tmp_path / "derived.toml"
    path.write_text(result.toml)
    model = load_design_config(path)
    assert model.metadata["station_source_json"].encode("utf-8") == raw(doc)
    assert model.metadata["station_source_kind"] == "derived_geometry"
    assert model.metadata["artifact_class"] == "unqualified_design_draft"


def test_scaled_saved_draft_cannot_retain_stale_station_binding(tmp_path):
    original = build_design_draft(SOURCE, inputs(), station_bundle=parse_station_bundle(raw()),
        airfoil_definition=load_project_airfoil("NACA2412"))
    path = tmp_path / "imported.toml"
    path.write_text(original.toml)
    result = build_design_draft(path, inputs(chord_scale=1.1),
        airfoil_definition=load_project_airfoil("NACA2412"))
    target = tmp_path / "scaled.toml"
    target.write_text(result.toml)
    model = load_design_config(target)
    assert "station_bundle_sha256" not in model.metadata
    assert "station_span_complete" not in model.metadata
    assert model.metadata["source_design_sha256"] == original.draft_sha256
