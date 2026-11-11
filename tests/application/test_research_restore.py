"""Resealed contradictions from the WSL restore finding; no numerical solver."""
from copy import deepcopy
from dataclasses import replace
import json
import math
from pathlib import Path

import pytest

from pyfoldable.application import mechanism_transient as mech
from pyfoldable.application import provider_design_analysis as managed
from pyfoldable.application import research_design as research
from pyfoldable.application.research_result_checks import check_mechanism_history
from pyfoldable.dynamics.mechanism_contracts import DryFriction
from pyfoldable.dynamics.mechanism_transient import DriveHistory, RPM_TO_RAD_S, StopContact
from research_inert_support import bem, inert_history, mechanism, store

ROOT = Path(__file__).resolve().parents[2]


def encode(row):
    row["result_sha256"] = research._digest({k: v for k, v in row.items() if k != "result_sha256"})
    return research.saved_result_json(row).encode()


@pytest.fixture
def case(tmp_path, monkeypatch):
    store(tmp_path, monkeypatch, ("NACA2412",))
    calls = bem(monkeypatch)
    active = research.build_research_design(ROOT, research.defaults(ROOT))
    repo = managed.application_provider_repository()
    row = research.run_research(active, repo.families[0], repo, None)
    assert len(calls) == 1
    return active, row, calls


@pytest.mark.parametrize("edits", [{"rpm": 7100.}, {"hinge_mm": 220., "root_mm": 120.}, {"root_mm": 120.}])
def test_restore_rejects_resealed_mismatched_inputs_even_with_rederived_outer_geometry(case, edits):
    active, row, calls = case
    other = research.build_research_design(ROOT, replace(active.inputs, **edits))
    row.update(inputs=research.asdict(other.inputs), geometry=research.geometry_result(other),
               input_sha256=replace(other, draft=active.draft).identity)
    with pytest.raises(ValueError, match="contradict"):
        research.read_saved_result(encode(row))
    assert len(calls) == 1


def test_restore_rejects_resealed_executed_operating_condition(case):
    _, row, _ = case
    doc = json.loads(row["aerodynamics"]["report_text"])
    doc["request"]["operating_condition"]["forward_speed_m_s"] = 19.
    doc["request_sha256"] = research.design_analysis._sha(research.design_analysis._json(doc["request"]))
    text = research.design_analysis._json(doc) + "\n"
    artifact = research.design_analysis.DesignAnalysisArtifact(
        doc["request_sha256"], research.hashlib.sha256(text.encode()).hexdigest(), text, "INERT.json")
    row["aerodynamics"] = managed.snapshot_success(artifact, evidence_class="inert_fixture")
    with pytest.raises(ValueError, match="contradict"):
        research.read_saved_result(encode(row))


def test_legacy_restore_uses_retained_draft_not_current_defaults(case, monkeypatch):
    _, row, calls = case
    row.pop("template_toml", None)
    for key in ("declared_stow_limit_deg", "declared_stow_limit_centerline_envelope_m",
                "legacy_audit_full_stow_fields_scope"):
        row["geometry"].pop(key)
    row["mechanism"].pop("requested", None)
    monkeypatch.setattr(research, "defaults", lambda *a: pytest.fail("Current defaults read on restore"))
    monkeypatch.setattr(research, "build_research_design", lambda *a: pytest.fail("Current design rebuilt on restore"))
    assert research.read_saved_result(encode(row)) == row
    assert len(calls) == 1


def test_restore_rejects_resealed_derived_geometry_and_failure_attribution(case):
    active, _, calls = case
    failure = research.run_research(active, None, managed.ManagedProviderRepository(), None)
    assert research.read_saved_result(encode(failure)) == failure
    other = deepcopy(failure)
    other["geometry"]["first_aerodynamic_station_m"] = .100
    with pytest.raises(ValueError, match="contradict"):
        research.read_saved_result(encode(other))
    other = deepcopy(failure)
    snapshot = other["aerodynamics"]
    snapshot.pop("failure_reason")
    other["aerodynamics"] = managed._seal(snapshot)
    with pytest.raises(ValueError):
        research.read_saved_result(encode(other))
    assert len(calls) == 1


def test_restore_binds_mechanics_to_inputs_and_initial_pose(case, monkeypatch):
    active, _, calls = case
    options = research.MechanismInputs(10., 40., .000001, "INERT assumed CG", 1200., .5, .1,
                                       .01, -10., .001, .002, "none", 0., 0.)
    runs = mechanism(monkeypatch)
    row = research.run_research(active, None, managed.ManagedProviderRepository(), options)
    assert row["mechanism"]["status"] == "computed" and len(runs) == 1
    monkeypatch.setattr(mech, "solve_mechanism_transient", lambda *a: pytest.fail("Restore reran mechanism"))
    assert research.read_saved_result(encode(row)) == row
    other = deepcopy(row)
    other["mechanism"]["inputs"]["mass_g"] = 11.
    with pytest.raises(ValueError, match="contradict"):
        research.read_saved_result(encode(other))
    other = deepcopy(row)
    pose = replace(active, inputs=replace(active.inputs, fold_deg=-70.))
    other.update(inputs=research.asdict(pose.inputs), geometry=research.geometry_result(pose), input_sha256=pose.identity)
    with pytest.raises(ValueError, match="contradict"):
        research.read_saved_result(encode(other))
    other = deepcopy(row)
    report = json.loads(other["mechanism"]["report_text"])
    report["result"]["samples"] = []
    other["mechanism"]["report_text"] = mech._json(report) + "\n"
    other["mechanism"]["report_sha256"] = mech._sha(other["mechanism"]["report_text"])
    with pytest.raises(ValueError):
        research.read_saved_result(encode(other))
    assert len(calls) == 1


def test_restore_rejects_resealed_foreign_admission(case):
    _, row, _ = case
    doc = json.loads(row["aerodynamics"]["report_text"])
    q = doc["request"]
    admission = q["provider_design_admission"]
    admission["geometry"]["profile"] = "NACA0012"
    q["provider_design_request_sha256"] = research._digest(
        {"admission": admission, "polar_run_sha256": q["ui_request_sha256"]})
    doc["request_sha256"] = research.design_analysis._sha(research.design_analysis._json(q))
    payload = research.design_analysis._json(doc) + "\n"
    a = research.design_analysis.DesignAnalysisArtifact(
        doc["request_sha256"], research.hashlib.sha256(payload.encode()).hexdigest(), payload, "INERT.json")
    row["aerodynamics"] = managed.snapshot_success(a, evidence_class="inert_fixture")
    with pytest.raises(ValueError, match="admitted geometry profile contradicts"):
        research.read_saved_result(encode(row))


def test_restore_preserves_real_attempt_shape_for_solver_failure(case, monkeypatch):
    active, _, _ = case
    calls = bem(monkeypatch, fail=True)
    repo = managed.application_provider_repository()
    row = research.run_research(active, repo.families[0], repo, None)
    assert row["aerodynamics"]["failure_stage"] == "solver_invocation"
    assert row["aerodynamics"]["report_text"] is None
    assert research.read_saved_result(encode(row)) == row
    assert len(calls) == 1


def test_restore_uses_frozen_source_for_new_chord_and_twist_controls(case):
    active, row, _ = case
    forged = replace(active, inputs=replace(active.inputs, chord_scale=1.1))
    row.update(inputs=research.asdict(forged.inputs), input_sha256=forged.identity)
    with pytest.raises(ValueError, match="chord scale contradicts"):
        research.read_saved_result(encode(row))


@pytest.mark.parametrize("field,value", [("thrust_n", "foreign"), ("polar_query_envelope", {})])
def test_restore_rejects_invalid_success_output_shapes(case, field, value):
    _, row, _ = case
    doc = json.loads(row["aerodynamics"]["report_text"])
    doc["rotor"][field] = value
    payload = research.design_analysis._json(doc) + "\n"
    a = research.design_analysis.DesignAnalysisArtifact(
        doc["request_sha256"], research.hashlib.sha256(payload.encode()).hexdigest(), payload, "INERT.json")
    row["aerodynamics"] = managed.snapshot_success(a, evidence_class="inert_fixture")
    with pytest.raises(ValueError):
        research.read_saved_result(encode(row))


def test_restore_rejects_foreign_provider_cell_with_resealed_report(tmp_path, monkeypatch):
    store(tmp_path, monkeypatch, ("NACA0012", "NACA2412"))
    bem(monkeypatch)
    repo = managed.application_provider_repository()
    rows = {}
    for f in repo.families:
        profile = f.requests[0].airfoil.id
        active = research.build_research_design(ROOT, replace(research.defaults(ROOT), profile=profile))
        rows[profile] = research.run_research(active, f, repo, None)
    row = rows["NACA2412"]
    doc = json.loads(row["aerodynamics"]["report_text"])
    other = json.loads(rows["NACA0012"]["aerodynamics"]["report_text"])
    q = doc["request"]
    admission = q["provider_design_admission"]
    admission["cells"][0] = other["request"]["provider_design_admission"]["cells"][0]
    q["provider_design_request_sha256"] = research._digest(
        {"admission": admission, "polar_run_sha256": q["ui_request_sha256"]})
    doc["request_sha256"] = research.design_analysis._sha(research.design_analysis._json(q))
    payload = research.design_analysis._json(doc) + "\n"
    a = research.design_analysis.DesignAnalysisArtifact(
        doc["request_sha256"], research.hashlib.sha256(payload.encode()).hexdigest(), payload, "INERT.json")
    row["aerodynamics"] = managed.snapshot_success(a, evidence_class="inert_fixture")
    with pytest.raises(ValueError, match="cell.*contradicts"):
        research.read_saved_result(encode(row))


def test_restore_rejects_resealed_total_in_conflict_with_retained_radial_loads(case):
    _, row, _ = case
    doc = json.loads(row["aerodynamics"]["report_text"])
    doc["rotor"]["thrust_n"] = 1000.
    payload = research.design_analysis._json(doc) + "\n"
    a = research.design_analysis.DesignAnalysisArtifact(
        doc["request_sha256"], research.hashlib.sha256(payload.encode()).hexdigest(), payload, "INERT.json")
    row["aerodynamics"] = managed.snapshot_success(a, evidence_class="inert_fixture")
    with pytest.raises(ValueError, match="thrust total contradicts"):
        research.read_saved_result(encode(row))



def _reseal_report(row, doc):
    payload = research.design_analysis._json(doc) + "\n"
    artifact = research.design_analysis.DesignAnalysisArtifact(
        doc["request_sha256"], research.hashlib.sha256(payload.encode()).hexdigest(), payload, "INERT.json")
    row["aerodynamics"] = managed.snapshot_success(artifact, evidence_class=row["aerodynamics"]["evidence_class"])
    return encode(row)


def reseal_rotor(row, mutate):
    doc = json.loads(row["aerodynamics"]["report_text"])
    mutate(doc["rotor"])
    # Regenerate the output hash and all snapshot copies before the outer checksum.
    return _reseal_report(row, doc)


def out_of_domain_mach(rotor):
    solution = rotor["elements"][0]["solution"]
    solution["mach"] = solution["polar_query_envelope"]["mach_max"] = .9
    rotor["polar_query_envelope"]["mach_max"] = .9


@pytest.mark.parametrize("mutation,diagnostic", [
    (lambda rotor: rotor["elements"][0]["solution"].update(radius_m=.9), "midpoint radius"),
    (lambda rotor: rotor["elements"][0]["solution"].update(chord_m=.75), "chord"),
    (lambda rotor: rotor["elements"][0]["solution"].update(converged=False), "convergence"),
    (out_of_domain_mach, "retained polar domain"),
    (lambda rotor: rotor["elements"][0].update(width_m=.01), "width"),
    (lambda rotor: rotor["elements"][0]["solution"].update(differential_thrust_n_m=42.), "annular thrust"),
    (lambda rotor: rotor["polar_query_envelope"].update(mach_min=.1), "aggregate query envelope"),
    (lambda rotor: rotor["elements"][0]["solution"]["polar_query_envelope"].update(mach_min=.3), "query bounds"),
    (lambda rotor: rotor["elements"][0]["solution"].update(mach=.25), "one query|final query"),
    (lambda rotor: rotor["elements"][0]["solution"]["polar_query_envelope"].update(query_count=10000), "query count"),
    (lambda rotor: rotor["elements"][0]["solution"]["polar_query_envelope"].update(mach_max=.3), "one query"),
])
def test_restore_rejects_resealed_radial_witnesses(case, mutation, diagnostic):
    _, row, calls = case
    first = row["aerodynamics"]["radial_elements"][0]["solution"]
    assert first["radius_m"] == .14705 and first["chord_m"] == .06961875000000001
    assert research.read_saved_result(encode(row)) == row
    with pytest.raises(ValueError, match=diagnostic):
        research.read_saved_result(reseal_rotor(row, mutation))
    assert len(calls) == 1


@pytest.mark.parametrize("contact", (False, True))
def test_restore_checks_every_rpm_and_termination_of_mechanism_only_record(case, monkeypatch, contact):
    active, _, calls = case
    options = research.MechanismInputs(10., 40., .000001, "INERT assumed CG", 1200., .5, .1,
                                       .01, -10., .001, .002, "none", 0., 0.)
    runs = mechanism(monkeypatch, contact=contact)
    row = research.run_mechanics_only(active, options)
    assert row["aerodynamics"] is None and len(runs) == 1
    monkeypatch.setattr(mech, "solve_mechanism_transient", lambda *a: pytest.fail("Restore reran mechanism"))
    original = encode(row)
    assert research.read_saved_result(original) == row

    def reseal(mutate):
        copy = json.loads(original)
        report = json.loads(copy["mechanism"]["report_text"])
        result = report["result"]
        mutate(result)
        copy["mechanism"]["report_text"] = mech._json(report) + "\n"
        copy["mechanism"]["report_sha256"] = mech._sha(copy["mechanism"]["report_text"])
        return encode(copy)

    def forge_ramp(result):
        i = len(result["samples"])//2
        assert 1200 < result["rpm"][i] < 2400
        result["rpm"][i] = result["samples"][i]["rpm"] = 9999.
        omega = 9999. * research.normalize_quantity("1 rpm", "angular_speed", field="rpm").si_value
        result["omega_rad_s"][i] = result["samples"][i]["omega_rad_s"] = omega

    with pytest.raises(ValueError, match="RPM.*drive"):
        research.read_saved_result(reseal(forge_ramp))
    # A valid stop contact can end the drive early; a completed report must reach its end.
    with pytest.raises(ValueError, match="termination"):
        research.read_saved_result(reseal(lambda result: result.update(
            status="completed" if contact else "stop_contact")))
    assert len(calls) == 1


def test_restore_rejects_resealed_prepared_request_with_different_condition(case):
    _, row, _ = case
    report = json.loads(row["aerodynamics"]["report_text"])
    q = report["request"]
    ui = q["ui_request"]
    ui["analysis_request"]["operating_condition"]["angular_speed_rad_s"] = 7100 * (2 * research.math.pi / 60)
    q["ui_request_sha256"] = research.design_analysis._sha(research.design_analysis._json(ui))
    q["provider_design_request_sha256"] = research._digest({
        "admission": q["provider_design_admission"], "polar_run_sha256": q["ui_request_sha256"]})
    report["request_sha256"] = research.design_analysis._sha(research.design_analysis._json(q))
    raw = _reseal_report(row, report)
    with pytest.raises(ValueError, match="prepared analysis request contradicts"):
        research.read_saved_result(raw)


@pytest.mark.parametrize("field", ("thrust", "torque"))
def test_restore_checks_resealed_differential_load_with_consistent_totals(case, field):
    active, row, _ = case
    condition = active.design.operating_conditions[0]
    blade = active.design.blade

    def forge(rotor):
        first = rotor["elements"][0]
        differential, element_load = (("differential_thrust_n_m", "thrust_n") if field == "thrust"
                                      else ("differential_torque_nm_m", "torque_nm"))
        first["solution"][differential] += 40.
        first[element_load] = first["solution"][differential] * first["width_m"]
        thrust, torque = (math.fsum(e[k] for e in rotor["elements"]) for k in ("thrust_n", "torque_nm"))
        power = torque * condition.angular_speed_rad_s
        n = condition.angular_speed_rad_s / (2 * math.pi)
        d, rho = blade.diameter_m, condition.air_density_kg_m3
        force_scale = rho * n**2 * d**4
        rotor.update(thrust_n=thrust, torque_nm=torque, shaft_power_w=power,
                     thrust_coefficient=thrust/force_scale, torque_coefficient=torque/(force_scale*d),
                     power_coefficient=power/(rho*n**3*d**5),
                     propulsive_efficiency=condition.forward_speed_m_s*thrust/power)

    raw = reseal_rotor(row, forge)
    with pytest.raises(ValueError, match=f"differential {field}"):
        research.read_saved_result(raw)


@pytest.mark.parametrize("field", ("omega_dot_rad_s2", "applied_torque_nm",
                                   "spring_torque_nm", "viscous_dissipated_energy_j"))
def test_restore_checks_resealed_mechanism_drive_dynamics_and_quadrature(case, monkeypatch, field):
    active, _, _ = case
    options = research.MechanismInputs(10., 40., .000001, "INERT assumed CG", 1200., .5, .1,
                                       .01, -10., .001, .002, "none", 0., 0.)
    mechanism(monkeypatch)
    row = research.run_mechanics_only(active, options)
    assert research.read_saved_result(encode(row)) == row
    doc = json.loads(row["mechanism"]["report_text"])
    data = doc["result"]
    params = doc["request"]["transient"]["parameters"]
    i = len(data["samples"])//2
    sample = data["samples"][i]

    def set_sample(index, key, value):
        data["samples"][index][key] = data[key][index] = value

    if field == "omega_dot_rad_s2":
        set_sample(i, field, 0.)
        set_sample(i, "euler_torque_nm", 0.)
    elif field == "applied_torque_nm":
        set_sample(i, field, sample[field]+.04)
        set_sample(i, "applied_power_w", sample[field]*sample["angular_velocity_rad_s"])
        work = 0.
        for j, time in enumerate(data["time_s"]):
            if j:
                work += .5*(data["applied_power_w"][j-1]+data["applied_power_w"][j])*(time-data["time_s"][j-1])
            set_sample(j, "applied_work_j", work)
    elif field == "spring_torque_nm":
        set_sample(i, field, sample[field]+.04)
    else:
        for j in range(i, len(data["samples"])):
            set_sample(j, field, data[field][j]+.01)
            set_sample(j, "total_dissipated_energy_j", data[field][j]+data["dry_friction_dissipated_energy_j"][j])
    if field != "viscous_dissipated_energy_j":
        terms = ("applied_torque_nm", "spring_torque_nm", "damping_torque_nm",
                 "dry_friction_torque_nm", "centrifugal_torque_nm", "euler_torque_nm")
        set_sample(i, "angular_acceleration_rad_s2", sum(sample[k] for k in terms)/params["hinge_inertia_kg_m2"])
    row["mechanism"]["report_text"] = mech._json(doc) + "\n"
    row["mechanism"]["report_sha256"] = mech._sha(row["mechanism"]["report_text"])
    raw = encode(row)
    monkeypatch.setattr(mech, "solve_mechanism_transient", lambda *a: pytest.fail("Restore reran mechanism"))
    with pytest.raises(ValueError, match=field):
        research.read_saved_result(raw)


@pytest.mark.parametrize("contact_at_knot", (False, True))
def test_mechanism_output_uses_right_side_at_knot_but_incoming_side_at_terminal_contact(
        monkeypatch, contact_at_knot):
    example = mech.build_literature_modal_example()
    origin, step = .125, 1/1024
    knot = origin + 2*step
    drive = DriveHistory((origin, knot, origin+4*step), (1200., 2400., 1800.), (.1, .2, .4))
    params = replace(example.transient.parameters, hinge_radius_m=.27, dry_friction=DryFriction(
        "regularized_coulomb", .01, .1, "inert fixture"))
    request = replace(example.transient, parameters=params, drive=drive, initial_angular_velocity_rad_s=.1)
    times = tuple(origin+i*step for i in range(3 if contact_at_knot else 5))
    angles = (request.initial_angle_rad,)*len(times)
    starts = (0,) if contact_at_knot else (0, 2)
    velocities = (.1,)*len(times)
    contact = None
    if contact_at_knot:
        angles = (*angles[:-1], request.parameters.upper_stop_rad)
        contact = StopContact("upper", knot, angles[-1], velocities[-1])
    history = inert_history(request, times, angles, velocities, starts, contact)
    monkeypatch.setattr(mech, "solve_mechanism_transient", lambda _: history)
    report = mech.run_mechanism_transient(replace(example, transient=request))
    result = json.loads(report.report_json)["result"]
    incoming = 1200. * RPM_TO_RAD_S / (2*step)
    outgoing = -600. * RPM_TO_RAD_S / (2*step)
    assert result["omega_dot_rad_s2"][2] == (incoming if contact_at_knot else outgoing)
    assert result["applied_torque_nm"][2] == .2
    assert result["dry_friction_dissipated_energy_j"][-1] > 0.
    check_mechanism_history(result, request)
    result["omega_dot_rad_s2"][2] = result["samples"][2]["omega_dot_rad_s2"] = (
        outgoing if contact_at_knot else incoming)
    with pytest.raises(ValueError, match="omega_dot_rad_s2"):
        check_mechanism_history(result, request)


@pytest.mark.parametrize("theta", (0., 1.e-5, -1.e-5))
def test_mechanism_energy_allows_only_cosine_roundoff_near_open(monkeypatch, theta):
    example = mech.build_literature_modal_example()
    params = replace(example.transient.parameters, hinge_radius_m=.27,
                     spring_stiffness_nm_rad=0., viscous_damping_nm_s_rad=0.)
    request = replace(example.transient, parameters=params, initial_angle_rad=theta,
                      drive=DriveHistory((0., .002), (2400., 2400.), (0., 0.)))
    history = inert_history(request, (0., .001, .002), (theta,)*3, (0.,)*3, (0,))
    monkeypatch.setattr(mech, "solve_mechanism_transient", lambda _: history)
    result = json.loads(mech.run_mechanism_transient(replace(example, transient=request)).report_json)["result"]
    check_mechanism_history(result, request)
    coefficient = params.mass_kg * params.hinge_radius_m * params.cg_distance_m * result["omega_rad_s"][1]**2
    cosine = math.cos(theta)
    # A neighboring libm result changes 1-cos(theta) by many energy ULPs.
    energy = coefficient * (1 - math.nextafter(cosine, -math.inf))
    result["effective_energy_j"][1] = result["samples"][1]["effective_energy_j"] = energy
    check_mechanism_history(result, request)
    result["effective_energy_j"][1] = result["samples"][1]["effective_energy_j"] = (
        energy + 16 * coefficient * math.ulp(cosine))
    with pytest.raises(ValueError, match="effective_energy_j"):
        check_mechanism_history(result, request)
