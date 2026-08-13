"""Unit-boundary tests for canonical PyFoldable inputs."""

import math

import pytest

from pyfoldable.core import UnitError, normalize_quantity, parse_quantity


@pytest.mark.parametrize(
    ("raw", "dimension", "expected"),
    [
        ("250 mm", "length", 0.25),
        ("10 in", "length", 0.254),
        ("7100 rpm", "angular_speed", 7100.0 * 2.0 * math.pi / 60.0),
        ("90 deg", "angle", math.pi / 2.0),
        ("0.23677 N*m", "torque", 0.23677),
        ("107.215 kPa", "pressure", 107215.0),
        ("15 degC", "temperature", 288.15),
        ({"value": 1.2, "unit": "mm"}, "length", 0.0012),
    ],
)
def test_common_engineering_units_convert_to_si(raw, dimension, expected) -> None:
    assert parse_quantity(raw, dimension) == pytest.approx(expected)


def test_dimensionless_value_may_be_bare() -> None:
    result = normalize_quantity(0.85, "dimensionless", field="target_ratio")
    assert result.si_value == pytest.approx(0.85)
    assert result.input_unit == "1"


def test_dimensional_bare_number_is_rejected() -> None:
    with pytest.raises(UnitError, match="explicit unit"):
        parse_quantity(250, "length", field="blade.diameter")


def test_wrong_dimension_is_rejected() -> None:
    with pytest.raises(UnitError, match="expects dimension"):
        parse_quantity("30 A", "length", field="blade.diameter")


def test_nonfinite_quantity_is_rejected() -> None:
    with pytest.raises(UnitError, match="finite"):
        parse_quantity(float("nan"), "dimensionless")
