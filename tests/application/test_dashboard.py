import math
from pathlib import Path

import pytest

from pyfoldable.application.dashboard import (
    DashboardConfigError,
    EvidenceState,
    load_dashboard_snapshot,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "configs" / "ui" / "dashboard.toml"


def test_default_dashboard_is_bound_to_canonical_design_and_evidence():
    snapshot = load_dashboard_snapshot(REPO_ROOT)

    assert snapshot.design_id == "TIP_HINGED_250_CANONICAL"
    assert math.isclose(snapshot.open_diameter_m, 0.25)
    assert math.isclose(snapshot.stowed_envelope_m, 0.14)
    assert math.isclose(snapshot.checkpoint_rpm, 7100.0)
    assert len(snapshot.manifest_sha256) == 64
    assert snapshot.design_path == REPO_ROOT / "configs/designs/TIP_HINGED_250_CANONICAL.toml"
    assert len(snapshot.design_sha256) == 64
    assert snapshot.qualification_warning
    assert snapshot.blade_count == 2
    assert math.isclose(snapshot.hub_radius_m, 0.018)
    assert math.isclose(snapshot.hinge_radius_m, 0.1)
    assert len(snapshot.blade_stations) == 5
    assert snapshot.blade_stations[0].airfoil_id == "NACA2412"
    assert snapshot.operating_conditions[0].id == "hover_7100_rpm"
    assert math.isclose(snapshot.operating_conditions[0].rpm, 7100.0)
    assert math.isclose(snapshot.operating_conditions[0].dynamic_viscosity_pa_s, 1.81e-5)

    gates = {gate.id: gate for gate in snapshot.gates}
    assert set(gates) == {"PR-06C", "PR-06D", "PR-07", "PR-08", "PR-09", "PR-10"}
    assert gates["PR-06C"].state is EvidenceState.BLOCKED
    assert gates["PR-06D"].state is EvidenceState.SCREENING_ONLY
    assert gates["PR-07"].state is EvidenceState.PENDING
    assert gates["PR-08"].state is EvidenceState.PENDING
    assert gates["PR-09"].state is EvidenceState.PENDING
    assert gates["PR-10"].state is EvidenceState.PENDING
    assert all(gate.evidence_path.exists() for gate in snapshot.gates)
    assert all(len(gate.evidence_sha256) == 64 for gate in snapshot.gates)


def test_dashboard_rejects_manifest_that_disagrees_with_evidence(tmp_path):
    invalid_manifest = tmp_path / "dashboard.toml"
    invalid_manifest.write_text(
        MANIFEST.read_text(encoding="utf-8").replace(
            'expected_decision = "pr06c_blocked"',
            'expected_decision = "pr06c_passed"',
        ),
        encoding="utf-8",
    )

    with pytest.raises(DashboardConfigError, match="expected decision"):
        load_dashboard_snapshot(REPO_ROOT, manifest_path=invalid_manifest)


def test_dashboard_rejects_qualified_state_without_qualified_evidence(tmp_path):
    invalid_manifest = tmp_path / "dashboard.toml"
    invalid_manifest.write_text(
        MANIFEST.read_text(encoding="utf-8").replace(
            'state = "blocked"',
            'state = "qualified"',
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(DashboardConfigError, match="cannot be marked qualified"):
        load_dashboard_snapshot(REPO_ROOT, manifest_path=invalid_manifest)


def test_dashboard_rejects_evidence_paths_outside_repository(tmp_path):
    invalid_manifest = tmp_path / "dashboard.toml"
    invalid_manifest.write_text(
        MANIFEST.read_text(encoding="utf-8").replace(
            'evidence_path = "reports/pr06c_physical_gate.json"',
            'evidence_path = "../outside.json"',
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises(DashboardConfigError, match="inside the repository"):
        load_dashboard_snapshot(REPO_ROOT, manifest_path=invalid_manifest)
