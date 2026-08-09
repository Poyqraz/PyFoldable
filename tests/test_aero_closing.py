"""Aero kapanma momenti (opt-in) ve geriye dönük uyumluluk testleri."""

from dataclasses import replace

import pytest

from pyfoldable.aero_closing import closing_moment_nm
from pyfoldable.dynamics.hinge_moments import compute_hinge_moments
from pyfoldable.kinematics import theta_deg_from_rpm
from pyfoldable.models import (
    AeroClosingConfig,
    BatteryConfig,
    CalibrationConfig,
    FoldableGeometry,
    FoldablePropellerConfig,
    HingeConfig,
    KinematicsConfig,
    MotorConfig,
    SystemConfig,
    load_config,
)


def _config(
    *,
    kinematics_mode: str = "moment_based",
    aero_closing: AeroClosingConfig = AeroClosingConfig(),
) -> FoldablePropellerConfig:
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
            stow_model="parallel_fold",
        ),
        hinge=HingeConfig(
            theta_min_deg=-180.0,
            theta_max_deg=0.0,
            rpm_threshold=2000.0,
            rpm_full_open=8000.0,
            hinge_radius_m=0.10,
            hinge_stiffness_nm_per_rad=0.55,
            hinge_friction_nm=0.007,
            hinge_inertia_kgm2=5.0e-6,
        ),
        kinematics=KinematicsConfig(
            model="linear_saturation", k_open=1.0, kinematics_mode=kinematics_mode
        ),
        calibration=CalibrationConfig(
            k_thrust=1.0, k_torque=1.0, ct_ref=0.10, model_note="test"
        ),
        reference_propeller_id="APC_10x4.7",
        motor=MotorConfig(980.0, 0.06, 1.2, 30.0),
        battery=BatteryConfig(11.1, 0.98),
        system=SystemConfig(0.015),
        aero_closing=aero_closing,
    )


ON = AeroClosingConfig(close_moment_gain=80.0, axial_velocity_m_s=12.0)


def test_closing_zero_when_disabled_by_default() -> None:
    config = _config()
    assert closing_moment_nm(6000.0, -160.0, config, theta_dependent=True) == 0.0


def test_closing_zero_when_no_axial_velocity() -> None:
    config = _config(aero_closing=AeroClosingConfig(close_moment_gain=80.0, axial_velocity_m_s=0.0))
    assert closing_moment_nm(6000.0, 0.0, config) == 0.0


def test_closing_zero_at_zero_rpm() -> None:
    config = _config(aero_closing=ON)
    assert closing_moment_nm(0.0, 0.0, config) == 0.0


def test_closing_positive_when_enabled() -> None:
    config = _config(aero_closing=ON)
    assert closing_moment_nm(6000.0, 0.0, config) > 0.0


def test_closing_scales_with_axial_velocity_squared() -> None:
    slow = _config(aero_closing=AeroClosingConfig(close_moment_gain=80.0, axial_velocity_m_s=6.0))
    fast = _config(aero_closing=AeroClosingConfig(close_moment_gain=80.0, axial_velocity_m_s=12.0))
    m_slow = closing_moment_nm(6000.0, 0.0, slow)
    m_fast = closing_moment_nm(6000.0, 0.0, fast)
    # q ~ V^2 => 2x hız -> 4x moment
    assert m_fast == pytest.approx(4.0 * m_slow, rel=1e-9)


def test_theta_dependent_extension_reduces_moment_when_folded() -> None:
    config = _config(aero_closing=ON)
    open_moment = closing_moment_nm(6000.0, 0.0, config, theta_dependent=True)
    folded_moment = closing_moment_nm(6000.0, -170.0, config, theta_dependent=True)
    assert folded_moment < open_moment


def test_closing_reduces_moment_based_deployment() -> None:
    off = _config(aero_closing=AeroClosingConfig())
    on = _config(aero_closing=ON)
    rpm = 6000.0
    theta_off = theta_deg_from_rpm(rpm, off)
    theta_on = theta_deg_from_rpm(rpm, on)
    # Kapanma momenti açılmayı azaltır => daha negatif (kısmi açılma)
    assert theta_on < theta_off


def test_v2_hinge_component_reduces_net_moment() -> None:
    off = _config(aero_closing=AeroClosingConfig())
    on = _config(aero_closing=ON)
    kwargs = dict(rpm=6000.0, theta_deg=-90.0, theta_dot_rad_s=0.0, tip_thrust_n=1.0)
    m_off = compute_hinge_moments(config=off, **kwargs)
    m_on = compute_hinge_moments(config=on, **kwargs)
    assert m_off.M_closing_nm == 0.0
    assert m_on.M_closing_nm > 0.0
    assert m_on.M_net_nm < m_off.M_net_nm


@pytest.mark.parametrize("config_name", ["TIP_HINGED_250_V01", "TIP_HINGED_250_V02"])
def test_existing_configs_have_closing_disabled(config_name: str) -> None:
    config = load_config(f"configs/foldable/{config_name}.json")
    assert config.aero_closing.close_moment_gain == 0.0
    assert config.aero_closing.axial_velocity_m_s == 0.0
    assert closing_moment_nm(6000.0, theta_deg_from_rpm(6000.0, config), config) == 0.0


def test_v03_config_enables_features() -> None:
    config = load_config("configs/foldable/TIP_HINGED_250_V03.json")
    assert config.kinematics.kinematics_mode == "nonlinear_saturation"
    assert config.kinematics.curve_sharpness > 0.0
    assert config.aero_closing.close_moment_gain > 0.0
    assert config.aero_closing.axial_velocity_m_s > 0.0
