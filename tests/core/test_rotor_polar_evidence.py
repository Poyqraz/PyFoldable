import hashlib
import math

import pytest

from pyfoldable.core import (
    AirfoilCoordinateIdentity,
    BEMAnnulusSettings,
    BEMRotorSettings,
    BladeGeometry,
    BladeStation,
    OperatingCondition,
    PolarFamily,
    PolarTable,
    PolarPromotionEvidence,
    ProviderIdentity,
    RotorPolarEvidencePolicy,
    SpanwisePolarAnchor,
    SpanwisePolarSchedule,
    assess_rotor_polar_evidence,
    solve_bem_rotor,
)


def _family(
    airfoil_id: str,
    *,
    source: str,
    confidence: tuple[float | None, ...] = (None, None),
    provider_name: str = "xfoil-subprocess",
) -> PolarFamily:
    metadata = {
        "evidence_class": "provider_generated_polar",
        "complete": True,
        "cache_key": f"cache-{airfoil_id}",
        "airfoil_source": f"local:{airfoil_id}.dat",
        "airfoil_coordinate_sha256": hashlib.sha256(
            airfoil_id.encode("utf-8")
        ).hexdigest(),
        "provider": {
            "name": provider_name,
            "adapter_version": "2",
            "backend_name": "XFOIL" if provider_name == "xfoil-subprocess" else "NeuralFoil",
            "backend_version": "6.99" if provider_name == "xfoil-subprocess" else "0.3.3",
        },
        "confidence": confidence,
    }
    return PolarFamily(
        tuple(
            PolarTable(
                airfoil_id=airfoil_id,
                scenario_id="pr06c-real",
                reynolds=reynolds,
                mach=mach,
                alpha_rad=(-math.pi / 2.0, math.pi / 2.0),
                cl=(0.8, 0.8),
                cd=(0.02, 0.02),
                cm=(0.0, 0.0),
                source=source,
                metadata=metadata,
            )
            for mach in (0.0, 0.5)
            for reynolds in (1.0e3, 1.0e7)
        )
    )


def _schedule(
    *,
    confidence: tuple[float | None, ...] = (None, None),
    provider_name: str = "xfoil-subprocess",
    radii: tuple[float, float] = (0.2, 0.8),
) -> SpanwisePolarSchedule:
    return SpanwisePolarSchedule(
        "E63-to-APC12",
        (
            SpanwisePolarAnchor(
                radii[0],
                _family(
                    "E63",
                    source="xfoil-subprocess:6.99:E63",
                    confidence=confidence,
                    provider_name=provider_name,
                ),
            ),
            SpanwisePolarAnchor(
                radii[1],
                _family(
                    "APC12",
                    source="xfoil-subprocess:6.99:APC12",
                    confidence=confidence,
                    provider_name=provider_name,
                ),
            ),
        ),
    )


def _blade() -> BladeGeometry:
    return BladeGeometry(
        diameter_m=0.30,
        hub_radius_m=0.02,
        blade_count=2,
        stations=(
            BladeStation(0.2, 0.03, 0.35, "E63"),
            BladeStation(0.8, 0.02, 0.20, "APC12"),
        ),
    )


def _condition() -> OperatingCondition:
    return OperatingCondition(
        id="evidence",
        angular_speed_rad_s=500.0,
        forward_speed_m_s=5.0,
        air_density_kg_m3=1.225,
        dynamic_viscosity_pa_s=1.81e-5,
        temperature_k=288.15,
        pressure_pa=101325.0,
    )


def _policy() -> RotorPolarEvidencePolicy:
    return RotorPolarEvidencePolicy(
        required_airfoil_ids=("E63", "APC12"),
        expected_coordinate_identities=tuple(
            AirfoilCoordinateIdentity(
                airfoil_id=airfoil_id,
                source=f"local:{airfoil_id}.dat",
                sha256=hashlib.sha256(airfoil_id.encode("utf-8")).hexdigest(),
            )
            for airfoil_id in ("E63", "APC12")
        ),
        allowed_provider_identities=(
            ProviderIdentity("xfoil-subprocess", "2", "XFOIL", "6.99"),
            ProviderIdentity("neuralfoil", "2", "NeuralFoil", "0.3.3"),
        ),
        expected_anchor_radii=(0.2, 0.8),
        required_operating_condition_ids=("evidence",),
        expected_final_query_count=4,
        allowed_promotion_record_sha256=("f" * 64,),
        minimum_confidence=0.5,
    )


def _promotion() -> PolarPromotionEvidence:
    return PolarPromotionEvidence(
        review_state="approved",
        promotion_allowed=True,
        first_capture_manifest_sha256="a" * 64,
        second_capture_manifest_sha256="b" * 64,
        reproducibility_report_sha256="c" * 64,
        promotion_record_sha256="f" * 64,
    )


def test_provider_backed_spanwise_query_envelope_passes_all_evidence_gates():
    schedule = _schedule()
    result = solve_bem_rotor(
        _blade(),
        _condition(),
        schedule,
        settings=BEMRotorSettings(
            annulus_count=4,
            annulus_settings=BEMAnnulusSettings(
                loading_branch="signed_nonreversed"
            ),
        ),
    )

    evidence = assess_rotor_polar_evidence(
        schedule, (result,), _policy(), promotion=_promotion()
    )

    assert evidence.passed
    assert all(evidence.gates.values())
    assert evidence.query_envelope["query_count"] == 4
    assert evidence.query_envelope["reynolds_min"] > 0.0
    assert evidence.query_envelope["alpha_rad_min"] <= evidence.query_envelope["alpha_rad_max"]
    assert evidence.airfoil_ids == ("E63", "APC12")
    assert evidence.operating_condition_ids == ("evidence",)
    assert evidence.matches_benchmark(("evidence",), 4)
    assert not evidence.matches_benchmark(("different",), 4)
    assert evidence.as_mapping()["schema_version"] == 1


def test_evidence_rejects_low_confidence_or_unapproved_provider():
    low_schedule = _schedule(confidence=(0.2, 0.3), provider_name="neuralfoil")
    result = solve_bem_rotor(
        _blade(), _condition(), low_schedule, settings=BEMRotorSettings(4)
    )
    low = assess_rotor_polar_evidence(
        low_schedule, (result,), _policy(), promotion=_promotion()
    )
    assert not low.passed
    assert not low.gates["minimum_confidence"]

    unknown_schedule = _schedule(provider_name="hand-edited")
    result = solve_bem_rotor(
        _blade(), _condition(), unknown_schedule, settings=BEMRotorSettings(4)
    )
    unknown = assess_rotor_polar_evidence(
        unknown_schedule, (result,), _policy(), promotion=_promotion()
    )
    assert not unknown.gates["approved_providers"]


def test_evidence_rejects_clamped_span_or_missing_query_envelope():
    schedule = _schedule(radii=(0.3, 0.7))
    result = solve_bem_rotor(
        _blade(),
        _condition(),
        schedule,
        bounds="clamp",
        settings=BEMRotorSettings(4),
    )
    clamped = assess_rotor_polar_evidence(
        schedule, (result,), _policy(), promotion=_promotion()
    )
    assert not clamped.gates["no_clamped_queries"]

    empty = assess_rotor_polar_evidence(
        schedule, (), _policy(), promotion=_promotion()
    )
    assert not empty.gates["query_envelope"]


def test_analytic_proxy_metadata_cannot_be_promoted_as_representative():
    family = _family("E63", source="analytic-proxy:E63")
    proxy = PolarFamily(
        tuple(
            PolarTable(
                airfoil_id=table.airfoil_id,
                scenario_id=table.scenario_id,
                reynolds=table.reynolds,
                mach=table.mach,
                alpha_rad=table.alpha_rad,
                cl=table.cl,
                cd=table.cd,
                cm=table.cm,
                source=table.source,
                metadata={**table.metadata, "evidence_class": "analytic_proxy"},
            )
            for table in family.tables
        )
    )
    schedule = SpanwisePolarSchedule(
        "proxy",
        (
            SpanwisePolarAnchor(0.2, proxy),
            SpanwisePolarAnchor(0.8, _family("APC12", source="xfoil:APC12")),
        ),
    )
    result = solve_bem_rotor(
        _blade(), _condition(), schedule, settings=BEMRotorSettings(4)
    )

    evidence = assess_rotor_polar_evidence(
        schedule, (result,), _policy(), promotion=_promotion()
    )

    assert not evidence.gates["provider_generated_tables"]


def test_evidence_rejects_unpinned_coordinate_provider_and_promotion_identity():
    schedule = _schedule()
    result = solve_bem_rotor(
        _blade(), _condition(), schedule, settings=BEMRotorSettings(4)
    )

    wrong_coordinate_policy = RotorPolarEvidencePolicy(
        required_airfoil_ids=_policy().required_airfoil_ids,
        expected_coordinate_identities=(
            AirfoilCoordinateIdentity("E63", "local:E63.dat", "0" * 64),
            _policy().expected_coordinate_identities[1],
        ),
        allowed_provider_identities=_policy().allowed_provider_identities,
        expected_anchor_radii=(0.2, 0.8),
        required_operating_condition_ids=("evidence",),
        expected_final_query_count=4,
        allowed_promotion_record_sha256=("f" * 64,),
    )
    wrong_coordinate = assess_rotor_polar_evidence(
        schedule, (result,), wrong_coordinate_policy, promotion=_promotion()
    )
    assert not wrong_coordinate.gates["coordinate_identity"]

    wrong_provider_policy = RotorPolarEvidencePolicy(
        required_airfoil_ids=_policy().required_airfoil_ids,
        expected_coordinate_identities=_policy().expected_coordinate_identities,
        allowed_provider_identities=(
            ProviderIdentity("xfoil-subprocess", "2", "XFOIL", "7.0"),
        ),
        expected_anchor_radii=(0.2, 0.8),
        required_operating_condition_ids=("evidence",),
        expected_final_query_count=4,
        allowed_promotion_record_sha256=("f" * 64,),
    )
    wrong_provider = assess_rotor_polar_evidence(
        schedule, (result,), wrong_provider_policy, promotion=_promotion()
    )
    assert not wrong_provider.gates["approved_providers"]

    unreviewed = PolarPromotionEvidence(
        review_state="unreviewed",
        promotion_allowed=False,
        first_capture_manifest_sha256="a" * 64,
        second_capture_manifest_sha256="b" * 64,
        reproducibility_report_sha256="c" * 64,
        promotion_record_sha256="f" * 64,
    )
    evidence = assess_rotor_polar_evidence(
        schedule, (result,), _policy(), promotion=unreviewed
    )
    assert not evidence.gates["reviewed_promotion"]

    wrong_schedule_policy = RotorPolarEvidencePolicy(
        required_airfoil_ids=_policy().required_airfoil_ids,
        expected_coordinate_identities=_policy().expected_coordinate_identities,
        allowed_provider_identities=_policy().allowed_provider_identities,
        expected_anchor_radii=(0.25, 0.8),
        required_operating_condition_ids=("evidence",),
        expected_final_query_count=4,
        allowed_promotion_record_sha256=("f" * 64,),
    )
    wrong_schedule = assess_rotor_polar_evidence(
        schedule, (result,), wrong_schedule_policy, promotion=_promotion()
    )
    assert not wrong_schedule.gates["spanwise_anchor_identity"]


def test_evidence_requires_exact_condition_set_and_final_query_count():
    schedule = _schedule()
    result = solve_bem_rotor(
        _blade(), _condition(), schedule, settings=BEMRotorSettings(4)
    )
    extra = solve_bem_rotor(
        _blade(),
        OperatingCondition(
            id="unexpected",
            angular_speed_rad_s=500.0,
            forward_speed_m_s=5.0,
            air_density_kg_m3=1.225,
            dynamic_viscosity_pa_s=1.81e-5,
            temperature_k=288.15,
            pressure_pa=101325.0,
        ),
        schedule,
        settings=BEMRotorSettings(4),
    )

    wrong_count = assess_rotor_polar_evidence(
        schedule, (result,), _policy(), promotion=_promotion()
    )
    assert wrong_count.gates["operating_condition_coverage"]
    assert wrong_count.gates["final_query_count"]

    unexpected = assess_rotor_polar_evidence(
        schedule, (result, extra), _policy(), promotion=_promotion()
    )
    assert not unexpected.gates["operating_condition_coverage"]
    assert not unexpected.gates["final_query_count"]
