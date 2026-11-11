"""Post-processing and restoration of a recorded coupled run (no solver is executed).

The fixture is unmodified output of an actual DUST+MBDyn+preCICE run (see its README);
these tests exercise PyFoldable's acceptance logic and internal-correspondence checks.
"""
import json
import shutil
from pathlib import Path

import pytest

from pyfoldable.application import coupled_analysis as svc
from pyfoldable.coupled import postprocess
from pyfoldable.coupled.postprocess import digest

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "coupled" / "release_30w"


@pytest.fixture()
def run(tmp_path):
    dst = tmp_path / "run"
    shutil.copytree(FIXTURE, dst)
    return dst


def _build(run, outcome="finished"):
    return postprocess.build_result(run, participant_outcome=outcome, participant_message="",
                                    exit_codes={"mbdyn": 2, "dust": 0, "adapter": 0}, extraction_ok=True)


def _bytes(row):
    return json.dumps(row).encode()


def _reseal(row):
    body = {k: v for k, v in row.items() if k != "result_sha256"}
    return {**body, "result_sha256": digest(body)}


def test_recorded_run_is_accepted_and_consistent(run):
    row = _build(run)
    ex = row["execution"]
    assert ex["status"] == "completed" and ex["windows_accepted"] == 30 == ex["valid_prefix_windows"]
    checks = {c["name"]: c for c in row["checks"]}
    for name in ("kinematic_closure_position_m", "load_transfer_force_relative", "load_transfer_moment_relative",
                 "interface_power_closure_relative", "prescribed_speed_deviation_rpm", "hinge_balance_relative_residual"):
        assert checks[name]["passed"] is True, name
    theta = [r["theta_deg"][0] for r in row["series"]]
    assert theta[0] == pytest.approx(-5.0) and max(theta) > 0.0   # released, opened, reached the stop
    assert any(any(r["contact_active"]) for r in row["series"])
    assert all(r["within_admitted_table"] for r in row["series"])
    assert row["physical_qualification"] is False
    assert svc.read_saved_coupled_result(_bytes(row))["result_sha256"] == row["result_sha256"]


def test_failed_participant_never_becomes_completed(run):
    row = _build(run, outcome="failed")
    assert row["execution"]["status"] == "failed_solver"
    svc.read_saved_coupled_result(_bytes(row))


def test_unconverged_window_truncates_valid_prefix(run):
    log = run / "structure" / "precice-MBDyn-iterations.log"
    lines = log.read_text().splitlines()
    parts = lines[10].split()
    parts[3] = "0"
    lines[10] = "  ".join(parts)
    log.write_text("\n".join(lines) + "\n")
    row = _build(run)
    assert row["execution"]["status"] == "failed_unconverged_coupling"
    assert row["execution"]["first_unconverged_window"] == 10
    assert row["execution"]["valid_prefix_windows"] == 9


def test_reynolds_outside_admitted_table_is_a_coverage_failure(run):
    req = json.loads((run / "request.json").read_text())
    req["c81"]["envelope"]["reynolds"][1] = 250000.0
    (run / "request.json").write_text(json.dumps(req))
    row = _build(run)
    assert row["execution"]["status"] == "failed_aero_coverage"
    assert row["execution"]["first_uncovered_window"] == 1
    with pytest.raises(ValueError):  # the altered request no longer matches its digest
        svc.read_saved_coupled_result(_bytes(row))


@pytest.mark.parametrize("mutate,message", [
    (lambda r: r["series"][5].__setitem__("thrust_n", r["series"][5]["thrust_n"] + 0.1), "Thrust"),
    (lambda r: r["series"][7]["theta_deg"].__setitem__(0, r["series"][7]["theta_deg"][0] + 0.01), "Hinge angle"),
    (lambda r: r["series"][3].__setitem__("coupling_converged", False), "completed status"),
    (lambda r: r["radial"][40].__setitem__(7, 5.0e5), "Coverage verdict"),
])
def test_resealed_contradictions_are_rejected(run, mutate, message):
    row = _build(run)
    mutate(row)
    with pytest.raises(ValueError, match=message):
        svc.read_saved_coupled_result(_bytes(_reseal(row)))


def test_legacy_record_without_later_control_restores_but_unknown_omission_is_rejected(run):
    row = _build(run)
    assert "vortex_stretching" not in row["request"]["controls"]  # fixture predates the control
    svc.read_saved_coupled_result(_bytes(row))
    tampered = json.loads(json.dumps(row))
    req = tampered["request"]
    del req["controls"]["ll_tol"]
    req["request_sha256"] = digest({k: v for k, v in req.items() if k != "request_sha256"})
    with pytest.raises(ValueError, match="legacy meaning"):
        svc.read_saved_coupled_result(_bytes(_reseal(tampered)))


def test_altered_mechanics_or_table_is_rejected_even_when_digests_are_resealed(run):
    row = _build(run)
    for change in ("mechanics", "c81"):
        tampered = json.loads(json.dumps(row))
        req = tampered["request"]
        if change == "mechanics":
            req["mechanics"]["stop_stiffness_nm_per_rad"] *= 2
        else:
            req["c81"]["text"] = req["c81"]["text"].replace("0.31", "0.35", 1)
        body = {k: v for k, v in req.items() if k != "request_sha256"}
        req["request_sha256"] = digest(body)
        with pytest.raises(ValueError):
            svc.read_saved_coupled_result(_bytes(_reseal(tampered)))
