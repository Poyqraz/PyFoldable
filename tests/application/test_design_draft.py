"""UI-03B design-draft round-trip acceptance tests."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from pyfoldable.application.design_draft import (
    DesignDraftInputs,
    DraftUnitSelection,
    build_design_draft,
)
from pyfoldable.core import load_design_config


REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_CONFIG = REPO_ROOT / "configs/designs/TIP_HINGED_250_CANONICAL.toml"


def _edited_inputs() -> DesignDraftInputs:
    return DesignDraftInputs(
        diameter="220 mm",
        hub_radius="16 mm",
        hinge_radius="85 mm",
        blade_count=3,
        airfoil_id="NACA0012",
        chord_scale=1.10,
        twist_scale=0.90,
        preview_fold_angle="-60 deg",
        angular_speed="6800 rpm",
        forward_speed="4 m/s",
        air_density="1.18 kg/m^3",
        dynamic_viscosity="1.79e-5 Pa*s",
        temperature="20 degC",
        pressure="100 kPa",
    )


def test_design_draft_round_trips_without_mutating_the_canonical_file(tmp_path: Path) -> None:
    canonical_before = CANONICAL_CONFIG.read_bytes()

    artifact = build_design_draft(CANONICAL_CONFIG, _edited_inputs())

    assert CANONICAL_CONFIG.read_bytes() == canonical_before
    assert artifact.filename == "TIP_HINGED_250_CANONICAL_DRAFT.toml"
    assert len(artifact.source_sha256) == 64
    assert len(artifact.draft_sha256) == 64
    assert 'artifact_class = "unqualified_design_draft"' in artifact.toml
    assert f'source_design_sha256 = "{artifact.source_sha256}"' in artifact.toml
    assert "UI preview pose; not a hinge stop or a physical result" in artifact.toml

    draft_path = tmp_path / artifact.filename
    draft_path.write_text(artifact.toml, encoding="utf-8")
    round_tripped = load_design_config(draft_path)

    assert round_tripped.id == "TIP_HINGED_250_CANONICAL_DRAFT"
    assert round_tripped.blade.diameter_m == pytest.approx(0.220)
    assert round_tripped.blade.hub_radius_m == pytest.approx(0.016)
    assert round_tripped.blade.blade_count == 3
    assert round_tripped.blade.stations[0].chord_m == pytest.approx(
        0.028 * (0.220 / 0.250) * 1.10
    )
    assert round_tripped.blade.stations[0].twist_rad == pytest.approx(
        math.radians(31.0) * 0.90
    )
    assert {station.airfoil_id for station in round_tripped.blade.stations} == {
        "NACA0012"
    }
    assert round_tripped.hinge is not None
    assert round_tripped.hinge.radius_m == pytest.approx(0.085)
    condition = round_tripped.operating_conditions[0]
    assert condition.angular_speed_rad_s == pytest.approx(6800 * 2 * math.pi / 60)
    assert condition.forward_speed_m_s == pytest.approx(4.0)
    assert condition.air_density_kg_m3 == pytest.approx(1.18)
    assert condition.temperature_k == pytest.approx(293.15)
    assert condition.pressure_pa == pytest.approx(100_000.0)


def test_draft_unit_selection_changes_representation_not_si_values(tmp_path: Path) -> None:
    inputs = _edited_inputs()
    engineering = build_design_draft(CANONICAL_CONFIG, inputs)
    alternate = build_design_draft(
        CANONICAL_CONFIG,
        inputs,
        units=DraftUnitSelection(
            length="in",
            angle="rad",
            angular_speed="rad/s",
            speed="km/h",
            temperature="K",
            pressure="Pa",
        ),
    )

    engineering_path = tmp_path / "engineering.toml"
    alternate_path = tmp_path / "alternate.toml"
    engineering_path.write_text(engineering.toml, encoding="utf-8")
    alternate_path.write_text(alternate.toml, encoding="utf-8")

    engineering_design = load_design_config(engineering_path)
    alternate_design = load_design_config(alternate_path)
    assert alternate.toml != engineering.toml
    assert 'diameter = "8.661' in alternate.toml
    assert 'forward_speed = "14.4 km/h"' in alternate.toml
    assert alternate_design.blade.diameter_m == pytest.approx(
        engineering_design.blade.diameter_m
    )
    assert alternate_design.blade.hub_radius_m == pytest.approx(
        engineering_design.blade.hub_radius_m
    )
    assert [station.chord_m for station in alternate_design.blade.stations] == pytest.approx(
        [station.chord_m for station in engineering_design.blade.stations]
    )
    assert [station.twist_rad for station in alternate_design.blade.stations] == pytest.approx(
        [station.twist_rad for station in engineering_design.blade.stations]
    )
    assert alternate_design.operating_conditions[0].angular_speed_rad_s == pytest.approx(
        engineering_design.operating_conditions[0].angular_speed_rad_s
    )
    assert alternate_design.operating_conditions[0].forward_speed_m_s == pytest.approx(
        engineering_design.operating_conditions[0].forward_speed_m_s
    )
    assert alternate_design.hinge is not None
    assert engineering_design.hinge is not None
    assert alternate_design.hinge.radius_m == pytest.approx(
        engineering_design.hinge.radius_m
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("diameter", "220", "explicit unit"),
        ("hinge_radius", "120 mm", "inside the open blade radius"),
        ("airfoil_id", "", "airfoil_id"),
    ],
)
def test_design_draft_rejects_ambiguous_or_invalid_preview_inputs(
    field: str,
    value: object,
    message: str,
) -> None:
    inputs = _edited_inputs()
    invalid = DesignDraftInputs(**{**inputs.__dict__, field: value})

    with pytest.raises(ValueError, match=message):
        build_design_draft(CANONICAL_CONFIG, invalid)
