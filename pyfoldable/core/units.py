"""Strict unit normalization at PyFoldable input boundaries.

The physics core stores SI scalars.  User-facing configuration may use common
engineering units, but conversion must happen before a model object is built.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from numbers import Real
from typing import Mapping, TypeAlias


class UnitError(ValueError):
    """Raised when a quantity is missing, malformed, or dimensionally invalid."""


QuantityInput: TypeAlias = str | Real | Mapping[str, object]


@dataclass(frozen=True)
class UnitDefinition:
    dimension: str
    factor_to_si: float
    offset_to_si: float = 0.0


@dataclass(frozen=True)
class NormalizedQuantity:
    """A parsed quantity and the provenance needed for an audit trail."""

    si_value: float
    dimension: str
    input_unit: str
    canonical_unit: str


_CANONICAL_UNITS: dict[str, str] = {
    "dimensionless": "1",
    "length": "m",
    "area": "m^2",
    "angle": "rad",
    "angular_speed": "rad/s",
    "angular_speed_per_voltage": "rad/s/V",
    "speed": "m/s",
    "mass": "kg",
    "density": "kg/m^3",
    "dynamic_viscosity": "Pa*s",
    "force": "N",
    "torque": "N*m",
    "power": "W",
    "pressure": "Pa",
    "stress": "Pa",
    "time": "s",
    "current": "A",
    "voltage": "V",
    "resistance": "ohm",
    "temperature": "K",
}


def _unit(dimension: str, factor: float, offset: float = 0.0) -> UnitDefinition:
    return UnitDefinition(dimension, factor, offset)


_UNITS: dict[str, UnitDefinition] = {
    "1": _unit("dimensionless", 1.0),
    "%": _unit("dimensionless", 0.01),
    "m": _unit("length", 1.0),
    "mm": _unit("length", 1.0e-3),
    "cm": _unit("length", 1.0e-2),
    "in": _unit("length", 0.0254),
    "inch": _unit("length", 0.0254),
    "m^2": _unit("area", 1.0),
    "mm^2": _unit("area", 1.0e-6),
    "rad": _unit("angle", 1.0),
    "deg": _unit("angle", math.pi / 180.0),
    "degree": _unit("angle", math.pi / 180.0),
    "rad/s": _unit("angular_speed", 1.0),
    "rpm": _unit("angular_speed", 2.0 * math.pi / 60.0),
    "rad/s/v": _unit("angular_speed_per_voltage", 1.0),
    "rpm/v": _unit("angular_speed_per_voltage", 2.0 * math.pi / 60.0),
    "m/s": _unit("speed", 1.0),
    "km/h": _unit("speed", 1.0 / 3.6),
    "kg": _unit("mass", 1.0),
    "g": _unit("mass", 1.0e-3),
    "kg/m^3": _unit("density", 1.0),
    "g/cm^3": _unit("density", 1000.0),
    "pa*s": _unit("dynamic_viscosity", 1.0),
    "n": _unit("force", 1.0),
    "n*m": _unit("torque", 1.0),
    "nm": _unit("torque", 1.0),
    "w": _unit("power", 1.0),
    "kw": _unit("power", 1000.0),
    "pa": _unit("pressure", 1.0),
    "kpa": _unit("pressure", 1000.0),
    "mpa": _unit("pressure", 1.0e6),
    "s": _unit("time", 1.0),
    "ms": _unit("time", 1.0e-3),
    "a": _unit("current", 1.0),
    "ma": _unit("current", 1.0e-3),
    "v": _unit("voltage", 1.0),
    "ohm": _unit("resistance", 1.0),
    "ω": _unit("resistance", 1.0),
    "k": _unit("temperature", 1.0),
    "degc": _unit("temperature", 1.0, 273.15),
    "celsius": _unit("temperature", 1.0, 273.15),
}

_NUMBER_AND_UNIT = re.compile(
    r"^\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)\s*(.*?)\s*$"
)


def canonical_unit(dimension: str) -> str:
    """Return the SI unit label used by the canonical model."""
    try:
        return _CANONICAL_UNITS[dimension]
    except KeyError as exc:
        raise UnitError(f"Unknown physical dimension: {dimension!r}.") from exc


def _normalize_unit_label(unit: str) -> str:
    normalized = unit.strip().replace("·", "*").replace("²", "^2").replace("³", "^3")
    normalized = normalized.replace("°C", "degC").replace("°c", "degC").replace("℃", "degC")
    normalized = re.sub(r"\s+", "", normalized)
    return normalized.casefold()


def normalize_quantity(
    value: QuantityInput,
    dimension: str,
    *,
    field: str = "quantity",
) -> NormalizedQuantity:
    """Parse a unit-bearing value and return its canonical SI representation.

    Physical inputs must carry a unit. Bare numbers are accepted only for
    dimensionless fields, preventing an ambiguous ``250`` from silently being
    interpreted as metres instead of millimetres.
    """
    canonical = canonical_unit(dimension)

    if isinstance(value, bool):
        raise UnitError(f"{field} must be a numeric quantity, not bool.")

    if isinstance(value, Real):
        if dimension != "dimensionless":
            raise UnitError(
                f"{field} requires an explicit unit; received bare value {value!r}."
            )
        numeric = float(value)
        unit_label = "1"
    elif isinstance(value, Mapping):
        if "value" not in value or "unit" not in value:
            raise UnitError(f"{field} mappings require 'value' and 'unit'.")
        raw_numeric = value["value"]
        if isinstance(raw_numeric, bool) or not isinstance(raw_numeric, Real):
            raise UnitError(f"{field}.value must be numeric.")
        numeric = float(raw_numeric)
        unit_label = str(value["unit"])
    elif isinstance(value, str):
        match = _NUMBER_AND_UNIT.match(value)
        if not match:
            raise UnitError(f"{field} is not a valid quantity: {value!r}.")
        numeric = float(match.group(1))
        unit_label = match.group(2) or "1"
    else:
        raise UnitError(f"{field} has unsupported quantity type {type(value).__name__}.")

    if not math.isfinite(numeric):
        raise UnitError(f"{field} must be finite.")

    lookup = _normalize_unit_label(unit_label)
    try:
        definition = _UNITS[lookup]
    except KeyError as exc:
        raise UnitError(f"{field} uses unsupported unit {unit_label!r}.") from exc
    compatible = definition.dimension == dimension or (
        dimension == "stress" and definition.dimension == "pressure"
    )
    if not compatible:
        raise UnitError(
            f"{field} expects dimension {dimension!r}, but unit {unit_label!r} "
            f"has dimension {definition.dimension!r}."
        )

    si_value = numeric * definition.factor_to_si + definition.offset_to_si
    return NormalizedQuantity(si_value, dimension, unit_label.strip() or "1", canonical)


def parse_quantity(value: QuantityInput, dimension: str, *, field: str = "quantity") -> float:
    """Return only the SI scalar for a unit-bearing value."""
    return normalize_quantity(value, dimension, field=field).si_value
