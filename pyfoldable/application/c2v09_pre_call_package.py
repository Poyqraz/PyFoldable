"""One pre-call package for the pending initial evaluator transaction.

Actual evaluator, source, mapper, partition, selection, seal and trajectory
calls stay at zero. PRE-CALL READY FOR REVIEW is not execution authorization.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Mapping

from pyfoldable.application.c2v09_binding_collector import pinned_certificate_sources
from pyfoldable.application.c2v09_cosine_path_certificate import observe_ulp_terminal_guard
from pyfoldable.application.c2v09_declared_operations import (
    ARITHMETIC_QUALNAMES,
    REQUIRED_GRAPH_QUALNAMES,
    arithmetic_operation_record,
)
from pyfoldable.application.c2v09_initial_applicability import (
    CONTRACT_BLOCKED,
    build_applicability_dossier,
    declare_initial_operation_graph,
)
from pyfoldable.application.c2v09_initial_call_binding import (
    InitialCallBinding,
    _thread_id,
    bind_initial_call,
    revalidate_initial_call_binding,
)
from pyfoldable.application.c2v09_ordered_declaration import canonical_bytes, sha256_bytes

PRE_CALL_READY = "PRE-CALL READY FOR REVIEW"
UNRESOLVED = "UNRESOLVED PRE-CALL HYPOTHESES"
DIGEST_SCOPE = (
    "SHA-256 of the section 7.3 canonical bytes of canonical_payload only. "
    "canonical_sha256 and digest_scope are outside that payload."
)
_REQUIRED_FILE_DELTAS = (
    "pyfoldable/application/cmm2_coupled_transient_service.py",
    "pyfoldable/dynamics/cmm2_coupled_transient.py",
)
_REQUIRED_DISPOSITIONS = (
    "historical XCR0",
    "historical wrapper",
    "CPython executable",
    "loader",
    "libm",
)
_CONSUMED_PROBE_SYMBOLS = ("read_state", "xcr0_read_permitted")
_EMBEDDED_ARITHMETIC = (
    "project_foldable_blade.kernel_radius",
    "solve_bem_rotor.annulus_edge",
    "solve_bem_rotor.midpoint",
)
_ARITHMETIC_OPCODES = {
    "FoldableRotorState.angle_from_deployed_rad": "BINARY_OP -",
    "BladeGeometry.radius_m": "BINARY_OP /",
    "project_foldable_blade.kernel_radius": "BINARY_OP *",
    "solve_bem_rotor.annulus_edge": "STORE_FAST outer",
    "solve_bem_rotor.midpoint": "STORE_FAST midpoint",
}
_FILE_DELTA_ROLES = {
    "pyfoldable/application/cmm2_coupled_transient_service.py": (
        "consumed by the initial evaluator constructor and call; "
        "qualname code identity does not relabel this file hash"
    ),
    "pyfoldable/dynamics/cmm2_coupled_transient.py": (
        "deferred integration solver; the hash mismatch remains and is not "
        "initial geometric clearance"
    ),
}


def _git_text(root: Path, *args: str) -> str | None:
    try:
        return subprocess.check_output(["git", *args], cwd=root, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def review_historical_file_deltas(root: Path) -> list[dict[str, object]]:
    """Keep certificate file mismatches visible. Do not relabel the hashes."""
    rows = []
    for path, historical in pinned_certificate_sources(root):
        current_path = root / path
        current = sha256_bytes(current_path.read_bytes()) if current_path.is_file() else None
        if current == historical:
            continue
        rows.append(
            {
                "path": path,
                "historical_sha256": historical,
                "current_sha256": current,
                "file_identity": "MISMATCH" if current is not None else "NOT ESTABLISHED",
                "waived": False,
                "hash_relabelled": False,
                "code_identity_clears_file_hash": False,
                "consumed_initial_operation": _FILE_DELTA_ROLES.get(
                    path,
                    "not an initial geometric operation; the file hash mismatch remains",
                ),
                "initial_operation_reuse": _FILE_DELTA_ROLES.get(
                    path,
                    "not an initial geometric operation; the file hash mismatch remains",
                ),
                "mismatch_preserved": True,
            }
        )
    return rows


def scoped_runtime_dispositions(native: Mapping[str, object]) -> list[dict[str, object]]:
    """Identifier match or mismatch does not by itself settle applicability."""
    comparison = native.get("comparison") if isinstance(native.get("comparison"), Mapping) else {}
    rows = []
    named = (
        ("historical XCR0", comparison.get("historical_xcr0"), "cosine and probe feature observation"),
        ("historical wrapper", comparison.get("historical_wrapper"), "math.cos wrapper address"),
        ("CPython executable", comparison.get("executable"), "interpreter image"),
        ("loader", (comparison.get("libraries") or {}).get("loader") if isinstance(comparison.get("libraries"), Mapping) else None, "dynamic loader"),
        ("libm", (comparison.get("libraries") or {}).get("libm") if isinstance(comparison.get("libraries"), Mapping) else None, "libm file"),
    )
    for name, value, consumed in named:
        if isinstance(value, Mapping):
            classification = str(value.get("classification", "NOT ESTABLISHED"))
        elif isinstance(value, str):
            classification = value
        else:
            classification = "NOT ESTABLISHED"
        rows.append(
            {
                "name": name,
                "classification": classification,
                "consumed_by": consumed,
                "disposition": (
                    "CONSUMED PATH IDENTIFIER DIFFERS"
                    if classification == "MISMATCH"
                    else "CONSUMED PATH IDENTIFIER MATCHES HISTORICAL RECORD"
                    if classification == "MATCH"
                    else "NOT ESTABLISHED"
                ),
                "settles_applicability": False,
                "historical_equality_assumed": False,
            }
        )
    return rows


def geometric_applicability_argument(graph: list[dict[str, object]]) -> dict[str, object]:
    """Connect consumed operations to conditional lemmas. Code identity is not transfer."""
    wanted = {
        "FoldableRotorState.angle_from_deployed_rad": "deployed-angle subtraction is checked, not bypassed",
        "BladeGeometry.radius_m": "blade radius consumed by the kernel-radius product",
        "project_foldable_blade": "source cosine input",
        "project_foldable_blade.kernel_radius": "kernel-radius product q*R, distinct from the annulus midpoint",
        "solve_bem_rotor.annulus_edge": "annulus edges consumed inside solve_bem_rotor",
        "solve_bem_rotor.midpoint": "annulus midpoint consumed inside solve_bem_rotor",
        "_projection_factor": "mapper cosine uses the same represented angle at a separate call site",
        "_station_at_hinge": "hinge-station construction",
        "PolarFamily.query": "normalized polar query branches",
        "SpanwisePolarSchedule.section": "spanwise normalized query",
        "projected_radius_m": "mapper radius is not a substitute for the kernel radius",
        "map_projected_material_loads": "mapper ownership of the projected intervals",
    }
    links = []
    for row in graph:
        if row["qualname"] not in wanted:
            continue
        links.append(
            {
                "qualname": row["qualname"],
                "code_classification": row["classification"],
                "lemma": wanted[row["qualname"]],
                "code_identity_is_lemma_transfer": False,
                "historical_argument_reuse": "NOT ESTABLISHED",
                "assumptions_established_for_this_path": False,
                "family": row["family"],
            }
        )
    return {
        "code_identity_is_lemma_transfer": False,
        "cosine_result_identity": "POST-RETURN ONLY",
        "bem_numerical_success_reuses_geometric_proof": False,
        "every_angle_bem_convergence_required": False,
        "historical_argument_reuse": "NOT ESTABLISHED",
        "links": links,
    }


def _hypothesis(name: str, missing: str) -> dict[str, object]:
    return {"name": name, "missing": missing, "timing": "pre-call"}


def _nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def _ulp_path_established(ulp: Mapping[str, object]) -> bool:
    edges = ulp.get("call_edges")
    edge_ok = (
        isinstance(edges, list)
        and bool(edges)
        and all(
            isinstance(edge, Mapping)
            and edge.get("source") == "loaded bytes"
            and edge.get("loaded_bytes_match_file") is True
            and edge.get("disk_disassembly_is_proof") is False
            for edge in edges
        )
    )
    return (
        ulp.get("wrapper_address_establishes_path") is False
        and ulp.get("disk_disassembly_is_proof") is False
        and ulp.get("ulp_function_calls") == 0
        and ulp.get("nextafter_function_calls") == 0
        and ulp.get("output_sampled") is False
        and ulp.get("selected_nextafter") == "OBSERVED"
        and ulp.get("loaded_wrapper_matches_file") is True
        and _nonempty_text(ulp.get("loaded_wrapper_bytes_hex"))
        and _nonempty_text(ulp.get("loaded_stub_bytes_hex"))
        and _nonempty_text(ulp.get("got_slot"))
        and _nonempty_text(ulp.get("selected_address"))
        and ulp.get("evidence") == "loaded wrapper plt got"
        and edge_ok
    )


def interpreter_arithmetic_record(native: Mapping[str, object]) -> dict[str, object]:
    """Bytecode of the consumed arithmetic operations. Do not execute them."""
    operations = [arithmetic_operation_record(qualname) for qualname in ARITHMETIC_QUALNAMES]
    controls = native.get("controls") if isinstance(native.get("controls"), Mapping) else {}
    same_recording = (
        native.get("kind") == "genuine"
        and native.get("pid") == os.getpid()
        and native.get("thread_id") == _thread_id()
        and controls.get("classification") == "OBSERVED"
    )
    return {
        "output_sampled": False,
        "same_recording_as_probe": same_recording,
        "controls_classification": controls.get("classification", "NOT ESTABLISHED"),
        "operations": operations,
    }


def _arithmetic_established(record: object) -> bool:
    if not isinstance(record, Mapping):
        return False
    if record.get("output_sampled") is not False or record.get("same_recording_as_probe") is not True:
        return False
    if record.get("controls_classification") != "OBSERVED":
        return False
    rows = record.get("operations")
    if not isinstance(rows, list):
        return False
    found = {row.get("qualname"): row for row in rows if isinstance(row, Mapping)}
    slices: dict[str, str] = {}
    for qualname in ARITHMETIC_QUALNAMES:
        row = found.get(qualname)
        if not isinstance(row, Mapping) or row.get("output_sampled") is not False:
            return False
        start = row.get("start_offset")
        end = row.get("end_offset")
        parent = row.get("parent_co_code_length")
        opcodes = row.get("opcodes")
        blob = row.get("co_code_hex")
        if not isinstance(start, int) or not isinstance(end, int) or end <= start:
            return False
        if not isinstance(parent, int) or parent < end:
            return False
        if not isinstance(opcodes, list) or _ARITHMETIC_OPCODES[qualname] not in opcodes:
            return False
        if not isinstance(blob, str):
            return False
        try:
            raw = bytes.fromhex(blob)
        except ValueError:
            return False
        if len(raw) != end - start:
            return False
        if qualname in _EMBEDDED_ARITHMETIC and end - start >= parent:
            return False
        slices[qualname] = blob
    if len({slices[qualname] for qualname in _EMBEDDED_ARITHMETIC}) != len(_EMBEDDED_ARITHMETIC):
        return False
    return True


def _cosine_established(native: Mapping[str, object]) -> bool:
    correspondence = native.get("runtime_correspondence")
    if not isinstance(correspondence, Mapping) or correspondence.get("disk_disassembly_is_proof") is not False:
        return False
    if correspondence.get("whole_elf_required") is not False:
        return False
    cosine = correspondence.get("cosine")
    if not isinstance(cosine, Mapping):
        return False
    conversion = cosine.get("conversion")
    constants = cosine.get("constants")
    call_edges = cosine.get("cosine_call_edges")
    constants_known = (
        isinstance(constants, list)
        and bool(constants)
        and all(isinstance(row, Mapping) and row.get("classification") in {"MATCH", "MISMATCH"} for row in constants)
    )
    edges_known = (
        isinstance(call_edges, list)
        and bool(call_edges)
        and all(
            isinstance(edge, Mapping)
            and edge.get("kind") == "direct"
            and edge.get("source") == "loaded bytes"
            and edge.get("loaded_bytes_match_file") is True
            and edge.get("disk_disassembly_is_proof") is False
            and _nonempty_text(edge.get("target"))
            for edge in call_edges
        )
    )
    targets = {edge.get("target") for edge in call_edges} if isinstance(call_edges, list) else set()
    return (
        cosine.get("loaded_wrapper_matches_file") is True
        and _nonempty_text(cosine.get("loaded_wrapper_bytes_hex"))
        and _nonempty_text(cosine.get("file_wrapper_bytes_hex"))
        and edges_known
        and cosine.get("plt_stub") in targets
        and isinstance(conversion, Mapping)
        and conversion.get("classification") == "OBSERVED"
        and conversion.get("kind") == "direct"
        and _nonempty_text(conversion.get("target"))
        and conversion.get("source") == "loaded bytes"
        and conversion.get("loaded_bytes_match_file") is True
        and conversion.get("disk_disassembly_is_proof") is False
        and _nonempty_text(cosine.get("plt_stub_bytes_hex"))
        and _nonempty_text(cosine.get("got_slot"))
        and _nonempty_text(cosine.get("selected_address"))
        and cosine.get("evidence") == "python wrapper plt got"
        and cosine.get("selected_classification") == "OBSERVED"
        and _nonempty_text(cosine.get("body_bytes_hex"))
        and _nonempty_text(cosine.get("body_sha256"))
        and constants_known
        and cosine.get("controls_classification") == "OBSERVED"
        and cosine.get("cosine_function_calls") == 0
        and cosine.get("disk_disassembly_is_proof") is False
        and cosine.get("libm_body_argument") in {"APPLIES", "DOES NOT APPLY"}
    )


def _probe_range_gaps(native: Mapping[str, object]) -> list[dict[str, object]]:
    image = native.get("measurement_image") if isinstance(native.get("measurement_image"), Mapping) else {}
    gaps = []
    if image.get("loaded_code_correspondence") == "MATCH" and image.get("correspondence_coverage") != "whole file":
        gaps.append(_hypothesis("loaded probe image", "prefix coverage presented as whole-image correspondence"))
    ranges = image.get("consumed_instruction_ranges")
    found = {row.get("name"): row for row in ranges if isinstance(row, Mapping)} if isinstance(ranges, list) else {}
    for name in _CONSUMED_PROBE_SYMBOLS:
        row = found.get(name)
        if not isinstance(row, Mapping):
            gaps.append(_hypothesis(name, "captured loaded bytes"))
            continue
        mapping = row.get("address_to_elf")
        captured = (
            row.get("correspondence") == "MATCH"
            and row.get("whole_elf") is False
            and row.get("disk_disassembly_is_proof") is False
            and row.get("call_edges_decoded_from_loaded_bytes") is True
            and isinstance(row.get("call_edges"), list)
            and _nonempty_text(row.get("file_bytes_hex"))
            and row.get("file_bytes_hex") == row.get("loaded_bytes_hex")
            and isinstance(mapping, Mapping)
            and _nonempty_text(mapping.get("mapped_file"))
            and _nonempty_text(mapping.get("runtime_address"))
            and mapping.get("file_offset") is not None
        )
        if not captured:
            gaps.append(_hypothesis(name, "captured loaded bytes"))
    return gaps


def _graph_hypotheses(graph: list[dict[str, object]], ulp_established: bool) -> list[dict[str, object]]:
    present: dict[str, Mapping[str, object]] = {}
    unresolved = []
    for row in graph:
        if not isinstance(row, Mapping) or not isinstance(row.get("qualname"), str) or not isinstance(row.get("classification"), str):
            unresolved.append(_hypothesis("operation graph", "malformed graph row"))
            continue
        present[str(row["qualname"])] = row
    for qualname in REQUIRED_GRAPH_QUALNAMES:
        row = present.get(qualname)
        if row is None:
            missing = "loaded nextafter path" if qualname == "math.ulp" and not ulp_established else "required graph row"
            unresolved.append(_hypothesis(qualname, missing))
            continue
        classification = row.get("classification")
        if classification == "MISMATCH" or (classification == "NOT ESTABLISHED" and qualname != "math.ulp"):
            unresolved.append(_hypothesis(qualname, "loaded code identity"))
    return unresolved


def _disposition_hypotheses(dispositions: object) -> list[dict[str, object]]:
    if not isinstance(dispositions, list):
        return [_hypothesis("scoped runtime disposition", "scoped identity not established")]
    found = {row.get("name"): row for row in dispositions if isinstance(row, Mapping)}
    unresolved = []
    for name in _REQUIRED_DISPOSITIONS:
        row = found.get(name)
        if not isinstance(row, Mapping) or row.get("settles_applicability") is not False:
            unresolved.append(_hypothesis(name, "scoped transfer argument"))
        elif row.get("classification") not in {"MATCH", "MISMATCH"}:
            unresolved.append(_hypothesis(name, "scoped identity not established"))
    return unresolved


def _delta_hypotheses(file_deltas: object) -> list[dict[str, object]]:
    if not isinstance(file_deltas, list):
        return [_hypothesis("historical file mismatch", "required mismatch record")]
    found = {row.get("path"): row for row in file_deltas if isinstance(row, Mapping)}
    unresolved = []
    for path in _REQUIRED_FILE_DELTAS:
        row = found.get(path)
        preserved = (
            isinstance(row, Mapping)
            and row.get("file_identity") == "MISMATCH"
            and row.get("waived") is False
            and row.get("hash_relabelled") is False
            and row.get("mismatch_preserved") is True
            and _nonempty_text(row.get("initial_operation_reuse"))
        )
        if not preserved:
            unresolved.append(_hypothesis(path, "required mismatch record"))
    return unresolved


def _label(
    time_conflict: bool,
    graph: list[dict[str, object]],
    ulp: Mapping[str, object],
    *,
    native: Mapping[str, object] | None = None,
    dispositions: list[dict[str, object]] | None = None,
    file_deltas: list[dict[str, object]] | None = None,
    interpreter_arithmetic: Mapping[str, object] | None = None,
) -> tuple[str, list[dict[str, object]]]:
    """Every unresolved pre-call hypothesis stays visible. A wrapper address is not a path."""
    unresolved: list[dict[str, object]] = []
    if time_conflict:
        unresolved.append(_hypothesis("time_s", "manifest knot conflicts with declared +0.0 s"))
    ulp_established = _ulp_path_established(ulp)
    unresolved.extend(_graph_hypotheses(graph, ulp_established))
    if not ulp_established and not any(row["name"] == "math.ulp" and "nextafter" in str(row["missing"]) for row in unresolved):
        unresolved.append(_hypothesis("math.ulp", "loaded nextafter path"))
    if ulp.get("wrapper_address_establishes_path") is True:
        unresolved.append(_hypothesis("math.ulp", "wrapper address treated as the loaded path"))
    observed = native if isinstance(native, Mapping) else {}
    if observed.get("kind") != "genuine":
        unresolved.append(_hypothesis("native observation", "unestablished native test double"))
    else:
        if not _cosine_established(observed):
            unresolved.append(_hypothesis("cosine path", "loaded-path correspondence"))
        unresolved.extend(_probe_range_gaps(observed))
    unresolved.extend(_disposition_hypotheses(dispositions))
    unresolved.extend(_delta_hypotheses(file_deltas))
    if not _arithmetic_established(interpreter_arithmetic):
        unresolved.append(_hypothesis("interpreter binary64 arithmetic", "control-state observation"))
    if unresolved:
        return UNRESOLVED, unresolved
    return PRE_CALL_READY, []


def prepare_pre_call_package(root: Path, *, binding: InitialCallBinding | None = None) -> dict[str, object]:
    """Retain one transaction and its capsule. Do not call the evaluator."""
    prepared = binding if binding is not None else bind_initial_call(root)
    checked = revalidate_initial_call_binding(prepared)
    dossier = build_applicability_dossier(root, binding=prepared)
    graph = declare_initial_operation_graph(root)
    ulp = observe_ulp_terminal_guard()
    deltas = review_historical_file_deltas(root)
    dispositions = scoped_runtime_dispositions(prepared.native_observation)
    arithmetic = interpreter_arithmetic_record(prepared.native_observation)
    time_declaration = prepared.initial_arguments.get("time_declaration")
    if not isinstance(time_declaration, Mapping):
        time_declaration = {"conflict": True, "time_s_hex": "NOT ESTABLISHED"}
    label, unresolved = _label(
        bool(time_declaration.get("conflict")),
        graph,
        ulp,
        native=prepared.native_observation,
        dispositions=dispositions,
        file_deltas=deltas,
        interpreter_arithmetic=arithmetic,
    )
    if checked.classification != "REVALIDATED":
        label = UNRESOLVED
        unresolved = [{"name": "binding revalidation", "missing": checked.classification, "timing": "pre-call"}, *unresolved]
    payload = {
        "label": label,
        "implementation_commit": _git_text(root, "rev-parse", "HEAD"),
        "implementation_tree": _git_text(root, "rev-parse", "HEAD^{tree}"),
        "authorizes_execution": False,
        "eligibility_evidence": False,
        "physical_qualification": False,
        "candidate29_disposition": prepared.candidate29_disposition,
        "status": CONTRACT_BLOCKED,
        "time_declaration": dict(time_declaration),
        "time_s": prepared.initial_arguments.get("time_s"),
        "theta_rad_hex": prepared.initial_arguments.get("theta_rad_hex"),
        "theta_dot_rad_s_hex": prepared.initial_arguments.get("theta_dot_rad_s_hex"),
        "omega_rad_s_hex": prepared.initial_arguments.get("omega_rad_s_hex"),
        "binding_revalidation": checked.classification,
        "geometric_applicability_argument": geometric_applicability_argument(graph),
        "historical_file_deltas": deltas,
        "runtime_dispositions": dispositions,
        "runtime_correspondence": prepared.native_observation.get("runtime_correspondence"),
        "interpreter_arithmetic": arithmetic,
        "ulp_terminal_guard": ulp,
        "measurement_image": dossier["genuine_runtime_observations"].get("measurement_image"),
        "unresolved_pre_call": unresolved,
        "post_return_only": [
            "valid returned source object",
            "same retained object consumed by the mapper",
            "mapped intervals consumed by the partition evaluator",
        ],
        "deferred_integration": ["solve_cmm2_transient", "first_radau_contact", "later dense intervals"],
        "deferred_radau_is_prerequisite_for_isolated_source_attempt": False,
        "post_return_demanded_before_existence": False,
        "every_angle_bem_convergence_required": False,
        "future_v2_seal_required": False,
        "dossier_status": dossier["status"],
    }
    return {
        "binding": prepared,
        "revalidation": checked.classification,
        "label": label,
        "authorizes_execution": False,
        "digest_scope": DIGEST_SCOPE,
        "canonical_payload": payload,
        "canonical_sha256": sha256_bytes(canonical_bytes(payload)),
    }
