"""Allow-listed, session-only analysis execution for the UI-04 workspace."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from pyfoldable.core import (
    BEMAnnulusSettings,
    BEMRotorSettings,
    FoldableRotorState,
    assess_foldable_opening_sensitivity,
    build_rotor_benchmark_proxy_polar_family,
    load_rotor_benchmark_fixture,
)

from .opening_sensitivity import OpeningSensitivityRow, load_opening_sensitivity


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PR06D_ANALYSIS_ID = "pr06d_opening_sensitivity_v1"
ANALYSIS_SERVICE_ID = "pyfoldable.application.analysis_run"
ANALYSIS_SERVICE_VERSION = 1
SESSION_ARTIFACT_CLASS = "session_screening_computation"
SCREENING_QUALIFICATION = "screening_only_until_pr06c_passes"
PR06D_ANGLES_DEG = (0, 15, 30, 45, 60)
PR06D_HINGE_RADIUS_RATIO = 0.75
PR06D_RADIAL_DOMAIN = "station_span"
PR06D_INCLUDE_TIP_LOSS = True
PR06D_INCLUDE_ROOT_LOSS = False
PR06D_LOADING_BRANCH = "signed_nonreversed"
PR06D_POLAR_BUILDER_ID = "build_rotor_benchmark_proxy_polar_family:v1"
PR06D_ANNULUS_COUNT = 80
DEFAULT_PR06D_FIXTURE = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "rotor_benchmark"
    / "uiuc_apcsf_10x4.7_v1.json"
)
DEFAULT_PR06D_ARCHIVE = PROJECT_ROOT / "reports/pr06d_opening_sensitivity.json"


class AnalysisRunError(ValueError):
    """Raised when a UI analysis request or its result violates the recipe."""


@dataclass(frozen=True)
class AnalysisRecipe:
    id: str
    title: str
    artifact_class: str
    fixture_path: Path
    fixture_sha256: str
    archived_report_path: Path
    archived_report_sha256: str
    expected_case_count: int
    expected_condition_count: int
    expected_state_count: int
    annulus_count: int
    angles_deg: tuple[int, ...]
    hinge_radius_ratio: float
    radial_domain: str
    include_tip_loss: bool
    include_root_loss: bool
    loading_branch: str
    polar_builder_id: str
    polar_representative: bool
    policy_sha256: str
    archived_rows: tuple[OpeningSensitivityRow, ...]


@dataclass(frozen=True)
class AnalysisRunArtifact:
    analysis_id: str
    service_id: str
    service_version: int
    artifact_class: str
    qualification: str
    physical_qualification: bool
    fixture_id: str
    fixture_path: Path
    fixture_sha256: str
    archived_report_path: Path
    archived_report_sha256: str
    matches_archived_report: bool
    request_sha256: str
    policy_sha256: str
    report_sha256: str
    report_json: str
    manifest_sha256: str
    manifest_json: str
    filename: str
    case_count: int
    condition_count: int
    state_count: int
    annulus_count: int
    duration_seconds: float
    rows: tuple[OpeningSensitivityRow, ...]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(document: Mapping[str, Any]) -> str:
    payload = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _policy_document() -> dict[str, Any]:
    return {
        "angles_deg": list(PR06D_ANGLES_DEG),
        "annulus_count": PR06D_ANNULUS_COUNT,
        "hinge_radius_ratio": PR06D_HINGE_RADIUS_RATIO,
        "include_root_loss": PR06D_INCLUDE_ROOT_LOSS,
        "include_tip_loss": PR06D_INCLUDE_TIP_LOSS,
        "loading_branch": PR06D_LOADING_BRANCH,
        "polar_builder_id": PR06D_POLAR_BUILDER_ID,
        "polar_evidence_class": "analytic_proxy",
        "polar_representative": False,
        "radial_domain": PR06D_RADIAL_DOMAIN,
    }


def _repository_file(root: Path, relative: str, *, field: str) -> Path:
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise AnalysisRunError(f"{field} must remain inside the repository.") from exc
    if not path.is_file():
        raise AnalysisRunError(f"{field} does not exist: {relative}")
    return path


def get_analysis_recipe(
    repo_root: str | Path,
    analysis_id: str = PR06D_ANALYSIS_ID,
) -> AnalysisRecipe:
    """Resolve one fixed recipe without accepting paths or executable commands."""
    if analysis_id != PR06D_ANALYSIS_ID:
        raise AnalysisRunError(f"Analysis id {analysis_id!r} is not allow-listed.")
    root = Path(repo_root).resolve()
    fixture = _repository_file(
        root,
        "tests/fixtures/rotor_benchmark/uiuc_apcsf_10x4.7_v1.json",
        field="fixture",
    )
    archive = _repository_file(
        root,
        "reports/pr06d_opening_sensitivity.json",
        field="archived report",
    )
    fixture_sha256 = _sha256(fixture)
    archived_report_sha256 = _sha256(archive)
    try:
        fixture_document = load_rotor_benchmark_fixture(fixture)
        archived_snapshot = load_opening_sensitivity(root, report_path=archive)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise AnalysisRunError(f"Allow-listed analysis assets are invalid: {exc}") from exc
    if fixture_document.source_sha256 != fixture_sha256:
        raise AnalysisRunError("Allow-listed fixture changed while resolving the recipe.")
    if archived_snapshot.report_sha256 != archived_report_sha256:
        raise AnalysisRunError("Archived report changed while resolving the recipe.")
    policy = _policy_document()
    return AnalysisRecipe(
        id=analysis_id,
        title="PR-06D · 254 mm APC açılma duyarlılığı",
        artifact_class=SESSION_ARTIFACT_CLASS,
        fixture_path=fixture,
        fixture_sha256=fixture_sha256,
        archived_report_path=archive,
        archived_report_sha256=archived_report_sha256,
        expected_case_count=250,
        expected_condition_count=50,
        expected_state_count=5,
        annulus_count=PR06D_ANNULUS_COUNT,
        angles_deg=PR06D_ANGLES_DEG,
        hinge_radius_ratio=PR06D_HINGE_RADIUS_RATIO,
        radial_domain=PR06D_RADIAL_DOMAIN,
        include_tip_loss=PR06D_INCLUDE_TIP_LOSS,
        include_root_loss=PR06D_INCLUDE_ROOT_LOSS,
        loading_branch=PR06D_LOADING_BRANCH,
        polar_builder_id=PR06D_POLAR_BUILDER_ID,
        polar_representative=False,
        policy_sha256=_canonical_sha256(policy),
        archived_rows=archived_snapshot.rows,
    )


def build_pr06d_opening_sensitivity_report(
    fixture_path: Path = DEFAULT_PR06D_FIXTURE,
    *,
    provenance_root: Path = PROJECT_ROOT,
) -> Mapping[str, Any]:
    """Build the exact report consumed by both the CLI and the UI-04 service."""
    fixture = load_rotor_benchmark_fixture(fixture_path)
    family = build_rotor_benchmark_proxy_polar_family()
    blade = fixture.blade(family.airfoil_id)
    angles_deg = PR06D_ANGLES_DEG
    states = tuple(
        FoldableRotorState(
            id=f"fold-{angle_deg:02d}deg",
            hinge_radius_m=PR06D_HINGE_RADIUS_RATIO * blade.radius_m,
            opening_angle_rad=math.radians(-angle_deg),
            deployed_angle_rad=0.0,
        )
        for angle_deg in angles_deg
    )
    settings = BEMRotorSettings(
        annulus_count=PR06D_ANNULUS_COUNT,
        radial_domain=PR06D_RADIAL_DOMAIN,
        annulus_settings=BEMAnnulusSettings(
            include_tip_loss=PR06D_INCLUDE_TIP_LOSS,
            include_root_loss=PR06D_INCLUDE_ROOT_LOSS,
            loading_branch=PR06D_LOADING_BRANCH,
        ),
    )
    evidence = assess_foldable_opening_sensitivity(
        blade,
        states,
        tuple(fixture.condition(point) for point in fixture.eligible_points),
        {family.airfoil_id: family},
        settings=settings,
    )
    point_regimes = {point.id: point.regime for point in fixture.eligible_points}
    summaries = []
    for state, angle_deg in zip(states, angles_deg):
        state_cases = [case for case in evidence.cases if case.state_id == state.id]
        regime_summaries = {}
        for regime in ("static", "forward"):
            ratios = [
                case.thrust_ratio_to_deployed
                for case in state_cases
                if point_regimes[case.condition_id] == regime
            ]
            torque_ratios = [
                case.torque_ratio_to_deployed
                for case in state_cases
                if point_regimes[case.condition_id] == regime
            ]
            regime_summaries[regime] = {
                "point_count": len(ratios),
                "thrust_ratio_median": statistics.median(ratios),
                "thrust_ratio_minimum": min(ratios),
                "thrust_ratio_maximum": max(ratios),
                "torque_ratio_median": statistics.median(torque_ratios),
            }
        summaries.append(
            {
                "state_id": state.id,
                "angle_from_deployed_deg": -float(angle_deg),
                "projection_factor": state_cases[0].projection_factor,
                "effective_diameter_m": state_cases[0].effective_diameter_m,
                "regimes": regime_summaries,
            }
        )
    return {
        **dict(evidence.as_mapping()),
        "benchmark_id": "pr06d-uiuc-apcsf-10x4.7-opening-screen-v1",
        "fixture": {
            "id": fixture.id,
            "path": str(fixture_path.resolve().relative_to(provenance_root.resolve())),
            "sha256": fixture.source_sha256,
            "qualification_point_count": len(fixture.eligible_points),
        },
        "solver": {
            "annulus_count": settings.annulus_count,
            "radial_domain": settings.radial_domain,
            "loading_branch": settings.annulus_settings.loading_branch,
        },
        "polar_evidence": {
            "airfoil_id": family.airfoil_id,
            "evidence_class": "analytic_proxy",
            "representative": False,
        },
        "angle_summaries": summaries,
        "decision": "pr06d_opening_sensitivity_software_complete_screening_only",
        "scope": (
            "Geometry/solver sensitivity only. Folded-state physical accuracy remains "
            "blocked by PR-06C and these ratios must not drive a final design decision."
        ),
    }


def render_pr06d_opening_sensitivity_markdown(report: Mapping[str, Any]) -> str:
    rows = "\n".join(
        "| {angle:.0f} | {factor:.4f} | {diameter:.4f} | {static:.3f} | "
        "{forward:.3f} | {torque:.3f} |".format(
            angle=summary["angle_from_deployed_deg"],
            factor=summary["projection_factor"],
            diameter=summary["effective_diameter_m"],
            static=summary["regimes"]["static"]["thrust_ratio_median"],
            forward=summary["regimes"]["forward"]["thrust_ratio_median"],
            torque=summary["regimes"]["static"]["torque_ratio_median"],
        )
        for summary in report["angle_summaries"]
    )
    table_header = (
        "| fold angle (deg) | radial projection | effective D (m) | "
        "median static T/T0 | median forward T/T0 | median static Q/Q0 |"
    )
    fixture_line = (
        f"- Fixture: `{report['fixture']['id']}` "
        f"({report['fixture']['qualification_point_count']} points)"
    )
    annuli_line = (
        f"- Annuli: {report['solver']['annulus_count']}; loading branch: "
        f"`{report['solver']['loading_branch']}`"
    )
    return f"""# PR-06D opening-angle sensitivity

## Decision

**Software sweep complete; physical qualification remains blocked.** The exact deployed
endpoint matches the fixed path over all {report['condition_count']} frozen propulsive
points, and {report['state_count']} ordered opening states produced a complete
{report['case_count']}-case grid.

{table_header}
| ---: | ---: | ---: | ---: | ---: | ---: |
{rows}

## Evidence boundary

{fixture_line}
{annuli_line}
- Polar: analytic proxy, explicitly non-representative
- Qualification: `{report['qualification']}`
- Physical qualification: `false`

{report['scope']}
"""


def _positive_integer(report: Mapping[str, Any], field: str) -> int:
    value = report.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise AnalysisRunError(f"{field} must be a positive integer.")
    return value


def _validate_report(report: Mapping[str, Any], recipe: AnalysisRecipe) -> None:
    if report.get("qualification") != SCREENING_QUALIFICATION:
        raise AnalysisRunError("Analysis output must remain screening-only.")
    if report.get("physical_qualification") is not False:
        raise AnalysisRunError("Analysis output cannot claim physical qualification.")
    case_count = _positive_integer(report, "case_count")
    condition_count = _positive_integer(report, "condition_count")
    state_count = _positive_integer(report, "state_count")
    if case_count != condition_count * state_count:
        raise AnalysisRunError("Analysis case matrix is incomplete.")
    if (
        case_count != recipe.expected_case_count
        or condition_count != recipe.expected_condition_count
        or state_count != recipe.expected_state_count
    ):
        raise AnalysisRunError("Analysis case matrix violates the fixed recipe limits.")

    fixture = report.get("fixture")
    if not isinstance(fixture, Mapping) or fixture.get("sha256") != recipe.fixture_sha256:
        raise AnalysisRunError("Analysis fixture SHA-256 does not match the allow-listed input.")
    solver = report.get("solver")
    if not isinstance(solver, Mapping) or solver.get("annulus_count") != recipe.annulus_count:
        raise AnalysisRunError("Analysis annulus_count violates the fixed resource policy.")
    if (
        solver.get("radial_domain") != recipe.radial_domain
        or solver.get("loading_branch") != recipe.loading_branch
    ):
        raise AnalysisRunError("Analysis solver settings violate the fixed resource policy.")
    polar = report.get("polar_evidence")
    if not isinstance(polar, Mapping) or (
        polar.get("evidence_class") != "analytic_proxy"
        or polar.get("representative") is not False
    ):
        raise AnalysisRunError("Analysis must use the non-representative analytic proxy.")


def run_analysis(
    repo_root: str | Path,
    analysis_id: str = PR06D_ANALYSIS_ID,
) -> AnalysisRunArtifact:
    """Run one bounded recipe in memory and require exact archived equivalence."""
    recipe = get_analysis_recipe(repo_root, analysis_id)
    root = Path(repo_root).resolve()
    started = time.perf_counter()
    try:
        raw_report = build_pr06d_opening_sensitivity_report(
            recipe.fixture_path,
            provenance_root=root,
        )
    except AnalysisRunError:
        raise
    except (OSError, RuntimeError, TypeError, ValueError, ArithmeticError) as exc:
        raise AnalysisRunError(f"Analysis core failed: {exc}") from exc
    if not isinstance(raw_report, Mapping):
        raise AnalysisRunError("Analysis service returned a non-object report.")
    report = dict(raw_report)
    _validate_report(report, recipe)
    try:
        report_json = json.dumps(
            report,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ) + "\n"
    except (TypeError, ValueError) as exc:
        raise AnalysisRunError("Analysis report must contain finite JSON values.") from exc

    try:
        archived_bytes = recipe.archived_report_path.read_bytes()
        archived_text = archived_bytes.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise AnalysisRunError(f"Cannot read archived report: {exc}") from exc
    actual_archive_sha256 = hashlib.sha256(archived_bytes).hexdigest()
    if actual_archive_sha256 != recipe.archived_report_sha256:
        raise AnalysisRunError("Archived report changed during the analysis request.")
    try:
        archived_report = json.loads(
            archived_text,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON constant {value}")
            ),
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise AnalysisRunError(f"Archived report is invalid: {exc}") from exc
    if report != archived_report or report_json.encode("utf-8") != archived_bytes:
        raise AnalysisRunError(
            "Session computation does not match the versioned archived report."
        )

    request_document = {
        "analysis_id": recipe.id,
        "service_id": ANALYSIS_SERVICE_ID,
        "service_version": ANALYSIS_SERVICE_VERSION,
        "fixture_sha256": recipe.fixture_sha256,
        "archived_report_sha256": actual_archive_sha256,
        "policy_sha256": recipe.policy_sha256,
    }
    request_sha256 = _canonical_sha256(request_document)
    fixture = report["fixture"]
    report_sha256 = hashlib.sha256(report_json.encode("utf-8")).hexdigest()
    fixture_relative_path = str(recipe.fixture_path.relative_to(root))
    archive_relative_path = str(recipe.archived_report_path.relative_to(root))
    manifest = {
        "schema_version": 1,
        "artifact_class": recipe.artifact_class,
        "analysis": {
            "id": recipe.id,
            "service_id": ANALYSIS_SERVICE_ID,
            "service_version": ANALYSIS_SERVICE_VERSION,
            "request_sha256": request_sha256,
            "policy_sha256": recipe.policy_sha256,
            "policy": _policy_document(),
        },
        "qualification": SCREENING_QUALIFICATION,
        "physical_qualification": False,
        "fixture": {
            "id": str(fixture["id"]),
            "path": fixture_relative_path,
            "sha256": recipe.fixture_sha256,
        },
        "archived_report": {
            "path": archive_relative_path,
            "sha256": actual_archive_sha256,
            "matches": True,
        },
        "session_report": {
            "sha256": report_sha256,
            "content": report,
        },
    }
    manifest_json = json.dumps(
        manifest,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    return AnalysisRunArtifact(
        analysis_id=recipe.id,
        service_id=ANALYSIS_SERVICE_ID,
        service_version=ANALYSIS_SERVICE_VERSION,
        artifact_class=recipe.artifact_class,
        qualification=SCREENING_QUALIFICATION,
        physical_qualification=False,
        fixture_id=str(fixture["id"]),
        fixture_path=recipe.fixture_path,
        fixture_sha256=recipe.fixture_sha256,
        archived_report_path=recipe.archived_report_path,
        archived_report_sha256=actual_archive_sha256,
        matches_archived_report=True,
        request_sha256=request_sha256,
        policy_sha256=recipe.policy_sha256,
        report_sha256=report_sha256,
        report_json=report_json,
        manifest_sha256=hashlib.sha256(manifest_json.encode("utf-8")).hexdigest(),
        manifest_json=manifest_json,
        filename="pr06d_opening_sensitivity_session_manifest.json",
        case_count=int(report["case_count"]),
        condition_count=int(report["condition_count"]),
        state_count=int(report["state_count"]),
        annulus_count=recipe.annulus_count,
        duration_seconds=time.perf_counter() - started,
        rows=recipe.archived_rows,
    )
