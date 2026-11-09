"""Sixth catalog entry: real geometry, inert numerical seams, immutable old data."""
from dataclasses import replace
import csv
import hashlib
import io
import json
from pathlib import Path
import tarfile

import pytest

from pyfoldable.application import design_analysis, provider_design_analysis as app
from pyfoldable.application import provider_record_store as storage
from pyfoldable.application.design_draft import DesignDraftArtifact
from pyfoldable.application.profile_bem_comparison import add_record, comparison_document, comparison_csv
from pyfoldable.core.airfoil import airfoil_coordinate_sha256
from pyfoldable.core.profile_catalog import PROJECT_AIRFOIL_IDS, load_project_airfoil
from pyfoldable.providers import xfoil
from test_provider_design_analysis import scenario, install_inert_bem, inert_cell

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'tests/fixtures/provider_design_analysis/pr108_catalog_inert_compatibility.tar.gz'
OLD_CATALOG = 'cab021803ad8832d82cac8954ff6a3548731b9c1aff4a9d6c4642f7bb4d4a0a0'
OLD_ASSETS = {
    'NACA0012': ('d38fe158fae271d9b8b80aafd94356fba9bbf2adedbf872a642eda4c714f88a6', 'ab62d56cc86a591da4f83c1980ea5b07743c4e47bdb0eb63a8e166e190a96d42'),
    'NACA2412': ('598edb7d31e3dc039e993a1cdd6ad3412796e9c762ed5a1bbb41e1e928c8e5ef', '3f84aba0f9234ed6e9fe4eedebe88ae8701a19ae181d70e21a02b0704916999a'),
    'NACA23012': ('ee1360611f922b88a7bc7a3263f3931468d2c7f0fac974231d470a217b670f26', 'e89b3a24cee51eaffecbe80ea1fd8022e6531f185c0bb0496362c941b644281e'),
    'NACA4415': ('2108c3a650454f89e6d9193110e166da58151db587b619e7c179758d96ee6823', '44fb14376fc3b15e6d2a501fefb8388dce4bb3dfbc2a2cfd7af4c7f08ce0ea5a'),
    'NACA63-412': ('89446c03b3725d25482c7e5cf56ec95b8c47873a5e5e7094a148d26aa3b1c03c', 'f001973703830e0db98893169ebcdaf848deb3b3d175e7781cebb44a254327c2'),
}


@pytest.fixture(autouse=True)
def no_genuine_calls(monkeypatch):
    def forbidden(*a, **k):
        pytest.fail('No genuine provider/banner/BEM call in sixth-profile tests')
    monkeypatch.setattr(xfoil.XfoilProvider, 'generate', forbidden)
    monkeypatch.setattr(xfoil, '_discover_backend_version', forbidden)
    monkeypatch.setattr(design_analysis, 'solve_bem_rotor', forbidden)


def test_original_assets_and_six_distinct_identities():
    assert PROJECT_AIRFOIL_IDS == (*OLD_ASSETS, 'NACA4412')
    for name, (byte_sha, coordinate_sha) in OLD_ASSETS.items():
        raw = (ROOT / 'pyfoldable/data/airfoils' / (name + '.dat')).read_bytes()
        foil = load_project_airfoil(name)
        assert hashlib.sha256(raw).hexdigest() == byte_sha
        assert airfoil_coordinate_sha256(foil) == coordinate_sha
        assert foil.metadata['catalog_sha256'] != OLD_CATALOG
    assert len({airfoil_coordinate_sha256(load_project_airfoil(p)) for p in PROJECT_AIRFOIL_IDS}) == 6


def test_naca4412_exact_pdas_transcription_and_open_te():
    from decimal import Decimal
    rows = list(csv.DictReader((ROOT / 'docs/declarations/pdas_naca4412_common_x_20261108.csv').open()))
    upper = [(float(Decimal(r['upper_x_percent'])/100), float(Decimal(r['upper_y_percent'])/100)) for r in rows]
    lower = [(float(Decimal(r['lower_x_percent'])/100), float(Decimal(r['lower_y_percent'])/100)) for r in rows]
    expected = tuple(reversed(upper)) + tuple(lower[1:])
    foil = load_project_airfoil('NACA4412')
    assert len(rows) == 26 and len(foil.coordinates) == 51
    assert foil.coordinates == expected
    assert foil.coordinates[0] == (1., .001295)
    assert foil.coordinates[-1] == (1., -.001248)
    assert (0.4, .098030) in foil.coordinates
    assert (0.4, -.018030) in foil.coordinates
    assert foil.metadata['trailing_edge'] == 'open'
    assert foil.metadata['trailing_edge_gap_ratio'] == pytest.approx(.002543)
    assert airfoil_coordinate_sha256(foil) != airfoil_coordinate_sha256(load_project_airfoil('NACA4415'))


def test_old_store_snapshot_and_request_identities_survive_catalog_append(tmp_path, monkeypatch):
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == 'bfbbdd66e6e0c4cc0f16026d5c5aa27605d1e9e39e762514b50fac285e861440'
    with tarfile.open(FIXTURE) as tar:
        retained = {m.name: tar.extractfile(m).read() for m in tar if m.isfile()}
    for name, data in retained.items():
        target = tmp_path / name
        assert target.resolve().is_relative_to(tmp_path.resolve())
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    provenance = json.loads(retained['provenance.json'])
    old_snapshot = json.loads(retained['snapshot.json'])
    old_draft = DesignDraftArtifact(**json.loads(retained['draft.json']))
    selection, current_repository = scenario('NACA2412')
    assert selection.draft.draft_sha256 != old_draft.draft_sha256
    # Only the catalog metadata changed; source geometry/conditions are unchanged.
    current_catalog = load_project_airfoil('NACA2412').metadata['catalog_sha256']
    assert old_draft.toml.replace(OLD_CATALOG, current_catalog) == selection.draft.toml
    monkeypatch.setenv(storage.STORE_ENVIRONMENT_VARIABLE, str(tmp_path/'store'))
    repository = app.application_provider_repository()  # actual reopened store
    family = repository.families[0]
    assert family.stored_version.content_sha256 == provenance['stored_version_sha256']
    assert [r.cache_key(family.provider) for r in family.requests] == provenance['request_sha256']
    current_family = current_repository.families[0]
    assert [r.cache_key(current_family.provider) for r in current_family.requests] == provenance['request_sha256']
    assert all(r.airfoil.metadata['catalog_sha256'] == OLD_CATALOG for r in family.requests)
    current = replace(selection, stored_version_sha256=family.stored_version.content_sha256)
    old = replace(current, draft=old_draft)
    old_prepared = app.prepare_provider_design_analysis(old, repository)
    new_prepared = app.prepare_provider_design_analysis(current, repository)
    old_report = json.loads(old_snapshot['report_text'])
    assert old_report['request']['provider_design_request_sha256'] == provenance['prepared_request_sha256']
    # Admission binds the actual store location and application source too.
    # Reopening elsewhere and editing even an error message requires fresh admission.
    previous_admission = old_report['request']['provider_design_admission']
    current_old_admission = json.loads(old_prepared.admission_json)
    assert current_old_admission['stored_version']['root'] != previous_admission['stored_version']['root']
    assert current_old_admission['implementation_file_sha256'] != previous_admission['implementation_file_sha256']
    previous_admission['stored_version']['root'] = current_old_admission['stored_version']['root']
    previous_admission['implementation_file_sha256'] = current_old_admission['implementation_file_sha256']
    assert current_old_admission == previous_admission
    assert old_prepared.request_sha256 != provenance['prepared_request_sha256']
    assert old_prepared.request_sha256 != new_prepared.request_sha256
    with pytest.raises(app.ProviderDesignPreparationError, match='stale'):
        app.run_provider_design_analysis(old_prepared, active_selection=current, repository=repository)
    calls = install_inert_bem(monkeypatch)
    new_result = app.run_provider_design_analysis(new_prepared, active_selection=current, repository=repository)
    assert len(calls) == 1 and new_result.record['status'] == 'success'
    saved = add_record((), old_snapshot)
    doc = comparison_document(saved, evidence_class='inert_fixture')
    assert saved[0] == old_snapshot
    assert comparison_csv(doc).encode() == retained['comparison.csv']
    assert all((tmp_path/name).read_bytes() == data for name, data in retained.items())


@pytest.mark.parametrize('mutation', ['foreign_profile', 'same_name_wrong_coordinates', 'foreign_return'])
def test_naca4412_rejects_foreign_evidence_before_explicit_execution(mutation):
    selection, repository = scenario('NACA4412')
    family = repository.families[0]
    _, foreign = scenario('NACA2412')
    if mutation == 'foreign_profile':
        bad = replace(foreign.families[0], family_id=selection.family_id)
    elif mutation == 'same_name_wrong_coordinates':
        # Internally coherent wrong shape: receipts/requests match one another,
        # but not the selected PDAS NACA4412 asset. No stale claimed hash trick.
        wrong = replace(load_project_airfoil('NACA2412'), id='NACA4412', metadata={})
        requests = tuple(replace(r, airfoil=wrong) for r in family.requests)
        bad = replace(family, requests=requests, cells=tuple(inert_cell(r, family.provider) for r in requests))
    else:
        bad = replace(family, cells=foreign.families[0].cells)
    with pytest.raises(app.ProviderDesignPreparationError) as caught:
        app.prepare_provider_design_analysis(selection, app.ManagedProviderRepository((bad,)))
    assert caught.value.code == {'foreign_profile': 'missing_applicable_family',
                                 'same_name_wrong_coordinates': 'foreign_coordinates',
                                 'foreign_return': 'request_binding'}[mutation]
    state = {}
    with pytest.raises(app.ProviderDesignPreparationError):
        app.run_active_provider_design(state, selection, app.ManagedProviderRepository((bad,)))
    assert app.ACTIVE_OUTCOME not in state


def test_naca4412_missing_family_has_attributed_null_totals_and_exports():
    selection, _ = scenario('NACA4412')
    with pytest.raises(app.ProviderDesignPreparationError) as caught:
        app.prepare_provider_design_analysis(selection, app.ManagedProviderRepository())
    assert caught.value.code == 'missing_applicable_family'
    record = app.preparation_failure_record(selection, caught.value)
    assert record['airfoil_id'] == 'NACA4412'
    assert record['airfoil_coordinate_sha256'] == airfoil_coordinate_sha256(load_project_airfoil('NACA4412'))
    for key in ['thrust_n', 'torque_nm', 'shaft_power_w', 'report_sha256', 'analysis_request_sha256']:
        assert record[key] is None
    document = comparison_document(add_record((), record), evidence_class='caller_supplied_unqualified')
    row = next(csv.DictReader(io.StringIO(comparison_csv(document))))
    assert row['record_sha256'] == document['records'][0]['record_sha256']
    assert row['airfoil_id'] == 'NACA4412'
    assert record['attempted_selection_sha256'] in json.dumps(document)
