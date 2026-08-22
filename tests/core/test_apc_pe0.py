import hashlib
import math

import pytest

from pyfoldable.core import APCPE0Error, parse_apc_pe0


SOURCE_URL = "https://example.invalid/10x47SF.PE0"
PE0 = b"""10x4.7SF
v-test-1
Simulation Date: 02/24/2026
 0.8300 0.6400 2.0 2.0 2.0 0.0 0.0 0.0600 22.0 0.04 0.03 0.1 0.0 0.0
 2.5000 1.1400 4.7 4.7 4.7 0.0 0.0 0.0425 16.0 0.05 0.04 0.1 0.0 0.0
 4.9000 0.3600 4.1 4.1 4.1 0.0 0.0 0.0425 7.7 0.01 0.01 0.0 0.0 0.0
 5.0000 0.0200 4.0 4.0 4.0 0.0 0.0 0.0425 7.2 0.01 0.00 0.0 0.0 0.0
 RADIUS: 5.00
 HUBRAD: 0.25
 HUBTRA: 0.83
 BLADES: 2
 AIRFOIL1: 4.90, E63
 AIRFOIL2: 5.00, APC12
"""


def test_pe0_parser_preserves_geometry_identity_and_airfoil_contract():
    digest = hashlib.sha256(PE0).hexdigest()

    geometry = parse_apc_pe0(
        PE0, source_url=SOURCE_URL, expected_sha256=digest
    )
    blade = geometry.blade(airfoil_id="E63-local")

    assert geometry.version == "v-test-1"
    assert geometry.simulation_date.isoformat() == "2026-02-24"
    assert geometry.source_sha256 == digest
    assert geometry.radius_m == pytest.approx(5.0 * 0.0254)
    assert geometry.hub_radius_m == pytest.approx(0.25 * 0.0254)
    assert [transition.airfoil_id for transition in geometry.airfoil_transitions] == [
        "E63",
        "APC12",
    ]
    assert blade.stations[0].r_over_R == pytest.approx(0.83 / 5.0)
    assert blade.stations[1].twist_rad == pytest.approx(math.radians(16.0))
    assert all(station.airfoil_id == "E63-local" for station in blade.stations)


def test_pe0_parser_fails_closed_on_digest_or_missing_provenance():
    with pytest.raises(APCPE0Error, match="SHA-256 mismatch"):
        parse_apc_pe0(PE0, source_url=SOURCE_URL, expected_sha256="0" * 64)

    with pytest.raises(APCPE0Error, match="version or simulation date"):
        parse_apc_pe0(b"not a PE0 file", source_url=SOURCE_URL)

    malformed = PE0.replace(b"0.0600 22.0", b"nan 22.0")
    with pytest.raises(APCPE0Error, match="finite and physical"):
        parse_apc_pe0(malformed, source_url=SOURCE_URL)
