"""Nonlineer (eksponansiyel-yaklaşım) açılma yasası ve mod dağıtımı testleri."""

from dataclasses import replace

import pytest

from pyfoldable.kinematics import (
    theta_deg_from_hinge,
    theta_deg_from_rpm,
    theta_deg_nonlinear_saturation,
)
from pyfoldable.models import (
    BatteryConfig,
    CalibrationConfig,
    FoldableGeometry,
    FoldablePropellerConfig,
    HingeConfig,
    KinematicsConfig,
    MotorConfig,
    SystemConfig,
)


def _base_config(kinematics: KinematicsConfig) -> FoldablePropellerConfig:
    return FoldablePropellerConfig(
        id="TEST",
        description="test",
        geometry=FoldableGeometry(
            diameter_open_m=0.25,
            main_blade_length_m=0.10,
            tip_segment_length_m=0.025,
            hinge_position_m=0.10,
            tip_segment_mass_kg=0.002,
            tip_segment_cg_from_hinge_m=0.0125,
        ),
        hinge=HingeConfig(
            theta_min_deg=-45.0,
            theta_max_deg=0.0,
            rpm_threshold=2000.0,
            rpm_full_open=8000.0,
            hinge_radius_m=0.10,
            hinge_stiffness_nm_per_rad=0.55,
            hinge_friction_nm=0.007,
        ),
        kinematics=kinematics,
        calibration=CalibrationConfig(
            k_thrust=1.0, k_torque=1.0, ct_ref=0.10, model_note="test"
        ),
        reference_propeller_id="APC_10x4.7",
        motor=MotorConfig(980.0, 0.06, 1.2, 30.0),
        battery=BatteryConfig(11.1, 0.98),
        system=SystemConfig(0.015),
    )


@pytest.fixture
def nonlinear_config() -> FoldablePropellerConfig:
    return _base_config(
        KinematicsConfig(
            model="exponential_saturation",
            k_open=1.0,
            kinematics_mode="nonlinear_saturation",
            curve_sharpness=3.0,
        )
    )


def test_below_threshold_fully_folded(nonlinear_config: FoldablePropellerConfig) -> None:
    assert theta_deg_from_rpm(1000.0, nonlinear_config) == -45.0
    assert theta_deg_from_rpm(2000.0, nonlinear_config) == -45.0


def test_at_or_above_full_open_is_max(nonlinear_config: FoldablePropellerConfig) -> None:
    assert theta_deg_from_rpm(8000.0, nonlinear_config) == 0.0
    assert theta_deg_from_rpm(12000.0, nonlinear_config) == 0.0


def test_monotonic_toward_open(nonlinear_config: FoldablePropellerConfig) -> None:
    angles = [
        theta_deg_from_rpm(rpm, nonlinear_config)
        for rpm in [2500.0, 3500.0, 5000.0, 7000.0]
    ]
    assert all(angles[i] < angles[i + 1] for i in range(len(angles) - 1))


def test_zero_sharpness_degrades_to_linear(
    nonlinear_config: FoldablePropellerConfig,
) -> None:
    linear_kin = replace(nonlinear_config.kinematics, curve_sharpness=0.0)
    for rpm in [2500.0, 4000.0, 5000.0, 6500.0]:
        nonlinear = theta_deg_nonlinear_saturation(
            rpm, nonlinear_config.hinge, linear_kin
        )
        # rpm_only linear saturation (k_open=1) referansı ile aynı olmalı
        linear = theta_deg_from_hinge(rpm, nonlinear_config.hinge, linear_kin)
        assert nonlinear == pytest.approx(linear, abs=1e-9)


def test_positive_sharpness_opens_faster_than_linear(
    nonlinear_config: FoldablePropellerConfig,
) -> None:
    linear_kin = replace(nonlinear_config.kinematics, curve_sharpness=0.0)
    for rpm in [2500.0, 3000.0, 4000.0, 5000.0]:
        nonlinear = theta_deg_nonlinear_saturation(
            rpm, nonlinear_config.hinge, nonlinear_config.kinematics
        )
        linear = theta_deg_nonlinear_saturation(rpm, nonlinear_config.hinge, linear_kin)
        # theta_min negatif; daha açık = daha büyük (0'a yakın)
        assert nonlinear > linear


def test_unknown_kinematics_mode_raises() -> None:
    bad = _base_config(
        KinematicsConfig(
            model="linear_saturation", k_open=1.0, kinematics_mode="bogus_mode"
        )
    )
    with pytest.raises(ValueError, match="Unknown kinematics_mode"):
        theta_deg_from_rpm(5000.0, bad)
