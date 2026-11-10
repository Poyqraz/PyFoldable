from dataclasses import replace
from pathlib import Path

import pytest

from pyfoldable.application import research_design as release
from pyfoldable.application import provider_design_analysis as managed
from pyfoldable.core.profile_catalog import PROJECT_AIRFOIL_IDS

ROOT = Path(__file__).resolve().parents[2]


def test_six_profiles_share_parent_and_retain_coordinates():
    designs = [release.build_research_design(ROOT, replace(release.defaults(ROOT), profile=p))
               for p in PROJECT_AIRFOIL_IDS]
    assert len({d.coordinate_sha256 for d in designs}) == 6
    assert len({tuple((s.r_over_R, s.chord_m, s.twist_rad) for s in d.design.blade.stations)
                for d in designs}) == 1
    assert all(d.design.blade.hub_radius_m != d.inputs.root_mm / 1000 for d in designs)


def test_named_project_requirement_and_either_order_are_distinct():
    baseline = release.defaults(ROOT, "project_250")
    assert baseline.root_mm is None
    historic = release.build_research_design(ROOT, replace(
        baseline, root_mm=20, root_meaning="physical blade start", root_source="declared test root", hinge_mm=65))
    exploratory = release.build_research_design(ROOT, replace(release.defaults(ROOT), hinge_mm=205))
    assert exploratory.exposed_lengths_m[0] < exploratory.exposed_lengths_m[1]
    assert historic.exposed_lengths_m[0] < historic.exposed_lengths_m[1]
    assert managed._geometry(release.selection_for(exploratory, None))["length_order_policy"] == "either_order"
    with pytest.raises(managed.ProviderDesignPreparationError, match="longer_proximal_required"):
        managed._geometry(release.selection_for(historic, None))


def test_no_data_and_missing_mechanism_leave_geometry_and_null_totals(monkeypatch):
    d = release.build_research_design(ROOT, release.defaults(ROOT))
    monkeypatch.setattr(managed, "run_provider_design_analysis",
                        lambda *a, **k: pytest.fail("BEM reached without admission"))
    row = release.run_research(d, None, managed.ManagedProviderRepository(), None)
    assert row["geometry"]["status"] == "computed"
    assert row["aerodynamics"]["status"] == "failure"
    assert row["aerodynamics"]["thrust_n"] is None
    assert row["aerodynamics"]["report_text"] is None
    assert row["mechanism"]["status"] == "missing_inputs"
    assert release.read_saved_result(release.saved_result_json(row).encode()) == row
    row["geometry"]["status"] = "changed"
    with pytest.raises(ValueError, match="checksum"):
        release.read_saved_result(release.saved_result_json(row).encode())
