"""Validated, downloadable design drafts for the UI-03B workflow.

The canonical design is always read-only.  Preview controls are normalized to SI,
applied to a separate strict model, serialized with explicit units, and loaded once
more through the canonical parser before the artifact is returned.
"""

from __future__ import annotations

import hashlib
import json
import math
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from pyfoldable.core.config import load_design_config
from pyfoldable.core.models import (
    AirfoilDefinition,
    BladeGeometry,
    BladeStation,
    PropellerDesign,
)
from pyfoldable.core.units import QuantityInput, normalize_quantity


@dataclass(frozen=True)
class DesignDraftInputs:
    """Editable fields accepted from the geometry and condition preview."""

    diameter: QuantityInput
    hub_radius: QuantityInput
    hinge_radius: QuantityInput
    blade_count: int
    airfoil_id: str
    chord_scale: float
    twist_scale: float
    preview_fold_angle: QuantityInput
    angular_speed: QuantityInput
    forward_speed: QuantityInput
    air_density: QuantityInput
    dynamic_viscosity: QuantityInput
    temperature: QuantityInput
    pressure: QuantityInput


@dataclass(frozen=True)
class DraftUnitSelection:
    """Explicit representation units used in the downloadable TOML."""

    length: str = "mm"
    angle: str = "deg"
    angular_speed: str = "rpm"
    speed: str = "m/s"
    temperature: str = "K"
    pressure: str = "Pa"

    def __post_init__(self) -> None:
        supported = {
            "length": {"m", "mm", "cm", "in"},
            "angle": {"rad", "deg"},
            "angular_speed": {"rad/s", "rpm"},
            "speed": {"m/s", "km/h"},
            "temperature": {"K", "degC"},
            "pressure": {"Pa", "kPa", "MPa"},
        }
        for field, choices in supported.items():
            value = getattr(self, field)
            if value not in choices:
                raise ValueError(
                    f"Unsupported draft {field} unit {value!r}; expected one of "
                    f"{sorted(choices)}."
                )


@dataclass(frozen=True)
class DesignDraftArtifact:
    """A validated draft that can be downloaded but never overwrites its source."""

    filename: str
    toml: str
    source_sha256: str
    draft_sha256: str


_RUNTIME_METADATA = {
    "schema_version",
    "source_file",
    "canonical_unit_system",
    "input_units",
}


def _normalized(value: QuantityInput, dimension: str, field: str) -> float:
    if isinstance(value, str):
        try:
            float(value.strip())
        except ValueError:
            pass
        else:
            raise ValueError(f"{field} requires an explicit unit; received {value!r}.")
    return normalize_quantity(value, dimension, field=field).si_value


def _validate_scalar(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric.")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite.")
    return number


def _build_model(source: PropellerDesign, inputs: DesignDraftInputs) -> PropellerDesign:
    if isinstance(inputs.blade_count, bool) or not isinstance(inputs.blade_count, int):
        raise ValueError("blade_count must be an integer.")
    if inputs.blade_count < 1:
        raise ValueError("blade_count must be at least one.")
    airfoil_id = inputs.airfoil_id.strip()
    if not airfoil_id:
        raise ValueError("airfoil_id must not be empty.")
    chord_scale = _validate_scalar("chord_scale", inputs.chord_scale)
    twist_scale = _validate_scalar("twist_scale", inputs.twist_scale)
    if chord_scale <= 0.0:
        raise ValueError("chord_scale must be greater than zero.")
    if twist_scale < 0.0:
        raise ValueError("twist_scale must be non-negative.")

    diameter_m = _normalized(inputs.diameter, "length", "draft.diameter")
    hub_radius_m = _normalized(inputs.hub_radius, "length", "draft.hub_radius")
    hinge_radius_m = _normalized(inputs.hinge_radius, "length", "draft.hinge_radius")
    preview_fold_angle_rad = _normalized(
        inputs.preview_fold_angle,
        "angle",
        "draft.preview_fold_angle",
    )
    if source.hinge is None:
        raise ValueError("The source design must define hinge geometry.")
    if not (
        source.hinge.stowed_angle_rad
        <= preview_fold_angle_rad
        <= source.hinge.deployed_angle_rad
    ):
        raise ValueError("preview_fold_angle must remain inside the hinge angle range.")
    if not source.operating_conditions:
        raise ValueError("The source design must define an operating condition.")

    diameter_scale = diameter_m / source.blade.diameter_m
    blade = BladeGeometry(
        diameter_m=diameter_m,
        hub_radius_m=hub_radius_m,
        blade_count=inputs.blade_count,
        stations=tuple(
            BladeStation(
                r_over_R=station.r_over_R,
                chord_m=station.chord_m * diameter_scale * chord_scale,
                twist_rad=station.twist_rad * twist_scale,
                airfoil_id=airfoil_id,
            )
            for station in source.blade.stations
        ),
    )
    hinge = replace(source.hinge, radius_m=hinge_radius_m)
    condition = replace(
        source.operating_conditions[0],
        angular_speed_rad_s=_normalized(
            inputs.angular_speed,
            "angular_speed",
            "draft.angular_speed",
        ),
        forward_speed_m_s=_normalized(inputs.forward_speed, "speed", "draft.forward_speed"),
        air_density_kg_m3=_normalized(inputs.air_density, "density", "draft.air_density"),
        dynamic_viscosity_pa_s=_normalized(
            inputs.dynamic_viscosity,
            "dynamic_viscosity",
            "draft.dynamic_viscosity",
        ),
        temperature_k=_normalized(inputs.temperature, "temperature", "draft.temperature"),
        pressure_pa=_normalized(inputs.pressure, "pressure", "draft.pressure"),
    )

    airfoils = list(source.airfoils)
    if airfoil_id not in {airfoil.id for airfoil in airfoils}:
        is_naca_4_digit = (
            airfoil_id.startswith("NACA")
            and len(airfoil_id) == 8
            and airfoil_id[4:].isdigit()
        )
        if not is_naca_4_digit:
            raise ValueError(
                "An airfoil absent from the source must be an analytic NACA 4-digit id."
            )
        airfoils.append(AirfoilDefinition(airfoil_id, "analytic_naca_4_digit"))

    metadata = {
        key: value
        for key, value in source.metadata.items()
        if key not in _RUNTIME_METADATA
    }
    metadata.update(
        {
            "artifact_class": "unqualified_design_draft",
            "source_design_id": source.id,
            "preview_fold_angle": f"{math.degrees(preview_fold_angle_rad):.17g} deg",
            "preview_fold_angle_semantics": (
                "UI preview pose; not a hinge stop or a physical result"
            ),
        }
    )
    return replace(
        source,
        id=f"{source.id}_DRAFT",
        description=f"Unqualified UI draft derived from {source.id}",
        blade=blade,
        airfoils=tuple(airfoils),
        operating_conditions=(condition, *source.operating_conditions[1:]),
        hinge=hinge,
        metadata=metadata,
    )


def _number(value: float) -> str:
    if not math.isfinite(value):
        raise ValueError("Draft output cannot contain non-finite values.")
    return repr(float(value))


def _quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _quantity(value_si: float, dimension: str, units: DraftUnitSelection) -> str:
    unit = {
        "length": units.length,
        "angle": units.angle,
        "angular_speed": units.angular_speed,
        "angular_speed_per_voltage": (
            "rpm/V" if units.angular_speed == "rpm" else "rad/s/V"
        ),
        "speed": units.speed,
        "temperature": units.temperature,
        "pressure": units.pressure,
        "stress": units.pressure,
        "dimensionless": "1",
        "area": "m^2",
        "mass": "kg",
        "density": "kg/m^3",
        "dynamic_viscosity": "Pa*s",
        "force": "N",
        "torque": "N*m",
        "power": "W",
        "time": "s",
        "current": "A",
        "voltage": "V",
        "resistance": "ohm",
    }[dimension]
    factor = {
        "m": 1.0,
        "mm": 1.0e-3,
        "cm": 1.0e-2,
        "in": 0.0254,
        "rad": 1.0,
        "deg": math.pi / 180.0,
        "rad/s": 1.0,
        "rpm": 2.0 * math.pi / 60.0,
        "rad/s/V": 1.0,
        "rpm/V": 2.0 * math.pi / 60.0,
        "m/s": 1.0,
        "km/h": 1.0 / 3.6,
        "K": 1.0,
        "degC": 1.0,
        "Pa": 1.0,
        "kPa": 1.0e3,
        "MPa": 1.0e6,
        "1": 1.0,
        "m^2": 1.0,
        "kg": 1.0,
        "kg/m^3": 1.0,
        "Pa*s": 1.0,
        "N": 1.0,
        "N*m": 1.0,
        "W": 1.0,
        "s": 1.0,
        "A": 1.0,
        "V": 1.0,
        "ohm": 1.0,
    }[unit]
    if unit == "km/h":
        output_value = value_si * 3.6
    elif unit == "rpm":
        output_value = value_si * 60.0 / (2.0 * math.pi)
    elif unit == "rpm/V":
        output_value = value_si * 60.0 / (2.0 * math.pi)
    elif unit == "deg":
        output_value = math.degrees(value_si)
    else:
        output_value = value_si / factor
    if unit == "degC":
        output_value = value_si - 273.15
    return f"{_number(output_value)} {unit}"


def _metadata_lines(metadata: Mapping[str, Any]) -> list[str]:
    lines: list[str] = []
    for key in sorted(metadata):
        value = metadata[key]
        if isinstance(value, bool):
            rendered = "true" if value else "false"
        elif isinstance(value, str):
            rendered = _quoted(value)
        elif isinstance(value, int) and not isinstance(value, bool):
            rendered = str(value)
        elif isinstance(value, float):
            rendered = _number(value)
        else:
            raise ValueError(
                f"Draft metadata {key!r} must be a TOML scalar, got {type(value).__name__}."
            )
        lines.append(f"{key} = {rendered}")
    return lines


def _serialize(design: PropellerDesign, units: DraftUnitSelection) -> str:
    lines = [
        "schema_version = 1",
        "",
        "[design]",
        f"id = {_quoted(design.id)}",
        f"description = {_quoted(design.description)}",
        "",
        "[blade]",
        f"diameter = {_quoted(_quantity(design.blade.diameter_m, 'length', units))}",
        f"hub_radius = {_quoted(_quantity(design.blade.hub_radius_m, 'length', units))}",
        f"blade_count = {design.blade.blade_count}",
    ]
    for station in design.blade.stations:
        lines.extend(
            [
                "",
                "[[blade.stations]]",
                f"r_over_R = {_number(station.r_over_R)}",
                f"chord = {_quoted(_quantity(station.chord_m, 'length', units))}",
                f"twist = {_quoted(_quantity(station.twist_rad, 'angle', units))}",
                f"airfoil = {_quoted(station.airfoil_id)}",
            ]
        )
    for airfoil in design.airfoils:
        lines.extend(
            [
                "",
                "[[airfoils]]",
                f"id = {_quoted(airfoil.id)}",
                f"source = {_quoted(airfoil.source)}",
            ]
        )
        if airfoil.metadata:
            raise ValueError("Draft serialization does not support nested airfoil metadata.")
    for condition in design.operating_conditions:
        lines.extend(
            [
                "",
                "[[operating_conditions]]",
                f"id = {_quoted(condition.id)}",
                "angular_speed = "
                + _quoted(_quantity(condition.angular_speed_rad_s, "angular_speed", units)),
                "forward_speed = "
                + _quoted(_quantity(condition.forward_speed_m_s, "speed", units)),
                "air_density = "
                + _quoted(_quantity(condition.air_density_kg_m3, "density", units)),
                "dynamic_viscosity = "
                + _quoted(
                    _quantity(
                        condition.dynamic_viscosity_pa_s,
                        "dynamic_viscosity",
                        units,
                    )
                ),
                "temperature = "
                + _quoted(_quantity(condition.temperature_k, "temperature", units)),
                f"pressure = {_quoted(_quantity(condition.pressure_pa, 'pressure', units))}",
            ]
        )
    if design.hinge is not None:
        hinge = design.hinge
        lines.extend(
            [
                "",
                "[hinge]",
                f"radius = {_quoted(_quantity(hinge.radius_m, 'length', units))}",
                f"axial_offset = {_quoted(_quantity(hinge.axial_offset_m, 'length', units))}",
                "tangential_offset = "
                + _quoted(_quantity(hinge.tangential_offset_m, "length", units)),
                f"axis_azimuth = {_quoted(_quantity(hinge.axis_azimuth_rad, 'angle', units))}",
                f"axis_elevation = {_quoted(_quantity(hinge.axis_elevation_rad, 'angle', units))}",
                f"stowed_angle = {_quoted(_quantity(hinge.stowed_angle_rad, 'angle', units))}",
                f"deployed_angle = {_quoted(_quantity(hinge.deployed_angle_rad, 'angle', units))}",
                f"stop_angle = {_quoted(_quantity(hinge.stop_angle_rad, 'angle', units))}",
            ]
        )
    if design.motor is not None:
        motor = design.motor
        lines.extend(
            [
                "",
                "[motor]",
                f"id = {_quoted(motor.id)}",
                "kv = "
                + _quoted(
                    _quantity(motor.kv_rad_s_per_v, "angular_speed_per_voltage", units)
                ),
                f"resistance = {_quoted(_quantity(motor.resistance_ohm, 'resistance', units))}",
                "no_load_current = "
                + _quoted(_quantity(motor.no_load_current_a, "current", units)),
                f"max_current = {_quoted(_quantity(motor.max_current_a, 'current', units))}",
            ]
        )
        if motor.max_power_w is not None:
            lines.append(f"max_power = {_quoted(_quantity(motor.max_power_w, 'power', units))}")
    if design.material is not None:
        material = design.material
        lines.extend(
            [
                "",
                "[material]",
                f"id = {_quoted(material.id)}",
                f"density = {_quoted(_quantity(material.density_kg_m3, 'density', units))}",
            ]
        )
        if material.allowable_stress_pa is not None:
            lines.append(
                "allowable_stress = "
                + _quoted(_quantity(material.allowable_stress_pa, "stress", units))
            )
        if material.elastic_modulus_pa is not None:
            lines.append(
                "elastic_modulus = "
                + _quoted(_quantity(material.elastic_modulus_pa, "stress", units))
            )
        if material.metadata:
            lines.extend(["", "[material.metadata]", *_metadata_lines(material.metadata)])
    if design.manufacturing is not None:
        manufacturing = design.manufacturing
        lines.extend(
            [
                "",
                "[manufacturing]",
                f"process = {_quoted(manufacturing.process)}",
                "min_wall_thickness = "
                + _quoted(
                    _quantity(manufacturing.min_wall_thickness_m, "length", units)
                ),
                "min_trailing_edge_thickness = "
                + _quoted(
                    _quantity(
                        manufacturing.min_trailing_edge_thickness_m,
                        "length",
                        units,
                    )
                ),
                f"build_orientation = {_quoted(manufacturing.build_orientation)}",
            ]
        )
        if manufacturing.metadata:
            lines.extend(
                ["", "[manufacturing.metadata]", *_metadata_lines(manufacturing.metadata)]
            )
    for record in design.validation_records:
        lines.extend(
            [
                "",
                "[[validation_records]]",
                f"id = {_quoted(record.id)}",
                f"metric = {_quoted(record.metric)}",
                f"dimension = {_quoted(record.dimension)}",
                f"observed = {_quoted(_quantity(record.observed_si, record.dimension, units))}",
                f"source = {_quoted(record.source)}",
            ]
        )
        if record.predicted_si is not None:
            lines.append(
                f"predicted = {_quoted(_quantity(record.predicted_si, record.dimension, units))}"
            )
        if record.uncertainty_si is not None:
            lines.append(
                "uncertainty = "
                + _quoted(_quantity(record.uncertainty_si, record.dimension, units))
            )
        if record.sign_convention:
            lines.append(f"sign_convention = {_quoted(record.sign_convention)}")
        if record.metadata:
            raise ValueError("Draft serialization does not support nested validation metadata.")
    lines.extend(["", "[metadata]", *_metadata_lines(design.metadata), ""])
    return "\n".join(lines)


def build_design_draft(
    source_path: str | Path,
    inputs: DesignDraftInputs,
    *,
    units: DraftUnitSelection | None = None,
) -> DesignDraftArtifact:
    """Build and round-trip a draft without writing beside or over its source."""
    path = Path(source_path).resolve()
    source_bytes = path.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    source = load_design_config(path)
    draft = _build_model(source, inputs)
    draft_metadata = dict(draft.metadata)
    draft_metadata["source_design_sha256"] = source_sha256
    draft = replace(draft, metadata=draft_metadata)
    toml = _serialize(draft, units or DraftUnitSelection())

    # The same strict public loader that consumes canonical designs must accept the
    # download.  A temporary file keeps this proof separate from the repository.
    with tempfile.TemporaryDirectory(prefix="pyfoldable-draft-") as directory:
        round_trip_path = Path(directory) / "draft.toml"
        round_trip_path.write_text(toml, encoding="utf-8")
        load_design_config(round_trip_path)

    if path.read_bytes() != source_bytes:
        raise RuntimeError("Canonical design changed while building its draft.")
    return DesignDraftArtifact(
        filename=f"{source.id}_DRAFT.toml",
        toml=toml,
        source_sha256=source_sha256,
        draft_sha256=hashlib.sha256(toml.encode("utf-8")).hexdigest(),
    )
