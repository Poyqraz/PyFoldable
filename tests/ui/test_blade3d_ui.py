"""Lofted 3-D blade in the normal workflow: design preview with fold contacts, BEM result on the blade, coupled
playback and the synchronised flow scene (all solvers inert or recorded)."""
import json
import sys
from pathlib import Path

from pyfoldable.core.profile_catalog import PROJECT_AIRFOIL_IDS

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "application"))
from research_inert_support import bem, store  # noqa: E402
from test_coupled_ui import FIXTURE_RBF, _flow_app, _forbid_runs, _no_toolchain, _record  # noqa: E402
from test_research_release_ui import ANALYSIS, DESIGN, RESULTS, app, go  # noqa: E402


def _text(at):
    return " ".join([c.value for c in at.caption] + [m.value for m in at.markdown] + [w.value for w in at.warning]
                    + [i.value for i in at.info])


def test_design_preview_draws_the_lofted_blade_and_stops_at_the_first_fold_contact(tmp_path, monkeypatch):
    store(tmp_path, monkeypatch, PROJECT_AIRFOIL_IDS)
    at = go(app(), DESIGN)
    for view in ("3B", "Plan"):
        at.radio(key="research_preview").set_value(view).run()
        assert not at.exception, view
        text = _text(at)
        assert "katalog profili" in text and "firar kenarı tarafına" in text
        # the default preview pose (-110 deg) is beyond the first surface contact: drawn at the contact, not interlocked
        assert "durduruldu" in text and "temas" in text
    at.number_input(key="research_axial_800_fold_deg").set_value(-20.0).run()
    assert not at.exception and "durduruldu" not in _text(at)


def test_bem_result_is_shown_on_the_blade_with_kind_unit_and_strip_meaning(tmp_path, monkeypatch):
    store(tmp_path, monkeypatch, PROJECT_AIRFOIL_IDS)
    bem(monkeypatch)
    at = go(app(), ANALYSIS)
    at.button(key="research_run").click().run()
    assert not at.exception and at.radio(key="research_page").value == RESULTS
    assert at.selectbox(key="research_blade_field").value == "dthrust_per_span"
    assert "birim açıklık" in _text(at).lower() and "kordal basınç dağılımı değildir" in _text(at)
    at.selectbox(key="research_blade_field").set_value("thrust_element").run()
    assert not at.exception and "Eleman toplamı" in _text(at)
    at.slider(key="research_blade_radius").set_value(300.0).run()
    assert not at.exception


def test_coupled_blade_tab_synchronises_window_quantity_and_frame(tmp_path, monkeypatch):
    store(tmp_path, monkeypatch, PROJECT_AIRFOIL_IDS)
    bem(monkeypatch)
    _no_toolchain(monkeypatch, tmp_path)
    _forbid_runs(monkeypatch)
    row = _record(tmp_path, FIXTURE_RBF)
    at = app()
    at.session_state["research_coupled_results"] = ((json.dumps(row, sort_keys=True, separators=(",", ":")), False),)
    at.session_state["_coupled_active"] = (None, row["result_sha256"])
    go(at, RESULTS)
    at.radio(key="research_results_kind").set_value("Dinamik bağlaşık").run()
    at.radio(key="coupled_tab").set_value("3B oynatma").run()
    assert not at.exception
    at.select_slider(key="coupled_blade_window").set_value(20).run()
    at.selectbox(key="coupled_blade_field").set_value("fz_element").run()
    at.radio(key="coupled_blade_frame").set_value("rotor").run()
    assert not at.exception
    text = _text(at)
    assert "Eleman toplamı" in text and "tüm pencerelerde sabit" in text


def test_flow_scene_colours_the_blades_with_the_same_window(tmp_path, monkeypatch):
    at = _flow_app(tmp_path, monkeypatch)
    at.selectbox(key="coupled_flow_field").set_value("alpha").run()
    at.radio(key="coupled_flow_frame").set_value("rotor").run()
    assert not at.exception
    assert "aynı kabul edilen pencere" in _text(at)


def test_manual_colour_limits_are_kept_per_quantity(tmp_path, monkeypatch):
    store(tmp_path, monkeypatch, PROJECT_AIRFOIL_IDS)
    bem(monkeypatch)
    at = go(app(), ANALYSIS)
    at.button(key="research_run").click().run()
    at.radio(key="research_blade_scale").set_value("manual").run()
    at.number_input(key="research_blade_dthrust_per_span_lo").set_value(-5.0).run()
    at.selectbox(key="research_blade_field").set_value("alpha").run()
    assert not at.exception
    lo = at.number_input(key="research_blade_alpha_lo").value
    assert lo != -5.0                     # N/m limits never carried into degrees
