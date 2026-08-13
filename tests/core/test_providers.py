"""Provider contracts, cache identity, and partial-result behavior."""

from dataclasses import replace

import pytest

from pyfoldable.core import (
    AirfoilDefinition,
    PolarGenerationRequest,
    PolarGenerationResult,
    PolarPointResult,
    PolarProviderCapabilityError,
    PolarProviderExecutionError,
    ProviderCapabilities,
    ProviderIdentity,
    generate_polar,
)


AIRFOIL = AirfoilDefinition(
    id="TEST",
    source="fixture",
    coordinates=((1.0, 0.0), (0.5, 0.1), (0.0, 0.0), (0.5, -0.1), (1.0, 0.0)),
)
IDENTITY = ProviderIdentity("fake", "1", "fake-backend", "2")
CAPABILITIES = ProviderCapabilities(
    supports_mach=True,
    supports_n_crit=True,
    supports_forced_transition=True,
    supports_pointwise_confidence=True,
    supports_partial_results=True,
    supports_vectorized_alpha=True,
    supports_iteration_limit=True,
)


def _request(**changes) -> PolarGenerationRequest:
    base = PolarGenerationRequest(
        airfoil=AIRFOIL,
        alpha_rad=(-0.1, 0.0, 0.1),
        reynolds=100_000.0,
        options={"model_size": "large", "nested": {"b": 2, "a": 1}},
    )
    return replace(base, **changes)


def _point(alpha: float, *, confidence: float = 0.9) -> PolarPointResult:
    return PolarPointResult(
        alpha_rad=alpha,
        status="converged",
        cl=10.0 * alpha,
        cd=0.01 + alpha * alpha,
        cm=-0.02,
        confidence=confidence,
        iterations=5,
    )


class FakeProvider:
    identity = IDENTITY
    capabilities = CAPABILITIES

    def generate(self, request: PolarGenerationRequest) -> PolarGenerationResult:
        return PolarGenerationResult(
            request=request,
            provider=self.identity,
            points=tuple(_point(alpha) for alpha in request.alpha_rad),
            elapsed_s=0.01,
        )


def test_cache_key_is_deterministic_and_option_order_independent() -> None:
    first = _request(options={"nested": {"b": 2, "a": 1}, "model_size": "large"})
    second = _request(options={"model_size": "large", "nested": {"a": 1, "b": 2}})

    assert first.cache_key(IDENTITY) == second.cache_key(IDENTITY)
    assert len(first.cache_key(IDENTITY)) == 64


def test_request_snapshots_mutable_options_for_stable_cache_identity() -> None:
    options = {"model_size": "large", "nested": {"value": 1}}
    request = _request(options=options)
    original_key = request.cache_key(IDENTITY)

    options["model_size"] = "small"
    options["nested"]["value"] = 2

    assert request.cache_key(IDENTITY) == original_key
    assert request.options["model_size"] == "large"


@pytest.mark.parametrize(
    "changed",
    [
        {"alpha_rad": (-0.2, 0.0, 0.1)},
        {"reynolds": 200_000.0},
        {"mach": 0.1},
        {"n_crit": 7.0},
        {"xtr_upper": 0.5},
        {"max_iterations": 200},
        {"timeout_s": 60.0},
        {"scenario_id": "rough"},
        {"options": {"model_size": "xlarge"}},
    ],
)
def test_every_request_input_changes_cache_key(changed) -> None:
    assert _request().cache_key(IDENTITY) != _request(**changed).cache_key(IDENTITY)


def test_alpha_order_is_preserved_in_cache_and_descending_sweep_is_valid() -> None:
    ascending = _request(alpha_rad=(-0.1, 0.0, 0.1))
    descending = _request(alpha_rad=(0.1, 0.0, -0.1))

    assert ascending.cache_key(IDENTITY) != descending.cache_key(IDENTITY)


def test_geometry_and_backend_versions_change_cache_key() -> None:
    changed_geometry = replace(
        _request(),
        airfoil=replace(AIRFOIL, coordinates=(*AIRFOIL.coordinates[:-1], (1.0, -0.001))),
    )
    changed_backend = replace(IDENTITY, backend_version="3")

    assert _request().cache_key(IDENTITY) != changed_geometry.cache_key(IDENTITY)
    assert _request().cache_key(IDENTITY) != _request().cache_key(changed_backend)


def test_capability_validation_never_silently_ignores_fields() -> None:
    limited = ProviderCapabilities(False, False, False, False, True, False, False)

    with pytest.raises(
        PolarProviderCapabilityError,
        match="mach, n_crit, forced_transition, max_iterations",
    ):
        _request(
            mach=0.1,
            n_crit=7.0,
            xtr_upper=0.5,
            max_iterations=100,
        ).validate_capabilities(limited)


def test_generate_polar_validates_then_calls_provider() -> None:
    result = generate_polar(FakeProvider(), _request())

    assert result.complete
    assert result.converged_mask == (True, True, True)
    assert result.cache_key == result.request.cache_key(IDENTITY)


def test_partial_result_preserves_failure_and_can_build_partial_table() -> None:
    request = _request()
    failed = PolarPointResult(0.0, "not_converged", iterations=100, message="limit")
    result = PolarGenerationResult(
        request=request,
        provider=IDENTITY,
        points=(_point(-0.1), failed, _point(0.1, confidence=0.4)),
        elapsed_s=1.0,
        warnings=("one XFOIL point did not converge",),
    )

    assert not result.complete
    assert result.converged_mask == (True, False, True)
    assert result.usable_mask == (True, False, True)
    with pytest.raises(PolarProviderExecutionError, match="failed points"):
        result.to_polar_table()

    table = result.to_polar_table(require_complete=False)
    assert table.alpha_rad == (-0.1, 0.1)
    assert table.metadata["complete"] is False
    assert table.metadata["requested_point_count"] == 3
    assert table.metadata["usable_point_count"] == 2


def test_descending_provider_sweep_becomes_increasing_polar_table() -> None:
    request = _request(alpha_rad=(0.1, 0.0, -0.1))
    result = PolarGenerationResult(
        request,
        IDENTITY,
        tuple(_point(alpha) for alpha in request.alpha_rad),
        0.01,
    )

    assert tuple(point.alpha_rad for point in result.points) == (0.1, 0.0, -0.1)
    assert result.to_polar_table().alpha_rad == (-0.1, 0.0, 0.1)


def test_low_confidence_point_is_usable_but_not_converged() -> None:
    request = _request()
    low = PolarPointResult(
        0.0,
        "low_confidence",
        cl=0.0,
        cd=0.01,
        cm=-0.02,
        confidence=0.2,
    )
    result = PolarGenerationResult(
        request,
        IDENTITY,
        (_point(-0.1), low, _point(0.1)),
        0.01,
    )

    assert result.complete
    assert result.converged_mask == (True, False, True)
    assert result.usable_mask == (True, True, True)


def test_result_rejects_missing_or_reordered_points() -> None:
    request = _request()
    with pytest.raises(ValueError, match="one point"):
        PolarGenerationResult(request, IDENTITY, (_point(-0.1), _point(0.0)), 0.0)
    with pytest.raises(ValueError, match="alpha order"):
        PolarGenerationResult(
            request,
            IDENTITY,
            (_point(0.0), _point(-0.1), _point(0.1)),
            0.0,
        )


def test_point_status_controls_coefficient_presence() -> None:
    with pytest.raises(ValueError, match="requires aerodynamic coefficients"):
        PolarPointResult(0.0, "converged")
    with pytest.raises(ValueError, match="cannot contain coefficients"):
        PolarPointResult(0.0, "not_converged", cl=0.0, cd=0.01, cm=0.0)
    with pytest.raises(ValueError, match="requires a confidence"):
        PolarPointResult(0.0, "low_confidence", cl=0.0, cd=0.01, cm=0.0)
    with pytest.raises(ValueError, match="non-negative integer"):
        PolarPointResult(0.0, "not_converged", iterations=1.5)


def test_provider_metadata_cannot_override_required_provenance() -> None:
    request = _request()
    result = PolarGenerationResult(
        request,
        IDENTITY,
        tuple(_point(alpha) for alpha in request.alpha_rad),
        0.01,
        metadata={"cache_key": "forged", "provider": {"name": "forged"}},
    )

    table = result.to_polar_table()
    assert table.metadata["cache_key"] == result.cache_key
    assert table.metadata["provider"] == IDENTITY.as_mapping()


def test_request_rejects_duplicate_alpha_and_non_integer_iterations() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        _request(alpha_rad=(-0.1, 0.0, 0.0))
    with pytest.raises(ValueError, match="positive integer"):
        _request(max_iterations=10.5)


def test_request_requires_normalized_unit_chord_geometry() -> None:
    unnormalized = replace(
        AIRFOIL,
        coordinates=tuple((2.0 * x, y) for x, y in AIRFOIL.coordinates),
    )
    with pytest.raises(ValueError, match="normalized unit chord"):
        _request(airfoil=unnormalized)


def test_generate_rejects_results_that_contradict_capabilities() -> None:
    class ContradictoryProvider(FakeProvider):
        capabilities = replace(
            CAPABILITIES,
            supports_pointwise_confidence=False,
        )

    with pytest.raises(PolarProviderExecutionError, match="returned confidence"):
        generate_polar(ContradictoryProvider(), _request())


def test_generate_rejects_mismatched_result_identity() -> None:
    class WrongIdentityProvider(FakeProvider):
        def generate(self, request: PolarGenerationRequest) -> PolarGenerationResult:
            return PolarGenerationResult(
                request,
                replace(IDENTITY, backend_version="wrong"),
                tuple(_point(alpha) for alpha in request.alpha_rad),
                0.01,
            )

    with pytest.raises(PolarProviderExecutionError, match="identity"):
        generate_polar(WrongIdentityProvider(), _request())


def test_generate_rejects_partial_result_when_not_declared() -> None:
    class UnexpectedPartialProvider(FakeProvider):
        capabilities = replace(CAPABILITIES, supports_partial_results=False)

        def generate(self, request: PolarGenerationRequest) -> PolarGenerationResult:
            return PolarGenerationResult(
                request,
                self.identity,
                (
                    _point(-0.1),
                    PolarPointResult(0.0, "not_converged"),
                    _point(0.1),
                ),
                0.01,
            )

    with pytest.raises(PolarProviderExecutionError, match="partial results"):
        generate_polar(UnexpectedPartialProvider(), _request())
