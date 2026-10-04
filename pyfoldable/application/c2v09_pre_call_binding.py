"""Zero-call observation of the bindings a future initial call would use.

Retained callable objects are the evidence. Names and hashes are labels.
This module does not call the source or the mapper.
"""

from __future__ import annotations

import ast
import hashlib
import os
import subprocess
import sys
import threading
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping

from pyfoldable.application.c2v09_binding_collector import UNHISTORICAL_MODULES, pinned_certificate_sources
from pyfoldable.application.c2v09_cosine_path_certificate import prepare_cosine_path_certificate
from pyfoldable.application.c2v09_ordered_declaration import (
    CANDIDATE29_MANIFEST_SHA256,
    TECHNICAL_HEAD,
    build_extended_declaration,
    canonical_bytes,
    load_reviewed_materials,
    sha256_bytes,
)
from pyfoldable.application.cmm2_coupled_transient_service import Cmm2FoldableBemMappedAeroEvaluator


SOURCE_BINDING = "solve_foldable_bem_rotor"
MAPPER_BINDING = "map_foldable_bem_aero_loads"
POST_RETURN_ONLY = "POST-RETURN ONLY"
_BOUND_NAMES = (SOURCE_BINDING, MAPPER_BINDING)
_DEFINING_MODULES = {
    SOURCE_BINDING: "pyfoldable.core.foldable_rotor",
    MAPPER_BINDING: "pyfoldable.core.foldable_aero_load",
}
_EXPECTED_IMPLEMENTATIONS = {
    "__call__": (
        "pyfoldable/application/cmm2_coupled_transient_service.py",
        "Cmm2FoldableBemMappedAeroEvaluator.__call__",
    ),
    SOURCE_BINDING: ("pyfoldable/core/foldable_rotor.py", "solve_foldable_bem_rotor"),
    MAPPER_BINDING: ("pyfoldable/core/foldable_aero_load.py", "map_foldable_bem_aero_loads"),
}
_DIRECT_NODES = ("__call__", SOURCE_BINDING, MAPPER_BINDING)
_CODE_FIELDS = (
    "co_name",
    "co_argcount",
    "co_posonlyargcount",
    "co_kwonlyargcount",
    "co_nlocals",
    "co_stacksize",
    "co_flags",
    "co_names",
    "co_varnames",
    "co_freevars",
    "co_cellvars",
    "co_firstlineno",
)
_SELF_PATH = "pyfoldable/application/c2v09_pre_call_binding.py"
PROCESS_SCOPE = "this process and calling thread only; not another process's observation"
DIGEST_SCOPE = (
    "SHA-256 of the section 7.3 canonical bytes of canonical_payload only. "
    "canonical_sha256 and digest_scope are outside that payload. "
    "Retained callable objects are not in this payload."
)


def _freeze(value: object) -> object:
    if isinstance(value, (str, int, bool, type(None))):
        return value
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted((str(key), _freeze(item)) for key, item in value.items()))
    return ("NOT ESTABLISHED", id(value))


def _thread_id() -> str:
    return str(threading.get_native_id()) if hasattr(threading, "get_native_id") else str(threading.get_ident())


def _namespace_association(name: str, function: object) -> bool:
    """Export identity and co_filename only. This is not source conformance."""
    if name == "__call__":
        module = __import__("pyfoldable.application.cmm2_coupled_transient_service", fromlist=["_"])
        owner = getattr(module, "Cmm2FoldableBemMappedAeroEvaluator", None)
        defined = getattr(owner, "__call__", None)
    else:
        module = __import__(_DEFINING_MODULES[name], fromlist=["_"])
        defined = getattr(module, name, None)
    code = getattr(function, "__code__", None)
    origin = getattr(module, "__file__", None)
    if function is not defined or code is None or not isinstance(origin, str):
        return False
    return Path(code.co_filename).resolve() == Path(origin).resolve()


def _compiler_settings() -> dict[str, object]:
    return {
        "mode": "exec",
        "dont_inherit": True,
        "optimize": sys.flags.optimize,
        "python_version": sys.version,
        "executed": False,
    }


def _values_equal(expected: object, loaded: object) -> str:
    """Supported literals only. A shared type name is not equality."""
    if type(expected) is not type(loaded):
        return "MISMATCH"
    if isinstance(expected, float):
        return "MATCH" if expected.hex() == loaded.hex() else "MISMATCH"
    if isinstance(expected, tuple):
        if len(expected) != len(loaded):
            return "MISMATCH"
        states = [_values_equal(left, right) for left, right in zip(expected, loaded)]
        if "MISMATCH" in states:
            return "MISMATCH"
        if "NOT ESTABLISHED" in states:
            return "NOT ESTABLISHED"
        return "MATCH"
    if expected is None or isinstance(expected, (bool, int, str, bytes)):
        return "MATCH" if expected == loaded else "MISMATCH"
    return "NOT ESTABLISHED"


def compare_code_structure(loaded: object, expected: object) -> str:
    """Recursive structure. A co_code digest by itself does not establish a match."""
    if not isinstance(loaded, types.CodeType) or not isinstance(expected, types.CodeType):
        return "NOT ESTABLISHED"
    for name in _CODE_FIELDS:
        if getattr(loaded, name) != getattr(expected, name):
            return "MISMATCH"
    for name in ("co_qualname", "co_exceptiontable"):
        if hasattr(loaded, name) or hasattr(expected, name):
            if getattr(loaded, name, None) != getattr(expected, name, None):
                return "MISMATCH"
    if loaded.co_code != expected.co_code:
        return "MISMATCH"
    if len(loaded.co_consts) != len(expected.co_consts):
        return "MISMATCH"
    unresolved = False
    for left, right in zip(loaded.co_consts, expected.co_consts):
        if isinstance(left, types.CodeType) or isinstance(right, types.CodeType):
            nested = compare_code_structure(left, right)
        else:
            nested = _values_equal(left, right)
        if nested == "MISMATCH":
            return "MISMATCH"
        if nested == "NOT ESTABLISHED":
            unresolved = True
    return "NOT ESTABLISHED" if unresolved else "MATCH"


def _code_for_qualname(module_code: types.CodeType, qualname: str) -> types.CodeType | None:
    current = module_code
    for part in qualname.split("."):
        found = None
        for const in current.co_consts:
            if isinstance(const, types.CodeType) and const.co_name == part:
                found = const
                break
        if found is None:
            return None
        current = found
    return current


def _ast_literal(node: ast.AST) -> tuple[str, object]:
    if isinstance(node, ast.Constant) and (node.value is None or isinstance(node.value, (bool, int, float, str, bytes))):
        return ("LITERAL", node.value)
    if isinstance(node, ast.Tuple):
        values = []
        for item in node.elts:
            kind, value = _ast_literal(item)
            if kind != "LITERAL":
                return ("NOT ESTABLISHED", None)
            values.append(value)
        return ("LITERAL", tuple(values))
    return ("NOT ESTABLISHED", None)


def _find_ast_function(tree: ast.AST, qualname: str) -> ast.AST | None:
    if not isinstance(tree, ast.Module):
        return None
    nodes = list(tree.body)
    found: ast.AST | None = None
    for index, part in enumerate(qualname.split(".")):
        found = None
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == part:
                found = node
                break
        if found is None:
            return None
        if index < qualname.count("."):
            if not isinstance(found, ast.ClassDef):
                return None
            nodes = list(found.body)
    return found


def compare_signature_defaults(function: object, source: str, qualname: str) -> str:
    """Literal signature defaults from source text, compared with the live function."""
    try:
        function_node = _find_ast_function(ast.parse(source), qualname)
    except SyntaxError:
        return "NOT ESTABLISHED"
    if not isinstance(function_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return "NOT ESTABLISHED"
    positional: list[object] = []
    for default in function_node.args.defaults:
        kind, value = _ast_literal(default)
        if kind != "LITERAL":
            return "NOT ESTABLISHED"
        positional.append(value)
    keywords: dict[str, object] = {}
    for parameter, default in zip(function_node.args.kwonlyargs, function_node.args.kw_defaults):
        if default is None:
            continue
        kind, value = _ast_literal(default)
        if kind != "LITERAL":
            return "NOT ESTABLISHED"
        keywords[parameter.arg] = value
    expected_positional = tuple(positional) if positional else None
    expected_keywords = keywords or None
    loaded_positional = getattr(function, "__defaults__", None)
    loaded_keywords = getattr(function, "__kwdefaults__", None)
    if expected_positional is None and loaded_positional is None:
        positional_state = "MATCH"
    elif expected_positional is None or loaded_positional is None:
        positional_state = "MISMATCH"
    else:
        positional_state = _values_equal(expected_positional, loaded_positional)
    if expected_keywords is None and loaded_keywords is None:
        keyword_state = "MATCH"
    elif expected_keywords is None or not isinstance(loaded_keywords, dict):
        keyword_state = "MISMATCH"
    elif set(expected_keywords) != set(loaded_keywords):
        keyword_state = "MISMATCH"
    else:
        keyword_state = "MATCH"
        for key, value in expected_keywords.items():
            state = _values_equal(value, loaded_keywords[key])
            if state == "MISMATCH":
                return "MISMATCH"
            if state == "NOT ESTABLISHED":
                keyword_state = "NOT ESTABLISHED"
    if positional_state == "MISMATCH" or keyword_state == "MISMATCH":
        return "MISMATCH"
    if positional_state == "NOT ESTABLISHED" or keyword_state == "NOT ESTABLISHED":
        return "NOT ESTABLISHED"
    return "MATCH"


def _direct_node(root: Path, name: str, function: object) -> dict[str, object]:
    path, qualname = _EXPECTED_IMPLEMENTATIONS[name]
    node: dict[str, object] = {
        "path": path,
        "qualname": qualname,
        "namespace_association": _namespace_association(name, function),
        "implementation_identity": "NOT ESTABLISHED",
        "code_structure": "NOT ESTABLISHED",
        "defaults": "NOT ESTABLISHED",
        "source_sha256": None,
        "geometric_applicability": "NOT ESTABLISHED",
        "transitive_graph": "NOT ESTABLISHED",
        "co_code_digest_is_sufficient": False,
        "file_identity": "SEPARATE",
        "loaded_implementation_scope": "direct node only",
    }
    source_file = root / path
    code = getattr(function, "__code__", None)
    if not source_file.is_file() or not isinstance(code, types.CodeType):
        return node
    source_bytes = source_file.read_bytes()
    node["source_sha256"] = sha256_bytes(source_bytes)
    try:
        text = source_bytes.decode("utf-8")
        compiled = compile(text, str(source_file), "exec", dont_inherit=True, optimize=sys.flags.optimize)
        expected = _code_for_qualname(compiled, qualname)
    except (SyntaxError, UnicodeError, ValueError, OverflowError):
        return node
    if expected is None:
        return node
    code_status = compare_code_structure(code, expected)
    defaults_status = compare_signature_defaults(function, text, qualname)
    node["code_structure"] = code_status
    node["defaults"] = defaults_status
    if code_status == "MATCH" and defaults_status == "MATCH":
        node["implementation_identity"] = "MATCH"
    elif code_status == "MISMATCH" or defaults_status == "MISMATCH":
        node["implementation_identity"] = "MISMATCH"
    return node


def _callable_globals(namespace: Mapping[str, object], names: tuple[str, ...]) -> dict[str, object]:
    found: dict[str, object] = {}
    for name in names:
        value = namespace.get(name)
        if callable(value):
            found[name] = value
    return found


def _overall_identity(nodes: Mapping[str, Mapping[str, object]]) -> str:
    identities = [str(nodes[name]["implementation_identity"]) for name in _DIRECT_NODES]
    if all(identity == "MATCH" for identity in identities):
        return "MATCH"
    if any(identity == "MISMATCH" for identity in identities):
        return "MISMATCH"
    return "NOT ESTABLISHED"


@dataclass
class PreCallObservation:
    """In-process bindings. A serialized copy is not this object."""

    retained_callables: dict[str, object]
    retained_code_objects: dict[str, object]
    defining_module_association: bool
    call_constants: tuple[object, ...]
    code_hashes: dict[str, str]
    module_file_hashes: dict[str, str]
    module_origins: dict[str, str | None]
    historical_source_mismatches: tuple[str, ...]
    proposed_current_graph_binding: dict[str, object]
    inputs: dict[str, object]
    native: dict[str, object]
    pid: int
    thread_id: str
    checkout_sha: str | None
    tree_sha: str | None
    returned_bem_object_correspondence: str = POST_RETURN_ONLY
    mapped_interval_consumption: str = POST_RETURN_ONLY
    eligibility_evidence: bool = False
    physical_qualification: bool = False
    observation_kind: str = "live_process"
    source_callbacks: int = 0
    bound_defaults: dict[str, object] = field(default_factory=dict)
    call_signature_defaults: object = None
    call_signature_kwdefaults: object = None
    runtime: dict[str, object] = field(default_factory=dict)
    implementation_comparison: dict[str, object] = field(default_factory=dict)
    modules_without_historical_record: tuple[dict[str, object], ...] = ()
    certificate_source_file_identity: tuple[dict[str, object], ...] = ()
    retained_evaluator_call: object = None
    process_scope: str = PROCESS_SCOPE
    source_root: str | None = None
    loaded_implementation_identity: str = "NOT ESTABLISHED"
    geometric_applicability: str = "NOT ESTABLISHED"
    direct_implementation: dict[str, object] = field(default_factory=dict)
    retained_global_callables: dict[str, object] = field(default_factory=dict)
    compiler_settings: dict[str, object] = field(default_factory=dict)

    def constants_match(self, claimed: tuple[object, ...]) -> bool:
        return claimed == self.call_constants

    def defaults_match(self, claimed_bound: Mapping[str, object], claimed_call: object, claimed_kw: object) -> bool:
        return (
            claimed_bound == self.bound_defaults
            and claimed_call == self.call_signature_defaults
            and claimed_kw == self.call_signature_kwdefaults
        )


def is_live_pre_call_evidence(value: object) -> bool:
    if not isinstance(value, PreCallObservation):
        return False
    if value.observation_kind != "live_process" or value.eligibility_evidence is not False:
        return False
    source = value.retained_callables.get(SOURCE_BINDING)
    mapper = value.retained_callables.get(MAPPER_BINDING)
    return source is not None and mapper is not None and source is not mapper


def name_only_double(name: str) -> dict[str, str]:
    return {"observation_kind": "test_double", "name": name}


def same_calling_context(observation: PreCallObservation, *, pid: int, thread_id: str) -> bool:
    return observation.pid == pid and observation.thread_id == thread_id


def _certificate_file_identity(root: Path) -> tuple[dict[str, object], ...]:
    """Pinned file hashes only. A missing file stays unestablished and is not dropped."""
    rows: list[dict[str, object]] = []
    for path, historical in pinned_certificate_sources(root):
        file = root / path
        if not file.is_file():
            current = None
            identity = "NOT ESTABLISHED"
        else:
            current = sha256_bytes(file.read_bytes())
            identity = "MATCH" if current == historical else "MISMATCH"
        rows.append(
            {
                "path": path,
                "historical_sha256": historical,
                "current_sha256": current,
                "file_identity": identity,
                "loaded_code_identity": "NOT ESTABLISHED",
                "operation_graph_applicability": "NOT ESTABLISHED",
                "geometric_applicability": "NOT ESTABLISHED",
            }
        )
    return tuple(rows)


def _unhistorical(root: Path) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    entries = list(UNHISTORICAL_MODULES) + [("pre_call_binding", _SELF_PATH, "python_source")]
    for role, path, kind in entries:
        file = root / path
        current = sha256_bytes(file.read_bytes()) if file.is_file() else None
        native_identity = "NOT A COMPILED IMAGE" if kind == "python_source" else "NOT ESTABLISHED"
        loaded: object = "NOT ESTABLISHED"
        if role == "pre_call_binding" and current is not None:
            loaded = hashlib.sha256(observe_pre_call_binding.__code__.co_code).hexdigest()
        rows.append(
            {
                "role": role,
                "path": path,
                "kind": kind,
                "file_identity": "NO HISTORICAL RECORD" if current is not None else "NOT ESTABLISHED",
                "current_sha256": current,
                "historical_sha256": None,
                "loaded_code_identity": loaded,
                "loaded_code_scope": (
                    "observe_pre_call_binding code object in this process"
                    if role == "pre_call_binding"
                    else "NOT ESTABLISHED"
                ),
                "operation_graph_applicability": "NOT ESTABLISHED",
                "geometric_applicability": "NOT ESTABLISHED",
                "compiled_loaded_native_identity": native_identity,
                "amends_collector_inventory": False,
            }
        )
    return tuple(rows)


def _inputs(root: Path, loader: Callable[[Path], object]) -> dict[str, object]:
    try:
        materials = loader(root)
        declaration = build_extended_declaration(root)
        data = materials.candidate29_bytes
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, AttributeError):
        return {"classification": "NOT ESTABLISHED", "bytes": None}
    return {
        "classification": "OBSERVED",
        "bytes": data,
        "sha256": sha256_bytes(data),
        "theta0": tuple(materials.theta0),
        "uncertainty_hex": tuple(materials.uncertainty_hex),
        "candidate29_manifest_sha256": CANDIDATE29_MANIFEST_SHA256,
        "declaration_sha256": declaration.sha256,
        "technical_head": TECHNICAL_HEAD,
    }


def _repaired_file_sha(root: Path) -> str | None:
    repaired = root / "reports/c2v09_cosine_path_certificate/repaired_observation.json"
    return sha256_bytes(repaired.read_bytes()) if repaired.is_file() else None


def _public(value: object) -> object:
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, list):
        return [_public(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _public(item) for key, item in value.items()}
    return {"unsupported": type(value).__name__}


def _native_unestablished(root: Path, *, observer_name: str) -> dict[str, object]:
    return {
        "classification": "NOT ESTABLISHED",
        "selected_address": None,
        "selected_evidence": None,
        "got_slot": None,
        "independent_cdll_is_evidence": False,
        "python_wrapper": {"classification": "NOT ESTABLISHED"},
        "loaded_body": {"classification": "NOT ESTABLISHED"},
        "loaded_constants": None,
        "numerical_controls_and_features": {"classification": "NOT ESTABLISHED"},
        "libm_body_argument": "NOT ESTABLISHED",
        "historical_cpython_wrapper_argument": "NOT ESTABLISHED",
        "cosine_function_calls": 0,
        "ld_bind_now": os.environ.get("LD_BIND_NOW"),
        "executable": None,
        "thread_id": _thread_id(),
        "native_observer": observer_name,
        "historical_repaired_observation_sha256": _repaired_file_sha(root),
        "repaired_record_used_as_live_evidence": False,
        "eligibility_evidence": False,
        "process_scope": PROCESS_SCOPE,
    }


def _native(root: Path, observer: Callable[[Path], Mapping[str, object]]) -> dict[str, object]:
    if observer is not prepare_cosine_path_certificate:
        return _native_unestablished(root, observer_name="test_double")
    try:
        observed = observer(root)
        payload = observed["canonical_payload"] if "canonical_payload" in observed else observed
        if not isinstance(payload, Mapping):
            raise TypeError("cosine payload is not a mapping")
        selected = payload.get("selected_call_target") or {}
        if not isinstance(selected, Mapping):
            selected = {}
        wrapper = payload.get("python_wrapper") or {}
        body = payload.get("loaded_body") or {}
        controls = payload.get("numerical_controls_and_features") or {}
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, AttributeError):
        return _native_unestablished(root, observer_name="prepare_cosine_path_certificate")
    calls = payload.get("cosine_function_calls")
    address = selected.get("address")
    established = (
        calls == 0
        and selected.get("classification") == "OBSERVED"
        and isinstance(address, str)
        and address != ""
        and selected.get("independent_cdll_is_evidence") is False
        and selected.get("evidence") == "python wrapper plt got"
    )
    wrapper_public = _public(wrapper) if isinstance(wrapper, Mapping) else {"classification": "NOT ESTABLISHED"}
    if isinstance(wrapper_public, dict):
        wrapper_public.pop("disassembly", None)
    body_public = _public(body) if isinstance(body, Mapping) else {"classification": "NOT ESTABLISHED"}
    return {
        "classification": "OBSERVED" if established else "NOT ESTABLISHED",
        "selected_address": address if established else None,
        "selected_evidence": selected.get("evidence") if isinstance(selected.get("evidence"), str) else None,
        "got_slot": selected.get("got_slot"),
        "independent_cdll_is_evidence": False,
        "python_wrapper": wrapper_public,
        "loaded_body": body_public,
        "loaded_constants": _public(payload.get("loaded_constants")),
        "numerical_controls_and_features": _public(controls),
        "libm_body_argument": payload.get("libm_body_argument") if isinstance(payload.get("libm_body_argument"), str) else "NOT ESTABLISHED",
        "historical_cpython_wrapper_argument": (
            payload.get("historical_cpython_wrapper_argument")
            if isinstance(payload.get("historical_cpython_wrapper_argument"), str)
            else "NOT ESTABLISHED"
        ),
        "cosine_function_calls": 0 if calls == 0 else calls,
        "ld_bind_now": payload.get("ld_bind_now"),
        "executable": _public(payload.get("executable")),
        "thread_id": _thread_id(),
        "native_observer": "prepare_cosine_path_certificate",
        "historical_repaired_observation_sha256": _repaired_file_sha(root),
        "repaired_record_used_as_live_evidence": False,
        "eligibility_evidence": False,
        "process_scope": PROCESS_SCOPE,
    }


def _git_text(root: Path, *args: str) -> str | None:
    try:
        return subprocess.check_output(["git", *args], cwd=root, text=True).strip()
    except (OSError, subprocess.SubprocessError):
        return None


def observe_pre_call_binding(
    root: Path,
    *,
    materials_loader: Callable[[Path], object] = load_reviewed_materials,
    cosine_observer: Callable[[Path], Mapping[str, object]] = prepare_cosine_path_certificate,
) -> PreCallObservation:
    """Read loaded bindings. Do not call the source or the mapper."""
    call = Cmm2FoldableBemMappedAeroEvaluator.__call__
    namespace = call.__globals__
    retained: dict[str, object] = {}
    code_objects: dict[str, object] = {}
    code_hashes: dict[str, str] = {}
    file_hashes: dict[str, str] = {}
    origins: dict[str, str | None] = {}
    bound_defaults: dict[str, object] = {}
    code_objects["__call__"] = call.__code__
    code_hashes["__call__"] = hashlib.sha256(call.__code__.co_code).hexdigest()
    service_module = __import__(call.__module__, fromlist=["_"])
    origins["__call__"] = getattr(service_module, "__file__", None)
    if isinstance(origins["__call__"], str):
        file_hashes["__call__"] = sha256_bytes(Path(origins["__call__"]).read_bytes())
    for name in _BOUND_NAMES:
        function = namespace[name]
        retained[name] = function
        code = getattr(function, "__code__", None)
        code_objects[name] = code
        bound_defaults[name] = {
            "defaults": _freeze(getattr(function, "__defaults__", None)),
            "kwdefaults": _freeze(getattr(function, "__kwdefaults__", None)),
        }
        associated = _namespace_association(name, function)
        if not associated or code is None:
            code_hashes[name] = ""
            file_hashes[name] = ""
            origins[name] = None
            continue
        module = __import__(_DEFINING_MODULES[name], fromlist=["_"])
        origin = module.__file__
        origins[name] = origin
        code_hashes[name] = hashlib.sha256(code.co_code).hexdigest()
        file_hashes[name] = sha256_bytes(Path(origin).read_bytes())
    nodes = {
        "__call__": _direct_node(root, "__call__", call),
        SOURCE_BINDING: _direct_node(root, SOURCE_BINDING, retained[SOURCE_BINDING]),
        MAPPER_BINDING: _direct_node(root, MAPPER_BINDING, retained[MAPPER_BINDING]),
    }
    association = all(bool(nodes[name]["namespace_association"]) for name in _DIRECT_NODES)
    identity = _overall_identity(nodes)
    direct_implementation = {
        "transitive_graph": "NOT ESTABLISHED",
        "geometric_applicability": "NOT ESTABLISHED",
        "coverage": "direct retained evaluator, source, and mapper nodes only",
        **nodes,
    }
    inputs = _inputs(root, materials_loader)
    certificate_sources = _certificate_file_identity(root)
    return PreCallObservation(
        retained,
        code_objects,
        association,
        tuple(_freeze(item) for item in call.__code__.co_consts),
        code_hashes,
        file_hashes,
        origins,
        tuple(row["path"] for row in certificate_sources if row["file_identity"] == "MISMATCH"),
        {
            "status": "PROPOSED / NOT A HISTORICAL CLASSIFICATION",
            "defining_module_association": association,
            "loaded_implementation_identity": identity,
            "eligibility_evidence": False,
            "geometric_applicability": "NOT ESTABLISHED",
            "transitive_graph": "NOT ESTABLISHED",
            "does_not_rewrite_historical_classifications": True,
        },
        inputs,
        _native(root, cosine_observer),
        os.getpid(),
        _thread_id(),
        _git_text(root, "rev-parse", "HEAD"),
        _git_text(root, "rev-parse", "HEAD^{tree}"),
        bound_defaults=bound_defaults,
        call_signature_defaults=_freeze(call.__defaults__),
        call_signature_kwdefaults=_freeze(call.__kwdefaults__),
        runtime={
            "python_version": sys.version,
            "executable": sys.executable,
            "pid": os.getpid(),
            "thread_id": _thread_id(),
        },
        implementation_comparison={
            "status": "DIRECT NODE COMPARISON",
            "defining_module_association": association,
            "loaded_implementation_identity": identity,
            "eligibility_evidence": False,
            "geometric_applicability": "NOT ESTABLISHED",
            "transitive_graph": "NOT ESTABLISHED",
            "historical_classifications_rewritten": False,
            "co_code_digest_is_sufficient": False,
            "call_co_names": tuple(call.__code__.co_names),
        },
        modules_without_historical_record=_unhistorical(root),
        certificate_source_file_identity=certificate_sources,
        retained_evaluator_call=call,
        source_root=str(root),
        loaded_implementation_identity=identity,
        direct_implementation=direct_implementation,
        retained_global_callables=_callable_globals(namespace, call.__code__.co_names),
        compiler_settings=_compiler_settings(),
    )


@dataclass
class PreCallRevalidation:
    """Same-process check of retained operands. It does not authorize a call."""

    classification: str
    same_process: bool
    same_thread: bool
    bindings_unchanged: bool
    operands_unchanged: bool
    implementation_identity: str
    nodes: dict[str, object]
    authorizes_execution: bool = False
    eligibility_evidence: bool = False
    physical_qualification: bool = False

    def __post_init__(self) -> None:
        self.authorizes_execution = False
        self.eligibility_evidence = False
        self.physical_qualification = False


def _foreign_revalidation() -> PreCallRevalidation:
    return PreCallRevalidation(
        "NOT ESTABLISHED",
        False,
        False,
        False,
        False,
        "NOT ESTABLISHED",
        {},
    )


def _bindings_unchanged(observation: PreCallObservation) -> bool:
    call = observation.retained_evaluator_call
    if Cmm2FoldableBemMappedAeroEvaluator.__call__ is not call:
        return False
    namespace = getattr(call, "__globals__", {})
    for name in _BOUND_NAMES:
        if namespace.get(name) is not observation.retained_callables.get(name):
            return False
    for name, expected in observation.retained_global_callables.items():
        if namespace.get(name) is not expected:
            return False
    return True


def revalidate_pre_call_binding(observation: object) -> PreCallRevalidation:
    """Re-read the retained objects and captured source bytes. JSON cannot pass."""
    if not isinstance(observation, PreCallObservation) or observation.source_root is None:
        return _foreign_revalidation()
    same_process = observation.pid == os.getpid()
    same_thread = observation.thread_id == _thread_id()
    if not same_process or not same_thread:
        return PreCallRevalidation(
            "INVALIDATED",
            same_process,
            same_thread,
            False,
            False,
            "NOT ESTABLISHED",
            {},
        )
    if not _bindings_unchanged(observation):
        return PreCallRevalidation(
            "INVALIDATED",
            True,
            True,
            False,
            False,
            "NOT ESTABLISHED",
            {},
        )
    root = Path(observation.source_root)
    nodes: dict[str, dict[str, object]] = {}
    operands_unchanged = True
    for name in _DIRECT_NODES:
        function = observation.retained_evaluator_call if name == "__call__" else observation.retained_callables[name]
        node = _direct_node(root, name, function)
        stored = observation.direct_implementation.get(name)
        stored_sha = stored.get("source_sha256") if isinstance(stored, Mapping) else None
        if node["source_sha256"] != stored_sha:
            operands_unchanged = False
        nodes[name] = node
    if not operands_unchanged:
        return PreCallRevalidation("INVALIDATED", True, True, True, False, "NOT ESTABLISHED", nodes)
    identity = _overall_identity(nodes)
    classification = "REVALIDATED" if identity == "MATCH" else identity
    return PreCallRevalidation(classification, True, True, True, True, identity, nodes)


def _json_ready(value: object) -> object:
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, float):
        return value.hex()
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError(f"Pre-call record cannot serialize {type(value).__name__}.")


def persistent_pre_call_record(observation: PreCallObservation) -> dict[str, object]:
    """Serialize identities only. The retained callables stay in the process."""
    payload = {
        "outcome": "zero-call pre-call binding observation",
        "eligibility_evidence": False,
        "physical_qualification": False,
        "retained_references_serialized": False,
        "checkout_sha": observation.checkout_sha,
        "tree_sha": observation.tree_sha,
        "pid": observation.pid,
        "thread_id": observation.thread_id,
        "authorizes_execution": False,
        "defining_module_association": observation.defining_module_association,
        "loaded_implementation_identity": observation.loaded_implementation_identity,
        "geometric_applicability": observation.geometric_applicability,
        "transitive_graph": "NOT ESTABLISHED",
        "direct_implementation": {
            key: value
            for key, value in observation.direct_implementation.items()
        },
        "global_callable_names": sorted(observation.retained_global_callables),
        "compiler_settings": observation.compiler_settings,
        "callable_names": list(observation.retained_callables),
        "code_hashes": observation.code_hashes,
        "module_file_hashes": observation.module_file_hashes,
        "module_origins": observation.module_origins,
        "historical_source_mismatches": list(observation.historical_source_mismatches),
        "certificate_source_file_identity": [dict(row) for row in observation.certificate_source_file_identity],
        "proposed_current_graph_binding": observation.proposed_current_graph_binding,
        "inputs": {
            "classification": observation.inputs["classification"],
            "sha256": observation.inputs.get("sha256"),
            "byte_length": len(observation.inputs["bytes"]) if isinstance(observation.inputs.get("bytes"), bytes) else None,
            "utf8": observation.inputs["bytes"].decode("utf-8") if isinstance(observation.inputs.get("bytes"), bytes) else None,
            "theta0": list(observation.inputs["theta0"]) if observation.inputs.get("theta0") else None,
            "uncertainty_hex": list(observation.inputs["uncertainty_hex"]) if observation.inputs.get("uncertainty_hex") else None,
            "candidate29_manifest_sha256": observation.inputs.get("candidate29_manifest_sha256"),
            "declaration_sha256": observation.inputs.get("declaration_sha256"),
            "technical_head": observation.inputs.get("technical_head"),
        },
        "native": observation.native,
        "bound_defaults": observation.bound_defaults,
        "call_signature_defaults": observation.call_signature_defaults,
        "call_signature_kwdefaults": observation.call_signature_kwdefaults,
        "runtime": observation.runtime,
        "implementation_comparison": observation.implementation_comparison,
        "modules_without_historical_record": [dict(row) for row in observation.modules_without_historical_record],
        "returned_bem_object_correspondence": POST_RETURN_ONLY,
        "mapped_interval_consumption": POST_RETURN_ONLY,
        "source_callbacks": observation.source_callbacks,
        "process_scope": observation.process_scope,
    }
    ready = _json_ready(payload)
    return {
        "digest_scope": DIGEST_SCOPE,
        "canonical_payload": ready,
        "canonical_sha256": sha256_bytes(canonical_bytes(ready)),
    }
