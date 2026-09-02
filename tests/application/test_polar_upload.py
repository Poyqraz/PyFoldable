"""PY-03 strict upload boundary; synthetic coefficients are test-only."""

import hashlib
import json
from dataclasses import asdict, replace

import pytest

from pyfoldable.application.polar_upload import (
    MAX_POLAR_UPLOAD_BYTES, PolarUploadError, inspect_polar_bundle,
    prepare_polar_run, run_polar_run,
)
from pyfoldable.application.design_analysis import DesignAnalysisError
from pyfoldable.application.design_draft import DesignDraftInputs, build_design_draft
from pyfoldable.core import PolarTable
from pyfoldable.core.profile_catalog import load_project_airfoil


def draft(**changes):
    inputs = DesignDraftInputs(
        diameter="250 mm", hub_radius="18 mm", hinge_radius="100 mm", blade_count=2,
        airfoil_id="NACA2412", chord_scale=1.0, twist_scale=1.0,
        preview_fold_angle="0 deg", angular_speed="7100 rpm", forward_speed="0 m/s",
        air_density="1.225 kg/m^3", dynamic_viscosity="1.81e-5 Pa*s",
        temperature="288.15 K", pressure="101325 Pa",
    )
    return build_design_draft("configs/designs/TIP_HINGED_250_CANONICAL.toml",
        replace(inputs, **changes), airfoil_definition=load_project_airfoil(changes.get("airfoil_id", "NACA2412")))


def document():
    foil = load_project_airfoil("NACA2412")
    return {"schema_version": 1, "artifact_class": "active_design_polar_bundle",
        "physical_qualification": False, "tables": [asdict(PolarTable(
            airfoil_id=foil.id, reynolds=re, mach=ma, alpha_rad=(-1.57, 1.57),
            cl=(0.8, 0.8), cd=(0.02, 0.02), cm=(0., 0.), scenario_id="synthetic-test",
            source="synthetic test only", metadata={
                "airfoil_coordinate_sha256": foil.metadata["airfoil_coordinate_sha256"],
                "provider": {"name": "test", "version": "1"}, "confidence": [0.9, 0.9],
            },
        )) for re in (100., 1e7) for ma in (0., 1.)]}


def payload(doc=None):
    return json.dumps(document() if doc is None else doc).encode()


def test_upload_preserves_raw_identity_nested_provenance_and_core_family():
    raw = payload()
    bundle = inspect_polar_bundle(raw)
    assert bundle.source_sha256 == hashlib.sha256(raw).hexdigest()
    assert bundle.table_count == 4
    assert bundle.point_count == 8
    assert bundle.airfoil_id == "NACA2412"
    family = bundle.to_family()
    assert family.tables[0].metadata["provider"]["name"] == "test"
    family.tables[0].metadata.clear()
    assert bundle.to_family().tables[0].metadata  # No retained mutable model.


@pytest.mark.parametrize("raw", [b"", b"[]", b"null", b"\xff", b'{"schema_version":1,"schema_version":1}', b'{"x":NaN}', b'{"x":1e999}', b'[' * 1100 + b']' * 1100])
def test_invalid_json_is_controlled(raw):
    with pytest.raises(PolarUploadError):
        inspect_polar_bundle(raw)


def test_oversized_upload_is_rejected():
    with pytest.raises(PolarUploadError, match="size|bytes"):
        inspect_polar_bundle(b" " * (MAX_POLAR_UPLOAD_BYTES + 1))


@pytest.mark.parametrize("location", ["source", "metadata_value", "metadata_key"])
def test_decoded_unpaired_unicode_surrogates_are_rejected(location):
    doc = document()
    if location == "source": doc["tables"][0]["source"] = "bad\ud800source"
    elif location == "metadata_value": doc["tables"][0]["metadata"]["note"] = "\udfff"
    else: doc["tables"][0]["metadata"]["bad\ud800key"] = "text"
    with pytest.raises(PolarUploadError):
        inspect_polar_bundle(payload(doc))


def test_consistently_wrong_coordinate_hash_is_rejected_at_draft_boundary():
    doc = document()
    for table in doc["tables"]: table["metadata"]["airfoil_coordinate_sha256"] = "0" * 64
    inspect_polar_bundle(payload(doc))  # Internally consistent, but not this draft.
    with pytest.raises(PolarUploadError, match="coordinate"):
        prepare_polar_run(draft(), payload(doc))


def test_duplicate_key_error_does_not_echo_untrusted_markdown():
    raw = b'{"![image](https://example.invalid)":1,"![image](https://example.invalid)":2}'
    with pytest.raises(PolarUploadError) as caught:
        inspect_polar_bundle(raw)
    assert "![image]" not in str(caught.value)


@pytest.mark.parametrize("budget", ["total_points", "nodes", "string", "key"])
def test_additional_resource_limits(budget):
    doc = document()
    if budget == "total_points":
        doc["tables"] = [dict(doc["tables"][0], reynolds=100. + i,
            alpha_rad=[j / 1000. for j in range(721)],
            cl=[0.] * 721, cd=[.01] * 721, cm=[0.] * 721) for i in range(23)]
    elif budget == "nodes": doc["tables"][0]["metadata"]["nodes"] = [0] * 100001
    elif budget == "string": doc["tables"][0]["source"] = "a" * 4097
    else: doc["tables"][0]["metadata"]["x" * 257] = 0
    with pytest.raises(PolarUploadError):
        inspect_polar_bundle(payload(doc))


@pytest.mark.parametrize("key,value", [("complete", 1), ("requested_point_count", 3), ("usable_point_count", True)])
def test_provider_completeness_declarations_must_be_consistent(key, value):
    doc = document(); doc["tables"][0]["metadata"][key] = value
    with pytest.raises(PolarUploadError):
        inspect_polar_bundle(payload(doc))


@pytest.mark.parametrize("key,value", [
    ("schema_version", True), ("schema_version", 1.0), ("schema_version", 2),
    ("physical_qualification", True), ("physical_qualification", 0),
    ("artifact_class", "qualified"), ("tables", []), ("unexpected", "ignored?"),
])
def test_strict_root_contract(key, value):
    doc = document(); doc[key] = value
    with pytest.raises(PolarUploadError):
        inspect_polar_bundle(payload(doc))


@pytest.mark.parametrize("key,value", [
    ("reynolds", True), ("reynolds", "100"), ("mach", -1), ("source", " "),
    ("airfoil_id", None), ("scenario_id", 42), ("metadata", []),
    ("alpha_rad", [1, 0]), ("alpha_rad", [0, 0]), ("alpha_rad", [False, 1]),
    ("cd", [-1, 0]), ("cl", ["0", "1"]), ("cm", [0]), ("alpha_deg", [0, 1]),
])
def test_strict_table_contract(key, value):
    doc = document(); doc["tables"][0][key] = value
    with pytest.raises(PolarUploadError):
        inspect_polar_bundle(payload(doc))


@pytest.mark.parametrize("metadata", [{}, {"airfoil_coordinate_sha256": "bad"},
    {"airfoil_coordinate_sha256": "A" * 64}, {"complete": False},
    {"nested": {"physical_qualification": True}}])
def test_identity_and_qualification_claims_fail_closed(metadata):
    doc = document()
    if "complete" in metadata or "nested" in metadata:
        doc["tables"][0]["metadata"].update(metadata)
    else:
        doc["tables"][0]["metadata"] = metadata
    with pytest.raises(PolarUploadError):
        inspect_polar_bundle(payload(doc))


@pytest.mark.parametrize("change", ["duplicate", "profile", "scenario", "hash", "ragged", "points", "tables", "depth"])
def test_family_consistency_and_resource_budgets(change):
    doc = document(); table = doc["tables"][0]
    if change == "duplicate": doc["tables"].append(table)
    elif change == "profile": table["airfoil_id"] = "NACA0012"
    elif change == "scenario": table["scenario_id"] = "different"
    elif change == "hash": table["metadata"]["airfoil_coordinate_sha256"] = "0" * 64
    elif change == "ragged": doc["tables"].pop()
    elif change == "points": table["alpha_rad"] = list(range(722))
    elif change == "tables": doc["tables"] *= 17
    else:
        node = table["metadata"]
        for _ in range(25): node["nested"] = {}; node = node["nested"]
    with pytest.raises(PolarUploadError):
        inspect_polar_bundle(payload(doc))


def test_preparation_does_not_solve_and_identity_tracks_every_input(monkeypatch):
    import pyfoldable.application.design_analysis as analysis
    monkeypatch.setattr(analysis, "solve_bem_rotor", lambda *a, **k: pytest.fail("automatic solve"))
    original = prepare_polar_run(draft(), payload(), annulus_count=4)
    assert original.request_sha256 != prepare_polar_run(draft(diameter="260 mm"), payload(), annulus_count=4).request_sha256
    assert original.request_sha256 != prepare_polar_run(draft(), payload() + b"\n", annulus_count=4).request_sha256
    assert original.request_sha256 != prepare_polar_run(draft(), payload(), annulus_count=8).request_sha256
    assert original == prepare_polar_run(draft(), payload(), annulus_count=4)


@pytest.mark.parametrize("changes", [{"preview_fold_angle": "-30 deg"}, {"angular_speed": "0 rpm"}, {"airfoil_id": "NACA0012"}])
def test_unsupported_draft_is_rejected_before_run(changes):
    with pytest.raises((PolarUploadError, DesignAnalysisError)):
        prepare_polar_run(draft(**changes), payload())


@pytest.mark.parametrize("annuli", [True, 4.0, 0, 3, 81, 100000])
def test_ui_budget_is_enforced_in_service(annuli):
    with pytest.raises(PolarUploadError):
        prepare_polar_run(draft(), payload(), annulus_count=annuli)


def test_explicit_real_kernel_run_preserves_upload_and_screening_boundary():
    raw = payload(); request = prepare_polar_run(draft(), raw, annulus_count=4)
    artifact = run_polar_run(request)
    result = json.loads(artifact.report_json)
    assert result["physical_qualification"] is False
    assert result["request"]["polar_upload"]["source_json"] == raw.decode()
    assert result["request"]["polar_upload"]["source_sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["request"]["ui_request_sha256"] == request.request_sha256
    preimage = json.dumps(result["request"]["ui_request"], sort_keys=True, separators=(",", ":"), allow_nan=False)
    assert hashlib.sha256(preimage.encode()).hexdigest() == request.request_sha256
    assert result["request"]["draft_sha256"] == request.draft.draft_sha256
    assert result["rotor"]["thrust_n"] > 0
    assert artifact.report_sha256 == hashlib.sha256(artifact.report_json.encode()).hexdigest()


def test_changed_or_forged_request_is_rejected():
    request = prepare_polar_run(draft(), payload(), annulus_count=4)
    with pytest.raises(PolarUploadError, match="identity"):
        run_polar_run(replace(request, payload=payload() + b" "))


def test_narrow_polars_do_not_trigger_clamp_or_partial_result():
    doc = document()
    for table in doc["tables"]: table["alpha_rad"] = [0., 0.001]
    request = prepare_polar_run(draft(), payload(doc), annulus_count=4)
    with pytest.raises(DesignAnalysisError, match="without partial"):
        run_polar_run(request)


def test_nonfinite_derived_sound_speed_rejected_before_solving(monkeypatch):
    import pyfoldable.application.design_analysis as analysis
    monkeypatch.setattr(analysis, "solve_bem_rotor", lambda *a, **k: pytest.fail("invalid solve"))
    with pytest.raises(DesignAnalysisError, match="sound speed"):
        prepare_polar_run(draft(temperature="1e308 K"), payload(), annulus_count=4)


def test_underflowing_rotor_normalization_is_a_controlled_failure():
    factor = 1e-70
    tiny = draft(diameter=f"{.25 * factor} m", hub_radius=f"{.018 * factor} m",
        hinge_radius=f"{.1 * factor} m", angular_speed=f"{7100 / factor} rpm",
        dynamic_viscosity=f"{1.81e-5 * factor} Pa*s")
    request = prepare_polar_run(tiny, payload(), annulus_count=4)
    with pytest.raises(DesignAnalysisError, match="without partial totals"):
        run_polar_run(request)
