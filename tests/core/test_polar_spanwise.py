import math

import pytest

from pyfoldable.core import (
    PolarFamily,
    PolarInterpolationError,
    PolarTable,
    SpanwisePolarAnchor,
    SpanwisePolarSchedule,
)


def _family(airfoil_id: str, cl: float) -> PolarFamily:
    return PolarFamily(
        (
            PolarTable(
                airfoil_id=airfoil_id,
                scenario_id="span-test",
                reynolds=1.0e5,
                mach=0.0,
                alpha_rad=(-math.pi / 2.0, math.pi / 2.0),
                cl=(cl, cl),
                cd=(0.02, 0.02),
                cm=(0.0, 0.0),
                source=f"source-{airfoil_id}",
            ),
        )
    )


def test_spanwise_schedule_blends_coefficients_and_provenance():
    root = _family("root", 0.2)
    tip = _family("tip", 0.8)
    schedule = SpanwisePolarSchedule(
        "root-to-tip",
        (SpanwisePolarAnchor(0.2, root), SpanwisePolarAnchor(0.8, tip)),
    )

    result = schedule.section(0.5).query(
        alpha_rad=0.0, reynolds=1.0e5, mach=0.0
    )

    assert result.cl == pytest.approx(0.5)
    assert result.airfoil_id == "blend(root,tip;w=0.50000000)"
    assert result.sources == ("source-root", "source-tip")
    assert "span" in result.interpolated_dimensions


def test_spanwise_schedule_endpoints_are_exact_and_bounds_fail_closed():
    root = _family("root", 0.2)
    tip = _family("tip", 0.8)
    schedule = SpanwisePolarSchedule(
        "root-to-tip",
        (SpanwisePolarAnchor(0.2, root), SpanwisePolarAnchor(0.8, tip)),
    )

    assert schedule.section(0.2).airfoil_id == "root"
    assert schedule.section(0.8).airfoil_id == "tip"
    with pytest.raises(PolarInterpolationError, match="outside"):
        schedule.section(0.1)
    clamped = schedule.section(0.1, bounds="clamp").query(
        alpha_rad=0.0, reynolds=1.0e5, mach=0.0
    )
    assert clamped.cl == pytest.approx(0.2)
    assert "span" in clamped.clamped_dimensions


def test_spanwise_schedule_requires_immutable_typed_increasing_anchors():
    root = _family("root", 0.2)
    tip = _family("tip", 0.8)

    with pytest.raises(TypeError, match="tuple"):
        SpanwisePolarSchedule(  # type: ignore[arg-type]
            "mutable",
            [SpanwisePolarAnchor(0.2, root), SpanwisePolarAnchor(0.8, tip)],
        )
    with pytest.raises(ValueError, match="strictly increasing"):
        SpanwisePolarSchedule(
            "reversed",
            (SpanwisePolarAnchor(0.8, tip), SpanwisePolarAnchor(0.2, root)),
        )
