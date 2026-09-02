"""Budgeted finite-grid minimization; no continuous or physical optimum claim."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from .design_analysis import DesignAnalysisArtifact


class SearchError(ValueError):
    """Invalid search plan, identity or callback output."""


class EvaluationFailure(ValueError):
    """Expected candidate-domain failure; recorded, not assigned a penalty score."""


def _number(value: Any) -> float:
    try:
        if type(value) not in (int, float) or not math.isfinite(value):
            raise SearchError("Search numbers must be finite and cannot be strings/bools.")
        return float(value)
    except OverflowError as exc:
        raise SearchError("Search number exceeds floating-point range.") from exc


def _name(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", value):
        raise SearchError("Search names must be short lowercase identifiers.")
    return value


def _json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        raise SearchError("Search content must be finite JSON-safe data.") from exc


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _snapshot(value: Mapping[str, Any], limit: int) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise SearchError("Search identity/details must be a mapping.")
    document = _json(dict(value))
    if len(document.encode()) > limit:
        raise SearchError("Search identity/details byte budget exceeded.")
    snapshot = json.loads(document)
    pending = [snapshot]
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            if "physical_qualification" in node and node["physical_qualification"] is not False:
                raise SearchError("Search inputs cannot declare physical qualification.")
            pending.extend(node.values())
        elif isinstance(node, list):
            pending.extend(node)
    return snapshot


@dataclass(frozen=True)
class SearchAxis:
    name: str
    values: tuple[float, ...]
    lower: float
    upper: float

    def __post_init__(self) -> None:
        _name(self.name)
        lower, upper = _number(self.lower), _number(self.upper)
        if lower > upper or not isinstance(self.values, (tuple, list)) or not 1 <= len(self.values) <= 9:
            raise SearchError("An axis requires ordered bounds and 1–9 points.")
        values = tuple(sorted(_number(value) for value in self.values))
        if len(set(values)) != len(values) or any(not lower <= value <= upper for value in values):
            raise SearchError("Axis values must be unique and inside declared bounds.")
        object.__setattr__(self, "values", values)
        object.__setattr__(self, "lower", lower)
        object.__setattr__(self, "upper", upper)


@dataclass(frozen=True)
class GridSearchPlan:
    axes: tuple[SearchAxis, ...]
    max_evaluations: int
    required_constraints: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (not isinstance(self.axes, (tuple, list)) or not 1 <= len(self.axes) <= 4
                or not all(isinstance(axis, SearchAxis) for axis in self.axes)):
            raise SearchError("A grid requires 1–4 typed axes.")
        if len({axis.name for axis in self.axes}) != len(self.axes):
            raise SearchError("Duplicate search axis name.")
        if type(self.max_evaluations) is not int or not 1 <= self.max_evaluations <= 81:
            raise SearchError("Evaluation budget must be an integer from 1 to 81.")
        if math.prod(len(axis.values) for axis in self.axes) > self.max_evaluations:
            raise SearchError("Full grid exceeds evaluation budget; no candidate was run.")
        if not isinstance(self.required_constraints, (tuple, list)) or len(self.required_constraints) > 16:
            raise SearchError("Required constraints must be at most 16 named checks.")
        constraints = tuple(sorted(_name(name) for name in self.required_constraints))
        if len(set(constraints)) != len(constraints):
            raise SearchError("Duplicate required constraint name.")
        object.__setattr__(self, "axes", tuple(sorted(self.axes, key=lambda axis: axis.name)))
        object.__setattr__(self, "required_constraints", constraints)


@dataclass(frozen=True)
class Evaluation:
    objective: float
    constraints: Mapping[str, bool | None] = field(default_factory=dict)
    details: Mapping[str, Any] = field(default_factory=dict)


def run_grid_search(
    plan: GridSearchPlan,
    evaluate: Callable[[dict[str, float]], Evaluation],
    *,
    evaluator_identity: Mapping[str, Any],
) -> DesignAnalysisArtifact:
    """Enumerate canonical grid order once, minimizing among known-feasible rows.

    Missing constraint == unknown, never passed. Only explicit domain/arithmetic
    failures are caught; programming errors/cancellation abort without a report.
    This is a numerical callback boundary, not evidence authentication.
    """
    if not isinstance(plan, GridSearchPlan) or not callable(evaluate):
        raise SearchError("Expected a typed grid plan and evaluator callback.")
    request = {"algorithm": "finite_grid_minimize_v1", "random_seed": None,
        "plan": asdict(plan), "objective_direction": "minimize",
        "evaluator_identity": _snapshot(evaluator_identity, 4 * 1024 * 1024),
        "evaluator_identity_scope": "caller_declared_not_authenticated",
        "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    request_sha = _sha(_json(request))
    candidates = []
    counts = dict.fromkeys(("feasible", "infeasible", "blocked", "failed"), 0)
    best = None
    for index, values in enumerate(itertools.product(*(axis.values for axis in plan.axes))):
        parameters = dict(zip((axis.name for axis in plan.axes), values))
        row = {"index": index, "parameters": parameters, "objective": None,
            "constraints": {}, "details": {}, "status": "failed", "error": None}
        try:
            result = evaluate(dict(parameters))
        except (EvaluationFailure, ArithmeticError) as exc:
            row["error"] = f"{type(exc).__name__}: {str(exc)[:1024]}"
        else:
            try:
                if not isinstance(result, Evaluation) or not isinstance(result.constraints, Mapping):
                    raise SearchError("Callback must return a typed Evaluation with constraint mapping.")
                objective = _number(result.objective)
                if set(result.constraints) - set(plan.required_constraints):
                    raise SearchError("Evaluator returned undeclared constraints.")
                if any(value is not None and type(value) is not bool for value in result.constraints.values()):
                    raise SearchError("Constraint values must be literal true/false/null.")
                constraints = {name: result.constraints.get(name) for name in plan.required_constraints}
                details = _snapshot(result.details, 256 * 1024)
                status = ("infeasible" if False in constraints.values() else
                    "blocked" if None in constraints.values() else "feasible")
                row.update(objective=objective, constraints=constraints, details=details, status=status)
                if status == "feasible" and (best is None or objective < best["objective"]):
                    best = row
            except SearchError as exc:
                row["error"] = str(exc)
        counts[row["status"]] += 1
        candidates.append(row)
    document = {"schema_version": 1, "artifact_class": "finite_grid_search_screening",
        "physical_qualification": False, "qualification": "numerical_screening_not_design_recommendation",
        "request": request, "request_sha256": request_sha,
        "evaluations_attempted": len(candidates), "grid_exhausted": True,
        "all_evaluations_succeeded": counts["failed"] == 0,
        "status_counts": counts, "candidates": candidates, "best_candidate": best,
        "selection_scope": "evaluated_known_feasible_grid_points_only_not_continuous_global_optimum"}
    report = _json(document) + "\n"
    return DesignAnalysisArtifact(request_sha, _sha(report), report, "finite_grid_search_screening.json")
