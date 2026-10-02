"""Append-only C2V-09 declaration for candidates 00…27, 28 and 29.

The original manifest bytes stay the pinned snapshot. Candidate 28 and 29
are read from the reviewed technical HEAD, not rebuilt from helper defaults.
This module does not call a motor, BEM, mapper or trajectory.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


TECHNICAL_HEAD = "fd55fa97676c84c896511765e94561a706252239"
ORIGINAL_MANIFEST_SHA256 = "265d531f51f08d45139313cd81b0239de0c2e9dd8926e12ded66d2011d83c1f7"
CANDIDATE28_MANIFEST_SHA256 = "c2061c293190a5fec947230b89c98c553da22aab738b6146c54fd49955dfb547"
CANDIDATE29_MANIFEST_SHA256 = "0b37fb45c005d7a046dee6541d1a89e4a0a5cead7434621718c90d191843b7a4"
RUNTIME_BINDING_SHA256 = "5a2a8ab62faf7729769ea9dd620ffd07635605ae170ef523c91d3ec560c16a67"
COSINE_RECORD_SHA256 = "7c9fc9cc0def92fb3d4f2c850e63e85ce70821aa562fbc1c9a9ab45f5e12b865"
PRIOR_GEOMETRIC_RECORD_SHA256 = "0b672af90ee94197489522c45ab173834b893a7a47786c196eed7f0478cb4526"
CONNECTION_RECORD_SHA256 = "80abd1b5d16872a67004a0511fdb8ad40c8d04d5e1319635d1b79459b4280897"
CANDIDATE28_DISPOSITION = "CANDIDATE REJECTED: SOURCE DOMAIN / NOT SELECTED"
CANDIDATE29_DISPOSITION = "NOT SELECTED"
SELECTION_POLICY = "prc_c2v09_ordered_candidates_v3_proposed"
EXTENDED_DECLARATION_SHA256 = "13f4ac4f671c5b81ba68cb96537e5b9c29ff72c260cd634568983910531dce43"
TECHNICAL_ARTIFACT_SHA256 = {
    "docs/cmm2_numerical_feasibility_amendment.md": "372179bda248811450a33c2beacf8c9ce930a05add3cc58bfe58fec82e99c59a",
    "docs/cmm2_c2v09_candidate29_proposal.md": "d49dccd482e3c5ec71d78cd92968620fdd118c64888eabcdcd45149484e9d884",
    "docs/cmm2_c2v09_partition_policy_proposal.md": "c563fddc5774d1a4ecfc2ae7961dc05915e04a1185e5ccb43084870db8a1d0d2",
    "docs/cmm2_c2v09_partition_scope_runtime_proposal.md": "b15665e115628c850e1f877891a8c5099404be0e6c1b206ce7a63f1901dd189c",
    "docs/cmm2_c2v09_partition_runtime_certificate.md": "d0c9196a747ad2e49f94bb264e33bca95eec0a20e1bc900dc1bd5442d0ef5b35",
    "docs/cmm2_c2v09_partition_initial_assessment.md": "eba42e24e8f5d128ccb218f3fad1d6d983aa5a8b22784a81ae0c351b379cf666",
}
CANDIDATE29_DISPOSITION_SENTENCE = "Candidate29 remains **NOT SELECTED**"

POLICY_PATHS = (
    "docs/cmm2_numerical_feasibility_amendment.md",
    "docs/cmm2_c2v09_candidate29_proposal.md",
    "docs/cmm2_c2v09_partition_policy_proposal.md",
    "docs/cmm2_c2v09_partition_scope_runtime_proposal.md",
    "docs/cmm2_c2v09_partition_runtime_certificate.md",
    "docs/cmm2_c2v09_partition_initial_assessment.md",
)
ORIGINAL_MANIFEST_PATH = "tests/fixtures/prc/prc_critical_fixture_manifest_v1.canonical.json"


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(value: object) -> bytes:
    """Section 7.3 encoding: sorted compact ASCII JSON, no final newline."""
    return json.dumps(
        _section7(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def historical_manifest_bytes(value: object) -> bytes:
    """Candidate-manifest encoding used by the reviewed declaration digests."""
    return json.dumps(
        _binary64_tree(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _section7(value: object) -> object:
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("Eligibility encoding rejects a non-finite value.")
        return value.hex()
    if isinstance(value, dict):
        return {str(key): _section7(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple)):
        return [_section7(inner) for inner in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError(f"Unsupported declaration value {type(value).__name__}.")


def _binary64_tree(value: object) -> object:
    if isinstance(value, float):
        return {"binary64": value.hex()}
    if isinstance(value, dict):
        return {str(key): _binary64_tree(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_binary64_tree(inner) for inner in value]
    return value


def _read_text(root: Path, path: str) -> str:
    return (root / path).read_text(encoding="utf-8")


def _json_fence(text: str, index: int) -> str:
    parts = text.split("```json\n")
    if len(parts) <= index + 1:
        raise RuntimeError(f"Reviewed document is missing JSON fence {index}.")
    return parts[index + 1].split("```", 1)[0]


@dataclass(frozen=True)
class ReviewedMaterials:
    """Bytes and digests taken from the reviewed declarations."""

    original_bytes: bytes
    candidate28_bytes: bytes
    candidate29_bytes: bytes
    artifact_digests: Mapping[str, str]
    theta0: tuple[str, str]
    uncertainty_hex: tuple[str, ...]
    candidate29_source_sha256: str
    candidate28_disposition: str
    candidate29_disposition: str
    certificate_runtime: Mapping[str, str]

    def with_candidate29_bytes(self, data: bytes) -> "ReviewedMaterials":
        return ReviewedMaterials(
            self.original_bytes,
            self.candidate28_bytes,
            data,
            self.artifact_digests,
            self.theta0,
            self.uncertainty_hex,
            self.candidate29_source_sha256,
            self.candidate28_disposition,
            self.candidate29_disposition,
            self.certificate_runtime,
        )

    def with_artifact_digest(self, path: str, digest: str) -> "ReviewedMaterials":
        updated = dict(self.artifact_digests)
        updated[path] = digest
        return ReviewedMaterials(
            self.original_bytes,
            self.candidate28_bytes,
            self.candidate29_bytes,
            updated,
            self.theta0,
            self.uncertainty_hex,
            self.candidate29_source_sha256,
            self.candidate28_disposition,
            self.candidate29_disposition,
            self.certificate_runtime,
        )

    def with_theta0(self, theta0: tuple[str, str]) -> "ReviewedMaterials":
        return ReviewedMaterials(
            self.original_bytes,
            self.candidate28_bytes,
            self.candidate29_bytes,
            self.artifact_digests,
            theta0,
            self.uncertainty_hex,
            self.candidate29_source_sha256,
            self.candidate28_disposition,
            self.candidate29_disposition,
            self.certificate_runtime,
        )


@dataclass(frozen=True)
class ExtendedDeclaration:
    order: tuple[str, ...]
    original_manifest_sha256: str
    candidate28_manifest_sha256: str
    candidate29_manifest_sha256: str
    technical_head: str
    sha256: str
    candidate28_disposition: str
    candidate29_disposition: str
    payload: Mapping[str, object]


def load_reviewed_materials(root: Path | None = None) -> ReviewedMaterials:
    """Load pinned declaration bytes. A digest mismatch fails closed."""
    repository = repository_root() if root is None else root
    original = (repository / ORIGINAL_MANIFEST_PATH).read_bytes()
    if sha256_bytes(original) != ORIGINAL_MANIFEST_SHA256:
        raise RuntimeError("Original 00…27 manifest bytes do not match the pinned digest.")
    parsed_original = json.loads(original.decode("utf-8"))
    identifiers = [row["id"] for row in parsed_original["c2v09_candidates"]]
    if identifiers != [f"C2V09-{index:02d}" for index in range(28)]:
        raise RuntimeError("Original manifest is not candidates 00…27 in order.")

    amendment = _read_text(repository, "docs/cmm2_numerical_feasibility_amendment.md")
    proposal = _read_text(repository, "docs/cmm2_c2v09_candidate29_proposal.md")
    certificate = _read_text(repository, "docs/cmm2_c2v09_partition_runtime_certificate.md")
    if CANDIDATE28_DISPOSITION not in amendment:
        raise RuntimeError("The amendment no longer contains the candidate28 rejection.")
    if CANDIDATE29_DISPOSITION_SENTENCE not in amendment:
        raise RuntimeError("The amendment no longer contains the candidate29 disposition.")

    candidate28 = historical_manifest_bytes(json.loads(_json_fence(amendment, 0)))
    candidate29_object = json.loads(_json_fence(proposal, 0))
    candidate29 = historical_manifest_bytes(candidate29_object)
    if sha256_bytes(candidate28) != CANDIDATE28_MANIFEST_SHA256:
        raise RuntimeError("Candidate28 manifest does not match the reviewed digest.")
    if sha256_bytes(candidate29) != CANDIDATE29_MANIFEST_SHA256:
        raise RuntimeError("Candidate29 manifest does not match the reviewed digest.")

    binding = _json_fence(certificate, 0)
    cosine = _json_fence(certificate, 1)
    connection_text = _json_fence(certificate, 2)
    if sha256_bytes(binding.encode("utf-8")) != RUNTIME_BINDING_SHA256:
        raise RuntimeError("Runtime-binding record does not match the reviewed digest.")
    if sha256_bytes(cosine.encode("utf-8")) != COSINE_RECORD_SHA256:
        raise RuntimeError("Cosine record does not match the reviewed digest.")
    if sha256_bytes(connection_text.encode("utf-8")) != CONNECTION_RECORD_SHA256:
        raise RuntimeError("Connection record does not match the reviewed digest.")
    geometric = _json_fence(_read_text(repository, "docs/cmm2_c2v09_partition_initial_assessment.md"), 0)
    if sha256_bytes(geometric.encode("utf-8")) != PRIOR_GEOMETRIC_RECORD_SHA256:
        raise RuntimeError("Prior geometric record does not match the reviewed digest.")

    binding_object = json.loads(binding)
    cosine_object = json.loads(cosine)
    connection = json.loads(connection_text)
    theta0 = tuple(cosine_object["Theta0_exact"])
    if len(theta0) != 2:
        raise RuntimeError("Reviewed Theta0 is not an endpoint pair.")
    uncertainty = tuple(float(row["uncertainty_m"]).hex() for row in connection["original_v1_rows"])
    if connection.get("stored_uncertainty_recomputed") is not False:
        raise RuntimeError("Stored uncertainty was recomputed in the reviewed record.")
    family = binding_object["CPU_family_model_stepping"]
    runtime = {
        "executable_sha256": binding_object["artifacts"]["CPython_builtin_math"]["sha256"],
        "libm_sha256": binding_object["artifacts"]["libm"]["sha256"],
        "libc_sha256": binding_object["artifacts"]["libc"]["sha256"],
        "loader_sha256": binding_object["artifacts"]["loader"]["sha256"],
        "python_version": str(binding_object["python_version"]).split()[0],
        "fegetround": str(binding_object["fegetround"]),
        "mxcsr_hex": str(binding_object["MXCSR_hex"]),
        "mxcsr_daz": str(binding_object["MXCSR_DAZ"]),
        "mxcsr_ftz": str(binding_object["MXCSR_FTZ"]),
        "cpu_family": str(family[0]),
        "cpu_model": str(family[1]),
        "cpu_stepping": str(family[2]),
        "cos_vaddr": str(binding_object["resolved_cos_body_vaddr"]),
    }
    return ReviewedMaterials(
        original,
        candidate28,
        candidate29,
        dict(TECHNICAL_ARTIFACT_SHA256),
        (theta0[0], theta0[1]),
        uncertainty,
        str(candidate29_object["effective_binding"]["source_sha256"]),
        CANDIDATE28_DISPOSITION,
        CANDIDATE29_DISPOSITION,
        runtime,
    )


def build_extended_declaration(root: Path | None = None) -> ExtendedDeclaration:
    """Pin 00…27, then append the reviewed 28 and 29 records."""
    materials = load_reviewed_materials(root)
    identifiers = [f"C2V09-{index:02d}" for index in range(30)]
    payload = {
        "technical_head": TECHNICAL_HEAD,
        "selection_policy": SELECTION_POLICY,
        "order": identifiers,
        "original_00_27_sha256": ORIGINAL_MANIFEST_SHA256,
        "candidate28_manifest_sha256": CANDIDATE28_MANIFEST_SHA256,
        "candidate28_disposition": materials.candidate28_disposition,
        "candidate29_manifest_sha256": CANDIDATE29_MANIFEST_SHA256,
        "candidate29_disposition": materials.candidate29_disposition,
        "candidate29_source_sha256": materials.candidate29_source_sha256,
        "theta0": list(materials.theta0),
        "uncertainty_hex": list(materials.uncertainty_hex),
        "stored_uncertainty_recomputed": False,
        "proof": {
            "runtime_binding_sha256": RUNTIME_BINDING_SHA256,
            "cosine_record_sha256": COSINE_RECORD_SHA256,
            "prior_geometric_record_sha256": PRIOR_GEOMETRIC_RECORD_SHA256,
            "connection_record_sha256": CONNECTION_RECORD_SHA256,
        },
        "policy_artifact_sha256": dict(materials.artifact_digests),
        "certificate_runtime": dict(materials.certificate_runtime),
    }
    digest = sha256_bytes(canonical_bytes(payload))
    if digest != EXTENDED_DECLARATION_SHA256:
        raise RuntimeError("Extended declaration digest does not match the pin.")
    return ExtendedDeclaration(
        tuple(identifiers),
        ORIGINAL_MANIFEST_SHA256,
        CANDIDATE28_MANIFEST_SHA256,
        CANDIDATE29_MANIFEST_SHA256,
        TECHNICAL_HEAD,
        digest,
        materials.candidate28_disposition,
        materials.candidate29_disposition,
        payload,
    )
