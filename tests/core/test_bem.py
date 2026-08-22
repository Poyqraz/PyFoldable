import json
import math

import pytest

from pyfoldable.core import (
    BEMAnnulusError,
    BEMAnnulusSettings,
    BEMConvergenceError,
    BladeGeometry,
    BladeStation,
    OperatingCondition,
    PolarFamily,
    PolarTable,
    solve_bem_annulus,
)


def _blade(*, airfoil_id: str = "foil") -> tuple[BladeGeometry, BladeStation]:
    station = BladeStation(0.7, 0.035, math.radians(24.0), airfoil_id)
    blade = BladeGeometry(
        diameter_m=0.30,
        hub_radius_m=0.025,
        blade_count=2,
        stations=(
            BladeStation(0.2, 0.04, math.radians(30.0), airfoil_id),
            station,
        ),
    )
    return blade, station


def _condition(*, omega: float = 500.0, forward_speed: float = 0.0) -> OperatingCondition:
    return OperatingCondition(
        id="hover",
        angular_speed_rad_s=omega,
        forward_speed_m_s=forward_speed,
        air_density_kg_m3=1.225,
        dynamic_viscosity_pa_s=1.81e-5,
        temperature_k=288.15,
        pressure_pa=101325.0,
    )


def _family(*, cl: float = 0.8, cd: float = 0.02, airfoil_id: str = "foil") -> PolarFamily:
    tables = []
    for mach in (0.0, 1.0):
        for reynolds in (1.0e4, 1.0e7):
            tables.append(
                PolarTable(
                    airfoil_id=airfoil_id,
                    scenario_id="synthetic-constant",
                    reynolds=reynolds,
                    mach=mach,
                    alpha_rad=(-math.pi / 2.0, math.pi / 2.0),
                    cl=(cl, cl),
                    cd=(cd, cd),
                    cm=(0.0, 0.0),
                    source=f"constant-m{mach}-re{reynolds}",
                )
            )
    return PolarFamily(tuple(tables))


def test_hover_solution_is_finite_and_has_positive_induced_flow_and_loads():
    blade, station = _blade()

    result = solve_bem_annulus(blade, station, _condition(), _family())

    assert result.converged
    assert result.iterations > 0
    assert result.axial_induced_velocity_m_s > 0.0
    assert result.tangential_induced_velocity_m_s > 0.0
    assert result.differential_thrust_n_m > 0.0
    assert result.differential_torque_nm_m > 0.0
    assert all(
        math.isfinite(value)
        for value in (
            result.psi_rad,
            result.relative_speed_m_s,
            result.reynolds,
            result.mach,
            result.residual_m2_s,
        )
    )


def test_solution_satisfies_qprop_circulation_and_local_load_equations():
    blade, station = _blade()
    condition = _condition()

    result = solve_bem_annulus(blade, station, condition, _family())

    radius = station.r_over_R * blade.radius_m
    wa = condition.forward_speed_m_s + result.axial_induced_velocity_m_s
    wt = condition.angular_speed_rad_s * radius - result.tangential_induced_velocity_m_s
    wake_ratio = station.r_over_R * wa / wt
    correction = math.sqrt(
        1.0
        + (4.0 * wake_ratio * blade.radius_m / (math.pi * blade.blade_count * radius))
        ** 2
    )
    swirl_circulation = (
        result.tangential_induced_velocity_m_s
        * (4.0 * math.pi * radius / blade.blade_count)
        * result.tip_loss_factor
        * correction
    )
    blade_circulation = 0.5 * result.relative_speed_m_s * station.chord_m * result.cl
    force_scale = (
        blade.blade_count
        * 0.5
        * condition.air_density_kg_m3
        * result.relative_speed_m_s**2
        * station.chord_m
    )

    assert result.residual_m2_s == pytest.approx(
        swirl_circulation - blade_circulation, abs=1.0e-9
    )
    assert result.circulation_m2_s == pytest.approx(blade_circulation)
    assert (
        result.axial_induced_velocity_m_s * wa
        - result.tangential_induced_velocity_m_s * wt
    ) == pytest.approx(0.0, abs=1.0e-10)
    assert result.differential_thrust_n_m == pytest.approx(
        force_scale
        * (
            result.cl * math.cos(result.inflow_angle_rad)
            - result.cd * math.sin(result.inflow_angle_rad)
        )
    )
    assert result.differential_torque_nm_m == pytest.approx(
        force_scale
        * (
            result.cl * math.sin(result.inflow_angle_rad)
            + result.cd * math.cos(result.inflow_angle_rad)
        )
        * radius
    )


def test_zero_aerodynamic_loading_returns_no_induction_solution():
    blade, station = _blade()

    result = solve_bem_annulus(blade, station, _condition(), _family(cl=0.0, cd=0.0))

    assert result.iterations == 0
    assert result.psi_rad == pytest.approx(0.0)
    assert result.axial_induced_velocity_m_s == pytest.approx(0.0)
    assert result.tangential_induced_velocity_m_s == pytest.approx(0.0)
    assert result.differential_thrust_n_m == pytest.approx(0.0)
    assert result.differential_torque_nm_m == pytest.approx(0.0)


def test_tip_loss_can_be_disabled_explicitly():
    blade, station = _blade()

    with_loss = solve_bem_annulus(blade, station, _condition(), _family())
    without_loss = solve_bem_annulus(
        blade,
        station,
        _condition(),
        _family(),
        settings=BEMAnnulusSettings(include_tip_loss=False),
    )

    assert 0.0 < with_loss.tip_loss_factor < 1.0
    assert without_loss.tip_loss_factor == 1.0
    assert with_loss.psi_rad != pytest.approx(without_loss.psi_rad)


def test_root_loss_is_an_explicit_non_qprop_extension():
    blade, _ = _blade()
    station = BladeStation(0.2, 0.04, math.radians(30.0), "foil")

    qprop = solve_bem_annulus(blade, station, _condition(), _family())
    with_root_loss = solve_bem_annulus(
        blade,
        station,
        _condition(),
        _family(),
        settings=BEMAnnulusSettings(include_root_loss=True),
    )

    assert qprop.root_loss_factor == 1.0
    assert 0.0 < with_root_loss.root_loss_factor < 1.0
    radius = station.r_over_R * blade.radius_m
    root_argument = (
        0.5
        * blade.blade_count
        * (radius - blade.hub_radius_m)
        / (blade.hub_radius_m * math.sin(with_root_loss.inflow_angle_rad))
    )
    expected_root_loss = (2.0 / math.pi) * math.acos(math.exp(-root_argument))
    assert with_root_loss.root_loss_factor == pytest.approx(expected_root_loss)
    assert with_root_loss.combined_loss_factor == pytest.approx(
        with_root_loss.tip_loss_factor * with_root_loss.root_loss_factor
    )
    assert with_root_loss.psi_rad != pytest.approx(qprop.psi_rad)


@pytest.mark.parametrize(
    ("station", "condition", "family", "message"),
    (
        (BladeStation(1.0, 0.03, 0.3, "foil"), _condition(), _family(), "strictly"),
        (BladeStation(1.0 / 6.0, 0.03, 0.3, "foil"), _condition(), _family(), "strictly"),
        (_blade()[1], _condition(omega=0.0), _family(), "greater than zero"),
        (_blade()[1], _condition(forward_speed=-1.0), _family(), "Negative forward"),
        (_blade()[1], _condition(), _family(airfoil_id="other"), "does not match"),
    ),
)
def test_unsupported_annulus_requests_are_rejected(station, condition, family, message):
    blade, _ = _blade()

    with pytest.raises(BEMAnnulusError, match=message):
        solve_bem_annulus(blade, station, condition, family)


def test_no_positive_loading_solution_fails_closed():
    blade, station = _blade()

    with pytest.raises(BEMConvergenceError, match="No positive-loading"):
        solve_bem_annulus(blade, station, _condition(), _family(cl=-0.5, cd=0.0))


def test_root_solver_failure_uses_typed_convergence_error():
    blade, station = _blade()

    with pytest.raises(BEMConvergenceError, match="root solve"):
        solve_bem_annulus(
            blade,
            station,
            _condition(),
            _family(),
            settings=BEMAnnulusSettings(max_iterations=1),
        )


def test_result_mapping_preserves_polar_provenance_and_is_json_serializable():
    blade, station = _blade()

    result = solve_bem_annulus(blade, station, _condition(), _family())
    payload = result.as_mapping()

    assert payload["schema_version"] == 2
    assert payload["scenario_id"] == "synthetic-constant"
    assert payload["polar_bounds"] == "error"
    assert payload["settings"]["include_tip_loss"] is True
    assert payload["polar_sources"]
    assert "reynolds" in payload["interpolated_dimensions"]
    json.dumps(payload)


def test_annulus_settings_mapping_records_every_model_switch():
    settings = BEMAnnulusSettings(include_tip_loss=False, include_root_loss=True)

    payload = settings.as_mapping()

    assert payload["include_tip_loss"] is False
    assert payload["include_root_loss"] is True
    assert payload["relative_residual_tolerance"] == pytest.approx(1.0e-10)
    json.dumps(payload)


@pytest.mark.parametrize(
    "kwargs",
    (
        {"bracket_samples": 2.5},
        {"max_iterations": True},
        {"include_tip_loss": 1},
        {"include_root_loss": "yes"},
    ),
)
def test_annulus_settings_reject_ambiguous_runtime_types(kwargs):
    with pytest.raises(TypeError):
        BEMAnnulusSettings(**kwargs)
