"""The local result list validates before it applies its limit."""
import json
import os
from pathlib import Path

from pyfoldable.application import research_design as research

ROOT = Path(__file__).resolve().parents[2]


def test_newer_invalid_files_do_not_hide_an_older_valid_result(tmp_path, monkeypatch):
    monkeypatch.setenv("PYFOLDABLE_RESULTS", str(tmp_path))
    row = json.loads((ROOT / "reports/blade3d_20261113/bem_naca2412_axial800_2026-11-11-v1.json").read_text())
    valid = research.store_local_result(row)
    os.utime(valid, (1_000_000, 1_000_000))
    for index in range(51):
        (tmp_path / f"foreign_{index}.json").write_text("{}")
    listed = research.local_results()
    assert [r["result_sha256"] for r in listed] == [row["result_sha256"]]
