"""The interblade diagnostic is separate from the original three surface reports."""

from __future__ import annotations

import hashlib
import json
import math
import runpy
from pathlib import Path

from pyfoldable.geometry.surface_clearance import ClearanceControls


ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = runpy.run_path(str(ROOT / "examples" / "prepare_chord_surface_50mm_screening.py"))
build_interblade_pair_diagnostic = _SCRIPT["build_interblade_pair_diagnostic"]
render_interblade_pair_report = _SCRIPT["render_interblade_pair_report"]
DIRECTORY = ROOT / "reports" / "chord_surface_50mm_screening"
DIAGNOSTIC = DIRECTORY / "interblade_pair_diagnostic.json"
REPORT = DIRECTORY / "interblade_pair_diagnostic.md"
ASSEMBLY = DIRECTORY / "assembly_view.png"
CLOSEUP = DIRECTORY / "hinge_closeup.png"
ORIGINAL = {
    "study.json": "ae2f3434fea0687f79fbbe9a9b5d7e0e4efe488c276e53d5fb3423e411738718",
    "report.md": "546e95e1b61bd19ea57a00741cd429d338dd2f0aefc1b2c34169506a95729537",
    "plan_view.png": "434990960aeec4f2e27c3dba8e29e75c5040e91ebee45ea2b4cf177703f36244",
    "surface_view.png": "8b88f5a8f03852f540e63f91ad770f8e9d8c6f34c9e85d7bd22d45a7e6a15c52",
}
RETAINED = {
    "reports/retained_pins/jvp01_geometry_identity/packet.json": "5df16176a8774b02a0b2d3bd5dfc3b98c2e272761714f5f7b5c743d7f1388531",
    "reports/retained_pins/hinge_location_geometry_screening/study.json": "f3c3e927c0ede938e5e770cce2eab405ca8413cec997eb17ab620b5fe22a7124",
    "reports/retained_pins/intermediate_fold_50mm_screening/study.json": "8d219acb44aa7cdd5fcf7d858ab1a59636d9aa413214d0756384102a8e4e2815",
}


def _without_runtime(record: dict) -> dict:
    copy = json.loads(json.dumps(record))
    copy.pop("runtime", None)
    return copy


def _hashes() -> dict[str, str]:
    found = {
        name: hashlib.sha256((DIRECTORY / name).read_bytes()).hexdigest()
        for name in ORIGINAL
    }
    found.update({
        relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        for relative in RETAINED
    })
    return found


def test_pair_diagnostic_preserves_the_original_reports() -> None:
    before = _hashes()
    recorded = json.loads(DIAGNOSTIC.read_text(encoding="utf-8"))
    rebuilt = build_interblade_pair_diagnostic(ROOT)
    assert _hashes() == before
    assert before == {**ORIGINAL, **RETAINED}
    assert _without_runtime(recorded) == _without_runtime(rebuilt)
    assert recorded["reviewed_surface_head"] == "284a2e4f3b33f999fddcb9d8eb0b3a98ebf53c26"
    assert recorded["study_draft_sha256"] == "89dfdd1907e9fe2221adea7ffa193f1849fbc1d6052dced1dafe5d20279c07d1"
    assert recorded["physical_qualification"] is False
    assert recorded["qualified_winner"] is None
    assert recorded["selected_stop"] is None
    assert recorded["selected_hinge"] is None
    assert recorded["full_propeller_clearance"] is None
    assert recorded["path"]["start_deg"] == 0.0
    assert recorded["path"]["end_deg"] == -135.0
    assert recorded["declaration"]["required_clearance_m"] == 0.0
    assert recorded["declaration"]["root_attachment_m"] == 0.0
    assert recorded["declaration"]["hinge_attachment_m"] == 0.0
    assert recorded["declaration"]["calls_per_pair"] == 1
    assert recorded["declaration"]["retries"] is False
    assert recorded["aggregate_used"]["pair_calls"] == 4
    assert recorded["aggregate_used"]["node_comparisons"] <= 200000
    assert recorded["aggregate_used"]["feature_tests"] <= 8192
    assert [(row["a"], row["b"]) for row in recorded["pairs"]] == [
        ("blade_1_root", "blade_2_root"),
        ("blade_1_root", "blade_2_tip"),
        ("blade_1_tip", "blade_2_root"),
        ("blade_1_tip", "blade_2_tip"),
    ]
    for row in recorded["pairs"]:
        result = row["result"]
        assert result["node_comparisons"] <= 50000
        assert result["feature_tests"] <= 2048
        assert len(result["intervals"]) <= 127
    own = recorded["preserved_original_m135"]["own_root_tip"]
    assert [row["status"] for row in own] == ["unknown", "unknown"]
    assert recorded["preserved_original_m135"]["station_span_complete"] is False
    assert recorded["preserved_original_m135"]["full_propeller_clearance"] is None
    assert render_interblade_pair_report(recorded) == REPORT.read_text(encoding="utf-8")
    assert "Selected stop: none" in REPORT.read_text(encoding="utf-8")
    assert ASSEMBLY.read_bytes().startswith(b"\x89PNG")
    assert CLOSEUP.read_bytes().startswith(b"\x89PNG")


def test_diagnostic_calls_each_interblade_pair_once(monkeypatch) -> None:
    module = build_interblade_pair_diagnostic.__globals__
    calls = []
    real = module["pair_clearance"]

    def _wrapped(*args, **kwargs):
        calls.append(kwargs)
        return real(*args, **kwargs)

    def _forbidden(*_args, **_kwargs):
        raise AssertionError("original surface report was rerun")

    monkeypatch.setitem(module, "pair_clearance", _wrapped)
    monkeypatch.setitem(module, "run_surface_clearance", _forbidden)
    record = build_interblade_pair_diagnostic(ROOT)
    assert [(call["controls"].max_node_comparisons, call["controls"].max_feature_tests, call["controls"].max_depth, call["controls"].max_intervals, call["clearance_m"]) for call in calls] == [
        (50000, 2048, 6, 127, 0.0),
        (50000, 2048, 6, 127, 0.0),
        (50000, 2048, 6, 127, 0.0),
        (50000, 2048, 6, 127, 0.0),
    ]
    assert all(isinstance(call["controls"], ClearanceControls) for call in calls)
    assert record["aggregate_used"]["pair_calls"] == 4


def _point_set(part, angle_deg: float) -> set[tuple[float, float, float]]:
    return {
        tuple(round(coord, 9) for coord in point)
        for triangle in _SCRIPT["_posed_triangles"](part, math.radians(angle_deg))
        for point in triangle
    }


def test_spatial_views_keep_the_numerical_record_and_the_shared_boundary(monkeypatch) -> None:
    module = build_interblade_pair_diagnostic.__globals__

    def _forbidden(*_args, **_kwargs):
        raise AssertionError("clearance was rerun")

    monkeypatch.setitem(module, "pair_clearance", _forbidden)
    monkeypatch.setitem(module, "run_surface_clearance", _forbidden)
    before = _hashes()
    json_bytes = DIAGNOSTIC.read_bytes()
    module["write_spatial_views"](ROOT, DIRECTORY)
    module["refresh_interblade_report"](ROOT, DIRECTORY)
    assert _hashes() == before
    assert DIAGNOSTIC.read_bytes() == json_bytes
    report = REPORT.read_text(encoding="utf-8")
    assert report == render_interblade_pair_report(json.loads(json_bytes))
    assert "XY projections" in report
    assert "copies the hinge station twice" in report
    assert "not a contact finding" in report
    assert (DIRECTORY / "assembly_oblique.png").read_bytes().startswith(b"\x89PNG")
    assert (DIRECTORY / "hinge_region_views.png").read_bytes().startswith(b"\x89PNG")
    _bundle, _trial, _draft, parts = module["_retained_parts"](ROOT)
    lookup = {part.name: part for part in parts}
    assert _point_set(lookup["blade_1_root"], 0.0) == _point_set(lookup["blade_1_root"], -135.0)
    assert _point_set(lookup["blade_1_tip"], 0.0) != _point_set(lookup["blade_1_tip"], -135.0)
    shared_deployed = _point_set(lookup["blade_1_root"], 0.0) & _point_set(lookup["blade_1_tip"], 0.0)
    shared_folded = _point_set(lookup["blade_1_root"], -135.0) & _point_set(lookup["blade_1_tip"], -135.0)
    assert len(shared_deployed) > 10
    assert len(shared_folded) < len(shared_deployed)
