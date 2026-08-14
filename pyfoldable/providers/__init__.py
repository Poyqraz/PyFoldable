"""Optional aerodynamic data providers."""

from .neuralfoil import NeuralFoilProvider
from .xfoil import XfoilProvider

__all__ = ["NeuralFoilProvider", "XfoilProvider"]
