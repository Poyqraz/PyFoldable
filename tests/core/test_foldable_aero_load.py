"""Screening tests for the planar projected material-load adapter.

These checks do not qualify folded-tip aerodynamics, aerodynamic hinge torque,
or a project rotor. CMM-2 transient coupling is not under test.
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import replace
from decimal import Context, Decimal, localcontext
from pathlib import Path

import numpy as np
import pytest

from pyfoldable.core import (
    BEMAnnulusSettings,
    BEMRotorSettings,
    BladeGeometry,
    BladeStation,
    FoldableRotorState,
    OperatingCondition,
    PolarFamily,
    PolarTable,
    SpanwisePolarAnchor,
    SpanwisePolarSchedule,
    solve_bem_rotor,
    solve_foldable_bem_rotor,
)
import pyfoldable.core.foldable_aero_load as foldable_aero_load
from pyfoldable.core.foldable_aero_load import (
    DISTRIBUTED_COUPLE_MODEL,
    HINGE_RATE_AERODYNAMIC_MODEL,
    LOAD_MAPPING_MODEL,
    PROJECTION_MODEL,
    QUALIFICATION,
    SECTIONAL_AERODYNAMIC_COUPLE,
    MappedRadialContribution,
    PlanarProjectedMaterialLoadError,
    ProjectedAnnulusLoad,
    aerodynamic_generalized_power_w,
    map_foldable_bem_aero_loads,
    map_projected_annulus,
    map_projected_material_loads,
    one_blade_material_force_density_n_per_m,
    projected_radius_m,
)
from pyfoldable.core.foldable_aero_load import _stable_movable_hinge_integral


def _annulus(
    inner: float,
    outer: float,
    *,
    thrust: float = 0.0,
    torque: float,
    extrapolated: bool = False,
    index: int = 0,
) -> ProjectedAnnulusLoad:
    return ProjectedAnnulusLoad(
        inner,
        outer,
        thrust,
        torque,
        extrapolated,
        index,
    )


def _map_cell(
    inner: float,
    outer: float,
    *,
    thrust: float,
    torque: float,
    hinge: float,
    theta: float,
    blades: int,
) -> tuple[MappedRadialContribution, ...]:
    return map_projected_annulus(
        _annulus(inner, outer, thrust=thrust, torque=torque),
        hinge_radius_m=hinge,
        theta_rad=theta,
        blade_count=blades,
    )


def _quad(function, lower: float, upper: float) -> float:
    nodes, weights = np.polynomial.legendre.leggauss(64)
    midpoint = 0.5 * (lower + upper)
    half = 0.5 * (upper - lower)
    samples = [
        float(weight) * function(midpoint + half * float(node))
        for node, weight in zip(nodes, weights)
    ]
    return float(math.fsum(samples) * half)


def _blade() -> BladeGeometry:
    return BladeGeometry(
        diameter_m=0.30,
        hub_radius_m=0.02,
        blade_count=2,
        stations=(
            BladeStation(0.2, 0.04, 0.45, "root"),
            BladeStation(0.5, 0.035, 0.35, "root"),
            BladeStation(0.8, 0.025, 0.22, "tip"),
            BladeStation(1.0, 0.015, 0.15, "tip"),
        ),
    )


def _family(airfoil_id: str, cl: float, cm: float = 0.0) -> PolarFamily:
    return PolarFamily(
        tuple(
            PolarTable(
                airfoil_id=airfoil_id,
                scenario_id="aero-load-screen",
                reynolds=reynolds,
                mach=mach,
                alpha_rad=(-math.pi / 2.0, math.pi / 2.0),
                cl=(cl, cl),
                cd=(0.02, 0.02),
                cm=(cm, cm),
                source=f"fixture:{airfoil_id}:cm{cm}",
            )
            for mach in (0.0, 0.5)
            for reynolds in (1.0e3, 1.0e7)
        )
    )


def _schedule(cm: float = 0.0) -> SpanwisePolarSchedule:
    return SpanwisePolarSchedule(
        "root-to-tip",
        (
            SpanwisePolarAnchor(0.2, _family("root", 0.6, cm)),
            SpanwisePolarAnchor(0.8, _family("tip", 0.8, cm)),
            SpanwisePolarAnchor(1.0, _family("tip", 0.8, cm)),
        ),
    )


def _condition() -> OperatingCondition:
    return OperatingCondition(
        id="aero-load",
        angular_speed_rad_s=500.0,
        forward_speed_m_s=4.0,
        air_density_kg_m3=1.225,
        dynamic_viscosity_pa_s=1.81e-5,
        temperature_k=288.15,
        pressure_pa=101325.0,
    )


def _settings(annulus_count: int, radial_domain: str = "station_span") -> BEMRotorSettings:
    return BEMRotorSettings(
        annulus_count,
        radial_domain,
        BEMAnnulusSettings(loading_branch="signed_nonreversed"),
    )


def _state(theta: float, hinge: float = 0.075) -> FoldableRotorState:
    return FoldableRotorState(
        id=f"theta-{theta:.6g}",
        hinge_radius_m=hinge,
        opening_angle_rad=theta,
        deployed_angle_rad=0.0,
    )


def _roundoff_tolerance(*values: float, splits: int) -> float:
    scale = max(abs(value) for value in values)
    if scale == 0.0:
        return 0.0
    return (splits + 1) * math.ulp(scale)


def test_analytic_interval_shaft_generalized_load():
    hinge = 0.125
    inner = 0.25
    outer = 0.5
    torque_density = 4.0
    blades = 2
    pieces = _map_cell(
        inner,
        outer,
        thrust=8.0,
        torque=torque_density,
        hinge=hinge,
        theta=0.0,
        blades=blades,
    )

    assert len(pieces) == 1
    expected = -(torque_density / blades) * (outer - inner)
    assert pieces[0].one_blade_shaft_generalized_load_nm == expected
    assert pieces[0].one_blade_shaft_generalized_load_nm < 0.0
    assert pieces[0].whole_rotor_resisting_torque_nm == torque_density * (outer - inner)


def test_analytic_movable_hinge_generalized_load():
    hinge = 0.125
    inner = 0.25
    outer = 0.5
    torque_density = 4.0
    thrust_density = 8.0
    blades = 2
    theta = 0.3
    with_thrust = _map_cell(
        inner,
        outer,
        thrust=thrust_density,
        torque=torque_density,
        hinge=hinge,
        theta=theta,
        blades=blades,
    )
    without_thrust = _map_cell(
        inner,
        outer,
        thrust=0.0,
        torque=torque_density,
        hinge=hinge,
        theta=theta,
        blades=blades,
    )
    expected = -(torque_density / blades) * (
        (outer - inner) - hinge * math.log(outer / inner)
    )

    assert with_thrust[0].role == "movable_tip"
    assert with_thrust[0].one_tip_hinge_generalized_torque_nm == expected
    assert with_thrust[0].one_tip_hinge_generalized_torque_nm < 0.0
    assert (
        with_thrust[0].one_tip_hinge_generalized_torque_nm
        == without_thrust[0].one_tip_hinge_generalized_torque_nm
    )
    assert (
        with_thrust[0].one_blade_shaft_generalized_load_nm
        == without_thrust[0].one_blade_shaft_generalized_load_nm
    )
    assert with_thrust[0].whole_rotor_thrust_n != without_thrust[0].whole_rotor_thrust_n


def test_virtual_work_quadrature_matches_generalized_loads():
    hinge = 0.2
    theta = 0.35
    blades = 3
    torque_density = 1.7
    thrust_density = -0.4
    phi = 0.7
    factor = math.cos(theta)
    s0 = 0.04
    s1 = 0.11
    r0 = hinge + s0 * factor
    r1 = hinge + s1 * factor
    piece = _map_cell(
        r0,
        r1,
        thrust=thrust_density,
        torque=torque_density,
        hinge=hinge,
        theta=theta,
        blades=blades,
    )[0]

    def basis_r(angle: float) -> tuple[float, float]:
        return (math.cos(angle), math.sin(angle))

    def basis_t(angle: float) -> tuple[float, float]:
        return (-math.sin(angle), math.cos(angle))

    def dot(left: tuple[float, float], right: tuple[float, float]) -> float:
        return left[0] * right[0] + left[1] * right[1]

    tangential = basis_t(phi)

    def integrand(coordinate: str, material: float) -> float:
        projected = hinge + material * factor
        f_t = -(torque_density / (blades * projected)) * factor
        derivative = (
            (
                hinge * basis_t(phi)[0] + material * basis_t(phi + theta)[0],
                hinge * basis_t(phi)[1] + material * basis_t(phi + theta)[1],
            )
            if coordinate == "phi"
            else (
                material * basis_t(phi + theta)[0],
                material * basis_t(phi + theta)[1],
            )
        )
        return f_t * dot(tangential, derivative)

    q_phi = _quad(lambda material: integrand("phi", material), s0, s1)
    q_theta = _quad(lambda material: integrand("theta", material), s0, s1)
    assert q_phi == pytest.approx(
        piece.one_blade_shaft_generalized_load_nm, rel=0.0, abs=1e-12
    )
    assert q_theta == pytest.approx(
        piece.one_tip_hinge_generalized_torque_nm, rel=0.0, abs=1e-12
    )

    omega = -12.5
    theta_dot = 3.25

    def power_density(material: float) -> float:
        return omega * integrand("phi", material) + theta_dot * integrand(
            "theta", material
        )

    virtual_power = _quad(power_density, s0, s1)
    generalized = (
        omega * piece.one_blade_shaft_generalized_load_nm
        + theta_dot * piece.one_tip_hinge_generalized_torque_nm
    )
    assert virtual_power == pytest.approx(generalized, rel=0.0, abs=1e-11)


def test_generalized_power_identity():
    hinge = 0.125
    tip = 0.5
    torque_density = 2.0
    blades = 2
    theta_dot = 1.5
    omega = 40.0
    mapped = map_projected_material_loads(
        (_annulus(hinge, tip, thrust=3.0, torque=torque_density),),
        hinge_radius_m=hinge,
        theta_rad=0.2,
        blade_count=blades,
        hinge_rate_rad_s=theta_dot,
        projected_tip_radius_m=tip,
        operating_condition_id="power",
    )
    power = mapped.aerodynamic_generalized_power_w(omega)
    formula = aerodynamic_generalized_power_w(
        whole_rotor_shaft_generalized_load_nm=(
            mapped.whole_rotor_aerodynamic_shaft_generalized_load_nm
        ),
        one_tip_hinge_generalized_torque_nm=(
            mapped.one_tip_hinge_generalized_torque_nm
        ),
        blade_count=blades,
        omega_rad_s=omega,
        hinge_rate_rad_s=theta_dot,
    )
    shaft_only = (
        -mapped.resisting_shaft_torque_nm * omega
    )
    assert power == formula
    assert power != shaft_only
    assert power - shaft_only == pytest.approx(
        blades * mapped.one_tip_hinge_generalized_torque_nm * theta_dot,
        rel=0.0,
        abs=1e-12,
    )


def test_zero_aerodynamic_load():
    hinge = 0.2
    tip = 0.45
    for theta, theta_dot, omega in (
        (0.0, 0.0, 10.0),
        (-0.8, 4.0, -3.0),
        (1.1, -2.5, 80.0),
    ):
        mapped = map_projected_material_loads(
            (_annulus(0.1, tip, thrust=6.0, torque=0.0),),
            hinge_radius_m=hinge,
            theta_rad=theta,
            blade_count=4,
            hinge_rate_rad_s=theta_dot,
            projected_tip_radius_m=tip,
            operating_condition_id="zero-torque",
        )
        assert mapped.whole_rotor_aerodynamic_shaft_generalized_load_nm == 0.0
        assert mapped.one_tip_hinge_generalized_torque_nm == 0.0
        assert mapped.aerodynamic_generalized_power_w(omega) == 0.0
        assert mapped.resisting_shaft_torque_nm == 0.0


def test_deployed_sign_and_projection():
    hinge = 0.125
    inner = 0.25
    outer = 0.5
    pieces = _map_cell(
        inner,
        outer,
        thrust=1.0,
        torque=2.0,
        hinge=hinge,
        theta=0.0,
        blades=2,
    )
    mapped = map_projected_material_loads(
        (_annulus(hinge, outer, thrust=1.0, torque=2.0),),
        hinge_radius_m=hinge,
        theta_rad=0.0,
        blade_count=2,
        hinge_rate_rad_s=0.0,
        projected_tip_radius_m=outer,
        operating_condition_id="deployed",
    )

    assert mapped.projection_factor == 1.0
    assert pieces[0].one_tip_hinge_generalized_torque_nm < 0.0
    assert projected_radius_m(0.2, hinge_radius_m=hinge, theta_rad=0.0) == hinge + 0.2


def test_blade_count_scaling():
    hinge = 0.25
    inner = 0.25
    outer = 1.0
    torque_density = 4.0
    products = []
    shaft_loads = []
    one_tips = []
    for blades in (1, 2, 4):
        mapped = map_projected_material_loads(
            (_annulus(inner, outer, thrust=8.0, torque=torque_density),),
            hinge_radius_m=hinge,
            theta_rad=0.25,
            blade_count=blades,
            hinge_rate_rad_s=0.0,
            projected_tip_radius_m=outer,
            operating_condition_id="scaling",
        )
        products.append(mapped.synchronous_n_times_one_tip_hinge_generalized_torque_nm)
        shaft_loads.append(mapped.whole_rotor_aerodynamic_shaft_generalized_load_nm)
        one_tips.append(mapped.one_tip_hinge_generalized_torque_nm)

    assert shaft_loads[0] == shaft_loads[1] == shaft_loads[2]
    assert shaft_loads[0] == -torque_density * (outer - inner)
    assert one_tips[1] == pytest.approx(one_tips[0] / 2.0, rel=0.0, abs=1e-15)
    assert one_tips[2] == pytest.approx(one_tips[0] / 4.0, rel=0.0, abs=1e-15)
    assert products[1] == pytest.approx(products[0], rel=0.0, abs=1e-15)
    assert products[2] == pytest.approx(products[0], rel=0.0, abs=1e-15)


def test_fixed_root_contributes_shaft_load_and_zero_hinge_load():
    hinge = 0.5
    inner = 0.25
    outer = 0.375
    torque_density = 4.0
    blades = 2
    pieces = _map_cell(
        inner,
        outer,
        thrust=1.0,
        torque=torque_density,
        hinge=hinge,
        theta=0.4,
        blades=blades,
    )

    assert len(pieces) == 1
    assert pieces[0].role == "fixed_root"
    assert pieces[0].one_tip_hinge_generalized_torque_nm == 0.0
    assert pieces[0].one_blade_shaft_generalized_load_nm == (
        -(torque_density / blades) * (outer - inner)
    )


def test_hinge_crossing_partition_preserves_cell_loads():
    hinge = 0.125
    inner = 0.0625
    outer = 0.25
    thrust_density = 4.0
    torque_density = 2.0
    pieces = _map_cell(
        inner,
        outer,
        thrust=thrust_density,
        torque=torque_density,
        hinge=hinge,
        theta=-0.4,
        blades=2,
    )
    fixed, movable = pieces
    cell_thrust = thrust_density * (outer - inner)
    cell_torque = torque_density * (outer - inner)

    assert fixed.role == "fixed_root"
    assert movable.role == "movable_tip"
    assert fixed.inner_projected_radius_m == inner
    assert fixed.outer_projected_radius_m == hinge
    assert movable.inner_projected_radius_m == hinge
    assert movable.outer_projected_radius_m == outer
    assert (hinge - inner) + (outer - hinge) == outer - inner
    assert math.fsum(
        (fixed.whole_rotor_thrust_n, movable.whole_rotor_thrust_n)
    ) == cell_thrust
    assert math.fsum(
        (
            fixed.whole_rotor_resisting_torque_nm,
            movable.whole_rotor_resisting_torque_nm,
        )
    ) == cell_torque
    assert fixed.one_tip_hinge_generalized_torque_nm == 0.0
    assert movable.one_tip_hinge_generalized_torque_nm == -(torque_density / 2.0) * (
        (outer - hinge) - hinge * math.log(outer / hinge)
    )
    assert movable.one_tip_hinge_generalized_torque_nm < 0.0


def test_projected_material_jacobian():
    hinge = 0.08
    s0 = 0.02
    s1 = 0.05
    torque_density = 1.25
    thrust_density = 3.5
    blades = 2
    for theta in (-1.0, -0.4, 0.0, 0.2, 1.2):
        factor = math.cos(theta)
        r0 = projected_radius_m(s0, hinge_radius_m=hinge, theta_rad=theta)
        r1 = projected_radius_m(s1, hinge_radius_m=hinge, theta_rad=theta)
        assert r0 == hinge + s0 * factor
        assert r1 - r0 == pytest.approx(
            factor * (s1 - s0), rel=0.0, abs=4.0 * math.ulp(max(abs(r1), 1.0))
        )
        projected = hinge + 0.03 * factor
        f_z, f_t, f_r = one_blade_material_force_density_n_per_m(
            0.03,
            hinge_radius_m=hinge,
            theta_rad=theta,
            blade_count=blades,
            differential_thrust_n_m=thrust_density,
            differential_torque_nm_m=torque_density,
        )
        assert f_r == 0.0
        assert f_z == (thrust_density / blades) * factor
        assert f_t == -(torque_density / (blades * projected)) * factor

    near = math.acos(1.0e-8)
    assert projected_radius_m(0.01, hinge_radius_m=hinge, theta_rad=near) > hinge
    with pytest.raises(PlanarProjectedMaterialLoadError, match="projection"):
        projected_radius_m(0.01, hinge_radius_m=hinge, theta_rad=0.5 * math.pi)
    with pytest.raises(PlanarProjectedMaterialLoadError, match="projection"):
        projected_radius_m(0.01, hinge_radius_m=hinge, theta_rad=-0.5 * math.pi)
    with pytest.raises(PlanarProjectedMaterialLoadError, match="projection factor"):
        projected_radius_m(
            0.01,
            hinge_radius_m=hinge,
            theta_rad=math.acos(5.0e-13),
        )


def test_incomplete_movable_span_fails_closed():
    hinge = 0.05
    tip = 0.30
    partial = (_annulus(0.10, 0.20, torque=1.0, index=0),)
    with pytest.raises(PlanarProjectedMaterialLoadError, match="coverage"):
        map_projected_material_loads(
            partial,
            hinge_radius_m=hinge,
            theta_rad=0.2,
            blade_count=2,
            hinge_rate_rad_s=0.0,
            projected_tip_radius_m=tip,
            operating_condition_id="partial",
        )

    gapped = (
        _annulus(0.04, 0.10, torque=1.0, index=0),
        _annulus(0.12, tip, torque=1.0, index=1),
    )
    with pytest.raises(PlanarProjectedMaterialLoadError, match="gap"):
        map_projected_material_loads(
            gapped,
            hinge_radius_m=hinge,
            theta_rad=0.2,
            blade_count=2,
            hinge_rate_rad_s=0.0,
            projected_tip_radius_m=tip,
            operating_condition_id="gapped",
        )

    overlap = (
        _annulus(0.04, 0.12, torque=1.0, index=0),
        _annulus(0.10, tip, torque=1.0, index=1),
    )
    with pytest.raises(PlanarProjectedMaterialLoadError, match="overlap"):
        map_projected_material_loads(
            overlap,
            hinge_radius_m=hinge,
            theta_rad=0.2,
            blade_count=2,
            hinge_rate_rad_s=0.0,
            projected_tip_radius_m=tip,
            operating_condition_id="overlap",
        )


def test_invalid_projection_fails_closed():
    cell = (_annulus(0.1, 0.2, torque=1.0),)
    for theta in (math.nan, math.inf, -math.inf, 2.0, math.pi / 2.0):
        with pytest.raises(PlanarProjectedMaterialLoadError):
            map_projected_material_loads(
                cell,
                hinge_radius_m=0.05,
                theta_rad=theta,
                blade_count=2,
                hinge_rate_rad_s=0.0,
                projected_tip_radius_m=0.2,
                operating_condition_id="invalid",
            )
    for rate in (math.nan, math.inf):
        with pytest.raises(PlanarProjectedMaterialLoadError, match="hinge_rate"):
            map_projected_material_loads(
                cell,
                hinge_radius_m=0.05,
                theta_rad=0.2,
                blade_count=2,
                hinge_rate_rad_s=rate,
                projected_tip_radius_m=0.2,
                operating_condition_id="invalid-rate",
            )
    with pytest.raises(PlanarProjectedMaterialLoadError, match="blade_count"):
        map_projected_material_loads(
            cell,
            hinge_radius_m=0.05,
            theta_rad=0.2,
            blade_count=0,
            hinge_rate_rad_s=1.0e6,
            projected_tip_radius_m=0.2,
            operating_condition_id="invalid-count",
        )
    with pytest.raises(PlanarProjectedMaterialLoadError, match="positive"):
        map_projected_annulus(
            cell[0],
            hinge_radius_m=0.0,
            theta_rad=0.2,
            blade_count=2,
        )
    with pytest.raises(PlanarProjectedMaterialLoadError, match="positive"):
        map_projected_annulus(
            _annulus(0.0, 0.2, torque=1.0),
            hinge_radius_m=0.05,
            theta_rad=0.2,
            blade_count=2,
        )


def _split_count(mapped) -> int:
    counts: dict[int, int] = {}
    for interval in mapped.intervals:
        counts[interval.source_index] = counts.get(interval.source_index, 0) + 1
    return sum(1 for count in counts.values() if count > 1)


def test_mapped_shaft_matches_existing_bem_torque():
    foldable = solve_foldable_bem_rotor(
        _blade(),
        _state(0.0),
        _condition(),
        _schedule(),
        settings=_settings(12),
    )
    before = foldable.rotor_result.as_mapping()
    mapped = map_foldable_bem_aero_loads(foldable, hinge_rate_rad_s=0.0)
    torque = foldable.rotor_result.torque_nm
    residual = mapped.whole_rotor_aerodynamic_shaft_generalized_load_nm + torque
    tolerance = _roundoff_tolerance(
        torque,
        mapped.whole_rotor_aerodynamic_shaft_generalized_load_nm,
        splits=_split_count(mapped),
    )

    assert foldable.rotor_result.as_mapping() == before
    assert residual == 0.0
    assert abs(residual) <= tolerance
    assert mapped.resisting_shaft_torque_nm == pytest.approx(
        torque, rel=0.0, abs=tolerance
    )
    assert mapped.resisting_shaft_torque_nm == (
        -mapped.whole_rotor_aerodynamic_shaft_generalized_load_nm
    )


def test_deployed_foldable_matches_fixed_bem_shaft():
    blade = _blade()
    schedule = _schedule()
    condition = _condition()
    settings = _settings(12)
    state = _state(0.0)
    fixed = solve_bem_rotor(blade, condition, schedule, settings=settings)
    foldable = solve_foldable_bem_rotor(
        blade, state, condition, schedule, settings=settings
    )
    before = foldable.rotor_result.as_mapping()
    mapped = map_foldable_bem_aero_loads(foldable, hinge_rate_rad_s=0.0)

    assert foldable.rotor_result.as_mapping() == fixed.as_mapping() == before
    assert mapped.projection_factor == 1.0
    tolerance = _roundoff_tolerance(
        fixed.torque_nm,
        mapped.resisting_shaft_torque_nm,
        splits=_split_count(mapped),
    )
    assert mapped.resisting_shaft_torque_nm == pytest.approx(
        fixed.torque_nm, rel=0.0, abs=tolerance
    )
    assert fixed.torque_nm > 0.0
    assert mapped.one_tip_hinge_generalized_torque_nm < 0.0
    assert mapped.physical_qualification is False


def test_finite_fold_bem_mapping_is_screening_only():
    theta = math.radians(-30.0)
    foldable = solve_foldable_bem_rotor(
        _blade(),
        _state(theta),
        _condition(),
        _schedule(),
        settings=_settings(8),
    )
    before = foldable.rotor_result.as_mapping()
    repeated = solve_foldable_bem_rotor(
        _blade(),
        _state(theta),
        _condition(),
        _schedule(),
        settings=_settings(8),
    )
    mapped = map_foldable_bem_aero_loads(foldable, hinge_rate_rad_s=-0.15)
    payload = mapped.as_mapping()

    assert foldable.rotor_result.as_mapping() == before == repeated.rotor_result.as_mapping()
    assert math.isfinite(mapped.one_tip_hinge_generalized_torque_nm)
    assert mapped.qualification == QUALIFICATION
    assert mapped.physical_qualification is False
    assert mapped.load_mapping_model == LOAD_MAPPING_MODEL
    assert mapped.projection_model == PROJECTION_MODEL
    assert mapped.distributed_couple_model == DISTRIBUTED_COUPLE_MODEL
    assert mapped.hinge_rate_aerodynamic_model == HINGE_RATE_AERODYNAMIC_MODEL
    assert mapped.sectional_aerodynamic_couple == SECTIONAL_AERODYNAMIC_COUPLE
    assert mapped.hinge_rate_rad_s == -0.15
    assert payload["sectional_aerodynamic_couple"] == "excluded_in_v1"
    assert "hinge_torque_nm" not in _mapping_keys(payload)
    tolerance = _roundoff_tolerance(
        foldable.rotor_result.torque_nm,
        mapped.resisting_shaft_torque_nm,
        splits=_split_count(mapped),
    )
    fold_residual = (
        mapped.whole_rotor_aerodynamic_shaft_generalized_load_nm
        + foldable.rotor_result.torque_nm
    )
    assert fold_residual == 0.0
    assert abs(fold_residual) <= tolerance


def test_finite_hinge_rate_is_recorded_and_ignored_by_force_law():
    foldable = solve_foldable_bem_rotor(
        _blade(),
        _state(math.radians(-20.0)),
        _condition(),
        _schedule(),
        settings=_settings(8),
    )
    quiet = map_foldable_bem_aero_loads(foldable, hinge_rate_rad_s=0.0)
    moving = map_foldable_bem_aero_loads(foldable, hinge_rate_rad_s=2.5)

    assert moving.hinge_rate_rad_s == 2.5
    assert quiet.one_tip_hinge_generalized_torque_nm == (
        moving.one_tip_hinge_generalized_torque_nm
    )
    assert quiet.whole_rotor_aerodynamic_shaft_generalized_load_nm == (
        moving.whole_rotor_aerodynamic_shaft_generalized_load_nm
    )
    assert moving.aerodynamic_generalized_power_w(500.0) != (
        quiet.aerodynamic_generalized_power_w(500.0)
    )


def test_sectional_cm_is_excluded():
    theta = math.radians(-25.0)
    settings = _settings(8)
    state = _state(theta)
    blade = _blade()
    condition = _condition()
    zero_cm = solve_foldable_bem_rotor(
        blade, state, condition, _schedule(0.0), settings=settings
    )
    nonzero_cm = solve_foldable_bem_rotor(
        blade, state, condition, _schedule(0.35), settings=settings
    )
    mapped_zero = map_foldable_bem_aero_loads(zero_cm, hinge_rate_rad_s=0.4)
    mapped_nonzero = map_foldable_bem_aero_loads(nonzero_cm, hinge_rate_rad_s=0.4)

    assert zero_cm.rotor_result.torque_nm == nonzero_cm.rotor_result.torque_nm
    assert mapped_zero.one_tip_hinge_generalized_torque_nm == (
        mapped_nonzero.one_tip_hinge_generalized_torque_nm
    )
    assert mapped_zero.sectional_aerodynamic_couple == "excluded_in_v1"
    assert "cm" not in _mapping_keys(mapped_zero.as_mapping())


def test_mapping_serialization_is_deterministic():
    foldable = solve_foldable_bem_rotor(
        _blade(),
        _state(math.radians(-15.0)),
        _condition(),
        _schedule(),
        settings=_settings(6),
    )
    first = map_foldable_bem_aero_loads(foldable, hinge_rate_rad_s=0.1)
    second = map_foldable_bem_aero_loads(foldable, hinge_rate_rad_s=0.1)
    encoded = json.dumps(first.as_mapping(), allow_nan=False)

    assert first.as_mapping() == second.as_mapping()
    assert encoded == json.dumps(second.as_mapping(), allow_nan=False)
    assert json.loads(encoded)["physical_qualification"] is False
    assert json.loads(encoded)["load_mapping_model"] == LOAD_MAPPING_MODEL


def test_annulus_refinement_is_characterization_only():
    """Characterization of one smooth fixture. Not a physical-accuracy gate."""
    theta = math.radians(-30.0)
    loads = []
    for count in (4, 8, 16):
        foldable = solve_foldable_bem_rotor(
            _blade(),
            _state(theta),
            _condition(),
            _schedule(),
            settings=_settings(count),
        )
        mapped = map_foldable_bem_aero_loads(foldable, hinge_rate_rad_s=0.0)
        loads.append(mapped.one_tip_hinge_generalized_torque_nm)
        assert math.isfinite(loads[-1])
        assert mapped.qualification == QUALIFICATION

    q4, q8, q16 = loads
    assert abs(q16 - q8) < abs(q8 - q4)


def test_small_angle_cylindrical_radius_differs_at_second_order():
    hinge = 0.11
    material = 0.07
    limit = material**2 / (2.0 * (hinge + material))
    projected = projected_radius_m(
        material, hinge_radius_m=hinge, theta_rad=0.0
    )
    cylindrical = math.sqrt(hinge**2 + material**2 + 2.0 * hinge * material)
    assert projected == hinge + material
    assert cylindrical == pytest.approx(projected, rel=0.0, abs=math.ulp(projected))

    for theta in (1.0e-2, 1.0e-3, 1.0e-4):
        projected = hinge + material * math.cos(theta)
        cylindrical = math.sqrt(
            hinge**2 + material**2 + 2.0 * hinge * material * math.cos(theta)
        )
        difference = cylindrical - projected
        assert difference / theta == pytest.approx(0.0, abs=abs(theta) * limit * 2.0)
        assert difference / theta**2 == pytest.approx(limit, rel=1.0e-4, abs=0.0)


def test_inboard_hinge_station_span_fails_closed_and_extension_is_visible():
    blade = BladeGeometry(
        diameter_m=0.30,
        hub_radius_m=0.02,
        blade_count=2,
        stations=(
            BladeStation(0.40, 0.04, 0.30, "foil"),
            BladeStation(0.70, 0.03, 0.20, "foil"),
            BladeStation(1.00, 0.02, 0.10, "foil"),
        ),
    )
    family = {"foil": _family("foil", 0.7)}
    condition = _condition()
    state = _state(0.0, hinge=0.04)
    station_span = solve_foldable_bem_rotor(
        blade,
        state,
        condition,
        family,
        settings=_settings(8, "station_span"),
    )
    with pytest.raises(PlanarProjectedMaterialLoadError, match="coverage"):
        map_foldable_bem_aero_loads(station_span, hinge_rate_rad_s=0.0)

    extended = solve_foldable_bem_rotor(
        blade,
        state,
        condition,
        family,
        settings=_settings(8, "hub_to_tip"),
    )
    mapped = map_foldable_bem_aero_loads(extended, hinge_rate_rad_s=0.0)
    assert extended.rotor_result.geometry_extended is True
    assert mapped.geometry_extended is True
    assert any(interval.geometry_extrapolated for interval in mapped.intervals)


def test_adapter_module_does_not_reference_cmm_or_shaft_axis_radius():
    source = Path(foldable_aero_load.__file__).read_text(encoding="utf-8")
    assert "coupled_transient" not in source
    assert "CMM1_LIMITATIONS" not in source
    assert "sqrt(" not in source
    assert "PolarQueryResult" not in source


def _decimal_hinge_integral(inner: float, outer: float, hinge: float) -> Decimal:
    with localcontext(Context(prec=80)):
        start = Decimal.from_float(inner)
        end = Decimal.from_float(outer)
        radius = Decimal.from_float(hinge)
        return (end - start) - radius * (end / start).ln()


def _matches_decimal_integral(produced: float, reference: Decimal) -> bool:
    if not math.isfinite(produced) or produced <= 0.0:
        return False
    difference = abs(Decimal.from_float(produced) - reference)
    allowance = Decimal.from_float(math.ulp(produced)) * 8
    return difference <= allowance


def test_projected_tip_over_coverage_fails_closed():
    hinge = 0.05
    tip = 0.20
    over = (_annulus(hinge, 0.25, thrust=0.0, torque=2.0),)
    with pytest.raises(
        PlanarProjectedMaterialLoadError,
        match="source domain extends beyond declared projected tip",
    ):
        map_projected_material_loads(
            over,
            hinge_radius_m=hinge,
            theta_rad=0.0,
            blade_count=2,
            hinge_rate_rad_s=0.0,
            projected_tip_radius_m=tip,
            operating_condition_id="over-coverage",
        )

    exact = map_projected_material_loads(
        (_annulus(hinge, tip, thrust=0.0, torque=2.0),),
        hinge_radius_m=hinge,
        theta_rad=0.0,
        blade_count=2,
        hinge_rate_rad_s=0.0,
        projected_tip_radius_m=tip,
        operating_condition_id="exact-tip",
    )
    assert exact.source_outer_projected_radius_m == tip
    assert exact.one_tip_hinge_generalized_torque_nm < 0.0

    with pytest.raises(PlanarProjectedMaterialLoadError, match="coverage"):
        map_projected_material_loads(
            (_annulus(hinge, 0.15, thrust=0.0, torque=2.0),),
            hinge_radius_m=hinge,
            theta_rad=0.0,
            blade_count=2,
            hinge_rate_rad_s=0.0,
            projected_tip_radius_m=tip,
            operating_condition_id="under-coverage",
        )


def test_nextafter_hinge_load_matches_decimal_and_stays_negative():
    hinge = 0.075
    outer = math.nextafter(hinge, math.inf)
    mapped = map_projected_material_loads(
        (_annulus(hinge, outer, thrust=0.0, torque=1.0),),
        hinge_radius_m=hinge,
        theta_rad=0.0,
        blade_count=1,
        hinge_rate_rad_s=0.0,
        projected_tip_radius_m=outer,
        operating_condition_id="nextafter",
    )
    reference = -_decimal_hinge_integral(hinge, outer, hinge)
    produced = mapped.one_tip_hinge_generalized_torque_nm

    assert produced < 0.0
    assert math.isfinite(produced)
    assert _matches_decimal_integral(-produced, -reference)


def test_stable_hinge_integral_matches_independent_decimal_grid():
    hinge = 0.075
    slightly_outboard = math.nextafter(hinge, math.inf)
    cases = (
        (hinge, math.nextafter(hinge, math.inf), hinge),
        (hinge, hinge * (1.0 + 1.0e-12), hinge),
        (slightly_outboard, hinge + 1.0e-6, hinge),
        (0.2, 0.5, 0.1),
        (1.0e-8, 1.0e6, 1.0e-8),
        (1.0e-15, 1.0e300, 1.0e-15),
        (1.0, 1.5, 0.25),
        (2.0, 2.0 * (1.0 + 1.0e-10), 1.0),
    )
    for inner, outer, radius in cases:
        assert outer > inner >= radius > 0.0
        produced = _stable_movable_hinge_integral(inner, outer, radius)
        reference = _decimal_hinge_integral(inner, outer, radius)
        assert _matches_decimal_integral(produced, reference), (
            inner,
            outer,
            radius,
            produced,
            reference,
        )


def test_positive_density_keeps_negative_movable_hinge_load():
    hinge = 0.2
    for outer, density in (
        (math.nextafter(hinge, math.inf), 1.0),
        (hinge * (1.0 + 1.0e-8), 3.0),
        (0.8, 1.0e-4),
        (1.5, 2.0),
    ):
        positive = _map_cell(
            hinge,
            outer,
            thrust=1.0,
            torque=density,
            hinge=hinge,
            theta=0.2,
            blades=2,
        )
        negative = _map_cell(
            hinge,
            outer,
            thrust=1.0,
            torque=-density,
            hinge=hinge,
            theta=0.2,
            blades=2,
        )
        zero = _map_cell(
            hinge,
            outer,
            thrust=1.0,
            torque=0.0,
            hinge=hinge,
            theta=0.2,
            blades=2,
        )
        assert positive[0].one_tip_hinge_generalized_torque_nm < 0.0
        assert negative[0].one_tip_hinge_generalized_torque_nm > 0.0
        assert zero[0].one_tip_hinge_generalized_torque_nm == 0.0


def test_extreme_radius_ratio_stays_finite_and_serializes():
    inner = 1.0e-15
    outer = 1.0e300
    mapped = map_projected_material_loads(
        (_annulus(inner, outer, thrust=0.0, torque=1.0e-300),),
        hinge_radius_m=inner,
        theta_rad=0.0,
        blade_count=1,
        hinge_rate_rad_s=0.0,
        projected_tip_radius_m=outer,
        operating_condition_id="extreme-ratio",
    )
    encoded = json.dumps(mapped.as_mapping(), allow_nan=False)

    assert math.isfinite(mapped.whole_rotor_aerodynamic_shaft_generalized_load_nm)
    assert math.isfinite(mapped.one_tip_hinge_generalized_torque_nm)
    assert mapped.one_tip_hinge_generalized_torque_nm < 0.0
    assert "Infinity" not in encoded
    assert "NaN" not in encoded


def test_nonfinite_evidence_envelope_is_rejected():
    mapped = map_projected_material_loads(
        (_annulus(0.1, 0.2, thrust=1.0, torque=1.0),),
        hinge_radius_m=0.1,
        theta_rad=0.0,
        blade_count=1,
        hinge_rate_rad_s=0.0,
        projected_tip_radius_m=0.2,
        operating_condition_id="envelope",
    )
    with pytest.raises(PlanarProjectedMaterialLoadError):
        replace(mapped, one_tip_hinge_generalized_torque_nm=math.nan)
    with pytest.raises(PlanarProjectedMaterialLoadError):
        replace(mapped, whole_rotor_aerodynamic_shaft_generalized_load_nm=math.inf)
    with pytest.raises(PlanarProjectedMaterialLoadError):
        replace(mapped, projection_factor=math.nan)
    with pytest.raises(PlanarProjectedMaterialLoadError):
        replace(mapped, blade_count=0)
    with pytest.raises(PlanarProjectedMaterialLoadError):
        replace(
            mapped.intervals[0],
            one_tip_hinge_generalized_torque_nm=math.inf,
        )


def test_aggregate_overflow_fails_closed():
    huge = sys.float_info.max
    with pytest.raises(PlanarProjectedMaterialLoadError, match="nonfinite"):
        map_projected_material_loads(
            (
                _annulus(0.5, 1.5, thrust=0.0, torque=huge, index=0),
                _annulus(1.5, 2.5, thrust=0.0, torque=huge, index=1),
            ),
            hinge_radius_m=0.5,
            theta_rad=0.0,
            blade_count=1,
            hinge_rate_rad_s=0.0,
            projected_tip_radius_m=2.5,
            operating_condition_id="aggregate-overflow",
        )


def test_unrepresentable_blade_count_fails_closed():
    with pytest.raises(PlanarProjectedMaterialLoadError, match="nonfinite"):
        map_projected_material_loads(
            (_annulus(0.1, 0.2, thrust=1.0, torque=1.0),),
            hinge_radius_m=0.1,
            theta_rad=0.0,
            blade_count=10**1000,
            hinge_rate_rad_s=0.0,
            projected_tip_radius_m=0.2,
            operating_condition_id="huge-blade-count",
        )


def test_overflowing_power_fails_closed():
    with pytest.raises(PlanarProjectedMaterialLoadError, match="power"):
        aerodynamic_generalized_power_w(
            whole_rotor_shaft_generalized_load_nm=1.0e308,
            one_tip_hinge_generalized_torque_nm=0.0,
            blade_count=1,
            omega_rad_s=-1.0e308,
            hinge_rate_rad_s=0.0,
        )


def _mapping_keys(payload: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            keys.add(key)
            keys.update(_mapping_keys(value))
    elif isinstance(payload, list):
        for value in payload:
            keys.update(_mapping_keys(value))
    return keys
