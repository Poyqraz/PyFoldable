"""Read-only application view of the PR-06D screening matrix."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
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


def _document(path: Path) -> tuple[Mapping[str, Any], str]:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant {value}")

    try:
        source = path.read_bytes()
        raw = json.loads(
            source,
            parse_constant=reject_constant,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise OpeningSensitivityError(f"Cannot load opening-sensitivity report: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise OpeningSensitivityError("Opening-sensitivity report root must be an object.")
    return raw, hashlib.sha256(source).hexdigest()


def _count(document: Mapping[str, Any], key: str) -> int:
    value = document.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise OpeningSensitivityError(f"{key} must be a positive integer.")
    return value


def _finite(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OpeningSensitivityError(f"{field} must be numeric.")
    number = float(value)
    if not math.isfinite(number):
        raise OpeningSensitivityError(f"{field} must be finite.")
    return number


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
    document, report_sha256 = _document(path)

    qualification = document.get("qualification")
    if qualification != "screening_only_until_pr06c_passes":
        raise OpeningSensitivityError(
            "Opening-sensitivity evidence must remain screening-only until PR-06C passes."
        )
    decision = document.get("decision")
    if decision != "pr06d_opening_sensitivity_software_complete_screening_only":
        raise OpeningSensitivityError("Unexpected PR-06D opening-sensitivity decision.")
    if document.get("physical_qualification") is not False:
        raise OpeningSensitivityError(
            "Opening-sensitivity evidence cannot claim physical qualification."
        )
    polar_evidence = document.get("polar_evidence")
    if not isinstance(polar_evidence, Mapping) or (
        polar_evidence.get("evidence_class") != "analytic_proxy"
        or polar_evidence.get("representative") is not False
    ):
        raise OpeningSensitivityError(
            "Opening-sensitivity evidence must use a non-representative analytic proxy."
        )
    if document.get("deployed_endpoint_exact") is not True:
        raise OpeningSensitivityError("The deployed endpoint equivalence must be exact.")

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
        for index, summary in enumerate(summaries):
            if not isinstance(summary, Mapping):
                raise TypeError
            static = summary["regimes"]["static"]
            forward = summary["regimes"]["forward"]
            if not isinstance(static, Mapping) or not isinstance(forward, Mapping):
                raise TypeError
            for regime_name, regime_values in (("static", static), ("forward", forward)):
                point_count = regime_values.get("point_count")
                if (
                    isinstance(point_count, bool)
                    or not isinstance(point_count, int)
                    or point_count < 1
                ):
                    raise ValueError
                for field in (
                    "thrust_ratio_median",
                    "thrust_ratio_minimum",
                    "thrust_ratio_maximum",
                    "torque_ratio_median",
                ):
                    _finite(
                        regime_values[field],
                        f"angle_summaries[{index}].{regime_name}.{field}",
                    )
            state_id_value = summary["state_id"]
            if not isinstance(state_id_value, str) or not state_id_value:
                raise ValueError
            state_id = state_id_value
            angle = _finite(
                summary["angle_from_deployed_deg"],
                f"angle_summaries[{index}].angle_from_deployed_deg",
            )
            diameter = _finite(
                summary["effective_diameter_m"],
                f"angle_summaries[{index}].effective_diameter_m",
            )
            projection = _finite(
                summary["projection_factor"],
                f"angle_summaries[{index}].projection_factor",
            )
            if diameter <= 0.0 or not 0.0 <= projection <= 1.0:
                raise ValueError
            rows.append(
                OpeningSensitivityRow(
                    state_id=state_id,
                    angle_from_deployed_deg=angle,
                    effective_diameter_m=diameter,
                    projection_factor=projection,
                    static_thrust_ratio_median=_finite(
                        static["thrust_ratio_median"],
                        f"angle_summaries[{index}].static.thrust_ratio_median",
                    ),
                    static_torque_ratio_median=_finite(
                        static["torque_ratio_median"],
                        f"angle_summaries[{index}].static.torque_ratio_median",
                    ),
                    forward_thrust_ratio_median=_finite(
                        forward["thrust_ratio_median"],
                        f"angle_summaries[{index}].forward.thrust_ratio_median",
                    ),
                    forward_torque_ratio_median=_finite(
                        forward["torque_ratio_median"],
                        f"angle_summaries[{index}].forward.torque_ratio_median",
                    ),
                )
            )
    except OpeningSensitivityError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise OpeningSensitivityError(
            "Invalid angle summary in opening-sensitivity report."
        ) from exc

    state_ids = [row.state_id for row in rows]
    angles = [row.angle_from_deployed_deg for row in rows]
    if len(set(state_ids)) != state_count or any(
        right >= left for left, right in zip(angles, angles[1:])
    ):
        raise OpeningSensitivityError("Opening states must be unique and ordered.")

    states = document.get("states")
    if not isinstance(states, list) or len(states) != state_count:
        raise OpeningSensitivityError("Opening states do not match the summaries.")
    state_documents: dict[str, Mapping[str, Any]] = {}
    try:
        for index, state in enumerate(states):
            if not isinstance(state, Mapping):
                raise TypeError
            state_id_value = state["id"]
            if not isinstance(state_id_value, str) or not state_id_value:
                raise ValueError
            if state_id_value in state_documents:
                raise ValueError
            angle_rad = _finite(
                state["angle_from_deployed_rad"],
                f"states[{index}].angle_from_deployed_rad",
            )
            _finite(state["deployed_angle_rad"], f"states[{index}].deployed_angle_rad")
            hinge_radius = _finite(
                state["hinge_radius_m"],
                f"states[{index}].hinge_radius_m",
            )
            if hinge_radius <= 0.0 or state.get("projection_model") != "radial_cosine_v1":
                raise ValueError
            state_documents[state_id_value] = state
            row = rows[index]
            if row.state_id != state_id_value or not math.isclose(
                row.angle_from_deployed_deg,
                math.degrees(angle_rad),
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise ValueError
    except OpeningSensitivityError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise OpeningSensitivityError("Opening states do not match the summaries.") from exc

    condition_ids = document.get("condition_ids")
    if (
        not isinstance(condition_ids, list)
        or len(condition_ids) != condition_count
        or len(set(condition_ids)) != condition_count
        or not all(isinstance(value, str) and value for value in condition_ids)
    ):
        raise OpeningSensitivityError("Opening-sensitivity condition matrix is invalid.")
    cases = document.get("cases")
    if not isinstance(cases, list) or len(cases) != case_count:
        raise OpeningSensitivityError("Opening-sensitivity case matrix is incomplete.")
    case_pairs: set[tuple[str, str]] = set()
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    try:
        for index, case in enumerate(cases):
            if not isinstance(case, Mapping):
                raise TypeError
            state_id_value = case["state_id"]
            condition_id_value = case["condition_id"]
            if (
                not isinstance(state_id_value, str)
                or not state_id_value
                or not isinstance(condition_id_value, str)
                or not condition_id_value
            ):
                raise ValueError
            state_id = state_id_value
            condition_id = condition_id_value
            pair = (state_id, condition_id)
            case_pairs.add(pair)
            if condition_id.startswith("static-"):
                regime = "static"
            elif condition_id.startswith("forward-"):
                regime = "forward"
            else:
                raise ValueError
            grouped.setdefault((state_id, regime), []).append(case)
            for field in (
                "effective_diameter_m",
                "projection_factor",
                "thrust_n",
                "torque_nm",
                "thrust_ratio_to_deployed",
                "torque_ratio_to_deployed",
            ):
                _finite(case[field], f"cases[{index}].{field}")
            diameter = float(case["effective_diameter_m"])
            projection = float(case["projection_factor"])
            case_angle = _finite(
                case["angle_from_deployed_rad"],
                f"cases[{index}].angle_from_deployed_rad",
            )
            if diameter <= 0.0 or not 0.0 <= projection <= 1.0:
                raise ValueError
            state = state_documents.get(state_id)
            if state is None or not math.isclose(
                case_angle,
                float(state["angle_from_deployed_rad"]),
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise ValueError
            if case_angle == 0.0 and case.get("fixed_mapping_equal") is not True:
                raise ValueError
    except OpeningSensitivityError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise OpeningSensitivityError("Invalid case in opening-sensitivity report.") from exc
    expected_pairs = {
        (state_id, condition_id)
        for state_id in state_ids
        for condition_id in condition_ids
    }
    if case_pairs != expected_pairs or len(case_pairs) != case_count:
        raise OpeningSensitivityError("Opening-sensitivity case matrix is incomplete.")

    summaries_by_state = {item["state_id"]: item for item in summaries}
    for row in rows:
        summary = summaries_by_state[row.state_id]
        for regime, thrust_expected, torque_expected in (
            (
                "static",
                row.static_thrust_ratio_median,
                row.static_torque_ratio_median,
            ),
            (
                "forward",
                row.forward_thrust_ratio_median,
                row.forward_torque_ratio_median,
            ),
        ):
            regime_cases = grouped.get((row.state_id, regime), [])
            if not regime_cases:
                raise OpeningSensitivityError("Angle summaries do not match the case matrix.")
            if summary["regimes"][regime]["point_count"] != len(regime_cases):
                raise OpeningSensitivityError("Angle summaries do not match the case matrix.")
            thrust_actual = statistics.median(
                float(case["thrust_ratio_to_deployed"]) for case in regime_cases
            )
            torque_actual = statistics.median(
                float(case["torque_ratio_to_deployed"]) for case in regime_cases
            )
            thrust_values = [
                float(case["thrust_ratio_to_deployed"]) for case in regime_cases
            ]
            if not (
                math.isclose(thrust_actual, thrust_expected, rel_tol=0.0, abs_tol=1e-12)
                and math.isclose(
                    torque_actual,
                    torque_expected,
                    rel_tol=0.0,
                    abs_tol=1e-12,
                )
                and math.isclose(
                    min(thrust_values),
                    float(summary["regimes"][regime]["thrust_ratio_minimum"]),
                    rel_tol=0.0,
                    abs_tol=1e-12,
                )
                and math.isclose(
                    max(thrust_values),
                    float(summary["regimes"][regime]["thrust_ratio_maximum"]),
                    rel_tol=0.0,
                    abs_tol=1e-12,
                )
            ):
                raise OpeningSensitivityError("Angle summaries do not match the case matrix.")
        state_cases = grouped[(row.state_id, "static")] + grouped[
            (row.state_id, "forward")
        ]
        if any(
            not math.isclose(
                float(case["effective_diameter_m"]),
                row.effective_diameter_m,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
            or not math.isclose(
                float(case["projection_factor"]),
                row.projection_factor,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
            for case in state_cases
        ):
            raise OpeningSensitivityError("Angle summaries do not match the case matrix.")

    return OpeningSensitivitySnapshot(
        qualification=qualification,
        decision=decision,
        case_count=case_count,
        condition_count=condition_count,
        state_count=state_count,
        report_sha256=report_sha256,
        rows=tuple(rows),
    )
