import pytest


@pytest.fixture(autouse=True)
def _isolated_results_folder(tmp_path, monkeypatch):
    # UI runs save every BEM result locally; keep tests out of the owner's outputs/research_results.
    monkeypatch.setenv("PYFOLDABLE_RESULTS", str(tmp_path / "saved_results"))
