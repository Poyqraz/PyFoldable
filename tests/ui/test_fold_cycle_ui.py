"""Analysis flow → complete opening–closing cycle → integrated result workspace → saved and reopened."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_research_release_ui import ANALYSIS, DESIGN, RECORDS, RESULTS, app, go  # noqa: E402


def _fast(at):
    for key, value in (("cycle_rest", 0.02), ("cycle_up", 0.15), ("cycle_hold", 0.2), ("cycle_down", 0.3), ("cycle_end", 0.1)):
        at.number_input(key=key).set_value(value)
    at.radio(key="cycle_aero").set_value("off")
    return at.run()


def test_cycle_runs_from_analysis_and_opens_the_connection_load_workspace():
    at = go(app(), ANALYSIS)
    table = next(d.value for d in at.dataframe if "Yöntem" in d.value.columns)
    assert any(str(y).startswith("Tam açılma–kapanma çevrimi") for y in table["Yöntem"])
    assert at.selectbox(key="cycle_preset").value == "spring"
    _fast(at)
    at.button(key="cycle_run").click().run()
    assert not at.exception
    assert at.radio(key="research_page").value == RESULTS
    assert at.radio(key="research_results_kind").value == "Açılma–kapanma çevrimi"
    labels = {m.label: m.value for m in at.metric}
    assert labels["Açıldı mı"] == "evet" and labels["Kapalıya döndü mü"] == "evet"
    text = " ".join(c.value for c in at.caption)
    assert "Kırmızı ok" in text and "yapısal gerilme çözülmedi" in text and "kısıt tepkileri" in text
    # one sample index drives every view: choosing an event moves the time cursor
    at.selectbox(key="cycle_event").set_value("first_open_contact").run()
    assert not at.exception
    from pyfoldable.dynamics import fold_cycle as fc
    row = fc.verify(__import__("json").loads(open(at.session_state["_fold_cycle_active"], encoding="utf-8").read()))
    ev = next(e for e in row["events"] if e["key"] == "first_open_contact")
    assert at.slider(key="cycle_index").value == ev["index"]           # the event's own sample, not a snapped time
    assert any(f"{ev['time_s']:.5f}" in c.value for c in at.caption)
    at.radio(key="cycle_frame").set_value("hinge").run()
    assert not at.exception
    loads = next(d.value for d in at.dataframe if "Bileşen (kanat 1, dil orta düzlemi)" in d.value.columns)
    assert len(loads) == 6 and set(loads["Mafsal"]) == {"kısıt tepkisi", "eleman (yay/stop/mandal)"}


def test_saved_cycle_is_listed_and_reopens_without_recalculation_and_passive_does_not_return():
    at = go(app(), ANALYSIS)
    at.selectbox(key="cycle_preset").set_value("passive").run()
    assert not at.exception
    assert at.number_input(key="cycle_k__passive").value == 0.0 and at.number_input(key="cycle_preload__passive").value == 0.0
    at.selectbox(key="cycle_preset").set_value("latch_actuator").run()           # each preset keeps its own widgets
    assert at.checkbox(key="cycle_latch__latch_actuator").value and at.number_input(key="cycle_act__latch_actuator").value == -0.3
    at.selectbox(key="cycle_preset").set_value("passive").run()
    _fast(at)
    at.button(key="cycle_run").click().run()
    assert not at.exception
    assert {m.label: m.value for m in at.metric}["Kapalıya döndü mü"] == "hayır"
    assert any("geri katlayan bir moment yoktur" in w.value for w in at.warning)
    go(at, RECORDS)
    table = next(d.value for d in at.dataframe if "Kapalıya döndü" in d.value.columns)
    assert list(table["Kapalıya döndü"]) == ["hayır"]
    at.button(key="cycle_saved_open").click().run()
    assert not at.exception
    assert at.radio(key="research_page").value == RESULTS


def _stored(at):
    import json
    from pyfoldable.dynamics import fold_cycle as fc
    return fc.verify(json.loads(open(at.session_state["_fold_cycle_active"], encoding="utf-8").read()))


def test_run_uses_the_values_on_screen_and_the_new_inputs_reach_the_case():
    at = go(app(), ANALYSIS)
    _fast(at)
    at.number_input(key="cycle_rpm").set_value(3100.0)
    at.number_input(key="cycle_final_rpm").set_value(500.0)
    at.radio(key="cycle_rest_inflow").set_value("zero")
    at.button(key="cycle_run").click().run()                     # changed and clicked in the same rerun
    assert not at.exception and at.radio(key="research_page").value == RESULTS
    case = _stored(at)["case"]
    assert case["schedule"]["operating_rpm"] == 3100.0 and case["schedule"]["final_rpm"] == 500.0
    assert case["aero"]["rest_inflow"] == "zero"
    assert "sensitivity" not in _stored(at)                       # opt-in
    assert any("duyarlılığı hesaplanmadı" in c.value for c in at.caption)
    peaks = next(d.value for d in at.dataframe if "Büyüklük" in d.value.columns)
    assert {"Birim", "Devir [RPM]", "Kanat"} <= set(peaks.columns) and set(peaks["Birim"]) == {"N", "N·m"}
    assert not any("geri katlayan bir moment yoktur" in w.value for w in at.warning)   # the shaft did not stop


def test_changing_a_phase_duration_and_clicking_run_in_the_same_rerun_keeps_the_click():
    at = go(app(), ANALYSIS)
    _fast(at)
    at.number_input(key="cycle_hold").set_value(0.25)
    at.button(key="cycle_run").click().run()                     # Streamlit 1.40 keys the button by its parameters
    assert not at.exception and at.radio(key="research_page").value == RESULTS
    assert _stored(at)["case"]["schedule"]["hold_s"] == 0.25


def test_default_configuration_warns_about_surface_contact_before_the_run():
    at = go(app(), ANALYSIS)
    assert any("temas eder" in w.value and "-66,6" in w.value for w in at.warning)
    at.number_input(key="cycle_stowed__spring").set_value(-60.0).run()
    assert not any("temas eder" in w.value for w in at.warning)


def test_downloads_are_built_once_per_record_not_per_slider_step(monkeypatch):
    from pyfoldable.application import fold_cycle_views as views
    at = go(app(), ANALYSIS)
    _fast(at)
    at.button(key="cycle_run").click().run()
    calls = []
    real = views.series_csv
    monkeypatch.setattr(views, "series_csv", lambda row: calls.append(1) or real(row))
    at.button(key="cycle_downloads_build").click().run()
    at.slider(key="cycle_index").set_value(5).run()
    at.slider(key="cycle_index").set_value(9).run()
    assert not at.exception and len(calls) == 1
    assert any(b.label == "Zaman serisi CSV" for b in at.get("download_button"))


def test_cycle_rpm_follows_the_design_unless_overridden():
    at = go(app(), ANALYSIS)
    assert at.number_input(key="cycle_rpm").value == 2400.0
    go(at, DESIGN).number_input(key="research_axial_800_rpm").set_value(3000.0).run()
    go(at, ANALYSIS)
    assert at.number_input(key="cycle_rpm").value == 3000.0
    at.number_input(key="cycle_rpm").set_value(2800.0).run()
    go(at, DESIGN).number_input(key="research_axial_800_rpm").set_value(3200.0).run()
    go(at, ANALYSIS)
    assert at.number_input(key="cycle_rpm").value == 2800.0
    assert any("3200" in w.value for w in at.warning)
    at.button(key="cycle_rpm_from_design").click().run()
    assert at.number_input(key="cycle_rpm").value == 3200.0
    # the browser keeps its own value unless told: Streamlit 1.65 keys the widget id on the key alone
    assert at.number_input(key="cycle_rpm").proto.set_value


def test_a_stow_limit_above_the_stowed_stop_bound_does_not_break_the_analysis_page():
    at = go(app(), ANALYSIS)
    go(at, DESIGN).number_input(key="research_axial_800_fold_deg").set_value(-2.0)     # the preview pose must stay within the limit
    at.number_input(key="research_axial_800_stow_limit_deg").set_value(-3.0).run()
    go(at, ANALYSIS)                                                                     # go() asserts no exception
    assert at.number_input(key="cycle_stowed__spring").value == -5.0
    assert any("katlanma sınırının" in w.value for w in at.warning)


def test_an_older_horizontal_gravity_record_is_not_called_identical_and_every_blade_is_checked(monkeypatch):
    import json
    from pyfoldable.application import fold_cycle_ui as fcui
    from pyfoldable.dynamics import fold_cycle as fc
    at = go(app(), ANALYSIS)
    _fast(at)
    at.radio(key="cycle_gravity").set_value("shaft_horizontal")
    at.button(key="cycle_run").click().run()
    old = {k: v for k, v in _stored(at).items() if k not in ("result_sha256", "events_by_blade")}
    old["schema_version"] = 1                            # schema 1 never wrote events_by_blade
    path = at.session_state["_fold_cycle_active"]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(fc.seal(old), f)
    blades = []
    real = fcui.pl.connection_checks
    monkeypatch.setattr(fcui.pl, "connection_checks", lambda loads, *a: blades.append(1) or real(loads, *a))
    for key, value in (("cycle_pin_d", 3.0), ("cycle_tang_t", 4.0), ("cycle_plate_t", 2.0)):
        at.number_input(key=key).set_value(value)
    at.run()
    assert not at.exception
    assert not any("özdeş" in c.value for c in at.caption)
    assert len(blades) == 2


def test_reversed_actuator_window_is_an_input_error():
    at = go(app(), ANALYSIS)
    at.selectbox(key="cycle_preset").set_value("latch_actuator").run()
    at.number_input(key="cycle_act_start__latch_actuator").set_value(2.0)
    at.number_input(key="cycle_act_end__latch_actuator").set_value(1.0).run()
    assert any("Çevrim girdileri geçersiz" in e.value for e in at.error)
    assert at.button(key="cycle_run").disabled


def test_latch_preset_with_the_default_design_engages_the_latch():
    at = go(app(), ANALYSIS)
    at.selectbox(key="cycle_preset").set_value("latch_actuator").run()
    assert at.number_input(key="cycle_capture__latch_actuator").value > 0
    at.button(key="cycle_run").click().run()
    assert not at.exception
    assert any(e["kind"] == "latch_engaged" for e in _stored(at)["latch_events"])
    assert not any("hiç kilitlenmedi" in w.value for w in at.warning)


def test_result_page_state_survives_navigation_and_is_not_reverified_per_slider_step(monkeypatch):
    from pyfoldable.dynamics import fold_cycle as fc
    at = go(app(), ANALYSIS)
    _fast(at)
    at.button(key="cycle_run").click().run()
    calls = []
    real = fc.verify
    monkeypatch.setattr(fc, "verify", lambda row: calls.append(1) or real(row))
    at.slider(key="cycle_index").set_value(5).run()
    at.slider(key="cycle_index").set_value(9).run()
    assert not at.exception and len(calls) <= 1
    # re-selecting the same event jumps back after the slider moved
    ev = next(e for e in _stored(at)["events"] if e["key"] == "first_open_contact")
    at.selectbox(key="cycle_event").set_value("first_open_contact").run()
    assert at.slider(key="cycle_index").value == ev["index"]
    at.slider(key="cycle_index").set_value(3).run()
    at.selectbox(key="cycle_event").set_value("first_open_contact").run()
    assert at.slider(key="cycle_index").value == ev["index"]
    # pin-lug inputs persist; an unsourced allowable gives no verdict
    for key, value in (("cycle_pin_d", 3.0), ("cycle_tang_t", 4.0), ("cycle_plate_t", 2.0), ("cycle_allow_pin_shear_pa", 100.0)):
        at.number_input(key=key).set_value(value)
    at.run()
    go(at, RECORDS)
    go(at, RESULTS)
    assert at.number_input(key="cycle_pin_d").value == 3.0
    status = next(d.value for d in at.dataframe if "Durum" in d.value.columns)["Durum"]
    assert "yeterli" not in set(status) and "girdi gerekli (kaynak)" in set(status)
    at.text_input(key="cycle_allow_source").set_value("Malzeme veri sayfası X").run()
    status = next(d.value for d in at.dataframe if "Durum" in d.value.columns)["Durum"]
    assert set(status) & {"yeterli", "yetersiz"}


def test_horizontal_shaft_offers_a_blade_choice_and_checks_the_connection_of_every_blade():
    at = go(app(), ANALYSIS)
    _fast(at)
    at.radio(key="cycle_gravity").set_value("shaft_horizontal")
    at.button(key="cycle_run").click().run()
    assert not at.exception
    row = _stored(at)
    assert at.radio(key="cycle_blade").options == ["Kanat 1", "Kanat 2"]
    at.radio(key="cycle_blade").set_value(1).run()
    assert not at.exception
    assert next(d.value for d in at.dataframe if "Bileşen (kanat 2, dil orta düzlemi)" in d.value.columns) is not None
    assert any(m.label == "Son θ [°] (kanat 2)" for m in at.metric)
    for key, value in (("cycle_pin_d", 3.0), ("cycle_tang_t", 4.0), ("cycle_plate_t", 2.0)):
        at.number_input(key=key).set_value(value)
    at.run()
    assert not at.exception
    checks = next(d.value for d in at.dataframe if "Durum" in d.value.columns)
    assert set(checks["Kanat"]) <= {1, 2} and len(checks) > 0
    assert "events_by_blade" in row


def test_vanished_comparison_record_warns_instead_of_crashing(monkeypatch, tmp_path):
    from pyfoldable.application import fold_cycle_ui as fcui
    at = go(app(), ANALYSIS)
    _fast(at)
    at.button(key="cycle_run").click().run()
    real = fcui.saved
    ghost = {"path": tmp_path / "gone.json", "sha": "0" * 64, "saved": 0.0, "profile": "NACA2412", "mode": "mechanical_cycle_no_aero",
             "rpm": 2400.0, "offset_mm": 0.0, "returned": True, "preset": "spring"}
    monkeypatch.setattr(fcui, "saved", lambda limit=30: [*real(limit), ghost])
    at.run()
    assert not at.exception
    assert any("doğrulanamadı" in w.value for w in at.warning)


def _coupled_tab(row, root):
    from pyfoldable.application import fold_cycle_ui
    fold_cycle_ui.coupled_loads_tab(row, root)


def test_coupled_loads_tab_has_a_blade_choice_and_says_when_checks_are_missing(monkeypatch, tmp_path):
    from streamlit.testing.v1 import AppTest
    from pyfoldable.application import coupled_analysis
    from pyfoldable.coupled import hinge_loads
    (tmp_path / "structure").mkdir()
    (tmp_path / "structure" / "out.jnt").write_text("")
    blade = {k: [0.0, 1.0, 2.0] for k in ("N_tension", "V_inplane", "V_axial", "M_pin", "M_bending", "M_torsion")}
    comp = {"time_s": [0.0, 0.01, 0.02], "theta_deg": [[-5.0, -6.0]] * 3, "contact_active": [[False, False]] * 3,
            "blades": [blade, {**blade, "N_tension": [0.0, 3.0, 9.0]}], "startup_transient_windows": 1,
            "peaks": [{"key": "N_tension", "label": "En büyük eksenel çekme", "blade": 1, "value": 9.0, "window": 3,
                       "time_s": 0.02, "theta_deg": -6.0, "rpm": 2000.0, "in_contact": False}],
            "checks": [], "checks_skipped_reason": "Mühürlü run tanımında bağlaşım düğümleri (coupling_nodes) yok.",
            "startup_overlaps": [{"event": "release", "blade": None, "window": 1, "time_s": 0.0}]}
    monkeypatch.setattr(coupled_analysis, "local_run_dir", lambda root, row: tmp_path)
    monkeypatch.setattr(hinge_loads, "load", lambda run_dir, row: comp)
    at = AppTest.from_function(_coupled_tab, args=({}, tmp_path)).run()
    assert not at.exception
    assert at.radio(key="coupled_hinge_blade").options == ["Kanat 1", "Kanat 2"]
    peaks = next(d.value for d in at.dataframe if "Büyüklük" in d.value.columns)
    assert list(peaks["Kanat"]) == [2] and list(peaks["Birim"]) == ["N"]
    assert any("coupling_nodes" in i.value for i in at.info)
    assert any("bırakma" in w.value for w in at.warning)
