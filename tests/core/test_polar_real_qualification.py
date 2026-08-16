"""Real-backend qualification capture and evidence-bundle behavior."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from pyfoldable.core import (
    AirfoilDefinition,
    POLAR_REAL_QUALIFICATION_COMPARISON_SCHEMA_VERSION,
    POLAR_REAL_QUALIFICATION_SCHEMA_VERSION,
    PolarGenerationRequest,
    PolarGenerationResult,
    PolarPointResult,
    ProviderCapabilities,
    ProviderIdentity,
    capture_real_polar_qualification,
    compare_polar_real_qualification_bundles,
    write_polar_real_qualification_comparison,
    write_polar_real_qualification_failure_bundle,
    write_polar_real_qualification_bundle,
)


CAPABILITIES = ProviderCapabilities(
    supports_mach=True,
    supports_n_crit=True,
    supports_forced_transition=True,
    supports_pointwise_confidence=False,
    supports_partial_results=True,
    supports_vectorized_alpha=True,
    supports_iteration_limit=True,
    supports_timeout=True,
)


class CaptureProvider:
    capabilities = CAPABILITIES

    def __init__(
        self,
        identity: ProviderIdentity,
        *,
        cl_offset: float = 0.0,
        no_usable_points: bool = False,
    ) -> None:
        self.identity = identity
        self.cl_offset = cl_offset
        self.no_usable_points = no_usable_points
        self.calls = 0

    def generate(self, request: PolarGenerationRequest) -> PolarGenerationResult:
        self.calls += 1
        points = (
            tuple(
                PolarPointResult(alpha, "not_converged")
                for alpha in request.alpha_rad
            )
            if self.no_usable_points
            else tuple(
                PolarPointResult(
                    alpha,
                    "converged",
                    cl=5.0 * alpha + self.cl_offset,
                    cd=0.01 + alpha * alpha,
                    cm=-0.02,
                )
                for alpha in request.alpha_rad
            )
        )
        return PolarGenerationResult(
            request,
            self.identity,
            points,
            0.01,
            metadata={"nested": {"values": (1, 2)}},
        )


def _request(*, source: str = "unit-test") -> PolarGenerationRequest:
    return PolarGenerationRequest(
        airfoil=AirfoilDefinition(
            "TEST",
            source,
            (
                (1.0, 0.0),
                (0.5, 0.08),
                (0.0, 0.0),
                (0.5, -0.08),
                (1.0, 0.0),
            ),
        ),
        alpha_rad=(-0.1, 0.0, 0.1),
        reynolds=200_000.0,
        scenario_id="capture-test",
    )


def _capture():
    xfoil_identity = ProviderIdentity("xfoil-subprocess", "2", "XFOIL", "6.99")
    neural_identity = ProviderIdentity("neuralfoil", "1", "NeuralFoil", "0.3.3")
    xfoil = CaptureProvider(xfoil_identity)
    neural = CaptureProvider(neural_identity, cl_offset=0.01)
    capture = capture_real_polar_qualification(
        (xfoil, neural),
        _request(),
        expected_providers=(xfoil_identity, neural_identity),
        reference_provider=xfoil_identity,
        case_name="test-real-capture",
        source_revision="0123456789abcdef0123456789abcdef01234567",
        captured_at_utc="2026-08-15T10:00:00Z",
        environment={"python": "test", "packages": {"NeuralFoil": "0.3.3"}},
    )
    return capture, xfoil, neural


def test_capture_requires_exact_backend_identities_before_execution() -> None:
    identity = ProviderIdentity("xfoil-subprocess", "2", "XFOIL", "6.99")
    provider = CaptureProvider(identity)
    wrong = ProviderIdentity("xfoil-subprocess", "2", "XFOIL", "6.996")
    with pytest.raises(ValueError, match="do not match the pinned"):
        capture_real_polar_qualification(
            (provider,),
            _request(),
            expected_providers=(wrong,),
            reference_provider=wrong,
            case_name="mismatch",
            source_revision="0123456789abcdef0123456789abcdef01234567",
            captured_at_utc="2026-08-15T10:00:00Z",
        )
    assert provider.calls == 0


def test_capture_rejects_invalid_provenance_before_execution() -> None:
    identity = ProviderIdentity("xfoil-subprocess", "2", "XFOIL", "6.99")
    provider = CaptureProvider(identity)
    with pytest.raises(ValueError, match="40- or 64-character"):
        capture_real_polar_qualification(
            (provider,),
            _request(),
            expected_providers=(identity,),
            reference_provider=identity,
            case_name="invalid-provenance",
            source_revision="not-a-commit",
            captured_at_utc="2026-08-15T10:00:00Z",
        )
    assert provider.calls == 0


def test_capture_builds_cross_provider_report_from_single_runs() -> None:
    capture, xfoil, neural = _capture()
    assert xfoil.calls == 1
    assert neural.calls == 1
    assert capture.benchmark.passed
    assert tuple(entry.provider for entry in capture.benchmark.entries) == (
        xfoil.identity,
        neural.identity,
    )


def test_bundle_is_hash_manifested_and_explicitly_unreviewed(tmp_path: Path) -> None:
    capture, _, _ = _capture()
    destination = write_polar_real_qualification_bundle(
        capture, tmp_path / "qualification"
    )
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == POLAR_REAL_QUALIFICATION_SCHEMA_VERSION
    assert manifest["review_state"] == "unreviewed"
    assert manifest["promotion_allowed"] is False
    assert manifest["expected_providers"] == manifest["actual_providers"]
    for entry in manifest["files"]:
        payload = (destination / entry["path"]).read_bytes()
        assert len(payload) == entry["size_bytes"]
        assert hashlib.sha256(payload).hexdigest() == entry["sha256"]


def test_bundle_never_overwrites_previous_evidence(tmp_path: Path) -> None:
    capture, _, _ = _capture()
    destination = tmp_path / "qualification"
    write_polar_real_qualification_bundle(capture, destination)
    original = (destination / "manifest.json").read_bytes()
    with pytest.raises(FileExistsError, match="will not be overwritten"):
        write_polar_real_qualification_bundle(capture, destination)
    assert (destination / "manifest.json").read_bytes() == original


def test_provider_failure_is_preserved_as_unreviewed_hashed_evidence(
    tmp_path: Path,
) -> None:
    xfoil_identity = ProviderIdentity("xfoil-subprocess", "2", "XFOIL", "6.99")
    neural_identity = ProviderIdentity("neuralfoil", "1", "NeuralFoil", "0.3.3")
    destination = write_polar_real_qualification_failure_bundle(
        case_name="failed-execution",
        source_revision="0123456789abcdef0123456789abcdef01234567",
        captured_at_utc="2026-08-15T10:00:00Z",
        expected_providers=(xfoil_identity, neural_identity),
        reference_provider=xfoil_identity,
        request=_request(),
        environment={"runner": "test"},
        error=RuntimeError("solver exited with status -8"),
        output_directory=tmp_path / "failure",
    )

    manifest = json.loads((destination / "manifest.json").read_text())
    failure = json.loads((destination / "failure.json").read_text())
    assert manifest["capture_failed"] is True
    assert manifest["benchmark_passed"] is False
    assert manifest["review_state"] == "unreviewed"
    assert manifest["promotion_allowed"] is False
    assert failure["error_type"] == "RuntimeError"
    assert failure["error_message"] == "solver exited with status -8"
    payload = (destination / manifest["files"][0]["path"]).read_bytes()
    assert hashlib.sha256(payload).hexdigest() == manifest["files"][0]["sha256"]


def test_unusable_reference_is_preserved_as_failed_review_evidence(
    tmp_path: Path,
) -> None:
    xfoil_identity = ProviderIdentity("xfoil-subprocess", "2", "XFOIL", "6.99")
    neural_identity = ProviderIdentity("neuralfoil", "1", "NeuralFoil", "0.3.3")
    capture = capture_real_polar_qualification(
        (
            CaptureProvider(xfoil_identity, no_usable_points=True),
            CaptureProvider(neural_identity),
        ),
        _request(),
        expected_providers=(xfoil_identity, neural_identity),
        reference_provider=xfoil_identity,
        case_name="failed-reference",
        source_revision="0123456789abcdef0123456789abcdef01234567",
        captured_at_utc="2026-08-15T10:00:00Z",
    )
    assert not capture.benchmark.passed
    assert all(entry.acceptance is None for entry in capture.benchmark.entries)
    destination = write_polar_real_qualification_bundle(capture, tmp_path / "failed")
    assert len(tuple((destination / "results").glob("*.json"))) == 2


def test_request_fingerprint_ignores_environment_specific_source_path(
    tmp_path: Path,
) -> None:
    template, _, _ = _capture()
    identities = template.expected_providers

    def build(source: str, destination: str) -> str:
        capture = capture_real_polar_qualification(
            (CaptureProvider(identities[0]), CaptureProvider(identities[1])),
            _request(source=source),
            expected_providers=identities,
            reference_provider=identities[0],
            case_name="stable-fingerprint",
            source_revision="0123456789abcdef0123456789abcdef01234567",
            captured_at_utc="2026-08-15T10:00:00Z",
        )
        path = write_polar_real_qualification_bundle(capture, tmp_path / destination)
        return json.loads(
            (path / "manifest.json").read_text(encoding="utf-8")
        )["request_sha256"]

    assert build("/runner/a/NACA0012.dat", "first") == build(
        "C:/runner/b/NACA0012.dat", "second"
    )


def test_bundle_comparison_ignores_only_capture_time_and_elapsed_telemetry(
    tmp_path: Path,
) -> None:
    first_capture, _, _ = _capture()
    identities = first_capture.expected_providers
    second_capture = capture_real_polar_qualification(
        (CaptureProvider(identities[0]), CaptureProvider(identities[1], cl_offset=0.01)),
        _request(source="/different/runner/path.dat"),
        expected_providers=identities,
        reference_provider=identities[0],
        case_name=first_capture.case_name,
        source_revision=first_capture.source_revision,
        captured_at_utc="2026-08-15T11:00:00Z",
        environment=first_capture.environment,
    )
    first = write_polar_real_qualification_bundle(first_capture, tmp_path / "first")
    second = write_polar_real_qualification_bundle(second_capture, tmp_path / "second")

    report = compare_polar_real_qualification_bundles(first, second)

    assert report["schema_version"] == (
        POLAR_REAL_QUALIFICATION_COMPARISON_SCHEMA_VERSION
    )
    assert report["reproducible"] is True, report["differences"]
    assert report["promotion_allowed"] is False
    assert report["differences"] == []
    assert (
        report["first_bundle"]["semantic_sha256"]
        == report["second_bundle"]["semantic_sha256"]
    )


def test_bundle_comparison_reports_physical_result_difference(tmp_path: Path) -> None:
    first_capture, _, _ = _capture()
    identities = first_capture.expected_providers
    changed_capture = capture_real_polar_qualification(
        (CaptureProvider(identities[0]), CaptureProvider(identities[1], cl_offset=0.02)),
        _request(),
        expected_providers=identities,
        reference_provider=identities[0],
        case_name=first_capture.case_name,
        source_revision=first_capture.source_revision,
        captured_at_utc="2026-08-15T11:00:00Z",
        environment=first_capture.environment,
    )
    first = write_polar_real_qualification_bundle(first_capture, tmp_path / "first")
    changed = write_polar_real_qualification_bundle(changed_capture, tmp_path / "changed")

    report = compare_polar_real_qualification_bundles(first, changed)

    assert report["reproducible"] is False
    assert any(".cl:" in difference for difference in report["differences"])


def test_bundle_comparison_rejects_tampered_evidence(tmp_path: Path) -> None:
    capture, _, _ = _capture()
    first = write_polar_real_qualification_bundle(capture, tmp_path / "first")
    second = write_polar_real_qualification_bundle(capture, tmp_path / "second")
    (second / "benchmark.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="size mismatch|hash mismatch"):
        compare_polar_real_qualification_bundles(first, second)


def test_comparison_writer_resolves_single_downloaded_artifact_directory(
    tmp_path: Path,
) -> None:
    capture, _, _ = _capture()
    first = write_polar_real_qualification_bundle(
        capture,
        tmp_path / "download-a" / "artifact-a" / "polar-real-qualification",
    )
    second = write_polar_real_qualification_bundle(
        capture,
        tmp_path / "download-b" / "artifact-b" / "polar-real-qualification",
    )
    destination, report = write_polar_real_qualification_comparison(
        tmp_path / "download-a",
        tmp_path / "download-b",
        tmp_path / "comparison" / "report.json",
    )

    assert destination.is_file()
    assert report["reproducible"] is True
    with pytest.raises(FileExistsError, match="will not be overwritten"):
        write_polar_real_qualification_comparison(
            tmp_path / "download-a",
            tmp_path / "download-b",
            destination,
        )
