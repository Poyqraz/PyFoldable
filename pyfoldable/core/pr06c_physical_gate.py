"""Final, fail-closed PR-06C physical-qualification decision."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


PR06C_PHYSICAL_GATE_SCHEMA_VERSION = 1
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_EXPECTED_BENCHMARK_GATES = (
    "solution_coverage",
    "ct_wmape",
    "cp_wmape",
    "ct_bias",
    "cp_bias",
    "radial_convergence",
    "representative_polar_evidence",
    "regime_solution_coverage",
    "regime_ct_wmape",
    "regime_cp_wmape",
    "regime_ct_bias",
    "regime_cp_bias",
)
_EXPECTED_POLAR_GATES = (
    "required_airfoil_schedule",
    "spanwise_anchor_identity",
    "provider_generated_tables",
    "coordinate_identity",
    "approved_providers",
    "minimum_confidence",
    "query_envelope",
    "operating_condition_coverage",
    "final_query_count",
    "no_clamped_queries",
    "source_coverage",
    "reviewed_promotion",
)
_FROZEN_POLICY = {
    "minimum_solution_coverage": 0.95,
    "maximum_ct_wmape": 0.15,
    "maximum_cp_wmape": 0.20,
    "maximum_absolute_ct_normalized_bias": 0.10,
    "maximum_absolute_cp_normalized_bias": 0.15,
    "maximum_radial_terminal_delta": 0.005,
    "require_representative_polar_evidence": True,
}


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value.lower()) is not None


def canonical_json_sha256(value: Any) -> str:
    """Return a stable digest for one JSON-compatible evidence document."""
    payload = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class PR06CPhysicalGatePolicy:
    """Pinned identities required by the final PR-06C decision."""

    benchmark_id: str
    fixture_sha256: str
    required_airfoil_ids: tuple[str, ...]
    allowed_provider_names: tuple[str, ...]
    required_model_variants: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.benchmark_id:
            raise ValueError("benchmark_id must not be empty.")
        if not _valid_sha256(self.fixture_sha256):
            raise ValueError("fixture_sha256 must be a lowercase SHA-256 digest.")
        object.__setattr__(self, "fixture_sha256", self.fixture_sha256.lower())
        for name in (
            "required_airfoil_ids",
            "allowed_provider_names",
            "required_model_variants",
        ):
            values = getattr(self, name)
            if (
                not isinstance(values, tuple)
                or not values
                or any(not isinstance(value, str) or not value for value in values)
                or len(set(values)) != len(values)
            ):
                raise ValueError(f"{name} must be a non-empty tuple of unique strings.")

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "fixture_sha256": self.fixture_sha256,
            "required_airfoil_ids": list(self.required_airfoil_ids),
            "allowed_provider_names": list(self.allowed_provider_names),
            "required_model_variants": list(self.required_model_variants),
            "frozen_benchmark_policy": dict(_FROZEN_POLICY),
        }


@dataclass(frozen=True)
class PR06CPhysicalGateDecision:
    """Auditable PR-06C decision; passing requires every evidence class."""

    policy: PR06CPhysicalGatePolicy
    gates: Mapping[str, bool]
    blockers: tuple[str, ...]
    benchmark_variant_sha256: str | None
    model_form_review_sha256: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "gates", MappingProxyType(dict(self.gates)))

    @property
    def passed(self) -> bool:
        return bool(self.gates) and all(self.gates.values())

    @property
    def failed_gates(self) -> tuple[str, ...]:
        return tuple(name for name, passed in self.gates.items() if not passed)

    def as_mapping(self) -> Mapping[str, Any]:
        return {
            "schema_version": PR06C_PHYSICAL_GATE_SCHEMA_VERSION,
            "passed": self.passed,
            "decision": "pr06c_physically_qualified" if self.passed else "pr06c_blocked",
            "policy": dict(self.policy.as_mapping()),
            "gates": dict(self.gates),
            "failed_gates": list(self.failed_gates),
            "blockers": list(self.blockers),
            "benchmark_variant_sha256": self.benchmark_variant_sha256,
            "model_form_review_sha256": self.model_form_review_sha256,
        }


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _frozen_policy_matches(value: Any) -> bool:
    policy = _mapping(value)
    if set(policy) != set(_FROZEN_POLICY):
        return False
    for name, expected in _FROZEN_POLICY.items():
        actual = policy.get(name)
        if isinstance(expected, bool):
            if actual is not expected:
                return False
        elif (
            isinstance(actual, bool)
            or not isinstance(actual, (int, float))
            or not math.isclose(float(actual), expected, rel_tol=0.0, abs_tol=1.0e-15)
        ):
            return False
    return True


def _polar_evidence_gates(
    evidence: Any,
    *,
    policy: PR06CPhysicalGatePolicy,
    point_ids: tuple[str, ...],
    annulus_count: int | None,
) -> tuple[bool, bool]:
    document = _mapping(evidence)
    gates = _mapping(document.get("gates"))
    evidence_policy = _mapping(document.get("policy"))
    providers = document.get("providers")
    coordinates = _mapping(document.get("coordinate_sources"))
    promotion = _mapping(document.get("promotion"))
    envelope = _mapping(document.get("query_envelope"))
    provider_identity = bool(
        isinstance(providers, list)
        and providers
        and all(
            isinstance(provider, Mapping)
            and provider.get("name") in policy.allowed_provider_names
            and all(
                isinstance(provider.get(name), str) and provider.get(name)
                for name in (
                    "adapter_version",
                    "backend_name",
                    "backend_version",
                )
            )
            for provider in providers
        )
    )
    coordinate_identity = bool(
        set(coordinates) == set(policy.required_airfoil_ids)
        and all(
            isinstance(coordinates[airfoil_id], Mapping)
            and isinstance(coordinates[airfoil_id].get("source"), str)
            and coordinates[airfoil_id].get("source")
            and _valid_sha256(coordinates[airfoil_id].get("sha256"))
            for airfoil_id in policy.required_airfoil_ids
        )
    )
    promotion_identity = bool(
        promotion.get("review_state") == "approved"
        and promotion.get("promotion_allowed") is True
        and all(
            _valid_sha256(promotion.get(name))
            for name in (
                "first_capture_manifest_sha256",
                "second_capture_manifest_sha256",
                "reproducibility_report_sha256",
                "promotion_record_sha256",
            )
        )
    )
    expected_coordinates = evidence_policy.get("expected_coordinate_identities")
    allowed_providers = evidence_policy.get("allowed_provider_identities")
    evidence_policy_binding = bool(
        tuple(evidence_policy.get("required_airfoil_ids", ()))
        == policy.required_airfoil_ids
        and isinstance(expected_coordinates, list)
        and {
            coordinate.get("airfoil_id"): {
                "source": coordinate.get("source"),
                "sha256": coordinate.get("sha256"),
            }
            for coordinate in expected_coordinates
            if isinstance(coordinate, Mapping)
            and isinstance(coordinate.get("airfoil_id"), str)
        }
        == coordinates
        and isinstance(allowed_providers, list)
        and all(provider in allowed_providers for provider in providers or ())
        and tuple(evidence_policy.get("required_operating_condition_ids", ()))
        == point_ids
        and evidence_policy.get("expected_final_query_count")
        == len(point_ids) * annulus_count
        if annulus_count is not None
        else False
    )
    promotion_policy_binding = bool(
        promotion.get("promotion_record_sha256")
        in evidence_policy.get("allowed_promotion_record_sha256", ())
    )
    complete = bool(
        document.get("passed") is True
        and tuple(document.get("airfoil_ids", ())) == policy.required_airfoil_ids
        and set(gates) == set(_EXPECTED_POLAR_GATES)
        and all(gates.get(name) is True for name in _EXPECTED_POLAR_GATES)
        and provider_identity
        and coordinate_identity
        and promotion_identity
        and evidence_policy_binding
        and promotion_policy_binding
    )
    query_binding = bool(
        annulus_count is not None
        and annulus_count > 0
        and tuple(document.get("operating_condition_ids", ())) == point_ids
        and envelope.get("query_count") == len(point_ids) * annulus_count
    )
    return complete, query_binding


def _review_gates(
    review: Any,
    *,
    policy: PR06CPhysicalGatePolicy,
    variant_sha256: str | None,
) -> tuple[bool, bool, str | None]:
    document = _mapping(review)
    compared = document.get("compared_variants")
    selected = document.get("selected_variant")
    review_sha = canonical_json_sha256(document) if document else None
    independent = bool(
        document.get("schema_version") == 1
        and document.get("review_state") == "approved"
        and document.get("independent_reviewer") is True
        and isinstance(document.get("reviewer_id"), str)
        and document.get("reviewer_id")
        and _valid_sha256(document.get("report_sha256"))
        and isinstance(compared, list)
        and set(compared) == set(policy.required_model_variants)
        and selected in compared
        and document.get("target_fitting_performed") is False
    )
    bound = bool(
        variant_sha256 is not None
        and document.get("benchmark_variant_sha256") == variant_sha256
    )
    return independent, bound, review_sha


def assess_pr06c_physical_gate(
    benchmark_report: Mapping[str, Any],
    model_form_review: Mapping[str, Any] | None,
    *,
    policy: PR06CPhysicalGatePolicy,
) -> PR06CPhysicalGateDecision:
    """Bind the frozen benchmark, typed polar evidence, and independent review."""
    if not isinstance(benchmark_report, Mapping):
        raise TypeError("benchmark_report must be a mapping.")
    if model_form_review is not None and not isinstance(model_form_review, Mapping):
        raise TypeError("model_form_review must be a mapping or None.")
    if not isinstance(policy, PR06CPhysicalGatePolicy):
        raise TypeError("policy must be a PR06CPhysicalGatePolicy.")

    fixture = _mapping(benchmark_report.get("fixture"))
    variant = _mapping(benchmark_report.get("selected_variant"))
    benchmark_gates = _mapping(variant.get("gates"))
    predictions = variant.get("predictions")
    point_ids = tuple(
        prediction.get("point_id")
        for prediction in predictions
        if isinstance(prediction, Mapping)
        and isinstance(prediction.get("point_id"), str)
    ) if isinstance(predictions, list) else ()
    settings = _mapping(variant.get("settings"))
    raw_annulus_count = settings.get("annulus_count")
    annulus_count = (
        raw_annulus_count
        if isinstance(raw_annulus_count, int) and not isinstance(raw_annulus_count, bool)
        else None
    )
    variant_sha = canonical_json_sha256(variant) if variant else None
    representative, query_binding = _polar_evidence_gates(
        variant.get("polar_evidence"),
        policy=policy,
        point_ids=point_ids,
        annulus_count=annulus_count,
    )
    independent_review, review_binding, review_sha = _review_gates(
        model_form_review,
        policy=policy,
        variant_sha256=variant_sha,
    )
    benchmark_accuracy = bool(
        variant.get("passed") is True
        and set(benchmark_gates) == set(_EXPECTED_BENCHMARK_GATES)
        and all(benchmark_gates.get(name) is True for name in _EXPECTED_BENCHMARK_GATES)
        and variant.get("point_count") == len(point_ids)
        and len(point_ids) > 0
        and len(set(point_ids)) == len(point_ids)
    )
    gates = {
        "benchmark_identity": benchmark_report.get("benchmark_id")
        == policy.benchmark_id,
        "fixture_identity": fixture.get("sha256") == policy.fixture_sha256,
        "frozen_policy": _frozen_policy_matches(benchmark_report.get("policy")),
        "benchmark_accuracy": benchmark_accuracy,
        "representative_polar_evidence": representative,
        "benchmark_query_binding": query_binding,
        "independent_model_form_review": independent_review,
        "review_binds_benchmark": review_binding,
    }
    explanations = {
        "benchmark_identity": "the qualification benchmark id is not the pinned PR-06C id",
        "fixture_identity": "the UIUC fixture digest is absent or changed",
        "frozen_policy": "the frozen accuracy thresholds are absent or changed",
        "benchmark_accuracy": "one or more overall, regime, coverage, bias, or convergence gates failed",
        "representative_polar_evidence": "the exact E63-to-APC12 provider, coordinate, confidence, and two-capture chain is incomplete",
        "benchmark_query_binding": "polar evidence is not bound to every benchmark annulus query",
        "independent_model_form_review": "an approved independent no-target-fitting model-form comparison is absent",
        "review_binds_benchmark": "the model-form review is not bound to the selected benchmark variant digest",
    }
    blockers = tuple(explanations[name] for name, passed in gates.items() if not passed)
    return PR06CPhysicalGateDecision(
        policy=policy,
        gates=gates,
        blockers=blockers,
        benchmark_variant_sha256=variant_sha,
        model_form_review_sha256=review_sha,
    )
