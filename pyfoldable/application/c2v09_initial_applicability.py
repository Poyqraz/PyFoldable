"""Zero-call applicability dossier for the pending initial evaluator transaction.

The accepted input, argument, and global-classification repair is f74f7d4.
This module does not call the evaluator, source, mapper, partition, selection,
seal, or trajectory.
"""

from __future__ import annotations

import ctypes
import json
import math
import sys
from pathlib import Path
from typing import Callable, Mapping

from pyfoldable.application.c2v09_initial_call_binding import (
    CONTRACT_BLOCKED,
    POST_RETURN_ONLY,
    InitialCallBinding,
    _referenced_globals,
    bind_initial_call,
    revalidate_initial_call_binding,
)
from pyfoldable.application.c2v09_ordered_declaration import (
    CANDIDATE29_DISPOSITION,
    TECHNICAL_ARTIFACT_SHA256,
    TECHNICAL_HEAD,
    _json_fence,
    sha256_bytes,
)
from pyfoldable.application.c2v09_pre_call_binding import (
    _code_for_qualname,
    compare_code_structure,
    compare_signature_defaults,
)
from pyfoldable.application.cmm2_coupled_transient_service import Cmm2FoldableBemMappedAeroEvaluator
from pyfoldable.core.bem_rotor import _interpolate_station, _radial_limits, solve_bem_rotor
from pyfoldable.core.config import load_design_config
from pyfoldable.core.foldable_aero_load import (
    _native_terminal_annuli,
    _projection_factor,
    map_foldable_bem_aero_loads,
    map_projected_material_loads,
    projected_radius_m,
)
from pyfoldable.core.foldable_rotor import (
    FoldableRotorState,
    _station_at_hinge,
    project_foldable_blade,
    project_spanwise_polar_schedule,
    solve_foldable_bem_rotor,
)
from pyfoldable.core.polar import PolarFamily
from pyfoldable.core.polar_spanwise import SpanwisePolarSchedule


ACCEPTED_REPAIR_HEAD = "f74f7d4f0cf2c2a6e6cd37aeec666aea786d12ca"
ACCEPTED_REPAIR_TREE = "25f74c3f8256ad279ec14630b35c0735552348df"
REPAIRED_OBSERVATION_PATH = "reports/c2v09_cosine_path_certificate/repaired_observation.json"
REPAIRED_OBSERVATION_SHA256 = "273744853a2c2b0691cc208fbb5d00e97d8b802379958d106f29d096c3f8b08a"
CERTIFICATE_PATH = "docs/cmm2_c2v09_partition_runtime_certificate.md"
IMPLEMENTATION_SOURCE = "pyfoldable/application/c2v09_cosine_path_certificate.py"

_DECLARED_OPERATIONS = (
    ("pyfoldable/application/cmm2_coupled_transient_service.py", "Cmm2FoldableBemMappedAeroEvaluator.__call__", Cmm2FoldableBemMappedAeroEvaluator.__call__, "evaluator call", "transaction"),
    ("pyfoldable/core/foldable_rotor.py", "solve_foldable_bem_rotor", solve_foldable_bem_rotor, "source call", "transaction"),
    ("pyfoldable/core/foldable_aero_load.py", "map_foldable_bem_aero_loads", map_foldable_bem_aero_loads, "mapper call", "transaction"),
    ("pyfoldable/core/config.py", "load_design_config", load_design_config, "draft parse", "transaction"),
    ("pyfoldable/core/foldable_rotor.py", "FoldableRotorState.angle_from_deployed_rad", FoldableRotorState.angle_from_deployed_rad.fget, "angle from deployed", "geometric lemma"),
    ("pyfoldable/core/foldable_rotor.py", "project_foldable_blade", project_foldable_blade, "source cosine projection and kernel-radius product", "geometric lemma"),
    ("pyfoldable/core/foldable_rotor.py", "project_spanwise_polar_schedule", project_spanwise_polar_schedule, "spanwise anchor projection", "geometric lemma"),
    ("pyfoldable/core/foldable_aero_load.py", "_projection_factor", _projection_factor, "mapper cosine input", "geometric lemma"),
    ("pyfoldable/core/foldable_rotor.py", "_station_at_hinge", _station_at_hinge, "hinge station construction", "geometric lemma"),
    ("pyfoldable/core/bem_rotor.py", "_radial_limits", _radial_limits, "radial domain construction", "geometric lemma"),
    ("pyfoldable/core/bem_rotor.py", "_interpolate_station", _interpolate_station, "normalized radial query", "geometric lemma"),
    ("pyfoldable/core/polar.py", "PolarFamily.query", PolarFamily.query, "polar query branches", "geometric lemma"),
    ("pyfoldable/core/polar_spanwise.py", "SpanwisePolarSchedule.section", SpanwisePolarSchedule.section, "spanwise normalized query", "geometric lemma"),
    ("pyfoldable/core/foldable_aero_load.py", "projected_radius_m", projected_radius_m, "mapper projected radius", "geometric lemma"),
    ("pyfoldable/core/foldable_aero_load.py", "map_projected_material_loads", map_projected_material_loads, "mapper interval ownership", "geometric lemma"),
    ("pyfoldable/core/foldable_aero_load.py", "_native_terminal_annuli", _native_terminal_annuli, "python terminal-guard helper", "native terminal guard"),
    ("pyfoldable/core/bem_rotor.py", "solve_bem_rotor", solve_bem_rotor, "bem numerical solution", "bem numerical dependency"),
)


def _operation_row(root: Path, path: str, qualname: str, function: object, operation: str, family: str) -> dict[str, object]:
    source_path = root / path
    code_status = "NOT ESTABLISHED"
    defaults = "NOT ESTABLISHED"
    referenced = "NOT ESTABLISHED"
    if source_path.is_file() and hasattr(function, "__code__"):
        text = source_path.read_text(encoding="utf-8")
        compiled = compile(text, str(source_path), "exec", dont_inherit=True, optimize=sys.flags.optimize)
        expected = _code_for_qualname(compiled, qualname)
        if expected is not None:
            code_status = compare_code_structure(function.__code__, expected)
        defaults = compare_signature_defaults(function, text, qualname)
        referenced = _referenced_globals(root, function)
    if "MISMATCH" in (code_status, defaults, referenced):
        overall = "MISMATCH"
    elif "NOT ESTABLISHED" in (code_status, defaults, referenced):
        overall = "NOT ESTABLISHED"
    else:
        overall = "MATCH"
    return {
        "path": path,
        "qualname": qualname,
        "operation": operation,
        "family": family,
        "classification": overall,
        "constants": code_status,
        "defaults": defaults,
        "globals": referenced,
        "geometric_lemma": family == "geometric lemma",
        "bem_numerical_dependency": family == "bem numerical dependency",
        "module_digest_clears_this_row": False,
        "filename_clears_this_row": False,
        "proof_role": (
            "loaded code structure of this qualname only"
            if overall == "MATCH"
            else "this qualname is not established"
        ),
    }


def declare_initial_operation_graph(root: Path) -> list[dict[str, object]]:
    """Finite source-to-mapper and scope-A graph. A filename clears nothing."""
    rows = [
        _operation_row(root, path, qualname, function, operation, family)
        for path, qualname, function, operation, family in _DECLARED_OPERATIONS
    ]
    rows.append(_native_guard_row())
    return rows


def _c_function_address(function: object) -> str | None:
    getter = ctypes.pythonapi.PyCFunction_GetFunction
    getter.argtypes = [ctypes.py_object]
    getter.restype = ctypes.c_void_p
    try:
        value = getter(function)
    except (OSError, ValueError, TypeError):
        return None
    if not value:
        ctypes.pythonapi.PyErr_Clear()
        return None
    return hex(int(value))


def _native_guard_row() -> dict[str, object]:
    address = _c_function_address(math.ulp)
    return {
        "path": None,
        "qualname": "math.ulp",
        "operation": "native terminal guard",
        "family": "native terminal guard",
        "classification": "NOT ESTABLISHED",
        "observed_wrapper_address": address,
        "calls": 0,
        "geometric_lemma": False,
        "bem_numerical_dependency": False,
        "module_digest_clears_this_row": False,
        "filename_clears_this_row": False,
        "historical_equality_assumed": False,
        "proof_role": "this process wrapper address is not a historical nextafter binding",
    }


def _historical_ulp(root: Path) -> dict[str, object]:
    path = root / CERTIFICATE_PATH
    pin = TECHNICAL_ARTIFACT_SHA256[CERTIFICATE_PATH]
    if not path.is_file() or sha256_bytes(path.read_bytes()) != pin:
        return {"classification": "NOT ESTABLISHED", "exact_equality_assumed": False, "clears_this_process": False}
    native = json.loads(_json_fence(path.read_text(encoding="utf-8"), 0)).get("native_math_ulp_path")
    if not isinstance(native, dict):
        return {"classification": "NOT ESTABLISHED", "exact_equality_assumed": False, "clears_this_process": False}
    return {
        "classification": "HISTORICAL HYPOTHESIS",
        "wrapper_elf_vaddr": native.get("wrapper_ELF_vaddr"),
        "nextafter_got_vaddr": native.get("nextafter_GOT_vaddr"),
        "exact_equality_assumed": False,
        "clears_this_process": False,
    }


def classify_implementation_change(
    current_digest: str,
    historical_digest: str | None,
    *,
    review_binding: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """A hash difference is pending until an explicit review names this digest."""
    scope = None
    if not isinstance(historical_digest, str):
        relation = "NOT ESTABLISHED"
    elif current_digest == historical_digest:
        relation = "HISTORICAL EQUALITY"
    elif (
        isinstance(review_binding, Mapping)
        and review_binding.get("current_digest") == current_digest
        and isinstance(review_binding.get("scope"), str)
        and review_binding.get("scope")
    ):
        relation = "REVIEWED REBINDING"
        scope = str(review_binding["scope"])
    else:
        relation = "CHANGED / REVIEW PENDING"
    return {
        "current_implementation_sha256": current_digest,
        "historical_implementation_sha256": historical_digest,
        "relation": relation,
        "review_scope": scope,
        "historical_equality_assumed": False,
        "clears_runtime_differences": False,
        "runtime_transfer_approved": False,
    }


def _implementation_rebinding(root: Path) -> dict[str, object]:
    current = sha256_bytes((root / IMPLEMENTATION_SOURCE).read_bytes())
    observed = root / REPAIRED_OBSERVATION_PATH
    historical = None
    if observed.is_file() and sha256_bytes(observed.read_bytes()) == REPAIRED_OBSERVATION_SHA256:
        payload = json.loads(observed.read_text(encoding="utf-8"))["canonical_payload"]
        value = payload.get("implementation_sha256")
        historical = value if isinstance(value, str) else None
    return classify_implementation_change(current, historical)


def _blocked(name: str, classification: str, timing: str) -> dict[str, object]:
    row: dict[str, object] = {
        "name": name,
        "classification": classification,
        "contract": CONTRACT_BLOCKED,
        "timing": timing,
    }
    if timing == "POST-RETURN ONLY":
        row["demanded_before_it_exists"] = False
    if timing == "deferred integration":
        row["prerequisite_for_isolated_source_attempt"] = False
    return row


def _not_current_runtime() -> dict[str, object]:
    return {
        "current": False,
        "kind": "NOT CURRENT",
        "loaded_code_correspondence": "NOT ESTABLISHED",
        "measurement_image": {
            "file_image_identity": "NOT ESTABLISHED",
            "loaded_code_correspondence": "NOT ESTABLISHED",
            "handle_associated": False,
            "second_compilation_is_evidence": False,
            "source_hash_is_the_image": False,
        },
        "test_double_is_measurement_evidence": False,
        "archived_json_is_measurement_evidence": False,
        "cosine_function_calls": 0,
    }


def _serialized_dossier() -> dict[str, object]:
    return {
        "status": CONTRACT_BLOCKED,
        "authorizes_execution": False,
        "eligibility_evidence": False,
        "physical_qualification": False,
        "candidate29_disposition": CANDIDATE29_DISPOSITION,
        "binding_revalidation": "NOT ESTABLISHED",
        "serialized_record_is_a_live_binding": False,
        "genuine_runtime_observations": _not_current_runtime(),
        "retained_observation": {"role": "historical/unvalidated", "revalidation": "NOT ESTABLISHED"},
        "deferred_radau_is_prerequisite_for_isolated_source_attempt": False,
        "post_return_demanded_before_existence": False,
    }


def build_applicability_dossier(
    root: Path,
    *,
    binding: InitialCallBinding | None = None,
    native_observer: Callable[..., object] | None = None,
) -> dict[str, object]:
    """One reviewable dossier. Unresolved rows stay contract blocked."""
    if binding is not None and not isinstance(binding, InitialCallBinding):
        return _serialized_dossier()
    prepared = binding if binding is not None else bind_initial_call(
        root,
        **({} if native_observer is None else {"native_observer": native_observer}),
    )
    checked = revalidate_initial_call_binding(prepared)
    current = checked.classification == "REVALIDATED"
    graph = declare_initial_operation_graph(root)
    native = prepared.native_observation
    measurement = native.get("measurement_image") if isinstance(native.get("measurement_image"), dict) else {}
    genuine = current and native.get("kind") == "genuine" and measurement.get("handle_associated") is True
    if genuine:
        current_measurement = dict(measurement)
        correspondence = current_measurement.get("loaded_code_correspondence", "NOT ESTABLISHED")
        if correspondence != "MATCH":
            correspondence = "NOT ESTABLISHED"
    else:
        current_measurement = {
            "file_image_identity": "NOT ESTABLISHED",
            "loaded_code_correspondence": "NOT ESTABLISHED",
            "handle_associated": False,
            "second_compilation_is_evidence": False,
            "source_hash_is_the_image": False,
        }
        correspondence = "NOT ESTABLISHED"
    admission = prepared.admission
    unmet = [
        _blocked("returned source object", POST_RETURN_ONLY, "POST-RETURN ONLY"),
        _blocked("mapped interval consumption", POST_RETURN_ONLY, "POST-RETURN ONLY"),
        _blocked("solve_cmm2_transient", str(prepared.deferred_routines.get("solve_cmm2_transient")), "deferred integration"),
        _blocked("first_radau_contact", str(prepared.deferred_routines.get("cmm2_radau_dense")), "deferred integration"),
        _blocked("native terminal guard historical path", "NOT ESTABLISHED", "pre-call"),
        _blocked("applicability review", "UNREVIEWED", "pre-call"),
    ]
    if prepared.initial_arguments.get("time_s") != "0x0.0p+0":
        unmet.append(_blocked("time_s", str(prepared.initial_arguments.get("time_s")), "pre-call"))
    if correspondence != "MATCH":
        unmet.append(_blocked("loaded probe-image correspondence", "NOT ESTABLISHED", "pre-call"))
    for row in graph:
        if row["classification"] != "MATCH":
            unmet.append(_blocked(str(row["qualname"]), str(row["classification"]), "pre-call"))
    for name in admission.historical_source_mismatches:
        unmet.append(_blocked(f"historical source {name}", "MISMATCH", "pre-call"))
    for name in prepared.applicability.get("historical_mismatches") or []:
        unmet.append(_blocked(str(name), "MISMATCH", "pre-call"))
    justified = [
        {
            "qualname": row["qualname"],
            "family": row["family"],
            "proof_role": row["proof_role"],
            "clears_other_rows": False,
            "current_runtime": current,
        }
        for row in graph
        if row["classification"] == "MATCH" and current
    ]
    runtime = {
        "current": current,
        "kind": native.get("kind") if current else "NOT CURRENT",
        "pid": prepared.pid,
        "thread_id": prepared.thread_id,
        "measurement_image": current_measurement,
        "loaded_code_correspondence": correspondence,
        "test_double_is_measurement_evidence": False,
        "archived_json_is_measurement_evidence": False,
        "cosine_function_calls": native.get("cosine_function_calls", 0) if current else 0,
    }
    retained = {
        "role": "current" if current else "historical/unvalidated",
        "revalidation": checked.classification,
        "original_pid": prepared.pid,
        "original_thread_id": prepared.thread_id,
        "measurement_image": dict(measurement) if isinstance(measurement, dict) else {},
    }
    return {
        "status": CONTRACT_BLOCKED,
        "authorizes_execution": False,
        "eligibility_evidence": False,
        "physical_qualification": False,
        "candidate29_disposition": CANDIDATE29_DISPOSITION,
        "accepted_repair": {
            "head": ACCEPTED_REPAIR_HEAD,
            "tree": ACCEPTED_REPAIR_TREE,
            "scope": "input, argument, and global-classification repair",
        },
        "frozen_technical_authority": {
            "technical_head": TECHNICAL_HEAD,
            "policy_bundle_sha256": admission.policy_bundle_sha256,
            "policy_bundle": admission.policy_bundle,
        },
        "historical_certificate_hypotheses": {
            "source_mismatches": list(admission.historical_source_mismatches),
            "native_comparison": prepared.applicability.get("historical_mismatches"),
            "ulp_path": _historical_ulp(root),
            "implementation": _implementation_rebinding(root),
            "exact_equality_assumed": False,
            "equivalence_assumed": False,
        },
        "current_implementation": {
            "checkout_sha": admission.executing_head,
            "operation_graph": graph,
            "module_digest_clears_any_row": False,
            "filename_clears_any_row": False,
            "current_runtime": current,
        },
        "binding_revalidation": checked.classification,
        "serialized_record_is_a_live_binding": True,
        "genuine_runtime_observations": runtime,
        "retained_observation": retained,
        "justified_correspondence": justified,
        "unmet_hypotheses": unmet,
        "time_s": prepared.initial_arguments.get("time_s"),
        "post_return": dict(prepared.post_return),
        "dependent_counters": dict(prepared.dependent_counters),
        "archived_record_authorizes_later_process": False,
        "deferred_radau_is_prerequisite_for_isolated_source_attempt": False,
        "post_return_demanded_before_existence": False,
    }
