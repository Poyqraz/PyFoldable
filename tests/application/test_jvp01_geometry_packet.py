"""Identity checks for the schema-example JVP-01 geometry packet."""

from __future__ import annotations

import hashlib
import json
import runpy
from pathlib import Path

from pyfoldable.core.airfoil import airfoil_coordinate_sha256
from pyfoldable.core.profile_catalog import load_project_airfoil


ROOT = Path(__file__).resolve().parents[2]
# examples is not an installed package. Load the evidence script by path.
_PACKET_SCRIPT = runpy.run_path(str(ROOT / "examples" / "prepare_jvp01_geometry_packet.py"))
SOURCE_RELATIVE = _PACKET_SCRIPT["SOURCE_RELATIVE"]
build_jvp01_packet = _PACKET_SCRIPT["build_jvp01_packet"]
render_jvp01_report = _PACKET_SCRIPT["render_jvp01_report"]
PACKET_PATH = ROOT / "reports" / "jvp01_geometry_identity" / "packet.json"
REPORT_PATH = ROOT / "reports" / "jvp01_geometry_identity" / "report.md"
NACA2412_SHA256 = "3f84aba0f9234ed6e9fe4eedebe88ae8701a19ae181d70e21a02b0704916999a"
_GEOMETRIC_FIELDS = (
    "radial_gap",
    "surface_step",
    "fold_misalignment",
    "pitch_misalignment",
    "sweep_misalignment",
    "exposed_hardware",
    "joint_tolerances",
)


def _without_runtime(packet: dict) -> dict:
    copy = json.loads(json.dumps(packet))
    copy.pop("runtime", None)
    return copy


def test_committed_packet_matches_existing_services_and_states_absence() -> None:
    recorded = json.loads(PACKET_PATH.read_text(encoding="utf-8"))
    rebuilt = build_jvp01_packet(ROOT)
    report = REPORT_PATH.read_text(encoding="utf-8")

    assert _without_runtime(recorded) == _without_runtime(rebuilt)
    assert recorded["physical_qualification"] is False
    assert recorded["scenario"]["thirteen_inch_included"] is False
    assert recorded["source"]["path"] == SOURCE_RELATIVE
    assert recorded["source"]["sha256"] == hashlib.sha256(
        (ROOT / SOURCE_RELATIVE).read_bytes()
    ).hexdigest()
    assert recorded["profile"]["airfoil_coordinate_sha256"] == NACA2412_SHA256
    assert recorded["profile"]["airfoil_coordinate_sha256"] == airfoil_coordinate_sha256(
        load_project_airfoil("NACA2412")
    )
    assert recorded["case_A"]["bundle"] == recorded["parent"]["bundle"]
    assert recorded["case_A"]["canonical_sha256"] == recorded["parent"]["canonical_sha256"]
    assert recorded["hinge"]["radius_m"] == 0.1
    assert recorded["hinge"]["station_inserted"] is False
    assert recorded["hinge"]["schema_axial_offset_m"] == 0.0
    assert recorded["hinge"]["schema_tangential_offset_m"] == 0.0
    assert recorded["draft"]["chord_scale"] == 1.0
    assert recorded["draft"]["twist_scale"] == 1.0
    assert len(recorded["stations"]) == 5
    assert recorded["stations"][3]["radius_m"] == 0.1
    assert recorded["coverage"]["span_complete"] is False
    assert recorded["coverage"]["surface_path_clearance"] is None
    for name in _GEOMETRIC_FIELDS:
        field = recorded["geometric_inventory"][name]
        assert field["status"] == "absent"
        assert field["value"] is None
        assert field["source"] is None
        assert field["uncertainty"] is None
    assert set(recorded["mechanical_properties"].values()) == {"unestablished"}
    assert recorded["case_C"]["status"] == "unsolved"
    assert "thrust_n" not in json.dumps(recorded)
    assert "BEM" in recorded["not_executed"]
    assert recorded["services"]["two_cut_generator_used"] is False
    assert "physical_qualification: false" in report
    assert recorded["parent"]["canonical_sha256"] in report
    assert "Those zeros are not a flush-joint measurement." in report
    assert render_jvp01_report(recorded) == report
