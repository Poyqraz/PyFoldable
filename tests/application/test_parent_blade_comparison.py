"""Synthetic software checks only; no CAD, source solver or physical evidence."""
from copy import deepcopy
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from pyfoldable.application.blade_stations import parse_station_bundle
from pyfoldable.application.parent_blade_comparison import (
    StationComparisonError, compare_parent_blade_stations,
)


def encoded(value):
    return json.dumps(value, allow_nan=False).encode()


def inputs():
    profile = hashlib.sha256(b"first-party synthetic profile identity, not coordinates").hexdigest()
    parent = {"schema_version": 1, "units": {"length": "m", "angle": "rad"},
        "diameter": .25, "hub_radius": .018, "airfoil_id": "synthetic-profile",
        "airfoil_coordinate_sha256": profile,
        "provenance": {"kind": "declared_design", "reference": "synthetic software check",
            "locator": "in-memory stations", "revision": "1"},
        "stations": [{"radius": r, "chord": c, "twist": t}
            for r, c, t in [(.018, .028, .5), (.06, .025, .4),
                (.1, .017, .2), (.115, .012, .15), (.125, .008, .1)]]}
    parent_sha = parse_station_bundle(encoded(parent)).canonical_sha256
    fixed, tip = deepcopy(parent), deepcopy(parent)
    for role, child, rows in [('fixed', fixed, parent['stations'][:3]),
            ('tip', tip, parent['stations'][2:])]:
        child['stations'] = deepcopy(rows)
        child['provenance'].update(kind='derived_geometry', parent_sha256=parent_sha,
            locator=role+' complementary cut')
    declaration = {"schema_version": 1, "evidence_label": "synthetic software check",
        "hinge_radius_m": .1,
        "bundle_sha256": {"parent": parent_sha, "fixed": parse_station_bundle(encoded(fixed)).canonical_sha256,
            "tip": parse_station_bundle(encoded(tip)).canonical_sha256},
        "frames": {role: {"id": "study-shaft", "radial_origin": "shaft_axis",
            "pose": "deployed", "transform": "identity", "radius_coordinate": "global_shaft_radius"}
            for role in ('parent', 'fixed', 'tip')},
        "correspondence": [{"component": role, "child_index": ci, "parent_index": pi}
            for role, pairs in [('fixed', [(0, 0), (1, 1), (2, 2)]),
                ('tip', [(0, 2), (1, 3), (2, 4)])] for ci, pi in pairs],
        "joint_modifications": []}
    return [parent, fixed, tip, declaration]


def refresh(data):
    # Explicitly rebind the modified synthetic child; no stale identity accepted.
    for role, doc in zip(('parent', 'fixed', 'tip'), data[:3]):
        data[3]['bundle_sha256'][role] = parse_station_bundle(encoded(doc)).canonical_sha256


def compare(data=None):
    return compare_parent_blade_stations(*(encoded(x) for x in (inputs() if data is None else data)))


def payload(data=None):
    return json.loads(compare(data).canonical_json)


def test_preserved_inheritance_and_deterministic_output():
    report = compare()
    doc = json.loads(report.canonical_json)
    assert report == compare()
    assert report.sha256 == hashlib.sha256(report.canonical_json.encode()).hexdigest()
    assert doc['station_comparison'] == 'SUPPLIED_STATIONS_MATCH'
    assert len(doc['rows']) == 6  # hinge station explicitly present in both children
    assert all(r['differences'] == dict(radius_m=0., chord_m=0., twist_rad=0.) for r in doc['rows'])
    assert all(r['airfoil_coordinate_identity_equal'] for r in doc['rows'])
    assert doc['coverage']['fixed']['required_span_m'] == [.018, .1]
    assert doc['coverage']['tip']['required_span_m'] == [.1, .125]
    assert doc['coverage']['parent']['supplied_span_complete']
    assert doc['missing_parent_stations'] == {'fixed': [], 'tip': []}
    assert doc['evidence_label'] == 'synthetic software check'
    for role in ('parent', 'fixed', 'tip'):
        assert doc['sources'][role]['raw_sha256'] == hashlib.sha256(encoded(inputs()[('parent','fixed','tip').index(role)])).hexdigest()
    assert doc['sources']['tip']['provenance']['parent_sha256'] == doc['sources']['parent']['canonical_sha256']
    assert '| tip | 0 | 2 |' in report.comparison_table
    assert 'twist_rad' in report.comparison_table
    assert doc['physical_qualification'] is False
    assert all(v is None for v in doc['unestablished'].values())


def test_twist_reset_and_chord_change_are_visible_not_repaired():
    data = inputs()
    data[2]['stations'][0]['twist'] = data[0]['stations'][0]['twist']
    data[2]['stations'][1]['chord'] = .013
    refresh(data)
    doc = payload(data)
    tip = [r for r in doc['rows'] if r['component'] == 'tip']
    assert tip[0]['child']['twist_rad'] == .5
    assert tip[0]['parent']['twist_rad'] == .2
    assert tip[0]['differences']['twist_rad'] == .5-.2
    assert tip[1]['differences']['chord_m'] == .013-.012
    assert doc['station_comparison'] == 'DIFFERENCES_OR_GAPS'


def test_wrong_parent_and_stale_child_identities_rejected():
    data = inputs()
    data[2]['provenance']['parent_sha256'] = '0'*64
    refresh(data)
    with pytest.raises(StationComparisonError, match='parent identity'):
        compare(data)
    data = inputs()
    data[2]['stations'][0]['twist'] = .4
    with pytest.raises(StationComparisonError, match='bundle identity'):
        compare(data)


def test_same_profile_name_does_not_establish_coordinate_identity():
    data = inputs()
    data[2]['airfoil_coordinate_sha256'] = '0'*64
    refresh(data)
    doc = payload(data)
    row = doc['rows'][-1]
    assert row['airfoil_label_equal'] is True
    assert row['airfoil_coordinate_identity_equal'] is False
    assert row['child']['airfoil_coordinate_sha256'] == '0'*64
    assert doc['station_comparison'] == 'DIFFERENCES_OR_GAPS'


def test_partial_coverage_and_unmapped_children_no_interpolation():
    data = inputs()
    data[2]['stations'].pop(1)
    data[2]['stations'][-1]['radius'] = .12
    data[3]['correspondence'] = [r for r in data[3]['correspondence'] if r['component'] != 'tip']
    data[3]['correspondence'].append(dict(component='tip', child_index=0, parent_index=2))
    refresh(data)
    doc = payload(data)
    assert doc['coverage']['tip']['tip_gap_m'] == .125-.12
    assert not doc['coverage']['tip']['supplied_span_complete']
    assert doc['missing_parent_stations']['tip'] == [3, 4]
    row = doc['rows'][-1]
    assert row['parent'] is None and row['differences'] is None
    assert row['status'] == 'NO_DECLARED_CORRESPONDENCE'
    assert row['child']['radius_m'] == .12
    assert doc['station_comparison'] == 'DIFFERENCES_OR_GAPS'


def test_radius_differences_are_not_rescaled():
    data = inputs()
    data[2]['stations'][1]['radius'] = .116
    refresh(data)
    row = payload(data)['rows'][-2]
    assert row['differences']['radius_m'] == .116-.115
    assert row['child']['radius_m'] == .116


def test_joint_modifications_are_declarations_not_exemptions():
    data = inputs()
    data[2]['stations'][0]['chord'] = .02
    data[3]['joint_modifications'] = [dict(component='tip', child_index=0,
        description='Synthetic declared lug change; geometry not reconstructed',
        reference='synthetic CAD placeholder', revision='1')]
    refresh(data)
    doc = payload(data)
    assert doc['joint_modifications'] == data[3]['joint_modifications']
    assert doc['rows'][3]['declared_joint_modification']
    assert doc['rows'][3]['status'] == 'DIFFERENT'
    assert doc['station_comparison'] == 'DIFFERENCES_OR_GAPS'


def test_joint_region_without_a_sample_remains_a_separate_declaration():
    data = inputs()
    data[3]['joint_modifications'] = [dict(component='fixed', child_index=None,
        description='Synthetic gap between stations; no section values supplied',
        reference='synthetic declaration only', revision='1')]
    doc = payload(data)
    assert doc['joint_modifications'] == data[3]['joint_modifications']
    assert not any(r['declared_joint_modification'] for r in doc['rows'])
    assert doc['station_comparison'] == 'SUPPLIED_STATIONS_MATCH'
    assert doc['unestablished']['complete_3d_surface_equivalence'] is None


@pytest.mark.parametrize('change', [
    lambda d: d[3]['frames']['tip'].update(transform='translated'),
    lambda d: d[3]['frames']['tip'].update(id='local-tip'),
    lambda d: d[3]['frames']['tip'].update(radius_coordinate='local_span'),
])
def test_unsupported_frames_and_transforms_are_not_assumed(change):
    data = inputs(); change(data)
    with pytest.raises(StationComparisonError, match='unsupported frame|Unsupported frame'):
        compare(data)


@pytest.mark.parametrize('change', [
    lambda d: d[3].update(hinge_radius_m=True),
    lambda d: d[3].update(unknown=1),
    lambda d: d[3]['correspondence'].append(deepcopy(d[3]['correspondence'][0])),
    lambda d: d[3]['correspondence'][0].update(child_index=True),
    lambda d: d[3]['correspondence'][0].update(parent_index=100),
    lambda d: d[2]['provenance'].update(kind='declared_design'),
    lambda d: d[2]['stations'][0].update(radius=.099),
])
def test_invalid_or_noncomplementary_request_is_controlled(change):
    data = inputs(); change(data); refresh(data)
    with pytest.raises(StationComparisonError):
        compare(data)


def test_no_ulp_gate_or_profile_name_lineage_inference():
    data = inputs()
    data[2]['stations'][-1]['twist'] = math.nextafter(.1, math.inf)
    refresh(data)
    assert payload(data)['rows'][-1]['status'] == 'DIFFERENT'
    data = inputs()
    del data[2]['provenance']['parent_sha256']
    data[2]['provenance']['kind'] = 'declared_design'
    refresh(data)
    with pytest.raises(StationComparisonError, match='parent identity'):
        compare(data)


def test_cli_json_and_readable_table(tmp_path):
    paths = []
    for name, data in zip(('parent','fixed','tip','declaration'), inputs()):
        p = tmp_path / (name+'.json'); p.write_bytes(encoded(data)); paths.append(str(p))
    script = Path(__file__).resolve().parents[2] / 'examples/compare_parent_blade_stations.py'
    command = [sys.executable, str(script), *paths]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)['station_comparison'] == 'SUPPLIED_STATIONS_MATCH'
    table = subprocess.run(command+['--format','table'], capture_output=True, text=True, check=True)
    assert '| tip | 0 | 2 |' in table.stdout
    assert '3D' in table.stdout and 'synthetic software check' in table.stdout
