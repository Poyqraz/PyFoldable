"""Bind the pending initial-call evaluator without invoking it.

Declaration defaults and caller claims are not the actual inputs. Deferred
Radau and integration routines stay uncleared. Applicability stays blocked.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from pyfoldable.application.c2v09_ordered_declaration import (
    CANDIDATE29_DISPOSITION,
    _json_fence,
    _read_text,
)
from pyfoldable.application.c2v09_pre_call_admission import PreCallAdmission, prepare_pre_call_admission
from pyfoldable.application.c2v09_pre_call_binding import (
    MAPPER_BINDING,
    SOURCE_BINDING,
    _code_for_qualname,
    _thread_id,
    compare_code_structure,
)
from pyfoldable.application.cmm2_coupled_transient_service import Cmm2FoldableBemMappedAeroEvaluator
from pyfoldable.application.coupled_transient_service import CoupledEnvironment
from pyfoldable.application.design_draft import DesignDraftArtifact
from pyfoldable.application.mechanism_binding import _load_draft
from pyfoldable.core.bem import BEMAnnulusSettings
from pyfoldable.core.bem_rotor import BEMRotorSettings
from pyfoldable.core.config import load_design_config
from pyfoldable.core.foldable_aero_load import map_foldable_bem_aero_loads
from pyfoldable.core.foldable_rotor import solve_foldable_bem_rotor
from pyfoldable.core.models import PolarTable
from pyfoldable.core.polar import PolarFamily
from pyfoldable.core.polar_spanwise import SpanwisePolarAnchor, SpanwisePolarSchedule
from pyfoldable.core.rotational_augmentation import RotationalAugmentationModel
from pyfoldable.dynamics.cmm2_coupled_transient import solve_cmm2_transient


CONTRACT_BLOCKED = "CONTRACT BLOCKED"
POST_RETURN_ONLY = "POST-RETURN ONLY"
_COUNTERS = {"source": 0, "mapper": 0, "partition": 0, "selection": 0, "seal": 0, "trajectory": 0}
_ACTIVE_CODE = (
    ("pyfoldable/application/cmm2_coupled_transient_service.py", "Cmm2FoldableBemMappedAeroEvaluator.__init__", Cmm2FoldableBemMappedAeroEvaluator.__init__),
    ("pyfoldable/application/cmm2_coupled_transient_service.py", "Cmm2FoldableBemMappedAeroEvaluator.__call__", Cmm2FoldableBemMappedAeroEvaluator.__call__),
    ("pyfoldable/core/foldable_rotor.py", "solve_foldable_bem_rotor", solve_foldable_bem_rotor),
    ("pyfoldable/core/foldable_aero_load.py", "map_foldable_bem_aero_loads", map_foldable_bem_aero_loads),
    ("pyfoldable/core/config.py", "load_design_config", load_design_config),
)


def binary64_hex(value: float) -> str:
    """Exact binary64 text, including the sign of zero."""
    return float(value).hex()


def _floats(values: object) -> tuple[float, ...]:
    if not isinstance(values, (list, tuple)):
        raise TypeError("expected a numeric sequence")
    return tuple(float(value) for value in values)


def _polar_schedule(document: Mapping[str, object]) -> SpanwisePolarSchedule:
    anchors = []
    for row in document["anchors"]:
        if not isinstance(row, Mapping):
            raise TypeError("polar anchor is not an object")
        family = row["family"]
        if not isinstance(family, Mapping):
            raise TypeError("polar family is not an object")
        tables = []
        for table in family["tables"]:
            if not isinstance(table, Mapping):
                raise TypeError("polar table is not an object")
            tables.append(
                PolarTable(
                    airfoil_id=str(table["airfoil_id"]),
                    reynolds=float(table["reynolds"]),
                    mach=float(table["mach"]),
                    alpha_rad=_floats(table["alpha_rad"]),
                    cl=_floats(table["cl"]),
                    cd=_floats(table["cd"]),
                    cm=_floats(table["cm"]),
                    source=str(table["source"]),
                    scenario_id=str(table["scenario_id"]),
                    metadata=dict(table.get("metadata") or {}),
                )
            )
        anchors.append(SpanwisePolarAnchor(float(row["r_over_R"]), PolarFamily(tuple(tables))))
    return SpanwisePolarSchedule(str(document["id"]), tuple(anchors))


def _settings(document: Mapping[str, object]) -> BEMRotorSettings:
    annulus = document["annulus_settings"]
    if not isinstance(annulus, Mapping):
        raise TypeError("annulus settings are not an object")
    rotation = annulus["rotational_augmentation"]
    if not isinstance(rotation, Mapping):
        raise TypeError("rotational augmentation is not an object")
    model = RotationalAugmentationModel(
        kind=rotation["kind"],
        lift_curve_slope_per_rad=None if rotation["lift_curve_slope_per_rad"] is None else float(rotation["lift_curve_slope_per_rad"]),
        zero_lift_angle_rad=None if rotation["zero_lift_angle_rad"] is None else float(rotation["zero_lift_angle_rad"]),
        maximum_chord_over_radius=float(rotation["maximum_chord_over_radius"]),
        maximum_absolute_alpha_rad=float(rotation["maximum_absolute_alpha_rad"]),
    )
    return BEMRotorSettings(
        annulus_count=int(document["annulus_count"]),
        radial_domain=document["radial_domain"],
        annulus_settings=BEMAnnulusSettings(
            bracket_samples=int(annulus["bracket_samples"]),
            max_iterations=int(annulus["max_iterations"]),
            angle_tolerance_rad=float(annulus["angle_tolerance_rad"]),
            residual_tolerance_m2_s=float(annulus["residual_tolerance_m2_s"]),
            relative_residual_tolerance=float(annulus["relative_residual_tolerance"]),
            minimum_tip_loss_factor=float(annulus["minimum_tip_loss_factor"]),
            include_tip_loss=bool(annulus["include_tip_loss"]),
            include_root_loss=bool(annulus["include_root_loss"]),
            loading_branch=annulus["loading_branch"],
            rotational_augmentation=model,
        ),
    )


def _environment(document: Mapping[str, object]) -> CoupledEnvironment:
    return CoupledEnvironment(
        id=str(document["id"]),
        forward_speed_m_s=float(document["forward_speed_m_s"]),
        air_density_kg_m3=float(document["air_density_kg_m3"]),
        dynamic_viscosity_pa_s=float(document["dynamic_viscosity_pa_s"]),
        temperature_k=float(document["temperature_k"]),
        pressure_pa=float(document["pressure_pa"]),
    )


def _candidate(root: Path) -> dict[str, object]:
    text = _read_text(root, "docs/cmm2_c2v09_candidate29_proposal.md")
    return _loads(_json_fence(text, 0))


def _loads(text: str) -> dict[str, object]:
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise TypeError("candidate29 manifest is not an object")
    return parsed


def _compare_active(root: Path) -> list[dict[str, object]]:
    rows = []
    for path, qualname, function in _ACTIVE_CODE:
        source_path = root / path
        classification = "NOT ESTABLISHED"
        if source_path.is_file() and hasattr(function, "__code__"):
            compiled = compile(source_path.read_text(encoding="utf-8"), str(source_path), "exec", dont_inherit=True, optimize=sys.flags.optimize)
            expected = _code_for_qualname(compiled, qualname)
            if expected is not None:
                classification = compare_code_structure(function.__code__, expected)
        rows.append({"qualname": qualname, "path": path, "classification": classification, "role": "active initial graph"})
    return rows


def _applicability(admission: PreCallAdmission) -> dict[str, object]:
    native = admission.native_comparison
    genuine = native.get("native_observer") == "prepare_cosine_path_certificate" and native.get("collector_kind") == "collect_binding_record"
    return {
        "status": CONTRACT_BLOCKED,
        "native_is_genuine": genuine,
        "exact_historical_equality_assumed": False,
        "equivalence_assumed": False,
        "body_match_proof_role": "historical libm body predicate only; not wrapper, GOT, executable, library, or XCR0 identity",
        "historical_mismatches": list(native.get("mismatches") or []),
        "historical_xcr0": native.get("historical_xcr0", {"classification": "NOT ESTABLISHED"}),
        "loaded_body": native.get("loaded_body", {"classification": "NOT ESTABLISHED"}),
        "eligibility_evidence": False,
        "unreviewed_applicability": "CONTRACT BLOCKED",
    }


@dataclass
class InitialCallBinding:
    """Retained evaluator and inputs. Calling the evaluator is not authorized."""

    evaluator: Cmm2FoldableBemMappedAeroEvaluator
    retained: dict[str, object]
    input_identity: dict[str, object]
    initial_arguments: dict[str, object]
    active_graph: list[dict[str, object]]
    deferred_routines: dict[str, object]
    applicability: dict[str, object]
    native_observation: dict[str, object]
    post_return: dict[str, str]
    admission: PreCallAdmission
    caller_claims: dict[str, object]
    caller_claims_role: str
    candidate29_disposition: str
    pid: int
    thread_id: str
    authorizes_execution: bool = False
    eligibility_evidence: bool = False
    physical_qualification: bool = False
    dependent_counters: dict[str, int] = field(default_factory=lambda: dict(_COUNTERS))

    def __post_init__(self) -> None:
        self.authorizes_execution = False
        self.eligibility_evidence = False
        self.physical_qualification = False
        self.dependent_counters = dict(_COUNTERS)


def bind_initial_call(
    root: Path,
    *,
    admission: PreCallAdmission | None = None,
    caller_claims: Mapping[str, object] | None = None,
) -> InitialCallBinding:
    """Parse the pending candidate29 inputs and retain the unevaluated instance."""
    prepared = prepare_pre_call_admission(root) if admission is None else admission
    manifest = _candidate(root)
    effective = manifest["effective_binding"]
    if not isinstance(effective, Mapping):
        raise TypeError("candidate29 effective binding is not an object")
    artifact = DesignDraftArtifact(
        "candidate29.toml",
        str(manifest["draft_toml"]),
        str(effective["source_sha256"]),
        str(effective["draft_sha256"]),
    )
    design = _load_draft(artifact)
    polars_document = effective["polars"]
    settings_document = effective["bem_settings"]
    environment_document = effective["environment"]
    if not isinstance(polars_document, Mapping) or not isinstance(settings_document, Mapping) or not isinstance(environment_document, Mapping):
        raise TypeError("candidate29 inputs are not objects")
    polars = _polar_schedule(polars_document)
    settings = _settings(settings_document)
    environment = _environment(environment_document)
    hinge = float(design.hinge.radius_m)
    manifest_hinge = float(effective["hinge_radius_m"])
    evaluator = Cmm2FoldableBemMappedAeroEvaluator(
        design.blade,
        polars,
        settings,
        environment,
        hinge,
        str(effective["bounds"]),
    )
    identity = {
        "parsed_draft_matches_manifest": binary64_hex(hinge) == binary64_hex(manifest_hinge) and effective["bounds"] == "error",
        "hinge_radius_hex": binary64_hex(hinge),
        "station_r_over_r_hex": [binary64_hex(station.r_over_R) for station in design.blade.stations],
        "station_count": len(design.blade.stations),
        "blade_count": design.blade.blade_count,
        "polar_schedule_id": polars.id,
        "bounds": evaluator.bounds,
        "source_sha256": artifact.source_sha256,
        "draft_sha256": artifact.draft_sha256,
        "evidence_role": "parsed draft and verified manifest bytes",
    }
    arguments = {
        "time_s": "NOT ESTABLISHED",
        "theta_rad_hex": binary64_hex(float(effective["initial_angle_rad"])),
        "theta_dot_rad_s_hex": binary64_hex(float(effective["initial_angular_velocity_rad_s"])),
        "omega_rad_s_hex": binary64_hex(float(effective["initial_omega_rad_s"])),
    }
    native_kind = "genuine" if prepared.native_comparison.get("native_observer") == "prepare_cosine_path_certificate" else "test_double"
    return InitialCallBinding(
        evaluator,
        {
            "blade": evaluator.blade,
            "polars": evaluator.polars,
            "settings": evaluator.settings,
            "environment": evaluator.environment,
            SOURCE_BINDING: evaluator.__call__.__globals__.get(SOURCE_BINDING),
            MAPPER_BINDING: evaluator.__call__.__globals__.get(MAPPER_BINDING),
            "__call__": Cmm2FoldableBemMappedAeroEvaluator.__call__,
            "__call_code__": evaluator.__call__.__code__,
            "active_codes": {qualname: function.__code__ for _path, qualname, function in _ACTIVE_CODE},
        },
        identity,
        arguments,
        _compare_active(root),
        {
            "solve_cmm2_transient": "NOT CLEARED",
            "cmm2_radau_dense": "NOT CLEARED",
            "clearance_granted": False,
            "retained_callable_is_not_a_clearance": solve_cmm2_transient,
        },
        _applicability(prepared),
        {"kind": native_kind, "comparison": prepared.native_comparison},
        {"returned_source_object": POST_RETURN_ONLY, "mapped_interval_consumption": POST_RETURN_ONLY},
        prepared,
        dict(caller_claims or {}),
        "not actual-input evidence",
        CANDIDATE29_DISPOSITION,
        os.getpid(),
        _thread_id(),
    )


def revalidate_initial_call_binding(value: object) -> InitialCallRevalidation:
    """Same process and thread. An archived record is not this binding."""
    if not isinstance(value, InitialCallBinding):
        return InitialCallRevalidation("NOT ESTABLISHED")
    if value.pid != os.getpid() or value.thread_id != _thread_id():
        return InitialCallRevalidation("INVALIDATED")
    evaluator = value.evaluator
    if (
        evaluator.blade is not value.retained["blade"]
        or evaluator.polars is not value.retained["polars"]
        or evaluator.settings is not value.retained["settings"]
        or evaluator.environment is not value.retained["environment"]
        or type(evaluator).__call__ is not value.retained["__call__"]
        or binary64_hex(evaluator.hinge_radius_m) != value.input_identity["hinge_radius_hex"]
        or evaluator.successful_bem_solves != 0
        or evaluator.successful_map_calls != 0
    ):
        return InitialCallRevalidation("INVALIDATED")
    namespace = evaluator.__call__.__globals__
    if namespace.get(SOURCE_BINDING) is not value.retained[SOURCE_BINDING] or namespace.get(MAPPER_BINDING) is not value.retained[MAPPER_BINDING]:
        return InitialCallRevalidation("INVALIDATED")
    if value.retained[SOURCE_BINDING] is not solve_foldable_bem_rotor or value.retained[MAPPER_BINDING] is not map_foldable_bem_aero_loads:
        return InitialCallRevalidation("INVALIDATED")
    if evaluator.__call__.__code__ is not value.retained["__call_code__"]:
        return InitialCallRevalidation("INVALIDATED")
    for _path, qualname, function in _ACTIVE_CODE:
        if function.__code__ is not value.retained["active_codes"][qualname]:
            return InitialCallRevalidation("INVALIDATED")
    return InitialCallRevalidation("REVALIDATED")


@dataclass
class InitialCallRevalidation:
    classification: str
    authorizes_execution: bool = False
    eligibility_evidence: bool = False
    physical_qualification: bool = False
    applicability: str = CONTRACT_BLOCKED

    def __post_init__(self) -> None:
        self.authorizes_execution = False
        self.eligibility_evidence = False
        self.physical_qualification = False
        self.applicability = CONTRACT_BLOCKED
