"""Minimal propulsion exports for PyFoldable operating-point coupling."""

from .models import (  # noqa: F401
    BatterySpec,
    MotorSpec,
    OperatingPoint,
    PropellerSpec,
    SystemSpec,
)
from .solver import PropulsionSolver, SolverConfig  # noqa: F401
