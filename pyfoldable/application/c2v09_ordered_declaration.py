"""Append-only C2V-09 declaration for candidates 00…27, 28 and 29.

The original manifest bytes stay the pinned snapshot. Candidate 28 and 29
are read from the reviewed technical HEAD, not rebuilt from helper defaults.
This module does not call a motor, BEM, mapper or trajectory.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
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
EXTENDED_DECLARATION_SHA256 = "8e0c514ac71c1da182f9d779649ab628bb8797321fad6508217afcf90790ee56"

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


def _git_bytes(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=root)


def technical_file_bytes(root: Path, path: str) -> bytes:
    return _git_bytes(root, "show", f"{TECHNICAL_HEAD}:{path}")


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

    amendment = technical_file_bytes(repository, "docs/cmm2_numerical_feasibility_amendment.md").decode("utf-8")
    proposal = technical_file_bytes(repository, "docs/cmm2_c2v09_candidate29_proposal.md").decode("utf-8")
    certificate = technical_file_bytes(repository, "docs/cmm2_c2v09_partition_runtime_certificate.md").decode("utf-8")
    if CANDIDATE28_DISPOSITION not in amendment:
        raise RuntimeError("Technical HEAD no longer contains the candidate28 rejection.")
    if "candidate29 remains **NOT SELECTED**" not in amendment and "NOT SELECTED" not in amendment:
        raise RuntimeError("Technical HEAD no longer contains the candidate29 disposition.")

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
    geometric_text = technical_file_bytes(repository, "docs/cmm2_c2v09_partition_initial_assessment.md").decode("utf-8")
    geometric = _json_fence(geometric_text, 0)
    if sha256_bytes(geometric.encode("utf-8")) != PRIOR_GEOMETRIC_RECORD_SHA256:
        raise RuntimeError("Prior geometric record does not match the reviewed digest.")

    cosine_object = json.loads(cosine)
    connection = json.loads(connection_text)
    theta0 = tuple(cosine_object["Theta0_exact"])
    if len(theta0) != 2:
        raise RuntimeError("Reviewed Theta0 is not an endpoint pair.")
    uncertainty = tuple(float(row["uncertainty_m"]).hex() for row in connection["original_v1_rows"])
    if connection.get("stored_uncertainty_recomputed") is not False:
        raise RuntimeError("Stored uncertainty was recomputed in the reviewed record.")
    artifacts = {
        path: sha256_bytes(technical_file_bytes(repository, path))
        for path in POLICY_PATHS
    }
    return ReviewedMaterials(
        original,
        candidate28,
        candidate29,
        artifacts,
        (theta0[0], theta0[1]),
        uncertainty,
        str(candidate29_object["effective_binding"]["source_sha256"]),
        CANDIDATE28_DISPOSITION,
        CANDIDATE29_DISPOSITION,
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
    }
    digest = sha256_bytes(canonical_bytes(payload))
    if EXTENDED_DECLARATION_SHA256 and digest != EXTENDED_DECLARATION_SHA256:
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
