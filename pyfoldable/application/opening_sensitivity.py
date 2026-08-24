"""Read-only application view of the PR-06D screening matrix."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


class OpeningSensitivityError(ValueError):
    """Raised when the frozen opening-sensitivity report is inconsistent."""


@dataclass(frozen=True)
class OpeningSensitivityRow:
    state_id: str
    angle_from_deployed_deg: float
    effective_diameter_m: float
    projection_factor: float
    static_thrust_ratio_median: float
    static_torque_ratio_median: float
    forward_thrust_ratio_median: float
    forward_torque_ratio_median: float


@dataclass(frozen=True)
class OpeningSensitivitySnapshot:
    qualification: str
    decision: str
    case_count: int
    condition_count: int
    state_count: int
    report_sha256: str
    rows: tuple[OpeningSensitivityRow, ...]


def _document(path: Path) -> Mapping[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OpeningSensitivityError(f"Cannot load opening-sensitivity report: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise OpeningSensitivityError("Opening-sensitivity report root must be an object.")
    return raw


def _count(document: Mapping[str, Any], key: str) -> int:
    value = document.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise OpeningSensitivityError(f"{key} must be a positive integer.")
    return value


def load_opening_sensitivity(
    repo_root: str | Path,
    *,
    report_path: str | Path | None = None,
) -> OpeningSensitivitySnapshot:
    root = Path(repo_root).resolve()
    path = (
        Path(report_path)
        if report_path is not None
        else root / "reports/pr06d_opening_sensitivity.json"
    )
    document = _document(path)

    qualification = document.get("qualification")
    if qualification != "screening_only_until_pr06c_passes":
        raise OpeningSensitivityError(
            "Opening-sensitivity evidence must remain screening-only until PR-06C passes."
        )
    decision = document.get("decision")
    if decision != "pr06d_opening_sensitivity_software_complete_screening_only":
        raise OpeningSensitivityError("Unexpected PR-06D opening-sensitivity decision.")

    case_count = _count(document, "case_count")
    condition_count = _count(document, "condition_count")
    state_count = _count(document, "state_count")
    if case_count != condition_count * state_count:
        raise OpeningSensitivityError("Opening-sensitivity case matrix is incomplete.")

    summaries = document.get("angle_summaries")
    if not isinstance(summaries, list) or len(summaries) != state_count:
        raise OpeningSensitivityError("Angle summaries do not cover every opening state.")

    rows: list[OpeningSensitivityRow] = []
    try:
        for summary in summaries:
            static = summary["regimes"]["static"]
            forward = summary["regimes"]["forward"]
            rows.append(
                OpeningSensitivityRow(
                    state_id=str(summary["state_id"]),
                    angle_from_deployed_deg=float(summary["angle_from_deployed_deg"]),
                    effective_diameter_m=float(summary["effective_diameter_m"]),
                    projection_factor=float(summary["projection_factor"]),
                    static_thrust_ratio_median=float(static["thrust_ratio_median"]),
                    static_torque_ratio_median=float(static["torque_ratio_median"]),
                    forward_thrust_ratio_median=float(forward["thrust_ratio_median"]),
                    forward_torque_ratio_median=float(forward["torque_ratio_median"]),
                )
            )
    except (KeyError, TypeError, ValueError) as exc:
        raise OpeningSensitivityError("Invalid angle summary in opening-sensitivity report.") from exc

    return OpeningSensitivitySnapshot(
        qualification=qualification,
        decision=decision,
        case_count=case_count,
        condition_count=condition_count,
        state_count=state_count,
        report_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        rows=tuple(rows),
    )
