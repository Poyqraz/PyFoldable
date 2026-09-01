"""Airfoil coordinate readers and geometry validation.

The canonical coordinate order is the UIUC/Selig convention: upper-surface
trailing edge to leading edge, then lower-surface leading edge to trailing edge.
Coordinates are translated and scaled to unit chord before they enter the
solver-neutral :class:`AirfoilDefinition` model.
"""

from __future__ import annotations

import csv
import hashlib
import io
import math
import re
from bisect import bisect_right
from dataclasses import replace
from pathlib import Path
from typing import Literal, Sequence

from .models import AirfoilDefinition


AirfoilFileFormat = Literal["auto", "selig", "lednicer", "csv"]


class AirfoilGeometryError(ValueError):
    """Raised when an airfoil file or its geometry is invalid."""


def airfoil_coordinate_sha256(airfoil: AirfoilDefinition) -> str:
    """Hash exact coordinate content using the existing polar-provider format.

    This is distinct from source_sha256 (file bytes) and does not prove that a
    coordinate set represents a manufactured blade or a validated polar.
    """
    if not isinstance(airfoil, AirfoilDefinition) or not airfoil.coordinates:
        raise AirfoilGeometryError("Coordinate identity requires an airfoil geometry.")
    payload = "\n".join(f"{x:.17g},{y:.17g}" for x, y in airfoil.coordinates)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_airfoil_definition(airfoil: AirfoilDefinition) -> AirfoilDefinition:
    """Validate already canonical coordinates without resampling/renormalizing.

    Frozen models may still contain mutable metadata; return a fresh metadata
    snapshot. A claimed coordinate hash is checked rather than trusted.
    """
    if not isinstance(airfoil, AirfoilDefinition):
        raise AirfoilGeometryError("Expected an AirfoilDefinition.")
    if not 5 <= len(airfoil.coordinates) <= 2000:
        raise AirfoilGeometryError("Airfoil coordinates require 5 to 2000 points.")
    for point in airfoil.coordinates:
        if len(point) != 2 or any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) for value in point
        ):
            raise AirfoilGeometryError("Coordinates must be finite numeric pairs.")
    points = tuple((float(x), float(y)) for x, y in airfoil.coordinates)
    if min(x for x, _ in points) != 0.0 or max(x for x, _ in points) != 1.0:
        raise AirfoilGeometryError("Coordinates must already use normalized unit chord.")
    if tuple(_canonical_order(points)) != points:
        raise AirfoilGeometryError("Coordinates must use canonical upper-TE/LE/lower-TE order.")
    if abs(points[_leading_edge_index(points)][1]) > 1e-12:
        raise AirfoilGeometryError("Canonical leading-edge ordinate must be zero.")
    _reject_repeated_points(points)
    _reject_self_intersections(points)
    metrics = _geometry_metrics(points)
    result = replace(airfoil, coordinates=points)
    digest = airfoil_coordinate_sha256(result)
    if "airfoil_coordinate_sha256" in airfoil.metadata and airfoil.metadata["airfoil_coordinate_sha256"] != digest:
        raise AirfoilGeometryError("Airfoil coordinate SHA-256 does not match the geometry.")
    return replace(result, metadata={
        **airfoil.metadata, **metrics, "point_count": len(points),
        "airfoil_coordinate_sha256": digest,
    })


_NUMBER = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")
_POINT_TOLERANCE = 1.0e-10
_ORDER_TOLERANCE = 1.0e-7


def _clean_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.replace("\ufeff", "").replace("\x1a", "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            lines.append(line)
    return lines


def _numbers(line: str) -> tuple[float, ...]:
    tokens = _NUMBER.findall(line)
    if not tokens:
        return ()
    residue = _NUMBER.sub("", line)
    if residue.replace(",", "").replace(";", "").strip():
        return ()
    return tuple(float(token) for token in tokens)


def _is_count_row(values: Sequence[float]) -> bool:
    return (
        len(values) == 2
        and all(value >= 2.0 and float(value).is_integer() for value in values)
    )


def _point_rows(lines: Sequence[str], *, start: int) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for index, line in enumerate(lines[start:], start=start + 1):
        values = _numbers(line)
        if len(values) != 2:
            raise AirfoilGeometryError(
                f"Line {index} must contain exactly two numeric coordinates."
            )
        if not all(math.isfinite(value) for value in values):
            raise AirfoilGeometryError(f"Line {index} contains a non-finite coordinate.")
        points.append((values[0], values[1]))
    return points


def _parse_dat(
    text: str,
    requested_format: AirfoilFileFormat,
) -> tuple[str, str, list[tuple[float, float]]]:
    lines = _clean_lines(text)
    if not lines:
        raise AirfoilGeometryError("Airfoil coordinate file is empty.")

    first_values = _numbers(lines[0])
    name = ""
    start = 0
    if len(first_values) != 2:
        name = lines[0]
        start = 1
    if start >= len(lines):
        raise AirfoilGeometryError("Airfoil file does not contain coordinate rows.")

    possible_counts = _numbers(lines[start])
    detected = "lednicer" if _is_count_row(possible_counts) else "selig"
    file_format = detected if requested_format == "auto" else requested_format

    if file_format == "selig":
        return name, file_format, _point_rows(lines, start=start)
    if file_format != "lednicer":
        raise AirfoilGeometryError(f"Unsupported DAT format {file_format!r}.")
    if not _is_count_row(possible_counts):
        raise AirfoilGeometryError("Lednicer format requires upper/lower point counts.")

    upper_count, lower_count = (int(value) for value in possible_counts)
    points = _point_rows(lines, start=start + 1)
    expected = upper_count + lower_count
    if len(points) != expected:
        raise AirfoilGeometryError(
            f"Lednicer count row declares {expected} points, but {len(points)} were read."
        )
    upper = points[:upper_count]
    lower = points[upper_count:]
    return name, file_format, _combine_lednicer_surfaces(upper, lower)


def _parse_csv(text: str) -> tuple[str, str, list[tuple[float, float]]]:
    cleaned = "\n".join(_clean_lines(text))
    if not cleaned:
        raise AirfoilGeometryError("Airfoil CSV file is empty.")
    try:
        dialect = csv.Sniffer().sniff(cleaned[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(cleaned), dialect))
    if not rows:
        raise AirfoilGeometryError("Airfoil CSV file is empty.")

    header = [cell.strip().casefold() for cell in rows[0]]
    has_header = "x" in header and "y" in header
    if has_header:
        x_index = header.index("x")
        y_index = header.index("y")
        data_rows = rows[1:]
    else:
        x_index, y_index = 0, 1
        data_rows = rows

    points: list[tuple[float, float]] = []
    for row_number, row in enumerate(data_rows, start=2 if has_header else 1):
        if not row or all(not cell.strip() for cell in row):
            continue
        if max(x_index, y_index) >= len(row):
            raise AirfoilGeometryError(f"CSV row {row_number} is missing x or y.")
        try:
            point = (float(row[x_index]), float(row[y_index]))
        except ValueError as exc:
            raise AirfoilGeometryError(
                f"CSV row {row_number} contains a non-numeric coordinate."
            ) from exc
        if not all(math.isfinite(value) for value in point):
            raise AirfoilGeometryError(
                f"CSV row {row_number} contains a non-finite coordinate."
            )
        points.append(point)
    return "", "csv", points


def _near(point_a: tuple[float, float], point_b: tuple[float, float]) -> bool:
    return math.dist(point_a, point_b) <= _POINT_TOLERANCE


def _remove_consecutive_duplicates(
    points: Sequence[tuple[float, float]],
) -> tuple[list[tuple[float, float]], int]:
    cleaned: list[tuple[float, float]] = []
    removed = 0
    for point in points:
        if cleaned and _near(point, cleaned[-1]):
            removed += 1
        else:
            cleaned.append(point)
    return cleaned, removed


def _combine_lednicer_surfaces(
    first: Sequence[tuple[float, float]],
    second: Sequence[tuple[float, float]],
) -> list[tuple[float, float]]:
    if len(first) < 2 or len(second) < 2:
        raise AirfoilGeometryError("Lednicer surfaces require at least two points each.")

    first_mean = sum(point[1] for point in first) / len(first)
    second_mean = sum(point[1] for point in second) / len(second)
    upper, lower = (first, second) if first_mean >= second_mean else (second, first)

    upper_ordered = list(upper)
    if upper_ordered[0][0] < upper_ordered[-1][0]:
        upper_ordered.reverse()
    lower_ordered = list(lower)
    if lower_ordered[0][0] > lower_ordered[-1][0]:
        lower_ordered.reverse()

    if _near(upper_ordered[-1], lower_ordered[0]):
        return upper_ordered + lower_ordered[1:]
    return upper_ordered + lower_ordered


def _normalize(points: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(points) < 5:
        raise AirfoilGeometryError("Airfoil geometry requires at least five points.")
    x_min = min(point[0] for point in points)
    x_max = max(point[0] for point in points)
    chord = x_max - x_min
    if not math.isfinite(chord) or chord <= _POINT_TOLERANCE:
        raise AirfoilGeometryError("Airfoil chord must be finite and greater than zero.")
    leading_y_values = [
        point[1] for point in points if abs(point[0] - x_min) <= chord * _ORDER_TOLERANCE
    ]
    leading_y = sum(leading_y_values) / len(leading_y_values)
    return [((x - x_min) / chord, (y - leading_y) / chord) for x, y in points]


def _leading_edge_index(points: Sequence[tuple[float, float]]) -> int:
    minimum = min(point[0] for point in points)
    candidates = [
        index for index, point in enumerate(points) if abs(point[0] - minimum) <= _ORDER_TOLERANCE
    ]
    interior = [index for index in candidates if 0 < index < len(points) - 1]
    if not interior:
        raise AirfoilGeometryError(
            "Coordinate order must pass from a trailing edge through an interior leading edge."
        )
    return interior[len(interior) // 2]


def _canonical_order(points: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    ordered = list(points)
    leading_index = _leading_edge_index(ordered)
    if ordered[0][0] < 1.0 - 5.0e-2 or ordered[-1][0] < 1.0 - 5.0e-2:
        raise AirfoilGeometryError(
            "Coordinate sequence must begin and end at the trailing edge."
        )

    first_mean = sum(point[1] for point in ordered[: leading_index + 1]) / (
        leading_index + 1
    )
    second_mean = sum(point[1] for point in ordered[leading_index:]) / (
        len(ordered) - leading_index
    )
    if first_mean < second_mean:
        ordered.reverse()
        leading_index = _leading_edge_index(ordered)

    upper_x = [point[0] for point in ordered[: leading_index + 1]]
    lower_x = [point[0] for point in ordered[leading_index:]]
    if any(next_x > x + _ORDER_TOLERANCE for x, next_x in zip(upper_x, upper_x[1:])):
        raise AirfoilGeometryError(
            "Upper-surface x coordinates must progress toward the leading edge."
        )
    if any(next_x < x - _ORDER_TOLERANCE for x, next_x in zip(lower_x, lower_x[1:])):
        raise AirfoilGeometryError(
            "Lower-surface x coordinates must progress toward the trailing edge."
        )
    return ordered


def _reject_repeated_points(points: Sequence[tuple[float, float]]) -> None:
    seen: dict[tuple[int, int], int] = {}
    scale = 1.0 / _POINT_TOLERANCE
    for index, point in enumerate(points):
        key = (round(point[0] * scale), round(point[1] * scale))
        if key in seen:
            first_index = seen[key]
            is_closed_trailing_edge = first_index == 0 and index == len(points) - 1
            if not is_closed_trailing_edge:
                raise AirfoilGeometryError(
                    f"Airfoil contains a repeated non-consecutive point at indices "
                    f"{first_index} and {index}."
                )
        else:
            seen[key] = index


def _orientation(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_intersect(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
) -> bool:
    o1, o2 = _orientation(a, b, c), _orientation(a, b, d)
    o3, o4 = _orientation(c, d, a), _orientation(c, d, b)
    proper_crossing = (
        (o1 > _POINT_TOLERANCE and o2 < -_POINT_TOLERANCE)
        or (o1 < -_POINT_TOLERANCE and o2 > _POINT_TOLERANCE)
    ) and (
        (o3 > _POINT_TOLERANCE and o4 < -_POINT_TOLERANCE)
        or (o3 < -_POINT_TOLERANCE and o4 > _POINT_TOLERANCE)
    )
    if proper_crossing:
        return True

    def on_segment(
        start: tuple[float, float],
        end: tuple[float, float],
        point: tuple[float, float],
    ) -> bool:
        return (
            abs(_orientation(start, end, point)) <= _POINT_TOLERANCE
            and min(start[0], end[0]) - _POINT_TOLERANCE
            <= point[0]
            <= max(start[0], end[0]) + _POINT_TOLERANCE
            and min(start[1], end[1]) - _POINT_TOLERANCE
            <= point[1]
            <= max(start[1], end[1]) + _POINT_TOLERANCE
        )

    return any(
        (
            on_segment(a, b, c),
            on_segment(a, b, d),
            on_segment(c, d, a),
            on_segment(c, d, b),
        )
    )


def _reject_self_intersections(points: Sequence[tuple[float, float]]) -> None:
    segment_count = len(points) - 1
    closed = _near(points[0], points[-1])
    for first in range(segment_count):
        for second in range(first + 2, segment_count):
            if closed and first == 0 and second == segment_count - 1:
                continue
            if _segments_intersect(
                points[first], points[first + 1], points[second], points[second + 1]
            ):
                raise AirfoilGeometryError(
                    f"Airfoil perimeter self-intersects between segments {first} and {second}."
                )


def _surface_table(
    points: Sequence[tuple[float, float]], *, upper: bool
) -> tuple[list[float], list[float]]:
    grouped: dict[float, list[float]] = {}
    for x, y in points:
        grouped.setdefault(round(x, 12), []).append(y)
    xs = sorted(grouped)
    ys = [max(grouped[x]) if upper else min(grouped[x]) for x in xs]
    return xs, ys


def _interpolate(xs: Sequence[float], ys: Sequence[float], x: float) -> float:
    index = bisect_right(xs, x)
    if index == 0:
        return ys[0]
    if index >= len(xs):
        return ys[-1]
    x0, x1 = xs[index - 1], xs[index]
    if abs(x1 - x0) <= _POINT_TOLERANCE:
        return (ys[index - 1] + ys[index]) / 2.0
    weight = (x - x0) / (x1 - x0)
    return ys[index - 1] + weight * (ys[index] - ys[index - 1])


def _geometry_metrics(
    points: Sequence[tuple[float, float]],
) -> dict[str, float | str | bool]:
    leading_index = _leading_edge_index(points)
    upper_x, upper_y = _surface_table(points[: leading_index + 1], upper=True)
    lower_x, lower_y = _surface_table(points[leading_index:], upper=False)
    samples = [index / 500.0 for index in range(1, 500)]
    thicknesses = [
        _interpolate(upper_x, upper_y, x) - _interpolate(lower_x, lower_y, x)
        for x in samples
    ]
    minimum = min(thicknesses)
    maximum = max(thicknesses)
    if minimum < -1.0e-6:
        raise AirfoilGeometryError(
            f"Upper and lower surfaces cross; minimum thickness is {minimum:.6g} chord."
        )
    if maximum <= 1.0e-6:
        raise AirfoilGeometryError("Airfoil maximum thickness must be greater than zero.")

    trailing_edge_gap = math.dist(points[0], points[-1])
    return {
        "trailing_edge": "closed" if trailing_edge_gap <= 1.0e-4 else "open",
        "trailing_edge_gap_ratio": trailing_edge_gap,
        "maximum_thickness_ratio": maximum,
        "minimum_interior_thickness_ratio": max(0.0, minimum),
        "canonical_order": "upper_TE_to_LE_to_lower_TE",
        "normalized_to_unit_chord": True,
    }


def parse_airfoil_coordinates(
    text: str,
    *,
    airfoil_id: str | None = None,
    source: str = "<memory>",
    file_format: AirfoilFileFormat = "auto",
) -> AirfoilDefinition:
    """Parse, normalize, and validate airfoil coordinates from text."""
    if file_format not in {"auto", "selig", "lednicer", "csv"}:
        raise AirfoilGeometryError(f"Unsupported airfoil format {file_format!r}.")
    if file_format == "csv":
        input_name, detected_format, raw_points = _parse_csv(text)
    else:
        input_name, detected_format, raw_points = _parse_dat(text, file_format)

    input_count = len(raw_points)
    raw_points, duplicate_count = _remove_consecutive_duplicates(raw_points)
    normalized = _normalize(raw_points)
    ordered = _canonical_order(normalized)
    _reject_repeated_points(ordered)
    _reject_self_intersections(ordered)
    metrics = _geometry_metrics(ordered)

    resolved_id = (airfoil_id or input_name).strip()
    if not resolved_id:
        raise AirfoilGeometryError(
            "Airfoil id is required when the coordinate file has no name header."
        )
    metadata = {
        "coordinate_format": detected_format,
        "input_name": input_name,
        "input_point_count": input_count,
        "point_count": len(ordered),
        "consecutive_duplicates_removed": duplicate_count,
        "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        **metrics,
    }
    return AirfoilDefinition(
        id=resolved_id,
        source=source,
        coordinates=tuple(ordered),
        metadata=metadata,
    )


def load_airfoil_coordinates(
    path: str | Path,
    *,
    airfoil_id: str | None = None,
    file_format: AirfoilFileFormat = "auto",
) -> AirfoilDefinition:
    """Load an airfoil coordinate file and return its canonical definition."""
    coordinate_path = Path(path)
    selected_format = (
        "csv"
        if file_format == "auto" and coordinate_path.suffix.casefold() == ".csv"
        else file_format
    )
    try:
        text = coordinate_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise AirfoilGeometryError(
            f"Could not read airfoil coordinate file {coordinate_path}."
        ) from exc
    return parse_airfoil_coordinates(
        text,
        airfoil_id=airfoil_id or coordinate_path.stem,
        source=str(coordinate_path),
        file_format=selected_format,
    )
