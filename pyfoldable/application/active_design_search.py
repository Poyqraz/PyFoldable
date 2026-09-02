"""Small chord/twist grids using the existing coordinate-bound BEM service."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from pyfoldable.core import BEMRotorSettings
from pyfoldable.core.units import normalize_quantity

from . import design_analysis as analysis, design_draft, design_search, folding_mechanism
from .design_draft import DesignDraftArtifact, DraftUnitSelection
from .design_search import Evaluation, EvaluationFailure, GridSearchPlan, SearchAxis, SearchError, run_grid_search
from .polar_upload import PolarRunRequest, inspect_polar_bundle, prepare_polar_run


_CONSTRAINTS = ("minimum_thrust", "positive_shaft_power", "physical_validation", "structural_evidence", "stowed_geometry")


@dataclass(frozen=True)
class ActiveSearchRequest:
    base: PolarRunRequest
    plan: GridSearchPlan
    minimum_thrust_n: float
    request_sha256: str
    context_json: str


def _geometry_bound(draft: DesignDraftArtifact) -> dict:
    model, _ = analysis._load_open(draft)
    requirement = model.metadata.get("stowed_envelope_requirement")
    if requirement is None:
        return {"constraint": None, "reason": "no_declared_stowed_requirement"}
    if not math.isclose(model.hinge.axis_elevation_rad, math.pi / 2, rel_tol=0., abs_tol=1e-12):
        return {"constraint": None, "reason": "unsupported_hinge_orientation_for_planar_bound"}
    try:
        target = normalize_quantity(requirement, "length").si_value
        audit = folding_mechanism.build_mechanism_geometry_audit(
            folding_mechanism.MechanismGeometryInputs(model.blade.diameter_m,
                model.blade.hub_radius_m, model.hinge.radius_m, 0., target),
            tuple(station.r_over_R for station in model.blade.stations),
        )
    except ValueError:
        return {"constraint": None, "reason": "invalid_or_unsupported_geometry_requirement"}
    return {"constraint": None if audit.minimum_requirement_reachable else False,
        "reason": "necessary_centerline_bound_only_not_full_surface_clearance",
        "audit": asdict(audit)}


def prepare_active_search(
    base: PolarRunRequest, *, chord_scales: tuple[float, ...], twist_scales: tuple[float, ...],
    minimum_thrust_n: float, max_evaluations: int = 25,
) -> ActiveSearchRequest:
    """Preflight every budget/identity before running even one candidate."""
    if not isinstance(base, PolarRunRequest):
        raise SearchError("Expected the current prepared polar request.")
    fresh = prepare_polar_run(base.draft, base.payload, annulus_count=base.annulus_count)
    if fresh != base:
        raise SearchError("Base request identity changed.")
    minimum = design_search._number(minimum_thrust_n)
    if minimum < 0:
        raise SearchError("Minimum screening thrust must be nonnegative.")
    if type(max_evaluations) is not int or not 1 <= max_evaluations <= 25:
        raise SearchError("Active search evaluation budget must be an integer from 1 to 25.")
    plan = GridSearchPlan((SearchAxis("chord_scale", chord_scales, .5, 1.5),
        SearchAxis("twist_scale", twist_scales, .5, 1.5)), max_evaluations, _CONSTRAINTS)
    count = len(plan.axes[0].values) * len(plan.axes[1].values)
    if base.annulus_count > 40 or count * base.annulus_count > 400:
        raise SearchError("Aggregate solver budget is 400 annuli; at most 40 per candidate.")
    context = {"schema_version": 1, "base_request_sha256": base.request_sha256,
        "plan": asdict(plan), "minimum_thrust_n": minimum, "objective": "shaft_power_w_minimize",
        "geometry_bound": _geometry_bound(base.draft),
        "implementation_sha256": {name: hashlib.sha256(Path(path).read_bytes()).hexdigest()
            for name, path in (("adapter", __file__), ("engine", design_search.__file__),
                ("geometry_audit", folding_mechanism.__file__))}}
    text = design_search._json(context)
    return ActiveSearchRequest(base, plan, minimum, design_search._sha(text), text)


def _candidate_draft(base: DesignDraftArtifact, parameters: dict[str, float]) -> DesignDraftArtifact:
    model, _ = analysis._load_open(base)
    blade = replace(model.blade, stations=tuple(replace(station,
        chord_m=station.chord_m * parameters["chord_scale"],
        twist_rad=station.twist_rad * parameters["twist_scale"])
        for station in model.blade.stations))
    metadata = {key: value for key, value in model.metadata.items() if key not in design_draft._RUNTIME_METADATA}
    metadata.update(source_design_sha256=base.draft_sha256, source_design_id=model.id,
        baseline_draft_sha256=base.draft_sha256,
        search_chord_scale=parameters["chord_scale"], search_twist_scale=parameters["twist_scale"])
    candidate = replace(model, id=f"{model.id}_SEARCH", blade=blade, metadata=metadata)
    toml = design_draft._serialize(candidate, DraftUnitSelection())
    artifact = DesignDraftArtifact("active_search_candidate.toml", toml, base.draft_sha256,
        hashlib.sha256(toml.encode()).hexdigest())
    analysis._load_open(artifact)  # Round trip through the same canonical parser.
    return artifact


def run_active_search(request: ActiveSearchRequest) -> analysis.DesignAnalysisArtifact:
    """Explicit serial grid evaluation; each candidate starts from the same draft."""
    if not isinstance(request, ActiveSearchRequest):
        raise SearchError("Expected a prepared active search request.")
    if not isinstance(request.plan, GridSearchPlan):
        raise SearchError("Expected a prepared active search grid plan.")
    axes = {axis.name: axis.values for axis in request.plan.axes}
    if set(axes) != {"chord_scale", "twist_scale"}:
        raise SearchError("Active search requires exactly chord_scale and twist_scale axes.")
    fresh = prepare_active_search(request.base, chord_scales=axes["chord_scale"],
        twist_scales=axes["twist_scale"], minimum_thrust_n=request.minimum_thrust_n,
        max_evaluations=request.plan.max_evaluations)
    if fresh != request:
        raise SearchError("Search request identity changed.")
    bundle = inspect_polar_bundle(request.base.payload)
    family = bundle.to_family()
    context = json.loads(request.context_json)

    def evaluate(parameters: dict[str, float]) -> Evaluation:
        try:
            candidate = _candidate_draft(request.base.draft, parameters)
            artifact = analysis.run_design_analysis(candidate, {bundle.airfoil_id: family},
                settings=BEMRotorSettings(annulus_count=request.base.annulus_count))
        except (ValueError, ArithmeticError) as exc:
            raise EvaluationFailure(str(exc)) from exc
        result = json.loads(artifact.report_json)
        rotor = result["rotor"]
        return Evaluation(rotor["shaft_power_w"], {
            "minimum_thrust": rotor["thrust_n"] >= request.minimum_thrust_n,
            "positive_shaft_power": rotor["shaft_power_w"] > 0,
            "physical_validation": None, "structural_evidence": None,
            "stowed_geometry": context["geometry_bound"]["constraint"],
        }, {"draft_toml": candidate.toml, "draft_sha256": candidate.draft_sha256,
            "analysis_request_sha256": artifact.request_sha256,
            "analysis_report_sha256": artifact.report_sha256, "rotor": rotor})

    return run_grid_search(request.plan, evaluate, evaluator_identity={
        "id": "active_design_chord_twist_bem_v1", "active_search_request_sha256": request.request_sha256,
        "active_search_context": context, "base_draft_toml": request.base.draft.toml,
        "base_polar_json": request.base.payload.decode("utf-8"),
        "base_run_context": json.loads(request.base.context_json),
        "report_storage": "shared_inputs_once_candidate_drafts_and_full_rotor_outputs_per_row",
    })
