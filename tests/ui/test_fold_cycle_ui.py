"""Analysis flow → complete opening–closing cycle → integrated result workspace → saved and reopened."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_research_release_ui import ANALYSIS, RECORDS, RESULTS, app, go  # noqa: E402


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
