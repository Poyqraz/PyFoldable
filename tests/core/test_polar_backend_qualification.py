"""PR-05E real-backend qualification artifact invariants."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from pyfoldable.core import (
    PolarBackendQualification,
    PolarGoldenFixture,
    ProviderCapabilities,
    ProviderIdentity,
    load_polar_family_config,
    load_polar_golden_fixture,
    run_polar_provider_benchmark,
)
from pyfoldable.core.polar_backend_qualification import _validate_fixture_envelope


FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "polar_acceptance"
    / "naca0012_re200k.json"
)
REAL_FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "polar_real_qualification"
    / "naca0012_re200k_real_v1"
    / "golden.json"
)
REAL_CONFIG = (
    Path(__file__).parents[2]
    / "configs"
    / "polars"
    / "NACA0012_RE200K_REAL.toml"
)


class _MatchingProvider:
    identity = ProviderIdentity("real-test", "1", "solver", "6.9.1")
    capabilities = ProviderCapabilities(
        supports_mach=True,
        supports_n_crit=True,
        supports_forced_transition=True,
        supports_pointwise_confidence=False,
        supports_partial_results=True,
        supports_vectorized_alpha=True,
        supports_iteration_limit=True,
        supports_timeout=True,
    )

    def __init__(self, reference):
        self.reference = reference

    def generate(self, request):
        return replace(
            self.reference,
            provider=self.identity,
            elapsed_s=0.01,
        )


def _qualification() -> PolarBackendQualification:
    fixture = load_polar_golden_fixture(FIXTURE)
    report = run_polar_provider_benchmark(
        (_MatchingProvider(fixture.reference),), (fixture,)
    )
    digest = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    return PolarBackendQualification("a" * 64, ((fixture.name, digest),), report)


def test_qualification_writes_stable_auditable_json(tmp_path: Path) -> None:
    qualification = _qualification()
    destination = tmp_path / "nested" / "qualification.json"

    qualification.write_json(destination)

    document = json.loads(destination.read_text(encoding="utf-8"))
    assert document["schema_version"] == 1
    assert document["config_sha256"] == "a" * 64
    assert document["fixture_sha256"][0]["name"] == "naca0012_re200k_clean"
    assert document["report"]["entries"][0]["provider"]["backend_version"] == "6.9.1"
    assert document["passed"] is True


def test_qualification_rejects_missing_or_unmatched_fixture_digests() -> None:
    qualification = _qualification()
    with pytest.raises(ValueError, match="must not be empty"):
        PolarBackendQualification("a" * 64, (), qualification.report)
    with pytest.raises(ValueError, match="must cover"):
        PolarBackendQualification(
            "a" * 64, (("different", "b" * 64),), qualification.report
        )


@pytest.mark.parametrize("digest", ["A" * 64, "short", "z" * 64])
def test_qualification_rejects_noncanonical_digests(digest: str) -> None:
    qualification = _qualification()
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        PolarBackendQualification(
            digest, qualification.fixture_sha256, qualification.report
        )


def test_reviewed_fixture_matches_configured_semantic_airfoil_envelope() -> None:
    config = load_polar_family_config(REAL_CONFIG)
    fixture = load_polar_golden_fixture(REAL_FIXTURE)

    _validate_fixture_envelope(config, (fixture,))


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("n_crit", 8.0),
        ("xtr_upper", 0.9),
        ("xtr_lower", 0.9),
        ("max_iterations", 50),
        ("timeout_s", 31.0),
        ("options", {"changed": True}),
    ],
)
def test_reviewed_fixture_rejects_solver_envelope_drift(
    field_name: str, value: object
) -> None:
    config = load_polar_family_config(REAL_CONFIG)
    fixture = load_polar_golden_fixture(REAL_FIXTURE)
    changed_request = replace(fixture.reference.request, **{field_name: value})
    changed_fixture = PolarGoldenFixture(
        fixture.name,
        replace(fixture.reference, request=changed_request),
    )

    with pytest.raises(ValueError, match=field_name):
        _validate_fixture_envelope(config, (changed_fixture,))
