"""Canonical PyFoldable geometry, models, units, and design loading."""

from .airfoil import (
    AirfoilFileFormat,
    AirfoilGeometryError,
    load_airfoil_coordinates,
    parse_airfoil_coordinates,
)

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
from .polar import (
    PolarBoundsPolicy,
    PolarFamily,
    PolarInterpolationError,
    PolarQueryResult,
    load_polar_csv,
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
    "AirfoilFileFormat",
    "AirfoilGeometryError",
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
    "PolarBoundsPolicy",
    "PolarFamily",
    "PolarInterpolationError",
    "PolarQueryResult",
    "PropellerDesign",
    "QuantityInput",
    "SimulationResult",
    "UnitError",
    "ValidationRecord",
    "canonical_unit",
    "load_airfoil_coordinates",
    "load_design_config",
    "load_polar_csv",
    "normalize_quantity",
    "parse_airfoil_coordinates",
    "parse_quantity",
]
