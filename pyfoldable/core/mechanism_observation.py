"""PY-06D1 source-bound transition observations; comparison is never qualification.

Only a declared pre-contact phase of the PY-05 single rigid-tip model is supported.
Source hashes bind declarations, not independently verified raw data or certificates.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import platform
import re

from pyfoldable.dynamics.mechanism_transient import (
    StopContact, TransientRequest, sample_mechanism_transient,
)


def _finite(value: float, label: str, *, positive: bool = False) -> None:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or (value <= 0 if positive else value < 0)):
        raise ValueError(f"{label} must be finite and {'positive' if positive else 'nonnegative'}.")


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha(value: str | bytes) -> str:
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def _machine_coincident(a: float, b: float) -> bool:
    # A diagnostic only: never extend the trajectory or accept physical timing.
    return abs(a - b) <= 8 * max(math.ulp(a), math.ulp(b))


@dataclass(frozen=True)
class ObservationProvenance:
    physical_run_id: str
    raw_data_sha256: str
    design_sha256: str
    blade_id: str
    source: str
    classification: str
    angle_calibration_sha256: str
    synchronization_source: str
    initial_state_source: str
    initial_state_method: str
    parameter_source: str
    torque_source: str
    torque_evidence: str
    clock_basis: str
    angle_convention: str
    rpm_processing: str
    sampling_policy_source: str
    max_drive_gap_s: float
    max_observation_gap_s: float
    clock_uncertainty_s: float

    def __post_init__(self):
        numeric = {"max_drive_gap_s", "max_observation_gap_s", "clock_uncertainty_s"}
        for field in fields(self):
            value = getattr(self, field.name)
            if field.name in numeric:
                _finite(value, field.name, positive=field.name != "clock_uncertainty_s")
            elif not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > 2048:
                raise ValueError(f"{field.name} requires bounded nonblank text without edge whitespace.")
            elif field.name.endswith("sha256") and re.fullmatch(r"[0-9a-f]{64}", value) is None:
                raise ValueError(f"{field.name} requires a canonical SHA-256.")
        allowed = {
            "classification": {"software_fixture", "measured"},
            "initial_state_method": {"independent_measurement", "declared_fixture"},
            "torque_evidence": {"controlled_zero", "independently_measured"},
            "clock_basis": {"synchronized_elapsed_seconds"},
            "angle_convention": {"relative_hinge_rad_ccw_z_zero_radial_unwrapped"},
            "rpm_processing": {"unfiltered_piecewise_linear"},
        }
        for name, choices in allowed.items():
            if getattr(self, name) not in choices:
                raise ValueError(f"Unsupported {name}.")
        if self.classification == "measured" and self.initial_state_method != "independent_measurement":
            raise ValueError("Measured observations require independent initial-state measurement.")


@dataclass(frozen=True)
class ObservedContact:
    stop: str
    time_s: float

    def __post_init__(self):
        if self.stop not in ("lower", "upper"):
            raise ValueError("Observed contact must name lower or upper stop.")
        _finite(self.time_s, "contact time")


@dataclass(frozen=True)
class MechanismObservationRun:
    request: TransientRequest
    provenance: ObservationProvenance
    time_s: tuple[float, ...]
    angle_rad: tuple[float, ...]
    standard_uncertainty_rad: tuple[float, ...]
    observed_contact: ObservedContact | None = None

    def __post_init__(self):
        if not isinstance(self.request, TransientRequest) or not isinstance(self.provenance, ObservationProvenance):
            raise ValueError("Typed transient request and observation provenance are required.")
        arrays = (self.time_s, self.angle_rad, self.standard_uncertainty_rad)
        if (any(not isinstance(x, tuple) for x in arrays)
                or not 2 <= len(self.time_s) <= min(50_000, self.request.controls.max_samples)
                or any(len(x) != len(self.time_s) for x in arrays)):
            raise ValueError("Observation tuples require equal bounded lengths of at least two.")
        for t, angle, uncertainty in zip(*arrays):
            _finite(t, "observation time")
            _finite(uncertainty, "angle standard uncertainty")
            if isinstance(angle, bool) or not isinstance(angle, (int, float)) or not math.isfinite(angle):
                raise ValueError("Observation angle must be a finite radian value.")
        if any(b <= a for a, b in zip(self.time_s, self.time_s[1:])):
            raise ValueError("Observation times must increase strictly.")
        drive = self.request.drive
        if self.time_s[0] != drive.time_s[0] or self.time_s[-1] != drive.time_s[-1]:
            raise ValueError("Observations must cover the entire declared drive phase without extrapolation.")
        for times, limit in ((drive.time_s, self.provenance.max_drive_gap_s),
                             (self.time_s, self.provenance.max_observation_gap_s)):
            if any(b - a > limit for a, b in zip(times, times[1:])):
                raise ValueError("A declared maximum sampling gap was exceeded.")
        if self.provenance.torque_evidence == "controlled_zero" and any(drive.applied_hinge_torque_nm):
            raise ValueError("Controlled-zero torque must contain only explicit zero values.")
        if self.observed_contact is not None and (
                not isinstance(self.observed_contact, ObservedContact)
                or self.observed_contact.time_s != self.time_s[-1]):
            raise ValueError("The supported observed phase ends at its declared first contact.")


def _request_document(run: MechanismObservationRun) -> str:
    if not isinstance(run, MechanismObservationRun):
        raise ValueError("Expected a typed mechanism observation run.")
    root = Path(__file__).parents[1]
    paths = ("core/mechanism_observation.py", "dynamics/mechanism_transient.py",
             "dynamics/mechanism_contracts.py")
    return _json({"schema_version": 1, "run": asdict(run), "implementation": {
        "source_files_sha256": {path: _sha((root / path).read_bytes()) for path in paths},
        "source_identity_scope": "disk_sources_at_request_time",
        "python": platform.python_version(), "numpy": version("numpy"), "scipy": version("scipy"),
    }})


@dataclass(frozen=True)
class MechanismObservationComparison:
    request_sha256: str
    request_json: str
    status: str
    measurement_readiness: str
    compared_time_s: tuple[float, ...]
    predicted_angle_rad: tuple[float, ...]
    residual_rad: tuple[float, ...]
    standard_uncertainty_rad: tuple[float, ...]
    excluded_time_s: tuple[float, ...]
    exclusion_reason: str | None
    rmse_rad: float | None
    max_absolute_residual_rad: float | None
    predicted_contact: StopContact | None
    contact_assessment: str
    contact_time_residual_s: float | None
    uncertainty_assessment: str = "indeterminate_model_drive_and_clock_uncertainty_unpropagated"
    physical_qualification: bool = False
    parameter_fitting_performed: bool = False


def compare_mechanism_observations(
    run: MechanismObservationRun, *, expected_request_sha256: str | None = None,
) -> MechanismObservationComparison:
    """Report model-minus-observed residuals; never fit time, state or parameters."""
    document = _request_document(run)
    request_sha = _sha(document)
    if expected_request_sha256 is not None and request_sha != expected_request_sha256:
        raise ValueError("Prepared observation request is stale.")
    prediction = sample_mechanism_transient(run.request, run.time_s)
    count = len(prediction.time_s)
    if prediction.time_s != run.time_s[:count]:
        raise RuntimeError("Prediction does not preserve the requested observation times.")
    residual = tuple(a - b for a, b in zip(prediction.angle_rad, run.angle_rad))
    if any(not math.isfinite(x) for x in residual):
        raise ValueError("Observation residual overflowed.")
    predicted, observed = prediction.result.contact, run.observed_contact
    event_residual = None
    if predicted is not None and observed is not None:
        event = "same_stop_timing_reported" if predicted.stop == observed.stop else "different_stop"
        event_residual = predicted.time_s - observed.time_s
    elif predicted is not None:
        event = "predicted_contact_not_observed"
    elif observed is not None:
        event = "observed_contact_not_predicted"
    else:
        event = "no_contact_in_declared_phase"
    excluded = run.time_s[count:]
    boundary = bool(predicted is not None and excluded
                    and all(_machine_coincident(t, predicted.time_s) for t in excluded)
                    and (observed is None or observed.stop == predicted.stop))
    if predicted is None and observed is not None:
        stop_angle = getattr(run.request.parameters, observed.stop + "_stop_rad")
        boundary = _machine_coincident(prediction.result.angle_rad[-1], stop_angle)
    if boundary:
        event = "indeterminate_contact_boundary"
    status = ("blocked_incomplete_prediction" if excluded else
              "screening_event_mismatch" if event in {"different_stop", "predicted_contact_not_observed", "observed_contact_not_predicted"}
              else "screening_only")
    if boundary:
        status = "indeterminate_contact_boundary"
    # Scaled squares avoid overflow even when finite observations are very large.
    maximum = max(map(abs, residual), default=0.0)
    rmse = maximum * math.sqrt(math.fsum((x / maximum)**2 for x in residual) / count) if maximum else 0.0
    return MechanismObservationComparison(
        request_sha, document, status,
        "measured_declared_unverified" if run.provenance.classification == "measured" else "pending_no_measured_evidence",
        prediction.time_s, prediction.angle_rad, residual, run.standard_uncertainty_rad[:count],
        excluded, "prediction_terminated_at_first_contact" if excluded else None,
        None if excluded else rmse, None if excluded else maximum,
        predicted, event, event_residual,
    )


@dataclass(frozen=True)
class MechanismRunPartition:
    partition_sha256: str
    training_run_ids: tuple[str, ...]
    holdout_run_ids: tuple[str, ...]
    training_request_sha256: tuple[str, ...]
    holdout_request_sha256: tuple[str, ...]
    all_runs_declared_measured: bool


def partition_mechanism_runs(
    training: tuple[MechanismObservationRun, ...], holdout: tuple[MechanismObservationRun, ...],
) -> MechanismRunPartition:
    """Freeze declared physical-run partitions before fitting or preprocessing.

    Raw-data aliases are rejected even if renamed. Truthful acquisition identities
    remain a caller obligation: new fabricated IDs cannot be detected from hashes.
    """
    if any(not isinstance(group, tuple) or not 1 <= len(group) <= 64 for group in (training, holdout)):
        raise ValueError("Nonempty bounded training and holdout tuples are required.")
    runs = training + holdout
    if any(not isinstance(run, MechanismObservationRun) for run in runs):
        raise ValueError("Partitions require typed observation runs.")
    for field in ("physical_run_id", "raw_data_sha256"):
        values = [getattr(run.provenance, field) for run in runs]
        if len(set(values)) != len(values):
            raise ValueError(f"Repeated {field}: physical run/alias leakage in partition.")
    if len({(run.provenance.design_sha256, run.provenance.blade_id) for run in runs}) != 1:
        raise ValueError("Partitions must bind the same design revision and blade.")
    train_ids = tuple(run.provenance.physical_run_id for run in training)
    holdout_ids = tuple(run.provenance.physical_run_id for run in holdout)
    train_hashes = tuple(_sha(_request_document(run)) for run in training)
    holdout_hashes = tuple(_sha(_request_document(run)) for run in holdout)
    ready = all(run.provenance.classification == "measured" for run in runs)
    return MechanismRunPartition(_sha(_json({"training": train_hashes, "holdout": holdout_hashes})),
                                 train_ids, holdout_ids, train_hashes, holdout_hashes, ready)
