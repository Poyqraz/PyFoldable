"""Explicit, bounded physical-law contracts for the PY-05 mechanism model."""

from __future__ import annotations

import math
from dataclasses import dataclass


def _finite_nonnegative(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite nonnegative scalar.")
    try:
        valid = math.isfinite(value) and value >= 0.0
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite nonnegative scalar.") from exc
    if not valid:
        raise ValueError(f"{name} must be a finite nonnegative scalar.")


@dataclass(frozen=True)
class DryFriction:
    """Optional smooth Coulomb approximation; static friction is not modelled."""

    mode: str = "none"
    coulomb_torque_nm: float = 0.0
    transition_velocity_rad_s: float = 0.0
    source: str = "explicit_frictionless_model"

    def __post_init__(self) -> None:
        if self.mode not in {"none", "regularized_coulomb"}:
            raise ValueError("Dry-friction model must be 'none' or 'regularized_coulomb'.")
        _finite_nonnegative("coulomb_torque_nm", self.coulomb_torque_nm)
        _finite_nonnegative("transition_velocity_rad_s", self.transition_velocity_rad_s)
        if (not isinstance(self.source, str) or not self.source.strip()
                or len(self.source) > 4096):
            raise ValueError("Dry-friction source must be a nonempty string.")
        if self.mode == "none" and (
                self.coulomb_torque_nm != 0.0
                or self.transition_velocity_rad_s != 0.0):
            raise ValueError("The 'none' friction model requires zero torque and transition velocity.")
        if self.mode == "regularized_coulomb" and (
                self.coulomb_torque_nm <= 0.0
                or self.transition_velocity_rad_s <= 0.0):
            raise ValueError("Regularized Coulomb friction requires positive torque and transition velocity.")


@dataclass(frozen=True)
class ContactPolicy:
    """The only qualified contact behavior in PY-05A: stop at first touch."""

    mode: str = "first_contact_terminal"

    def __post_init__(self) -> None:
        if self.mode != "first_contact_terminal":
            raise ValueError("Only the first_contact_terminal contact policy is supported.")
