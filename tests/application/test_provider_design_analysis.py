"""Admission software tests: inert records/inert BEM only; no acquisition."""
from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace
import tarfile

import pytest

from pyfoldable.application import provider_design_analysis as app
from pyfoldable.application import design_analysis
from pyfoldable.application.design_draft import DesignDraftInputs, build_design_draft
from pyfoldable.application.profile_bem_comparison import add_record, comparison_document, comparison_csv
from pyfoldable.core import BEMRotorSettings
from pyfoldable.core.airfoil import airfoil_coordinate_sha256
from pyfoldable.core.profile_catalog import PROJECT_AIRFOIL_IDS, load_project_airfoil
from pyfoldable.core.providers import PolarGenerationRequest, ProviderIdentity, _canonical_value
from pyfoldable.providers import xfoil

SOURCE = Path("configs/designs/TIP_HINGED_250_CANONICAL.toml")


def encoded(value):
    return json.dumps(_canonical_value(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def draft(profile="NACA0012", **changes):
    inputs = DesignDraftInputs(
        diameter="250 mm", hub_radius="18 mm", hinge_radius="100 mm", blade_count=2,
        airfoil_id=profile, chord_scale=1., twist_scale=1., preview_fold_angle="0 deg",
        angular_speed="7100 rpm", forward_speed="0 m/s", air_density="1.225 kg/m^3",
        dynamic_viscosity="1.81e-5 Pa*s", temperature="288.15 K", pressure="101325 Pa",
    )
    return build_design_draft(SOURCE, replace(inputs, **changes), airfoil_definition=load_project_airfoil(profile))


def request_set(profile="NACA0012"):
    return tuple(PolarGenerationRequest(
        load_project_airfoil(profile), tuple(math.radians(a) for a in range(32, -41, -2)),
        re, ma, max_iterations=100, timeout_s=90., scenario_id="INERT-admission-software-test",
        options={"repanel": True},
    ) for ma in (.04, .27) for re in (26000., 89000.))


def inert_cell(request, provider):
    """First-party inert XFOIL-format records; no executable or solve exists."""
    polar = ("alpha CL CD CDp CM Top_Xtr Bot_Xtr\n" + "\n".join(
        f"{math.degrees(a):.8f} 0.8 0.02 0 0 1 1" for a in request.alpha_rad
    ) + "\n").encode()
    parsed, _ = xfoil._parse_polar(polar.decode())
    points, warnings = xfoil._reconcile_rows(request, parsed)
    script = xfoil._build_command_script(request, {"repanel": True}).encode()
    safe_id = request.airfoil.id
    airfoil = (f"_PyFoldable_{safe_id}\n" + "\n".join(f"{x:.17g} {y:.17g}" for x, y in request.airfoil.coordinates) + "\n").encode()
    preimage = xfoil._request_preimage(request, provider)
    observation = {"path": "INERT-NO-EXECUTABLE", "sha256": hashlib.sha256(b"INERT").hexdigest(), "unavailable_reason": None}
    receipt = {
        "schema_version": 1, "artifact_class": "xfoil_subprocess_capture",
        "provider_identity": provider.as_mapping(), "request_cache_key": request.cache_key(provider),
        "request_preimage_sha256": request.cache_key(provider),
        "coordinate_sha256": airfoil_coordinate_sha256(request.airfoil),
        "script_sha256": hashlib.sha256(script).hexdigest(), "airfoil_input_sha256": hashlib.sha256(airfoil).hexdigest(),
        "adapter_source_sha256": hashlib.sha256(Path(xfoil.__file__).read_bytes()).hexdigest(),
        "process_status": "completed", "returncode": 0,
        "stdout": xfoil._byte_receipt(b"INERT; NOT A PROCESS STREAM\n", partial=False),
        "stderr": xfoil._byte_receipt(b"", partial=False),
        "polar_file": xfoil._byte_receipt(polar, partial=False), "polar_read_status": "present",
        "polar_decoding_status": "decoded", "polar_parsed": True,
        "capture_receipt_written": True, "solver_output_usable": True, "evidence_ready": True,
        "points": [{k: v for k, v in asdict(p).items() if k not in ("confidence", "iterations")} for p in points],
        "executable_identity": {"prelaunch": observation, "postlaunch": observation, "matched": True},
    }
    result = {
        "request": _canonical_value(request.cache_payload(provider)), "provider": provider.as_mapping(),
        "request_sha256": request.cache_key(provider), "complete": True, "elapsed_s": 0.,
        "points": [asdict(p) for p in points], "warnings": list(warnings),
        "metadata": {"capture_evidence_ready": True, "capture_request_sha256": request.cache_key(provider)},
    }
    return app.RetainedCell(encoded(result), tuple({
        "capture.json": encoded(receipt), "request_preimage.json": preimage, "script.txt": script,
        "airfoil_input.dat": airfoil, "stdout.bin": b"INERT; NOT A PROCESS STREAM\n", "stderr.bin": b"", "polar.bin": polar,
    }.items()))


def scenario(profile="NACA0012"):
    requests = request_set(profile)
    provider = ProviderIdentity("INERT-fixture", "1", "INERT-no-backend", "0")
    policy = app.request_policy(requests[0], provider)
    selection = app.ProviderDesignSelection(
        draft(profile), app.TemplateDeclaration("canonical-station-seed-v1", SOURCE.read_bytes(), "repository schema example; unqualified"),
        app.RootDatum(20., "mm", "exposed blade root in shaft radial frame", "test-study-root-v1", "study_assumption"),
        "inert-family-" + profile, encoded(policy).decode(), 4,
    )
    family = app.ManagedProviderFamily(
        selection.family_id, provider, requests, tuple(inert_cell(r, provider) for r in requests),
        "inert_fixture", "first-party inert admission fixture; not provider execution",
        (("build-record.txt", b"INERT; no build or executable"),),
    )
    return selection, app.ManagedProviderRepository((family,))


@pytest.fixture(autouse=True)
def no_hidden_solver_or_provider(monkeypatch):
    def forbidden(*a, **k):
        pytest.fail("Unexpected real solver/provider call")
    monkeypatch.setattr(design_analysis, "solve_bem_rotor", forbidden)
    monkeypatch.setattr(xfoil.XfoilProvider, "generate", forbidden)
    monkeypatch.setattr(xfoil, "_discover_backend_version", forbidden)


def install_inert_bem(monkeypatch):
    calls = []
    def seam(blade, condition, families, *, settings, bounds):
        calls.append((blade, condition, families, settings, bounds))
        assert bounds == "error"
        rotor = {
            "airfoil_id": next(iter(families)), "thrust_n": 1.25, "torque_nm": .01,
            "shaft_power_w": .01 * condition.angular_speed_rad_s, "annulus_count": settings.annulus_count,
            "inner_radius_m": blade.stations[0].r_over_R * blade.radius_m,
            "outer_radius_m": blade.stations[-1].r_over_R * blade.radius_m,
            "polar_bounds": bounds, "settings": settings.as_mapping(),
            "polar_query_envelope": {"query_count": 0, "note": "INERT BEM seam; no numerical query"},
            "elements": [{"solution": {"settings": settings.annulus_settings.as_mapping(), "polar_query_envelope": {"query_count": 0}}}],
        }
        return SimpleNamespace(as_mapping=lambda: rotor)
    monkeypatch.setattr(design_analysis, "solve_bem_rotor", seam)
    return calls


@pytest.mark.parametrize("profile", PROJECT_AIRFOIL_IDS)
def test_five_profiles_prepare_and_explicitly_run_without_uploads(profile, monkeypatch):
    selection, repo = scenario(profile)
    prepared = app.prepare_provider_design_analysis(selection, repo)
    assert prepared.polar_run.payload
    assert json.loads(prepared.admission_json)["geometry"]["root"]["unit"] == "mm"
    calls = install_inert_bem(monkeypatch)
    outcome = app.run_provider_design_analysis(prepared, active_selection=selection, repository=repo)
    assert len(calls) == 1
    assert outcome.record["evidence_class"] == "inert_fixture"
    assert outcome.record["status"] == "success"
    report = json.loads(outcome.artifact.report_json)
    assert report["request"]["provider_design_admission"] == json.loads(prepared.admission_json)
    assert report["physical_qualification"] is False
    assert report["request"]["polar_evidence_status"] == "caller_supplied_unqualified"


@pytest.mark.parametrize("change,code", [
    ({"root": None}, "missing_root_declaration"),
    ({"root": app.RootDatum(80., "mm", "root", "assumption-v2", "study_assumption")}, "longer_proximal_required"),
    ({"provider_policy_json": "{}"}, "incompatible_policy"),
])
def test_missing_root_lengths_and_policy_fail_before_bem(change, code):
    selection, repo = scenario()
    with pytest.raises(app.ProviderDesignPreparationError) as caught:
        app.prepare_provider_design_analysis(replace(selection, **change), repo)
    assert caught.value.code == code


def test_foreign_request_coordinates_and_missing_cells_are_rejected():
    selection, repo = scenario()
    family = repo.families[0]
    foreign = inert_cell(request_set("NACA2412")[0], family.provider)
    for changed, code in [
        (replace(family, cells=(foreign,) + family.cells[1:]), "request_binding"),
        (replace(family, cells=family.cells[:-1] + (None,)), "incomplete_family"),
    ]:
        with pytest.raises(app.ProviderDesignPreparationError) as caught:
            app.prepare_provider_design_analysis(selection, app.ManagedProviderRepository((changed,)))
        assert caught.value.code == code
        assert "cells" in json.loads(caught.value.evidence_json)


def test_hashes_and_success_claim_do_not_replace_raw_receipts():
    selection, repo = scenario()
    family = repo.families[0]
    cell = family.cells[0]
    for name, payload in [("stdout.bin", b"changed"), ("polar.bin", b"alpha CL CD CM\n32 9 9 9\n")]:
        changed = replace(cell, capture_files=tuple((n, payload if n == name else b) for n, b in cell.capture_files))
        with pytest.raises(app.ProviderDesignPreparationError, match="capture"):
            app.prepare_provider_design_analysis(selection, app.ManagedProviderRepository((replace(family, cells=(changed,) + family.cells[1:]),)))


def test_stale_active_state_clears_download_but_keeps_saved_snapshot(monkeypatch):
    selection, repo = scenario()
    state = {}
    app.prepare_active_provider_design(state, selection, repo)
    calls = install_inert_bem(monkeypatch)
    app.run_active_provider_design(state, selection, repo)
    saved = add_record((), state[app.ACTIVE_OUTCOME].record)
    before = encoded(saved)
    changed = replace(selection, root=replace(selection.root, source_identity="another-declaration"))
    with pytest.raises(app.ProviderDesignPreparationError, match="stale"):
        app.run_active_provider_design(state, changed, repo)
    assert len(calls) == 1
    assert app.ACTIVE_OUTCOME not in state
    assert encoded(saved) == before


def test_inert_bem_failure_and_distinct_profile_exports_preserve_attribution(monkeypatch):
    first, repo = scenario()
    prepared = app.prepare_provider_design_analysis(first, repo)
    def fail(*a, **k):
        raise design_analysis.DesignAnalysisError("INERT coverage failure")
    monkeypatch.setattr(design_analysis, "solve_bem_rotor", fail)
    failed = app.run_provider_design_analysis(prepared, active_selection=first, repository=repo)
    assert failed.artifact is None
    assert failed.record["thrust_n"] is None
    assert failed.record["failure_stage"] == "solver_invocation"
    assert failed.record["provider_design_admission"]["family_id"] == first.family_id
    install_inert_bem(monkeypatch)
    a = app.run_provider_design_analysis(prepared, active_selection=first, repository=repo).record
    second, repo2 = scenario("NACA2412")
    b = app.run_provider_design_analysis(app.prepare_provider_design_analysis(second, repo2), active_selection=second, repository=repo2).record
    same = comparison_document((a, a), evidence_class="inert_fixture")
    assert same["software_controlled_comparison"] is False
    doc = comparison_document((a, b), evidence_class="inert_fixture")
    assert doc["software_controlled_comparison"] is True
    assert doc["performance_comparison"] is False
    for row in doc["records"]:
        assert hashlib.sha256(row["report_text"].encode()).hexdigest() == row["report_sha256"]
        assert row["record_sha256"] in comparison_csv(doc)


def test_no_matching_data_does_not_substitute_another_profile():
    selection, repo = scenario()
    with pytest.raises(app.ProviderDesignPreparationError) as caught:
        app.prepare_provider_design_analysis(replace(selection, draft=draft("NACA4415")), repo)
    assert caught.value.code == "missing_applicable_family"


def test_actual_partial_20261106_result_never_admits_a_family_or_reaches_bem():
    """Read the retained run only. Missing angles and unlaunched cells stay absent."""
    archive = Path("tests/fixtures/provider_design_analysis/partial_xfoil_20261106.tar.gz")
    with tarfile.open(archive, "r:gz") as tar:
        retained = {m.name: tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}
    result_raw = retained["run/result-00.json"]
    result_doc = json.loads(result_raw)
    summary = json.loads(retained["execution-summary.json"])
    experiment = json.loads(Path("reports/polar_query_feasibility/report.json").read_text())["recommended_experiment"]
    from pyfoldable.application.polar_query_feasibility import declared_probe_requests, _declared_provider
    requests = declared_probe_requests(experiment, {p: load_project_airfoil(p) for p in ("NACA0012", "NACA2412")})
    provider = _declared_provider(experiment)
    selection, _ = scenario()
    selection = replace(selection, family_id="actual-20261106-negative-only", provider_policy_json=encoded(app.request_policy(requests[0], provider)).decode())
    cell = app.RetainedCell(result_raw, tuple((n.rsplit("/", 1)[1], b) for n, b in retained.items() if "/capture/" in n))
    not_launched = app.UnlaunchedCell("Reviewed driver stopped after partial cell00", "retained execution-summary.json cells01-03; original execution archive")
    family = app.ManagedProviderFamily(selection.family_id, provider, requests[:4], (cell, not_launched, not_launched, not_launched),
        "caller_supplied_unqualified", "2026-11-06 execution archive sha256:e779bb00158571541a10419ecccb011fc1c8a5ea32cad40a59e005c59f9082e9; negative only",
        (("execution-summary.json", retained["execution-summary.json"]),))
    with pytest.raises(app.ProviderDesignPreparationError) as caught:
        app.prepare_provider_design_analysis(selection, app.ManagedProviderRepository((family,)))
    assert caught.value.code == "incomplete_family"
    rejected = json.loads(caught.value.evidence_json)
    assert rejected["complete_family_admitted"] is False
    assert rejected["cells"][0]["status"] == "partial"
    assert rejected["cells"][0]["returned_document"] == result_doc
    assert [c["status"] for c in rejected["cells"]][1:] == ["not_launched"] * 3
    assert all(c["attempted_request_sha256"] is None and c["returned_request_sha256"] is None for c in rejected["cells"][1:])
    missing = [p for p in rejected["cells"][0]["points"] if p["cl"] is None]
    assert [round(math.degrees(p["alpha_rad"])) for p in missing] == [32, -38]
    assert all(p["cl"] is p["cd"] is p["cm"] is None for p in missing)
    assert sum(p["status"] == "converged" for p in result_doc["points"]) == 35
    assert [c["execution_status"] for c in summary["cells"]][1:] == ["NOT_LAUNCHED"] * 7
    assert [c["attempts"] for c in summary["cells"]] == [1, 0, 0, 0, 0, 0, 0, 0]
    failure = app.preparation_failure_record(selection, caught.value)
    exported = comparison_document((failure,), evidence_class="caller_supplied_unqualified")
    assert exported["records"][0]["provider_design_rejection"] == rejected
    assert exported["records"][0]["thrust_n"] is None
    assert archive.read_bytes()  # no mutation or launch of original artifacts


@pytest.mark.parametrize("field,value", [("reynolds", 26001.), ("mach", .041), ("n_crit", 8.), ("alpha_rad", tuple(math.radians(a) for a in range(-40, 33, 2)))])
def test_exact_request_changes_are_not_self_authorizing(field, value):
    selection, repo = scenario()
    family = repo.families[0]
    changed_request = replace(family.requests[0], **{field: value})
    changed_cell = inert_cell(changed_request, family.provider)
    with pytest.raises(app.ProviderDesignPreparationError) as caught:
        app.prepare_provider_design_analysis(selection, replace(repo, families=(replace(family, cells=(changed_cell,) + family.cells[1:]),)))
    assert caught.value.code == "request_binding"


def test_resealed_capture_coefficients_still_must_match_returned_ledger():
    selection, repo = scenario()
    family = repo.families[0]
    cell = family.cells[0]
    raw = dict(cell.capture_files)
    raw["polar.bin"] = raw["polar.bin"].replace(b"0.8 0.02", b"0.9 0.02")
    receipt = json.loads(raw["capture.json"])
    receipt["polar_file"] = xfoil._byte_receipt(raw["polar.bin"], partial=False)
    raw["capture.json"] = encoded(receipt)
    changed = replace(cell, capture_files=tuple(raw.items()))
    with pytest.raises(app.ProviderDesignPreparationError, match="coefficients"):
        app.prepare_provider_design_analysis(selection, replace(repo, families=(replace(family, cells=(changed,) + family.cells[1:]),)))


def test_source_and_root_declarations_are_retained_without_hub_or_station_inference():
    selection, repo = scenario()
    prepared = app.prepare_provider_design_analysis(selection, repo)
    geometry = json.loads(prepared.admission_json)["geometry"]
    assert geometry["hub_radius_m"] == pytest.approx(.018)
    assert geometry["first_aerodynamic_station_m"] == .025
    assert geometry["root"]["value"] == 20.
    assert geometry["root"]["si_value_m"] == .020
    assert geometry["root"]["declaration_kind"] == "study_assumption"
    changed = replace(selection, root=replace(selection.root, value=21.))
    assert app.prepare_provider_design_analysis(changed, repo).request_sha256 != prepared.request_sha256
    with pytest.raises(app.ProviderDesignPreparationError, match="Template"):
        app.prepare_provider_design_analysis(replace(selection, template=replace(selection.template, source_bytes=b"foreign")), repo)


def test_retained_evidence_change_after_preparation_cannot_reach_bem():
    selection, repo = scenario()
    prepared = app.prepare_provider_design_analysis(selection, repo)
    family = repo.families[0]
    changed_repo = replace(repo, families=(replace(family, source_identity="another retained source"),))
    with pytest.raises(app.ProviderDesignPreparationError, match="stale"):
        app.run_provider_design_analysis(prepared, active_selection=selection, repository=changed_repo)


def test_wrong_provider_and_capture_request_do_not_authorize_admission():
    selection, repo = scenario()
    family = repo.families[0]
    other = ProviderIdentity("INERT-other", "1", "INERT-no-backend", "0")
    cell = inert_cell(family.requests[0], other)
    with pytest.raises(app.ProviderDesignPreparationError) as caught:
        app.prepare_provider_design_analysis(selection, replace(repo, families=(replace(family, cells=(cell,) + family.cells[1:]),)))
    assert caught.value.code == "request_binding"
    cell = family.cells[0]
    doc = json.loads(cell.result_json)
    doc["metadata"]["capture_request_sha256"] = "f" * 64
    changed = replace(cell, result_json=encoded(doc))
    with pytest.raises(app.ProviderDesignPreparationError) as caught:
        app.prepare_provider_design_analysis(selection, replace(repo, families=(replace(family, cells=(changed,) + family.cells[1:]),)))
    assert caught.value.code == "request_binding"


@pytest.mark.parametrize("malformed", ["metadata", "points", "executable_prelaunch"])
def test_malformed_retained_shapes_become_attributed_rejections_and_clear_active_state(malformed):
    selection, repo = scenario()
    state = {}
    app.prepare_active_provider_design(state, selection, repo)
    state[app.ACTIVE_OUTCOME] = "previous download must be removed"
    family = repo.families[0]
    cell = family.cells[0]
    if malformed in {"metadata", "points"}:
        result = json.loads(cell.result_json)
        result[malformed] = None
        cell = replace(cell, result_json=encoded(result))
    else:
        files = dict(cell.capture_files)
        receipt = json.loads(files["capture.json"])
        receipt["executable_identity"]["prelaunch"] = None
        files["capture.json"] = encoded(receipt)
        cell = replace(cell, capture_files=tuple(files.items()))
    changed_repo = replace(repo, families=(replace(family, cells=(cell,) + family.cells[1:]),))
    with pytest.raises(app.ProviderDesignPreparationError) as caught:
        app.prepare_active_provider_design(state, selection, changed_repo)
    assert app.ACTIVE_OUTCOME not in state
    assert app.ACTIVE_REQUEST not in state
    rejected = json.loads(caught.value.evidence_json)
    assert rejected["cells"][0]["result_json_sha256"] == hashlib.sha256(cell.result_json).hexdigest()
    record = app.preparation_failure_record(selection, caught.value)
    assert record["evidence_class"] == "inert_fixture"
    assert record["thrust_n"] is None
    assert record["provider_design_rejection"] == rejected


def test_missing_returned_record_is_not_inferred_to_be_unlaunched():
    selection, repo = scenario()
    family = repo.families[0]
    changed_repo = replace(repo, families=(replace(family, cells=(None,) + family.cells[1:]),))
    with pytest.raises(app.ProviderDesignPreparationError) as caught:
        app.prepare_provider_design_analysis(selection, changed_repo)
    assert json.loads(caught.value.evidence_json)["cells"][0]["status"] == "unavailable"


def test_foreign_coordinates_with_a_claimed_catalog_hash_are_rejected():
    selection, repo = scenario()
    family = repo.families[0]
    foil = family.requests[0].airfoil
    coordinates = ((foil.coordinates[0][0], foil.coordinates[0][1] + .001),) + foil.coordinates[1:]
    foreign = replace(foil, coordinates=coordinates)  # stale metadata still claims catalog identity
    assert foreign.metadata == foil.metadata
    requests = tuple(replace(r, airfoil=foreign) for r in family.requests)
    with pytest.raises(app.ProviderDesignPreparationError) as caught:
        app.prepare_provider_design_analysis(selection, replace(repo, families=(replace(family, requests=requests),)))
    assert caught.value.code == "foreign_coordinates"
