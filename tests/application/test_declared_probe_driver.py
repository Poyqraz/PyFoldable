"""Inert execution limits for the declared eight-cell polar probe."""

from __future__ import annotations

import copy
import textwrap
from dataclasses import replace
from pathlib import Path

import pytest

from pyfoldable.application.polar_query_feasibility import (
    PolarQueryFeasibilityError,
    build_polar_query_feasibility,
    run_declared_probe,
)
from pyfoldable.core.models import AirfoilDefinition
from pyfoldable.core.profile_catalog import load_project_airfoil
from pyfoldable.core.providers import (
    PolarGenerationRequest,
    PolarGenerationResult,
    PolarPointResult,
    ProviderIdentity,
)
from pyfoldable.providers.xfoil import XfoilProvider, _build_command_script


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def experiment() -> dict:
    return build_polar_query_feasibility(ROOT)["recommended_experiment"]


@pytest.fixture
def airfoils() -> dict:
    return {airfoil_id: load_project_airfoil(airfoil_id) for airfoil_id in ("NACA0012", "NACA2412")}


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
            mode = os.environ.get("FAKE_XFOIL_MODE", "success")
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
            if mode == "invalid_utf8":
                pathlib.Path("polar.txt").write_bytes(b"alpha CL\n\xff\xfe\n")
                raise SystemExit(0)
            alphas = [
                float(line.split()[1])
                for line in commands.splitlines()
                if line.upper().startswith("ALFA ")
            ]
            if mode == "partial" and len(alphas) > 1:
                alphas.pop(1)
            lines = [
                "XFOIL Version 6.99",
                " alpha      CL        CD       CDp       CM     Top_Xtr  Bot_Xtr",
                " ------  --------  --------  --------  --------  --------  --------",
            ]
            for alpha in alphas:
                lines.append(f"{alpha:8.4f} {0.1 * alpha:9.5f} 0.010000 0.005000 -0.02000 0.8000 0.7000")
            pathlib.Path("polar.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
            if mode == "rewrite_self":
                target = pathlib.Path(sys.argv[0])
                target.write_bytes(target.read_bytes() + b"\n# mutated\n")
            """
        ).lstrip(),
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable


def _provider(executable: Path) -> XfoilProvider:
    return XfoilProvider(executable, backend_version="6.99")


def _complete_without_evidence(request: PolarGenerationRequest) -> PolarGenerationResult:
    points = tuple(
        PolarPointResult(alpha_rad=alpha, status="converged", cl=0.1, cd=0.02, cm=0.0)
        for alpha in request.alpha_rad
    )
    return PolarGenerationResult(
        request=request,
        provider=ProviderIdentity(
            name="xfoil-subprocess",
            adapter_version="2",
            backend_name="XFOIL",
            backend_version="6.99-test",
        ),
        points=points,
        elapsed_s=0.01,
    )


def test_driver_launches_each_declared_cell_once_when_every_cell_is_ready(
    experiment: dict,
    airfoils: dict,
    fake_xfoil: Path,
    tmp_path: Path,
) -> None:
    provider = _provider(fake_xfoil)
    launched: list[PolarGenerationRequest] = []

    def launch(request: PolarGenerationRequest) -> PolarGenerationResult:
        launched.append(request)
        return provider.generate(request, capture_dir=tmp_path / f"cell-{len(launched)}")

    outcome = run_declared_probe(experiment, airfoils, launch)

    assert outcome["launch_count"] == 8
    assert outcome["bem_calls"] == 0
    assert outcome["retries"] == 0
    assert outcome["stop_reason"] is None
    assert outcome["manifest_enforces_execution"] is False
    assert [request.airfoil.id for request in launched] == ["NACA0012"] * 4 + ["NACA2412"] * 4
    assert len({request.cache_key(provider.identity) for request in launched}) == 8
    for request in launched:
        assert request.timeout_s == 90.0
        assert len(request.alpha_rad) == 37
        assert list(request.alpha_rad) == sorted(request.alpha_rad, reverse=True)
        script = _build_command_script(request, {"repanel": True})
        assert all(line.strip().upper() != "INIT" for line in script.splitlines())
        assert sum(line.startswith("ALFA ") for line in script.splitlines()) == 37
    assert all(cell["evidence_ready"] is True and cell["complete"] is True for cell in outcome["cells"])


@pytest.mark.parametrize(
    ("mode", "message"),
    [
        ("partial", None),
        ("sleep", "timeout"),
        ("nonzero", "status 7"),
        ("malformed", "no recognized header"),
        ("invalid_utf8", "UTF-8"),
        ("missing", "did not create polar.txt"),
        ("rewrite_self", "not evidence-ready"),
    ],
)
def test_failed_process_cell_prevents_the_next_launch(
    experiment: dict,
    airfoils: dict,
    fake_xfoil: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    message: str | None,
) -> None:
    monkeypatch.setenv("FAKE_XFOIL_MODE", mode)
    provider = _provider(fake_xfoil)
    launched: list[PolarGenerationRequest] = []

    def launch(request: PolarGenerationRequest) -> PolarGenerationResult:
        launched.append(request)
        probed = request
        if mode == "sleep":
            assert request.timeout_s == 90.0
            probed = PolarGenerationRequest(
                airfoil=request.airfoil,
                alpha_rad=request.alpha_rad,
                reynolds=request.reynolds,
                mach=request.mach,
                n_crit=request.n_crit,
                xtr_upper=request.xtr_upper,
                xtr_lower=request.xtr_lower,
                max_iterations=request.max_iterations,
                timeout_s=0.05,
                scenario_id=request.scenario_id,
                options=dict(request.options),
            )
        return provider.generate(probed, capture_dir=tmp_path / f"cell-{len(launched)}")

    outcome = run_declared_probe(experiment, airfoils, launch)

    assert len(launched) == 1
    assert outcome["launch_count"] == 1
    assert outcome["bem_calls"] == 0
    assert outcome["stop_reason"] is not None
    assert outcome["cells"][0]["evidence_ready"] is False
    if mode == "partial":
        assert outcome["cells"][0]["complete"] is False
        assert outcome["cells"][0]["error"] is None
    else:
        assert message in outcome["cells"][0]["error"]


def test_persistence_failure_and_unexpected_exception_stop_the_probe(
    experiment: dict,
    airfoils: dict,
    fake_xfoil: Path,
    tmp_path: Path,
) -> None:
    provider = _provider(fake_xfoil)
    blocker = tmp_path / "blocked"
    blocker.write_text("not a directory", encoding="utf-8")
    launched: list[str] = []

    def persist(request: PolarGenerationRequest) -> PolarGenerationResult:
        launched.append("persist")
        return provider.generate(request, capture_dir=blocker)

    persisted = run_declared_probe(experiment, airfoils, persist)
    assert launched == ["persist"]
    assert persisted["launch_count"] == 1
    assert "not evidence-complete" in persisted["cells"][0]["error"]

    def explode(request: PolarGenerationRequest) -> PolarGenerationResult:
        launched.append("explode")
        raise RuntimeError("unexpected probe fault")

    exploded = run_declared_probe(experiment, airfoils, explode)
    assert launched == ["persist", "explode"]
    assert exploded["launch_count"] == 1
    assert exploded["cells"][0]["error_type"] == "RuntimeError"
    assert exploded["bem_calls"] == 0


def test_partial_cell_after_ready_cells_does_not_continue(
    experiment: dict,
    airfoils: dict,
    fake_xfoil: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _provider(fake_xfoil)
    launched: list[PolarGenerationRequest] = []

    def launch(request: PolarGenerationRequest) -> PolarGenerationResult:
        launched.append(request)
        if len(launched) == 3:
            monkeypatch.setenv("FAKE_XFOIL_MODE", "partial")
        return provider.generate(request, capture_dir=tmp_path / f"cell-{len(launched)}")

    outcome = run_declared_probe(experiment, airfoils, launch)

    assert len(launched) == 3
    assert outcome["launch_count"] == 3
    assert [cell["evidence_ready"] for cell in outcome["cells"]] == [True, True, False]
    assert outcome["cells"][2]["complete"] is False
    assert outcome["stop_reason"] is not None


def test_complete_output_without_capture_evidence_does_not_continue(
    experiment: dict,
    airfoils: dict,
) -> None:
    launched: list[PolarGenerationRequest] = []

    def launch(request: PolarGenerationRequest) -> PolarGenerationResult:
        launched.append(request)
        return _complete_without_evidence(request)

    outcome = run_declared_probe(experiment, airfoils, launch)

    assert len(launched) == 1
    assert outcome["launch_count"] == 1
    assert outcome["cells"][0]["complete"] is True
    assert outcome["cells"][0]["evidence_ready"] is False
    assert outcome["stop_reason"] is not None


def test_driver_refuses_an_undeclared_ninth_launch_and_an_init_script(
    experiment: dict,
    airfoils: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launched: list[PolarGenerationRequest] = []

    def launch(request: PolarGenerationRequest) -> PolarGenerationResult:
        launched.append(request)
        raise AssertionError("launch must not be called")

    extra = copy.deepcopy(experiment)
    extra["requests"] = [*extra["requests"], extra["requests"][-1]]
    extra["call_limit"] = 9
    with pytest.raises(PolarQueryFeasibilityError, match="eight"):
        run_declared_probe(extra, airfoils, launch)
    assert launched == []

    def init_script(request: PolarGenerationRequest, options: dict) -> str:
        return "INIT\nQUIT\n"

    monkeypatch.setattr(
        "pyfoldable.application.polar_query_feasibility._build_command_script",
        init_script,
    )
    with pytest.raises(PolarQueryFeasibilityError, match="INIT"):
        run_declared_probe(experiment, airfoils, launch)
    assert launched == []


def _declared_provider(experiment: dict) -> ProviderIdentity:
    provider = experiment["provider"]
    return ProviderIdentity(
        name=provider["name"],
        adapter_version=provider["adapter_version"],
        backend_name=provider["backend_name"],
        backend_version=provider["backend_version"],
    )


def _ready_result(
    request: PolarGenerationRequest,
    provider: ProviderIdentity,
    *,
    capture_sha256: str | None = None,
) -> PolarGenerationResult:
    points = tuple(
        PolarPointResult(alpha_rad=alpha, status="converged", cl=0.1, cd=0.02, cm=0.0)
        for alpha in request.alpha_rad
    )
    return PolarGenerationResult(
        request=request,
        provider=provider,
        points=points,
        elapsed_s=0.01,
        metadata={
            "capture_evidence_ready": True,
            "capture_request_sha256": capture_sha256 or request.cache_key(provider),
        },
    )


def _stop_on_second_cell(experiment, airfoils, second):
    declared = _declared_provider(experiment)
    launched: list[PolarGenerationRequest] = []
    first: dict[str, PolarGenerationResult] = {}

    def launch(request: PolarGenerationRequest) -> PolarGenerationResult:
        launched.append(request)
        if len(launched) == 1:
            first["result"] = _ready_result(request, declared)
            return first["result"]
        return second(request, declared, first["result"])

    outcome = run_declared_probe(experiment, airfoils, launch)
    assert len(launched) == 2
    assert outcome["launch_count"] == 2
    assert outcome["stop_reason"]
    cell = outcome["cells"][1]
    assert cell["evidence_ready"] is False
    assert cell["attempted_request_sha256"]
    assert cell["returned_request_sha256"]
    assert cell["identity_mismatch"]
    return outcome, launched, declared


def test_replayed_first_cell_result_does_not_authorize_the_next_cell(
    experiment: dict,
    airfoils: dict,
) -> None:
    outcome, _, declared = _stop_on_second_cell(
        experiment,
        airfoils,
        lambda request, provider, first: first,
    )
    cell = outcome["cells"][1]
    assert cell["attempted_request_sha256"] != cell["returned_request_sha256"]
    assert cell["returned_request_sha256"] == outcome["cells"][0]["attempted_request_sha256"]
    assert declared.backend_version == "6.99"


def test_foreign_profile_and_wrong_condition_do_not_authorize_continuation(
    experiment: dict,
    airfoils: dict,
) -> None:
    foreign = AirfoilDefinition(
        id="FOREIGN",
        source="inert seam",
        coordinates=((1.0, 0.0), (0.0, 0.1), (0.0, -0.1), (1.0, 0.0)),
    )

    def foreign_result(request, provider, first):
        return _ready_result(replace(request, airfoil=foreign), provider)

    outcome, _, _ = _stop_on_second_cell(experiment, airfoils, foreign_result)
    assert outcome["cells"][1]["returned_profile"] == "FOREIGN"
    assert outcome["cells"][1]["attempted_profile"] == "NACA0012"

    def wrong_reynolds(request, provider, first):
        return _ready_result(replace(request, reynolds=request.reynolds + 1.0), provider)

    outcome, _, _ = _stop_on_second_cell(experiment, airfoils, wrong_reynolds)
    assert outcome["cells"][1]["attempted_request_sha256"] != outcome["cells"][1]["returned_request_sha256"]

    def wrong_mach(request, provider, first):
        return _ready_result(replace(request, mach=request.mach + 0.01), provider)

    outcome, _, _ = _stop_on_second_cell(experiment, airfoils, wrong_mach)
    assert "mach" in outcome["cells"][1]["identity_mismatch"] or outcome["cells"][1]["identity_mismatch"]


def test_provider_and_capture_identity_mismatches_stop_the_probe(
    experiment: dict,
    airfoils: dict,
) -> None:
    def wrong_provider(request, provider, first):
        return _ready_result(
            request,
            replace(provider, backend_version="not-the-declared-provider"),
        )

    outcome, _, _ = _stop_on_second_cell(experiment, airfoils, wrong_provider)
    assert outcome["cells"][1]["returned_provider"]["backend_version"] == "not-the-declared-provider"
    assert outcome["cells"][1]["attempted_request_sha256"] == outcome["cells"][1]["returned_request_sha256"]

    def wrong_capture(request, provider, first):
        return _ready_result(request, provider, capture_sha256=first.request.cache_key(provider))

    outcome, _, _ = _stop_on_second_cell(experiment, airfoils, wrong_capture)
    cell = outcome["cells"][1]
    assert cell["capture_request_sha256"] == outcome["cells"][0]["attempted_request_sha256"]
    assert cell["capture_request_sha256"] != cell["attempted_request_sha256"]


def test_driver_does_not_call_the_rotor_solver(
    experiment: dict,
    airfoils: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("BEM was called")

    monkeypatch.setattr(
        "pyfoldable.application.polar_query_feasibility.solve_bem_rotor",
        forbidden,
    )

    def explode(request: PolarGenerationRequest) -> PolarGenerationResult:
        raise RuntimeError("stop before a second cell")

    outcome = run_declared_probe(experiment, airfoils, explode)
    assert outcome["bem_calls"] == 0
    assert outcome["launch_count"] == 1
