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
    return pd.with_changes(d, **{"connection.axial_offset_mm": 9.5})


@pytest.fixture(scope="module")
def pred(kit_design):
    return fit.predictions(kit_design, lever_mm=30.0, fit_masses_g=(9.0, 6.0))


def _record(pred, **over):
    rec = {k: None for k in fit.FIELDS}
    rec.update(schema=fit.SCHEMA, kit_design_sha256=pred["kit_design_sha256"], print_printer="Bambu P1S",
               print_material="PLA (marka X)", print_nozzle_mm=0.4, print_layer_mm=0.2, print_walls=3,
               print_infill_fraction=1.0, pin_measured_diameter_mm=2.98,
               coupon_fit=["girmez", "sıkı", "akıcı", "boşluklu", "boşluklu"],
               coupon_hole_mm=[None, 3.02, 3.12, None, None], fit_pair_clearance_mm=0.2,
               lug_thickness_proximal_mm=6.6, lug_thickness_distal_mm=7.0, axial_float_mm=0.12,
               tilt_load_n=2.0, tilt_range_at_tab_mm=0.72, friction_breakaway_n=0.5, stop_gap_mm=0.0,
               stop_seats=True, folded_stop_deg=142.0, mass_fit_proximal_g=8.1, mass_fit_distal_g=5.7, notes="")
    rec.update(over)
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
