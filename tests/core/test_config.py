"""Versioned design configuration loader tests."""

import math
from pathlib import Path

import pytest

from pyfoldable.core import DesignConfigError, load_design_config


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_CONFIG = PROJECT_ROOT / "configs" / "designs" / "TIP_HINGED_250_CANONICAL.toml"


def test_reference_toml_loads_as_si_design() -> None:
    design = load_design_config(CANONICAL_CONFIG)

    assert design.id == "TIP_HINGED_250_CANONICAL"
    assert design.blade.diameter_m == pytest.approx(0.25)
    assert design.blade.hub_radius_m == pytest.approx(0.018)
    assert design.blade.stations[0].chord_m == pytest.approx(0.028)
    assert design.blade.stations[0].twist_rad == pytest.approx(math.radians(31.0))
    assert design.operating_conditions[0].angular_speed_rad_s == pytest.approx(
        7100.0 * 2.0 * math.pi / 60.0
    )
    assert design.hinge is not None
    assert design.hinge.radius_m == pytest.approx(0.1)
    assert design.motor is not None
    assert design.motor.kv_rad_s_per_v == pytest.approx(980.0 * 2.0 * math.pi / 60.0)


def test_loader_records_input_unit_provenance() -> None:
    design = load_design_config(CANONICAL_CONFIG)
    units = design.metadata["input_units"]

    assert units["blade.diameter"] == "mm"
    assert units["operating_conditions[0].angular_speed"] == "rpm"
    assert design.metadata["canonical_unit_system"] == "SI"
    assert design.metadata["schema_version"] == 1


def test_loader_rejects_unsupported_schema(tmp_path: Path) -> None:
    path = tmp_path / "invalid.toml"
    path.write_text("schema_version = 2\n", encoding="utf-8")

    with pytest.raises(DesignConfigError, match="Unsupported schema_version"):
        load_design_config(path)


def test_loader_rejects_unitless_physical_value(tmp_path: Path) -> None:
    content = CANONICAL_CONFIG.read_text(encoding="utf-8").replace(
        'diameter = "250 mm"', "diameter = 250", 1
    )
    path = tmp_path / "unitless.toml"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(DesignConfigError, match="explicit unit"):
        load_design_config(path)


def test_loader_rejects_fractional_blade_count(tmp_path: Path) -> None:
    content = CANONICAL_CONFIG.read_text(encoding="utf-8").replace(
        "blade_count = 2", "blade_count = 2.5", 1
    )
    path = tmp_path / "fractional_blades.toml"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(DesignConfigError, match="must be an integer"):
        load_design_config(path)
