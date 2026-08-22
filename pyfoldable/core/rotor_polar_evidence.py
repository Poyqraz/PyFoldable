"""Fail-closed qualification evidence for spanwise rotor polar consumption."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .bem_rotor import BEMRotorResult
from .polar_spanwise import SpanwisePolarSchedule
from .providers import ProviderIdentity


ROTOR_POLAR_EVIDENCE_SCHEMA_VERSION = 1
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _validate_sha256(name: str, value: str) -> None:
    if not isinstance(value, str) or _SHA256.fullmatch(value.lower()) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 digest.")


@dataclass(frozen=True)
class AirfoilCoordinateIdentity:
    """Pinned identity of one user-local airfoil coordinate document."""

    airfoil_id: str
    source: str
    sha256: str

    def __post_init__(self) -> None:
        if not self.airfoil_id or not self.source:
            raise ValueError("Airfoil coordinate identity fields must not be empty.")
        _validate_sha256("sha256", self.sha256)
        object.__setattr__(self, "sha256", self.sha256.lower())

    def as_mapping(self) -> Mapping[str, str]:
        return {
            "airfoil_id": self.airfoil_id,
            "source": self.source,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class PolarPromotionEvidence:
    """Immutable identity of the reviewed two-capture promotion decision."""

    review_state: str
    promotion_allowed: bool
    first_capture_manifest_sha256: str
    second_capture_manifest_sha256: str
    reproducibility_report_sha256: str
    promotion_record_sha256: str

    def __post_init__(self) -> None:
        if self.review_state not in {"approved", "unreviewed", "rejected"}:
            raise ValueError("Unsupported polar promotion review_state.")
        if not isinstance(self.promotion_allowed, bool):
            raise TypeError("promotion_allowed must be boolean.")
        for name in (
            "first_capture_manifest_sha256",
            "second_capture_manifest_sha256",
            "reproducibility_report_sha256",
            "promotion_record_sha256",
        ):
            _validate_sha256(name, getattr(self, name))

    @property
    def approved(self) -> bool:
        return self.review_state == "approved" and self.promotion_allowed

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "review_state": self.review_state,
            "promotion_allowed": self.promotion_allowed,
            "first_capture_manifest_sha256": self.first_capture_manifest_sha256,
            "second_capture_manifest_sha256": self.second_capture_manifest_sha256,
            "reproducibility_report_sha256": self.reproducibility_report_sha256,
            "promotion_record_sha256": self.promotion_record_sha256,
        }


@dataclass(frozen=True)
class RotorPolarEvidencePolicy:
    """Predeclared identities and minimum provider-confidence requirements."""

    required_airfoil_ids: tuple[str, ...]
    expected_coordinate_identities: tuple[AirfoilCoordinateIdentity, ...]
    allowed_provider_identities: tuple[ProviderIdentity, ...]
    expected_anchor_radii: tuple[float, ...]
    required_operating_condition_ids: tuple[str, ...]
    expected_final_query_count: int
    allowed_promotion_record_sha256: tuple[str, ...]
    minimum_confidence: float = 0.5

    def __post_init__(self) -> None:
        for name, values in (
            ("required_airfoil_ids", self.required_airfoil_ids),
            ("required_operating_condition_ids", self.required_operating_condition_ids),
            (
                "allowed_promotion_record_sha256",
                self.allowed_promotion_record_sha256,
            ),
        ):
            if (
                not isinstance(values, tuple)
                or not values
                or any(not isinstance(value, str) or not value for value in values)
                or len(set(values)) != len(values)
            ):
                raise ValueError(f"{name} must be a non-empty tuple of unique strings.")
        if (
            not isinstance(self.expected_coordinate_identities, tuple)
            or not self.expected_coordinate_identities
            or not all(
                isinstance(value, AirfoilCoordinateIdentity)
                for value in self.expected_coordinate_identities
            )
        ):
            raise TypeError(
                "expected_coordinate_identities must contain coordinate identities."
            )
        if (
            not isinstance(self.expected_anchor_radii, tuple)
            or len(self.expected_anchor_radii) < 2
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or not 0.0 < float(value) <= 1.0
                for value in self.expected_anchor_radii
            )
            or any(
                upper <= lower
                for lower, upper in zip(
                    self.expected_anchor_radii,
                    self.expected_anchor_radii[1:],
                )
            )
        ):
            raise ValueError(
                "expected_anchor_radii must be a strictly increasing radius tuple."
            )
        coordinate_ids = tuple(
            value.airfoil_id for value in self.expected_coordinate_identities
        )
        if coordinate_ids != self.required_airfoil_ids:
            raise ValueError(
                "Coordinate identities must exactly match required_airfoil_ids."
            )
        if (
            not isinstance(self.allowed_provider_identities, tuple)
            or not self.allowed_provider_identities
            or not all(
                isinstance(value, ProviderIdentity)
                for value in self.allowed_provider_identities
            )
            or len(set(self.allowed_provider_identities))
            != len(self.allowed_provider_identities)
        ):
            raise TypeError(
                "allowed_provider_identities must contain unique "
                "ProviderIdentity values."
            )
        if (
            isinstance(self.expected_final_query_count, bool)
            or not isinstance(self.expected_final_query_count, int)
            or self.expected_final_query_count < 1
        ):
            raise ValueError("expected_final_query_count must be a positive integer.")
        for digest in self.allowed_promotion_record_sha256:
            _validate_sha256("allowed_promotion_record_sha256", digest)
        if (
            isinstance(self.minimum_confidence, bool)
            or not isinstance(self.minimum_confidence, (int, float))
            or not math.isfinite(float(self.minimum_confidence))
            or not 0.0 <= float(self.minimum_confidence) <= 1.0
        ):
            raise ValueError("minimum_confidence must be finite and in [0, 1].")

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "required_airfoil_ids": list(self.required_airfoil_ids),
            "expected_coordinate_identities": [
                dict(value.as_mapping())
                for value in self.expected_coordinate_identities
            ],
            "allowed_provider_identities": [
                value.as_mapping() for value in self.allowed_provider_identities
            ],
            "expected_anchor_radii": list(self.expected_anchor_radii),
            "required_operating_condition_ids": list(
                self.required_operating_condition_ids
            ),
            "expected_final_query_count": self.expected_final_query_count,
            "allowed_promotion_record_sha256": list(
                self.allowed_promotion_record_sha256
            ),
            "minimum_confidence": float(self.minimum_confidence),
        }


@dataclass(frozen=True)
class RotorPolarEvidence:
    """Auditable result derived from polar tables and actual annulus queries."""

    policy: RotorPolarEvidencePolicy
    airfoil_ids: tuple[str, ...]
    gates: Mapping[str, bool]
    query_envelope: Mapping[str, int | float | None]
    operating_condition_ids: tuple[str, ...]
    providers: tuple[Mapping[str, str], ...]
    coordinate_sources: Mapping[str, Mapping[str, str]]
    promotion: PolarPromotionEvidence | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "gates", MappingProxyType(dict(self.gates)))
        object.__setattr__(
            self, "query_envelope", MappingProxyType(dict(self.query_envelope))
        )
        object.__setattr__(
            self,
            "providers",
            tuple(MappingProxyType(dict(provider)) for provider in self.providers),
        )
        object.__setattr__(
            self,
            "coordinate_sources",
            MappingProxyType(
                {
                    key: MappingProxyType(dict(value))
                    for key, value in self.coordinate_sources.items()
                }
            ),
        )

    @property
    def passed(self) -> bool:
        return bool(self.gates) and all(self.gates.values())

    def matches_benchmark(
        self, operating_condition_ids: Sequence[str], annulus_count: int
    ) -> bool:
        """Bind passed evidence to the exact benchmark cases and radial resolution."""
        expected_ids = tuple(operating_condition_ids)
        return (
            self.passed
            and self.operating_condition_ids == expected_ids
            and self.query_envelope.get("query_count")
            == len(expected_ids) * annulus_count
        )

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "schema_version": ROTOR_POLAR_EVIDENCE_SCHEMA_VERSION,
            "passed": self.passed,
            "policy": dict(self.policy.as_mapping()),
            "airfoil_ids": list(self.airfoil_ids),
            "operating_condition_ids": list(self.operating_condition_ids),
            "gates": dict(self.gates),
            "query_envelope": dict(self.query_envelope),
            "providers": [dict(provider) for provider in self.providers],
            "coordinate_sources": {
                key: dict(value) for key, value in self.coordinate_sources.items()
            },
            "promotion": (
                None if self.promotion is None else dict(self.promotion.as_mapping())
            ),
        }


def _provider_record(value: Any) -> Mapping[str, str] | None:
    if not isinstance(value, Mapping):
        return None
    required = ("name", "adapter_version", "backend_name", "backend_version")
    if any(not isinstance(value.get(key), str) or not value[key] for key in required):
        return None
    return {key: str(value[key]) for key in required}


def _query_envelope(
    results: Sequence[BEMRotorResult],
) -> tuple[Mapping[str, int | float | None], bool, tuple[str, ...]]:
    elements = tuple(element for result in results for element in result.elements)
    if not elements:
        return {
            "rotor_result_count": len(results),
            "query_count": 0,
            "solver_query_count": 0,
            "r_over_R_min": None,
            "r_over_R_max": None,
            "alpha_rad_min": None,
            "alpha_rad_max": None,
            "reynolds_min": None,
            "reynolds_max": None,
            "mach_min": None,
            "mach_max": None,
        }, False, ()
    solutions = tuple(element.solution for element in elements)
    envelopes = tuple(result.polar_query_envelope for result in results)
    envelope: Mapping[str, int | float | None] = {
        "rotor_result_count": len(results),
        "query_count": len(solutions),
        "solver_query_count": sum(item.query_count for item in envelopes),
        "r_over_R_min": min(solution.r_over_R for solution in solutions),
        "r_over_R_max": max(solution.r_over_R for solution in solutions),
        "alpha_rad_min": min(item.alpha_rad_min for item in envelopes),
        "alpha_rad_max": max(item.alpha_rad_max for item in envelopes),
        "reynolds_min": min(item.reynolds_min for item in envelopes),
        "reynolds_max": max(item.reynolds_max for item in envelopes),
        "mach_min": min(item.mach_min for item in envelopes),
        "mach_max": max(item.mach_max for item in envelopes),
    }
    sources = tuple(
        dict.fromkeys(
            source
            for result in results
            for source in result.polar_query_envelope.sources
        )
    )
    return envelope, True, sources


def assess_rotor_polar_evidence(
    schedule: SpanwisePolarSchedule,
    rotor_results: Sequence[BEMRotorResult],
    policy: RotorPolarEvidencePolicy,
    *,
    promotion: PolarPromotionEvidence | None = None,
) -> RotorPolarEvidence:
    """Assess real table identity and the envelope actually consumed by BEM."""
    if not isinstance(schedule, SpanwisePolarSchedule):
        raise TypeError("schedule must be a SpanwisePolarSchedule.")
    if not isinstance(policy, RotorPolarEvidencePolicy):
        raise TypeError("policy must be a RotorPolarEvidencePolicy.")
    if promotion is not None and not isinstance(promotion, PolarPromotionEvidence):
        raise TypeError("promotion must be PolarPromotionEvidence or None.")
    results = tuple(rotor_results)
    if not all(isinstance(result, BEMRotorResult) for result in results):
        raise TypeError("rotor_results must contain BEMRotorResult values.")

    tables = tuple(
        table for anchor in schedule.anchors for table in anchor.family.tables
    )
    providers: list[Mapping[str, str]] = []
    coordinate_sources: dict[str, Mapping[str, str]] = {}
    provider_tables = True
    coordinate_identity = True
    approved_providers = True
    minimum_confidence = True
    table_sources: list[str] = []
    for table in tables:
        metadata = table.metadata
        provider = _provider_record(metadata.get("provider"))
        provider_tables = provider_tables and bool(
            metadata.get("evidence_class") == "provider_generated_polar"
            and metadata.get("complete") is True
            and isinstance(metadata.get("cache_key"), str)
            and metadata["cache_key"]
            and provider is not None
        )
        if provider is not None:
            providers.append(provider)
            approved_providers = approved_providers and any(
                provider == expected.as_mapping()
                for expected in policy.allowed_provider_identities
            )
        else:
            approved_providers = False

        airfoil_source = metadata.get("airfoil_source")
        coordinate_hash = metadata.get("airfoil_coordinate_sha256")
        valid_coordinate = bool(
            isinstance(airfoil_source, str)
            and airfoil_source
            and isinstance(coordinate_hash, str)
            and _SHA256.fullmatch(coordinate_hash.lower())
        )
        coordinate_identity = coordinate_identity and valid_coordinate
        if valid_coordinate:
            record = {"source": airfoil_source, "sha256": coordinate_hash.lower()}
            previous = coordinate_sources.get(table.airfoil_id)
            coordinate_identity = coordinate_identity and (
                previous is None or previous == record
            )
            coordinate_sources[table.airfoil_id] = record

        confidence = metadata.get("confidence")
        if not isinstance(confidence, (tuple, list)) or len(confidence) != len(
            table.alpha_rad
        ):
            minimum_confidence = False
        else:
            numeric = tuple(value for value in confidence if value is not None)
            if numeric:
                minimum_confidence = minimum_confidence and all(
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and math.isfinite(float(value))
                    and float(value) >= policy.minimum_confidence
                    for value in numeric
                ) and len(numeric) == len(confidence)
            elif provider is not None and provider["name"] == "neuralfoil":
                minimum_confidence = False
        table_sources.append(table.source)

    envelope, has_queries, consumed_sources = _query_envelope(results)
    no_clamped = has_queries and all(
        result.polar_bounds == "error"
        and not result.polar_query_envelope.clamped_dimensions
        for result in results
    )
    declared_sources = set(table_sources)
    consumed_source_set = set(consumed_sources)
    airfoil_source_coverage = all(
        any(
            table.airfoil_id == airfoil_id and table.source in consumed_source_set
            for table in tables
        )
        for airfoil_id in policy.required_airfoil_ids
    )
    source_coverage = (
        has_queries
        and consumed_source_set.issubset(declared_sources)
        and airfoil_source_coverage
    )
    observed_condition_ids = tuple(result.operating_condition_id for result in results)
    reviewed_promotion = bool(
        promotion is not None
        and promotion.approved
        and promotion.promotion_record_sha256
        in policy.allowed_promotion_record_sha256
    )
    unique_provider_values = {
        tuple(sorted(provider.items())): provider for provider in providers
    }.values()
    expected_coordinates = {
        value.airfoil_id: {
            "source": value.source,
            "sha256": value.sha256,
        }
        for value in policy.expected_coordinate_identities
    }
    gates = {
        "required_airfoil_schedule": schedule.airfoil_ids
        == policy.required_airfoil_ids,
        "spanwise_anchor_identity": tuple(
            anchor.r_over_R for anchor in schedule.anchors
        )
        == policy.expected_anchor_radii,
        "provider_generated_tables": provider_tables,
        "coordinate_identity": coordinate_identity
        and coordinate_sources == expected_coordinates,
        "approved_providers": approved_providers,
        "minimum_confidence": minimum_confidence,
        "query_envelope": has_queries,
        "operating_condition_coverage": observed_condition_ids
        == policy.required_operating_condition_ids,
        "final_query_count": envelope["query_count"]
        == policy.expected_final_query_count,
        "no_clamped_queries": no_clamped,
        "source_coverage": source_coverage,
        "reviewed_promotion": reviewed_promotion,
    }
    return RotorPolarEvidence(
        policy=policy,
        airfoil_ids=schedule.airfoil_ids,
        gates=gates,
        query_envelope=envelope,
        operating_condition_ids=observed_condition_ids,
        providers=tuple(dict(provider) for provider in unique_provider_values),
        coordinate_sources=coordinate_sources,
        promotion=promotion,
    )
