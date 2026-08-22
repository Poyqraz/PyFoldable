import json
import math
from pathlib import Path

import pytest

from pyfoldable.core import (
    BEMAnnulusSettings,
    BEMRotorElementError,
    BEMRotorError,
    BEMRotorSettings,
    BladeGeometry,
    BladeStation,
    OperatingCondition,
    PolarFamily,
    PolarTable,
    load_design_config,
    solve_bem_rotor,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REAL_POLAR_GOLDEN = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "polar_real_qualification"
    / "naca0012_re200k_real_v1"
    / "golden.json"
)


def _blade(*, second_airfoil: str = "foil") -> BladeGeometry:
    return BladeGeometry(
        diameter_m=0.30,
        hub_radius_m=0.02,
        blade_count=2,
        stations=(
            BladeStation(0.2, 0.06, 0.50, "foil"),
            BladeStation(0.5, 0.045, 0.35, "foil"),
            BladeStation(0.8, 0.03, 0.20, second_airfoil),
        ),
    )


def _condition(*, forward_speed: float = 0.0) -> OperatingCondition:
    return OperatingCondition(
        id="rotor-condition",
        angular_speed_rad_s=500.0,
        forward_speed_m_s=forward_speed,
        air_density_kg_m3=1.225,
        dynamic_viscosity_pa_s=1.81e-5,
        temperature_k=288.15,
        pressure_pa=101325.0,
    )


def _family(
    *, cl: float | tuple[float, float] = 0.8, airfoil_id: str = "foil"
) -> PolarFamily:
    cl_values = (cl, cl) if isinstance(cl, float) else cl
    return PolarFamily(
        tuple(
            PolarTable(
                airfoil_id=airfoil_id,
                scenario_id="rotor-synthetic",
                reynolds=reynolds,
                mach=mach,
                alpha_rad=(-math.pi / 2.0, math.pi / 2.0),
                cl=cl_values,
                cd=(0.02, 0.02),
                cm=(0.0, 0.0),
                source=f"rotor-m{mach}-re{reynolds}",
            )
            for mach in (0.0, 1.0)
            for reynolds in (1.0e4, 1.0e7)
        )
    )


def _promoted_real_xfoil_family() -> PolarFamily:
    payload = json.loads(REAL_POLAR_GOLDEN.read_text(encoding="utf-8"))
    request = payload["request"]
    points = payload["reference"]["points"]
    return PolarFamily(
        (
            PolarTable(
                airfoil_id=request["airfoil"]["id"],
                scenario_id=request["scenario_id"],
                reynolds=request["reynolds"],
                mach=request["mach"],
                alpha_rad=tuple(point["alpha_rad"] for point in points),
                cl=tuple(point["cl"] for point in points),
                cd=tuple(point["cd"] for point in points),
                cm=tuple(point["cm"] for point in points),
                source="promoted-real-xfoil-6.99",
                metadata={
                    "golden_fixture": str(
                        REAL_POLAR_GOLDEN.relative_to(PROJECT_ROOT)
                    )
                },
            ),
        )
    )


def test_midpoint_geometry_interpolation_and_load_sums_are_exact():
    result = solve_bem_rotor(
        _blade(),
        _condition(),
        {"foil": _family()},
        settings=BEMRotorSettings(annulus_count=2),
    )

    assert result.inner_radius_m == pytest.approx(0.2 * 0.15)
    assert result.outer_radius_m == pytest.approx(0.8 * 0.15)
    assert result.elements[0].solution.r_over_R == pytest.approx(0.35)
    assert result.elements[0].solution.chord_m == pytest.approx(0.0525)
    assert result.elements[0].solution.twist_rad == pytest.approx(0.425)
    assert result.thrust_n == pytest.approx(
        math.fsum(element.thrust_n for element in result.elements)
    )
    assert result.torque_nm == pytest.approx(
        math.fsum(element.torque_nm for element in result.elements)
    )
    assert result.shaft_power_w == pytest.approx(500.0 * result.torque_nm)
    assert result.power_coefficient == pytest.approx(
        2.0 * math.pi * result.torque_coefficient
    )
    assert result.propulsive_efficiency is None


def test_radial_midpoint_quadrature_converges_on_smooth_geometry():
    results = [
        solve_bem_rotor(
            _blade(),
            _condition(),
            {"foil": _family()},
            settings=BEMRotorSettings(annulus_count=count),
        )
        for count in (10, 20, 40, 80)
    ]

    thrust_differences = [
        abs(upper.thrust_n - lower.thrust_n)
        for lower, upper in zip(results, results[1:])
    ]
    torque_differences = [
        abs(upper.torque_nm - lower.torque_nm)
        for lower, upper in zip(results, results[1:])
    ]
    assert thrust_differences[2] < thrust_differences[1] < thrust_differences[0]
    assert torque_differences[2] < torque_differences[1] < torque_differences[0]
    assert thrust_differences[2] / results[-1].thrust_n < 5.0e-4
    assert torque_differences[2] / results[-1].torque_nm < 5.0e-4


def test_hub_to_tip_extension_is_explicit_and_auditable():
    result = solve_bem_rotor(
        _blade(),
        _condition(),
        {"foil": _family()},
        settings=BEMRotorSettings(annulus_count=12, radial_domain="hub_to_tip"),
    )

    assert result.inner_radius_m == pytest.approx(0.02)
    assert result.outer_radius_m == pytest.approx(0.15)
    assert result.geometry_extended
    assert result.elements[0].geometry_extrapolated
    assert result.elements[-1].geometry_extrapolated
    assert result.thrust_n > 0.0


def test_canonical_design_contract_runs_without_silent_geometry_extension():
    design = load_design_config(
        PROJECT_ROOT / "configs" / "designs" / "TIP_HINGED_250_CANONICAL.toml"
    )
    family = _family(airfoil_id="NACA2412")

    station_span = solve_bem_rotor(
        design.blade,
        design.operating_conditions[0],
        {"NACA2412": family},
        settings=BEMRotorSettings(annulus_count=20),
    )
    full_span = solve_bem_rotor(
        design.blade,
        design.operating_conditions[0],
        {"NACA2412": family},
        settings=BEMRotorSettings(annulus_count=20, radial_domain="hub_to_tip"),
    )

    assert station_span.inner_radius_m == pytest.approx(0.2 * design.blade.radius_m)
    assert station_span.outer_radius_m == pytest.approx(0.98 * design.blade.radius_m)
    assert not station_span.geometry_extended
    assert full_span.geometry_extended
    assert full_span.inner_radius_m == pytest.approx(design.blade.hub_radius_m)
    assert full_span.outer_radius_m == pytest.approx(design.blade.radius_m)


def test_optional_root_loss_is_propagated_to_each_annulus():
    result = solve_bem_rotor(
        _blade(),
        _condition(),
        {"foil": _family()},
        settings=BEMRotorSettings(
            annulus_count=12,
            radial_domain="hub_to_tip",
            annulus_settings=BEMAnnulusSettings(include_root_loss=True),
        ),
    )

    assert result.elements[0].solution.root_loss_factor < 1.0
    assert result.settings.annulus_settings.include_root_loss


def test_forward_flight_efficiency_and_provenance_are_serializable():
    condition = _condition(forward_speed=8.0)
    result = solve_bem_rotor(
        _blade(),
        condition,
        {"foil": _family()},
        bounds="clamp",
        settings=BEMRotorSettings(annulus_count=8),
    )

    assert result.propulsive_efficiency == pytest.approx(
        condition.forward_speed_m_s * result.thrust_n / result.shaft_power_w
    )
    assert result.maximum_residual_m2_s < 1.0e-8
    assert result.polar_sources
    assert "reynolds" in result.interpolated_dimensions
    payload = result.as_mapping()
    assert payload["schema_version"] == 2
    assert payload["integration_method"] == "midpoint"
    assert payload["settings"]["annulus_count"] == 8
    json.dumps(payload)


def test_signed_branch_integrates_mixed_local_loading_without_partial_results():
    result = solve_bem_rotor(
        _blade(),
        _condition(forward_speed=28.0),
        {"foil": _family(cl=(-0.5, 1.0))},
        settings=BEMRotorSettings(
            annulus_count=24,
            annulus_settings=BEMAnnulusSettings(
                loading_branch="signed_nonreversed"
            ),
        ),
    )

    regimes = {element.solution.loading_regime for element in result.elements}
    assert regimes == {"negative", "positive"}
    assert all(
        element.solution.relative_speed_m_s > 0.0 for element in result.elements
    )


def test_promoted_real_xfoil_polar_reaches_the_rotor_consumer():
    blade = BladeGeometry(
        diameter_m=0.30,
        hub_radius_m=0.02,
        blade_count=2,
        stations=(
            BladeStation(0.2, 0.045, math.radians(24.0), "NACA0012"),
            BladeStation(0.9, 0.025, math.radians(18.0), "NACA0012"),
        ),
    )
    family = _promoted_real_xfoil_family()

    result = solve_bem_rotor(
        blade,
        _condition(),
        {"NACA0012": family},
        bounds="clamp",
        settings=BEMRotorSettings(annulus_count=24),
    )

    assert result.thrust_n > 0.0
    assert result.torque_nm > 0.0
    assert result.polar_sources == ("promoted-real-xfoil-6.99",)
    assert {"mach", "reynolds"}.issubset(result.clamped_dimensions)


@pytest.mark.parametrize(
    ("blade", "families", "message"),
    (
        (_blade(second_airfoil="tip-foil"), {"foil": _family()}, "one airfoil_id"),
        (_blade(), {}, "No polar family"),
        (_blade(), {"foil": _family(airfoil_id="other")}, "mapping key"),
    ),
)
def test_ambiguous_airfoil_requests_fail_closed(blade, families, message):
    with pytest.raises(BEMRotorError, match=message):
        solve_bem_rotor(blade, _condition(), families)


def test_one_failed_annulus_aborts_without_a_partial_total():
    with pytest.raises(BEMRotorElementError, match=r"Annulus 0 at r/R="):
        solve_bem_rotor(
            _blade(),
            _condition(),
            {"foil": _family(cl=-0.5)},
            settings=BEMRotorSettings(annulus_count=8),
        )


@pytest.mark.parametrize("annulus_count", (2.5, True))
def test_rotor_settings_require_an_unambiguous_integer_count(annulus_count):
    with pytest.raises(TypeError, match="annulus_count"):
        BEMRotorSettings(annulus_count=annulus_count)
