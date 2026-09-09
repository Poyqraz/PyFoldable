"""Offline PY-06D1 analytic example; stdout JSON, no prototype evidence."""
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pyfoldable.core.mechanism_observation import (
    MechanismObservationRun, ObservationProvenance, compare_mechanism_observations,
)
from pyfoldable.dynamics.mechanism_transient import (
    DriveHistory, MechanismParameters, TransientRequest,
)


def main():
    times = (0.0, 0.017, 0.101, 0.253, 0.4)
    angles = tuple(0.4 * math.cos(10 * t) for t in times)
    raw_sha = hashlib.sha256(json.dumps({"time_s": times, "angle_rad": angles}, sort_keys=True).encode()).hexdigest()
    source_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    provenance = ObservationProvenance(
        physical_run_id="synthetic-oscillator/run-1", raw_data_sha256=raw_sha,
        design_sha256=source_sha, blade_id="synthetic-rigid-tip",
        source="Closed-form theta=0.4*cos(10*t); not a prototype measurement",
        classification="software_fixture", angle_calibration_sha256=source_sha,
        synchronization_source="Analytic shared clock, no sensor",
        initial_state_source="Analytic theta(0)=0.4, theta_dot(0)=0",
        initial_state_method="declared_fixture", parameter_source="Synthetic J=0.003 and k=0.3",
        torque_source="Analytic zero input", torque_evidence="controlled_zero",
        clock_basis="synchronized_elapsed_seconds",
        angle_convention="relative_hinge_rad_ccw_z_zero_radial_unwrapped",
        rpm_processing="unfiltered_piecewise_linear", sampling_policy_source="Synthetic irregular sampling",
        max_drive_gap_s=0.4, max_observation_gap_s=0.2, clock_uncertainty_s=0.0,
    )
    request = TransientRequest(
        MechanismParameters(0.2, 0.1, 0.003, 0.0, 0.3, 0.0, 0.0, -2.0, 2.0),
        DriveHistory((0.0, 0.4), (0.0, 0.0), (0.0, 0.0)), 0.4, 0.0,
    )
    result = compare_mechanism_observations(
        MechanismObservationRun(request, provenance, times, angles, (0.001,) * len(times)))
    print(json.dumps(asdict(result), indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
