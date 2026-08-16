"""Auditable qualification runs against version-pinned real polar backends."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .polar_acceptance import (
    PolarBenchmarkReport,
    PolarGoldenFixture,
    run_polar_provider_benchmark,
)
from .polar_config import PolarFamilyConfig
from .providers import ProviderIdentity


POLAR_BACKEND_QUALIFICATION_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class PolarBackendQualification:
    """One reproducible real-backend benchmark and its immutable inputs."""

    config_sha256: str
    fixture_sha256: tuple[tuple[str, str], ...]
    report: PolarBenchmarkReport

    def __post_init__(self) -> None:
        _validate_digest(self.config_sha256, "config_sha256")
        if not self.fixture_sha256:
            raise ValueError("fixture_sha256 must not be empty.")
        names = tuple(name for name, _ in self.fixture_sha256)
        if len(set(names)) != len(names) or any(not name for name in names):
            raise ValueError("Fixture names must be non-empty and unique.")
        for _, digest in self.fixture_sha256:
            _validate_digest(digest, "fixture digest")
        if not isinstance(self.report, PolarBenchmarkReport):
            raise TypeError("report must be a PolarBenchmarkReport.")
        if set(names) != {entry.fixture_name for entry in self.report.entries}:
            raise ValueError("Fixture digests must cover the benchmark fixtures.")

    @property
    def passed(self) -> bool:
        return self.report.passed

    def as_mapping(self) -> dict[str, object]:
        return {
            "schema_version": POLAR_BACKEND_QUALIFICATION_SCHEMA_VERSION,
            "config_sha256": self.config_sha256,
            "fixture_sha256": tuple(
                {"name": name, "sha256": digest}
                for name, digest in self.fixture_sha256
            ),
            "report": self.report.as_mapping(),
            "passed": self.passed,
        }

    def write_json(self, path: str | Path) -> None:
        """Atomically write the qualification artifact as stable, reviewed JSON."""
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            self.as_mapping(), indent=2, sort_keys=True, allow_nan=False
        ) + "\n"
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", dir=destination.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, destination)
        except BaseException:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise


def qualify_real_polar_backends(
    config: PolarFamilyConfig,
    fixture_paths: Sequence[str | Path],
    *,
    expected_providers: Sequence[ProviderIdentity],
) -> PolarBackendQualification:
    """Run pinned configured backends over reviewed, in-envelope fixtures.

    Unlike adapter-contract tests, this function constructs the actual configured
    providers. Backend discovery therefore happens here and is intentionally allowed
    to fail when XFOIL or NeuralFoil is unavailable.
    """
    if not isinstance(config, PolarFamilyConfig):
        raise TypeError("config must be a PolarFamilyConfig.")
    if not fixture_paths:
        raise ValueError("fixture_paths must not be empty.")

    from .polar_acceptance import load_polar_golden_fixture

    paths = tuple(Path(path).resolve() for path in fixture_paths)
    fixtures = tuple(load_polar_golden_fixture(path) for path in paths)
    _validate_fixture_envelope(config, fixtures)
    runtime = config.build_runtime()
    expected = tuple(expected_providers)
    if not expected or not all(
        isinstance(identity, ProviderIdentity) for identity in expected
    ):
        raise TypeError(
            "expected_providers must contain at least one ProviderIdentity."
        )
    actual = tuple(provider.identity for provider in runtime.providers)
    if actual != expected:
        raise ValueError(
            "Installed provider identities do not match the pinned qualification "
            f"identities; expected={expected!r}, actual={actual!r}."
        )
    report = run_polar_provider_benchmark(
        runtime.providers, fixtures, criteria=config.acceptance_criteria
    )
    digests = tuple(
        (fixture.name, hashlib.sha256(path.read_bytes()).hexdigest())
        for fixture, path in zip(fixtures, paths)
    )
    return PolarBackendQualification(config.source_sha256, digests, report)


def _validate_fixture_envelope(
    config: PolarFamilyConfig, fixtures: Sequence[PolarGoldenFixture]
) -> None:
    plan = config.plan
    allowed_cells = {(request.reynolds, request.mach) for request in plan.requests}
    expected = plan.request_template
    for fixture in fixtures:
        request = fixture.reference.request
        if (
            request.airfoil.id != expected.airfoil.id
            or request.airfoil.coordinates != expected.airfoil.coordinates
        ):
            raise ValueError(
                f"Fixture {fixture.name!r} is outside the configured airfoil geometry."
            )
        if request.scenario_id != expected.scenario_id:
            raise ValueError(
                f"Fixture {fixture.name!r} is outside the configured scenario."
            )
        if request.alpha_rad != expected.alpha_rad:
            raise ValueError(
                f"Fixture {fixture.name!r} does not cover the configured alpha sweep."
            )
        if (request.reynolds, request.mach) not in allowed_cells:
            raise ValueError(
                f"Fixture {fixture.name!r} is outside the configured Re/Mach grid."
            )
        for field_name in (
            "n_crit",
            "xtr_upper",
            "xtr_lower",
            "max_iterations",
            "timeout_s",
        ):
            if getattr(request, field_name) != getattr(expected, field_name):
                raise ValueError(
                    f"Fixture {fixture.name!r} has a different configured "
                    f"{field_name} value."
                )
        if dict(request.options) != dict(expected.options):
            raise ValueError(
                f"Fixture {fixture.name!r} has different configured provider options."
            )


def _validate_digest(value: str, name: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest.")
