"""'Görseller' page: lazy figure cards over existing builders, visible missing sources, archive containment."""
import base64
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from pyfoldable.application import coupled_views, gallery_figures as gf, gallery_ui
from pyfoldable.application import provider_design_analysis as managed, research_design as research
from pyfoldable.coupled import postprocess

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_fold_cycle_ui import _fast  # noqa: E402
from test_research_release_ui import ANALYSIS, app, go  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
GALLERY = "Görseller"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")


def section(at, name):
    if at.radio(key="research_page").value != GALLERY:
        go(at, GALLERY)
    at.radio(key="gallery_section").set_value(name).run()
    assert not at.exception
    return at


def text(at):
    return " ".join(x.value for kind in ("caption", "markdown", "info", "warning", "error") for x in getattr(at, kind))


def charts(at):
    return at.get("plotly_chart")


def images(at):
    return [*at.get("image"), *at.get("imgs")]   # typed element on newer Streamlit, raw proto name on 1.40


def test_every_section_opens_without_records_builds_nothing_and_names_missing_sources():
    at = app()
    for name in gallery_ui.SECTIONS:
        section(at, name)
        assert not charts(at) and not images(at)
    for name in ("BEM sonucu", "Açılma–kapanma çevrimi", "Dinamik bağlaşık"):
        assert "Kaynak yok" in text(section(at, name))
    assert at.radio(key="gallery_section").value == "Dinamik bağlaşık"
    go(at, ANALYSIS)
    go(at, GALLERY)
    assert at.radio(key="gallery_section").value == "Dinamik bağlaşık"   # the choice survives navigation


@pytest.fixture()
def bem_row(monkeypatch):
    monkeypatch.setenv("PYFOLDABLE_PROVIDER_STORE", str(ROOT / "data/research_reference/axial_800_store"))
    repo = managed.application_provider_repository()
    family = next(f for f in repo.families if f.family_id == "research_axial_800_deploy_xfoil_v3:NACA2412")
    return research.run_research(research.build_research_design(ROOT, research.defaults(ROOT)), family, repo, None)


def test_a_light_bem_card_builds_one_chart_on_click_and_names_its_source(bem_row):
    at = app()
    at.session_state["research_saved_results"] = ((research.saved_result_json(bem_row), True),)
    section(at, "BEM sonucu")
    assert not charts(at)
    at.button(key="gallery_build_bem_radial").click().run()
    assert not at.exception and len(charts(at)) == 1
    assert bem_row["result_sha256"][:8] in text(at) and "fiziksel yeterlilik yok" in text(at)
    assert "Kaynak yok" in text(at)                      # mechanism and overlay cards still say what they need
    at.button(key="gallery_light_bem").click().run()     # light cards with a source: radial, field, link, slipstream
    assert not at.exception and len(charts(at)) == 4


def test_heavy_cards_wait_for_their_own_click(monkeypatch):
    calls = []
    monkeypatch.setattr(gf, "legacy_pngs", lambda name, root: calls.append(name) or [(f"{name}.png", PNG)])
    at = section(app(), "Eski örnek boru hattı")
    at.button(key="gallery_light_legacy").click().run()
    assert not at.exception and calls == [] and not images(at)
    at.button(key="gallery_build_legacy_physics").click().run()
    assert not at.exception and calls == ["physics"] and len(images(at)) == 1
    assert "θ = −180°" in text(at) and "tasarım kanıtı değil" in text(at)
    at.button(key="gallery_build_legacy_physics").click().run()   # rebuilt only on request, never per rerun
    section(at, "Tasarım")
    section(at, "Eski örnek boru hattı")
    assert calls == ["physics", "physics"] and len(images(at)) == 1


def test_archive_lists_exactly_the_reports_files_and_refuses_paths_outside():
    reports = ROOT / "reports"
    assert gallery_ui.archive_files(ROOT) == sorted(str(p.relative_to(reports).as_posix())
                                                    for p in reports.rglob("*") if p.is_file())
    for bad in ("../pyproject.toml", "/etc/hostname", "../reports_other/x.json", "", "."):
        with pytest.raises(ValueError):
            gallery_ui.archive_path(ROOT, bad)
    assert gallery_ui.archive_path(ROOT, "pr06d_opening_sensitivity.json") == (reports / "pr06d_opening_sensitivity.json").resolve()
    for name in gallery_ui.archive_files(ROOT):    # every listed file passes containment, so selecting it cannot crash
        gallery_ui.archive_path(ROOT, name)
    at = section(app(), "Arşiv kanıtı")
    at.selectbox(key="gallery_archive_folder").set_value(".").run()
    at.selectbox(key="gallery_archive_file").set_value("pr06d_opening_sensitivity.json").run()
    at.button(key="gallery_build_archive_file").click().run()
    assert not at.exception and len(charts(at)) == 1 and "arşiv kanıtı · değiştirilmez" in text(at)
    at.selectbox(key="gallery_archive_folder").set_value("app_demo_20261116").run()
    at.selectbox(key="gallery_archive_file").set_value("app_demo_20261116/03_bem_result_naca4415.jpg").run()
    at.button(key="gallery_build_archive_file").click().run()
    assert not at.exception and len(images(at)) == 1 and "ekran görüntüsü · belgeleme" in text(at)


def test_archive_does_not_list_a_link_that_points_outside_reports(tmp_path):
    (tmp_path / "reports").mkdir()
    (tmp_path / "outside.txt").write_text("dış")
    (tmp_path / "reports/inside.txt").write_text("iç")
    (tmp_path / "reports/link.txt").symlink_to(tmp_path / "outside.txt")
    assert gallery_ui.archive_files(tmp_path) == ["inside.txt"]


def test_archive_shows_text_evidence_by_content_and_refuses_binary():
    capture = next((ROOT / "reports").rglob("capture-00/polar.bin"))      # a raw XFOIL capture: plain text
    assert "XFOIL" in gallery_ui._archive_build({"file": capture})["text"]
    packed = next(p for p in (ROOT / "reports").rglob("*") if p.suffix in (".gz", ".xz"))
    with pytest.raises(ValueError, match="ikili"):
        gallery_ui._archive_build({"file": packed})


def test_design_section_names_the_selected_version_and_warns_for_a_test_fixture(monkeypatch):
    fake = SimpleNamespace(stored_version=SimpleNamespace(version_label="test v1"), family_id="fixture:NACA2412",
                           source_identity="inert unit-test fixture; seed 0", evidence_class="inert_fixture", requests=())
    monkeypatch.setattr(gallery_ui.rui, "_families", lambda *a: {"f" * 64: fake})
    at = section(app(), "Tasarım")
    version = next(s for s in at.selectbox if str(s.key).startswith("gallery_design_version_"))
    version.select_index(1).run()
    assert not at.exception
    assert "Test kaydı" in text(at) and "inert unit-test fixture" in text(at)
    assert "XFOIL" not in text(at) and "Statik" not in text(at)    # nothing claimed that this version does not show


def test_cycle_cards_follow_the_chosen_blade(monkeypatch):
    seen = []
    for name in ("timeline_figure", "angle_figure", "contribution_figure", "element_figure", "energy_figure"):
        monkeypatch.setattr(gallery_ui.fcv, name, lambda *a, blade=0, **k: seen.append(blade))
    for card in gallery_ui.CARDS:
        if card["id"] in ("cycle_timeline", "cycle_angle", "cycle_contrib", "cycle_elements", "cycle_energy"):
            card["build"]({"cycle": {}, "blade": 1})
    assert seen == [1] * 5


def test_cycle_timeline_card_keeps_its_cursor_when_the_results_slider_moves_the_shared_figure(monkeypatch):
    import plotly.graph_objects as pgo
    shared = pgo.Figure(layout={"shapes": [{"type": "line", "x0": 0.0, "x1": 0.0, "y0": 0, "y1": 1}]})
    monkeypatch.setattr(gallery_ui.fcv, "timeline_figure", lambda *a, **k: shared)   # the module-cached figure
    card = next(c for c in gallery_ui.CARDS if c["id"] == "cycle_timeline")
    tile = card["build"]({"cycle": {}, "blade": 0})
    shared.layout.shapes[-1].update(x0=5.0, x1=5.0)                                  # a Results slider step
    assert tile.layout.shapes[-1].x0 == 0.0


def test_result_cards_reuse_the_workspace_blade_and_radial_views(bem_row, tmp_path):
    at = app()
    at.session_state["research_saved_results"] = ((research.saved_result_json(bem_row), True),)
    section(at, "BEM sonucu")
    for card in ("bem_fields", "bem_radial_link", "bem_blade3d", "bem_rotation"):
        at.button(key=f"gallery_build_{card}").click().run()
        assert not at.exception
    assert len(charts(at)) == 4 and "Görsel üretilemedi" not in text(at)
    section(at, "Tasarım")
    at.button(key="gallery_build_design_blade").click().run()
    assert not at.exception and len(charts(at)) == 1 and "Görsel üretilemedi" not in text(at)
    row = _coupled(tmp_path, "release_30w")
    at.session_state["research_coupled_results"] = ((coupled_views.saved_json(row), True),)
    section(at, "Dinamik bağlaşık")
    for card in ("coupled_radial", "coupled_blade3d", "coupled_animation", "coupled_loads"):
        at.button(key=f"gallery_build_{card}").click().run()
        assert not at.exception
    assert len(charts(at)) == 3 and "Bağlantı yükleri eki yok" in text(at)   # fixtures have no local run folder


def test_coupled_rate_torque_power_and_re_mach_coverage_have_cards(tmp_path):
    at = app()
    at.session_state["research_coupled_results"] = ((coupled_views.saved_json(_coupled(tmp_path, "release_30w")), True),)
    section(at, "Dinamik bağlaşık")
    for card in ("coupled_rate", "coupled_torque", "coupled_power", "coupled_coverage_re", "coupled_coverage_mach"):
        at.button(key=f"gallery_build_{card}").click().run()
        assert not at.exception
    assert len(charts(at)) == 5 and "Görsel üretilemedi" not in text(at)


def _coupled(tmp_path, name):
    run = tmp_path / name
    shutil.copytree(ROOT / "tests/fixtures/coupled" / name, run)
    return postprocess.build_result(run, participant_outcome="finished", exit_codes={}, extraction_ok=True)


def test_two_coupled_records_overlay_aligned_on_the_chosen_event(tmp_path):
    rows = [_coupled(tmp_path, "release_30w"), _coupled(tmp_path, "release_30w_rbf")]
    at = app()
    at.session_state["research_coupled_results"] = tuple((coupled_views.saved_json(r), True) for r in rows)
    section(at, "Dinamik bağlaşık")
    assert "Kaynak yok" in text(at)                  # the overlay waits for a second record
    at.selectbox(key="gallery_coupled_other").select_index(1).run()
    at.button(key="gallery_build_coupled_overlay").click().run()
    assert not at.exception and len(charts(at)) == 1
    assert rows[1]["result_sha256"][:8] in text(at)
    at.button(key="gallery_build_coupled_flow_plane").click().run()   # fixtures have no local run folder
    assert not at.exception and len(charts(at)) == 1 and "Akış eki yok" in text(at)
    at.button(key="gallery_build_coupled_theta").click().run()
    assert len(charts(at)) == 2
    at.selectbox(key="gallery_coupled_source").select_index(1).run()   # another record: built figures are not reused
    assert not at.exception and not charts(at)


def test_cycle_cards_build_from_the_active_cycle():
    at = go(app(), ANALYSIS)
    _fast(at)
    at.button(key="cycle_run").click().run()
    assert not at.exception
    section(at, "Açılma–kapanma çevrimi")
    at.button(key="gallery_light_cycle").click().run()   # angle, contributions, elements, energy (timeline is heavy)
    assert not at.exception and len(charts(at)) == 4
    assert "Kaynak yok" in text(at)                       # the comparison waits for a second saved cycle
