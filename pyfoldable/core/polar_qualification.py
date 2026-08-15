"""Provider-result qualification used by orchestration and batch generation."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .providers import (
    PolarGenerationResult,
    PolarProviderError,
)


POLAR_RESULT_QUALIFICATION_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class PolarResultQualificationPolicy:
    """Minimum usable coverage and confidence policy for provider routing."""

    minimum_usable_fraction: float = 1.0
    minimum_usable_points: int = 2
    allow_low_confidence: bool = True

    def __post_init__(self) -> None:
        if (
            isinstance(self.minimum_usable_fraction, bool)
            or not isinstance(self.minimum_usable_fraction, (int, float))
            or not math.isfinite(float(self.minimum_usable_fraction))
            or not 0.0 < self.minimum_usable_fraction <= 1.0
        ):
            raise ValueError("minimum_usable_fraction must be in (0, 1].")
        if (
            isinstance(self.minimum_usable_points, bool)
            or not isinstance(self.minimum_usable_points, int)
            or self.minimum_usable_points < 2
        ):
            raise ValueError("minimum_usable_points must be an integer of at least two.")
        if not isinstance(self.allow_low_confidence, bool):
            raise ValueError("allow_low_confidence must be bool.")

    def evaluate(self, result: PolarGenerationResult) -> "PolarResultQualification":
        """Evaluate one result without mutating provider-health state."""
        if not isinstance(result, PolarGenerationResult):
            raise TypeError("result must be a PolarGenerationResult.")
        accepted_statuses = (
            {"converged", "low_confidence"}
            if self.allow_low_confidence
            else {"converged"}
        )
        accepted_indices = tuple(
            index
            for index, point in enumerate(result.points)
            if point.status in accepted_statuses
        )
        rejected_indices = tuple(
            index for index in range(len(result.points)) if index not in accepted_indices
        )
        usable_fraction = len(accepted_indices) / len(result.points)
        enough_points = len(accepted_indices) >= self.minimum_usable_points
        enough_coverage = usable_fraction >= self.minimum_usable_fraction
        accepted = enough_points and enough_coverage
        reasons: list[str] = []
        if not enough_points:
            reasons.append(
                f"usable points {len(accepted_indices)} < {self.minimum_usable_points}"
            )
        if not enough_coverage:
            reasons.append(
                "usable fraction "
                f"{usable_fraction:.6g} < {self.minimum_usable_fraction:.6g}"
            )
        if not reasons:
            reasons.append("accepted")
        return PolarResultQualification(
            point_count=len(result.points),
            converged_points=sum(
                point.status == "converged" for point in result.points
            ),
            low_confidence_points=sum(
                point.status == "low_confidence" for point in result.points
            ),
            accepted_points=len(accepted_indices),
            usable_fraction=usable_fraction,
            rejected_indices=rejected_indices,
            accepted=accepted,
            reason="; ".join(reasons),
            policy=self,
        )

    def as_mapping(self) -> dict[str, object]:
        return {
            "minimum_usable_fraction": float(self.minimum_usable_fraction),
            "minimum_usable_points": self.minimum_usable_points,
            "allow_low_confidence": self.allow_low_confidence,
        }


@dataclass(frozen=True)
class PolarResultQualification:
    """Immutable point coverage diagnostics for one provider result."""

    point_count: int
    converged_points: int
    low_confidence_points: int
    accepted_points: int
    usable_fraction: float
    rejected_indices: tuple[int, ...]
    accepted: bool
    reason: str
    policy: PolarResultQualificationPolicy

    def __post_init__(self) -> None:
        for name in (
            "point_count",
            "converged_points",
            "low_confidence_points",
            "accepted_points",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer.")
        if self.point_count < 2:
            raise ValueError("point_count must be at least two.")
        if any(
            value > self.point_count
            for value in (
                self.converged_points,
                self.low_confidence_points,
                self.accepted_points,
            )
        ):
            raise ValueError("Qualification point counts cannot exceed point_count.")
        expected_fraction = self.accepted_points / self.point_count
        if not math.isclose(
            self.usable_fraction,
            expected_fraction,
            rel_tol=0.0,
            abs_tol=1.0e-15,
        ):
            raise ValueError("usable_fraction must match accepted_points/point_count.")
        if tuple(sorted(set(self.rejected_indices))) != self.rejected_indices:
            raise ValueError("rejected_indices must be sorted and unique.")
        if any(index < 0 or index >= self.point_count for index in self.rejected_indices):
            raise ValueError("rejected_indices must refer to result points.")
        if len(self.rejected_indices) != self.point_count - self.accepted_points:
            raise ValueError("rejected_indices must cover every unaccepted point.")
        if not isinstance(self.accepted, bool):
            raise ValueError("accepted must be bool.")
        if not isinstance(self.reason, str) or not self.reason:
            raise ValueError("reason must be a non-empty string.")
        if not isinstance(self.policy, PolarResultQualificationPolicy):
            raise TypeError("policy must be a PolarResultQualificationPolicy.")
        expected_accepted = (
            self.accepted_points >= self.policy.minimum_usable_points
            and self.usable_fraction >= self.policy.minimum_usable_fraction
        )
        if self.accepted != expected_accepted:
            raise ValueError("accepted must agree with qualification policy.")

    def as_mapping(self) -> dict[str, object]:
        return {
            "schema_version": POLAR_RESULT_QUALIFICATION_SCHEMA_VERSION,
            "point_count": self.point_count,
            "converged_points": self.converged_points,
            "low_confidence_points": self.low_confidence_points,
            "accepted_points": self.accepted_points,
            "usable_fraction": self.usable_fraction,
            "rejected_indices": self.rejected_indices,
            "accepted": self.accepted,
            "reason": self.reason,
            "policy": self.policy.as_mapping(),
        }


class PolarProviderResultRejectedError(PolarProviderError):
    """Routing-neutral rejection of a valid but insufficient provider result."""

    def __init__(
        self,
        result: PolarGenerationResult,
        qualification: PolarResultQualification,
    ) -> None:
        if not isinstance(result, PolarGenerationResult):
            raise TypeError("result must be a PolarGenerationResult.")
        if not isinstance(qualification, PolarResultQualification):
            raise TypeError("qualification must be a PolarResultQualification.")
        if qualification.accepted:
            raise ValueError("An accepted result cannot be rejected.")
        if qualification.point_count != len(result.points):
            raise ValueError("qualification must describe the rejected result.")
        self.result = result
        self.qualification = qualification
        super().__init__(
            f"Provider result rejected: {qualification.reason}; "
            f"rejected point indices={qualification.rejected_indices}."
        )
