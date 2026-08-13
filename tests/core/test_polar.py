"""Polar table loading and multidimensional interpolation tests."""

import math
from pathlib import Path

import pytest

from pyfoldable.core import (
    PolarFamily,
    PolarInterpolationError,
    PolarTable,
    load_polar_csv,
)


def _table(
    reynolds: float,
    *,
    mach: float = 0.0,
    lift_offset: float = 0.0,
    source: str | None = None,
    scenario_id: str = "clean",
) -> PolarTable:
    return PolarTable(
        airfoil_id="TEST",
        reynolds=reynolds,
        mach=mach,
        alpha_rad=(-0.1, 0.0, 0.1),
        cl=(-1.0 + lift_offset, lift_offset, 1.0 + lift_offset),
        cd=(0.03, 0.01, 0.03),
        cm=(-0.02, -0.02, -0.02),
        source=source or f"Re{reynolds:g}_M{mach:g}",
        scenario_id=scenario_id,
    )


def test_angle_interpolation_is_linear() -> None:
    result = PolarFamily((_table(100_000.0),)).query(
        alpha_rad=0.05,
        reynolds=100_000.0,
        mach=0.0,
    )

    assert result.cl == pytest.approx(0.5)
    assert result.cd == pytest.approx(0.02)
    assert result.interpolated_dimensions == ("alpha_rad",)
    assert result.clamped_dimensions == ()


def test_reynolds_interpolation_uses_log_space() -> None:
    family = PolarFamily(
        (
            _table(100_000.0, lift_offset=0.0, source="low"),
            _table(400_000.0, lift_offset=2.0, source="high"),
        )
    )
    result = family.query(alpha_rad=0.0, reynolds=200_000.0, mach=0.0)

    assert result.cl == pytest.approx(1.0)
    assert result.sources == ("low", "high")
    assert result.interpolated_dimensions == ("reynolds",)


def test_mach_interpolation_is_linear() -> None:
    family = PolarFamily(
        (
            _table(100_000.0, mach=0.0, lift_offset=0.0),
            _table(100_000.0, mach=0.2, lift_offset=1.0),
        )
    )
    result = family.query(alpha_rad=0.0, reynolds=100_000.0, mach=0.1)

    assert result.cl == pytest.approx(0.5)
    assert result.interpolated_dimensions == ("mach",)


def test_out_of_bounds_errors_by_default() -> None:
    family = PolarFamily((_table(100_000.0),))

    with pytest.raises(PolarInterpolationError, match="alpha_rad"):
        family.query(alpha_rad=0.2, reynolds=100_000.0, mach=0.0)
    with pytest.raises(PolarInterpolationError, match="reynolds"):
        family.query(alpha_rad=0.0, reynolds=50_000.0, mach=0.0)
    with pytest.raises(PolarInterpolationError, match="mach"):
        family.query(alpha_rad=0.0, reynolds=100_000.0, mach=0.1)


def test_clamp_policy_reports_every_clamped_dimension() -> None:
    result = PolarFamily((_table(100_000.0),)).query(
        alpha_rad=0.2,
        reynolds=50_000.0,
        mach=0.1,
        bounds="clamp",
    )

    assert result.cl == pytest.approx(1.0)
    assert result.clamped_dimensions == ("alpha_rad", "mach", "reynolds")


def test_extrapolation_policy_is_not_available() -> None:
    with pytest.raises(PolarInterpolationError, match="Unsupported bounds"):
        PolarFamily((_table(100_000.0),)).query(
            alpha_rad=0.0,
            reynolds=100_000.0,
            mach=0.0,
            bounds="extrapolate",  # type: ignore[arg-type]
        )


def test_family_rejects_mixed_airfoils_scenarios_and_duplicate_points() -> None:
    other_airfoil = PolarTable(
        "OTHER",
        100_000.0,
        0.0,
        (-0.1, 0.1),
        (-1.0, 1.0),
        (0.02, 0.02),
        (0.0, 0.0),
        "x",
    )
    with pytest.raises(ValueError, match="same airfoil"):
        PolarFamily((_table(100_000.0), other_airfoil))
    with pytest.raises(ValueError, match="same scenario"):
        PolarFamily((_table(100_000.0), _table(200_000.0, scenario_id="rough")))
    with pytest.raises(ValueError, match="duplicate"):
        PolarFamily((_table(100_000.0), _table(100_000.0, source="duplicate")))


def test_polar_csv_loads_degrees_and_sorts_rows(tmp_path: Path) -> None:
    path = tmp_path / "polar.csv"
    path.write_text(
        "alpha_deg,cl,cd,cm\n5,0.5,0.02,-0.01\n-5,-0.5,0.02,-0.01\n0,0,0.01,-0.01\n",
        encoding="utf-8",
    )

    table = load_polar_csv(
        path,
        airfoil_id="TEST",
        reynolds=150_000.0,
        scenario_id="rough",
        metadata={"kind": "experimental"},
    )

    assert table.alpha_rad == pytest.approx(
        (math.radians(-5.0), 0.0, math.radians(5.0))
    )
    assert table.cl == (-0.5, 0.0, 0.5)
    assert table.scenario_id == "rough"
    assert table.metadata["kind"] == "experimental"


def test_polar_csv_rejects_missing_columns(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("alpha_deg,cl,cd\n0,0,0.01\n", encoding="utf-8")

    with pytest.raises(PolarInterpolationError, match="requires"):
        load_polar_csv(path, airfoil_id="TEST", reynolds=100_000.0)
