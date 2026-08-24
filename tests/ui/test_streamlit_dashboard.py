from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


REPO_ROOT = Path(__file__).resolve().parents[2]
APP_PATH = REPO_ROOT / "apps" / "pyfoldable_dashboard.py"
PAGES = (
    "Genel Bakış",
    "Tasarım Geometrisi",
    "Çalışma Koşulları",
    "Analiz Çalıştırma",
    "Performans Sonuçları",
    "Katlanma Davranışı",
    "Motor–Pervane",
    "CFD / FEA / Deney",
    "Doğrulama ve Kanıtlar",
    "Raporlar",
)


def test_dashboard_renders_bound_project_status_without_exceptions():
    app = AppTest.from_file(str(APP_PATH)).run(timeout=20)

    assert not app.exception
    assert app.title[0].value == "PyFoldable Engineering Workspace"
    assert {metric.label for metric in app.metric} >= {
        "Açık çap",
        "Katlanmış zarf",
        "Kontrol noktası",
    }
    rendered = "\n".join(item.value for item in app.markdown)
    assert "PR-06C" in rendered
    assert "Bloklu" in rendered
    assert "PR-06D" in rendered
    assert "Tarama amaçlı" in rendered
    assert "Manifest SHA-256" in rendered
    assert app.warning


def test_performance_page_is_explicitly_screening_only():
    app = AppTest.from_file(str(APP_PATH)).run(timeout=20)
    navigation = app.sidebar.radio[0]
    navigation.set_value("Performans Sonuçları").run(timeout=20)

    assert not app.exception
    assert app.warning
    assert "Tarama amaçlı" in app.warning[0].value
    assert {metric.label for metric in app.metric} >= {
        "Vaka",
        "Çalışma noktası",
        "Açılma durumu",
    }


def test_analysis_page_is_idle_until_an_explicit_run():
    app = AppTest.from_file(str(APP_PATH)).run(timeout=20)
    app.sidebar.radio[0].set_value("Analiz Çalıştırma").run(timeout=20)

    assert not app.exception
    assert app.title[0].value == "Analiz Çalıştırma"
    assert any(button.label == "Tarama analizini çalıştır" for button in app.button)
    assert app.warning
    assert "254 mm" in app.warning[0].value
    assert "250 mm taslak" in app.warning[0].value
    assert not app.success


def test_analysis_page_runs_once_and_keeps_the_screening_result_in_session():
    app = AppTest.from_file(str(APP_PATH)).run(timeout=20)
    app.sidebar.radio[0].set_value("Analiz Çalıştırma").run(timeout=20)

    next(button for button in app.button if button.label == "Tarama analizini çalıştır").click()
    app.run(timeout=60)

    assert not app.exception
    assert app.success
    assert "arşiv raporuyla birebir eşleşti" in app.success[0].value
    assert {metric.label for metric in app.metric} >= {
        "Yeni koşum vakası",
        "Çalışma noktası",
        "Açılma durumu",
    }
    rendered = "\n".join(item.value for item in app.markdown)
    assert "session_screening_computation" in rendered
    assert "screening_only_until_pr06c_passes" in rendered
    assert "Physical qualification · false" in rendered
    assert any(
        button.label == "Oturum manifestini JSON indir"
        for button in app.get("download_button")
    )

    app.run(timeout=20)
    assert not app.exception
    assert app.success


def test_design_page_reads_the_canonical_geometry():
    app = AppTest.from_file(str(APP_PATH)).run(timeout=20)
    app.sidebar.radio[0].set_value("Tasarım Geometrisi").run(timeout=20)

    assert not app.exception
    rendered = "\n".join(item.value for item in app.markdown)
    assert "TIP_HINGED_250_CANONICAL" in rendered
    assert {metric.label for metric in app.metric} >= {
        "Kanat sayısı",
        "Menteşe yarıçapı",
    }
    assert app.get("plotly_chart")
    assert {item.label for item in app.number_input} >= {
        "Açık çap [mm]",
        "Göbek yarıçapı [mm]",
        "Menteşe yarıçapı [mm]",
    }
    assert {item.label for item in app.selectbox} >= {"Kesit modeli"}
    assert {item.label for item in app.slider} >= {"Katlanma açısı [deg]"}
    assert app.get("download_button")
    assert any(item.label == "Taslak TOML indir" for item in app.get("download_button"))
    assert any(item.value == "Niteliksiz tasarım taslağı" for item in app.caption)
    assert app.warning
    assert "geometri önizlemesi" in app.warning[0].value.lower()


def test_design_preview_controls_regenerate_the_geometry_safely():
    app = AppTest.from_file(str(APP_PATH)).run(timeout=20)
    app.sidebar.radio[0].set_value("Tasarım Geometrisi").run(timeout=20)

    diameter = next(item for item in app.number_input if item.label == "Açık çap [mm]")
    diameter.set_value(220.0)
    fold = next(item for item in app.slider if item.label == "Katlanma açısı [deg]")
    fold.set_value(-60)
    app.run(timeout=20)

    assert not app.exception
    assert app.get("plotly_chart")
    assert {metric.label for metric in app.metric} >= {
        "Radyal zarf çapı",
        "Mesh zarf çapı",
    }


def test_design_draft_tracks_preview_and_operating_condition_controls():
    app = AppTest.from_file(str(APP_PATH)).run(timeout=20)
    app.sidebar.radio[0].set_value("Tasarım Geometrisi").run(timeout=20)

    next(item for item in app.number_input if item.label == "Açık çap [mm]").set_value(220.0)
    next(item for item in app.number_input if item.label == "RPM").set_value(6800.0)
    next(item for item in app.number_input if item.label == "V∞ [m/s]").set_value(4.0)
    app.run(timeout=20)

    assert not app.exception
    rendered = "\n".join(item.value for item in app.markdown)
    assert "Kanonik kaynak SHA-256" in rendered
    assert "Taslak SHA-256" in rendered
    assert app.success
    assert "round-trip" in app.success[0].value


@pytest.mark.parametrize("page", PAGES)
def test_every_navigation_target_has_a_safe_render_path(page):
    app = AppTest.from_file(str(APP_PATH)).run(timeout=20)
    app.sidebar.radio[0].set_value(page).run(timeout=20)

    assert not app.exception
    assert app.title


def test_dashboard_uses_the_declared_streamlit_140_width_api():
    source = APP_PATH.read_text(encoding="utf-8")

    assert 'width="stretch"' not in source
    assert "use_container_width=True" in source
