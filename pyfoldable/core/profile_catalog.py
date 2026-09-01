"""Offline, content-pinned project airfoil coordinate realizations (not polars)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from importlib.resources import files

from .airfoil import airfoil_coordinate_sha256, parse_airfoil_coordinates, validate_airfoil_definition
from .models import AirfoilDefinition


PROJECT_AIRFOIL_IDS = ("NACA0012", "NACA2412", "NACA23012", "NACA4415", "NACA63-412")
_ASSETS = files("pyfoldable").joinpath("data", "airfoils")


def load_project_airfoil(airfoil_id: str) -> AirfoilDefinition:
    """Load one named, validated coordinate realization without network or cache.

    No aliases, profile substitution or automatic polar generation. File hashes
    bind the bundled transcription; coordinate hashes bind the canonical shape.
    Neither establishes agreement with a manufactured blade or CFD/experiment.
    """
    if airfoil_id not in PROJECT_AIRFOIL_IDS:
        raise ValueError(f"Airfoil {airfoil_id!r} is not in the project catalog.")
    try:
        manifest_bytes = _ASSETS.joinpath("catalog.json").read_bytes()
        manifest = json.loads(manifest_bytes)
        rows = manifest["profiles"]
        if manifest["schema_version"] != 1 or tuple(row["id"] for row in rows) != PROJECT_AIRFOIL_IDS:
            raise ValueError("Project catalog schema/profile list mismatch.")
        row = next(row for row in rows if row["id"] == airfoil_id)
        if row["filename"] != f"{airfoil_id}.dat":
            raise ValueError("Unexpected project catalog coordinate filename.")
        data = _ASSETS.joinpath(row["filename"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != row["source_sha256"]:
            raise ValueError("Project catalog source SHA-256 mismatch.")
        foil = parse_airfoil_coordinates(data.decode("utf-8"), airfoil_id=airfoil_id, source=row["source"])
        if airfoil_coordinate_sha256(foil) != row["airfoil_coordinate_sha256"]:
            raise ValueError("Project catalog coordinate SHA-256 mismatch.")
        return validate_airfoil_definition(replace(foil, metadata={
            **foil.metadata,
            "source_table": row["source_table"],
            "catalog_schema_version": 1,
            "catalog_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "airfoil_coordinate_sha256": row["airfoil_coordinate_sha256"],
            "geometry_evidence_class": "reference_coordinate_realization_not_manufactured_geometry",
            "physical_qualification": False,
        }))
    except (OSError, KeyError, TypeError, ValueError, UnicodeError) as exc:
        raise ValueError(f"Invalid project airfoil catalog: {exc}") from exc
