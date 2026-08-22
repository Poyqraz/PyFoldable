"""Explicit radial scheduling and coefficient blending for polar families."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .polar import (
    PolarBoundsPolicy,
    PolarFamily,
    PolarInterpolationError,
    PolarQueryResult,
)


@dataclass(frozen=True)
class SpanwisePolarAnchor:
    """One airfoil polar family anchored at a nondimensional blade radius."""

    r_over_R: float
    family: PolarFamily

    def __post_init__(self) -> None:
        if not math.isfinite(self.r_over_R) or not 0.0 < self.r_over_R <= 1.0:
            raise ValueError("r_over_R must be finite and in (0, 1].")
        if not isinstance(self.family, PolarFamily):
            raise TypeError("family must be a PolarFamily.")


@dataclass(frozen=True)
class SpanwisePolarSection:
    """A local polar query that preserves both radial endpoint families."""

    lower: PolarFamily
    upper: PolarFamily
    weight: float
    span_clamped: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.lower, PolarFamily) or not isinstance(
            self.upper, PolarFamily
        ):
            raise TypeError("Spanwise polar endpoints must be PolarFamily instances.")
        if not math.isfinite(self.weight) or not 0.0 <= self.weight <= 1.0:
            raise ValueError("weight must be finite and in [0, 1].")
        if not isinstance(self.span_clamped, bool):
            raise TypeError("span_clamped must be boolean.")

    @property
    def airfoil_id(self) -> str:
        if self.weight <= 0.0 or self.lower.airfoil_id == self.upper.airfoil_id:
            return self.lower.airfoil_id
        if self.weight >= 1.0:
            return self.upper.airfoil_id
        return (
            f"blend({self.lower.airfoil_id},{self.upper.airfoil_id};"
            f"w={self.weight:.8f})"
        )

    @property
    def scenario_id(self) -> str:
        if self.lower.scenario_id == self.upper.scenario_id:
            return self.lower.scenario_id
        return f"blend({self.lower.scenario_id},{self.upper.scenario_id})"

    def query(
        self,
        *,
        alpha_rad: float,
        reynolds: float,
        mach: float,
        bounds: PolarBoundsPolicy = "error",
    ) -> PolarQueryResult:
        """Query both endpoints and blend only their aerodynamic coefficients."""
        if self.weight <= 0.0 or self.lower == self.upper:
            result = self.lower.query(
                alpha_rad=alpha_rad, reynolds=reynolds, mach=mach, bounds=bounds
            )
            if not self.span_clamped:
                return result
            return PolarQueryResult(
                airfoil_id=result.airfoil_id,
                scenario_id=result.scenario_id,
                alpha_rad=result.alpha_rad,
                reynolds=result.reynolds,
                mach=result.mach,
                cl=result.cl,
                cd=result.cd,
                cm=result.cm,
                sources=result.sources,
                interpolated_dimensions=result.interpolated_dimensions,
                clamped_dimensions=tuple(
                    sorted({*result.clamped_dimensions, "span"})
                ),
            )
        if self.weight >= 1.0:
            return self.upper.query(
                alpha_rad=alpha_rad, reynolds=reynolds, mach=mach, bounds=bounds
            )
        lower = self.lower.query(
            alpha_rad=alpha_rad, reynolds=reynolds, mach=mach, bounds=bounds
        )
        upper = self.upper.query(
            alpha_rad=alpha_rad, reynolds=reynolds, mach=mach, bounds=bounds
        )
        inverse = 1.0 - self.weight
        interpolated = set(lower.interpolated_dimensions)
        interpolated.update(upper.interpolated_dimensions)
        if self.lower.airfoil_id != self.upper.airfoil_id:
            interpolated.add("span")
        clamped = set(lower.clamped_dimensions)
        clamped.update(upper.clamped_dimensions)
        if self.span_clamped:
            clamped.add("span")
        return PolarQueryResult(
            airfoil_id=self.airfoil_id,
            scenario_id=self.scenario_id,
            alpha_rad=alpha_rad,
            reynolds=reynolds,
            mach=mach,
            cl=lower.cl * inverse + upper.cl * self.weight,
            cd=lower.cd * inverse + upper.cd * self.weight,
            cm=lower.cm * inverse + upper.cm * self.weight,
            sources=tuple(dict.fromkeys((*lower.sources, *upper.sources))),
            interpolated_dimensions=tuple(sorted(interpolated)),
            clamped_dimensions=tuple(sorted(clamped)),
        )


@dataclass(frozen=True)
class SpanwisePolarSchedule:
    """A fail-closed radial polar schedule with explicit coefficient blending."""

    id: str
    anchors: tuple[SpanwisePolarAnchor, ...]

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("SpanwisePolarSchedule.id must not be empty.")
        if not isinstance(self.anchors, tuple) or not all(
            isinstance(anchor, SpanwisePolarAnchor) for anchor in self.anchors
        ):
            raise TypeError("anchors must be a tuple of SpanwisePolarAnchor values.")
        if len(self.anchors) < 2:
            raise ValueError("SpanwisePolarSchedule requires at least two anchors.")
        radii = tuple(anchor.r_over_R for anchor in self.anchors)
        if any(upper <= lower for lower, upper in zip(radii, radii[1:])):
            raise ValueError("Spanwise polar anchors must be strictly increasing.")

    @property
    def airfoil_ids(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(anchor.family.airfoil_id for anchor in self.anchors))

    @property
    def scenario_ids(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(anchor.family.scenario_id for anchor in self.anchors))

    def section(
        self, r_over_R: float, *, bounds: PolarBoundsPolicy = "error"
    ) -> SpanwisePolarSection:
        """Return the two endpoint families and radial blend for one annulus."""
        if bounds not in {"error", "clamp"}:
            raise PolarInterpolationError(f"Unsupported bounds policy {bounds!r}.")
        if not math.isfinite(r_over_R):
            raise PolarInterpolationError("r_over_R must be finite.")
        first, last = self.anchors[0], self.anchors[-1]
        if r_over_R < first.r_over_R or r_over_R > last.r_over_R:
            if bounds == "error":
                raise PolarInterpolationError(
                    f"Requested span {r_over_R:g} is outside "
                    f"[{first.r_over_R:g}, {last.r_over_R:g}]."
                )
            anchor = first if r_over_R < first.r_over_R else last
            return SpanwisePolarSection(
                anchor.family, anchor.family, 0.0, span_clamped=True
            )
        for lower, upper in zip(self.anchors, self.anchors[1:]):
            if r_over_R <= upper.r_over_R:
                weight = (r_over_R - lower.r_over_R) / (
                    upper.r_over_R - lower.r_over_R
                )
                return SpanwisePolarSection(lower.family, upper.family, weight)
        return SpanwisePolarSection(last.family, last.family, 0.0)
