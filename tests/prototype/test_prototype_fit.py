"""Measurement prototype: fit record intake, model update from measured fit/play/friction/stop, hinge-zone shaping."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from pyfoldable.prototype import checks, fit
from pyfoldable.prototype import design as pd

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def kit_design():
    d = pd.default_design(ROOT, twist_scale=0.6)
    return pd.with_changes(d, **{"connection.axial_offset_mm": 9.5, "print_model.printer": "Bambu Lab P1S",
                                 "print_model.filament": "Eco Smart Standard PLA"})


@pytest.fixture(scope="module")
def pred(kit_design):
    return fit.predictions(kit_design, lever_mm=30.0, fit_masses_g=(9.0, 6.0))


def _record(pred, **over):
    rec = {k: None for k in fit.FIELDS}
    rec.update(schema=fit.SCHEMA, kit_design_sha256=pred["kit_design_sha256"], print_printer="Bambu Lab P1S",
               print_material_family="PLA", print_filament_product="Eco Smart Standard PLA", print_slicer="Bambu Studio",
               pin_grip_length_mm=pred["lug_thicknesses_mm"][0] + pred["lug_thicknesses_mm"][1] + 0.3 + 1.0,
               washer_stack_mm=1.0, print_nozzle_mm=0.4, print_layer_mm=0.2, print_walls=3,
               print_infill_fraction=1.0, pin_measured_diameter_mm=2.98,
               coupon_fit=["girmez", "sıkı", "akıcı", "boşluklu", "boşluklu"],
               coupon_hole_mm=[None, 3.02, 3.12, None, None], fit_pair_clearance_mm=0.2,
               lug_thickness_proximal_mm=6.6, lug_thickness_distal_mm=7.0, axial_float_mm=0.12,
               tilt_load_n=2.0, tilt_range_at_tab_mm=0.72, friction_breakaway_n=0.5, stop_gap_mm=0.0,
               stop_seats=True, folded_stop_deg=142.0, mass_fit_proximal_g=8.1, mass_fit_distal_g=5.7, notes="",
               measurement_resolution_mm=0.02, repeat_count=1, axial_float_spread_mm=None, tilt_range_spread_mm=None)
    rec.update(over)
    if "pin_grip_length_mm" not in over:          # hardware consistent with the measured lugs and float by default
        rec["pin_grip_length_mm"] = (rec["lug_thickness_proximal_mm"] + rec["lug_thickness_distal_mm"]
                                     + rec["washer_stack_mm"] + (rec["axial_float_mm"] or 0.0))
    return json.dumps(rec, ensure_ascii=False)


def test_template_lists_every_field_and_an_unfilled_template_is_rejected(pred):
    tpl = json.loads(fit.template(pred))
    assert set(tpl) == set(fit.FIELDS) and tpl["schema"] == fit.SCHEMA
    assert tpl["kit_design_sha256"] == pred["kit_design_sha256"]
    with pytest.raises(fit.RecordError, match="print_printer"):
        fit.parse(json.dumps(tpl), pred)


def test_a_complete_record_parses(pred):
    rec = fit.parse(_record(pred), pred)
    assert rec["fit_pair_clearance_mm"] == 0.2 and rec["stop_seats"] is True


@pytest.mark.parametrize("over, match", [
    ({"schema": "other/1"}, "schema"),
    ({"kit_design_sha256": "0" * 64}, "kit"),
    ({"extra_field": 1}, "extra_field"),
    ({"axial_float_mm": -0.1}, "axial_float_mm"),
    ({"tilt_range_at_tab_mm": float("nan")}, "tilt_range_at_tab_mm"),
    ({"coupon_fit": ["akıcı"]}, "coupon_fit"),
    ({"coupon_fit": ["akıcı", "x", "akıcı", "akıcı", "akıcı"]}, "coupon_fit"),
    ({"fit_pair_clearance_mm": 0.25}, "fit_pair_clearance_mm"),
    ({"stop_seats": "yes"}, "stop_seats"),
    ({"print_walls": 2.5}, "print_walls"),
])
def test_bad_records_fail_closed(pred, over, match):
    with pytest.raises(fit.RecordError, match=match):
        fit.parse(_record(pred, **over), pred)


def test_oversized_or_non_object_input_is_refused(pred):
    with pytest.raises(fit.RecordError):
        fit.parse("[]", pred)
    with pytest.raises(fit.RecordError):
        fit.parse(" " * (fit.MAX_BYTES + 1), pred)


def test_coupon_step_is_the_smallest_running_fit(pred):
    assert fit.coupon_step(pred["coupon_steps_mm"], ["girmez", "sıkı", "akıcı", "akıcı", "boşluklu"]) == 0.2
    assert fit.coupon_step(pred["coupon_steps_mm"], ["girmez"] * 5) is None


def test_measured_play_separates_axial_float_from_tilt(pred):
    rec = fit.parse(_record(pred), pred)
    play = fit.measured_play(rec, pred)
    assert play["axial_mm"] == pytest.approx(0.12)
    assert play["tilt_rad"] == pytest.approx((0.72 - 0.12) / (2 * 30.0))


def test_apply_carries_the_measured_play_into_the_clearance_model(kit_design, pred):
    rec = fit.parse(_record(pred), pred)
    out = fit.apply(kit_design, rec, pred, deploy_moment_per_rpm2=2.0e-4)
    d = out["design"]
    assert d.connection.hole_clearance_mm == 0.2
    assert d.connection.measured_axial_play_mm == pytest.approx(0.12)
    assert d.connection.measured_tilt_deg == pytest.approx(math.degrees(0.01))
    assert d.connection.play_record_sha256 == out["record_sha256"] and len(out["record_sha256"]) == 64
    assert pd.validate(d) == []
    jp = checks.joint_play(d)
    assert jp["source"].startswith("ölçüm") and jp["tilt_rad"] == pytest.approx(0.01)
    assert jp["tilt_rad"] < checks.joint_play(kit_design)["tilt_rad"]          # the model play is a worst case
    torque = 0.5 * 30.0
    assert out["friction_torque_nmm"] == pytest.approx(torque)
    assert out["self_deploy_rpm"] == pytest.approx(math.sqrt(torque / 2.0e-4))
    assert not out["warnings"]
    names = [r["quantity"] for r in out["rows"]]
    assert {"Eksenel boşluk", "Eğilme boşluğu", "Açık stop aralığı", "Sürtünme momenti"} <= set(names)


def test_apply_warns_when_the_stop_does_not_seat_or_the_coupon_disagrees(kit_design, pred):
    rec = fit.parse(_record(pred, stop_gap_mm=0.3, stop_seats=False, fit_pair_clearance_mm=0.1), pred)
    text = " ".join(fit.apply(kit_design, rec, pred)["warnings"])
    assert "stop" in text.lower() and "kupon" in text.lower()


def test_measured_play_needs_its_record_and_both_values(kit_design):
    half = pd.with_changes(kit_design, **{"connection.measured_tilt_deg": 1.0})
    assert any("ölçülen" in e.lower() for e in pd.validate(half))


def test_hinge_zone_shaping_scales_only_near_the_joint(kit_design):
    plain = kit_design.planform
    shaped = pd.planform_from_template(ROOT, twist_scale=0.6, hinge_zone_mm=30.0, hinge_zone_center_mm=99.0,
                                       hinge_chord_factor=0.7, hinge_twist_factor=0.5)
    d = pd.with_changes(kit_design, planform=shaped)
    assert pd.validate(d) == []
    c0, t0 = kit_design.section(99.0)
    c1, t1 = d.section(99.0)
    assert c1 == pytest.approx(0.7 * c0) and t1 == pytest.approx(0.5 * t0)
    for r in (40.0, 66.04, 132.08, 150.0):                      # outside the zone: the template planform
        assert d.section(r) == pytest.approx(kit_design.section(r))
    assert d.identity != kit_design.identity and plain.hinge_zone_mm == 0.0
    off = pd.with_changes(d, **{"connection.hinge_radius_mm": 110.0})
    assert any("ortalanmalı" in e for e in pd.validate(off))


def test_kit_fixture_parts_and_export(kit_design, tmp_path):
    pytest.importorskip("build123d")
    from pyfoldable.prototype import cad
    parts = cad.build(kit_design)
    prox, dist, lever = cad.fit_fixture(parts)
    assert prox.is_valid() and dist.is_valid() and lever == pytest.approx(30.0, abs=0.5)
    out = fit.export_kit(kit_design, tmp_path, clearances=(0.2,))
    names = {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()}
    assert {"README.md", "fit_record_template.json", "predictions.json", "SHA256SUMS",
            "3mf/hole_coupon.3mf", "3mf/fit_proximal_c0p20.3mf", "3mf/fit_distal_c0p20.3mf",
            "step/fit_proximal_c0p20.step", "step/hole_coupon.step"} <= names
    pred = json.loads((tmp_path / "predictions.json").read_text(encoding="utf-8"))
    assert pred["fit_pair_clearances_mm"] == [0.2] and pred["lever_mm"] == pytest.approx(lever)
    assert out["predictions"]["fit_masses_g"][0] > 0
    tpl = json.loads((tmp_path / "fit_record_template.json").read_text(encoding="utf-8"))
    assert tpl["kit_design_sha256"] == kit_design.identity


def test_study_estimates_are_not_clipped_at_the_current_offset(kit_design):
    from pyfoldable.prototype import study
    th = [-float(a) for a in range(2, 181)]
    sw = {"angles_deg": th, "gap_mm": [2.0] * len(th), "gap_play_mm": [1.0 if -a < 100 else -0.4 for a in th]}
    curve = {c["travel_deg"]: c for c in study.required_by_travel(kit_design, sw, (90, 140))}
    delta = kit_design.connection.axial_offset_mm
    assert curve[90]["required_mm"] == pytest.approx(delta + 0.5 - 2.0)          # margin shows: below δ
    assert curve[90]["required_with_play_mm"] == pytest.approx(delta - 1.0)       # worst-case gap 1.0 governs
    assert curve[140]["required_with_play_mm"] == pytest.approx(delta + 0.4)      # play governs beyond 100°


@pytest.mark.parametrize("text", [
    '{"print_nozzle_mm": 1' + "0" * 400 + "}",                  # an int too large for a float
    '{"fit_pair_clearance_mm": 1' + "0" * 400 + "}",
    "[" * 5000 + "]" * 5000,                                     # nesting beyond the parser's recursion limit
])
def test_hostile_json_is_a_record_error_not_a_crash(pred, text):
    with pytest.raises(fit.RecordError):
        fit.parse(text, pred)


def test_blank_required_text_and_zero_or_inconsistent_play_are_flagged(kit_design, pred):
    with pytest.raises(fit.RecordError, match="print_printer"):
        fit.parse(_record(pred, print_printer="   "), pred)
    rec = fit.parse(_record(pred, axial_float_mm=0.3, tilt_range_at_tab_mm=0.1), pred)
    assert any("Δ" in w for w in fit.apply(kit_design, rec, pred)["warnings"])
    rec = fit.parse(_record(pred, axial_float_mm=0.0, tilt_range_at_tab_mm=0.0), pred)
    assert any("sıfır" in w for w in fit.apply(kit_design, rec, pred)["warnings"])


def test_applying_a_record_to_another_design_warns_loudly(kit_design, pred):
    rec = fit.parse(_record(pred), pred)
    other = pd.with_changes(kit_design, **{"connection.hinge_radius_mm": 105.0})
    warnings = fit.apply(other, rec, pred)["warnings"]
    assert any("kit tasarımı değil" in w for w in warnings)
    assert not fit.apply(kit_design, rec, pred)["warnings"]


def test_exploration_candidates_drop_play_measured_on_another_design(kit_design, pred):
    from pyfoldable.prototype import explore
    measured = fit.apply(kit_design, fit.parse(_record(pred), pred), pred)["design"]
    cand = explore.candidate_design(measured, ROOT, {"connection.axial_offset_mm": 6.0})
    assert cand.connection.play_record_sha256 is None and cand.connection.measured_tilt_deg is None
    assert explore.candidate_design(measured, ROOT, {}).connection.play_record_sha256 is not None


def test_measured_play_fields_are_validated_as_a_set(kit_design):
    only_hash = pd.with_changes(kit_design, **{"connection.play_record_sha256": "a" * 64})
    assert pd.validate(only_hash) and checks.joint_play(only_hash)["source"].startswith("model")
    bad_hash = pd.with_changes(kit_design, **{"connection.measured_axial_play_mm": 0.1, "connection.measured_tilt_deg": 1.0,
                                              "connection.play_record_sha256": "z" * 64})
    assert pd.validate(bad_hash)
    text = pd.with_changes(kit_design, **{"connection.measured_axial_play_mm": "0.1", "connection.measured_tilt_deg": 1.0,
                                          "connection.play_record_sha256": "a" * 64})
    assert pd.validate(text)                                     # an error, not a TypeError


def test_narrow_hinge_zones_are_refused_and_loft_sampling_follows_the_zone(kit_design):
    from pyfoldable.prototype import cad
    narrow = pd.with_changes(kit_design, planform=pd.planform_from_template(
        ROOT, twist_scale=0.6, hinge_zone_mm=6.0, hinge_zone_center_mm=99.0, hinge_twist_factor=0.5))
    assert any("yarı genişliği" in e for e in pd.validate(narrow))
    zone = pd.with_changes(kit_design, planform=pd.planform_from_template(
        ROOT, twist_scale=0.6, hinge_zone_mm=12.0, hinge_zone_center_mm=99.0, hinge_twist_factor=0.5))
    radii = cad._radii(zone, 13.5, 99.0)
    assert max(b - a for a, b in zip(radii, radii[1:])) <= 12.0 / 4 + 1e-9


def test_committed_kit_belongs_to_the_current_b_design():
    from pyfoldable.prototype import explore, study
    path = ROOT / "reports/prototype_13in_20261118/fit_kit_B/predictions.json"
    pred = json.loads(path.read_text(encoding="utf-8"))
    base = pd.with_changes(pd.default_design(ROOT), **{"connection.axial_offset_mm": study.REPORT_OFFSET_MM})
    b = pd.with_changes(explore.candidate_design(base, ROOT, study.B_PARAMS), name="13in-B")
    assert pred["kit_design_sha256"] == b.identity          # regenerate the kit when the design record changes


def test_direct_play_sets_the_verdict_with_an_expanded_uncertainty_margin(kit_design, pred):
    rec = fit.parse(_record(pred, measurement_resolution_mm=0.02, repeat_count=3, axial_float_spread_mm=0.03,
                            tilt_range_spread_mm=0.12, lug_thickness_proximal_mm=pred["lug_thicknesses_mm"][0] - 0.15,
                            lug_thickness_distal_mm=pred["lug_thicknesses_mm"][1]), pred)
    u = fit.uncertainty(rec, pred)
    reading = 0.02 / math.sqrt(12) * math.sqrt(2)
    assert u["axial_mm"] == pytest.approx(math.hypot(reading, 0.03 / fit.D2[3]))
    assert u["tilt_rad"] == pytest.approx(math.hypot(math.hypot(reading, 0.12 / fit.D2[3]), u["axial_mm"]) / 60.0)
    assert u["print_z_mm"] == pytest.approx(max(0.2 / math.sqrt(12), 0.15 / math.sqrt(3)))
    d = fit.apply(kit_design, rec, pred)["design"]
    assert d.connection.measured_play_basis == "direct"
    jp = checks.joint_play(d)
    assert jp["source"].startswith("ölçüm (doğrudan") and jp["k"] == 2.0
    s = 24.0
    margin = 2.0 * math.sqrt(u["axial_mm"] ** 2 + (s * u["tilt_rad"]) ** 2 + 2 * u["print_z_mm"] ** 2)
    g = checks.gap_with_play(1.0, s, jp)
    assert g == pytest.approx(1.0 - jp["axial_play_mm"] - jp["tilt_rad"] * s - margin)


def test_transferred_play_supports_exploration_but_the_verdict_keeps_the_model(kit_design, pred):
    rec = fit.parse(_record(pred), pred)
    other = pd.with_changes(kit_design, **{"connection.axial_offset_mm": 6.0})
    d = fit.apply(other, rec, pred)["design"]
    assert d.connection.measured_play_basis == "transferred"
    jp = checks.joint_play(d)
    model = checks.joint_play(other)
    assert jp["source"].startswith("model") and jp["tilt_rad"] == pytest.approx(model["tilt_rad"])
    assert jp["transferred"]["tilt_rad"] == pytest.approx(0.01) and jp["transferred"]["axial_play_mm"] == pytest.approx(0.12)
    assert checks.gap_with_play(1.0, 24.0, jp) == pytest.approx(1.0 - model["axial_play_mm"] - model["tilt_rad"] * 24.0)
    assert checks.gap_with_play(1.0, 24.0, jp["transferred"]) > checks.gap_with_play(1.0, 24.0, jp)


def test_committed_e_kit_belongs_to_the_current_e_design():
    from pyfoldable.prototype import explore, study
    pred = json.loads((ROOT / "reports/prototype_13in_20261118/fit_kit_E/predictions.json").read_text(encoding="utf-8"))
    base = pd.with_changes(pd.default_design(ROOT), **{"connection.axial_offset_mm": study.REPORT_OFFSET_MM})
    e = pd.with_changes(explore.candidate_design(base, ROOT, study.E_PARAMS), name="13in-E")
    assert pred["kit_design_sha256"] == e.identity
    assert pred["lug_thicknesses_mm"] == pytest.approx(list(e.lug_thicknesses_mm))


def test_folded_dimensions_by_fold_angle(kit_design):
    from pyfoldable.prototype import study
    th = [-float(a) for a in range(2, 181)]
    sw = {"angles_deg": th, "gap_mm": [2.0] * len(th), "gap_play_mm": [1.0] * len(th), "folded_stop_deg": 144.0}
    rows = {r["fold_deg"]: r for r in study.folded_dimensions(kit_design, sw, (0, 90, 140, 180))}
    R = kit_design.planform.tip_radius_mm
    assert rows[0]["envelope_diameter_mm"] == pytest.approx(2 * R, abs=1.0)
    assert rows[140]["envelope_diameter_mm"] < rows[90]["envelope_diameter_mm"] < rows[0]["envelope_diameter_mm"]
    assert rows[140]["reachable"] and not rows[180]["reachable"]                 # beyond the folded stop
    assert rows[140]["width_mm"] > 0 and rows[140]["length_mm"] < 2 * R


def test_uncertainty_edge_cases_and_folded_stop_boundary(kit_design, pred):
    from pyfoldable.prototype import study
    one = fit.uncertainty(fit.parse(_record(pred, repeat_count=1, axial_float_spread_mm=0.5), pred), pred)
    assert one["axial_mm"] == pytest.approx(0.02 / math.sqrt(12) * math.sqrt(2))     # one reading: no spread term
    many = fit.uncertainty(fit.parse(_record(pred, repeat_count=30, axial_float_spread_mm=0.3), pred), pred)
    assert many["axial_mm"] >= 0.3 / fit.D2[10] - 1e-12                              # capped d2: conservative
    th = [-float(a) for a in range(2, 181)]
    sw = {"angles_deg": th, "gap_mm": [2.0] * len(th), "gap_play_mm": [1.0] * len(th), "folded_stop_deg": 140.0}
    rows = {r["fold_deg"]: r for r in study.folded_dimensions(kit_design, sw, (110, 140))}
    assert rows[110]["reachable"] and not rows[140]["reachable"]     # the nose has already penetrated at the stop angle
    empty = {"angles_deg": th, "gap_mm": [float("inf")] * len(th), "gap_play_mm": [float("inf")] * len(th)}
    assert study.required_by_travel(kit_design, empty, (60,))[0]["required_mm"] is None


def test_a_pin_size_change_brings_its_matched_pin_set(kit_design):
    from pyfoldable.prototype import explore
    d = explore.candidate_design(kit_design, ROOT, {"connection.pin_diameter_mm": 4.0})
    assert d.hardware.pin_nominal_mm == 4.0 and d.hardware.washer_id_mm == pytest.approx(4.3)
    assert not [e for e in pd.validate(d) if "Pim seti" in e]


def test_committed_f1s_kit_belongs_to_the_strengthened_f1_with_its_pin_set():
    from pyfoldable.prototype import explore, study
    pred = json.loads((ROOT / "reports/prototype_13in_20261118/fit_kit_F1S/predictions.json").read_text(encoding="utf-8"))
    d = pd.with_changes(explore.candidate_design(pd.default_design(ROOT), ROOT, study.F1S_PARAMS), name="13in-F1S")
    assert pred["kit_design_sha256"] == d.identity and pred["pin_diameter_mm"] == 4.0
    assert d.hardware.pin_nominal_mm == 4.0 and d.connection.axial_offset_mm == 6.5
    assert pred["folded_stop_deg"] >= -d.connection.stowed_angle_deg                  # the stronger stop keeps the fold


def test_fit_fixture_lug_faces_are_flat_bed_planes(kit_design):
    pytest.importorskip("build123d")
    from pyfoldable.prototype import cad
    prox, dist, _ = cad.fit_fixture(cad.build(kit_design))
    (p0, p1), (q0, q1) = kit_design.lug_bands_mm
    pb, db = prox.bounding_box(), dist.bounding_box()
    assert pb.min.Z == pytest.approx(p0, abs=1e-3)       # proximal: washer-seat face is the bottom plane
    assert db.max.Z == pytest.approx(q1, abs=1e-3)       # distal: washer-seat face is the top plane (prints inverted)


def test_kit_exports_a_pair_for_every_coupon_step_and_the_design_clearance(kit_design):
    from pyfoldable.prototype import fit
    assert fit.kit_clearances(kit_design) == (0.0, 0.1, 0.2, 0.3, 0.4)
    odd = pd.with_changes(kit_design, **{"connection.hole_clearance_mm": 0.45})
    assert fit.kit_clearances(odd) == (0.0, 0.1, 0.2, 0.3, 0.4, 0.45)


@pytest.mark.parametrize("over, reason", [
    ({"print_material_family": "ASA"}, "ASA"),
    ({"print_layer_mm": 0.16}, "katman"),
    ({"print_filament_product": "Another PLA"}, "filament"),
    ({"print_printer": "Bambu Lab X1C"}, "yazıcı"),
])
def test_a_specimen_from_another_material_or_process_is_transferred_evidence(kit_design, pred, over, reason):
    out = fit.apply(kit_design, fit.parse(_record(pred, **over), pred), pred)
    assert out["basis"] == "transferred" and any(reason in w for w in out["warnings"])
    assert out["design"].connection.measured_process and reason.lower() in " ".join(out["process_differences"]).lower()


def test_the_matching_process_is_direct_and_names_the_process(kit_design, pred):
    out = fit.apply(kit_design, fit.parse(_record(pred), pred), pred)
    assert out["basis"] == "direct" and not out["process_differences"]
    assert "Bambu Lab P1S" in out["design"].connection.measured_process and "PLA" in out["design"].connection.measured_process


def test_hardware_stack_consistency_with_the_measured_float(kit_design, pred):
    tp, td = pred["lug_thicknesses_mm"]
    rec = fit.parse(_record(pred, lug_thickness_proximal_mm=tp, lug_thickness_distal_mm=td,
                            pin_grip_length_mm=tp + td + 1.0 + 0.6, axial_float_mm=0.12), pred)
    warnings = fit.apply(kit_design, rec, pred)["warnings"]
    assert any("tutma boyu" in w for w in warnings)                       # grip predicts 0.6 mm float, 0.12 measured
    short = fit.parse(_record(pred, lug_thickness_proximal_mm=tp, lug_thickness_distal_mm=td,
                              pin_grip_length_mm=tp + td + 0.8), pred)
    assert any("kısa" in w for w in fit.apply(kit_design, short, pred)["warnings"])


def test_print_handoff_package_is_print_oriented_labelled_and_prefilled(kit_design, tmp_path):
    pytest.importorskip("build123d")
    import zipfile
    import xml.etree.ElementTree as ET
    out = fit.export_handoff(kit_design, tmp_path, clearances=(0.2,))
    names = {p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()}
    assert {"BASKI_REHBERI.md", "MONTAJ_VE_DONANIM.md", "BASKI_VE_OLCUM_KAYDI.md", "olcum_kaydi.json",
            "predictions.json", "SHA256SUMS", "3mf/01_kupon.3mf", "3mf/02_cift_c0p20.3mf",
            "stl/01_kupon.stl", "stl/02_cift_c0p20_proksimal.stl", "stl/02_cift_c0p20_distal.stl"} <= names
    ns = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
    with zipfile.ZipFile(tmp_path / "3mf/02_cift_c0p20.3mf") as z:
        root = ET.fromstring(z.read(next(n for n in z.namelist() if n.endswith(".model"))))
    objects = root.findall(".//m:object", ns)
    items = root.findall(".//m:build/m:item", ns)
    named = {o.get("id"): o.get("name") for o in objects if o.get("name")}
    tag = kit_design.name.replace("13in-", "")
    assert root.get("unit") == "millimeter" and len(items) == 2
    assert sorted(named[i.get("objectid")] for i in items) == sorted([f"{tag}_cift_c0.20_proksimal",
                                                                      f"{tag}_cift_c0.20_distal"])
    zs = [float(v.get("z")) for o in objects for v in o.findall(".//m:vertex", ns)]
    assert min(zs) == pytest.approx(0.0, abs=1e-3)                          # on the bed
    rec = json.loads((tmp_path / "olcum_kaydi.json").read_text(encoding="utf-8"))
    assert rec["print_printer"] == "Bambu Lab P1S" and rec["print_filament_product"] == "Eco Smart Standard PLA"
    assert rec["print_nozzle_mm"] is None and rec["print_layer_mm"] is None and rec["axial_float_mm"] is None
    guide = (tmp_path / "BASKI_REHBERI.md").read_text(encoding="utf-8")
    assert "01_kupon" in guide and "önerilen" in guide.lower() and "kullanılan" in guide.lower()
    assert out["predictions"]["kit_design_sha256"] == kit_design.identity


def test_reported_setting_changes_make_the_evidence_transferred(kit_design, pred):
    out = fit.apply(kit_design, fit.parse(_record(pred, print_changes="X-Y delik telafisi +0.1"), pred), pred)
    assert out["basis"] == "transferred" and any("ayar" in r for r in out["process_differences"])
    assert fit.apply(kit_design, fit.parse(_record(pred, print_changes="  "), pred), pred)["basis"] == "direct"


def test_a_correct_assembly_with_groove_slack_does_not_warn(kit_design, pred):
    tp, td = pred["lug_thicknesses_mm"]
    rec = fit.parse(_record(pred, lug_thickness_proximal_mm=tp, lug_thickness_distal_mm=td,
                            pin_grip_length_mm=tp + td + 1.0 + 0.25, washer_stack_mm=1.0, axial_float_mm=0.12), pred)
    assert not any("tutma boyu" in w for w in fit.apply(kit_design, rec, pred)["warnings"])     # 0.13 groove slack
    far = fit.parse(_record(pred, lug_thickness_proximal_mm=tp, lug_thickness_distal_mm=td, measurement_resolution_mm=0.01,
                            pin_grip_length_mm=tp + td + 1.0 + 0.45, washer_stack_mm=1.0, axial_float_mm=0.12), pred)
    assert any("tutma boyu" in w for w in fit.apply(kit_design, far, pred)["warnings"])  # 0.33 > 0.15


def test_project_hash_must_be_a_sha256(pred):
    with pytest.raises(fit.RecordError, match="print_project_sha256"):
        fit.parse(_record(pred, print_project_sha256="proje.3mf"), pred)
    assert fit.parse(_record(pred, print_project_sha256="ab" * 32), pred)["print_project_sha256"] == "ab" * 32


def test_design_clearance_is_snapped_and_is_the_nominal_pair(kit_design):
    d = pd.with_changes(kit_design, **{"connection.hole_clearance_mm": 0.123})
    cl = fit.kit_clearances(d)
    assert 0.12 in cl and len(cl) == len(fit.COUPON_STEPS_MM) + 1
    assert fit.nominal_clearance(d, cl) == 0.12


def test_an_old_measured_design_loads_as_transferred(kit_design, pred):
    d = fit.apply(kit_design, fit.parse(_record(pred), pred), pred)["design"]
    raw = json.loads(pd.to_json(d))
    raw["connection"].pop("measured_process")
    old = pd.from_json(json.dumps(raw))
    assert pd.validate(old) == [] and old.connection.measured_play_basis == "transferred"
    assert "schema /2" in old.connection.measured_process


def test_assembly_guide_follows_the_pin_set(kit_design):
    from pyfoldable.prototype import explore
    d5 = explore.candidate_design(kit_design, ROOT, {"connection.pin_diameter_mm": 5.0})
    text = fit.assembly_guide(d5, fit.predictions(d5, 30.0, (8.0, 2.5), 144.0))
    assert d5.hardware.pin_nominal_mm == 5.0
    assert "DIN 433 5,3 × 9 × 1" in text and "DIN 6799 4 " in text and "Ø4×14" not in text and "DIN 433 4,3" not in text
