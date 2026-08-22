import math

import pytest

from pyfoldable.core import (
    RotationalAugmentationDomainError,
    RotationalAugmentationModel,
)


def test_snel_1993_matches_published_lift_formula_golden_point():
    model = RotationalAugmentationModel.snel_1993(
        lift_curve_slope_per_rad=2.0 * math.pi,
        zero_lift_angle_rad=0.0,
    )
    result = model.apply(
        alpha_rad=1.0 / math.pi,
        cl_2d=1.0,
        cd_2d=0.02,
        chord_over_radius=0.2,
    )

    assert result.potential_cl == pytest.approx(2.0)
    assert result.augmentation_factor == pytest.approx(3.1 * 0.2**2)
    assert result.cl == pytest.approx(1.0 + 3.1 * 0.2**2)
    assert result.cd == 0.02
    assert result.applied


def test_disabled_model_is_an_exact_no_op_with_explicit_provenance():
    result = RotationalAugmentationModel.disabled().apply(
        alpha_rad=-2.0,
        cl_2d=-0.7,
        cd_2d=0.03,
        chord_over_radius=0.9,
    )

    assert result.cl == -0.7
    assert result.cd == 0.03
    assert result.potential_cl is None
    assert result.augmentation_factor == 0.0
    assert not result.applied
    assert result.as_mapping()["model_id"] == "disabled"


def test_snel_correction_tends_to_2d_value_as_chord_over_radius_tends_to_zero():
    model = RotationalAugmentationModel.snel_1993(
        lift_curve_slope_per_rad=2.0 * math.pi,
        zero_lift_angle_rad=-0.1,
    )
    coarse = model.apply(0.2, 0.5, 0.02, chord_over_radius=0.2)
    fine = model.apply(0.2, 0.5, 0.02, chord_over_radius=1.0e-8)

    assert abs(fine.cl - 0.5) < abs(coarse.cl - 0.5)
    assert fine.cl == pytest.approx(0.5, abs=1.0e-14)


def test_snel_rejects_unreviewed_geometry_or_alpha_domain_instead_of_clamping():
    model = RotationalAugmentationModel.snel_1993(
        lift_curve_slope_per_rad=2.0 * math.pi,
        zero_lift_angle_rad=0.0,
        maximum_chord_over_radius=0.5,
        maximum_absolute_alpha_rad=math.radians(45.0),
    )

    with pytest.raises(RotationalAugmentationDomainError, match="chord_over_radius"):
        model.apply(0.1, 0.5, 0.02, chord_over_radius=0.6)
    with pytest.raises(RotationalAugmentationDomainError, match="alpha_rad"):
        model.apply(math.radians(50.0), 0.5, 0.02, chord_over_radius=0.2)


def test_snel_result_stays_between_2d_and_potential_lift_in_supported_domain():
    model = RotationalAugmentationModel.snel_1993(
        lift_curve_slope_per_rad=2.0 * math.pi,
        zero_lift_angle_rad=-0.05,
    )
    result = model.apply(0.2, 0.4, 0.02, chord_over_radius=0.3)

    assert result.cl >= min(result.cl_2d, result.potential_cl)
    assert result.cl <= max(result.cl_2d, result.potential_cl)
    assert result.cd >= 0.0
