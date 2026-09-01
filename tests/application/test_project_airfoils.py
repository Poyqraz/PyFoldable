"""PY-02: one coordinate realization from catalog through preview and analysis."""

import hashlib
import json
import math
from dataclasses import replace
from pathlib import Path

import pytest

from pyfoldable.application.design_analysis import DesignAnalysisError, prepare_design_analysis, run_design_analysis
from pyfoldable.application.design_draft import DesignDraftInputs, build_design_draft
from pyfoldable.core import BEMRotorSettings, PolarFamily, PolarTable, load_design_config
from pyfoldable.core.airfoil import airfoil_coordinate_sha256, validate_airfoil_definition
from pyfoldable.core.profile_catalog import PROJECT_AIRFOIL_IDS, load_project_airfoil
from pyfoldable.core.providers import PolarGenerationRequest, PolarGenerationResult, PolarPointResult, ProviderIdentity
from pyfoldable.visualization.propeller_25d import PreviewBladeStation, PropellerPreviewSpec, build_propeller_preview_mesh


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "configs/designs/TIP_HINGED_250_CANONICAL.toml"
EXPECTED = ("NACA0012", "NACA2412", "NACA23012", "NACA4415", "NACA63-412")


def _draft(airfoil, **changes):
    inputs = DesignDraftInputs(
        diameter="250 mm", hub_radius="18 mm", hinge_radius="100 mm", blade_count=2,
        airfoil_id=airfoil.id, chord_scale=1.0, twist_scale=1.0,
        preview_fold_angle="0 deg", angular_speed="7100 rpm", forward_speed="0 m/s",
        air_density="1.225 kg/m^3", dynamic_viscosity="1.81e-5 Pa*s",
        temperature="288.15 K", pressure="101325 Pa",
    )
    return build_design_draft(SOURCE, replace(inputs, **changes), airfoil_definition=airfoil)


def _mesh(airfoil, angle=0):
    spec = PropellerPreviewSpec(
        diameter_m=0.25, hub_radius_m=0.018, blade_count=1, hinge_radius_m=0.1,
        fold_angle_deg=angle, airfoil_id=airfoil.id, airfoil_definition=airfoil,
    )
    stations = (PreviewBladeStation(0.2, 0.028, 0), PreviewBladeStation(0.6, 0.023, 0), PreviewBladeStation(0.98, 0.008, 0))
    return build_propeller_preview_mesh(spec, stations)


def _family(airfoil, digest):
    return PolarFamily(tuple(PolarTable(
        airfoil_id=airfoil.id, scenario_id="synthetic-identity-test",
        reynolds=re, mach=ma, alpha_rad=(-math.pi / 2, math.pi / 2),
        cl=(0.8, 0.8), cd=(0.02, 0.02), cm=(0, 0), source="synthetic-test-only",
        metadata={} if digest is None else {"airfoil_coordinate_sha256": digest},
    ) for re in (100, 1e7) for ma in (0, 1)))


def test_exact_five_project_profiles():
    assert PROJECT_AIRFOIL_IDS == EXPECTED
    with pytest.raises(ValueError, match="catalog"):
        load_project_airfoil("NACA4412")


@pytest.mark.parametrize("profile", EXPECTED)
def test_catalog_geometry_provenance_and_cwd_independence(profile, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    airfoil = load_project_airfoil(profile)
    assert airfoil.id == profile
    assert len(airfoil.coordinates) >= 50
    assert min(x for x, _ in airfoil.coordinates) == 0
    assert max(x for x, _ in airfoil.coordinates) == 1
    assert airfoil.metadata["airfoil_coordinate_sha256"] == airfoil_coordinate_sha256(airfoil)
    assert len(airfoil.metadata["source_sha256"]) == 64
    assert airfoil.metadata["physical_qualification"] is False
    assert airfoil.metadata["maximum_thickness_ratio"] == pytest.approx(0.15 if profile == "NACA4415" else 0.12, abs=0.002)
    assert airfoil.source


@pytest.mark.parametrize("profile", EXPECTED)
def test_draft_coordinates_roundtrip_without_changing_canonical(profile, tmp_path):
    before = SOURCE.read_bytes()
    airfoil = load_project_airfoil(profile)
    artifact = _draft(airfoil)
    path = tmp_path / artifact.filename
    path.write_text(artifact.toml, encoding="utf-8")
    restored = load_design_config(path)
    matching = [item for item in restored.airfoils if item.id == profile]
    assert len(matching) == 1
    assert matching[0].coordinates == airfoil.coordinates
    assert matching[0].source == airfoil.source
    assert matching[0].metadata == airfoil.metadata
    assert SOURCE.read_bytes() == before
    prep = json.loads(prepare_design_analysis(artifact).report_json)
    assert prep["preparation"]["airfoil_coordinate_sha256"] == airfoil_coordinate_sha256(airfoil)


@pytest.mark.parametrize("profile", EXPECTED)
def test_preview_uses_exact_coordinates_without_naca_substitution(profile, monkeypatch):
    import pyfoldable.visualization.propeller_25d as preview

    def forbidden(*args, **kwargs):
        raise AssertionError("coordinate preview must not call analytic NACA4")

    monkeypatch.setattr(preview, "naca4_section_loop", forbidden)
    airfoil = load_project_airfoil(profile)
    mesh = _mesh(airfoil)
    assert mesh.airfoil_coordinate_sha256 == airfoil_coordinate_sha256(airfoil)
    assert mesh.airfoil_id == profile
    points = airfoil.coordinates
    if math.dist(points[0], points[-1]) <= 1e-12:
        points = points[:-1]
    assert mesh.section_vertex_count == len(points)
    assert len(mesh.vertices) == mesh.station_count * len(points)
    for vertex, (x, y) in zip(mesh.vertices, points):
        assert vertex == pytest.approx((0.025, (x - 0.25) * 0.028, y * 0.028))
    for a, b, c in mesh.faces:
        ab = tuple(mesh.vertices[b][i] - mesh.vertices[a][i] for i in range(3))
        ac = tuple(mesh.vertices[c][i] - mesh.vertices[a][i] for i in range(3))
        cross = (ab[1]*ac[2]-ab[2]*ac[1], ab[2]*ac[0]-ab[0]*ac[2], ab[0]*ac[1]-ab[1]*ac[0])
        assert math.hypot(*cross) > 0


@pytest.mark.parametrize("angle", [-90, -180])
def test_coordinate_mesh_fold_preserves_root_and_rigid_tip(angle):
    foil = load_project_airfoil("NACA63-412")
    opened, folded = _mesh(foil), _mesh(foil, angle)
    n = opened.section_vertex_count
    split = (opened.hinge_root_station_index + 1) * n
    assert folded.vertices[:split] == opened.vertices[:split]
    for index in range(n):
        hinge = opened.hinge_tip_station_index * n + index
        tip = (opened.station_count - 1) * n + index
        assert math.dist(folded.vertices[hinge], folded.vertices[tip]) == pytest.approx(math.dist(opened.vertices[hinge], opened.vertices[tip]))


def test_catalog_pdas_anchor_values_and_distinct_trailing_edges():
    foil = load_project_airfoil("NACA63-412")
    assert (0.75, -0.007565) in foil.coordinates
    assert (0.5, 0.075761) in foil.coordinates
    assert foil.metadata["trailing_edge"] == "closed"
    assert load_project_airfoil("NACA2412").metadata["trailing_edge"] == "open"


def test_shared_coordinate_hash_retains_existing_provider_format():
    foil = load_project_airfoil("NACA0012")
    expected = hashlib.sha256("\n".join(f"{x:.17g},{y:.17g}" for x, y in foil.coordinates).encode()).hexdigest()
    assert airfoil_coordinate_sha256(foil) == expected


def test_selected_profile_and_explicit_definition_must_agree():
    with pytest.raises(ValueError, match="airfoil"):
        _draft(load_project_airfoil("NACA23012"), airfoil_id="NACA2412")


def test_same_name_changed_coordinates_cannot_keep_old_hash():
    foil = load_project_airfoil("NACA2412")
    forged = replace(foil, coordinates=tuple((x, y * 1.01) for x, y in foil.coordinates))
    with pytest.raises(ValueError, match="SHA|hash"):
        validate_airfoil_definition(forged)
    with pytest.raises(ValueError, match="SHA|hash"):
        _mesh(forged)


@pytest.mark.parametrize("digest", [None, "0" * 64])
def test_coordinate_draft_rejects_unbound_polar_family(digest):
    foil = load_project_airfoil("NACA2412")
    with pytest.raises(DesignAnalysisError, match="coordinate"):
        run_design_analysis(_draft(foil), {foil.id: _family(foil, digest)})


def test_matching_polar_coordinate_hash_allows_screening_not_qualification():
    foil = load_project_airfoil("NACA2412")
    result = run_design_analysis(_draft(foil), {foil.id: _family(foil, airfoil_coordinate_sha256(foil))}, settings=BEMRotorSettings(annulus_count=4))
    assert json.loads(result.report_json)["physical_qualification"] is False


def test_every_polar_table_must_match_coordinate_identity():
    foil = load_project_airfoil("NACA2412")
    family = _family(foil, airfoil_coordinate_sha256(foil))
    family.tables[-1].metadata.clear()
    with pytest.raises(DesignAnalysisError, match="coordinate"):
        run_design_analysis(_draft(foil), {foil.id: family})


@pytest.mark.parametrize("metadata", [None, [], "invalid"])
def test_coordinate_polar_metadata_must_be_a_mapping(metadata):
    foil = load_project_airfoil("NACA2412")
    family = _family(foil, airfoil_coordinate_sha256(foil))
    malformed = replace(family.tables[0], metadata=metadata)
    with pytest.raises(DesignAnalysisError, match="coordinate"):
        run_design_analysis(_draft(foil), {foil.id: PolarFamily((malformed, *family.tables[1:]))})


def test_coordinate_metadata_keys_roundtrip_as_literal_strings(tmp_path):
    foil = load_project_airfoil("NACA2412")
    foil = replace(foil, metadata={**foil.metadata, "source.version": "v1", 'quoted "key"': "reference"})
    path = tmp_path / "draft.toml"
    path.write_text(_draft(foil).toml, encoding="utf-8")
    restored = next(item for item in load_design_config(path).airfoils if item.id == foil.id)
    assert restored.metadata == foil.metadata


@pytest.mark.parametrize("profile", EXPECTED)
def test_provider_receives_same_shape_and_emits_same_coordinate_identity(profile):
    foil = load_project_airfoil(profile)
    request = PolarGenerationRequest(airfoil=foil, alpha_rad=(-0.1, 0.1), reynolds=100000)
    provider = ProviderIdentity("identity-fixture", "1", "synthetic", "1")
    result = PolarGenerationResult(request=request, provider=provider, elapsed_s=0.01, points=tuple(
        PolarPointResult(alpha_rad=a, status="converged", cl=a, cd=0.02, cm=0)
        for a in request.alpha_rad
    ))
    table = result.to_polar_table()
    assert table.metadata["airfoil_coordinate_sha256"] == _mesh(foil).airfoil_coordinate_sha256
    changed = validate_airfoil_definition(replace(foil,
        coordinates=tuple((x, y * 1.01) for x, y in foil.coordinates),
        metadata={key: value for key, value in foil.metadata.items() if key != "airfoil_coordinate_sha256"},
    ))
    assert replace(request, airfoil=changed).cache_key(provider) != request.cache_key(provider)


@pytest.mark.parametrize("field", ["source_sha256", "airfoil_coordinate_sha256"])
def test_catalog_rejects_mismatched_identity(field, tmp_path, monkeypatch):
    import pyfoldable.core.profile_catalog as catalog
    import shutil

    shutil.copytree(catalog._ASSETS, tmp_path / "assets")
    path = tmp_path / "assets" / "catalog.json"
    manifest = json.loads(path.read_text())
    manifest["profiles"][1][field] = "0" * 64
    path.write_text(json.dumps(manifest))
    monkeypatch.setattr(catalog, "_ASSETS", path.parent)
    with pytest.raises(ValueError, match="SHA-256"):
        load_project_airfoil("NACA2412")


@pytest.mark.parametrize("mutation", ["missing_hash", "stale_hash", "missing_coordinates"])
def test_config_rejects_incomplete_or_changed_coordinate_identity(mutation, tmp_path):
    from pyfoldable.core.config import DesignConfigError

    foil = load_project_airfoil("NACA2412")
    document = _draft(foil).toml
    digest = foil.metadata["airfoil_coordinate_sha256"]
    if mutation == "missing_hash":
        document = "\n".join(line for line in document.splitlines() if not line.startswith("airfoil_coordinate_sha256 ="))
    elif mutation == "stale_hash":
        document = document.replace(digest, "0" * 64)
    else:
        document = "\n".join(line for line in document.splitlines() if not line.startswith("coordinates ="))
    path = tmp_path / "draft.toml"
    path.write_text(document, encoding="utf-8")
    with pytest.raises(DesignConfigError, match="coordinate|SHA"):
        load_design_config(path)
