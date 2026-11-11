"""Resealed contradictions from the WSL restore finding; no numerical solver."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from pyfoldable.application import mechanism_transient as mech
from pyfoldable.application import provider_design_analysis as managed
from pyfoldable.application import research_design as research
from research_inert_support import bem, mechanism, store

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
