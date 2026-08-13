"""Canonical PyFoldable models, units, and versioned design loading."""

from .config import DesignConfigError, load_design_config
from .models import (
    AirfoilDefinition,
    BladeGeometry,
    BladeStation,
    HingeGeometry,
    ManufacturingModel,
    MaterialModel,
    MotorModel,
    OperatingCondition,
    PolarTable,
    PropellerDesign,
    SimulationResult,
    ValidationRecord,
)
from .units import (
    NormalizedQuantity,
    QuantityInput,
    UnitError,
    canonical_unit,
    normalize_quantity,
    parse_quantity,
)

__all__ = [
    "AirfoilDefinition",
    "BladeGeometry",
    "BladeStation",
    "DesignConfigError",
    "HingeGeometry",
    "ManufacturingModel",
    "MaterialModel",
    "MotorModel",
    "NormalizedQuantity",
    "OperatingCondition",
    "PolarTable",
    "PropellerDesign",
    "QuantityInput",
    "SimulationResult",
    "UnitError",
    "ValidationRecord",
    "canonical_unit",
    "load_design_config",
    "normalize_quantity",
    "parse_quantity",
]
