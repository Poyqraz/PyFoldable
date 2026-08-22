"""Strict local import of APC PE0 propeller geometry files.

APC website terms do not authorize redistribution of downloaded geometry. This
module therefore parses caller-supplied bytes and records source identity; it does
not vendor or silently download APC material.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from datetime import date, datetime

from .models import BladeGeometry, BladeStation


INCH_TO_M = 0.0254


class APCPE0Error(ValueError):
    """Raised when an APC PE0 file is malformed or fails identity checks."""


@dataclass(frozen=True)
class APCPE0Station:
    station_m: float
    chord_m: float
    thickness_ratio: float
    twist_rad: float


@dataclass(frozen=True)
class APCPE0AirfoilTransition:
    station_m: float
    airfoil_id: str


@dataclass(frozen=True)
class APCPE0Geometry:
    """Parsed geometry plus source/version provenance."""

    title: str
    version: str
    simulation_date: date
    radius_m: float
    hub_radius_m: float
    hub_transition_m: float
    blade_count: int
    stations: tuple[APCPE0Station, ...]
    airfoil_transitions: tuple[APCPE0AirfoilTransition, ...]
    source_url: str
    source_sha256: str

    def blade(self, *, airfoil_id: str) -> BladeGeometry:
        """Build the aerodynamic span without inventing geometry inside the hub."""
        selected = tuple(
            station
            for station in self.stations
            if station.station_m + 1.0e-12 >= self.hub_transition_m
            and station.station_m <= self.radius_m
            and station.chord_m > 0.0
        )
        if len(selected) < 2:
            raise APCPE0Error("PE0 geometry has fewer than two aerodynamic stations.")
        return BladeGeometry(
            diameter_m=2.0 * self.radius_m,
            hub_radius_m=self.hub_radius_m,
            blade_count=self.blade_count,
            stations=tuple(
                BladeStation(
                    r_over_R=station.station_m / self.radius_m,
                    chord_m=station.chord_m,
                    twist_rad=station.twist_rad,
                    airfoil_id=airfoil_id,
                )
                for station in selected
            ),
        )


_FLOAT_ROW = re.compile(r"^\s*[-+0-9]")
_AIRFOIL = re.compile(
    r"^\s*AIRFOIL\d+:\s*([0-9.]+)\s*,\s*(\S+)", re.IGNORECASE
)


def parse_apc_pe0(
    raw: bytes,
    *,
    source_url: str,
    expected_sha256: str | None = None,
) -> APCPE0Geometry:
    """Parse caller-supplied PE0 bytes and optionally enforce a pinned digest."""
    if not isinstance(raw, bytes):
        raise TypeError("raw must be bytes.")
    if not source_url:
        raise APCPE0Error("source_url must not be empty.")
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and digest.lower() != expected_sha256.lower():
        raise APCPE0Error(
            f"PE0 SHA-256 mismatch: observed {digest}, expected {expected_sha256}."
        )
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise APCPE0Error("PE0 input is not valid UTF-8 text.") from exc
    lines = text.splitlines()
    if not lines:
        raise APCPE0Error("PE0 input is empty.")
    version = next((line.strip() for line in lines if line.strip().startswith("v")), "")
    date_match = next(
        (
            re.search(r"Simulation Date:\s*(\d{2}/\d{2}/\d{4})", line)
            for line in lines
            if "Simulation Date:" in line
        ),
        None,
    )
    if not version or date_match is None:
        raise APCPE0Error("PE0 version or simulation date is missing.")

    values: dict[str, float | int] = {}
    labels = {
        "RADIUS": "radius",
        "HUBRAD": "hub",
        "HUBTRA": "transition",
        "BLADES": "blades",
    }
    for line in lines:
        for label, key in labels.items():
            match = re.match(rf"^\s*{label}:\s*([0-9.]+)", line)
            if match:
                values[key] = (
                    int(float(match.group(1)))
                    if key == "blades"
                    else float(match.group(1))
                )

    stations: list[APCPE0Station] = []
    for line in lines:
        if not _FLOAT_ROW.match(line):
            continue
        parts = line.split()
        if len(parts) != 14:
            continue
        try:
            row = tuple(float(value) for value in parts)
        except ValueError:
            continue
        stations.append(
            APCPE0Station(
                station_m=row[0] * INCH_TO_M,
                chord_m=row[1] * INCH_TO_M,
                thickness_ratio=row[7],
                twist_rad=math.radians(row[8]),
            )
        )
    transitions = tuple(
        APCPE0AirfoilTransition(float(match.group(1)) * INCH_TO_M, match.group(2))
        for line in lines
        if (match := _AIRFOIL.match(line))
    )
    if set(values) != {"radius", "hub", "transition", "blades"}:
        raise APCPE0Error("PE0 radius, hub, transition, or blade count is missing.")
    radius = float(values["radius"])
    hub = float(values["hub"])
    transition = float(values["transition"])
    blades = int(values["blades"])
    if not 0.0 < hub <= transition < radius or blades < 1:
        raise APCPE0Error("PE0 hub/radius dimensions or blade count are invalid.")
    if len(stations) < 2 or any(
        upper.station_m <= lower.station_m
        for lower, upper in zip(stations, stations[1:])
    ):
        raise APCPE0Error("PE0 stations must be present and strictly increasing.")
    if any(
        not all(
            math.isfinite(value)
            for value in (
                item.station_m,
                item.chord_m,
                item.thickness_ratio,
                item.twist_rad,
            )
        )
        or item.station_m < 0.0
        or item.chord_m < 0.0
        or item.thickness_ratio <= 0.0
        for item in stations
    ):
        raise APCPE0Error("PE0 station dimensions must be finite and physical.")
    if not transitions:
        raise APCPE0Error("PE0 airfoil transition data is missing.")
    if any(
        item.station_m < 0.0 or item.station_m > radius * INCH_TO_M
        for item in transitions
    ):
        raise APCPE0Error("PE0 airfoil transition lies outside the propeller radius.")
    return APCPE0Geometry(
        title=lines[0].strip(),
        version=version,
        simulation_date=datetime.strptime(date_match.group(1), "%m/%d/%Y").date(),
        radius_m=radius * INCH_TO_M,
        hub_radius_m=hub * INCH_TO_M,
        hub_transition_m=transition * INCH_TO_M,
        blade_count=blades,
        stations=tuple(stations),
        airfoil_transitions=transitions,
        source_url=source_url,
        source_sha256=digest,
    )
