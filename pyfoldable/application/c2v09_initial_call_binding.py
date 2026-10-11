"""Bind the pending initial-call evaluator without invoking it.

Declaration defaults and caller claims are not the actual inputs. Deferred
Radau and integration routines stay uncleared. Applicability stays blocked.
"""

from __future__ import annotations

import json
import math
import os
import platform
import sys
import types
from decimal import Decimal, InvalidOperation
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping

from pyfoldable.application.c2v09_binding_collector import collect_binding_record
from pyfoldable.application.c2v09_cosine_path_certificate import prepare_cosine_path_certificate
from pyfoldable.application.c2v09_declared_operations import (
    capture_operation_bindings,
    operation_bindings_hold,
    resolve_qualname,
)
from pyfoldable.application.c2v09_ordered_declaration import (
    CANDIDATE29_DISPOSITION,
    _json_fence,
    _read_text,
    historical_manifest_bytes,
    sha256_bytes,
)
from pyfoldable.application.c2v09_pre_call_admission import (
    PreCallAdmission,
    _certificate_obligations,
    compare_native_obligations,
    prepare_pre_call_admission,
)
from pyfoldable.application.c2v09_pre_call_binding import (
    MAPPER_BINDING,
    SOURCE_BINDING,
    _code_for_qualname,
    _thread_id,
    compare_code_structure,
    compare_signature_defaults,
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
from pyfoldable.dynamics.cmm2_radau_dense import first_radau_contact


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


INITIAL_TRANSACTION_TIME_HEX = "0x0.0p+0"
INITIAL_TIME_RATIONALE = (
    "The isolated initial transaction uses the integrator origin: absolute time "
    "is the first immutable actuation knot plus a zero relative time. The "
    "authorized declaration is +0.0 s only when that knot has the same binary64 "
    "bits. The knot list is not sole authority."
)


def _knot_hex(value: object) -> str | None:
    """Binary64 text only when the knot is that exact value."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    if isinstance(value, str):
        try:
            exact = Decimal(value)
            parsed = float(value)
        except (ValueError, InvalidOperation, OverflowError):
            return None
        if not math.isfinite(parsed) or exact != Decimal.from_float(parsed):
            return None
        return binary64_hex(parsed)
    if isinstance(value, int):
        try:
            parsed = float(value)
        except OverflowError:
            return None
        if not math.isfinite(parsed) or int(parsed) != value:
            return None
        return binary64_hex(parsed)
    if not math.isfinite(value):
        return None
    return binary64_hex(value)


def declare_initial_transaction_time(effective: Mapping[str, object]) -> dict[str, object]:
    """Declare +0.0 s only when the immutable manifest knot agrees."""
    actuation = effective.get("actuation")
    knots = actuation.get("time_s") if isinstance(actuation, Mapping) else None
    knot_hex = None
    if isinstance(knots, list) and knots:
        knot_hex = _knot_hex(knots[0])
    conflict = knot_hex != INITIAL_TRANSACTION_TIME_HEX
    return {
        "declared_hex": INITIAL_TRANSACTION_TIME_HEX,
        "manifest_first_knot_hex": knot_hex,
        "conflict": conflict,
        "used": not conflict,
        "time_s_hex": "NOT ESTABLISHED" if conflict else INITIAL_TRANSACTION_TIME_HEX,
        "knot_is_sole_authority": False,
        "governing_rationale": INITIAL_TIME_RATIONALE,
    }


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


def _consumed_active(qualname: str, fallback: object) -> object:
    """Call-site callee when this qualname is declared; otherwise the supplied callable."""
    resolved = resolve_qualname(qualname)
    if resolved is None:
        return fallback
    return resolved.callee


def _compare_active(root: Path) -> list[dict[str, object]]:
    rows = []
    for path, qualname, function in _ACTIVE_CODE:
        function = _consumed_active(qualname, function)
        source_path = root / path
        classification = "NOT ESTABLISHED"
        defaults = "NOT ESTABLISHED"
        if source_path.is_file() and hasattr(function, "__code__"):
            text = source_path.read_text(encoding="utf-8")
            compiled = compile(text, str(source_path), "exec", dont_inherit=True, optimize=sys.flags.optimize)
            expected = _code_for_qualname(compiled, qualname)
            if expected is not None:
                classification = compare_code_structure(function.__code__, expected)
            defaults = compare_signature_defaults(function, text, qualname)
        referenced = _referenced_globals(root, function)
        if "MISMATCH" in (classification, defaults, referenced):
            overall = "MISMATCH"
        elif "NOT ESTABLISHED" in (classification, defaults, referenced):
            overall = "NOT ESTABLISHED"
        else:
            overall = "MATCH"
        rows.append(
            {
                "qualname": qualname,
                "path": path,
                "classification": overall,
                "defaults": defaults,
                "constants": classification,
                "nested_code": classification,
                "globals": referenced,
                "role": "active initial graph",
            }
        )
    return rows


def _nested_codes(code: types.CodeType) -> list[types.CodeType]:
    found = [code]
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            found.extend(_nested_codes(const))
    return found


def _global_token(value: object) -> object:
    if isinstance(value, types.FunctionType):
        return ("function", value, value.__code__)
    if isinstance(value, float):
        return ("float", binary64_hex(value))
    if value is None or isinstance(value, (bool, int, str, bytes)):
        return ("literal", value)
    if isinstance(value, type):
        return ("type", value)
    return ("object", value)


def _callable_globals(function: object) -> dict[str, object]:
    code = getattr(function, "__code__", None)
    namespace = getattr(function, "__globals__", None)
    if not isinstance(code, types.CodeType) or not isinstance(namespace, dict):
        return {}
    names: set[str] = set()
    for nested in _nested_codes(code):
        names.update(str(name) for name in nested.co_names)
    snapshot = {}
    for name in names:
        if name not in namespace or isinstance(namespace[name], types.ModuleType):
            continue
        snapshot[name] = _global_token(namespace[name])
    return snapshot


def _in_repository(root: Path, filename: object) -> bool:
    if not isinstance(filename, str) or not filename:
        return False
    try:
        Path(filename).resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return Path(filename).is_file()


def _callee_source(root: Path, function: object) -> str:
    """Loaded callee code against its file. Modules outside this repository are skipped."""
    code = getattr(function, "__code__", None)
    if not isinstance(code, types.CodeType) or not _in_repository(root, code.co_filename):
        return "SKIP"
    qualname = getattr(code, "co_qualname", code.co_name)
    compiled = compile(
        Path(code.co_filename).read_text(encoding="utf-8"),
        code.co_filename,
        "exec",
        dont_inherit=True,
        optimize=sys.flags.optimize,
    )
    expected = _code_for_qualname(compiled, qualname)
    if expected is None:
        return "NOT ESTABLISHED"
    return compare_code_structure(code, expected)


def _referenced_globals(root: Path, function: object) -> str:
    namespace = getattr(function, "__globals__", None)
    code = getattr(function, "__code__", None)
    if not isinstance(namespace, dict) or not isinstance(code, types.CodeType):
        return "NOT ESTABLISHED"
    state = "MATCH"
    for name, token in _callable_globals(function).items():
        if not isinstance(token, tuple) or token[0] != "function":
            continue
        compared = _callee_source(root, token[1])
        if compared == "SKIP":
            continue
        if compared == "MISMATCH":
            return "MISMATCH"
        if compared != "MATCH":
            state = "NOT ESTABLISHED"
    return state


def _default_snapshot(function: object) -> dict[str, object]:
    keywords = getattr(function, "__kwdefaults__", None)
    return {
        "defaults": getattr(function, "__defaults__", None),
        "kwdefaults": None if keywords is None else dict(keywords),
    }


def _sequence_hex(values: object) -> list[str]:
    if not isinstance(values, tuple):
        raise TypeError("expected a retained numeric tuple")
    return [binary64_hex(value) for value in values]


def _optional_hex(value: float | None) -> str | None:
    if value is None:
        return None
    return binary64_hex(value)


def _frozen(value: object) -> object:
    """Immutable snapshot. Floats keep their binary64 sign bit."""
    if isinstance(value, float):
        return ("binary64", binary64_hex(value))
    if value is None or isinstance(value, (bool, int, str, bytes)):
        return value
    if isinstance(value, (list, tuple)):
        return tuple(_frozen(item) for item in value)
    if isinstance(value, Mapping):
        return tuple(sorted((str(key), _frozen(item)) for key, item in value.items()))
    return ("unsupported", type(value).__name__)


def _input_fingerprint(evaluator: Cmm2FoldableBemMappedAeroEvaluator) -> dict[str, object]:
    """Live field values. Object identity does not cover in-place writes."""
    blade = evaluator.blade
    environment = evaluator.environment
    annulus = evaluator.settings.annulus_settings
    rotation = annulus.rotational_augmentation
    return {
        "bounds": evaluator.bounds,
        "diameter_hex": binary64_hex(blade.diameter_m),
        "hub_hex": binary64_hex(blade.hub_radius_m),
        "blade_count": blade.blade_count,
        "stations": [
            {
                "r_over_R": binary64_hex(station.r_over_R),
                "chord_m": binary64_hex(station.chord_m),
                "twist_rad": binary64_hex(station.twist_rad),
                "airfoil_id": station.airfoil_id,
            }
            for station in blade.stations
        ],
        "polar_schedule_id": evaluator.polars.id,
        "polars": [
            {
                "r_over_R": binary64_hex(anchor.r_over_R),
                "tables": [
                    {
                        "airfoil_id": table.airfoil_id,
                        "reynolds_hex": binary64_hex(table.reynolds),
                        "mach_hex": binary64_hex(table.mach),
                        "alpha": _sequence_hex(table.alpha_rad),
                        "cl": _sequence_hex(table.cl),
                        "cd": _sequence_hex(table.cd),
                        "cm": _sequence_hex(table.cm),
                        "source": table.source,
                        "scenario_id": table.scenario_id,
                        "metadata": _frozen(dict(table.metadata)),
                    }
                    for table in anchor.family.tables
                ],
            }
            for anchor in evaluator.polars.anchors
        ],
        "bem": {
            "annulus_count": evaluator.settings.annulus_count,
            "radial_domain": evaluator.settings.radial_domain,
            "bracket_samples": annulus.bracket_samples,
            "max_iterations": annulus.max_iterations,
            "angle_tolerance_hex": binary64_hex(annulus.angle_tolerance_rad),
            "residual_tolerance_hex": binary64_hex(annulus.residual_tolerance_m2_s),
            "relative_residual_tolerance_hex": binary64_hex(annulus.relative_residual_tolerance),
            "minimum_tip_loss_factor_hex": binary64_hex(annulus.minimum_tip_loss_factor),
            "include_tip_loss": annulus.include_tip_loss,
            "include_root_loss": annulus.include_root_loss,
            "loading_branch": annulus.loading_branch,
            "rotational_augmentation": {
                "kind": rotation.kind,
                "lift_curve_slope_hex": _optional_hex(rotation.lift_curve_slope_per_rad),
                "zero_lift_angle_hex": _optional_hex(rotation.zero_lift_angle_rad),
                "maximum_chord_over_radius_hex": binary64_hex(rotation.maximum_chord_over_radius),
                "maximum_absolute_alpha_hex": binary64_hex(rotation.maximum_absolute_alpha_rad),
            },
        },
        "environment": {
            "id": environment.id,
            "forward_speed_m_s": binary64_hex(environment.forward_speed_m_s),
            "air_density_kg_m3": binary64_hex(environment.air_density_kg_m3),
            "dynamic_viscosity_pa_s": binary64_hex(environment.dynamic_viscosity_pa_s),
            "temperature_k": binary64_hex(environment.temperature_k),
            "pressure_pa": binary64_hex(environment.pressure_pa),
        },
    }


def _document_alpha_hex(document: Mapping[str, object]) -> list[str] | None:
    anchors = document.get("anchors")
    if not isinstance(anchors, list):
        return None
    values = []
    for anchor in anchors:
        if not isinstance(anchor, Mapping):
            return None
        family = anchor.get("family")
        if not isinstance(family, Mapping) or not isinstance(family.get("tables"), list):
            return None
        for table in family["tables"]:
            if not isinstance(table, Mapping) or not isinstance(table.get("alpha_rad"), list):
                return None
            values.extend(binary64_hex(float(value)) for value in table["alpha_rad"])
    return values


def _correspondence(
    *,
    hinge: float,
    manifest_hinge: float,
    bounds: str,
    manifest_bounds: object,
    polars: SpanwisePolarSchedule,
    polar_document: Mapping[str, object],
    environment: CoupledEnvironment,
    environment_document: Mapping[str, object],
) -> str:
    """Parsed objects agree with the manifest. A hash match alone is not that agreement."""
    document_alpha = _document_alpha_hex(polar_document)
    density = environment_document.get("air_density_kg_m3")
    agreed = (
        binary64_hex(hinge) == binary64_hex(manifest_hinge)
        and bounds == manifest_bounds
        and document_alpha is not None
        and document_alpha == _polar_alpha_hex(polars)
        and isinstance(density, (int, float))
        and not isinstance(density, bool)
        and binary64_hex(environment.air_density_kg_m3) == binary64_hex(float(density))
    )
    return "MATCH" if agreed else "MISMATCH"


def _polar_alpha_hex(polars: SpanwisePolarSchedule) -> list[str]:
    values = []
    for anchor in polars.anchors:
        for table in anchor.family.tables:
            values.extend(binary64_hex(value) for value in table.alpha_rad)
    return values


def _valid_digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _unestablished_native() -> dict[str, object]:
    return {
        "kind": "test_double",
        "wrapper_address": None,
        "plt_stub": None,
        "got_slot": None,
        "selected_address": None,
        "evidence": None,
        "loaded_body_sha256": None,
        "loaded_constants": None,
        "compiled_probe_image_sha256": None,
        "measurement_image": {
            "file_image_identity": "NOT ESTABLISHED",
            "loaded_code_correspondence": "NOT ESTABLISHED",
            "handle_associated": False,
            "second_compilation_is_evidence": False,
            "source_hash_is_the_image": False,
        },
        "probe_source_sha256": None,
        "controls": {"classification": "NOT ESTABLISHED"},
        "cosine_function_calls": 0,
        "ld_bind_now": os.environ.get("LD_BIND_NOW"),
        "pid": os.getpid(),
        "thread_id": _thread_id(),
        "attribution": "NOT ESTABLISHED",
        "comparison": {},
        "os": {"system": platform.system(), "machine": platform.machine()},
    }


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _fresh_native(root: Path, observer: Callable[[Path], object]) -> dict[str, object]:
    """This process's probe only. A substitute callable is not that probe."""
    if observer is not prepare_cosine_path_certificate:
        return _unestablished_native()
    try:
        observed = observer(root)
        payload = _mapping(observed.get("canonical_payload") if isinstance(observed, Mapping) else None)
        selected = _mapping(payload.get("selected_call_target"))
        wrapper = _mapping(payload.get("python_wrapper"))
        body = _mapping(payload.get("loaded_body"))
        controls = _mapping(payload.get("numerical_controls_and_features"))
        collected = collect_binding_record(root)["canonical_payload"]["executing_dependencies"]
        libraries = {
            name: _mapping(collected.get(name)).get("file_sha256")
            for name in ("libm", "libc", "loader")
        }
        source_sha = payload.get("probe_source_sha256")
        measurement = _mapping(payload.get("measurement_image"))
        image = measurement.get("file_image_sha256")
        image_ok = (
            _valid_digest(image)
            and image != source_sha
            and measurement.get("handle_associated") is True
            and measurement.get("second_compilation_is_evidence") is False
            and measurement.get("source_hash_is_the_image") is False
            and measurement.get("read_state_calls") == 1
        )
        compared = compare_native_obligations(
            {
                "loaded_body": body,
                "numerical_controls_and_features": controls,
                "python_wrapper": wrapper,
                "executable": _mapping(payload.get("executable")),
                "libraries": libraries,
                "loaded_constants": payload.get("loaded_constants"),
                "got_slot": selected.get("got_slot"),
            },
            _certificate_obligations(root),
        )
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, AttributeError):
        failed = _unestablished_native()
        failed["kind"] = "genuine"
        return failed
    observed_target = (
        selected.get("classification") == "OBSERVED"
        and selected.get("evidence") == "python wrapper plt got"
        and selected.get("independent_cdll_is_evidence") is False
        and isinstance(selected.get("address"), str)
        and isinstance(selected.get("got_slot"), str)
        and isinstance(selected.get("plt_stub"), str)
        and image_ok
        and payload.get("cosine_function_calls") == 0
    )
    return {
        "kind": "genuine",
        "wrapper_address": wrapper.get("address"),
        "plt_stub": selected.get("plt_stub"),
        "got_slot": selected.get("got_slot"),
        "selected_address": selected.get("address") if observed_target else None,
        "evidence": selected.get("evidence") if observed_target else None,
        "loaded_body_sha256": body.get("sha256"),
        "loaded_constants": payload.get("loaded_constants"),
        "compiled_probe_image_sha256": image if image_ok else None,
        "probe_source_sha256": source_sha if isinstance(source_sha, str) else None,
        "measurement_image": dict(measurement) if image_ok else {
            "file_image_identity": "NOT ESTABLISHED",
            "loaded_code_correspondence": measurement.get("loaded_code_correspondence", "NOT ESTABLISHED"),
            "handle_associated": False,
            "second_compilation_is_evidence": False,
            "source_hash_is_the_image": False,
        },
        "controls": {
            "classification": controls.get("classification"),
            "mxcsr": controls.get("mxcsr"),
            "fegetround": controls.get("fegetround"),
            "xcr0": controls.get("xcr0"),
            "x87_control": controls.get("x87_control"),
        },
        "cosine_function_calls": 0 if payload.get("cosine_function_calls") == 0 else payload.get("cosine_function_calls"),
        "ld_bind_now": payload.get("ld_bind_now"),
        "pid": os.getpid(),
        "thread_id": _thread_id(),
        "attribution": "wrapper plt got" if observed_target else "NOT ESTABLISHED",
        "comparison": compared,
        "runtime_correspondence": dict(_mapping(payload.get("runtime_correspondence"))),
        "os": {"system": platform.system(), "machine": platform.machine()},
    }


def _applicability(native: Mapping[str, object]) -> dict[str, object]:
    comparison = _mapping(native.get("comparison"))
    return {
        "status": CONTRACT_BLOCKED,
        "review_status": "UNREVIEWED",
        "native_is_genuine": native.get("kind") == "genuine",
        "exact_historical_equality_assumed": False,
        "equivalence_assumed": False,
        "body_match_clears_xcr0": False,
        "body_match_clears_wrapper": False,
        "body_match_clears_executable": False,
        "proof_roles": {
            "exact_historical_equality": "NOT A PROOF",
            "equivalence": "NOT A PROOF",
            "body_match": "historical libm body predicate only",
            "compiled_probe_image": "file digest of the probe image whose read_state ran in this observation; not a second compilation and not the C source hash",
            "wrapper_plt_got": "this process selected cosine target; not a historical address",
        },
        "body_match_proof_role": "historical libm body predicate only; not wrapper, GOT, executable, library, or XCR0 identity",
        "historical_mismatches": list(comparison.get("mismatches") or []),
        "historical_xcr0": comparison.get("historical_xcr0", {"classification": "NOT ESTABLISHED"}),
        "loaded_body": comparison.get("loaded_body", {"classification": "NOT ESTABLISHED"}),
        "eligibility_evidence": False,
        "unreviewed_applicability": CONTRACT_BLOCKED,
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
    source_root: Path
    native_observer: Callable[[Path], object]
    revalidation_classification: str = "NOT ESTABLISHED"
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
    native_observer: Callable[[Path], object] = prepare_cosine_path_certificate,
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
    recipe = manifest["source_recipe"]
    if not isinstance(recipe, Mapping):
        raise TypeError("candidate29 source recipe is not an object")
    draft_bytes = str(manifest["draft_toml"]).encode("utf-8")
    recipe_bytes = historical_manifest_bytes(dict(recipe))
    if sha256_bytes(draft_bytes) != effective["draft_sha256"] or sha256_bytes(recipe_bytes) != effective["source_sha256"]:
        raise RuntimeError("candidate29 draft or source recipe bytes do not match the manifest")
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
        "draft_bytes_sha256": sha256_bytes(draft_bytes),
        "source_recipe_bytes_sha256": sha256_bytes(recipe_bytes),
        "parsed_correspondence": _correspondence(
            hinge=hinge,
            manifest_hinge=manifest_hinge,
            bounds=evaluator.bounds,
            manifest_bounds=effective["bounds"],
            polars=polars,
            polar_document=polars_document,
            environment=environment,
            environment_document=environment_document,
        ),
        "polar_alpha_hex": _polar_alpha_hex(polars),
        "environment_air_density_hex": binary64_hex(environment.air_density_kg_m3),
        "fingerprint": _frozen(_input_fingerprint(evaluator)),
        "evidence_role": "parsed draft and verified manifest bytes",
    }
    time_declaration = declare_initial_transaction_time(effective)
    arguments = {
        "time_s": time_declaration["time_s_hex"],
        "time_declaration": {
            "declared_hex": time_declaration["declared_hex"],
            "manifest_first_knot_hex": time_declaration["manifest_first_knot_hex"],
            "conflict": time_declaration["conflict"],
            "used": time_declaration["used"],
            "knot_is_sole_authority": False,
            "governing_rationale": time_declaration["governing_rationale"],
        },
        "theta_rad_hex": binary64_hex(float(effective["initial_angle_rad"])),
        "theta_dot_rad_s_hex": binary64_hex(float(effective["initial_angular_velocity_rad_s"])),
        "omega_rad_s_hex": binary64_hex(float(effective["initial_omega_rad_s"])),
    }
    argument_snapshot = _frozen(arguments)
    native = _fresh_native(root, native_observer)
    bound = InitialCallBinding(
        evaluator,
        {
            "blade": evaluator.blade,
            "polars": evaluator.polars,
            "settings": evaluator.settings,
            "environment": evaluator.environment,
            "draft_bytes": draft_bytes,
            "source_recipe_bytes": recipe_bytes,
            SOURCE_BINDING: evaluator.__call__.__globals__.get(SOURCE_BINDING),
            MAPPER_BINDING: evaluator.__call__.__globals__.get(MAPPER_BINDING),
            "__call__": Cmm2FoldableBemMappedAeroEvaluator.__call__,
            "__call_code__": evaluator.__call__.__code__,
            "active_codes": {qualname: _consumed_active(qualname, function).__code__ for _path, qualname, function in _ACTIVE_CODE},
            "defaults": {qualname: _default_snapshot(_consumed_active(qualname, function)) for _path, qualname, function in _ACTIVE_CODE},
            "globals": {qualname: _callable_globals(_consumed_active(qualname, function)) for _path, qualname, function in _ACTIVE_CODE},
            "initial_argument_snapshot": argument_snapshot,
            "input_fingerprint": identity["fingerprint"],
            "operation_bindings": capture_operation_bindings(),
        },
        identity,
        dict(arguments),
        _compare_active(root),
        {
            "solve_cmm2_transient": "NOT CLEARED",
            "cmm2_radau_dense": "NOT CLEARED",
            "clearance_granted": False,
            "retained_callable_is_not_a_clearance": solve_cmm2_transient,
            "retained_radau_contact_is_not_a_clearance": first_radau_contact,
        },
        _applicability(native),
        native,
        {"returned_source_object": POST_RETURN_ONLY, "mapped_interval_consumption": POST_RETURN_ONLY},
        prepared,
        dict(caller_claims or {}),
        "not actual-input evidence",
        CANDIDATE29_DISPOSITION,
        os.getpid(),
        _thread_id(),
        root,
        native_observer,
    )
    bound.revalidation_classification = revalidate_initial_call_binding(bound).classification
    return bound


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
    if sha256_bytes(value.retained["draft_bytes"]) != value.input_identity["draft_bytes_sha256"]:
        return InitialCallRevalidation("INVALIDATED")
    if sha256_bytes(value.retained["source_recipe_bytes"]) != value.input_identity["source_recipe_bytes_sha256"]:
        return InitialCallRevalidation("INVALIDATED")
    if _polar_alpha_hex(evaluator.polars) != value.input_identity["polar_alpha_hex"]:
        return InitialCallRevalidation("INVALIDATED")
    if binary64_hex(evaluator.environment.air_density_kg_m3) != value.input_identity["environment_air_density_hex"]:
        return InitialCallRevalidation("INVALIDATED")
    for path, qualname, function in _ACTIVE_CODE:
        function = _consumed_active(qualname, function)
        if function.__code__ is not value.retained["active_codes"][qualname]:
            return InitialCallRevalidation("INVALIDATED")
        defaults = value.retained["defaults"][qualname]
        if function.__defaults__ != defaults["defaults"] or function.__kwdefaults__ != defaults["kwdefaults"]:
            return InitialCallRevalidation("INVALIDATED")
        source_path = Path(value.source_root) / path
        if not source_path.is_file():
            return InitialCallRevalidation("INVALIDATED")
        if compare_signature_defaults(function, source_path.read_text(encoding="utf-8"), qualname) != "MATCH":
            return InitialCallRevalidation("INVALIDATED")
        current = _callable_globals(function)
        snapshot = value.retained["globals"][qualname]
        if current != snapshot:
            return InitialCallRevalidation("INVALIDATED")
    if not operation_bindings_hold(value.retained.get("operation_bindings")):
        return InitialCallRevalidation("INVALIDATED")
    if _frozen(_input_fingerprint(evaluator)) != value.retained["input_fingerprint"]:
        return InitialCallRevalidation("INVALIDATED")
    if not isinstance(value.initial_arguments, Mapping) or _frozen(value.initial_arguments) != value.retained["initial_argument_snapshot"]:
        return InitialCallRevalidation("INVALIDATED")
    if not _native_continuous(value):
        return InitialCallRevalidation("INVALIDATED")
    return InitialCallRevalidation("REVALIDATED")


def _native_continuous(value: InitialCallBinding) -> bool:
    """Re-read a genuine probe. A test double is not promoted by staying unchanged."""
    retained = value.native_observation
    if retained.get("kind") != "genuine":
        return True
    fresh = _fresh_native(Path(value.source_root), value.native_observer)
    if fresh.get("kind") != "genuine" or fresh.get("attribution") != retained.get("attribution"):
        return False
    for key in ("wrapper_address", "plt_stub", "got_slot", "selected_address", "evidence", "loaded_body_sha256"):
        if fresh.get(key) != retained.get(key):
            return False
    if fresh.get("controls") != retained.get("controls") or fresh.get("cosine_function_calls") != 0:
        return False
    return _valid_digest(fresh.get("compiled_probe_image_sha256"))


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
