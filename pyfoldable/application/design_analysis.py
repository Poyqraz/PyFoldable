"""Active draft preparation and explicit-polar, fully-open BEM screening.

No benchmark recipe, provider fallback, optimization, or physical qualification
is performed here. Nominal station values omit induction and must not be used
as a promise that the BEM solver's complete polar query envelope is covered.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import re
import tempfile
from dataclasses import asdict, dataclass
from importlib import import_module
from importlib.metadata import version
from pathlib import Path
from typing import Any, Mapping

from pyfoldable import __version__
from pyfoldable.core import BEMRotorSettings, PolarFamily, PolarTable, load_design_config, solve_bem_rotor
from pyfoldable.core.bem_rotor import BEM_ROTOR_SCHEMA_VERSION, BEMRotorElementError
from pyfoldable.core.models import PropellerDesign
from pyfoldable.core.units import normalize_quantity
from pyfoldable.core.airfoil import airfoil_coordinate_sha256

from .design_draft import DesignDraftArtifact


SERVICE_ID = "pyfoldable.application.design_analysis"
SERVICE_VERSION = 2
MAX_DRAFT_BYTES = 1_000_000


class DesignAnalysisError(ValueError):
    """An active-design request cannot be evaluated without guessing inputs."""


@dataclass(frozen=True)
class DesignAnalysisArtifact:
    request_sha256: str
    report_sha256: str
    report_json: str
    filename: str


def _json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError, OverflowError) as exc:
        raise DesignAnalysisError("Analysis content must be finite, JSON-safe data.") from exc


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load(draft: DesignDraftArtifact) -> tuple[PropellerDesign, float]:
    if not isinstance(draft, DesignDraftArtifact):
        raise DesignAnalysisError("Expected a validated design draft artifact.")
    if not isinstance(draft.toml, str) or len(draft.toml.encode("utf-8")) > MAX_DRAFT_BYTES:
        raise DesignAnalysisError("Invalid or oversized draft TOML.")
    if _sha(draft.toml) != draft.draft_sha256:
        raise DesignAnalysisError("Draft SHA-256 does not match its TOML content.")
    if not isinstance(draft.source_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", draft.source_sha256):
        raise DesignAnalysisError("Invalid source SHA-256.")
    try:
        # The canonical parser remains the single unit/schema authority. Temporary
        # paths and filenames are deliberately excluded from result identity.
        with tempfile.TemporaryDirectory(prefix="pyfoldable-analysis-") as directory:
            path = Path(directory) / "draft.toml"
            path.write_text(draft.toml, encoding="utf-8")
            design = load_design_config(path)
        if design.metadata.get("artifact_class") != "unqualified_design_draft":
            raise DesignAnalysisError("Input is not an unqualified design draft.")
        if design.metadata.get("source_design_sha256") != draft.source_sha256:
            raise DesignAnalysisError("Source SHA-256 does not match draft metadata.")
        angle = normalize_quantity(
            design.metadata["preview_fold_angle"], "angle", field="preview_fold_angle"
        ).si_value
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise DesignAnalysisError(f"Invalid draft: {exc}") from exc
    if not design.operating_conditions:
        raise DesignAnalysisError("The draft has no operating condition.")
    condition = design.operating_conditions[0]
    if not math.isfinite(1.4 * 287.05 * condition.temperature_k):
        raise DesignAnalysisError("Derived sound speed must be finite.")
    if condition.angular_speed_rad_s <= 0:
        raise DesignAnalysisError("Analysis requires positive RPM.")
    if condition.forward_speed_m_s < 0:
        raise DesignAnalysisError("Analysis does not support negative forward speed.")
    return design, angle


def _load_open(draft: DesignDraftArtifact) -> tuple[PropellerDesign, float]:
    """Shared application boundary for preparation-to-run and actual BEM runs."""
    design, angle = _load(draft)
    hinge = design.hinge
    if hinge is None or any(abs(value) > 1e-12 for value in (
        angle, hinge.deployed_angle_rad, hinge.axial_offset_m, hinge.tangential_offset_m,
    )):
        raise DesignAnalysisError("This service supports only a fully open, zero-offset blade.")
    return design, angle


def _request(draft: DesignDraftArtifact, design: PropellerDesign) -> dict[str, Any]:
    return {
        "service_id": SERVICE_ID,
        "service_version": SERVICE_VERSION,
        "pyfoldable_version": __version__,
        "implementation": _implementation_identity(),
        "draft_toml": draft.toml,
        "draft_sha256": draft.draft_sha256,
        "source_sha256": draft.source_sha256,
        "source_identity_scope": "declared_source_hash_not_external_authentication",
        "condition_index": 0,
        "operating_condition": asdict(design.operating_conditions[0]),
    }


def _implementation_identity() -> dict[str, Any]:
    """Record runtime versions and source files, without a git/subprocess call.

    File hashes describe disk sources at request time, not a signed build or
    proof that a long-lived interpreter has reloaded subsequently edited code.
    Restart the process after source changes when reproducing a run.
    """
    modules = (
        SERVICE_ID, "pyfoldable.application.design_draft", "pyfoldable.core.bem",
        "pyfoldable.core.bem_rotor", "pyfoldable.core.config",
        "pyfoldable.core.models", "pyfoldable.core.polar",
        "pyfoldable.core.polar_spanwise", "pyfoldable.core.rotational_augmentation",
        "pyfoldable.core.units",
        "pyfoldable.core.airfoil", "pyfoldable.core.profile_catalog",
    )
    try:
        hashes = {
            name: hashlib.sha256(Path(import_module(name).__file__).read_bytes()).hexdigest()
            for name in modules
        }
    except (OSError, TypeError) as exc:
        raise DesignAnalysisError("Analysis implementation source identity is unavailable.") from exc
    return {
        "source_files_sha256": hashes,
        "source_identity_scope": "disk_sources_at_request_time_restart_after_edits",
        "python": platform.python_version(),
        "numpy": version("numpy"),
        "scipy": version("scipy"),
    }


def _preparation(design: PropellerDesign, angle: float) -> dict[str, Any]:
    condition = design.operating_conditions[0]
    blade = design.blade
    airfoils = {foil.id: foil for foil in design.airfoils}
    # Same dry-air constants as the existing BEM kernel; no atmospheric model is
    # fitted. rho, mu and temperature are explicit independent caller inputs.
    sound_speed = math.sqrt(1.4 * 287.05 * condition.temperature_k)
    stations = []
    for station in blade.stations:
        radius = station.r_over_R * blade.radius_m
        tangential_speed = condition.angular_speed_rad_s * radius
        speed = math.hypot(tangential_speed, condition.forward_speed_m_s)
        phi = math.atan2(condition.forward_speed_m_s, tangential_speed)
        stations.append({
            "r_over_R": station.r_over_R,
            "radius_m": radius,
            "chord_m": station.chord_m,
            "twist_rad": station.twist_rad,
            "airfoil_id": station.airfoil_id,
            "airfoil_coordinate_sha256": (
                airfoil_coordinate_sha256(airfoils[station.airfoil_id])
                if airfoils[station.airfoil_id].coordinates else None
            ),
            "relative_speed_m_s": speed,
            "reynolds": condition.air_density_kg_m3 * speed * station.chord_m / condition.dynamic_viscosity_pa_s,
            "mach": speed / sound_speed,
            "alpha_rad": station.twist_rad - phi,
        })
    return {
        "scope": "open_declared_stations_no_induction",
        "airfoil_coordinate_sha256": (
            stations[0]["airfoil_coordinate_sha256"]
            if len({station.airfoil_id for station in blade.stations}) == 1 else None
        ),
        "solver_envelope_complete": False,
        "preview_fold_angle_rad": angle,
        "diameter_m": blade.diameter_m,
        "blade_count": blade.blade_count,
        "root_gap_m": blade.stations[0].r_over_R * blade.radius_m - blade.hub_radius_m,
        "tip_gap_m": (1 - blade.stations[-1].r_over_R) * blade.radius_m,
        "stations": stations,
        "limitations": [
            "No induction, swirl, radial interpolation or load prediction in preparation.",
            "Values describe the open blade, not the preview fold pose.",
            "Extrema between stations and BEM trial queries are not covered.",
            "Airfoil names and caller polars do not establish representative evidence.",
            "No material, structural, motor or deployment feasibility is assessed.",
        ],
    }


def _artifact(request: dict[str, Any], *, kind: str, **results: Any) -> DesignAnalysisArtifact:
    request_sha = _sha(_json(request))
    document = {
        "schema_version": 1,
        "artifact_class": kind,
        "qualification": "screening_only_until_pr06c_passes",
        "physical_qualification": False,
        "request_sha256": request_sha,
        "request": request,
        **results,
    }
    payload = _json(document) + "\n"
    return DesignAnalysisArtifact(request_sha, _sha(payload), payload, f"{kind}.json")


def prepare_design_analysis(draft: DesignDraftArtifact) -> DesignAnalysisArtifact:
    """Compute nominal station kinematics from the exact downloadable draft."""
    design, angle = _load(draft)
    return _artifact(
        _request(draft, design), kind="active_design_analysis_preparation",
        preparation=_preparation(design, angle),
    )


def run_design_analysis(
    draft: DesignDraftArtifact,
    polar_families: Mapping[str, PolarFamily],
    *,
    settings: BEMRotorSettings | None = None,
) -> DesignAnalysisArtifact:
    """Run the existing BEM kernel on the fully-open first draft condition.

    Caller-supplied polar content is snapshotted, hashed and retained. It is
    unqualified input even when its metadata claims otherwise. There is no
    automatic proxy, clamp, nominal-envelope promotion or partial total.
    """
    design, angle = _load_open(draft)
    controls = BEMRotorSettings() if settings is None else settings
    if not isinstance(controls, BEMRotorSettings) or controls.radial_domain != "station_span":
        raise DesignAnalysisError("Active-design analysis requires station_span settings.")
    if (controls.annulus_count > 256 or controls.annulus_settings.bracket_samples > 512
            or controls.annulus_settings.max_iterations > 300):
        raise DesignAnalysisError("Analysis exceeds the bounded computation budget.")
    ids = {station.airfoil_id for station in design.blade.stations}
    if len(ids) != 1 or not isinstance(polar_families, Mapping) or set(polar_families) != ids:
        raise DesignAnalysisError("Supply exactly one matching polar family for the draft airfoil.")
    polar_content = {}
    for airfoil_id, family in polar_families.items():
        if not isinstance(family, PolarFamily) or family.airfoil_id != airfoil_id:
            raise DesignAnalysisError("The polar family airfoil identity does not match the draft.")
        polar_content[airfoil_id] = [
            asdict(table) for table in sorted(family.tables, key=lambda table: (table.mach, table.reynolds))
        ]
    # Detach nested mutable metadata before either hashing or solving.
    polar_content = json.loads(_json(polar_content))
    for airfoil_id, tables in polar_content.items():
        definition = next(foil for foil in design.airfoils if foil.id == airfoil_id)
        if definition.coordinates:
            expected = airfoil_coordinate_sha256(definition)
            if any(
                not isinstance(table["metadata"], Mapping)
                or table["metadata"].get("airfoil_coordinate_sha256") != expected
                for table in tables
            ):
                raise DesignAnalysisError("Every polar table must match the draft airfoil coordinate SHA-256.")
    snapshots = {
        airfoil_id: PolarFamily(tuple(PolarTable(**table) for table in tables))
        for airfoil_id, tables in polar_content.items()
    }
    request = _request(draft, design)
    request.update({
        "bem_rotor_schema_version": BEM_ROTOR_SCHEMA_VERSION,
        "policy": {**controls.as_mapping(), "bounds": "error", "solved_pose": "fully_open"},
        "polar_families": polar_content,
        "polar_evidence_status": "caller_supplied_unqualified",
    })
    try:
        result = solve_bem_rotor(
            design.blade, design.operating_conditions[0], snapshots,
            settings=controls, bounds="error",
        )
    except (ValueError, ArithmeticError, BEMRotorElementError) as exc:
        raise DesignAnalysisError(f"Active-design BEM failed without partial totals: {exc}") from exc
    return _artifact(
        request, kind="active_design_bem_screening",
        preparation=_preparation(design, angle), rotor=result.as_mapping(),
    )
