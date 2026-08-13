"""Versioned TOML/JSON loader for canonical PyFoldable designs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

try:  # pragma: no cover - exercised by Python 3.10 CI
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

from .models import (
    AirfoilDefinition,
    BladeGeometry,
    BladeStation,
    HingeGeometry,
    ManufacturingModel,
    MaterialModel,
    MotorModel,
    OperatingCondition,
    PropellerDesign,
    ValidationRecord,
)
from .units import QuantityInput, normalize_quantity


class DesignConfigError(ValueError):
    """Raised when a canonical design file is structurally invalid."""


def _mapping(parent: Mapping[str, Any], key: str, *, required: bool = True) -> Mapping[str, Any]:
    value = parent.get(key)
    if value is None and not required:
        return {}
    if not isinstance(value, Mapping):
        raise DesignConfigError(f"Config field {key!r} must be a table/object.")
    return value


def _tables(parent: Mapping[str, Any], key: str, *, required: bool = True) -> list[Mapping[str, Any]]:
    value = parent.get(key)
    if value is None and not required:
        return []
    if not isinstance(value, list) or not all(isinstance(item, Mapping) for item in value):
        raise DesignConfigError(f"Config field {key!r} must be an array of tables/objects.")
    return value


def _required(parent: Mapping[str, Any], key: str, path: str) -> Any:
    if key not in parent:
        raise DesignConfigError(f"Missing required config field {path}.{key}.")
    return parent[key]


def _integer(parent: Mapping[str, Any], key: str, path: str, *, minimum: int) -> int:
    raw = _required(parent, key, path)
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise DesignConfigError(f"Config field {path}.{key} must be an integer.")
    if raw < minimum:
        raise DesignConfigError(
            f"Config field {path}.{key} must be at least {minimum}."
        )
    return raw


def _quantity(
    parent: Mapping[str, Any],
    key: str,
    dimension: str,
    path: str,
    unit_inputs: dict[str, str],
    *,
    default: QuantityInput | None = None,
) -> float:
    raw = parent.get(key, default)
    if raw is None:
        raise DesignConfigError(f"Missing required config field {path}.{key}.")
    field_path = f"{path}.{key}"
    try:
        normalized = normalize_quantity(raw, dimension, field=field_path)
    except ValueError as exc:
        raise DesignConfigError(str(exc)) from exc
    unit_inputs[field_path] = normalized.input_unit
    return normalized.si_value


def _read_document(path: Path) -> Mapping[str, Any]:
    suffix = path.suffix.casefold()
    if suffix == ".toml":
        with path.open("rb") as stream:
            raw = tomllib.load(stream)
    elif suffix == ".json":
        raw = json.loads(path.read_text(encoding="utf-8"))
    else:
        raise DesignConfigError("Canonical design files must use .toml or .json.")
    if not isinstance(raw, Mapping):
        raise DesignConfigError("The design document root must be a table/object.")
    return raw


def load_design_config(path: str | Path) -> PropellerDesign:
    """Load a version-1 canonical design and normalize every quantity to SI."""
    config_path = Path(path)
    raw = _read_document(config_path)
    schema_version = raw.get("schema_version")
    if schema_version != 1:
        raise DesignConfigError(f"Unsupported schema_version {schema_version!r}; expected 1.")

    unit_inputs: dict[str, str] = {}
    design_raw = _mapping(raw, "design")
    blade_raw = _mapping(raw, "blade")
    station_rows = _tables(blade_raw, "stations")

    airfoils = tuple(
        AirfoilDefinition(
            id=str(_required(row, "id", f"airfoils[{index}]")),
            source=str(row.get("source", "unspecified")),
            metadata=dict(_mapping(row, "metadata", required=False)),
        )
        for index, row in enumerate(_tables(raw, "airfoils"))
    )
    stations = tuple(
        BladeStation(
            r_over_R=_quantity(row, "r_over_R", "dimensionless", f"blade.stations[{index}]", unit_inputs),
            chord_m=_quantity(row, "chord", "length", f"blade.stations[{index}]", unit_inputs),
            twist_rad=_quantity(row, "twist", "angle", f"blade.stations[{index}]", unit_inputs),
            airfoil_id=str(_required(row, "airfoil", f"blade.stations[{index}]")),
        )
        for index, row in enumerate(station_rows)
    )
    blade = BladeGeometry(
        diameter_m=_quantity(blade_raw, "diameter", "length", "blade", unit_inputs),
        hub_radius_m=_quantity(blade_raw, "hub_radius", "length", "blade", unit_inputs),
        blade_count=_integer(blade_raw, "blade_count", "blade", minimum=1),
        stations=stations,
    )

    conditions = tuple(
        OperatingCondition(
            id=str(_required(row, "id", f"operating_conditions[{index}]")),
            angular_speed_rad_s=_quantity(row, "angular_speed", "angular_speed", f"operating_conditions[{index}]", unit_inputs),
            forward_speed_m_s=_quantity(row, "forward_speed", "speed", f"operating_conditions[{index}]", unit_inputs),
            air_density_kg_m3=_quantity(row, "air_density", "density", f"operating_conditions[{index}]", unit_inputs),
            dynamic_viscosity_pa_s=_quantity(row, "dynamic_viscosity", "dynamic_viscosity", f"operating_conditions[{index}]", unit_inputs),
            temperature_k=_quantity(row, "temperature", "temperature", f"operating_conditions[{index}]", unit_inputs),
            pressure_pa=_quantity(row, "pressure", "pressure", f"operating_conditions[{index}]", unit_inputs),
        )
        for index, row in enumerate(_tables(raw, "operating_conditions"))
    )

    hinge_raw = _mapping(raw, "hinge", required=False)
    hinge = None
    if hinge_raw:
        hinge = HingeGeometry(
            radius_m=_quantity(hinge_raw, "radius", "length", "hinge", unit_inputs),
            axial_offset_m=_quantity(hinge_raw, "axial_offset", "length", "hinge", unit_inputs, default="0 m"),
            tangential_offset_m=_quantity(hinge_raw, "tangential_offset", "length", "hinge", unit_inputs, default="0 m"),
            axis_azimuth_rad=_quantity(hinge_raw, "axis_azimuth", "angle", "hinge", unit_inputs),
            axis_elevation_rad=_quantity(hinge_raw, "axis_elevation", "angle", "hinge", unit_inputs),
            stowed_angle_rad=_quantity(hinge_raw, "stowed_angle", "angle", "hinge", unit_inputs),
            deployed_angle_rad=_quantity(hinge_raw, "deployed_angle", "angle", "hinge", unit_inputs),
            stop_angle_rad=_quantity(hinge_raw, "stop_angle", "angle", "hinge", unit_inputs),
        )

    motor_raw = _mapping(raw, "motor", required=False)
    motor = None
    if motor_raw:
        motor = MotorModel(
            id=str(_required(motor_raw, "id", "motor")),
            kv_rad_s_per_v=_quantity(motor_raw, "kv", "angular_speed_per_voltage", "motor", unit_inputs),
            resistance_ohm=_quantity(motor_raw, "resistance", "resistance", "motor", unit_inputs),
            no_load_current_a=_quantity(motor_raw, "no_load_current", "current", "motor", unit_inputs),
            max_current_a=_quantity(motor_raw, "max_current", "current", "motor", unit_inputs),
            max_power_w=(
                _quantity(motor_raw, "max_power", "power", "motor", unit_inputs)
                if "max_power" in motor_raw
                else None
            ),
        )

    material_raw = _mapping(raw, "material", required=False)
    material = None
    if material_raw:
        material = MaterialModel(
            id=str(_required(material_raw, "id", "material")),
            density_kg_m3=_quantity(material_raw, "density", "density", "material", unit_inputs),
            allowable_stress_pa=(
                _quantity(material_raw, "allowable_stress", "stress", "material", unit_inputs)
                if "allowable_stress" in material_raw
                else None
            ),
            elastic_modulus_pa=(
                _quantity(material_raw, "elastic_modulus", "stress", "material", unit_inputs)
                if "elastic_modulus" in material_raw
                else None
            ),
            metadata=dict(_mapping(material_raw, "metadata", required=False)),
        )

    manufacturing_raw = _mapping(raw, "manufacturing", required=False)
    manufacturing = None
    if manufacturing_raw:
        manufacturing = ManufacturingModel(
            process=str(_required(manufacturing_raw, "process", "manufacturing")),
            min_wall_thickness_m=_quantity(manufacturing_raw, "min_wall_thickness", "length", "manufacturing", unit_inputs),
            min_trailing_edge_thickness_m=_quantity(manufacturing_raw, "min_trailing_edge_thickness", "length", "manufacturing", unit_inputs),
            build_orientation=str(_required(manufacturing_raw, "build_orientation", "manufacturing")),
            metadata=dict(_mapping(manufacturing_raw, "metadata", required=False)),
        )

    validation_records = tuple(
        ValidationRecord(
            id=str(_required(row, "id", f"validation_records[{index}]")),
            metric=str(_required(row, "metric", f"validation_records[{index}]")),
            dimension=str(_required(row, "dimension", f"validation_records[{index}]")),
            observed_si=_quantity(row, "observed", str(row["dimension"]), f"validation_records[{index}]", unit_inputs),
            source=str(_required(row, "source", f"validation_records[{index}]")),
            predicted_si=(
                _quantity(row, "predicted", str(row["dimension"]), f"validation_records[{index}]", unit_inputs)
                if "predicted" in row
                else None
            ),
            uncertainty_si=(
                _quantity(row, "uncertainty", str(row["dimension"]), f"validation_records[{index}]", unit_inputs)
                if "uncertainty" in row
                else None
            ),
            sign_convention=str(row.get("sign_convention", "")),
            metadata=dict(_mapping(row, "metadata", required=False)),
        )
        for index, row in enumerate(_tables(raw, "validation_records", required=False))
    )

    metadata = dict(_mapping(raw, "metadata", required=False))
    metadata.update(
        {
            "schema_version": schema_version,
            "source_file": str(config_path.resolve()),
            "canonical_unit_system": "SI",
            "input_units": unit_inputs,
        }
    )
    return PropellerDesign(
        id=str(_required(design_raw, "id", "design")),
        description=str(design_raw.get("description", "")),
        blade=blade,
        airfoils=airfoils,
        operating_conditions=conditions,
        hinge=hinge,
        motor=motor,
        material=material,
        manufacturing=manufacturing,
        validation_records=validation_records,
        metadata=metadata,
    )
