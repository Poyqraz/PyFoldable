"""One pre-call package for the pending initial evaluator transaction.

Actual evaluator, source, mapper, partition, selection, seal and trajectory
calls stay at zero. PRE-CALL READY FOR REVIEW is not execution authorization.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Mapping

from pyfoldable.application.c2v09_binding_collector import pinned_certificate_sources
from pyfoldable.application.c2v09_cosine_path_certificate import observe_ulp_terminal_guard
from pyfoldable.application.c2v09_initial_applicability import (
    CONTRACT_BLOCKED,
    build_applicability_dossier,
    declare_initial_operation_graph,
)
from pyfoldable.application.c2v09_initial_call_binding import (
    InitialCallBinding,
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
        "project_foldable_blade": "source cosine input and separate kernel-radius product q*R",
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
                "family": row["family"],
            }
        )
    return {
        "code_identity_is_lemma_transfer": False,
        "cosine_result_identity": "POST-RETURN ONLY",
        "bem_numerical_success_reuses_geometric_proof": False,
        "links": links,
    }


def _label(time_conflict: bool, graph: list[dict[str, object]], ulp: Mapping[str, object]) -> tuple[str, list[dict[str, object]]]:
    unresolved = []
    if time_conflict:
        unresolved.append({"name": "time_s", "missing": "manifest knot conflicts with declared +0.0 s", "timing": "pre-call"})
    for row in graph:
        if row["family"] == "bem numerical dependency":
            continue
        if row["classification"] == "NOT ESTABLISHED" and row["qualname"] != "math.ulp":
            unresolved.append({"name": row["qualname"], "missing": "loaded code identity", "timing": "pre-call"})
    if ulp.get("wrapper_address") is None:
        unresolved.append({"name": "math.ulp", "missing": "loaded wrapper was not observed", "timing": "pre-call"})
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
    time_declaration = prepared.initial_arguments.get("time_declaration")
    if not isinstance(time_declaration, Mapping):
        time_declaration = {"conflict": True, "time_s_hex": "NOT ESTABLISHED"}
    label, unresolved = _label(bool(time_declaration.get("conflict")), graph, ulp)
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
        "historical_file_deltas": review_historical_file_deltas(root),
        "runtime_dispositions": scoped_runtime_dispositions(prepared.native_observation),
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
