"""Auditable, opt-in rotational lift augmentation models.

The first supported model is the Snel et al. sectional lift correction.  It is
kept separate from polar generation so a rotor benchmark can report 2-D and
3-D-model ablations without changing or relabeling the source polar tables.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal, Mapping


RotationalAugmentationKind = Literal["disabled", "snel_1993"]
SNEL_1993_SOURCE = (
    "https://publicaties.ecn.nl/PdfFetch.aspx?nr=ECN-C--93-052"
)


class RotationalAugmentationDomainError(ValueError):
    """Raised when a correction is requested outside its reviewed domain."""


def _finite(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number.")
    if not math.isfinite(float(value)):
        raise ValueError(f"{name} must be finite.")


@dataclass(frozen=True)
class RotationalAugmentationResult:
    """Corrected coefficients and the complete local model audit trail."""

    model_id: str
    applied: bool
    alpha_rad: float
    chord_over_radius: float
    cl_2d: float
    cd_2d: float
    potential_cl: float | None
    augmentation_factor: float
    cl: float
    cd: float
    source: str | None

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "model_id": self.model_id,
            "applied": self.applied,
            "alpha_rad": self.alpha_rad,
            "chord_over_radius": self.chord_over_radius,
            "cl_2d": self.cl_2d,
            "cd_2d": self.cd_2d,
            "potential_cl": self.potential_cl,
            "augmentation_factor": self.augmentation_factor,
            "cl": self.cl,
            "cd": self.cd,
            "source": self.source,
        }


@dataclass(frozen=True)
class RotationalAugmentationModel:
    """Versioned Snel lift correction with fail-closed applicability limits."""

    kind: RotationalAugmentationKind = "disabled"
    lift_curve_slope_per_rad: float | None = None
    zero_lift_angle_rad: float | None = None
    maximum_chord_over_radius: float = 0.75
    maximum_absolute_alpha_rad: float = math.radians(45.0)

    def __post_init__(self) -> None:
        if self.kind not in {"disabled", "snel_1993"}:
            raise ValueError("Unsupported rotational augmentation model.")
        _finite("maximum_chord_over_radius", self.maximum_chord_over_radius)
        _finite("maximum_absolute_alpha_rad", self.maximum_absolute_alpha_rad)
        if not 0.0 < self.maximum_chord_over_radius <= 1.0:
            raise ValueError("maximum_chord_over_radius must be in (0, 1].")
        if not 0.0 < self.maximum_absolute_alpha_rad <= math.pi:
            raise ValueError("maximum_absolute_alpha_rad must be in (0, pi].")
        if self.kind == "disabled":
            if (
                self.lift_curve_slope_per_rad is not None
                or self.zero_lift_angle_rad is not None
            ):
                raise ValueError(
                    "Disabled augmentation cannot carry lift-fit parameters."
                )
            return
        if self.lift_curve_slope_per_rad is None or self.zero_lift_angle_rad is None:
            raise ValueError(
                "Snel augmentation requires lift_curve_slope_per_rad and "
                "zero_lift_angle_rad."
            )
        _finite("lift_curve_slope_per_rad", self.lift_curve_slope_per_rad)
        _finite("zero_lift_angle_rad", self.zero_lift_angle_rad)
        if self.lift_curve_slope_per_rad <= 0.0:
            raise ValueError("lift_curve_slope_per_rad must be greater than zero.")
        if abs(self.zero_lift_angle_rad) > math.pi:
            raise ValueError("zero_lift_angle_rad must be in [-pi, pi].")

    @classmethod
    def disabled(cls) -> "RotationalAugmentationModel":
        return cls()

    @classmethod
    def snel_1993(
        cls,
        *,
        lift_curve_slope_per_rad: float,
        zero_lift_angle_rad: float,
        maximum_chord_over_radius: float = 0.75,
        maximum_absolute_alpha_rad: float = math.radians(45.0),
    ) -> "RotationalAugmentationModel":
        return cls(
            kind="snel_1993",
            lift_curve_slope_per_rad=lift_curve_slope_per_rad,
            zero_lift_angle_rad=zero_lift_angle_rad,
            maximum_chord_over_radius=maximum_chord_over_radius,
            maximum_absolute_alpha_rad=maximum_absolute_alpha_rad,
        )

    @property
    def model_id(self) -> str:
        return "disabled" if self.kind == "disabled" else "snel-1993-v1"

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "model_id": self.model_id,
            "kind": self.kind,
            "lift_curve_slope_per_rad": self.lift_curve_slope_per_rad,
            "zero_lift_angle_rad": self.zero_lift_angle_rad,
            "maximum_chord_over_radius": self.maximum_chord_over_radius,
            "maximum_absolute_alpha_rad": self.maximum_absolute_alpha_rad,
            "source": None if self.kind == "disabled" else SNEL_1993_SOURCE,
        }

    def apply(
        self,
        alpha_rad: float,
        cl_2d: float,
        cd_2d: float,
        *,
        chord_over_radius: float,
    ) -> RotationalAugmentationResult:
        for name, value in (
            ("alpha_rad", alpha_rad),
            ("cl_2d", cl_2d),
            ("cd_2d", cd_2d),
            ("chord_over_radius", chord_over_radius),
        ):
            _finite(name, value)
        if cd_2d < 0.0:
            raise ValueError("cd_2d must be non-negative.")
        if chord_over_radius <= 0.0:
            raise ValueError("chord_over_radius must be greater than zero.")
        if self.kind == "disabled":
            return RotationalAugmentationResult(
                self.model_id,
                False,
                float(alpha_rad),
                float(chord_over_radius),
                float(cl_2d),
                float(cd_2d),
                None,
                0.0,
                float(cl_2d),
                float(cd_2d),
                None,
            )
        if chord_over_radius > self.maximum_chord_over_radius:
            raise RotationalAugmentationDomainError(
                "chord_over_radius exceeds the reviewed Snel model domain."
            )
        if abs(alpha_rad) > self.maximum_absolute_alpha_rad:
            raise RotationalAugmentationDomainError(
                "alpha_rad exceeds the reviewed Snel model domain."
            )
        assert self.lift_curve_slope_per_rad is not None
        assert self.zero_lift_angle_rad is not None
        potential_cl = self.lift_curve_slope_per_rad * (
            alpha_rad - self.zero_lift_angle_rad
        )
        factor = 3.1 * chord_over_radius**2
        corrected_cl = cl_2d + factor * (potential_cl - cl_2d)
        return RotationalAugmentationResult(
            self.model_id,
            True,
            float(alpha_rad),
            float(chord_over_radius),
            float(cl_2d),
            float(cd_2d),
            potential_cl,
            factor,
            corrected_cl,
            float(cd_2d),
            SNEL_1993_SOURCE,
        )
