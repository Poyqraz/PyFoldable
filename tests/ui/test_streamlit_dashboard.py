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


@pytest.mark.parametrize("page", PAGES)
def test_every_navigation_target_has_a_safe_render_path(page):
    app = AppTest.from_file(str(APP_PATH)).run(timeout=20)
    app.sidebar.radio[0].set_value(page).run(timeout=20)

    assert not app.exception
    assert app.title
