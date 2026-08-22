import copy
import hashlib

from pyfoldable.core import (
    PR06CPhysicalGatePolicy,
    assess_pr06c_physical_gate,
    canonical_json_sha256,
)


FIXTURE_SHA256 = "c6f04a4d32ea9c4421db38ec67a2164be0b81b13c64b0a81718792dfd047531b"


def _policy() -> PR06CPhysicalGatePolicy:
    return PR06CPhysicalGatePolicy(
        benchmark_id="pr06c-uiuc-apcsf-10x4.7-qualification-v1",
        fixture_sha256=FIXTURE_SHA256,
        required_airfoil_ids=("E63", "APC12"),
        allowed_provider_names=("xfoil-subprocess",),
        required_model_variants=(
            "qualified_2d",
            "rotational_augmentation",
            "tip_wake_candidate",
        ),
    )


def _polar_evidence(point_ids: tuple[str, ...], annulus_count: int):
    coordinate_sources = {
        airfoil_id: {
            "source": f"caller-local:{airfoil_id}.dat",
            "sha256": hashlib.sha256(airfoil_id.encode()).hexdigest(),
        }
        for airfoil_id in ("E63", "APC12")
    }
    provider = {
        "name": "xfoil-subprocess",
        "adapter_version": "2",
        "backend_name": "XFOIL",
        "backend_version": "6.99",
    }
    return {
        "passed": True,
        "airfoil_ids": ["E63", "APC12"],
        "operating_condition_ids": list(point_ids),
        "gates": {
            gate: True
            for gate in (
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
        },
        "query_envelope": {"query_count": len(point_ids) * annulus_count},
        "providers": [provider],
        "coordinate_sources": coordinate_sources,
        "promotion": {
            "review_state": "approved",
            "promotion_allowed": True,
            "first_capture_manifest_sha256": "a" * 64,
            "second_capture_manifest_sha256": "b" * 64,
            "reproducibility_report_sha256": "c" * 64,
            "promotion_record_sha256": "d" * 64,
        },
        "policy": {
            "required_airfoil_ids": ["E63", "APC12"],
            "expected_coordinate_identities": [
                {"airfoil_id": airfoil_id, **coordinate_sources[airfoil_id]}
                for airfoil_id in ("E63", "APC12")
            ],
            "allowed_provider_identities": [provider],
            "expected_anchor_radii": [0.2, 0.98],
            "required_operating_condition_ids": list(point_ids),
            "expected_final_query_count": len(point_ids) * annulus_count,
            "allowed_promotion_record_sha256": ["d" * 64],
            "minimum_confidence": 0.5,
        },
    }


def _benchmark():
    point_ids = ("static-1", "forward-1")
    annulus_count = 80
    gate_names = (
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
    return {
        "benchmark_id": "pr06c-uiuc-apcsf-10x4.7-qualification-v1",
        "fixture": {"sha256": FIXTURE_SHA256},
        "policy": {
            "minimum_solution_coverage": 0.95,
            "maximum_ct_wmape": 0.15,
            "maximum_cp_wmape": 0.20,
            "maximum_absolute_ct_normalized_bias": 0.10,
            "maximum_absolute_cp_normalized_bias": 0.15,
            "maximum_radial_terminal_delta": 0.005,
            "require_representative_polar_evidence": True,
        },
        "selected_variant": {
            "passed": True,
            "gates": {name: True for name in gate_names},
            "point_count": 2,
            "representative_polar_evidence": True,
            "settings": {"annulus_count": annulus_count},
            "predictions": [{"point_id": point_id} for point_id in point_ids],
            "polar_evidence": _polar_evidence(point_ids, annulus_count),
        },
    }


def _review(benchmark):
    return {
        "schema_version": 1,
        "review_state": "approved",
        "independent_reviewer": True,
        "reviewer_id": "independent-aero-reviewer",
        "report_sha256": "e" * 64,
        "benchmark_variant_sha256": canonical_json_sha256(
            benchmark["selected_variant"]
        ),
        "compared_variants": [
            "qualified_2d",
            "rotational_augmentation",
            "tip_wake_candidate",
        ],
        "selected_variant": "rotational_augmentation",
        "target_fitting_performed": False,
    }


def test_complete_evidence_chain_passes_physical_gate():
    benchmark = _benchmark()
    decision = assess_pr06c_physical_gate(
        benchmark, _review(benchmark), policy=_policy()
    )

    assert decision.passed
    assert all(decision.gates.values())
    assert decision.failed_gates == ()
    assert decision.blockers == ()


def test_boolean_representative_claim_cannot_replace_typed_evidence():
    benchmark = _benchmark()
    benchmark["selected_variant"].pop("polar_evidence")
    decision = assess_pr06c_physical_gate(
        benchmark, _review(benchmark), policy=_policy()
    )

    assert not decision.passed
    assert not decision.gates["representative_polar_evidence"]
    assert "representative_polar_evidence" in decision.failed_gates


def test_gate_rejects_proxy_provider_and_changed_frozen_threshold():
    benchmark = _benchmark()
    benchmark["selected_variant"]["polar_evidence"]["providers"][0][
        "name"
    ] = "analytic-proxy"
    benchmark["policy"]["maximum_ct_wmape"] = 0.16
    decision = assess_pr06c_physical_gate(
        benchmark, _review(benchmark), policy=_policy()
    )

    assert not decision.gates["frozen_policy"]
    assert not decision.gates["representative_polar_evidence"]


def test_gate_rejects_missing_independent_review_and_unbound_report():
    benchmark = _benchmark()
    review = _review(benchmark)
    review["independent_reviewer"] = False
    review["benchmark_variant_sha256"] = "f" * 64
    decision = assess_pr06c_physical_gate(benchmark, review, policy=_policy())

    assert not decision.gates["independent_model_form_review"]
    assert not decision.gates["review_binds_benchmark"]


def test_gate_rejects_incomplete_query_binding_and_coordinate_identity():
    benchmark = _benchmark()
    evidence = benchmark["selected_variant"]["polar_evidence"]
    evidence["query_envelope"]["query_count"] -= 1
    evidence["coordinate_sources"].pop("APC12")
    decision = assess_pr06c_physical_gate(
        benchmark, _review(benchmark), policy=_policy()
    )

    assert not decision.gates["representative_polar_evidence"]
    assert not decision.gates["benchmark_query_binding"]


def test_gate_rejects_polar_artifact_not_bound_to_its_predeclared_policy():
    benchmark = _benchmark()
    evidence = benchmark["selected_variant"]["polar_evidence"]
    evidence["policy"]["allowed_promotion_record_sha256"] = ["e" * 64]
    decision = assess_pr06c_physical_gate(
        benchmark, _review(benchmark), policy=_policy()
    )

    assert not decision.gates["representative_polar_evidence"]


def test_gate_does_not_mutate_input_documents():
    benchmark = _benchmark()
    review = _review(benchmark)
    benchmark_before = copy.deepcopy(benchmark)
    review_before = copy.deepcopy(review)

    assess_pr06c_physical_gate(benchmark, review, policy=_policy())

    assert benchmark == benchmark_before
    assert review == review_before
