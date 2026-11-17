"""'Görseller' page: lazy figure cards over existing builders, visible missing sources, archive containment."""
import base64
import shutil
import sys
from pathlib import Path

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
    at.button(key="gallery_light_bem").click().run()     # light cards with a source: radial and slipstream
    assert not at.exception and len(charts(at)) == 2


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
    at = section(app(), "Arşiv kanıtı")
    at.selectbox(key="gallery_archive_folder").set_value(".").run()
    at.selectbox(key="gallery_archive_file").set_value("pr06d_opening_sensitivity.json").run()
    at.button(key="gallery_build_archive_file").click().run()
    assert not at.exception and len(charts(at)) == 1 and "arşiv kanıtı · değiştirilmez" in text(at)
    at.selectbox(key="gallery_archive_folder").set_value("app_demo_20261116").run()
    at.selectbox(key="gallery_archive_file").set_value("app_demo_20261116/03_bem_result_naca4415.jpg").run()
    at.button(key="gallery_build_archive_file").click().run()
    assert not at.exception and len(images(at)) == 1 and "ekran görüntüsü · belgeleme" in text(at)


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


def test_cycle_cards_build_from_the_active_cycle():
    at = go(app(), ANALYSIS)
    _fast(at)
    at.button(key="cycle_run").click().run()
    assert not at.exception
    section(at, "Açılma–kapanma çevrimi")
    at.button(key="gallery_light_cycle").click().run()   # angle, contributions, elements, energy (timeline is heavy)
    assert not at.exception and len(charts(at)) == 4
    assert "Kaynak yok" in text(at)                       # the comparison waits for a second saved cycle
