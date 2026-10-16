"""Subprocess boundary tests for the XFOIL provider."""

from __future__ import annotations

import json
import math
import os
import textwrap
from pathlib import Path

import pytest

from pyfoldable import XfoilProvider
from pyfoldable.core import (
    AirfoilDefinition,
    PolarGenerationRequest,
    PolarProviderCapabilityError,
    PolarProviderExecutionError,
    PolarProviderTimeoutError,
    PolarProviderUnavailableError,
    generate_polar,
)


@pytest.fixture
def fake_xfoil(tmp_path: Path) -> Path:
    executable = tmp_path / "fake_xfoil"
    executable.write_text(
        textwrap.dedent(
            r"""
            #!/usr/bin/env python3
            import os
            import pathlib
            import sys
            import time

            commands = sys.stdin.read()
            if commands.strip().upper() == "QUIT":
                print("XFOIL Version 6.99")
                raise SystemExit(0)

            capture = os.environ.get("FAKE_XFOIL_CAPTURE")
            if capture:
                pathlib.Path(capture).write_text(commands, encoding="utf-8")
            airfoil_capture = os.environ.get("FAKE_XFOIL_AIRFOIL_CAPTURE")
            if airfoil_capture:
                source = pathlib.Path("airfoil.dat").read_text(encoding="utf-8")
                pathlib.Path(airfoil_capture).write_text(source, encoding="utf-8")
            cwd_capture = os.environ.get("FAKE_XFOIL_CWD_CAPTURE")
            if cwd_capture:
                pathlib.Path(cwd_capture).write_text(os.getcwd(), encoding="utf-8")

            mode = os.environ.get("FAKE_XFOIL_MODE", "success")
            if "PACC\npolar.txt\n" in commands:
                print(
                    "Sequential READ or WRITE not allowed after EOF marker",
                    file=sys.stderr,
                )
                raise SystemExit(2)
            if mode == "sleep":
                time.sleep(2.0)
            if mode == "nonzero":
                print("simulated solver failure", file=sys.stderr)
                raise SystemExit(7)
            if mode == "missing":
                raise SystemExit(0)
            if mode == "malformed":
                pathlib.Path("polar.txt").write_text("not a polar\n", encoding="utf-8")
                raise SystemExit(0)

            alphas = [
                float(line.split()[1])
                for line in commands.splitlines()
                if line.upper().startswith("ALFA ")
            ]
            if mode == "partial" and len(alphas) > 1:
                alphas.pop(1)
            if mode == "extra":
                alphas.append(77.0)

            lines = [
                "XFOIL Version 6.99",
                " alpha      CL        CD       CDp       CM     Top_Xtr  Bot_Xtr",
                " ------  --------  --------  --------  --------  --------  --------",
            ]
            for alpha in alphas:
                cl = 0.1 * alpha
                cd = 0.01 + 0.0001 * alpha * alpha
                lines.append(
                    f"{alpha:8.4f} {cl:9.5f} {cd:9.6f} 0.005000 -0.02000 0.8000 0.7000"
                )
            pathlib.Path("polar.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
            """
        ).lstrip(),
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable


@pytest.fixture
def polar_request() -> PolarGenerationRequest:
    airfoil = AirfoilDefinition(
        id="TEST 12% foil",
        source="fixture",
        coordinates=(
            (1.0, 0.0),
            (0.5, 0.1),
            (0.0, 0.0),
            (0.5, -0.1),
            (1.0, 0.0),
        ),
    )
    return PolarGenerationRequest(
        airfoil=airfoil,
        alpha_rad=(-0.1, 0.0, 0.1),
        reynolds=120_000.0,
        mach=0.05,
        n_crit=7.0,
        xtr_upper=0.8,
        xtr_lower=0.7,
        max_iterations=80,
        timeout_s=1.0,
        scenario_id="clean",
    )


def _provider(fake_xfoil: Path) -> XfoilProvider:
    return XfoilProvider(fake_xfoil, backend_version="6.99-test")


def test_provider_discovers_version_and_declares_capabilities(fake_xfoil: Path) -> None:
    provider = XfoilProvider(fake_xfoil)

    assert provider.identity.name == "xfoil-subprocess"
    assert provider.identity.backend_name == "XFOIL"
    assert provider.identity.backend_version == "6.99"
    assert provider.capabilities.supports_mach
    assert provider.capabilities.supports_partial_results
    assert not provider.capabilities.supports_pointwise_confidence


def test_provider_rejects_missing_executable(tmp_path: Path) -> None:
    with pytest.raises(PolarProviderUnavailableError, match="was not found"):
        XfoilProvider(tmp_path / "does-not-exist")


def test_successful_run_builds_commands_and_cleans_workspace(
    fake_xfoil: Path,
    polar_request: PolarGenerationRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command_capture = tmp_path / "commands.txt"
    airfoil_capture = tmp_path / "airfoil.txt"
    cwd_capture = tmp_path / "cwd.txt"
    monkeypatch.setenv("FAKE_XFOIL_CAPTURE", str(command_capture))
    monkeypatch.setenv("FAKE_XFOIL_AIRFOIL_CAPTURE", str(airfoil_capture))
    monkeypatch.setenv("FAKE_XFOIL_CWD_CAPTURE", str(cwd_capture))

    result = generate_polar(_provider(fake_xfoil), polar_request)

    assert result.complete
    assert result.converged_mask == (True, True, True)
    assert result.to_polar_table().alpha_rad == polar_request.alpha_rad
    assert result.metadata["polar_row_count"] == 3
    assert result.metadata["repanel"] is True
    assert all(point.confidence is None for point in result.points)

    commands = command_capture.read_text(encoding="utf-8")
    assert "LOAD airfoil.dat" in commands
    assert "PANE" in commands
    assert "TYPE 1" in commands
    assert "VISC 120000" in commands
    assert "MACH 0.05" in commands
    assert "N 7" in commands
    assert "XTR 0.8 0.7" in commands
    assert "ITER 80" in commands
    assert "PACC\n\n\n" in commands
    assert "PACC\nPWRT 1\npolar.txt\n\nQUIT\n" in commands
    assert "PACC\npolar.txt\n" not in commands
    assert commands.index("ALFA -5.729") < commands.index("ALFA 0")
    assert commands.index("ALFA 0") < commands.index("ALFA 5.729")

    airfoil = airfoil_capture.read_text(encoding="utf-8")
    assert airfoil.startswith("_PyFoldable_TEST_12_foil\n")
    assert "0 0" in airfoil
    assert not Path(cwd_capture.read_text(encoding="utf-8")).exists()


def test_provider_identity_versions_deferred_polar_write(fake_xfoil: Path) -> None:
    provider = _provider(fake_xfoil)

    assert provider.identity.adapter_version == "2"


def test_missing_row_becomes_explicit_partial_result(
    fake_xfoil: Path,
    polar_request: PolarGenerationRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FAKE_XFOIL_MODE", "partial")

    result = generate_polar(_provider(fake_xfoil), polar_request)

    assert result.converged_mask == (True, False, True)
    assert result.points[1].status == "not_converged"
    assert result.points[1].cl is None
    assert result.warnings == ("XFOIL did not converge at 1 requested angle(s).",)


def test_descending_request_order_is_preserved(
    fake_xfoil: Path,
    polar_request: PolarGenerationRequest,
) -> None:
    descending = PolarGenerationRequest(
        airfoil=polar_request.airfoil,
        alpha_rad=tuple(reversed(polar_request.alpha_rad)),
        reynolds=polar_request.reynolds,
    )

    result = generate_polar(_provider(fake_xfoil), descending)

    assert tuple(point.alpha_rad for point in result.points) == descending.alpha_rad
    assert result.to_polar_table().alpha_rad == tuple(sorted(descending.alpha_rad))


def test_unmatched_polar_rows_are_reported(
    fake_xfoil: Path,
    polar_request: PolarGenerationRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FAKE_XFOIL_MODE", "extra")

    result = generate_polar(_provider(fake_xfoil), polar_request)

    assert result.complete
    assert result.warnings == ("Ignored 1 unmatched XFOIL polar row(s).",)


def test_provider_options_are_strict_and_can_disable_repaneling(
    fake_xfoil: Path,
    polar_request: PolarGenerationRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command_capture = tmp_path / "commands.txt"
    monkeypatch.setenv("FAKE_XFOIL_CAPTURE", str(command_capture))
    without_repanel = PolarGenerationRequest(
        airfoil=polar_request.airfoil,
        alpha_rad=polar_request.alpha_rad,
        reynolds=polar_request.reynolds,
        options={"repanel": False},
    )

    result = generate_polar(_provider(fake_xfoil), without_repanel)

    assert result.metadata["repanel"] is False
    assert "PANE" not in command_capture.read_text(encoding="utf-8")

    unsupported = PolarGenerationRequest(
        airfoil=polar_request.airfoil,
        alpha_rad=polar_request.alpha_rad,
        reynolds=polar_request.reynolds,
        options={"silent_ignore": True},
    )
    with pytest.raises(PolarProviderCapabilityError, match="silent_ignore"):
        generate_polar(_provider(fake_xfoil), unsupported)


def test_timeout_uses_typed_error(
    fake_xfoil: Path,
    polar_request: PolarGenerationRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FAKE_XFOIL_MODE", "sleep")
    short_request = PolarGenerationRequest(
        airfoil=polar_request.airfoil,
        alpha_rad=polar_request.alpha_rad,
        reynolds=polar_request.reynolds,
        timeout_s=0.05,
    )

    with pytest.raises(PolarProviderTimeoutError, match="0.05 s"):
        generate_polar(_provider(fake_xfoil), short_request)


def test_nonzero_exit_includes_diagnostics(
    fake_xfoil: Path,
    polar_request: PolarGenerationRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FAKE_XFOIL_MODE", "nonzero")

    with pytest.raises(
        PolarProviderExecutionError,
        match="status 7.*simulated solver failure",
    ):
        generate_polar(_provider(fake_xfoil), polar_request)


@pytest.mark.parametrize(
    ("mode", "message"),
    [
        ("missing", "did not create polar.txt"),
        ("malformed", "no recognized header"),
    ],
)
def test_missing_or_malformed_polar_is_rejected(
    fake_xfoil: Path,
    polar_request: PolarGenerationRequest,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    message: str,
) -> None:
    monkeypatch.setenv("FAKE_XFOIL_MODE", mode)

    with pytest.raises(PolarProviderExecutionError, match=message):
        generate_polar(_provider(fake_xfoil), polar_request)


def _capture(tmp_path: Path, name: str) -> Path:
    return tmp_path / name


def test_capture_survives_cleanup_for_success_and_nonconvergence(
    fake_xfoil: Path,
    polar_request: PolarGenerationRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _provider(fake_xfoil)
    success_dir = _capture(tmp_path, "success")
    result = provider.generate(polar_request, capture_dir=success_dir)
    receipt = json.loads((success_dir / "capture.json").read_text(encoding="utf-8"))
    assert result.complete
    assert not Path(receipt["executable"]["path"]).is_relative_to(success_dir)
    assert receipt["request_cache_key"] == polar_request.cache_key(provider.identity)
    assert receipt["coordinate_sha256"]
    assert receipt["script_sha256"] == __import__("hashlib").sha256((success_dir / "script.txt").read_bytes()).hexdigest()
    assert receipt["declared_build_policy"]["ubuntu_dfsg_package_allowed"] is False
    assert receipt["executable"]["sha256"]
    assert receipt["polar_file"]["status"] == "present"
    assert receipt["points"][0]["status"] == "converged"
    assert receipt["solver_success"] is True
    assert "ALFA" in (success_dir / "script.txt").read_text(encoding="utf-8")

    monkeypatch.setenv("FAKE_XFOIL_MODE", "partial")
    partial_dir = _capture(tmp_path, "partial")
    partial = provider.generate(polar_request, capture_dir=partial_dir)
    partial_receipt = json.loads((partial_dir / "capture.json").read_text(encoding="utf-8"))
    assert partial.points[1].status == "not_converged"
    assert partial_receipt["points"][1]["status"] == "not_converged"
    assert partial_receipt["points"][1]["cl"] is None
    assert partial_receipt["solver_success"] is False
    assert partial_receipt["polar_parsed"] is True


def test_capture_does_not_invent_points_for_timeout_exit_or_malformed_output(
    fake_xfoil: Path,
    polar_request: PolarGenerationRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _provider(fake_xfoil)
    monkeypatch.setenv("FAKE_XFOIL_MODE", "sleep")
    timeout_request = PolarGenerationRequest(
        airfoil=polar_request.airfoil,
        alpha_rad=polar_request.alpha_rad,
        reynolds=polar_request.reynolds,
        timeout_s=0.05,
    )
    timeout_dir = _capture(tmp_path, "timeout")
    with pytest.raises(PolarProviderTimeoutError):
        provider.generate(timeout_request, capture_dir=timeout_dir)
    timeout_receipt = json.loads((timeout_dir / "capture.json").read_text(encoding="utf-8"))
    assert timeout_receipt["process_status"] == "timeout"
    assert timeout_receipt["polar_file"]["status"] == "unavailable"
    assert {point["status"] for point in timeout_receipt["points"]} == {"unavailable"}
    assert all(point["cl"] is None for point in timeout_receipt["points"])
    assert timeout_receipt["stdout"]["status"] in {"empty", "partial", "unavailable"}
    assert timeout_receipt["solver_success"] is False

    monkeypatch.setenv("FAKE_XFOIL_MODE", "nonzero")
    exit_dir = _capture(tmp_path, "nonzero")
    with pytest.raises(PolarProviderExecutionError, match="status 7"):
        provider.generate(polar_request, capture_dir=exit_dir)
    exit_receipt = json.loads((exit_dir / "capture.json").read_text(encoding="utf-8"))
    assert exit_receipt["returncode"] == 7
    assert exit_receipt["polar_file"]["status"] == "unavailable"
    assert {point["status"] for point in exit_receipt["points"]} == {"unavailable"}

    monkeypatch.setenv("FAKE_XFOIL_MODE", "malformed")
    malformed_dir = _capture(tmp_path, "malformed")
    with pytest.raises(PolarProviderExecutionError, match="no recognized header"):
        provider.generate(polar_request, capture_dir=malformed_dir)
    malformed = json.loads((malformed_dir / "capture.json").read_text(encoding="utf-8"))
    assert malformed["polar_file"]["status"] == "present"
    assert malformed["polar_parsed"] is False
    assert {point["status"] for point in malformed["points"]} == {"unavailable"}
    assert "not_converged" not in json.dumps(malformed["points"])


def test_capture_persistence_failure_is_not_a_success(
    fake_xfoil: Path,
    polar_request: PolarGenerationRequest,
    tmp_path: Path,
) -> None:
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("blocked", encoding="utf-8")
    with pytest.raises(PolarProviderExecutionError, match="not evidence-complete"):
        _provider(fake_xfoil).generate(polar_request, capture_dir=blocker)


def test_coefficients_are_mapped_from_degrees(
    fake_xfoil: Path,
    polar_request: PolarGenerationRequest,
) -> None:
    result = generate_polar(_provider(fake_xfoil), polar_request)

    assert result.points[0].cl == pytest.approx(0.1 * math.degrees(-0.1), abs=1.0e-5)
    assert result.points[2].cd == pytest.approx(
        0.01 + 0.0001 * math.degrees(0.1) ** 2,
        abs=1.0e-6,
    )
