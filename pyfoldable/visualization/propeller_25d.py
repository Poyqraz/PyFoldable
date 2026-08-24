"""Deterministic 2.5D propeller geometry preview primitives.

The mesh is a visualization aid.  It does not replace CAD, aerodynamic analysis,
manufacturing geometry, or a structurally valid solid model.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Sequence


PREVIEW_QUALIFICATION = "geometry_preview_not_cad_or_physical_result"
_NACA4_PATTERN = re.compile(r"^NACA\s*([0-9]{4})$", re.IGNORECASE)


def _finite(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number.")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite.")
    return result


@dataclass(frozen=True)
class PreviewBladeStation:
    """One normalized span station used only for preview surface generation."""

    r_over_R: float
    chord_m: float
    twist_deg: float

    def __post_init__(self) -> None:
        r_over_r = _finite("r_over_R", self.r_over_R)
        chord = _finite("chord_m", self.chord_m)
        _finite("twist_deg", self.twist_deg)
        if not 0.0 < r_over_r <= 1.0:
            raise ValueError("r_over_R must lie in (0, 1].")
        if chord <= 0.0:
            raise ValueError("chord_m must be greater than zero.")


@dataclass(frozen=True)
class PropellerPreviewSpec:
    """Validated, SI-bound inputs for one interactive geometry preview."""

    diameter_m: float
    hub_radius_m: float
    blade_count: int
    hinge_radius_m: float
    fold_angle_deg: float
    airfoil_id: str = "NACA2412"
    chord_scale: float = 1.0
    twist_scale: float = 1.0
    section_point_count: int = 25

    def __post_init__(self) -> None:
        diameter = _finite("diameter_m", self.diameter_m)
        hub = _finite("hub_radius_m", self.hub_radius_m)
        hinge = _finite("hinge_radius_m", self.hinge_radius_m)
        fold_angle = _finite("fold_angle_deg", self.fold_angle_deg)
        chord_scale = _finite("chord_scale", self.chord_scale)
        twist_scale = _finite("twist_scale", self.twist_scale)
        if diameter <= 0.0:
            raise ValueError("diameter_m must be greater than zero.")
        radius = diameter / 2.0
        if not 0.0 < hub < radius:
            raise ValueError("hub_radius_m must lie between zero and the propeller radius.")
        if isinstance(self.blade_count, bool) or not isinstance(self.blade_count, int):
            raise TypeError("blade_count must be an integer.")
        if not 1 <= self.blade_count <= 8:
            raise ValueError("blade_count must lie between 1 and 8.")
        if not hub < hinge < radius:
            raise ValueError(
                "hinge_radius_m must lie between hub_radius_m and the propeller radius."
            )
        if not -180.0 <= fold_angle <= 0.0:
            raise ValueError("fold_angle_deg must lie between -180 and 0 degrees.")
        if chord_scale <= 0.0:
            raise ValueError("chord_scale must be greater than zero.")
        if twist_scale < 0.0:
            raise ValueError("twist_scale must not be negative.")
        if (
            isinstance(self.section_point_count, bool)
            or not isinstance(self.section_point_count, int)
            or self.section_point_count < 9
        ):
            raise ValueError("section_point_count must be an integer of at least 9.")
        if not isinstance(self.airfoil_id, str):
            raise TypeError("airfoil_id must be a string.")
        if _NACA4_PATTERN.fullmatch(self.airfoil_id.strip()) is None:
            raise ValueError("airfoil_id must identify an analytic NACA 4-digit section.")


@dataclass(frozen=True)
class PropellerPreviewMesh:
    """Renderer-neutral triangular blade mesh with preview provenance."""

    vertices: tuple[tuple[float, float, float], ...]
    faces: tuple[tuple[int, int, int], ...]
    blade_count: int
    station_count: int
    section_point_count: int
    hinge_root_station_index: int
    hinge_tip_station_index: int
    hinge_radius_m: float
    maximum_radius_m: float
    effective_radius_m: float
    mesh_envelope_radius_m: float
    qualification: str = PREVIEW_QUALIFICATION


def naca4_section_loop(
    airfoil_id: str,
    *,
    point_count: int = 25,
) -> tuple[tuple[float, float], ...]:
    """Return a cosine-spaced, closed-boundary NACA 4-digit section loop."""
    if not isinstance(airfoil_id, str):
        raise TypeError("airfoil_id must be a string.")
    match = _NACA4_PATTERN.fullmatch(airfoil_id.strip())
    if match is None:
        raise ValueError("airfoil_id must identify an analytic NACA 4-digit section.")
    if isinstance(point_count, bool) or not isinstance(point_count, int) or point_count < 9:
        raise ValueError("point_count must be an integer of at least 9.")

    digits = match.group(1)
    maximum_camber = int(digits[0]) / 100.0
    camber_position = int(digits[1]) / 10.0
    thickness = int(digits[2:]) / 100.0
    if thickness <= 0.0:
        raise ValueError("NACA 4-digit thickness must be greater than zero.")
    if maximum_camber > 0.0 and not 0.0 < camber_position < 1.0:
        raise ValueError("Cambered NACA 4-digit sections require a valid camber position.")

    upper: list[tuple[float, float]] = []
    lower: list[tuple[float, float]] = []
    for index in range(point_count):
        beta = math.pi * index / (point_count - 1)
        x_coord = 0.5 * (1.0 - math.cos(beta))
        thickness_y = 5.0 * thickness * (
            0.2969 * math.sqrt(x_coord)
            - 0.1260 * x_coord
            - 0.3516 * x_coord**2
            + 0.2843 * x_coord**3
            - 0.1036 * x_coord**4
        )
        if maximum_camber == 0.0:
            camber_y = 0.0
            slope = 0.0
        elif x_coord < camber_position:
            camber_y = maximum_camber / camber_position**2 * (
                2.0 * camber_position * x_coord - x_coord**2
            )
            slope = 2.0 * maximum_camber / camber_position**2 * (
                camber_position - x_coord
            )
        else:
            camber_y = maximum_camber / (1.0 - camber_position) ** 2 * (
                (1.0 - 2.0 * camber_position)
                + 2.0 * camber_position * x_coord
                - x_coord**2
            )
            slope = 2.0 * maximum_camber / (1.0 - camber_position) ** 2 * (
                camber_position - x_coord
            )
        angle = math.atan(slope)
        upper.append(
            (
                x_coord - thickness_y * math.sin(angle),
                camber_y + thickness_y * math.cos(angle),
            )
        )
        lower.append(
            (
                x_coord + thickness_y * math.sin(angle),
                camber_y - thickness_y * math.cos(angle),
            )
        )

    # One shared leading edge and one shared trailing edge; wrap closes the loop.
    return tuple(reversed(upper)) + tuple(lower[1:-1])


def _split_hinge_station(
    stations: tuple[PreviewBladeStation, ...],
    *,
    hinge_r_over_r: float,
) -> tuple[tuple[PreviewBladeStation, ...], int, int]:
    """Return root/tip hinge copies so the outboard surface remains rigid."""
    tolerance = 1e-12
    hinge_station = next(
        (
            station
            for station in stations
            if abs(station.r_over_R - hinge_r_over_r) <= tolerance
        ),
        None,
    )
    if hinge_station is None:
        for left, right in zip(stations, stations[1:]):
            if left.r_over_R < hinge_r_over_r < right.r_over_R:
                fraction = (hinge_r_over_r - left.r_over_R) / (
                    right.r_over_R - left.r_over_R
                )
                hinge_station = PreviewBladeStation(
                    r_over_R=hinge_r_over_r,
                    chord_m=left.chord_m
                    + fraction * (right.chord_m - left.chord_m),
                    twist_deg=left.twist_deg
                    + fraction * (right.twist_deg - left.twist_deg),
                )
                break
    if hinge_station is None:  # guarded by the station-span check in the builder
        raise ValueError("Hinge radius does not intersect the blade-station span.")

    inboard = [
        station for station in stations if station.r_over_R < hinge_r_over_r - tolerance
    ]
    outboard = [
        station for station in stations if station.r_over_R > hinge_r_over_r + tolerance
    ]
    root_index = len(inboard)
    tip_index = root_index + 1
    output = inboard + [hinge_station, hinge_station] + outboard
    return tuple(output), root_index, tip_index


def _validate_stations(
    stations: Sequence[PreviewBladeStation],
) -> tuple[PreviewBladeStation, ...]:
    normalized = tuple(stations)
    if len(normalized) < 2:
        raise ValueError("At least two blade stations are required.")
    if not all(isinstance(station, PreviewBladeStation) for station in normalized):
        raise TypeError("stations must contain PreviewBladeStation values.")
    if any(
        right.r_over_R <= left.r_over_R
        for left, right in zip(normalized, normalized[1:])
    ):
        raise ValueError("Blade stations must be strictly increasing in r_over_R.")
    return normalized


def build_propeller_preview_mesh(
    spec: PropellerPreviewSpec,
    stations: Sequence[PreviewBladeStation],
) -> PropellerPreviewMesh:
    """Build a deterministic multi-blade surface mesh for interactive rendering."""
    if not isinstance(spec, PropellerPreviewSpec):
        raise TypeError("spec must be a PropellerPreviewSpec.")
    source_stations = _validate_stations(stations)
    radius = spec.diameter_m / 2.0
    first_station_radius = source_stations[0].r_over_R * radius
    last_station_radius = source_stations[-1].r_over_R * radius
    if not (
        spec.hub_radius_m <= first_station_radius
        and first_station_radius < spec.hinge_radius_m < last_station_radius
    ):
        raise ValueError(
            "Hub and hinge radii must remain inside the defined blade-station span."
        )
    hinge_r_over_r = spec.hinge_radius_m / radius
    mesh_stations, hinge_root_index, hinge_tip_index = _split_hinge_station(
        source_stations,
        hinge_r_over_r=hinge_r_over_r,
    )
    section = naca4_section_loop(
        spec.airfoil_id,
        point_count=spec.section_point_count,
    )
    perimeter_count = len(section)
    fold_angle = math.radians(spec.fold_angle_deg)

    base_vertices: list[tuple[float, float, float]] = []
    for station_index, station in enumerate(mesh_stations):
        radial = station.r_over_R * radius
        chord = station.chord_m * spec.chord_scale
        twist = math.radians(station.twist_deg * spec.twist_scale)
        for chord_fraction, thickness_fraction in section:
            chord_axis = (chord_fraction - 0.25) * chord
            thickness_axis = thickness_fraction * chord
            local_y = chord_axis * math.cos(twist) - thickness_axis * math.sin(twist)
            local_z = chord_axis * math.sin(twist) + thickness_axis * math.cos(twist)
            local_x = radial
            if station_index >= hinge_tip_index:
                delta_x = radial - spec.hinge_radius_m
                local_x = (
                    spec.hinge_radius_m
                    + delta_x * math.cos(fold_angle)
                    - local_y * math.sin(fold_angle)
                )
                local_y = delta_x * math.sin(fold_angle) + local_y * math.cos(
                    fold_angle
                )
            base_vertices.append((local_x, local_y, local_z))

    base_faces: list[tuple[int, int, int]] = []
    for station_index in range(len(mesh_stations) - 1):
        if station_index == hinge_root_index:
            continue
        current = station_index * perimeter_count
        following = (station_index + 1) * perimeter_count
        for section_index in range(perimeter_count):
            next_section = (section_index + 1) % perimeter_count
            a = current + section_index
            b = following + section_index
            c = following + next_section
            d = current + next_section
            base_faces.extend(((a, b, c), (a, c, d)))

    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    vertices_per_blade = len(base_vertices)
    for blade_index in range(spec.blade_count):
        azimuth = 2.0 * math.pi * blade_index / spec.blade_count
        cosine = math.cos(azimuth)
        sine = math.sin(azimuth)
        offset = len(vertices)
        vertices.extend(
            (
                x_coord * cosine - y_coord * sine,
                x_coord * sine + y_coord * cosine,
                z_coord,
            )
            for x_coord, y_coord, z_coord in base_vertices
        )
        faces.extend(
            (a + offset, b + offset, c + offset) for a, b, c in base_faces
        )
        assert len(vertices) == (blade_index + 1) * vertices_per_blade

    projected_tip_radius = spec.hinge_radius_m + (
        radius - spec.hinge_radius_m
    ) * math.cos(abs(fold_angle))
    radial_envelope_radius = max(spec.hinge_radius_m, projected_tip_radius)
    mesh_envelope_radius = max(
        math.hypot(x_coord, y_coord) for x_coord, y_coord, _ in vertices
    )
    return PropellerPreviewMesh(
        vertices=tuple(vertices),
        faces=tuple(faces),
        blade_count=spec.blade_count,
        station_count=len(mesh_stations),
        section_point_count=spec.section_point_count,
        hinge_root_station_index=hinge_root_index,
        hinge_tip_station_index=hinge_tip_index,
        hinge_radius_m=spec.hinge_radius_m,
        maximum_radius_m=radius,
        effective_radius_m=radial_envelope_radius,
        mesh_envelope_radius_m=mesh_envelope_radius,
    )
