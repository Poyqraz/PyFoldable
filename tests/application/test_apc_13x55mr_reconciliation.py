"""Source-bound APC 13x5.5MR inventory. No vendor table and no solver."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from pyfoldable.application.apc_13x55mr_reconciliation import (
    ANSYS_EXPECTED_SHA256,
    build_apc_13x55mr_reconciliation,
    render_apc_13x55mr_reconciliation,
)


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports" / "apc_13x55mr_ansys_reconciliation"


def test_diameters_stay_distinct_and_unscaled() -> None:
    report = build_apc_13x55mr_reconciliation()
    diameters = set(report["diameters_mm"].values())
    assert diameters == {"330.2", "328.676", "328.93", "329.3519"}
    assert Decimal("13") * Decimal("25.4") == Decimal("330.2")
    assert Decimal("6.47") * Decimal("25.4") * 2 == Decimal("328.676")
    assert Decimal("6.475") * Decimal("25.4") * 2 == Decimal("328.9300")
    assert report["derived_checks"]["rounded_torque_reproduces_published_power"] is False


def test_inventory_keeps_apc_predictions_out_of_the_cfd_record() -> None:
    report = build_apc_13x55mr_reconciliation()
    assert report["physical_qualification"] is False
    assert report["genuine_two_profile_comparison"] == "UNESTABLISHED"
    assert report["solvers_executed"] == []
    assert report["performance_substitution_into_cfd"] is False
    assert report["synthetic_apc_202602_fixture_is_manufacturer_data"] is False
    assert report["performance_inventory"]["classification"] == "manufacturer_computational_prediction"
    assert report["performance_inventory"]["experimental_measurement"] is False
    inventory = report["performance_inventory"]
    assert inventory["full_coefficient_row_count"] == 502
    assert inventory["partial_speed_row_count"] == 8
    assert inventory["speed_line_count"] == 510
    partial_rpms = [block["rpm"] for block in inventory["rpm_blocks"] if block["partial_speed_rows"]]
    assert partial_rpms == [7000, 8000, 9000, 12000, 14000, 15000, 16000, 17000]
    assert report["performance_inventory"]["full_table_committed"] is False
    assert report["performance_inventory"]["rho_numeric_value_in_file"] is None
    assert report["published_4000_rpm_static_row"]["Thrust_N"] == "6.002"
    assert report["ansys_report"]["sha256_verified"] is False
    assert report["ansys_report"]["expected_sha256"] == ANSYS_EXPECTED_SHA256
    assert report["ansys_report"]["figures_read"] is False
    selected = [row for row in report["model_separation"] if row["selected_for_this_reconciliation"]]
    assert selected == [report["model_separation"][0]]
    assert selected[0]["name"] == "13x5.5MR"
    assert any(row["name"] == "13x5.5E" for row in report["model_separation"])
    assert any("MRF" in row["name"] for row in report["model_separation"])


def test_committed_report_matches_the_builder_and_omits_vendor_files() -> None:
    report = build_apc_13x55mr_reconciliation()
    stored = json.loads((REPORT / "report.json").read_text(encoding="utf-8"))
    assert stored == report
    text = (REPORT / "report.md").read_text(encoding="utf-8")
    assert text == render_apc_13x55mr_reconciliation(report)
    assert "physical_qualification: false" in text
    assert "329.3519" in text
    assert "not in the workspace" in text
    assert "same-mesh second-order" in text
    assert not (ROOT / "data" / "propellers" / "apc_202602" / "PER3_13x55MR.dat").exists()
    readme = (ROOT / "data" / "propellers" / "apc_202602" / "README.md").read_text(encoding="utf-8")
    assert "no APC geometry or performance table" in readme
