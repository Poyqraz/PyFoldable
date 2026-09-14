import pytest

from examples.run_literature_modal_audit import build_modal_audit


def test_modal_audit_keeps_rig_and_per_hinge_quantities_separate():
    result = build_modal_audit()
    assert result["physical_qualification"] is False
    assert result["prototype_parameters_changed"] is False
    assert result["angle_time_series_available"] is False
    assert len(result["rows"]) == 5
    first = result["rows"][0]
    assert first["system_modal_damping_nm_s_rad"] == pytest.approx(2 * .0051 * 15.237 * .111)
    assert first["per_hinge_damping_nm_s_rad"] == pytest.approx(first["system_modal_damping_nm_s_rad"] / 4)
    assert first["published_per_hinge_damping_nm_s_rad"] == .0043
    assert first["effective_modal_stiffness_nm_rad"] == pytest.approx(.0051 * 15.237**2)
    assert result["four_springs_quasistatic_stiffness_nm_rad"] == pytest.approx(.4)
    assert result["effective_modal_stiffness_is_measured_spring_stiffness"] is False
    assert len(result["registry_sha256"]) == 64
