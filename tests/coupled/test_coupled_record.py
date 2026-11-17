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

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "coupled"
FIXTURE = FIXTURES / "release_30w"            # split_rigid topology (records before the continuous line)
FIXTURE_RBF = FIXTURES / "release_30w_rbf"    # continuous_rbf topology (default)


def _copy(tmp_path, src):
    dst = tmp_path / "run"
    shutil.copytree(src, dst)
    return dst


@pytest.fixture(params=[FIXTURE, FIXTURE_RBF], ids=["split_rigid", "continuous_rbf"])
def run(tmp_path, request):
    return _copy(tmp_path, request.param)


@pytest.fixture()
def legacy_run(tmp_path):
    return _copy(tmp_path, FIXTURE)


@pytest.fixture()
def rbf_run(tmp_path):
    return _copy(tmp_path, FIXTURE_RBF)


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


def _set_all(r, key, value):
    for s in r["series"]:
        s[key] = value(s) if callable(value) else value


def _zero_first(key):
    """Zero blade 0 in the window where the channel is largest (it is 0 in many windows)."""
    return lambda r: max(r["series"], key=lambda s: abs(s[key][0]))[key].__setitem__(0, 0.0)


def _pass_all_checks(r):
    for c in r["checks"]:
        if c["limit"] is not None:
            c.update(value=0.0, passed=True)


@pytest.mark.parametrize("mutate", [
    lambda r: _set_all(r, "latch_active", False),
    lambda r: _set_all(r, "contact_active", lambda s: [False] * len(s["contact_active"])),
    _zero_first("theta_rate_rad_s"),
    _zero_first("hinge_law_torque_nm"),
    lambda r: r["series"][12]["hinge_contact_torque_nm"].__setitem__(0, 1.0),
    lambda r: r["series"][5].__setitem__("drive_torque_nm", 0.0),
    lambda r: r["execution"].__setitem__("valid_prefix_windows", 5),
    lambda r: r["execution"].__setitem__("valid_prefix_windows", 99),
    lambda r: r["execution"].__setitem__("first_unconverged_window", 3),
    lambda r: r["execution"].__setitem__("first_outside_fold_envelope_window", 7),
    lambda r: r["execution"].__setitem__("status", "failed_unconverged_coupling"),  # every window converged
    lambda r: r["execution"].__setitem__("windows_planned", 29),
    _pass_all_checks,
], ids=["latch", "contact", "theta_rate", "hinge_law", "contact_torque", "drive", "prefix_5", "prefix_99",
        "first_unconverged", "first_outside", "status", "planned", "checks"])
def test_resealed_derived_fields_are_rejected(run, mutate):
    row = _build(run)
    mutate(row)
    with pytest.raises(ValueError):
        svc.read_saved_coupled_result(_bytes(_reseal(row)))


def test_record_without_envelope_keys_still_meets_todays_envelope(run, monkeypatch):
    row = _build(run)
    for key in ("fold_envelope", "first_outside_fold_envelope_window"):
        del row["execution"][key]
    resealed = _bytes(_reseal(row))
    svc.read_saved_coupled_result(resealed)  # how records written before the envelope rule look
    monkeypatch.setattr(svc, "fold_envelope", lambda case: {"fold_limit_deg": 1.0})  # every window outside
    with pytest.raises(ValueError, match="completed status"):
        svc.read_saved_coupled_result(resealed)


def _with_control(row, key, value):
    """Record as a legacy generator wrote it: the control is part of the request, case and its digest."""
    tampered = json.loads(json.dumps(row))
    req, case = tampered["request"], tampered["run_definition"]["case"]
    req["controls"][key] = case["controls"][key] = value
    req["case_sha256"] = digest(case)
    req["request_sha256"] = digest({k: v for k, v in req.items() if k != "request_sha256"})
    return _reseal(tampered)


def test_removed_control_restores_only_at_its_legacy_equivalent_value(legacy_run):
    row = _build(legacy_run)
    svc.read_saved_coupled_result(_bytes(_with_control(row, "junction_station_merge", False)))
    for key, value in (("junction_station_merge", True), ("junction_station_merge", 0),
                       ("coupling_load_relative_tol", 1e-4)):
        with pytest.raises(ValueError, match=key):
            svc.read_saved_coupled_result(_bytes(_with_control(row, key, value)))


def test_malformed_record_names_the_underlying_exception(run):
    row = _build(run)
    del row["joint_outputs"]
    with pytest.raises(ValueError, match="Malformed coupled result.*KeyError.*joint_outputs"):
        svc.read_saved_coupled_result(_bytes(_reseal(row)))


def test_run_list_marks_records_that_do_not_restore(tmp_path, monkeypatch):
    monkeypatch.setenv(svc.RUNS_ENV, str(tmp_path))
    good = shutil.copytree(FIXTURE, tmp_path / "20990101T000001_good")
    old = shutil.copytree(FIXTURE, tmp_path / "20990101T000002_old")
    for d in (good, old):
        _build(d)
        (d / "status.json").write_text(json.dumps({"state": "completed", "result_available": True}))
    row = json.loads((old / "result.json").read_text())
    row["request"]["case_sha256"] = "0" * 64  # what a record of an older case generator looks like
    req = row["request"]
    req["request_sha256"] = digest({k: v for k, v in req.items() if k != "request_sha256"})
    (old / "result.json").write_text(json.dumps(_reseal(row)))
    rows = {r["run_id"]: r for r in svc.local_run_summaries(tmp_path)}
    assert rows[good.name]["restorable"] is True and rows[good.name]["restore_error"] is None
    assert rows[old.name]["restorable"] is False
    assert "eski üretici sürümü" in rows[old.name]["restore_error"]
    (good / "result.json").write_text("{}")  # a changed file is verified again, not served from the cache
    assert svc.local_run_summaries(tmp_path)[-1]["restorable"] is False


def test_flow_window_requests_are_validated_and_bounded(run, tmp_path, monkeypatch):
    from pyfoldable.coupled import flow
    monkeypatch.setenv(svc.RUNS_ENV, str(tmp_path))
    row = _build(run)
    (run / "dust" / "Output").mkdir(parents=True, exist_ok=True)
    not_ready = type("R", (), {"status": "missing", "message": "no toolchain"})()
    for extra in ([0], [31], [True], ["5"]):
        with pytest.raises(flow.FlowCompanionError) as err:
            svc.build_flow(tmp_path, row, extra_windows=extra, readiness=not_ready)
        assert err.value.code == "bad_window"
    fits = len(set(flow.select_windows(row, 2)) | {13})
    assert fits < 30
    monkeypatch.setattr(flow, "MAX_NPZ_BYTES", fits * svc.flow_frame_bytes_bound(row))
    with pytest.raises(flow.FlowCompanionError) as err:  # every one of the 30 windows
        svc.build_flow(tmp_path, row, max_frames=30, readiness=not_ready)
    assert err.value.code == "too_many_frames"
    with pytest.raises(flow.FlowCompanionError) as err:  # within bounds, it reaches the toolchain gate
        svc.build_flow(tmp_path, row, max_frames=2, extra_windows=[13], readiness=not_ready)
    assert err.value.code == "toolchain_missing"


def test_legacy_record_without_later_control_restores_but_unknown_omission_is_rejected(legacy_run):
    row = _build(legacy_run)
    assert "vortex_stretching" not in row["request"]["controls"]  # fixture predates the control
    svc.read_saved_coupled_result(_bytes(row))
    tampered = json.loads(json.dumps(row))
    req = tampered["request"]
    del req["controls"]["ll_tol"]
    req["request_sha256"] = digest({k: v for k, v in req.items() if k != "request_sha256"})
    with pytest.raises(ValueError, match="legacy meaning"):
        svc.read_saved_coupled_result(_bytes(_reseal(tampered)))


def test_continuous_rbf_record_reduces_dust_loads_and_keeps_only_body_states(rbf_run):
    """Real DUST rbf output: the independent RBF reduction closes on the exchanged node loads, the hinge
    moment sums the distal-segment nodes, and the record keeps MBDyn states of hub and body nodes only
    (coupling-node kinematics are already in the exchanged window data)."""
    row = _build(rbf_run)
    assert row["request"]["controls"]["aero_topology"] == "continuous_rbf"
    nodes = row["run_definition"]["coupling_nodes"]
    assert len(nodes) > 4 and len({n["dust_component"] for n in nodes}) == 2
    checks = {c["name"]: c for c in row["checks"]}
    assert checks["load_transfer_moment_relative"]["value"] < 1e-5
    assert {r[2] for r in row["radial"]} == {"proximal", "distal", "junction"}
    labels = {int(k) for k in row["node_states"][-1]["nodes"]}
    assert labels == {1, 2, 100, 101, 200, 201}
    w = row["window_exchange"][10]
    hinge = row["node_states"][11]["nodes"]["200"]["x"]
    m_h = sum(w["moment"][i][2] + (w["position"][i][0] - hinge[0]) * w["force"][i][1]
              - (w["position"][i][1] - hinge[1]) * w["force"][i][0]
              for i, n in enumerate(nodes) if n["blade"] == 0 and n["segment"] == "distal")
    assert row["series"][10]["hinge_aero_torque_nm"][0] == pytest.approx(m_h, abs=1e-12)


def test_saved_coupling_nodes_must_match_the_regenerated_case(run):
    row = _build(run)
    tampered = json.loads(json.dumps(row))
    node = next(n for n in tampered["run_definition"]["coupling_nodes"] if n["segment"] == "distal")
    node["segment"] = "proximal"
    with pytest.raises(ValueError, match="coupling nodes"):
        svc.read_saved_coupled_result(_bytes(_reseal(tampered)))


def test_result_size_estimate_bounds_recorded_runs_and_rejects_oversized_runs(run):
    from pyfoldable.coupled import deck as deckmod
    from pyfoldable.coupled.model import CoupledCase
    row = _build(run)
    case = svc.case_from_record(row)
    assert svc.estimated_result_bytes(case) >= len(_bytes(row))
    long_case = svc.case_from_record(row, duration_s=2.0)
    assert svc.estimated_result_bytes(long_case) > svc.MAX_COUPLED_RESULT_BYTES
    with pytest.raises(svc.CoupledPreparationError) as err:
        svc.check_result_budget(long_case)
    assert err.value.code == "result_too_large"
    svc.check_result_budget(case)


def test_supported_duration_is_explicit_and_is_the_size_budget_boundary(run):
    import math
    row = _build(run)
    case = svc.case_from_record(row)
    lim = svc.supported_duration(case)
    assert lim["windows"] >= 1 and lim["limit_bytes"] == svc.MAX_COUPLED_RESULT_BYTES
    assert lim["revolutions"] == pytest.approx(lim["duration_s"] * case.omega_rad_s / (2 * math.pi))
    edge = svc.case_from_record(row, duration_s=lim["duration_s"])
    assert edge.n_steps == lim["windows"]
    svc.check_result_budget(edge)
    over = svc.case_from_record(row, duration_s=lim["duration_s"] + 2 * case.dt_s)
    with pytest.raises(svc.CoupledPreparationError) as err:
        svc.check_result_budget(over)
    assert err.value.code == "result_too_large"
    assert f"{lim['duration_s']:.3f}" in str(err.value)


def test_compressed_record_restores_losslessly_and_inflation_is_bounded(run):
    import gzip
    row = _build(run)
    plain = svc.record_json_bytes(row)
    archive = svc.record_archive_bytes(row)
    assert archive[:2] == b"\x1f\x8b" and len(archive) < len(plain)
    assert svc.record_archive_bytes(row) == archive  # deterministic (no timestamp)
    assert gzip.decompress(archive) == plain
    assert svc.read_saved_coupled_result(archive) == svc.read_saved_coupled_result(plain)
    with pytest.raises(ValueError, match="size"):
        svc.read_saved_coupled_result(gzip.compress(b" " * (svc.MAX_COUPLED_RESULT_BYTES + 1), mtime=0))
    with pytest.raises(ValueError, match="size"):
        svc.read_saved_coupled_result(b"\x1f\x8b" + b"\0" * svc.MAX_COUPLED_ARCHIVE_BYTES)
    with pytest.raises(ValueError):
        svc.read_saved_coupled_result(archive[:-12])  # truncated stream
    with pytest.raises(ValueError):
        svc.read_saved_coupled_result(archive + archive)  # concatenated members are not one record
    with pytest.raises(ValueError):
        svc.read_saved_coupled_result(archive + b"trailing")


def test_xz_record_restores_losslessly_and_decoding_is_bounded(run):
    import lzma
    row = _build(run)
    plain = svc.record_json_bytes(row)
    archive = svc.record_xz_bytes(row)
    assert archive[:6] == svc.XZ_MAGIC and len(archive) < len(plain)
    assert svc.record_xz_bytes(row) == archive  # deterministic
    assert lzma.decompress(archive) == plain
    assert svc.read_saved_coupled_result(archive) == svc.read_saved_coupled_result(plain)
    xz = dict(format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC64)
    with pytest.raises(ValueError, match="size"):  # inflation bomb
        svc.read_saved_coupled_result(lzma.compress(b" " * (svc.MAX_COUPLED_RESULT_BYTES + 1), preset=6, **xz))
    with pytest.raises(ValueError, match="size"):
        svc.read_saved_coupled_result(svc.XZ_MAGIC + b"\0" * svc.MAX_COUPLED_ARCHIVE_BYTES)
    with pytest.raises(ValueError):  # decoder dictionary beyond the memory limit
        svc.read_saved_coupled_result(lzma.compress(plain, preset=9, **xz))
    with pytest.raises(ValueError):
        svc.read_saved_coupled_result(archive[:-12])  # truncated stream
    with pytest.raises(ValueError):
        svc.read_saved_coupled_result(archive + archive)  # concatenated streams are not one record
    with pytest.raises(ValueError):
        svc.read_saved_coupled_result(archive + b"trailing")
    with pytest.raises(ValueError):
        svc.read_saved_coupled_result(lzma.compress(plain, format=lzma.FORMAT_ALONE))  # not the declared container


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
