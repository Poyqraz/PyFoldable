import math

import pytest

from pyfoldable.core import (
    SignedPropulsorError,
    assess_signed_propulsor_state,
    tip_mounted_effective_inflow,
)


def test_tip_mounted_effective_inflow_preserves_vector_components():
    inflow = tip_mounted_effective_inflow(
        forward_speed_m_s=10.0,
        main_angular_speed_rad_s=100.0,
        main_tip_radius_m=0.125,
    )

    assert inflow.forward_component_m_s == 10.0
    assert inflow.tangential_component_m_s == 12.5
    assert inflow.magnitude_m_s == pytest.approx(math.hypot(10.0, 12.5))
    assert inflow.evidence_class == "methodology_only_tip_jointed_system"


@pytest.mark.parametrize(
    ("thrust", "power", "expected_mode"),
    (
        (1.0, 10.0, "propulsive"),
        (-1.0, 10.0, "powered_drag"),
        (-1.0, -10.0, "energy_extracting_drag"),
        (1.0, -10.0, "energy_extracting_thrust"),
        (0.0, 10.0, "near_neutral"),
    ),
)
def test_signed_propulsor_modes_do_not_mislabel_drag_as_efficiency(
    thrust, power, expected_mode
):
    result = assess_signed_propulsor_state(thrust, power, 5.0)

    assert result.mode == expected_mode
    if expected_mode == "propulsive":
        assert result.propulsive_efficiency == pytest.approx(0.5)
    else:
        assert result.propulsive_efficiency is None


def test_static_and_out_of_bounds_propulsive_efficiencies_fail_closed():
    static = assess_signed_propulsor_state(2.0, 10.0, 0.0)
    impossible = assess_signed_propulsor_state(3.0, 10.0, 5.0)

    assert static.mode == "propulsive"
    assert static.propulsive_efficiency is None
    assert "static_efficiency_undefined" in static.warnings
    assert impossible.mode == "propulsive"
    assert impossible.propulsive_efficiency is None
    assert "propulsive_efficiency_out_of_bounds" in impossible.warnings


def test_tip_mounted_inflow_rejects_invalid_geometry_or_velocity():
    with pytest.raises(SignedPropulsorError):
        tip_mounted_effective_inflow(10.0, 100.0, 0.0)
    with pytest.raises(SignedPropulsorError):
        tip_mounted_effective_inflow(-1.0, 100.0, 0.125)


@pytest.mark.parametrize(
    "kwargs",
    (
        {"thrust_n": float("nan"), "power_w": 1.0, "forward_speed_m_s": 1.0},
        {"thrust_n": 1.0, "power_w": 1.0, "forward_speed_m_s": -1.0},
        {
            "thrust_n": 1.0,
            "power_w": 1.0,
            "forward_speed_m_s": 1.0,
            "zero_tolerance": -1.0,
        },
    ),
)
def test_signed_propulsor_inputs_fail_closed(kwargs):
    with pytest.raises(SignedPropulsorError):
        assess_signed_propulsor_state(**kwargs)
