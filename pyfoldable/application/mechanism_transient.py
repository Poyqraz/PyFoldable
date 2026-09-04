"""Source-bound application contract for the PY-05A mechanism transient."""

from __future__ import annotations

import hashlib
import json
import platform
import re
import time
from dataclasses import asdict, dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any, Mapping

from pyfoldable import __version__
from pyfoldable.application.design_draft import DesignDraftArtifact
from pyfoldable.application.mechanism_binding import (
    MechanismBinding,
    MechanismBindingError,
    RadialMassSample,
    TipMassDistribution,
    bind_mechanism_draft,
    validate_mechanism_binding,
)
from pyfoldable.dynamics.mechanism_contracts import DryFriction
from pyfoldable.dynamics.mechanism_transient import (
    DriveHistory, MechanismParameters, SolverControls, TransientRequest,
    solve_mechanism_transient,
)

SERVICE_ID = "pyfoldable.application.mechanism_transient"
SERVICE_VERSION = 2
SOURCE_URL = "https://doi.org/10.1016/j.dib.2022.108388"
MAX_DRIVE_JSON_BYTES = 65_536
MAX_DRIVE_JSON_KNOTS = 4_096
MAX_BOUND_JSON_BYTES = 262_144


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
        "pyfoldable.dynamics.mechanism_contracts": Path(__file__).parents[1] / "dynamics/mechanism_contracts.py",
        "pyfoldable.application.mechanism_binding": Path(__file__).parent / "mechanism_binding.py",
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
        "contact_policy": set(asdict(request.transient.contact_policy)),
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
    references = provenance["references"]

    def valid_reference(item: object) -> bool:
        if not isinstance(item, dict):
            return False
        if set(item) == {"title", "doi", "transferred_values"}:
            return bool(
                isinstance(item["title"], str) and item["title"]
                and isinstance(item["doi"], str) and item["doi"]
                and isinstance(item["transferred_values"], dict)
            )
        if set(item) != {"binding_sha256", "binding"}:
            return False
        binding_sha = item.get("binding_sha256")
        binding = item.get("binding")
        return (
            isinstance(binding_sha, str)
            and re.fullmatch(r"[0-9a-f]{64}", binding_sha) is not None
            and isinstance(binding, dict)
            and _sha(_json(binding)) == binding_sha
        )

    if (not isinstance(references, list)
            or not all(valid_reference(item) for item in references)
            or not isinstance(provenance["limitations"], list)
            or not all(isinstance(item, str) and item
                       for item in provenance["limitations"])):
        raise MechanismTransientError("References and limitations must be explicit JSON lists.")
    return {"service_id": SERVICE_ID, "service_version": SERVICE_VERSION,
            "pyfoldable_version": __version__, "implementation": _implementation(),
            "model": "single_rigid_body_planar_hinge_prescribed_rotation",
            "coordinate_convention": "+z and theta CCW; theta=0 radial outward; negative theta folded",
            "transient": asdict(request.transient), "provenance": provenance}


def prepare_mechanism_transient(request: MechanismTransientRequest) -> MechanismTransientArtifact:
    document = _request_document(request)
    return MechanismTransientArtifact(_sha(_json(document)), None, None, None)


def load_drive_history_json(payload: str | bytes) -> DriveHistory:
    """Load the bounded exact v2 drive schema without duplicate JSON keys."""
    if not isinstance(payload, (str, bytes)):
        raise MechanismTransientError("Drive JSON must be UTF-8 text or bytes.")
    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    if len(raw) > MAX_DRIVE_JSON_BYTES:
        raise MechanismTransientError("Drive JSON size exceeds the bounded input limit.")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MechanismTransientError("Drive JSON must be valid UTF-8.") from exc

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise MechanismTransientError(f"Drive JSON contains duplicate key: {key}.")
            result[key] = value
        return result

    def reject_constant(value):
        raise MechanismTransientError(f"Drive JSON contains non-finite constant: {value}.")

    try:
        document = json.loads(text, object_pairs_hook=unique_object,
                              parse_constant=reject_constant)
    except MechanismTransientError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise MechanismTransientError("Drive JSON is malformed.") from exc
    required = {"time_s", "rpm", "applied_hinge_torque_nm"}
    if not isinstance(document, dict) or set(document) != required:
        raise MechanismTransientError("Drive JSON fields must exactly match the version-2 schema.")
    if any(not isinstance(document[name], list) for name in required):
        raise MechanismTransientError("Drive JSON fields must be arrays.")
    if len(document["time_s"]) > MAX_DRIVE_JSON_KNOTS:
        raise MechanismTransientError("Drive JSON exceeds the knot budget.")
    for name in required:
        if any(isinstance(value, bool) or not isinstance(value, (int, float))
               for value in document[name]):
            raise MechanismTransientError("Drive JSON arrays require numeric scalar values.")
    try:
        return DriveHistory(
            tuple(float(value) for value in document["time_s"]),
            tuple(float(value) for value in document["rpm"]),
            tuple(float(value) for value in document["applied_hinge_torque_nm"]),
        )
    except (ValueError, TypeError, OverflowError, ArithmeticError) as exc:
        raise MechanismTransientError(f"Drive JSON validation failed: {exc}") from exc


def _load_exact_json(payload: str | bytes, *, limit: int, label: str) -> dict[str, Any]:
    if not isinstance(payload, (str, bytes)):
        raise MechanismTransientError(f"{label} JSON must be UTF-8 text or bytes.")
    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    if len(raw) > limit:
        raise MechanismTransientError(f"{label} JSON size exceeds the bounded input limit.")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MechanismTransientError(f"{label} JSON must be valid UTF-8.") from exc

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise MechanismTransientError(f"{label} JSON contains duplicate key: {key}.")
            result[key] = value
        return result

    def reject_constant(value):
        raise MechanismTransientError(f"{label} JSON contains non-finite constant: {value}.")

    try:
        document = json.loads(
            text, object_pairs_hook=unique_object, parse_constant=reject_constant
        )
    except MechanismTransientError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise MechanismTransientError(f"{label} JSON is malformed.") from exc
    if not isinstance(document, dict):
        raise MechanismTransientError(f"{label} JSON root must be an object.")
    return document


def load_bound_mechanism_json(
    draft: DesignDraftArtifact, payload: str | bytes
) -> MechanismBinding:
    """Bind an exact active draft to a strict, bounded mechanism JSON document."""
    document = _load_exact_json(
        payload, limit=MAX_BOUND_JSON_BYTES, label="Bound mechanism"
    )
    fields = {
        "mass_distribution", "mechanical_source", "spring_stiffness_nm_rad",
        "rest_angle_rad", "viscous_damping_nm_s_rad", "initial_angle_rad",
        "initial_angular_velocity_rad_s", "drive", "dry_friction",
    }
    if set(document) != fields:
        raise MechanismTransientError(
            "Bound mechanism JSON fields must exactly match the version-1 schema."
        )
    mass_document = document["mass_distribution"]
    friction_document = document["dry_friction"]
    drive_document = document["drive"]
    if (not isinstance(mass_document, dict)
            or set(mass_document) != {"samples", "source", "classification"}
            or not isinstance(mass_document["samples"], list)
            or not 1 <= len(mass_document["samples"]) <= 4096):
        raise MechanismTransientError("Mass distribution must match the exact bounded schema.")
    if not isinstance(friction_document, dict) or set(friction_document) != {
        "mode", "coulomb_torque_nm", "transition_velocity_rad_s", "source"
    }:
        raise MechanismTransientError("Dry-friction fields must exactly match the schema.")
    if not isinstance(drive_document, dict):
        raise MechanismTransientError("Drive must be a JSON object.")
    try:
        samples = []
        for sample in mass_document["samples"]:
            required = {"distance_from_hinge_m", "mass_kg", "source"}
            allowed = required | {"intrinsic_inertia"}
            if not isinstance(sample, dict) or not required <= set(sample) <= allowed:
                raise MechanismTransientError("Mass-sample fields must exactly match the schema.")
            samples.append(RadialMassSample(**sample))
        drive = load_drive_history_json(_json(drive_document))
        friction = DryFriction(**friction_document)
        distribution = TipMassDistribution(
            tuple(samples), mass_document["source"], mass_document["classification"]
        )
        return bind_mechanism_draft(
            draft,
            distribution,
            spring_stiffness_nm_rad=document["spring_stiffness_nm_rad"],
            rest_angle_rad=document["rest_angle_rad"],
            viscous_damping_nm_s_rad=document["viscous_damping_nm_s_rad"],
            initial_angle_rad=document["initial_angle_rad"],
            initial_angular_velocity_rad_s=document["initial_angular_velocity_rad_s"],
            drive=drive,
            mechanical_source=document["mechanical_source"],
            controls=SolverControls(),
            dry_friction=friction,
        )
    except MechanismTransientError:
        raise
    except (MechanismBindingError, TypeError, ValueError, ArithmeticError, OverflowError) as exc:
        raise MechanismTransientError(f"Bound mechanism validation failed: {exc}") from exc


def _bound_request(binding: MechanismBinding) -> MechanismTransientRequest:
    try:
        binding = validate_mechanism_binding(binding)
        context = json.loads(binding.context_json)
    except (MechanismBindingError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise MechanismTransientError(f"Bound mechanism identity is invalid: {exc}") from exc
    transient = binding.request
    sources = {
        "parameters": {
            name: (
                binding.distribution.source
                if name in {"mass_kg", "cg_distance_m", "hinge_inertia_kg_m2"}
                else "exact_active_draft_hinge_geometry"
                if name in {"hinge_radius_m", "lower_stop_rad", "upper_stop_rad"}
                else binding.mechanical_source
            )
            for name in asdict(transient.parameters)
        },
        "drive": {name: binding.mechanical_source for name in asdict(transient.drive)},
        "initial_state": {
            "initial_angle_rad": binding.mechanical_source,
            "initial_angular_velocity_rad_s": binding.mechanical_source,
        },
        "controls": {
            name: "software_numerical_policy" for name in asdict(transient.controls)
        },
        "contact_policy": {
            name: "explicit_terminal_contact_policy"
            for name in asdict(transient.contact_policy)
        },
    }
    sources["parameters"]["dry_friction"] = transient.parameters.dry_friction.source
    return MechanismTransientRequest(
        transient,
        {
            "classification": "active_draft_bound_mechanism_screening_only",
            "prototype_measurement": False,
            "input_sources": sources,
            "references": [{
                "binding_sha256": binding.request_sha256,
                "binding": context,
            }],
            "limitations": list(context["limitations"]),
        },
    )


def prepare_bound_mechanism_transient(
    binding: MechanismBinding,
) -> MechanismTransientArtifact:
    return prepare_mechanism_transient(_bound_request(binding))


def run_bound_mechanism_transient(
    binding: MechanismBinding, *, expected_request_sha256: str | None = None
) -> MechanismTransientArtifact:
    return run_mechanism_transient(
        _bound_request(binding), expected_request_sha256=expected_request_sha256
    )


def run_mechanism_transient(request: MechanismTransientRequest, *, expected_request_sha256: str | None = None) -> MechanismTransientArtifact:
    request_document = _request_document(request)
    request_sha = _sha(_json(request_document))
    if expected_request_sha256 is not None and expected_request_sha256 != request_sha:
        raise MechanismTransientError("Prepared request identity no longer matches current inputs.")
    started = time.perf_counter()
    try:
        result = solve_mechanism_transient(request.transient)
    except (ValueError, RuntimeError, ArithmeticError, OverflowError, FloatingPointError) as exc:
        raise MechanismTransientError(f"Transient solve failed: {exc}") from exc
    result_data = asdict(result)
    result_data["samples"] = [
        {key: result_data[key][i] for key in (
            "time_s", "angle_rad", "angular_velocity_rad_s", "angular_acceleration_rad_s2",
            "rpm", "omega_rad_s", "omega_dot_rad_s2", "applied_torque_nm", "spring_torque_nm",
            "damping_torque_nm", "dry_friction_torque_nm", "centrifugal_torque_nm",
            "euler_torque_nm", "effective_energy_j", "applied_power_w", "damping_power_w",
            "dry_friction_power_w", "total_dissipation_power_w", "applied_work_j",
            "viscous_dissipated_energy_j", "dry_friction_dissipated_energy_j",
            "total_dissipated_energy_j")}
        for i in range(len(result.time_s))
    ]
    geometry_limitation = (
        "Active draft geometry is identity-bound, but no CAD mass/material inference, "
        "BEM, aerodynamic load or motor coupling is included."
        if request_document["provenance"]["classification"]
        == "active_draft_bound_mechanism_screening_only"
        else "No active blade geometry, BEM, aerodynamic load or motor coupling."
    )
    document = {"schema_version": 2, "artifact_class": "mechanism_transient_report",
                "qualification": "unqualified_mechanism_screening_only", "physical_qualification": False,
                "request_sha256": request_sha, "request": request_document,
                "runtime": {"elapsed_s": time.perf_counter() - started}, "result": result_data,
                "limitations": ["Dry friction is absent unless the explicit regularized Coulomb law is selected; static friction is not modelled.",
                                "First contact is audited on each RK45 quartic dense-output step; impact reaction, restitution, latch and bounce are not modelled.",
                                geometry_limitation,
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
        dry_friction=DryFriction(),
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
             "contact_policy": {"mode": "explicit_terminal_contact_policy"},
         },
         "references": [{"title": "Data for Folding and Deploying Identical Thick Panels with Spring-loaded Hinges",
                         "doi": SOURCE_URL, "transferred_values": {"inertia_kg_m2": inertia,
                         "natural_frequency_rad_s": natural_frequency, "damping_ratio": damping_ratio}}],
         "limitations": ["Effective k=I*omega_n^2 and c=2*I*omega_n*zeta are derived modal values.",
                         "This nonrotating aluminium rig is not the PyFoldable prototype."]},
    )
