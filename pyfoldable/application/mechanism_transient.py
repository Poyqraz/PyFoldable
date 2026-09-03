"""Source-bound application contract for the PY-05A mechanism transient."""

from __future__ import annotations

import hashlib
import json
import platform
import time
from dataclasses import asdict, dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any, Mapping

from pyfoldable import __version__
from pyfoldable.dynamics.mechanism_transient import (
    DriveHistory, MechanismParameters, SolverControls, TransientRequest,
    solve_mechanism_transient,
)

SERVICE_ID = "pyfoldable.application.mechanism_transient"
SERVICE_VERSION = 1
SOURCE_URL = "https://doi.org/10.1016/j.dib.2022.108388"


class MechanismTransientError(ValueError):
    """The application request cannot be evaluated without guessing."""


@dataclass(frozen=True)
class MechanismTransientRequest:
    transient: TransientRequest
    provenance: Mapping[str, Any]

    @property
    def parameters(self) -> MechanismParameters:
        return self.transient.parameters


@dataclass(frozen=True)
class MechanismTransientArtifact:
    request_sha256: str
    report_sha256: str | None
    report_json: str | None
    filename: str | None


def _json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise MechanismTransientError("Request must contain finite JSON-safe data.") from exc


def _sha(value: str | bytes) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def _implementation() -> dict[str, Any]:
    files = {
        SERVICE_ID: Path(__file__),
        "pyfoldable.dynamics.mechanism_transient": Path(__file__).parents[1] / "dynamics/mechanism_transient.py",
    }
    try:
        hashes = {name: _sha(path.read_bytes()) for name, path in files.items()}
    except OSError as exc:
        raise MechanismTransientError("Implementation source identity is unavailable.") from exc
    return {"source_files_sha256": hashes, "source_identity_scope": "disk_sources_at_request_time",
            "python": platform.python_version(), "numpy": version("numpy"), "scipy": version("scipy")}


def _request_document(request: MechanismTransientRequest) -> dict[str, Any]:
    if not isinstance(request, MechanismTransientRequest) or not isinstance(request.transient, TransientRequest):
        raise MechanismTransientError("Expected a validated mechanism transient request.")
    provenance = json.loads(_json(request.provenance))
    required = {"classification", "prototype_measurement", "input_sources", "references", "limitations"}
    if set(provenance) != required or provenance["prototype_measurement"] is not False:
        raise MechanismTransientError("Provenance must explicitly classify every unqualified input.")
    expected_sources = {
        "parameters": set(asdict(request.transient.parameters)),
        "drive": set(asdict(request.transient.drive)),
        "initial_state": {"initial_angle_rad", "initial_angular_velocity_rad_s"},
        "controls": set(asdict(request.transient.controls)),
    }
    if not isinstance(provenance["classification"], str) or not provenance["classification"]:
        raise MechanismTransientError("Provenance classification must be a nonempty string.")
    sources = provenance["input_sources"]
    if not isinstance(sources, dict) or set(sources) != set(expected_sources) or any(
        not isinstance(sources[group], dict) or set(sources[group]) != fields
        or any(not isinstance(value, str) or not value for value in sources[group].values())
        for group, fields in expected_sources.items()
    ):
        raise MechanismTransientError("Every request input requires string provenance.")
    if not isinstance(provenance["references"], list) or not isinstance(provenance["limitations"], list) or not all(
        isinstance(item, str) and item for item in provenance["limitations"]
    ):
        raise MechanismTransientError("References and limitations must be explicit JSON lists.")
    return {"service_id": SERVICE_ID, "service_version": SERVICE_VERSION,
            "pyfoldable_version": __version__, "implementation": _implementation(),
            "model": "single_rigid_body_planar_hinge_prescribed_rotation",
            "coordinate_convention": "+z and theta CCW; theta=0 radial outward; negative theta folded",
            "transient": asdict(request.transient), "provenance": provenance}


def prepare_mechanism_transient(request: MechanismTransientRequest) -> MechanismTransientArtifact:
    document = _request_document(request)
    return MechanismTransientArtifact(_sha(_json(document)), None, None, None)


def run_mechanism_transient(request: MechanismTransientRequest, *, expected_request_sha256: str | None = None) -> MechanismTransientArtifact:
    request_document = _request_document(request)
    request_sha = _sha(_json(request_document))
    if expected_request_sha256 is not None and expected_request_sha256 != request_sha:
        raise MechanismTransientError("Prepared request identity no longer matches current inputs.")
    started = time.perf_counter()
    try:
        result = solve_mechanism_transient(request.transient)
    except (ValueError, RuntimeError) as exc:
        raise MechanismTransientError(f"Transient solve failed: {exc}") from exc
    result_data = asdict(result)
    result_data["samples"] = [
        {key: result_data[key][i] for key in (
            "time_s", "angle_rad", "angular_velocity_rad_s", "angular_acceleration_rad_s2",
            "rpm", "omega_rad_s", "omega_dot_rad_s2", "applied_torque_nm", "spring_torque_nm",
            "damping_torque_nm", "centrifugal_torque_nm", "euler_torque_nm", "effective_energy_j",
            "damping_power_w")}
        for i in range(len(result.time_s))
    ]
    document = {"schema_version": 1, "artifact_class": "mechanism_transient_report",
                "qualification": "unqualified_mechanism_screening_only", "physical_qualification": False,
                "request_sha256": request_sha, "request": request_document,
                "runtime": {"elapsed_s": time.perf_counter() - started}, "result": result_data,
                "limitations": ["No dry friction, impact reaction, restitution, latch or bounce.",
                                "No active blade geometry, BEM, aerodynamic load or motor coupling.",
                                "Inputs are not measurements of the 250 mm prototype."]}
    payload = _json(document) + "\n"
    # The checksum is an envelope value so it can verify the exact delivered bytes
    # without a recursive/self-excluding JSON convention. Runtime makes each run
    # instance distinct; request_sha256 remains the deterministic input identity.
    report_sha = _sha(payload)
    return MechanismTransientArtifact(request_sha, report_sha, payload, "mechanism_transient_report.json")


def build_literature_modal_example() -> MechanismTransientRequest:
    inertia, natural_frequency, damping_ratio = 0.0051, 15.237, 0.111
    parameters = MechanismParameters(
        mass_kg=0.5, cg_distance_m=0.1, hinge_inertia_kg_m2=inertia, hinge_radius_m=0.0,
        spring_stiffness_nm_rad=inertia * natural_frequency**2, rest_angle_rad=0.0,
        viscous_damping_nm_s_rad=2 * inertia * natural_frequency * damping_ratio,
        lower_stop_rad=-1.5, upper_stop_rad=1.5,
    )
    parameter_sources = {name: "Yang et al. modal derivation" if name in {
        "hinge_inertia_kg_m2", "spring_stiffness_nm_rad", "viscous_damping_nm_s_rad"
    } else "illustrative_not_measured" for name in asdict(parameters)}
    return MechanismTransientRequest(
        TransientRequest(parameters, DriveHistory((0.0, 1.0), (0.0, 0.0), (0.0, 0.0)), 0.25, 0.0,
                         SolverControls(max_step_s=0.002)),
        {"classification": "literature_derived_modal_example", "prototype_measurement": False,
         "input_sources": {
             "parameters": parameter_sources,
             "drive": {name: "illustrative_not_measured" for name in asdict(DriveHistory((0.0, 1.0), (0.0, 0.0), (0.0, 0.0)))},
             "initial_state": {"initial_angle_rad": "illustrative_not_measured", "initial_angular_velocity_rad_s": "illustrative_not_measured"},
             "controls": {name: "software_numerical_policy" for name in asdict(SolverControls(max_step_s=0.002))},
         },
         "references": [{"title": "Data for Folding and Deploying Identical Thick Panels with Spring-loaded Hinges",
                         "doi": SOURCE_URL, "transferred_values": {"inertia_kg_m2": inertia,
                         "natural_frequency_rad_s": natural_frequency, "damping_ratio": damping_ratio}}],
         "limitations": ["Effective k=I*omega_n^2 and c=2*I*omega_n*zeta are derived modal values.",
                         "This nonrotating aluminium rig is not the PyFoldable prototype."]},
    )
