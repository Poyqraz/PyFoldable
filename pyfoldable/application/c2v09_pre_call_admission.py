"""Zero-call pre-call admission preparation.

This binds reviewed authority, declaration operands, direct-node identity, and
this process's native observations. It does not call the source, mapper,
partition, selector, seal, or trajectory.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping

from pyfoldable.application.c2v09_binding_collector import UNHISTORICAL_MODULES, collect_binding_record
from pyfoldable.application.c2v09_ordered_declaration import (
    CANDIDATE28_MANIFEST_SHA256,
    CANDIDATE29_MANIFEST_SHA256,
    CONNECTION_RECORD_SHA256,
    COSINE_RECORD_SHA256,
    ORIGINAL_MANIFEST_PATH,
    ORIGINAL_MANIFEST_SHA256,
    POLICY_PATHS,
    PRIOR_GEOMETRIC_RECORD_SHA256,
    RUNTIME_BINDING_SHA256,
    TECHNICAL_ARTIFACT_SHA256,
    TECHNICAL_HEAD,
    _json_fence,
    build_extended_declaration,
    canonical_bytes,
    historical_manifest_bytes,
    load_reviewed_materials,
    sha256_bytes,
)
from pyfoldable.application.c2v09_pre_call_binding import (
    MAPPER_BINDING,
    POST_RETURN_ONLY,
    SOURCE_BINDING,
    PreCallObservation,
    _thread_id,
    observe_pre_call_binding,
    revalidate_pre_call_binding,
)


CLOSURE_HEAD = "81424d85cacdd04b0e4df7a721548be7efa7286e"
MAIN_V1_SEAL_SHA256 = "389d5565d179358b4530bc98038f3046291594615d1acb0d3873655f678595b9"
STORED_SCALE_HEX = "0x1.c2f8b88dfb80cp-23"
ADMISSION_PATH = "pyfoldable/application/c2v09_pre_call_admission.py"
DIGEST_SCOPE = (
    "SHA-256 of the section 7.3 canonical bytes of canonical_payload only. "
    "canonical_sha256 and digest_scope are outside that payload."
)
POLICY_IDS = {
    "timestamp": "cmm2_contact_timestamp_quantization_v1_proposed",
    "selector": "prc_c2v09_ordered_candidates_v3_proposed",
    "partition_v2": "prc_c2v09_partition_provenance_neighborhood_v2_proposed",
    "scope_v3": "prc_c2v09_partition_geometry_scope_v3_proposed",
}
POLICY_LOCATORS = (
    {"path": "docs/cmm2_numerical_feasibility_amendment.md", "section": "2 and 7"},
    {"path": "docs/cmm2_c2v09_candidate29_proposal.md", "section": "1-3"},
    {"path": "docs/cmm2_c2v09_partition_policy_proposal.md", "section": "2-7"},
    {"path": "docs/cmm2_c2v09_partition_scope_runtime_proposal.md", "section": "2-3 and 5"},
    {"path": "docs/cmm2_numerical_verification_contract.md", "section": "11"},
)
_CHECKED_CALLABLES = {SOURCE_BINDING, MAPPER_BINDING, "__call__"}
_COUNTERS = {
    "source": 0,
    "mapper": 0,
    "partition": 0,
    "selection": 0,
    "seal": 0,
    "trajectory": 0,
}


def _git_text(root: Path, *args: str) -> str | None:
    try:
        return subprocess.check_output(["git", *args], cwd=root, text=True).strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _technical_authority_bytes(root: Path, path: str) -> bytes | None:
    """Bytes at the frozen technical HEAD. Absence is not a working-tree match."""
    try:
        return subprocess.check_output(
            ["git", "show", f"{TECHNICAL_HEAD}:{path}"],
            cwd=root,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _fences(text: str) -> tuple[str, ...]:
    parts = text.split("```json\n")
    return tuple(part.split("```", 1)[0] for part in parts[1:])


def _object_with(text: str, key: str) -> dict | None:
    for body in _fences(text):
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and key in parsed:
            return parsed
    return None


def _pinned_text(root: Path, path: str) -> str | None:
    """Technical-HEAD text when it matches the pin, otherwise a matching worktree copy."""
    pin = TECHNICAL_ARTIFACT_SHA256[path]
    technical = _technical_authority_bytes(root, path)
    if technical is not None and sha256_bytes(technical) == pin:
        return technical.decode("utf-8")
    current = root / path
    if current.is_file() and sha256_bytes(current.read_bytes()) == pin:
        return current.read_text(encoding="utf-8")
    return None


def _authority_hashes(root: Path) -> tuple[dict[str, str] | None, dict[str, str]]:
    technical: dict[str, str] = {}
    executing: dict[str, str] = {}
    complete = True
    for path in POLICY_PATHS:
        pin = TECHNICAL_ARTIFACT_SHA256[path]
        current = root / path
        if not current.is_file():
            executing[path] = "NOT ESTABLISHED"
        elif sha256_bytes(current.read_bytes()) == pin:
            executing[path] = "MATCH"
        else:
            executing[path] = "MISMATCH"
        observed = _technical_authority_bytes(root, path)
        if observed is None or sha256_bytes(observed) != pin:
            complete = False
            continue
        technical[path] = sha256_bytes(observed)
    return (technical if complete else None), executing


def build_policy_bundle(artifact_sha256: Mapping[str, str]) -> dict[str, object] | None:
    """Canonical policy bundle. The executing HEAD is not part of this object."""
    if set(artifact_sha256) != set(POLICY_PATHS):
        return None
    if any(artifact_sha256[path] != TECHNICAL_ARTIFACT_SHA256[path] for path in POLICY_PATHS):
        return None
    return {
        "technical_head": TECHNICAL_HEAD,
        "closure_head": CLOSURE_HEAD,
        "closure_role": "timestamp closure provenance; not the executing head",
        "policy_ids": dict(POLICY_IDS),
        "locators": [dict(row) for row in POLICY_LOCATORS],
        "proof_identities": {
            "runtime_binding_sha256": RUNTIME_BINDING_SHA256,
            "cosine_record_sha256": COSINE_RECORD_SHA256,
            "prior_geometric_record_sha256": PRIOR_GEOMETRIC_RECORD_SHA256,
            "connection_record_sha256": CONNECTION_RECORD_SHA256,
        },
        "technical_head_artifact_sha256": {path: artifact_sha256[path] for path in POLICY_PATHS},
    }


def _verified_operands(root: Path) -> dict[str, object]:
    """Re-read digest-checked technical-HEAD bytes. A loader result is not this."""
    failed = {"classification": "NOT ESTABLISHED", "digest": None, "theta0": None, "uncertainty_hex": None}
    certificate_text = _pinned_text(root, "docs/cmm2_c2v09_partition_runtime_certificate.md")
    proposal_text = _pinned_text(root, "docs/cmm2_c2v09_candidate29_proposal.md")
    scope_text = _pinned_text(root, "docs/cmm2_c2v09_partition_scope_runtime_proposal.md")
    amendment_text = _pinned_text(root, "docs/cmm2_numerical_feasibility_amendment.md")
    if amendment_text is None:
        technical_amendment = _technical_authority_bytes(root, "docs/cmm2_numerical_feasibility_amendment.md")
        if technical_amendment is not None and sha256_bytes(technical_amendment) == TECHNICAL_ARTIFACT_SHA256["docs/cmm2_numerical_feasibility_amendment.md"]:
            amendment_text = technical_amendment.decode("utf-8")
        elif (root / "docs/cmm2_numerical_feasibility_amendment.md").is_file():
            amendment_text = (root / "docs/cmm2_numerical_feasibility_amendment.md").read_text(encoding="utf-8")
    original = root / ORIGINAL_MANIFEST_PATH
    if not all((certificate_text, proposal_text, scope_text, amendment_text)) or not original.is_file():
        return failed
    if sha256_bytes(_json_fence(certificate_text, 0).encode("utf-8")) != RUNTIME_BINDING_SHA256:
        return failed
    if sha256_bytes(_json_fence(certificate_text, 1).encode("utf-8")) != COSINE_RECORD_SHA256:
        return failed
    if sha256_bytes(_json_fence(certificate_text, 2).encode("utf-8")) != CONNECTION_RECORD_SHA256:
        return failed
    candidate29_object = json.loads(_json_fence(proposal_text, 0))
    candidate29 = historical_manifest_bytes(candidate29_object)
    candidate28 = historical_manifest_bytes(json.loads(_json_fence(amendment_text, 0)))
    original_bytes = original.read_bytes()
    if sha256_bytes(candidate29) != CANDIDATE29_MANIFEST_SHA256:
        return failed
    if sha256_bytes(candidate28) != CANDIDATE28_MANIFEST_SHA256:
        return failed
    if sha256_bytes(original_bytes) != ORIGINAL_MANIFEST_SHA256:
        return failed
    if MAIN_V1_SEAL_SHA256 not in proposal_text:
        return failed
    scale_record = _object_with(scope_text, "stored_S_theta0_binary64")
    if scale_record is None or scale_record["stored_S_theta0_binary64"] != STORED_SCALE_HEX:
        return failed
    cosine = json.loads(_json_fence(certificate_text, 1))
    connection = json.loads(_json_fence(certificate_text, 2))
    theta0 = [str(value) for value in cosine["Theta0_exact"]]
    if theta0 != [str(value) for value in connection["Theta0_exact"]] or len(theta0) != 2:
        return failed
    uncertainty = [float(row["uncertainty_m"]).hex() for row in connection["original_v1_rows"]]
    if connection.get("stored_uncertainty_recomputed") is not False or len(uncertainty) != 11:
        return failed
    binding = candidate29_object["effective_binding"]
    draft = str(candidate29_object["draft_toml"]).encode("utf-8")
    if sha256_bytes(draft) != binding["draft_sha256"]:
        return failed
    payload = {
        "classification": "VERIFIED",
        "role": "verified operand",
        "candidate29_sha256": sha256_bytes(candidate29),
        "candidate29_byte_length": len(candidate29),
        "draft_sha256": binding["draft_sha256"],
        "source_sha256": binding["source_sha256"],
        "source_sha256_role": "field inside the verified manifest; not a live source file read",
        "original_00_27_sha256": sha256_bytes(original_bytes),
        "candidate28_sha256": sha256_bytes(candidate28),
        "main_v1_seal_sha256": MAIN_V1_SEAL_SHA256,
        "stored_scale_hex": STORED_SCALE_HEX,
        "theta0": theta0,
        "theta0_role": "verified operand",
        "uncertainty_hex": uncertainty,
        "initial_declaration_state": {
            "initial_angle_rad": binding["initial_angle_rad"],
            "initial_angular_velocity_rad_s": binding["initial_angular_velocity_rad_s"],
            "initial_omega_rad_s": binding["initial_omega_rad_s"],
            "bounds": binding["bounds"],
            "bem_settings": binding["bem_settings"],
            "controls": binding["controls"],
            "hinge_radius_m": binding["hinge_radius_m"],
        },
        "live_initial_request_object": "NOT ESTABLISHED",
    }
    payload["digest"] = sha256_bytes(canonical_bytes(payload))
    return payload


def _certificate_obligations(root: Path) -> dict[str, object] | None:
    certificate = _technical_authority_bytes(root, "docs/cmm2_c2v09_partition_runtime_certificate.md")
    if certificate is None:
        return None
    if sha256_bytes(certificate) != TECHNICAL_ARTIFACT_SHA256["docs/cmm2_c2v09_partition_runtime_certificate.md"]:
        return None
    text = certificate.decode("utf-8")
    binding = json.loads(_json_fence(text, 0))
    artifacts = binding["artifacts"]
    return {
        "xcr0": [str(value) for value in binding["XCR0_low_high"]],
        "mxcsr": str(binding["MXCSR_hex"]),
        "fegetround": str(binding["fegetround"]),
        "daz": bool(binding["MXCSR_DAZ"]),
        "ftz": bool(binding["MXCSR_FTZ"]),
        "executable_sha256": str(artifacts["CPython_builtin_math"]["sha256"]),
        "libm_sha256": str(artifacts["libm"]["sha256"]),
        "libc_sha256": str(artifacts["libc"]["sha256"]),
        "loader_sha256": str(artifacts["loader"]["sha256"]),
        "body_sha256": str(binding["resolved_cos_body_bytes_sha256"]),
        "body_vaddr": str(binding["resolved_cos_body_vaddr"]),
        "wrapper_vaddr": str(binding["math_cos_wrapper_vaddr"]),
        "got_vaddr": str(binding["cos_GOT_vaddr"]),
    }


def _compare_text(observed: object, expected: object) -> str:
    if observed is None or expected is None or observed == "":
        return "NOT ESTABLISHED"
    return "MATCH" if str(observed) == str(expected) else "MISMATCH"


def compare_native_obligations(observed: Mapping[str, object], obligations: Mapping[str, object] | None) -> dict[str, object]:
    """Compare one process's native record with the certificate. Body match clears nothing else."""
    mismatches: list[str] = []
    if obligations is None:
        return {
            "classification": "NOT ESTABLISHED",
            "mismatches": ["certificate obligations"],
            "body_match_clears_xcr0": False,
            "body_match_clears_wrapper": False,
            "body_match_clears_executable": False,
            "historical_xcr0": {"classification": "NOT ESTABLISHED"},
            "loaded_body": {"classification": "NOT ESTABLISHED"},
        }
    body = observed.get("loaded_body") if isinstance(observed.get("loaded_body"), Mapping) else {}
    controls = observed.get("numerical_controls_and_features")
    controls = controls if isinstance(controls, Mapping) else {}
    wrapper = observed.get("python_wrapper") if isinstance(observed.get("python_wrapper"), Mapping) else {}
    executable = observed.get("executable") if isinstance(observed.get("executable"), Mapping) else {}
    libraries = observed.get("libraries") if isinstance(observed.get("libraries"), Mapping) else {}
    constants = observed.get("loaded_constants")
    body_sha = _compare_text(body.get("sha256"), obligations["body_sha256"])
    body_vaddr = _compare_text(body.get("elf_vaddr"), obligations["body_vaddr"])
    body_class = "MATCH" if body_sha == "MATCH" and body_vaddr == "MATCH" and body.get("matches_historical_body") is True else (
        "NOT ESTABLISHED" if body_sha == "NOT ESTABLISHED" or body_vaddr == "NOT ESTABLISHED" else "MISMATCH"
    )
    xcr0_observed = controls.get("xcr0")
    xcr0_class = _compare_text(xcr0_observed, obligations["xcr0"])
    if controls.get("exact_historical_xcr0_match") is False and xcr0_class == "MATCH":
        xcr0_class = "MISMATCH"
    wrapper_class = _compare_text(wrapper.get("address"), obligations["wrapper_vaddr"])
    got_class = _compare_text(observed.get("got_slot"), obligations["got_vaddr"])
    executable_class = _compare_text(executable.get("file_sha256"), obligations["executable_sha256"])
    library_rows = {
        name: _compare_text(libraries.get(name), obligations[f"{name}_sha256"])
        for name in ("libm", "libc", "loader")
    }
    if isinstance(constants, list) and constants:
        constant_class = "MATCH"
        for row in constants:
            if not isinstance(row, Mapping) or row.get("classification") == "NOT ESTABLISHED":
                constant_class = "NOT ESTABLISHED"
                break
            if row.get("classification") != "MATCH":
                constant_class = "MISMATCH"
                break
    else:
        constant_class = "NOT ESTABLISHED"
    for name, classification in (
        ("historical XCR0", xcr0_class),
        ("historical wrapper", wrapper_class),
        ("historical GOT", got_class),
        ("CPython executable", executable_class),
        ("loaded constants", constant_class),
        ("libm", library_rows["libm"]),
        ("libc", library_rows["libc"]),
        ("loader", library_rows["loader"]),
    ):
        if classification == "MISMATCH":
            mismatches.append(name)
    return {
        "classification": "NOT TRANSFERRED",
        "loaded_body": {"classification": body_class},
        "historical_xcr0": {"classification": xcr0_class, "observed": xcr0_observed, "certificate": obligations["xcr0"]},
        "historical_wrapper": {"classification": wrapper_class, "observed": wrapper.get("address"), "certificate": obligations["wrapper_vaddr"]},
        "historical_got": {"classification": got_class, "observed": observed.get("got_slot"), "certificate": obligations["got_vaddr"]},
        "executable": {"classification": executable_class, "observed": executable.get("file_sha256"), "certificate": obligations["executable_sha256"]},
        "libraries": library_rows,
        "loaded_constants": {"classification": constant_class},
        "mxcsr": {"classification": _compare_text(controls.get("mxcsr"), obligations["mxcsr"])},
        "fegetround": {"classification": _compare_text(controls.get("fegetround"), obligations["fegetround"])},
        "mismatches": mismatches,
        "body_match_clears_xcr0": False,
        "body_match_clears_wrapper": False,
        "body_match_clears_executable": False,
        "selected_dispatch_uses_cdll_symbol": False,
    }


def _unchecked_names(observation: PreCallObservation) -> list[str]:
    names: set[str] = set()
    for code in observation.retained_code_objects.values():
        if code is None:
            continue
        names.update(str(name) for name in code.co_names)
    return sorted(name for name in names if name not in _CHECKED_CALLABLES)


def _coverage(observation: PreCallObservation, root: Path) -> dict[str, object]:
    graph = [
        {"role": "evaluator", "name": "__call__", "classification": "CHECKED DIRECT NODE"},
        {"role": "source", "name": SOURCE_BINDING, "classification": "CHECKED DIRECT NODE"},
        {"role": "mapper", "name": MAPPER_BINDING, "classification": "CHECKED DIRECT NODE"},
        {"role": "native terminal guard", "name": "math.ulp/math.nextafter", "classification": "NOT ESTABLISHED"},
        {"role": "partition interval consumer", "name": "PlanarProjectedMaterialLoadResult.intervals", "classification": "NOT ESTABLISHED"},
    ]
    graph.extend({"role": "transitive name", "name": name, "classification": "NOT ESTABLISHED"} for name in _unchecked_names(observation))
    inventory = []
    for row in observation.certificate_source_file_identity:
        copied = dict(row)
        copied["loaded_code_identity"] = "NOT ESTABLISHED"
        copied["operation_graph_applicability"] = "NOT ESTABLISHED"
        copied["geometric_applicability"] = "NOT ESTABLISHED"
        copied["direct_node_match_clears_this_row"] = False
        inventory.append(copied)
    unbound = [dict(row) for row in observation.modules_without_historical_record]
    current = root / ADMISSION_PATH
    unbound.append(
        {
            "role": "pre_call_admission",
            "path": ADMISSION_PATH,
            "kind": "python_source",
            "file_identity": "NO HISTORICAL RECORD" if current.is_file() else "NOT ESTABLISHED",
            "current_sha256": sha256_bytes(current.read_bytes()) if current.is_file() else None,
            "loaded_code_identity": "NOT ESTABLISHED",
            "operation_graph_applicability": "NOT ESTABLISHED",
            "geometric_applicability": "NOT ESTABLISHED",
            "amends_collector_inventory": False,
        }
    )
    for row in unbound:
        row["geometric_applicability"] = "NOT ESTABLISHED"
        row["direct_node_match_clears_this_row"] = False
    return {
        "graph_nodes": graph,
        "file_inventory": inventory,
        "historical_unbound_nodes": unbound,
        "historical_unbound_collector_count": len(UNHISTORICAL_MODULES),
        "direct_node_match_clears_transitive_graph": False,
        "direct_node_match_clears_file_inventory": False,
        "coverage": "direct evaluator, source, and mapper nodes plus verified declaration operands",
    }


def _matrix(prepared: Mapping[str, object]) -> list[dict[str, object]]:
    operands = prepared["verified_operands"]
    native = prepared["native_comparison"]
    verified = isinstance(operands, Mapping) and operands.get("classification") == "VERIFIED"

    def pre(name: str, classification: str) -> dict[str, object]:
        return {"name": name, "when": "PRE-CALL", "classification": classification}

    rows = [
        pre("technical authority artifact bytes", "VERIFIED" if prepared["policy_bundle_sha256"] else "NOT ESTABLISHED"),
        pre("closure head provenance", "VERIFIED"),
        pre("executing head", "SEPARATE"),
        pre("policy bundle digest", "VERIFIED" if prepared["policy_bundle_sha256"] else "NOT ESTABLISHED"),
        pre("four proof identities", "VERIFIED" if verified else "NOT ESTABLISHED"),
        pre("candidate29 manifest bytes", "VERIFIED" if verified else "NOT ESTABLISHED"),
        pre("candidate29 draft bytes", "VERIFIED" if verified else "NOT ESTABLISHED"),
        pre("candidate29 source identity", "VERIFIED DECLARATION FIELD" if verified else "NOT ESTABLISHED"),
        pre("stored scale", "VERIFIED" if verified else "NOT ESTABLISHED"),
        pre("Theta0", "VERIFIED" if verified else "NOT ESTABLISHED"),
        pre("stored uncertainties", "VERIFIED" if verified else "NOT ESTABLISHED"),
        pre("initial declaration state", "VERIFIED DECLARATION OPERAND" if verified else "NOT ESTABLISHED"),
        pre("live initial request object", "NOT ESTABLISHED"),
        pre("direct node implementation", prepared["direct_identity"]),
        pre("21-path file inventory", "FILE IDENTITY ONLY"),
        pre("historical unbound nodes", "NO HISTORICAL CLEARANCE"),
        pre("unchecked transitive graph", "NOT ESTABLISHED"),
        pre("geometric applicability", "NOT ESTABLISHED"),
        pre("native wrapper/GOT", native.get("historical_wrapper", {}).get("classification", "NOT ESTABLISHED")),
        pre("native body", native.get("loaded_body", {}).get("classification", "NOT ESTABLISHED")),
        pre("historical XCR0", native.get("historical_xcr0", {}).get("classification", "NOT ESTABLISHED")),
        pre("executable identity", native.get("executable", {}).get("classification", "NOT ESTABLISHED")),
        {"name": "returned source object correspondence", "when": "POST-RETURN", "classification": POST_RETURN_ONLY},
        {"name": "mapped interval consumption", "when": "POST-RETURN", "classification": POST_RETURN_ONLY},
        {"name": "partition evaluation", "when": "LATER", "classification": "NOT IN THIS TRANSACTION"},
        {"name": "Q4", "when": "LATER", "classification": "NOT IN THIS TRANSACTION"},
        {"name": "selection", "when": "LATER", "classification": "NOT IN THIS TRANSACTION"},
        {"name": "seal", "when": "LATER", "classification": "NOT IN THIS TRANSACTION"},
        {"name": "trajectory", "when": "LATER", "classification": "NOT IN THIS TRANSACTION"},
    ]
    return rows


@dataclass
class PreCallAdmission:
    """In-process preparation. A serialized copy cannot authorize a call."""

    classification: str
    policy_bundle: dict[str, object] | None
    policy_bundle_sha256: str | None
    technical_head: str
    closure_head: str
    executing_head: str | None
    executing_tree: str | None
    executing_authority_copies: dict[str, str]
    verified_operands: dict[str, object]
    declaration_sha256: str | None
    caller_claims: dict[str, object]
    caller_claims_role: str
    checked_coverage: dict[str, object]
    native_comparison: dict[str, object]
    historical_source_mismatches: tuple[str, ...]
    obligation_matrix: list[dict[str, object]]
    revalidation_classification: str
    pid: int
    thread_id: str
    observation: PreCallObservation | None = None
    authorizes_execution: bool = False
    eligibility_evidence: bool = False
    physical_qualification: bool = False
    dependent_counters: dict[str, int] = field(default_factory=lambda: dict(_COUNTERS))
    direct_identity: str = "NOT ESTABLISHED"

    def __post_init__(self) -> None:
        self.authorizes_execution = False
        self.eligibility_evidence = False
        self.physical_qualification = False
        self.dependent_counters = dict(_COUNTERS)


@dataclass
class AdmissionRevalidation:
    classification: str
    authorizes_execution: bool = False
    eligibility_evidence: bool = False
    physical_qualification: bool = False

    def __post_init__(self) -> None:
        self.authorizes_execution = False
        self.eligibility_evidence = False
        self.physical_qualification = False


def _invalid(root: Path, *, claims: Mapping[str, object], reason: str, observation: PreCallObservation | None = None) -> PreCallAdmission:
    technical, executing = _authority_hashes(root)
    bundle = None if technical is None else build_policy_bundle(technical)
    native = {"classification": "NOT ESTABLISHED", "mismatches": [reason], "body_match_clears_xcr0": False, "body_match_clears_wrapper": False, "body_match_clears_executable": False, "historical_xcr0": {"classification": "NOT ESTABLISHED"}, "loaded_body": {"classification": "NOT ESTABLISHED"}, "historical_wrapper": {"classification": "NOT ESTABLISHED"}, "executable": {"classification": "NOT ESTABLISHED"}}
    prepared = {
        "policy_bundle_sha256": None if bundle is None else sha256_bytes(canonical_bytes(bundle)),
        "verified_operands": {"classification": "NOT ESTABLISHED"},
        "native_comparison": native,
        "direct_identity": "NOT ESTABLISHED",
    }
    if reason == "operand":
        prepared["policy_bundle_sha256"] = None if bundle is None else sha256_bytes(canonical_bytes(bundle))
    return PreCallAdmission(
        "INVALIDATED",
        bundle if reason != "authority" else None,
        None if reason == "authority" or bundle is None else sha256_bytes(canonical_bytes(bundle)),
        TECHNICAL_HEAD,
        CLOSURE_HEAD,
        _git_text(root, "rev-parse", "HEAD"),
        _git_text(root, "rev-parse", "HEAD^{tree}"),
        executing,
        {"classification": "NOT ESTABLISHED", "theta0": None},
        None,
        dict(claims),
        "not an operand",
        {"graph_nodes": [], "file_inventory": [], "historical_unbound_nodes": [], "direct_node_match_clears_transitive_graph": False},
        native,
        (),
        _matrix(prepared),
        "INVALIDATED",
        os.getpid(),
        _thread_id(),
        observation,
        direct_identity="NOT ESTABLISHED",
    )


def _operand_rejected(root: Path, claims: Mapping[str, object], executing: dict[str, str], bundle: dict[str, object] | None, operands: dict[str, object], reason: str) -> PreCallAdmission:
    native = {
        "classification": "NOT ESTABLISHED",
        "mismatches": [reason],
        "body_match_clears_xcr0": False,
        "body_match_clears_wrapper": False,
        "body_match_clears_executable": False,
        "historical_xcr0": {"classification": "NOT ESTABLISHED"},
        "historical_wrapper": {"classification": "NOT ESTABLISHED"},
        "loaded_body": {"classification": "NOT ESTABLISHED"},
        "executable": {"classification": "NOT ESTABLISHED"},
    }
    prepared = {
        "policy_bundle_sha256": None if bundle is None else sha256_bytes(canonical_bytes(bundle)),
        "verified_operands": operands,
        "native_comparison": native,
        "direct_identity": "NOT ESTABLISHED",
    }
    return PreCallAdmission(
        "INVALIDATED",
        bundle,
        prepared["policy_bundle_sha256"],
        TECHNICAL_HEAD,
        CLOSURE_HEAD,
        _git_text(root, "rev-parse", "HEAD"),
        _git_text(root, "rev-parse", "HEAD^{tree}"),
        executing,
        operands,
        None,
        dict(claims),
        "not an operand",
        {"graph_nodes": [], "file_inventory": [], "historical_unbound_nodes": [], "direct_node_match_clears_transitive_graph": False},
        native,
        (),
        _matrix(prepared),
        "INVALIDATED",
        os.getpid(),
        _thread_id(),
        None,
    )


def prepare_pre_call_admission(
    root: Path,
    *,
    materials_loader: Callable[[Path], object] = load_reviewed_materials,
    pre_call_observer: Callable[[Path], PreCallObservation] | None = None,
    dependency_collector: Callable[[Path], Mapping[str, object]] = collect_binding_record,
    caller_claims: Mapping[str, object] | None = None,
    before_revalidate: Callable[[PreCallObservation], None] | None = None,
) -> PreCallAdmission:
    """Bind pre-call evidence in this process. Post-return rows stay empty."""
    claims = dict(caller_claims or {})
    observer = pre_call_observer or observe_pre_call_binding
    technical, executing = _authority_hashes(root)
    bundle = None if technical is None else build_policy_bundle(technical)
    bundle_sha = None if bundle is None else sha256_bytes(canonical_bytes(bundle))
    try:
        operands = _verified_operands(root)
        loaded = materials_loader(root)
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, AttributeError):
        return _invalid(root, claims=claims, reason="operand")
    if operands.get("classification") != "VERIFIED":
        return _invalid(root, claims=claims, reason="operand")
    if list(getattr(loaded, "theta0", ())) != operands["theta0"] or [str(value) for value in getattr(loaded, "uncertainty_hex", ())] != operands["uncertainty_hex"]:
        return _operand_rejected(root, claims, executing, bundle, operands, "materials disagree with verified operands")
    observation = observer(root)
    if not isinstance(observation, PreCallObservation):
        return _invalid(root, claims=claims, reason="operand")
    if before_revalidate is not None:
        before_revalidate(observation)
    checked = revalidate_pre_call_binding(observation)
    again = _verified_operands(root)
    native = _native_for(observation, root, dependency_collector)
    declaration_sha = None
    try:
        declaration_sha = build_extended_declaration(root).sha256
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, AttributeError):
        declaration_sha = None
    binding_invalid = again.get("digest") != operands["digest"] or checked.classification != "REVALIDATED"
    invalidated = bundle_sha is None or binding_invalid
    prepared_map = {
        "policy_bundle_sha256": bundle_sha,
        "verified_operands": operands,
        "native_comparison": native,
        "direct_identity": observation.loaded_implementation_identity,
    }
    return PreCallAdmission(
        "INVALIDATED" if invalidated else "ZERO-CALL PREPARATION",
        bundle,
        bundle_sha,
        TECHNICAL_HEAD,
        CLOSURE_HEAD,
        observation.checkout_sha,
        observation.tree_sha,
        executing,
        operands,
        declaration_sha,
        claims,
        "not an operand",
        _coverage(observation, root),
        native,
        observation.historical_source_mismatches,
        _matrix(prepared_map),
        "INVALIDATED" if binding_invalid else checked.classification,
        observation.pid,
        observation.thread_id,
        observation,
        direct_identity=observation.loaded_implementation_identity,
    )


def _native_for(observation: PreCallObservation, root: Path, collector: Callable[[Path], Mapping[str, object]]) -> dict[str, object]:
    obligations = _certificate_obligations(root)
    genuine_probe = observation.native.get("native_observer") == "prepare_cosine_path_certificate"
    genuine_collector = collector is collect_binding_record
    libraries: dict[str, object] = {}
    if genuine_collector:
        collected = collector(root)["canonical_payload"]["executing_dependencies"]
        for name in ("libm", "libc", "loader"):
            row = collected.get(name) or {}
            libraries[name] = row.get("file_sha256")
    observed = dict(observation.native)
    observed["libraries"] = libraries
    if not genuine_probe:
        return {
            "classification": "NOT ESTABLISHED",
            "native_observer": "test_double",
            "collector_kind": "collect_binding_record" if genuine_collector else "test_double",
            "mismatches": [],
            "body_match_clears_xcr0": False,
            "body_match_clears_wrapper": False,
            "body_match_clears_executable": False,
            "historical_xcr0": {"classification": "NOT ESTABLISHED"},
            "historical_wrapper": {"classification": "NOT ESTABLISHED"},
            "loaded_body": {"classification": "NOT ESTABLISHED"},
            "executable": {"classification": "NOT ESTABLISHED"},
            "selected_dispatch_uses_cdll_symbol": False,
        }
    compared = compare_native_obligations(observed, obligations)
    compared["native_observer"] = "prepare_cosine_path_certificate"
    compared["collector_kind"] = "collect_binding_record" if genuine_collector else "test_double"
    return compared


def revalidate_pre_call_admission(value: object) -> AdmissionRevalidation:
    """A JSON record is not this process's observation."""
    if not isinstance(value, PreCallAdmission) or value.observation is None:
        return AdmissionRevalidation("NOT ESTABLISHED")
    if value.pid != os.getpid() or value.thread_id != _thread_id():
        return AdmissionRevalidation("INVALIDATED")
    checked = revalidate_pre_call_binding(value.observation)
    if checked.classification != "REVALIDATED" or value.observation.source_root is None:
        return AdmissionRevalidation("INVALIDATED")
    again = _verified_operands(Path(value.observation.source_root))
    if again.get("digest") != value.verified_operands.get("digest"):
        return AdmissionRevalidation("INVALIDATED")
    return AdmissionRevalidation("REVALIDATED")


def persistent_pre_call_admission(admission: PreCallAdmission) -> dict[str, object]:
    """Serialize identities only. Live observations stay in the process."""
    payload = {
        "outcome": "zero-call pre-call admission preparation",
        "classification": admission.classification,
        "authorizes_execution": False,
        "eligibility_evidence": False,
        "physical_qualification": False,
        "retained_observations_serialized": False,
        "technical_head": admission.technical_head,
        "closure_head": admission.closure_head,
        "executing_head": admission.executing_head,
        "executing_tree": admission.executing_tree,
        "policy_bundle": admission.policy_bundle,
        "policy_bundle_sha256": admission.policy_bundle_sha256,
        "executing_authority_copies": admission.executing_authority_copies,
        "verified_operands": {
            key: value
            for key, value in admission.verified_operands.items()
            if key != "initial_declaration_state"
        },
        "initial_declaration_state": admission.verified_operands.get("initial_declaration_state"),
        "declaration_sha256": admission.declaration_sha256,
        "caller_claims": admission.caller_claims,
        "caller_claims_role": admission.caller_claims_role,
        "checked_coverage": admission.checked_coverage,
        "native_comparison": admission.native_comparison,
        "historical_source_mismatches": list(admission.historical_source_mismatches),
        "obligation_matrix": admission.obligation_matrix,
        "revalidation_classification": admission.revalidation_classification,
        "direct_identity": admission.direct_identity,
        "dependent_counters": admission.dependent_counters,
        "pid": admission.pid,
        "thread_id": admission.thread_id,
    }
    ready = json.loads(canonical_bytes(payload).decode("ascii"))
    return {
        "digest_scope": DIGEST_SCOPE,
        "canonical_payload": ready,
        "canonical_sha256": sha256_bytes(canonical_bytes(ready)),
    }
