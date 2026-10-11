"""Live call-site bindings for the declared initial-operation graph.

Import-time callables are not the consumed path. Properties are read from the
class dictionary, so the descriptor protocol does not run.
"""

from __future__ import annotations

import dis
import sys
import types
from dataclasses import dataclass
from pathlib import Path

from pyfoldable.application.c2v09_pre_call_binding import (
    _code_for_qualname,
    compare_code_structure,
    compare_signature_defaults,
)


@dataclass(frozen=True)
class OperationSpec:
    """One consumed operation and the namespace that actually looks it up."""

    path: str
    qualname: str
    source_qualname: str
    namespace_module: str
    attribute: str
    operation: str
    family: str
    owner: str | None = None
    required_names: tuple[str, ...] = ()
    required_varnames: tuple[str, ...] = ()
    required_constants: tuple[object, ...] = ()


@dataclass(frozen=True)
class ResolvedOperation:
    """Descriptor and callee captured without calling the operation."""

    spec: OperationSpec
    descriptor: object
    callee: types.FunctionType

    @property
    def code(self) -> types.CodeType:
        return self.callee.__code__


def _operation(
    path: str,
    qualname: str,
    namespace_module: str,
    attribute: str,
    operation: str,
    family: str,
    *,
    owner: str | None = None,
    source_qualname: str | None = None,
    required_names: tuple[str, ...] = (),
    required_varnames: tuple[str, ...] = (),
    required_constants: tuple[object, ...] = (),
) -> OperationSpec:
    return OperationSpec(
        path=path,
        qualname=qualname,
        source_qualname=source_qualname if source_qualname is not None else qualname,
        namespace_module=namespace_module,
        attribute=attribute,
        operation=operation,
        family=family,
        owner=owner,
        required_names=required_names,
        required_varnames=required_varnames,
        required_constants=required_constants,
    )


_SERVICE = "pyfoldable.application.cmm2_coupled_transient_service"
_ROTOR = "pyfoldable.core.foldable_rotor"
_AERO = "pyfoldable.core.foldable_aero_load"
_BEM = "pyfoldable.core.bem_rotor"
_DRAFT = "pyfoldable.application.mechanism_binding"
_MODELS = "pyfoldable.core.models"
_POLAR = "pyfoldable.core.polar"
_SPAN = "pyfoldable.core.polar_spanwise"

OPERATION_SPECS: tuple[OperationSpec, ...] = (
    _operation(
        "pyfoldable/application/cmm2_coupled_transient_service.py",
        "Cmm2FoldableBemMappedAeroEvaluator.__init__",
        _SERVICE,
        "__init__",
        "evaluator construction",
        "transaction",
        owner="Cmm2FoldableBemMappedAeroEvaluator",
    ),
    _operation(
        "pyfoldable/application/cmm2_coupled_transient_service.py",
        "Cmm2FoldableBemMappedAeroEvaluator.__call__",
        _SERVICE,
        "__call__",
        "evaluator call",
        "transaction",
        owner="Cmm2FoldableBemMappedAeroEvaluator",
    ),
    _operation(
        "pyfoldable/core/foldable_rotor.py",
        "solve_foldable_bem_rotor",
        _SERVICE,
        "solve_foldable_bem_rotor",
        "source call",
        "transaction",
    ),
    _operation(
        "pyfoldable/core/foldable_aero_load.py",
        "map_foldable_bem_aero_loads",
        _SERVICE,
        "map_foldable_bem_aero_loads",
        "mapper call",
        "transaction",
    ),
    _operation(
        "pyfoldable/core/config.py",
        "load_design_config",
        _DRAFT,
        "load_design_config",
        "draft parse",
        "transaction",
    ),
    _operation(
        "pyfoldable/core/foldable_rotor.py",
        "FoldableRotorState.angle_from_deployed_rad",
        _ROTOR,
        "angle_from_deployed_rad",
        "angle from deployed",
        "geometric lemma",
        owner="FoldableRotorState",
    ),
    _operation(
        "pyfoldable/core/models.py",
        "BladeGeometry.radius_m",
        _MODELS,
        "radius_m",
        "blade radius consumed by the kernel-radius product",
        "geometric lemma",
        owner="BladeGeometry",
    ),
    _operation(
        "pyfoldable/core/foldable_rotor.py",
        "FoldableBladeProjection.fixed_limit_equivalent",
        _ROTOR,
        "fixed_limit_equivalent",
        "fixed-limit projection identity",
        "geometric lemma",
        owner="FoldableBladeProjection",
    ),
    _operation(
        "pyfoldable/core/foldable_rotor.py",
        "FoldableBladeProjection.effective_radius_for_nominal",
        _ROTOR,
        "effective_radius_for_nominal",
        "nominal-to-effective radius",
        "geometric lemma",
        owner="FoldableBladeProjection",
    ),
    _operation(
        "pyfoldable/core/foldable_rotor.py",
        "project_foldable_blade",
        _ROTOR,
        "project_foldable_blade",
        "source cosine projection",
        "geometric lemma",
    ),
    _operation(
        "pyfoldable/core/foldable_rotor.py",
        "project_foldable_blade.kernel_radius",
        _ROTOR,
        "project_foldable_blade",
        "kernel-radius product q*R, distinct from the annulus midpoint",
        "geometric lemma",
        source_qualname="project_foldable_blade",
        required_names=("radius_m",),
    ),
    _operation(
        "pyfoldable/core/foldable_rotor.py",
        "project_spanwise_polar_schedule",
        _ROTOR,
        "project_spanwise_polar_schedule",
        "spanwise anchor projection",
        "geometric lemma",
    ),
    _operation(
        "pyfoldable/core/foldable_aero_load.py",
        "_projection_factor",
        _AERO,
        "_projection_factor",
        "mapper cosine input",
        "geometric lemma",
    ),
    _operation(
        "pyfoldable/core/foldable_rotor.py",
        "_station_at_hinge",
        _ROTOR,
        "_station_at_hinge",
        "hinge station construction",
        "geometric lemma",
    ),
    _operation(
        "pyfoldable/core/bem_rotor.py",
        "_radial_limits",
        _BEM,
        "_radial_limits",
        "radial domain construction",
        "geometric lemma",
    ),
    _operation(
        "pyfoldable/core/bem_rotor.py",
        "solve_bem_rotor.annulus_edge",
        _ROTOR,
        "solve_bem_rotor",
        "annulus edge construction inside solve_bem_rotor",
        "geometric lemma",
        source_qualname="solve_bem_rotor",
        required_names=("_radial_limits",),
        required_varnames=("inner", "outer"),
    ),
    _operation(
        "pyfoldable/core/bem_rotor.py",
        "solve_bem_rotor.midpoint",
        _ROTOR,
        "solve_bem_rotor",
        "annulus midpoint construction inside solve_bem_rotor",
        "geometric lemma",
        source_qualname="solve_bem_rotor",
        required_names=("_interpolate_station", "radius_m"),
        required_varnames=("midpoint",),
        required_constants=(0.5,),
    ),
    _operation(
        "pyfoldable/core/bem_rotor.py",
        "_interpolate_station",
        _BEM,
        "_interpolate_station",
        "normalized radial query",
        "geometric lemma",
    ),
    _operation(
        "pyfoldable/core/polar.py",
        "PolarFamily.query",
        _POLAR,
        "query",
        "polar query branches",
        "geometric lemma",
        owner="PolarFamily",
    ),
    _operation(
        "pyfoldable/core/polar_spanwise.py",
        "SpanwisePolarSchedule.section",
        _SPAN,
        "section",
        "spanwise normalized query",
        "geometric lemma",
        owner="SpanwisePolarSchedule",
    ),
    _operation(
        "pyfoldable/core/foldable_aero_load.py",
        "projected_radius_m",
        _AERO,
        "projected_radius_m",
        "mapper projected radius",
        "geometric lemma",
    ),
    _operation(
        "pyfoldable/core/foldable_aero_load.py",
        "map_projected_material_loads",
        _AERO,
        "map_projected_material_loads",
        "mapper interval ownership",
        "geometric lemma",
    ),
    _operation(
        "pyfoldable/core/foldable_aero_load.py",
        "_native_terminal_annuli",
        _AERO,
        "_native_terminal_annuli",
        "python terminal-guard helper",
        "native terminal guard",
    ),
    _operation(
        "pyfoldable/core/bem.py",
        "solve_bem_annulus.kernel_radius",
        _BEM,
        "solve_bem_annulus",
        "annulus kernel radius station.r_over_R * blade.radius_m",
        "geometric lemma",
        source_qualname="solve_bem_annulus",
        required_names=("radius_m",),
    ),
    _operation(
        "pyfoldable/core/bem_rotor.py",
        "solve_bem_rotor",
        _ROTOR,
        "solve_bem_rotor",
        "bem numerical solution",
        "bem numerical dependency",
    ),
)

REQUIRED_GRAPH_QUALNAMES: tuple[str, ...] = tuple(spec.qualname for spec in OPERATION_SPECS) + ("math.ulp",)
DECLARED_QUALNAMES = frozenset(spec.qualname for spec in OPERATION_SPECS)
ARITHMETIC_QUALNAMES: tuple[str, ...] = (
    "FoldableRotorState.angle_from_deployed_rad",
    "BladeGeometry.radius_m",
    "project_foldable_blade.kernel_radius",
    "solve_bem_annulus.kernel_radius",
    "solve_bem_rotor.annulus_edge",
    "solve_bem_rotor.midpoint",
)


def resolve_operation(spec: OperationSpec) -> ResolvedOperation | None:
    """Read the call-site namespace. Do not evaluate a property."""
    module = sys.modules.get(spec.namespace_module)
    if module is None:
        return None
    namespace = module.__dict__
    if spec.owner is None:
        if spec.attribute not in namespace:
            return None
        descriptor = namespace[spec.attribute]
        if not isinstance(descriptor, types.FunctionType):
            return None
        return ResolvedOperation(spec, descriptor, descriptor)
    owner = namespace.get(spec.owner)
    if not isinstance(owner, type) or spec.attribute not in owner.__dict__:
        return None
    descriptor = owner.__dict__[spec.attribute]
    if isinstance(descriptor, property):
        getter = descriptor.fget
        if not isinstance(getter, types.FunctionType):
            return None
        return ResolvedOperation(spec, descriptor, getter)
    if isinstance(descriptor, types.FunctionType):
        return ResolvedOperation(spec, descriptor, descriptor)
    return None


def resolve_qualname(qualname: str) -> ResolvedOperation | None:
    for spec in OPERATION_SPECS:
        if spec.qualname == qualname:
            return resolve_operation(spec)
    return None


def _binding_record(resolved: ResolvedOperation) -> dict[str, object]:
    callee = resolved.callee
    return {
        "descriptor": resolved.descriptor,
        "callee": callee,
        "code": callee.__code__,
        "defaults": callee.__defaults__,
        "kwdefaults": callee.__kwdefaults__,
    }


def capture_operation_bindings() -> dict[str, dict[str, object]]:
    """Retain the descriptor, callee, code, and defaults seen at bind time."""
    retained: dict[str, dict[str, object]] = {}
    for spec in OPERATION_SPECS:
        resolved = resolve_operation(spec)
        if resolved is not None:
            retained[spec.qualname] = _binding_record(resolved)
    return retained


def operation_bindings_hold(snapshot: object) -> bool:
    """The same identities must still be the consumed path."""
    if not isinstance(snapshot, dict):
        return False
    for spec in OPERATION_SPECS:
        saved = snapshot.get(spec.qualname)
        resolved = resolve_operation(spec)
        if not isinstance(saved, dict) or resolved is None:
            return False
        current = _binding_record(resolved)
        if (
            saved.get("descriptor") is not current["descriptor"]
            or saved.get("callee") is not current["callee"]
            or saved.get("code") is not current["code"]
            or saved.get("defaults") is not current["defaults"]
            or saved.get("kwdefaults") is not current["kwdefaults"]
            or saved.get("defaults") != current["defaults"]
            or saved.get("kwdefaults") != current["kwdefaults"]
        ):
            return False
    return True


def operation_markers(code: types.CodeType, spec: OperationSpec) -> str:
    consts = tuple(value for value in code.co_consts if not isinstance(value, types.CodeType))
    named = all(name in code.co_names for name in spec.required_names)
    variables = all(name in code.co_varnames for name in spec.required_varnames)
    constants = all(value in consts for value in spec.required_constants)
    if named and variables and constants:
        return "MATCH"
    return "NOT ESTABLISHED"


def _real_instructions(code: types.CodeType) -> list[dis.Instruction]:
    return [instruction for instruction in dis.get_instructions(code) if instruction.opname != "CACHE"]


def _find_instruction(instructions: list[dis.Instruction], opname: str, argrepr: str, start: int = 0) -> dis.Instruction | None:
    for instruction in instructions:
        if instruction.offset >= start and instruction.opname == opname and instruction.argrepr == argrepr:
            return instruction
    return None


def _window(code: types.CodeType, start: int, last: int) -> dict[str, object] | None:
    instructions = _real_instructions(code)
    opcodes: list[str] = []
    end = None
    for index, instruction in enumerate(instructions):
        if instruction.offset < start:
            continue
        if not opcodes and instruction.offset != start:
            return None
        opcodes.append(instruction.opname if not instruction.argrepr else f"{instruction.opname} {instruction.argrepr}")
        if instruction.offset == last:
            end = instructions[index + 1].offset if index + 1 < len(instructions) else len(code.co_code)
            break
    if end is None or end <= start:
        return None
    return {
        "start_offset": start,
        "end_offset": end,
        "co_code_hex": code.co_code[start:end].hex(),
        "opcodes": opcodes,
        "parent_co_code_length": len(code.co_code),
        "output_sampled": False,
    }


def _arithmetic_bounds(qualname: str, code: types.CodeType) -> tuple[int, int] | None:
    instructions = _real_instructions(code)
    if qualname == "FoldableRotorState.angle_from_deployed_rad":
        start = _find_instruction(instructions, "LOAD_ATTR", "opening_angle_rad")
        last = None if start is None else _find_instruction(instructions, "BINARY_OP", "-", start.offset)
    elif qualname == "BladeGeometry.radius_m":
        start = _find_instruction(instructions, "LOAD_ATTR", "diameter_m")
        last = None if start is None else _find_instruction(instructions, "BINARY_OP", "/", start.offset)
    elif qualname == "project_foldable_blade.kernel_radius":
        start = None
        last = None
        for index, instruction in enumerate(instructions):
            if instruction.opname != "LOAD_ATTR" or instruction.argrepr != "r_over_R":
                continue
            window = instructions[index:index + 12]
            pairs = {(item.opname, item.argrepr) for item in window}
            if ("LOAD_ATTR", "radius_m") in pairs and ("BINARY_OP", "*") in pairs and ("STORE_FAST", "nominal_radius") in pairs:
                start = instruction
                last = next(item for item in window if item.opname == "STORE_FAST" and item.argrepr == "nominal_radius")
                break
    elif qualname == "solve_bem_annulus.kernel_radius":
        start = None
        last = None
        for index, instruction in enumerate(instructions):
            if instruction.opname != "LOAD_ATTR" or instruction.argrepr != "r_over_R":
                continue
            window = instructions[index:index + 8]
            pairs = {(item.opname, item.argrepr) for item in window}
            if ("LOAD_ATTR", "radius_m") in pairs and ("BINARY_OP", "*") in pairs and ("STORE_DEREF", "radius") in pairs:
                start = instructions[index - 1] if index else instruction
                last = next(item for item in window if item.opname == "STORE_DEREF" and item.argrepr == "radius")
                break
    elif qualname == "solve_bem_rotor.annulus_edge":
        store = _find_instruction(instructions, "STORE_FAST", "inner")
        last = None if store is None else _find_instruction(instructions, "STORE_FAST", "outer", store.offset)
        start = None
        if store is not None:
            for instruction in instructions:
                if instruction.offset >= store.offset:
                    break
                if instruction.opname == "LOAD_FAST" and instruction.argrepr == "inner_radius":
                    start = instruction
    elif qualname == "solve_bem_rotor.midpoint":
        start = None
        last = None
        for instruction in instructions:
            if instruction.opname == "LOAD_CONST" and instruction.argrepr == "0.5":
                store = _find_instruction(instructions, "STORE_FAST", "midpoint", instruction.offset)
                if store is not None and store.offset - instruction.offset < 40:
                    start = instruction
                    last = store
                    break
    else:
        return None
    if start is None or last is None:
        return None
    return start.offset, last.offset


def arithmetic_operation_record(qualname: str) -> dict[str, object]:
    """The bytecode window for one arithmetic or store operation. Do not execute it."""
    resolved = resolve_qualname(qualname)
    empty: dict[str, object] = {
        "qualname": qualname,
        "start_offset": None,
        "end_offset": None,
        "co_code_hex": None,
        "opcodes": [],
        "parent_co_code_length": None,
        "output_sampled": False,
    }
    if resolved is None:
        return empty
    bounds = _arithmetic_bounds(qualname, resolved.code)
    if bounds is None:
        return empty
    window = _window(resolved.code, bounds[0], bounds[1])
    if window is None:
        return empty
    window["qualname"] = qualname
    return window


def classify_resolved_operation(root: Path, spec: OperationSpec, resolved: ResolvedOperation | None) -> dict[str, str]:
    """Compare the live callee with its source. A filename clears nothing."""
    unavailable = {
        "constants": "NOT ESTABLISHED",
        "defaults": "NOT ESTABLISHED",
        "markers": "NOT ESTABLISHED",
        "classification": "NOT ESTABLISHED",
    }
    if resolved is None:
        return unavailable
    source_path = root / spec.path
    if not source_path.is_file():
        return unavailable
    text = source_path.read_text(encoding="utf-8")
    compiled = compile(text, str(source_path), "exec", dont_inherit=True, optimize=sys.flags.optimize)
    expected = _code_for_qualname(compiled, spec.source_qualname)
    constants = "NOT ESTABLISHED" if expected is None else compare_code_structure(resolved.code, expected)
    defaults = compare_signature_defaults(resolved.callee, text, spec.source_qualname)
    markers = operation_markers(resolved.code, spec)
    if "MISMATCH" in (constants, defaults):
        overall = "MISMATCH"
    elif "NOT ESTABLISHED" in (constants, defaults, markers):
        overall = "NOT ESTABLISHED"
    else:
        overall = "MATCH"
    return {
        "constants": constants,
        "defaults": defaults,
        "markers": markers,
        "classification": overall,
    }
