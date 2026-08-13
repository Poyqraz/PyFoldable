"""Airfoil coordinate parsing, normalization, and validation tests."""

from pathlib import Path

import pytest

from pyfoldable.core import (
    AirfoilGeometryError,
    load_airfoil_coordinates,
    parse_airfoil_coordinates,
)


SELIG = """Example foil
# upper TE -> LE -> lower TE
1.0 0.01
0.5 0.08
0.0 0.0
0.5 -0.04
1.0 -0.01
"""


def test_selig_parser_normalizes_scale_offset_and_metadata() -> None:
    scaled = """Scaled foil
12.0 5.1
7.0 5.8
2.0 5.0
7.0 4.6
12.0 4.9
"""
    airfoil = parse_airfoil_coordinates(scaled, source="fixture.dat")

    assert airfoil.id == "Scaled foil"
    assert airfoil.source == "fixture.dat"
    assert airfoil.coordinates[0] == pytest.approx((1.0, 0.01))
    assert airfoil.coordinates[2] == pytest.approx((0.0, 0.0))
    assert airfoil.metadata["coordinate_format"] == "selig"
    assert airfoil.metadata["normalized_to_unit_chord"] is True
    assert airfoil.metadata["maximum_thickness_ratio"] == pytest.approx(0.12)
    assert len(airfoil.metadata["source_sha256"]) == 64


def test_reversed_selig_order_is_canonicalized() -> None:
    rows = SELIG.splitlines()
    reversed_text = "Example foil\n" + "\n".join(reversed(rows[2:]))

    airfoil = parse_airfoil_coordinates(reversed_text)

    assert airfoil.coordinates[0][1] > 0.0
    assert airfoil.coordinates[-1][1] < 0.0
    assert airfoil.metadata["canonical_order"] == "upper_TE_to_LE_to_lower_TE"


def test_lednicer_counts_and_surface_order_are_supported() -> None:
    text = """Lednicer foil
3 3
0.0 0.0
0.5 0.08
1.0 0.01
0.0 0.0
0.5 -.04
1.0 -.01
"""
    airfoil = parse_airfoil_coordinates(text)

    assert airfoil.metadata["coordinate_format"] == "lednicer"
    assert len(airfoil.coordinates) == 5
    assert airfoil.coordinates[0] == pytest.approx((1.0, 0.01))
    assert airfoil.coordinates[-1] == pytest.approx((1.0, -0.01))


def test_lednicer_count_mismatch_is_rejected() -> None:
    text = """Broken
3 3
0 0
0.5 0.1
1 0
0 0
1 0
"""
    with pytest.raises(AirfoilGeometryError, match="declares 6 points"):
        parse_airfoil_coordinates(text)


def test_csv_header_and_extra_columns_are_supported(tmp_path: Path) -> None:
    path = tmp_path / "fixture.csv"
    path.write_text(
        "station,x,y\n0,1,0.01\n1,0.5,0.08\n2,0,0\n3,0.5,-0.04\n4,1,-0.01\n",
        encoding="utf-8",
    )

    airfoil = load_airfoil_coordinates(path, airfoil_id="CSV_FOIL")

    assert airfoil.id == "CSV_FOIL"
    assert airfoil.metadata["coordinate_format"] == "csv"
    assert airfoil.coordinates[2] == pytest.approx((0.0, 0.0))


def test_consecutive_duplicate_is_removed_and_reported() -> None:
    text = SELIG.replace("0.5 0.08", "0.5 0.08\n0.5 0.08")
    airfoil = parse_airfoil_coordinates(text)

    assert airfoil.metadata["consecutive_duplicates_removed"] == 1
    assert airfoil.metadata["input_point_count"] == 6
    assert airfoil.metadata["point_count"] == 5


def test_nonconsecutive_duplicate_is_rejected() -> None:
    text = SELIG.replace("0.5 -0.04", "0.5 0.08")
    with pytest.raises(AirfoilGeometryError, match="repeated non-consecutive"):
        parse_airfoil_coordinates(text)


def test_crossing_surfaces_are_rejected() -> None:
    text = """Crossed
1.0 0.01
0.5 -0.03
0.0 0.0
0.5 0.04
1.0 -0.01
"""
    with pytest.raises(AirfoilGeometryError, match="cross|self-intersects"):
        parse_airfoil_coordinates(text)


def test_overlapping_nonadjacent_segments_are_rejected() -> None:
    text = """Overlap
1.0 0.1
0.5 0.1
0.0 0.0
0.5 0.1
1.0 -0.1
"""
    with pytest.raises(AirfoilGeometryError, match="repeated|self-intersects"):
        parse_airfoil_coordinates(text)


def test_invalid_coordinate_order_is_rejected() -> None:
    text = """Bad order
1.0 0.0
0.0 0.0
0.5 0.1
1.0 0.0
0.5 -0.1
"""
    with pytest.raises(AirfoilGeometryError, match="trailing edge|surface x coordinates"):
        parse_airfoil_coordinates(text)


def test_closed_and_open_trailing_edges_are_classified() -> None:
    closed = SELIG.replace("1.0 0.01", "1.0 0.0").replace("1.0 -0.01", "1.0 0.0")

    assert parse_airfoil_coordinates(closed).metadata["trailing_edge"] == "closed"
    assert parse_airfoil_coordinates(SELIG).metadata["trailing_edge"] == "open"


def test_headerless_memory_data_requires_an_id() -> None:
    text = "\n".join(SELIG.splitlines()[2:])
    with pytest.raises(AirfoilGeometryError, match="id is required"):
        parse_airfoil_coordinates(text)

    assert parse_airfoil_coordinates(text, airfoil_id="KNOWN").id == "KNOWN"
