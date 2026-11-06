"""PR107 review witnesses. All positive records/BEM calls are explicitly inert."""
from dataclasses import replace
import csv
import hashlib
import io
import json
import base64
from pathlib import Path
import tarfile
from decimal import localcontext, ROUND_FLOOR

import pytest

from pyfoldable.application import design_analysis, provider_design_analysis as app
from pyfoldable.application.profile_bem_comparison import add_record, comparison_document, comparison_csv
from pyfoldable.providers import xfoil
from pyfoldable.application.retained_xfoil_header import assess_retained_xfoil_header
from test_provider_design_analysis import scenario, encoded, install_inert_bem


@pytest.fixture(autouse=True)
def inert_only(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Unexpected genuine provider/BEM/banner call")
    monkeypatch.setattr(design_analysis, "solve_bem_rotor", forbidden)
    monkeypatch.setattr(xfoil.XfoilProvider, "generate", forbidden)
    monkeypatch.setattr(xfoil, "_discover_backend_version", forbidden)


def header(request):
    """INERT rendering of POLWRIT formats9001/9015, not a solver observation."""
    command_mach = float(xfoil._format_real(request.mach))
    command_re = float(xfoil._format_real(request.reynolds))
    return (f"\n XFOIL Version 6.99\n Calculated polar for: _PyFoldable_{request.airfoil.id}\n"
            " 1 1 Reynolds number fixed          Mach number fixed\n"
            f" xtrf = {request.xtr_upper:.3f} (top) {request.xtr_lower:.3f} (bottom)\n"
            f" Mach = {command_mach:.3f}     Re = {command_re / 1e6:.3f} e 6     Ncrit = {request.n_crit:.3f} {request.n_crit:.3f}\n\n").encode()


def change_polar(cell, polar):
    files = dict(cell.capture_files)
    receipt = json.loads(files["capture.json"])
    files["polar.bin"] = polar
    receipt["polar_file"] = xfoil._byte_receipt(polar, partial=False)
    files["capture.json"] = encoded(receipt)
    return replace(cell, capture_files=tuple(files.items()))


def control():
    selection, repository = scenario()
    family = repository.families[0]
    cells = tuple(change_polar(c, header(r) + dict(c.capture_files)["polar.bin"]) for r, c in zip(family.requests, family.cells))
    return selection, replace(repository, families=(replace(family, cells=cells),))


def first_cell(repository, cell):
    family = repository.families[0]
    return replace(repository, families=(replace(family, cells=(cell,) + family.cells[1:]),))


def test_valid_xfoil_format_inert_control_prepares_and_executes(monkeypatch):
    selection, repository = control()
    prepared = app.prepare_provider_design_analysis(selection, repository)
    calls = install_inert_bem(monkeypatch)
    outcome = app.run_provider_design_analysis(prepared, active_selection=selection, repository=repository)
    assert len(calls) == 1 and outcome.record["status"] == "success"
    assert outcome.record["evidence_class"] == "inert_fixture"
    observed = json.loads(prepared.admission_json)["cells"][0]
    assert observed["capture_observations"]["retained_receipt"]["document"] == json.loads(dict(repository.families[0].cells[0].capture_files)["capture.json"])


@pytest.mark.parametrize("old,new", [
    (b"_PyFoldable_NACA0012", b"NACA2412"),
    (b"Mach = 0.040", b"Mach = 0.900"),
    (b"Re = 0.026 e 6", b"Re = 9.000e6"),
])
@pytest.mark.parametrize("entry", ["preparation", "explicit_execution"])
def test_contradictory_headers_reject_even_with_updated_polar_receipt(old, new, entry):
    selection, repository = control()
    prepared = app.prepare_provider_design_analysis(selection, repository)
    cell = repository.families[0].cells[0]
    polar = dict(cell.capture_files)["polar.bin"]
    assert old in polar
    bad = first_cell(repository, change_polar(cell, polar.replace(old, new, 1)))
    with pytest.raises(app.ProviderDesignPreparationError) as caught:
        if entry == "preparation":
            app.prepare_provider_design_analysis(selection, bad)
        else:
            app.run_provider_design_analysis(prepared, active_selection=selection, repository=bad)
    assert caught.value.code == "invalid_capture"
    observed = json.loads(caught.value.evidence_json)["cells"][0]
    assert observed["capture_observations"]["retained_receipt"]["document"]["returncode"] == 0


@pytest.mark.parametrize("field,value", [("returncode", 7), ("polar_row_count", 1), ("repanel", False)])
@pytest.mark.parametrize("entry", ["preparation", "explicit_execution"])
def test_known_metadata_contradictions_are_rejected(field, value, entry):
    selection, repository = control()
    prepared = app.prepare_provider_design_analysis(selection, repository)
    cell = repository.families[0].cells[0]
    doc = json.loads(cell.result_json)
    doc["metadata"][field] = value
    bad = first_cell(repository, replace(cell, result_json=encoded(doc)))
    with pytest.raises(app.ProviderDesignPreparationError) as caught:
        if entry == "preparation":
            app.prepare_provider_design_analysis(selection, bad)
        else:
            app.run_provider_design_analysis(prepared, active_selection=selection, repository=bad)
    assert caught.value.code == "invalid_capture"


def rejected_record(selection, repository):
    with pytest.raises(app.ProviderDesignPreparationError) as caught:
        app.prepare_provider_design_analysis(selection, repository)
    return app.preparation_failure_record(selection, caught.value)


@pytest.mark.parametrize("field,values", [("n_crit", (7., 8.)), ("root", (80., 81.))])
def test_distinct_rejected_selections_have_distinct_immutable_references(field, values):
    selection, repository = control()
    records = []
    for value in values:
        if field == "root":
            changed = replace(selection, root=replace(selection.root, value=value))
        else:
            policy = json.loads(selection.provider_policy_json)
            policy[field] = value
            changed = replace(selection, provider_policy_json=encoded(policy).decode())
        record = rejected_record(changed, repository)
        assert record == rejected_record(changed, repository)
        records.append(record)
    assert records[0]["record_sha256"] != records[1]["record_sha256"]
    assert records[0]["attempt_sha256"] != records[1]["attempt_sha256"]
    saved = add_record(add_record((), records[0]), records[1])
    document = json.loads(json.dumps(comparison_document(saved, evidence_class="inert_fixture")))
    rows = list(csv.DictReader(io.StringIO(comparison_csv(document))))
    for row, record in zip(rows, document["records"]):
        attempted = record["attempted_selection"]
        canonical = encoded(attempted)
        assert row["attempt_sha256"] == record["attempted_selection_sha256"] == hashlib.sha256(canonical).hexdigest()
        assert record["analysis_request_sha256"] is record["ui_request_sha256"] is record["report_sha256"] is None
        assert record["thrust_n"] is record["torque_nm"] is record["shaft_power_w"] is None
        assert record["prepared_policy"] is None
        if field == "root":
            assert attempted["root"]["value"] in values
            assert attempted["root"]["unit"] == "mm"
            assert attempted["root"]["meaning"] == selection.root.meaning
            assert attempted["root"]["source_identity"] == selection.root.source_identity
            assert attempted["root"]["declaration_kind"] == "study_assumption"
        else:
            assert attempted["provider_policy"]["parsed"]["n_crit"] in values


def assessment(raw, request):
    script = xfoil._build_command_script(request, xfoil._validated_options(request.options))
    return assess_retained_xfoil_header(raw.decode(), request, script=script, airfoil_input=f"_PyFoldable_{request.airfoil.id}\n")


def test_genuine_rounded_header_is_compatible_independently_of_partial_coverage():
    archive = Path("tests/fixtures/provider_design_analysis/partial_xfoil_20261106.tar.gz")
    before = hashlib.sha256(archive.read_bytes()).hexdigest()
    with tarfile.open(archive) as tar:
        retained = {m.name: tar.extractfile(m).read() for m in tar.getmembers() if m.isfile()}
    raw_result = json.loads(retained["run/result-00.json"])
    request = app._result(raw_result).request
    raw_polar = retained["run/capture/cell-00-NACA0012/polar.bin"]
    result = assessment(raw_polar, request)
    assert result["compatible"] is True
    assert result["fields"]["mach"]["declarations"][0]["token"] == "0.041"
    assert result["fields"]["reynolds"]["declarations"][0]["token"] == "0.026 e 6"
    assert result["fields"]["mach"]["requested_value"] == 0.040507164718475736
    assert result["fields"]["reynolds"]["requested_value"] == 26030.624179244653
    assert raw_result["complete"] is False
    assert len([p for p in raw_result["points"] if p["cl"] is None]) == 2
    assert before == hashlib.sha256(archive.read_bytes()).hexdigest()


def test_command_formatting_is_applied_before_header_precision_and_exact_ties():
    _, repository = control()
    request = replace(repository.families[0].requests[0], mach=.04049999999999999)
    assert xfoil._format_real(request.mach) == "0.0405"
    raw = header(request) + b"alpha CL CD CM\n"
    assert b"Mach = 0.041" in raw
    assert assessment(raw, request)["fields"]["mach"]["status"] == "compatible"
    request = replace(request, mach=.0625)  # exact binary64 half-quantum boundary
    raw = header(request) + b"alpha CL CD CM\n"
    for printed, status in [(b"0.062", "compatible"), (b"0.063", "compatible"), (b"0.064", "contradictory")]:
        changed = raw.replace(b"Mach = 0.062", b"Mach = " + printed)
        assert assessment(changed, request)["fields"]["mach"]["status"] == status


@pytest.mark.parametrize("old,new,field", [
    (b"Mach = 0.040", b"Mach = garbage", "mach"),
    (b"Re = 0.026 e 6", b"Re : 0.026 e 6", "reynolds"),
    (b"Mach = 0.040", b"Mach = 0.040 Mach = 0.040", "mach"),
    (b"_PyFoldable_NACA0012", b"", "profile"),
])
def test_malformed_and_duplicate_fields_are_not_classified_as_missing(old, new, field):
    selection, repository = control()
    family = repository.families[0]
    cell = family.cells[0]
    changed = change_polar(cell, dict(cell.capture_files)["polar.bin"].replace(old, new, 1))
    with pytest.raises(app.ProviderDesignPreparationError) as caught:
        app.prepare_provider_design_analysis(selection, first_cell(repository, changed))
    evidence = json.loads(caught.value.evidence_json)
    observed = evidence["cells"][0]["capture_observations"]["polar_header"]
    assert observed["fields"][field]["status"] == "malformed"


def test_headerless_and_absent_optional_metadata_remain_explicitly_unavailable():
    selection, repository = scenario()
    prepared = app.prepare_provider_design_analysis(selection, repository)
    cell = json.loads(prepared.admission_json)["cells"][0]
    observations = cell["capture_observations"]
    assert all(f["status"] == "missing" and f["interpreted_value"] is None for f in observations["polar_header"]["fields"].values())
    for name in ("returncode", "polar_row_count", "repanel"):
        assert name not in cell["returned_document"]["metadata"]
        assert observations["known_returned_metadata"][name] == {"status": "missing"}


@pytest.mark.parametrize("field,value", [("returncode", True), ("returncode", 0.), ("polar_row_count", True), ("polar_row_count", "37"), ("repanel", 1), ("repanel", "true")])
def test_present_metadata_fields_require_provider_observation_types(field, value):
    selection, repository = control()
    cell = repository.families[0].cells[0]
    result = json.loads(cell.result_json)
    result["metadata"][field] = value
    with pytest.raises(app.ProviderDesignPreparationError) as caught:
        app.prepare_provider_design_analysis(selection, first_cell(repository, replace(cell, result_json=encoded(result))))
    observed = json.loads(caught.value.evidence_json)["cells"][0]["capture_observations"]
    assert observed["known_returned_metadata"][field]["status"] == "malformed"


def test_consistent_metadata_counts_parsed_rows_including_unmatched_rows(monkeypatch):
    selection, repository = control()
    cell = repository.families[0].cells[0]
    raw = dict(cell.capture_files)["polar.bin"] + b"80 0.8 0.02 0 0 1 1\n"
    changed = change_polar(cell, raw)
    result = json.loads(cell.result_json)
    result["metadata"].update(returncode=0, polar_row_count=38, repanel=True)
    changed = replace(changed, result_json=encoded(result))
    repository = first_cell(repository, changed)
    prepared = app.prepare_provider_design_analysis(selection, repository)
    observed = json.loads(prepared.admission_json)["cells"][0]["capture_observations"]
    assert observed["parsed_polar_row_count"] == 38
    assert all(x["status"] == "consistent" for x in observed["known_returned_metadata"].values())
    calls = install_inert_bem(monkeypatch)
    assert app.run_provider_design_analysis(prepared, active_selection=selection, repository=repository).record["status"] == "success"
    assert len(calls) == 1


@pytest.mark.parametrize("policy", ['{"n_crit": 7,', '{"n_crit": 8,'])
def test_malformed_policy_original_text_bytes_and_digest_survive_saved_export(policy):
    selection, repository = control()
    changed = replace(selection, provider_policy_json=policy)
    record = rejected_record(changed, repository)
    retained = record["attempted_selection"]["provider_policy"]
    assert retained["parse_status"] == "malformed" and retained["parsed"] is None
    assert retained["original_text"] == policy
    assert base64.b64decode(retained["utf8_base64"]) == policy.encode()
    assert retained["utf8_sha256"] == hashlib.sha256(policy.encode()).hexdigest()
    assert record["analysis_request_sha256"] is record["report_sha256"] is None


def test_attempt_identity_retains_inputs_before_root_validation_and_cannot_relabel():
    selection, repository = control()
    changed = replace(selection, root=replace(selection.root, value=80.))
    with pytest.raises(app.ProviderDesignPreparationError) as caught:
        app.prepare_provider_design_analysis(changed, repository)
    retained = json.loads(caught.value.evidence_json)["attempted_selection"]
    assert retained["draft"]["declared_draft_sha256"] == selection.draft.draft_sha256
    assert retained["draft"]["observed_toml_sha256"] == hashlib.sha256(selection.draft.toml.encode()).hexdigest()
    assert retained["template"]["observed_source_sha256"] == hashlib.sha256(selection.template.source_bytes).hexdigest()
    assert retained["family_id"] == selection.family_id and retained["annulus_count"] == 4
    assert retained["root"]["value"] == 80.
    with pytest.raises(app.ProviderDesignPreparationError, match="relabel"):
        app.preparation_failure_record(replace(changed, root=replace(changed.root, value=81.)), caught.value)


def test_header_assessment_is_independent_of_ambient_decimal_context():
    _, repository = control()
    request = replace(repository.families[0].requests[0], mach=.0625)
    raw = header(request) + b"alpha CL CD CM\n"
    expected = assessment(raw, request)
    with localcontext() as context:
        context.prec = 2
        context.rounding = ROUND_FLOOR
        assert assessment(raw, request) == expected
        assert context.prec == 2 and context.rounding == ROUND_FLOOR


@pytest.mark.parametrize("change", ["signed_zero_root", "annulus_type"])
def test_rejection_cannot_be_rebound_by_python_numeric_equality(change):
    selection, repository = control()
    wrong_policy = json.loads(selection.provider_policy_json)
    wrong_policy["n_crit"] = 7.
    selection = replace(selection, root=replace(selection.root, value=0.), provider_policy_json=encoded(wrong_policy).decode())
    with pytest.raises(app.ProviderDesignPreparationError) as caught:
        app.prepare_provider_design_analysis(selection, repository)
    different = replace(selection, root=replace(selection.root, value=-0.)) if change == "signed_zero_root" else replace(selection, annulus_count=4.)
    with pytest.raises(app.ProviderDesignPreparationError, match="relabel"):
        app.preparation_failure_record(different, caught.value)
