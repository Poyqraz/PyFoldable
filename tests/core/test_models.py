"""Invariant tests for solver-neutral canonical data models."""

import pytest

from pyfoldable.core import (
    AirfoilDefinition,
    BladeGeometry,
    BladeStation,
    PolarTable,
    PropellerDesign,
    SimulationResult,
)


def _stations() -> tuple[BladeStation, ...]:
    return (
        BladeStation(0.2, 0.028, 0.5, "NACA2412"),
        BladeStation(0.8, 0.015, 0.1, "NACA2412"),
    )


def test_blade_geometry_requires_monotonic_stations() -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        BladeGeometry(0.25, 0.018, 2, tuple(reversed(_stations())))


def test_blade_geometry_rejects_station_inside_hub() -> None:
    stations = (
        BladeStation(0.1, 0.028, 0.5, "NACA2412"),
        BladeStation(0.8, 0.015, 0.1, "NACA2412"),
    )
    with pytest.raises(ValueError, match="inside the hub"):
        BladeGeometry(0.25, 0.018, 2, stations)


def test_design_rejects_unknown_station_airfoil() -> None:
    blade = BladeGeometry(0.25, 0.018, 2, _stations())
    with pytest.raises(ValueError, match="undefined airfoils"):
        PropellerDesign("TEST", "", blade, (), ())


def test_polar_arrays_must_be_consistent() -> None:
    with pytest.raises(ValueError, match="same length"):
        PolarTable(
            "NACA2412",
            100_000.0,
            0.0,
            (-0.1, 0.0, 0.1),
            (-0.5, 0.0),
            (0.02, 0.01, 0.02),
            (0.0, 0.0, 0.0),
            "test",
        )


def test_minimal_design_accepts_defined_airfoil() -> None:
    blade = BladeGeometry(0.25, 0.018, 2, _stations())
    design = PropellerDesign(
        "TEST",
        "",
        blade,
        (AirfoilDefinition("NACA2412", "analytic"),),
        (),
    )
    assert design.blade.radius_m == pytest.approx(0.125)


def test_simulation_result_requires_reproducibility_identity() -> None:
    with pytest.raises(ValueError, match="git commit"):
        SimulationResult(
            design_id="TEST",
            operating_condition_id="hover",
            solver_name="bem",
            solver_version="0.1",
            git_commit="",
            converged=True,
        )

    result = SimulationResult(
        design_id="TEST",
        operating_condition_id="hover",
        solver_name="bem",
        solver_version="0.1",
        git_commit="abc1234",
        converged=True,
        polar_sources=("UIUC",),
        model_options={"tip_loss": "prandtl"},
    )
    assert result.polar_sources == ("UIUC",)
