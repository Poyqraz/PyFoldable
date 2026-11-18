"""'Prototip' page: explicit build, stale results and downloads, fail-closed errors, exploration, real CAD smoke."""
import io
import json
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from pyfoldable.application import prototype_ui
from pyfoldable.prototype import explore, export, loads, mass, strength
from pyfoldable.prototype.mass import MassProps

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_research_release_ui import ANALYSIS, app, go  # noqa: E402

PAGE = "Prototip"
ROOT = Path(__file__).resolve().parents[2]
META = {"stop_x_mm": (-14.0, -6.1), "stop_z_mm": (-1.4, 2.6), "nose_z_mm": (-1.4, 5.0)}
TETRA = (np.array([[0.0, 99.0, 0.0], [10.0, 99.0, 0.0], [0.0, 120.0, 0.0], [0.0, 99.0, 5.0]]),
         np.array([[0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3]]))


def text(at):
    return " ".join(x.value for kind in ("caption", "markdown", "info", "warning", "error") for x in getattr(at, kind))


def specs(at):
    return [json.loads(c.proto.spec) for c in at.get("plotly_chart")]


def _arr(x):
    """A plotly JSON array: a list or a base64 typed array ({dtype, bdata})."""
    import base64
    if isinstance(x, dict):
        return np.frombuffer(base64.b64decode(x["bdata"]), dtype=x["dtype"])
    return np.asarray(x, dtype=float)


def downloads(at):
    """Result downloads (the measurement kit and record template are always offered when a kit exists)."""
    return [b for b in at.get("download_button")
            if b.key not in ("proto_fit_template", "proto_fit_kit_zip", "proto_kitgen_zip")]


def _sweep():
    th = [-float(a) for a in range(2, 181)]
    gap = [2.0 + a / 40 for a in th]
    return {"angles_deg": th, "gap_mm": gap, "gap_play_mm": [g - 0.8 for g in gap],
            "nose_gap_mm": [float("inf") if -a < 10 else 3.0 + a / 30 for a in th],
            "where": [(-2.6, 74.9, 24.3)] * len(th),
            "min_gap_mm": -1.75, "min_gap_angle_deg": -150.0, "min_gap_play_mm": -2.55, "min_gap_play_angle_deg": -150.0,
            "required_travel_deg": 150.0, "body_clear_to_deg": 59.0, "folded_stop_deg": 91.0, "clear_travel_deg": 59.0,
            "full_travel_clear": False, "body_clear": False, "full_travel_clear_with_play": False,
            "required_offset_mm": 7.75, "required_offset_with_play_mm": 8.55, "joint_running_gap_mm": 0.3,
            "play": {"radial_play_mm": 0.2, "axial_play_mm": 0.3, "tilt_rad": 0.0545, "tilt_deg": 3.13,
                     "tilt_limited_by": "lug yüz aralığı", "tip_droop_mm": 3.9},
            "body_clearance_mm": 0.5, "method": "sahte tarama"}


def _result(d):
    """A complete evaluate() result without the CAD kernel (loads and strength are the real functions)."""
    mp = MassProps(4.0, (3.9, 120.0, 5.5), ((300.0, 0.0, 0.0), (0.0, 50.0, 0.0), (0.0, 0.0, 330.0)), 3200.0, "sahte")
    parts = SimpleNamespace(design=d, proximal="P", distal="D", hardware={"pin": "H"}, pin_axis=(0.0, 99.0), meta=META)
    load = loads.deployed(mp, d, META, 6000.0)
    rows = strength.checks(load, d, META)
    gov = strength.governing(rows)
    return {"design": d, "parts": parts, "sweep": _sweep(), "reasons": ["Gövdeler 59°'de çakışıyor (sahte)"],
            "eligible": False, "alignment": {"step_mm": d.connection.axial_offset_mm, "face_gap_mm": 0.3,
                                             "nose_ahead_of_le_mm": 2.0, "proximal_boss_below_surface_mm": 0.07,
                                             "distal_boss_above_surface_mm": 0.0, "head_below_proximal_surface_mm": 1.57,
                                             "clip_above_distal_surface_mm": 0.93, "lug_midplane_offset_mm": 4.3,
                                             "stack_thickness_mm": 8.3, "relief_radius_mm": 6.1, "hardware_inside_relief": True},
            "mass": {"proximal": mp, "distal": mp, "pin_set": mp, "blade": mp, "hardware": {},
                     "fold": mass.fold_mechanism_equivalent(mp, d)},
            "loads": load, "strength": rows, "governing": {"key": gov["key"], "label": gov["label"], "rpm_limit": gov["rpm_limit"]}}


@pytest.fixture()
def fake(monkeypatch):
    calls = []
    monkeypatch.setattr(explore, "evaluate", lambda d, rpm=None: calls.append(d.identity) or _result(d))
    monkeypatch.setattr(prototype_ui, "_mesh", lambda shape: TETRA)
    monkeypatch.setattr(prototype_ui, "_printability", lambda parts: [
        {"check": "Delik çevresi et kalınlığı", "value": "3.90 mm", "ok": True, "note": "≥ 2 çevre duvarı"},
        {"check": "Tabla sığması: rotor_hub_proximal", "value": "340×40×20 mm", "ok": False, "note": "tabla 256×256×256"}])
    return calls


def _fake_export(parts, folder, evaluation=None):
    folder.mkdir(parents=True)
    (folder / "summary.md").write_text("# Hesap özeti (sahte)\n", encoding="utf-8")
    return {"report": {}, "files": [("ab" * 32, "summary.md")]}


def test_page_renders_without_cad_and_builds_only_on_the_button(fake):
    at = go(app(), PAGE)
    assert not fake and not specs(at) and not downloads(at)
    t = text(at)
    assert "Fiziksel yeterlilik: yok" in t and "azami devir" in t and "motor bağlantısı" in t
    assert "Düzlem A: z = 0" in t and "pim boyu" in t
    at.number_input(key="proto_operating.max_rpm").set_value(5200.0).run()
    assert not fake and "azami devir" not in at.warning[0].value      # the owner input leaves the missing list
    at.button(key="proto_build").click().run()
    assert not at.exception and len(fake) == 1
    assembly, clearance, side, plan, need = specs(at)
    assert len(assembly["frames"]) == 15                                  # 0, −10 … −140 (the default stowed angle)
    assert [s["label"] for s in assembly["layout"]["sliders"][0]["steps"]][-2:] == ["-130", "-140"]
    scene = assembly["layout"]["scene"]                     # fixed ranges over every pose: the playback does not rescale
    assert scene["aspectmode"] == "manual"
    for axis in "xyz":
        lo, hi = scene[f"{axis}axis"]["range"]
        pts = np.concatenate([_arr(fr["data"][0][axis]) for fr in assembly["frames"]] + [_arr(assembly["data"][0][axis])])
        assert lo <= pts.min() and pts.max() <= hi
    names = [tr.get("name") for tr in clearance["data"]]
    assert names == ["Nominal boşluk", "En kötü oynama ile", "Stop burnu boşluğu"]
    labels = [a["text"] for a in clearance["layout"]["annotations"]]
    assert "katlanmış stop (burun teması)" in labels and "açık katlanma" in labels
    t = text(at)
    assert "Belirleyici kontrol" in t and "Parça niteliklendirmesi değildir" in t and "FoldMechanism" in t
    assert "Gövdeler 59°'de çakışıyor" in t and "Basılabilirlik kontrolü geçmedi: Tabla sığması" in t
    assert any("5200 RPM (sahibin azami devri)" in list(df.value.get("Durum", [])) for df in at.dataframe)
    assert any("UYGUN DEĞİL" in list(df.value.get("Sonuç", [])) for df in at.dataframe)
    go(at, ANALYSIS)
    go(at, PAGE)                                    # navigation keeps inputs and the result; nothing reruns
    assert at.number_input(key="proto_operating.max_rpm").value == 5200.0
    assert at.number_input(key="proto_connection.lug_interface_z_mm").value is None
    assert len(fake) == 1 and len(specs(at)) == 5


def test_changed_input_marks_the_result_stale_and_removes_the_download(fake, monkeypatch):
    monkeypatch.setattr(export, "export_candidate", _fake_export)
    at = go(app(), PAGE)
    at.button(key="proto_build").click().run()
    assert "Sahibin azami devri verilmedi" in text(at)
    at.button(key="proto_export").click().run()
    assert not at.exception and len(downloads(at)) == 1
    assert any("SHA-256" in df.value.columns for df in at.dataframe)
    ex = at.session_state["_proto_export"]
    identity = at.session_state["_proto_build"]["identity"]
    assert ex["name"] == f"13in-v1_{identity[:8]}.zip"
    assert zipfile.ZipFile(io.BytesIO(ex["zip"])).namelist() == [f"13in-v1_{identity[:8]}/summary.md"]
    at.number_input(key="proto_connection.axial_offset_mm").set_value(6.0).run()
    assert not at.exception and not downloads(at) and not specs(at)
    assert "güncel değil" in text(at) and len(fake) == 1
    at.number_input(key="proto_connection.axial_offset_mm").set_value(5.5).run()    # back to the built design
    assert len(specs(at)) == 5 and len(downloads(at)) == 1


def test_evaluate_failure_is_an_error_and_replaces_an_earlier_success(fake, monkeypatch):
    at = go(app(), PAGE)
    at.button(key="proto_build").click().run()
    assert len(specs(at)) == 5

    def boom(d, rpm=None):
        raise RuntimeError("çekirdek hatası")
    monkeypatch.setattr(explore, "evaluate", boom)
    at.button(key="proto_build").click().run()
    assert not at.exception
    assert any("çekirdek hatası" in e.value for e in at.error)
    assert not specs(at) and not any(b.key == "proto_export" for b in at.button)


def test_unbuildable_geometry_and_a_failed_export_offer_no_result_or_download(fake, monkeypatch):
    at = go(app(), PAGE)
    at.button(key="proto_build").click().run()

    def broken(parts, folder, evaluation=None):
        raise OSError("disk dolu")
    monkeypatch.setattr(export, "export_candidate", broken)
    at.button(key="proto_export").click().run()
    assert not at.exception and not downloads(at) and any("disk dolu" in e.value for e in at.error)
    monkeypatch.setattr(explore, "evaluate", lambda d, rpm=None: {"design": d, "reasons": ["Geometri kurulamadı: stop yok"],
                                                                  "eligible": False})
    at.button(key="proto_build").click().run()
    assert not at.exception and any("stop yok" in e.value for e in at.error)
    assert not specs(at) and not downloads(at) and not any(b.key == "proto_export" for b in at.button)


def test_exploration_keeps_rejected_candidates_with_reasons_and_loads_one_into_the_editor(monkeypatch):
    seen = {}
    grid = [{"connection.axial_offset_mm": 5.0, "planform.twist_scale": 1.0},
            {"connection.axial_offset_mm": 6.0, "planform.twist_scale": 0.35}]

    def run(base, root, axes, rpm=None, progress=None):
        seen["axes"] = axes
        for i, p in enumerate(grid):
            progress(i, len(grid), p)
        rows = [{"axial_offset_mm": 5.0, "twist_scale": 1.0, "uygun": False, "gerekçe": "Gövdeler 53°'de çakışıyor"},
                {"axial_offset_mm": 6.0, "twist_scale": 0.35, "uygun": True, "gerekçe": "—", "açık katlanma [°]": 150}]
        return {"axes": axes, "rows": rows, "results": [(p, {}) for p in grid], "reference_rpm": 6000.0,
                "alternatives": [{"label": "En hafif kanat", "params": grid[1], "identity": "abc", "duplicate": False}]}
    monkeypatch.setattr(explore, "run", run)
    at = go(app(), PAGE)
    assert "9 aday · üst sınır 24" in text(at)
    at.button(key="proto_explore").click().run()
    assert not at.exception
    assert seen["axes"] == {"connection.axial_offset_mm": [5.0, 5.5, 6.0], "planform.twist_scale": [1.0, 0.6, 0.35]}
    table = next(df.value for df in at.dataframe if "gerekçe" in df.value.columns)
    assert list(table["uygun"]) == [False, True] and "çakışıyor" in table["gerekçe"][0]
    assert any("En hafif kanat" in list(df.value.get("Seçenek", [])) for df in at.dataframe)
    at.selectbox(key="proto_candidate").select_index(1).run()
    at.button(key="proto_load").click().run()
    assert not at.exception and not any("Session State" in w.value for w in at.warning)
    assert at.number_input(key="proto_connection.axial_offset_mm").value == 6.0
    assert at.number_input(key="proto_planform.twist_scale").value == 0.35
    assert any("gerekçe" in df.value.columns for df in at.dataframe)     # a loaded candidate keeps the table current
    at.number_input(key="proto_connection.pin_x_mm").set_value(1.0).run()
    assert not any("gerekçe" in df.value.columns for df in at.dataframe) and "aday tablosu" in text(at)
    at.number_input(key="proto_operating.distal_thrust_n").set_value(2.0).run()   # no radius: an input error
    assert at.button(key="proto_build").disabled and at.button(key="proto_explore").disabled


def test_real_cad_build_shows_the_clearance_chart_and_exports_a_zip():
    pytest.importorskip("build123d")
    from pyfoldable.prototype import cad
    at = go(app(), PAGE)
    at.button(key="proto_build").click().run(timeout=240)
    assert not at.exception and "Geometri oluşturulamadı" not in text(at)
    assembly, clearance, side, plan, need = specs(at)
    assert clearance["data"][0]["name"] == "Nominal boşluk"
    assert sum(len(tr["i"]) for tr in assembly["data"]) < 10000           # a coarse preview mesh, not the sweep mesh
    parts = at.session_state["_proto_build"]["result"]["parts"]    # the playback poses the distal like distal_at
    v, _ = cad.tessellate(parts.distal, 0.3)
    w, _ = cad.tessellate(parts.distal_at(-90.0), 0.3)
    r = prototype_ui._rotate(v, parts.pin_axis, -90.0)
    assert np.allclose(r.min(0), w.min(0), atol=0.3) and np.allclose(r.max(0), w.max(0), atol=0.3)
    at.button(key="proto_export").click().run(timeout=300)
    assert not at.exception and len(downloads(at)) == 1
    names = zipfile.ZipFile(io.BytesIO(at.session_state["_proto_export"]["zip"])).namelist()
    assert any(n.endswith("/summary.md") for n in names) and any(n.endswith(".step") for n in names)
    assert any(n.endswith("/SHA256SUMS") for n in names)


def test_alignment_tab_shows_the_deployed_step_the_folded_envelope_and_the_offset_budget(fake):
    at = go(app(), PAGE)
    at.button(key="proto_build").click().run()
    assert not at.exception
    assembly, _, side, plan, need = specs(at)
    assert [tr["name"] for tr in side["data"]][:2] == ["Proksimal uç kesiti (z = 0)", "Distal kök kesiti (z = δ)"]
    for fig in (side, plan):                                  # equal aspect without collapsing in a wide column
        assert fig["layout"]["xaxis"]["constrain"] == "domain" and fig["layout"]["xaxis"]["range"]
    assert assembly["layout"]["scene"]["camera"]["eye"]["z"] < 1.0                 # close enough to read the joint
    assert any(str(tr.get("name", "")).startswith("Katlı zarf R") for tr in plan["data"])
    assert [tr["name"] for tr in need["data"]] == ["Nominal", "Boşlukla"]
    t = text(at)
    assert "Gereken ofset bütçesi" in t and "mekanizma tabanı" in t and "kanat payı" in t
    assert "Belirleyici nokta" in t and "None" not in " ".join(str(v) for df in at.dataframe for v in df.value.to_numpy().ravel())


def test_hinge_zone_inputs_follow_the_joint_and_reach_the_built_design(fake):
    at = go(app(), PAGE)
    at.number_input(key="proto_planform.hinge_zone_mm").set_value(45.0).run()
    at.number_input(key="proto_planform.hinge_twist_factor").set_value(0.5).run()
    assert not at.exception and not at.error
    at.button(key="proto_build").click().run()
    d = at.session_state["_proto_build"]["result"]["design"]
    assert d.planform.hinge_zone_mm == 45.0 and d.planform.hinge_zone_center_mm == d.connection.hinge_radius_mm
    assert d.section(99.0)[1] == pytest.approx(0.5 * prototype_ui.design.default_design(ROOT).section(99.0)[1])


def _kit(tmp_path):
    from pyfoldable.prototype import fit
    from pyfoldable.prototype import design as pd
    d = pd.with_changes(pd.default_design(ROOT, twist_scale=0.6), **{"connection.axial_offset_mm": 9.5})
    pred = fit.predictions(d, 30.0, (9.0, 6.0), 144.0)
    (tmp_path / "predictions.json").write_text(json.dumps(pred), encoding="utf-8")
    (tmp_path / "fit_record_template.json").write_text(fit.template(pred), encoding="utf-8")
    (tmp_path / "SHA256SUMS").write_text("", encoding="utf-8")
    (tmp_path / "3mf").mkdir()
    (tmp_path / "3mf" / "hole_coupon.3mf").write_bytes(b"3mf")
    rec = json.loads(fit.template(pred))
    rec.update(print_printer="P1S", print_material="PLA", print_nozzle_mm=0.4, print_layer_mm=0.2, print_walls=3,
               print_infill_fraction=1.0, pin_measured_diameter_mm=2.99, coupon_fit=["sıkı", "sıkı", "akıcı", "akıcı", "boşluklu"],
               fit_pair_clearance_mm=0.2, lug_thickness_proximal_mm=6.8, lug_thickness_distal_mm=7.2, axial_float_mm=0.1,
               tilt_load_n=2.0, tilt_range_at_tab_mm=0.4, friction_breakaway_n=0.3, stop_gap_mm=0.0, stop_seats=True,
               measurement_resolution_mm=0.01, repeat_count=3, axial_float_spread_mm=0.02, tilt_range_spread_mm=0.05)
    return json.dumps(rec, ensure_ascii=False)


def test_a_fit_record_is_validated_applied_to_the_design_and_removable(fake, monkeypatch, tmp_path):
    monkeypatch.setattr(prototype_ui, "KITS", {"E": ("E (test kiti)", tmp_path)})
    good = _kit(tmp_path)
    at = go(app(), PAGE)
    assert any(b.key == "proto_fit_template" for b in at.get("download_button"))
    names = zipfile.ZipFile(io.BytesIO(prototype_ui._kit_zip(str(tmp_path), ""))).namelist()
    assert f"{tmp_path.name}/predictions.json" in names and f"{tmp_path.name}/3mf/hole_coupon.3mf" in names
    before = at.session_state["_proto_fit_record"] if "_proto_fit_record" in at.session_state else None
    assert before is None
    at.text_area(key="proto_fit_text").set_value(good.replace('"P1S"', "null")).run()
    at.button(key="proto_fit_apply").click().run()
    assert "Ölçüm kaydı kullanılamadı" in text(at) and "print_printer" in text(at)
    assert "Ölçüm kaydı uygulanıyor" not in text(at)
    at.text_area(key="proto_fit_text").set_value(good).run()
    at.button(key="proto_fit_apply").click().run()
    assert not at.exception and "Ölçüm kaydı uygulanıyor" in text(at)          # in the same run, no lag
    assert "aktarılmış" in text(at) and "en kötü durum modelinde" in text(at)      # B-like kit on the default design
    assert any("Eksenel boşluk" in list(df.value.get("Büyüklük", [])) for df in at.dataframe)
    at.button(key="proto_build").click().run()
    d = at.session_state["_proto_build"]["result"]["design"]
    assert d.connection.measured_axial_play_mm == pytest.approx(0.1) and d.connection.play_record_sha256
    at.button(key="proto_fit_clear").click().run()
    assert "Ölçüm kaydı uygulanıyor" not in text(at) and "güncel değil" in text(at)    # the measured build is now stale
    at.text_area(key="proto_fit_text").set_value(good).run()
    at.button(key="proto_fit_apply").click().run()
    assert "Ölçüm kaydı uygulanıyor" in text(at)
    at.text_area(key="proto_fit_text").set_value("[" * 5000).run()
    at.button(key="proto_fit_apply").click().run()                         # a failed paste drops the older record
    assert not at.exception and "Ölçüm kaydı kullanılamadı" in text(at) and "Ölçüm kaydı uygulanıyor" not in text(at)


def test_kit_generator_writes_the_editor_design_kit_and_goes_stale_on_change(fake, monkeypatch, tmp_path):
    from pyfoldable.prototype import fit
    monkeypatch.setattr(prototype_ui, "KITS", {"E": ("E (test kiti)", tmp_path)})
    _kit(tmp_path)
    made = []

    def fake_kit(d, folder, clearances=fit.FIT_PAIR_CLEARANCES_MM):
        made.append(d.identity)
        (folder / "3mf").mkdir(parents=True)
        (folder / "3mf" / "fit_proximal_c0p20.3mf").write_bytes(b"3mf")
        (folder / "README.md").write_text("# kit", encoding="utf-8")
        return {"predictions": fit.predictions(d, 30.0, (8.0, 2.5), 144.0), "files": []}
    monkeypatch.setattr(fit, "export_kit", fake_kit)
    at = go(app(), PAGE)
    at.number_input(key="proto_connection.axial_offset_mm").set_value(6.5).run()
    at.button(key="proto_kitgen").click().run()
    assert not at.exception and len(made) == 1
    gen = at.session_state["_proto_kitgen"]
    names = zipfile.ZipFile(io.BytesIO(gen["zip"])).namelist()
    assert any(n.endswith("3mf/fit_proximal_c0p20.3mf") for n in names) and gen["name"].startswith("fit_kit_13in-v1_")
    assert any(b.key == "proto_kitgen_zip" for b in at.get("download_button"))
    at.radio(key="proto_fit_kit").set_value("G").run()                 # the generated kit is a record source
    pred = at.session_state["_proto_kitgen"]["pred"]
    rec = json.loads(fit.template(pred))
    rec.update(print_printer="P1S", print_material="PLA", print_nozzle_mm=0.4, print_layer_mm=0.2, print_walls=3,
               print_infill_fraction=1.0, pin_measured_diameter_mm=3.0, coupon_fit=["sıkı", "akıcı", "akıcı", "akıcı", "boşluklu"],
               fit_pair_clearance_mm=0.2, lug_thickness_proximal_mm=pred["lug_thicknesses_mm"][0],
               lug_thickness_distal_mm=pred["lug_thicknesses_mm"][1], axial_float_mm=0.1, tilt_load_n=2.0,
               tilt_range_at_tab_mm=0.5, friction_breakaway_n=0.3, stop_gap_mm=0.0, stop_seats=True,
               measurement_resolution_mm=0.01, repeat_count=3, axial_float_spread_mm=0.02, tilt_range_spread_mm=0.05)
    at.text_area(key="proto_fit_text").set_value(json.dumps(rec, ensure_ascii=False)).run()
    at.button(key="proto_fit_apply").click().run()
    assert not at.exception and "doğrudan" in text(at) and "13in-v1" in text(at)
    at.button(key="proto_fit_clear").click().run()
    at.number_input(key="proto_connection.axial_offset_mm").set_value(7.0).run()
    assert not any(b.key == "proto_kitgen_zip" for b in at.get("download_button"))
    assert "oluşturulan ölçüm kiti bu tasarıma ait değil" in text(at)
