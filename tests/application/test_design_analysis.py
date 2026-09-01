"""Active-design analysis must never rerun or relabel the APC benchmark."""

import hashlib
import json
import math
from dataclasses import replace
from pathlib import Path

import pytest

from pyfoldable.application.design_draft import DesignDraftInputs, build_design_draft
from pyfoldable.application.design_analysis import (
    DesignAnalysisError,
    prepare_design_analysis,
    run_design_analysis,
)
from pyfoldable.core import BEMRotorSettings, PolarFamily, PolarTable


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "configs/designs/TIP_HINGED_250_CANONICAL.toml"


def _draft(**changes):
    inputs = DesignDraftInputs(
        diameter="250 mm", hub_radius="18 mm", hinge_radius="100 mm",
        blade_count=2, airfoil_id="NACA2412", chord_scale=1.0, twist_scale=1.0,
        preview_fold_angle="0 deg", angular_speed="7100 rpm",
        forward_speed="0 m/s", air_density="1.225 kg/m^3",
        dynamic_viscosity="1.81e-5 Pa*s", temperature="288.15 K",
        pressure="101325 Pa",
    )
    return build_design_draft(SOURCE, replace(inputs, **changes))


def _family(*, airfoil_id="NACA2412", lift=0.8, re_min=100.0):
    return PolarFamily(tuple(
        PolarTable(
            airfoil_id=airfoil_id, scenario_id="synthetic-service-test",
            reynolds=reynolds, mach=mach,
            alpha_rad=(-math.pi / 2, math.pi / 2),
            cl=(lift, lift), cd=(0.02, 0.02), cm=(0.0, 0.0),
            source="first-party synthetic test; not measured",
        )
        for reynolds in (re_min, 1e7) for mach in (0.0, 1.0)
    ))


def _run(draft=None, family=None, **kwargs):
    return run_design_analysis(
        draft or _draft(), {"NACA2412": family or _family()},
        settings=kwargs.pop("settings", BEMRotorSettings(annulus_count=4)), **kwargs,
    )


def test_preparation_uses_actual_draft_and_has_no_performance_claim():
    draft = _draft()
    result = prepare_design_analysis(draft)
    doc = json.loads(result.report_json)
    assert doc["artifact_class"] == "active_design_analysis_preparation"
    assert doc["physical_qualification"] is False
    assert doc["preparation"]["scope"] == "open_declared_stations_no_induction"
    assert doc["preparation"]["solver_envelope_complete"] is False
    assert doc["request"]["draft_sha256"] == draft.draft_sha256
    assert doc["request"]["draft_toml"] == draft.toml
    assert doc["preparation"]["diameter_m"] == pytest.approx(0.250)
    assert "thrust_n" not in doc["preparation"]
    rows = doc["preparation"]["stations"]
    assert len(rows) == 5
    first = rows[0]
    speed = 7100 * 2 * math.pi / 60 * 0.025
    assert first["radius_m"] == pytest.approx(0.025)
    assert first["relative_speed_m_s"] == pytest.approx(speed)
    assert first["reynolds"] == pytest.approx(1.225 * speed * 0.028 / 1.81e-5)
    assert first["mach"] == pytest.approx(speed / math.sqrt(1.4 * 287.05 * 288.15))
    assert first["alpha_rad"] == pytest.approx(math.radians(31))
    assert doc["preparation"]["root_gap_m"] == pytest.approx(0.007)
    assert doc["preparation"]["tip_gap_m"] == pytest.approx(0.0025)


@pytest.mark.parametrize("changes", [
    {"diameter": "300 mm"}, {"angular_speed": "6800 rpm"},
    {"chord_scale": 1.1}, {"twist_scale": 0.8}, {"forward_speed": "5 m/s"},
    {"air_density": "1.1 kg/m^3"}, {"dynamic_viscosity": "1.9e-5 Pa*s"},
    {"temperature": "300 K"}, {"airfoil_id": "NACA0012"},
])
def test_each_active_input_changes_request_identity(changes):
    baseline = prepare_design_analysis(_draft())
    changed = prepare_design_analysis(_draft(**changes))
    assert changed.request_sha256 != baseline.request_sha256
    assert changed.report_sha256 != baseline.report_sha256


def test_geometric_scaling_and_twist_have_correct_nominal_effects():
    base = json.loads(prepare_design_analysis(_draft()).report_json)["preparation"]
    larger = json.loads(prepare_design_analysis(_draft(diameter="500 mm")).report_json)["preparation"]
    twisted = json.loads(prepare_design_analysis(_draft(twist_scale=0.5)).report_json)["preparation"]
    assert larger["stations"][0]["reynolds"] == pytest.approx(4 * base["stations"][0]["reynolds"])
    assert twisted["stations"][0]["alpha_rad"] == pytest.approx(base["stations"][0]["alpha_rad"] / 2)


def test_run_uses_existing_rotor_solver_and_reports_full_audit():
    before = SOURCE.read_bytes()
    result = _run()
    doc = json.loads(result.report_json)
    assert SOURCE.read_bytes() == before
    assert doc["artifact_class"] == "active_design_bem_screening"
    assert doc["physical_qualification"] is False
    assert doc["qualification"] == "screening_only_until_pr06c_passes"
    assert doc["request"]["policy"]["bounds"] == "error"
    assert doc["request"]["policy"]["radial_domain"] == "station_span"
    assert doc["request"]["polar_evidence_status"] == "caller_supplied_unqualified"
    rotor = doc["rotor"]
    assert rotor["thrust_n"] > 0
    assert rotor["shaft_power_w"] == pytest.approx(rotor["torque_nm"] * 7100 * 2 * math.pi / 60)
    assert rotor["propulsive_efficiency"] is None
    assert rotor["annulus_count"] == 4
    assert rotor["polar_query_envelope"]["query_count"] > 4
    assert doc["request"]["polar_families"]["NACA2412"][0]["cl"] == [0.8, 0.8]


def test_results_and_hashes_are_deterministic_and_content_addressed():
    first, second = _run(), _run()
    assert first == second
    assert first.report_sha256 == hashlib.sha256(first.report_json.encode()).hexdigest()
    request = json.loads(first.report_json)["request"]
    payload = json.dumps(request, sort_keys=True, separators=(",", ":"), allow_nan=False)
    assert first.request_sha256 == hashlib.sha256(payload.encode()).hexdigest()


def test_changed_diameter_changes_solver_totals_and_polar_change_changes_hash():
    first = _run()
    changed = _run(_draft(diameter="300 mm"))
    changed_polar = _run(family=_family(lift=0.9))
    assert json.loads(first.report_json)["rotor"]["thrust_n"] != json.loads(changed.report_json)["rotor"]["thrust_n"]
    assert first.request_sha256 != changed_polar.request_sha256


@pytest.mark.parametrize("changes", [{"angular_speed": "0 rpm"}, {"forward_speed": "-1 m/s"}])
def test_unsupported_operating_states_are_rejected(changes):
    with pytest.raises(DesignAnalysisError, match="positive RPM|negative forward"):
        prepare_design_analysis(_draft(**changes))


def test_preparation_explicitly_ignores_preview_pose_but_run_rejects_folded_pose():
    draft = _draft(preview_fold_angle="-30 deg")
    doc = json.loads(prepare_design_analysis(draft).report_json)
    assert doc["preparation"]["preview_fold_angle_rad"] == pytest.approx(-math.pi / 6)
    assert doc["preparation"]["scope"] == "open_declared_stations_no_induction"
    with pytest.raises(DesignAnalysisError, match="fully open"):
        _run(draft)


@pytest.mark.parametrize("field,value", [("draft_sha256", "0" * 64), ("source_sha256", "0" * 64), ("toml", "broken")])
def test_tampered_draft_is_rejected(field, value):
    with pytest.raises(DesignAnalysisError, match="SHA|draft"):
        prepare_design_analysis(replace(_draft(), **{field: value}))


def test_missing_wrong_or_extra_polars_are_not_substituted():
    for families in ({}, {"NACA2412": _family(airfoil_id="NACA0012")},
                     {"NACA2412": _family(), "extra": _family(airfoil_id="extra")}):
        with pytest.raises(DesignAnalysisError, match="polar|airfoil"):
            run_design_analysis(_draft(), families)


def test_out_of_bounds_polar_fails_without_partial_result():
    with pytest.raises(DesignAnalysisError, match="outside"):
        _run(family=_family(re_min=1e6))


def test_geometry_extension_is_not_silently_enabled():
    with pytest.raises(DesignAnalysisError, match="station_span"):
        _run(settings=BEMRotorSettings(radial_domain="hub_to_tip"))


def test_polar_tables_order_does_not_change_request_identity():
    family = _family()
    assert _run(family=family).request_sha256 == _run(family=PolarFamily(tuple(reversed(family.tables)))).request_sha256


def test_settings_change_request_identity():
    assert _run().request_sha256 != _run(settings=BEMRotorSettings(annulus_count=6)).request_sha256


def test_nominal_polar_coverage_does_not_imply_full_solver_coverage():
    family = PolarFamily(tuple(
        replace(table, alpha_rad=(math.radians(5), math.radians(31)))
        for table in _family().tables
    ))
    doc = json.loads(prepare_design_analysis(_draft()).report_json)
    for row in doc["preparation"]["stations"]:
        family.query(alpha_rad=row["alpha_rad"], reynolds=row["reynolds"], mach=row["mach"])
    with pytest.raises(DesignAnalysisError, match="outside"):
        _run(family=family)


def _rewrite_draft(old, before, after):
    assert before in old.toml
    toml = old.toml.replace(before, after)
    return replace(old, toml=toml, draft_sha256=hashlib.sha256(toml.encode()).hexdigest())


@pytest.mark.parametrize("field", ["axial_offset", "tangential_offset"])
def test_open_solver_rejects_offset_geometry(field):
    draft = _rewrite_draft(_draft(), f'{field} = "0.0 mm"', f'{field} = "1.0 mm"')
    with pytest.raises(DesignAnalysisError, match="zero-offset"):
        _run(draft)


def test_polar_metadata_mutation_during_solver_cannot_change_snapshot(monkeypatch):
    import pyfoldable.application.design_analysis as service

    family = _family()
    family.tables[0].metadata["note"] = "original"
    original_solver = service.solve_bem_rotor

    def mutate_then_solve(*args, **kwargs):
        family.tables[0].metadata["note"] = "changed-outside-snapshot"
        return original_solver(*args, **kwargs)

    monkeypatch.setattr(service, "solve_bem_rotor", mutate_then_solve)
    result = _run(family=family)
    tables = json.loads(result.report_json)["request"]["polar_families"]["NACA2412"]
    assert [table["metadata"].get("note") for table in tables].count("original") == 1
    assert "changed-outside-snapshot" not in result.report_json


def test_nonfinite_or_non_json_polar_metadata_is_rejected():
    for value in (math.nan, object()):
        family = _family()
        family.tables[0].metadata["invalid"] = value
        with pytest.raises(DesignAnalysisError, match="JSON-safe"):
            _run(family=family)


def test_actual_local_nonconvergence_cannot_return_totals():
    from pyfoldable.core import BEMAnnulusSettings

    settings = BEMRotorSettings(annulus_count=4, annulus_settings=BEMAnnulusSettings(max_iterations=1))
    with pytest.raises(DesignAnalysisError, match="without partial totals"):
        _run(settings=settings)


def test_mach_bounds_error_is_not_clamped():
    family = PolarFamily(tuple(replace(table, mach=table.mach * 0.001) for table in _family().tables))
    with pytest.raises(DesignAnalysisError, match="mach.*outside"):
        _run(family=family)


def test_source_code_and_runtime_identity_are_recorded():
    doc = json.loads(_run().report_json)
    identity = doc["request"]["implementation"]
    module_path = ROOT / "pyfoldable/core/bem.py"
    assert identity["source_files_sha256"]["pyfoldable.core.bem"] == hashlib.sha256(module_path.read_bytes()).hexdigest()
    assert all(identity[key] for key in ("python", "numpy", "scipy"))


def test_resource_budget_is_enforced():
    with pytest.raises(DesignAnalysisError, match="budget"):
        _run(settings=BEMRotorSettings(annulus_count=257))
