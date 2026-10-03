"""First-party synthetic software checks, not blade/physics measurements."""
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

import pytest

from pyfoldable.application.blade_stations import parse_station_bundle
from pyfoldable.application.design_draft import DesignDraftInputs
from pyfoldable.application import parent_blade_generator as generator
from pyfoldable.application.parent_blade_generator import (
    ParentGenerationError, generate_parent_blade_cuts,
)
from pyfoldable.core.airfoil import airfoil_coordinate_sha256
from pyfoldable.core.profile_catalog import load_project_airfoil


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'configs/designs/TIP_HINGED_250_CANONICAL.toml'


def controls(**changes):
    return replace(DesignDraftInputs(diameter='250 mm', hub_radius='18 mm',
        hinge_radius='100 mm', blade_count=2, airfoil_id='NACA2412', chord_scale=1.,
        twist_scale=1., preview_fold_angle='0 deg', angular_speed='7100 rpm',
        forward_speed='0 m/s', air_density='1.225 kg/m^3', dynamic_viscosity='1.81e-5 Pa*s',
        temperature='288.15 K', pressure='101325 Pa'), **changes)


def generate(hinges=(.075, .1), **kwargs):
    return generate_parent_blade_cuts(kwargs.pop('source', SOURCE),
        kwargs.pop('inputs', controls()), kwargs.pop('profile', load_project_airfoil('NACA2412')),
        hinge_radii_m=hinges, frame_id='synthetic-shaft',
        evidence_label='synthetic software check', **kwargs)


def test_one_immutable_parent_two_direct_cuts_and_comparison(monkeypatch):
    before = SOURCE.read_bytes()
    original = generator.build_design_draft
    calls = []
    def build(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(generator, 'build_design_draft', build)
    result = generate()
    doc = json.loads(result.canonical_json)
    assert len(calls) == 1
    assert SOURCE.read_bytes() == before
    assert result.sha256 == hashlib.sha256(result.canonical_json.encode()).hexdigest()
    parent = doc['parent_bundle']
    assert [r['radius'] for r in parent['stations']] == [.025, .05, .075, .1, .1225]
    digest = parse_station_bundle(json.dumps(parent).encode()).canonical_sha256
    assert doc['parent_canonical_sha256'] == digest
    assert parent['airfoil_coordinate_sha256'] == airfoil_coordinate_sha256(load_project_airfoil('NACA2412'))
    for placement in doc['placements']:
        assert placement['status'] == 'REPORTED'
        assert placement['parent_canonical_sha256'] == digest
        for role in ('fixed', 'tip'):
            component = placement['components'][role]
            assert component['bundle']['provenance']['parent_sha256'] == digest
            assert component['bundle']['diameter'] == parent['diameter']
            for row, pi in zip(component['bundle']['stations'], component['parent_indices']):
                assert row == parent['stations'][pi]  # exact stored values, no recomputation
                assert row['radius'].hex() == parent['stations'][pi]['radius'].hex()
        comparison = placement['comparison']
        assert all(r['differences'] == dict(radius_m=0., chord_m=0., twist_rad=0.) for r in comparison['rows'])
        assert all(r['airfoil_coordinate_identity_equal'] for r in comparison['rows'])
        assert comparison['station_comparison'] == 'DIFFERENCES_OR_GAPS'  # missing root/tip endpoints
        assert comparison['physical_qualification'] is False
        assert all(x is None for x in comparison['unestablished'].values())
    assert doc['placements'][0]['components']['fixed']['parent_indices'] == [0, 1, 2]
    assert doc['placements'][0]['components']['tip']['parent_indices'] == [2, 3, 4]
    assert doc['placements'][1]['components']['tip']['parent_indices'] == [3, 4]
    assert 'cut-00' in result.comparison_table and 'cut-01' in result.comparison_table
    assert doc['source_sha256'] == hashlib.sha256(before).hexdigest()
    assert doc['physical_qualification'] is False


def test_absent_hinge_endpoints_remain_gaps_no_interpolation():
    hinges = (8/13*.125, 10/13*.125)
    doc = json.loads(generate(hinges).canonical_json)
    parent_rows = doc['parent_bundle']['stations']
    for placement in doc['placements']:
        assert placement['status'] == 'REPORTED'
        assert 'HINGE_STATION_ABSENT' in placement['diagnostics']
        assert not placement['hinge_station_present']
        assert all(row['radius'] != placement['hinge_radius_m'] for row in parent_rows)
        comparison = placement['comparison']
        assert comparison['coverage']['fixed']['tip_gap_m'] > 0
        assert comparison['coverage']['tip']['root_gap_m'] > 0
        assert comparison['coverage']['parent']['root_gap_m'] == parent_rows[0]['radius']-doc['parent_bundle']['hub_radius']
        assert comparison['coverage']['parent']['tip_gap_m'] == .125-.1225
        assert len(placement['components']['fixed']['bundle']['stations']) == 3
        assert len(placement['components']['tip']['bundle']['stations']) == 2


def test_insufficient_child_rows_return_partial_diagnostics_not_padding():
    doc = json.loads(generate((.03, .11)).canonical_json)
    first, second = doc['placements']
    assert first['status'] == second['status'] == 'INSUFFICIENT_CHILD_ROWS'
    assert first['components']['fixed']['bundle'] is None
    assert len(first['components']['fixed']['station_rows']) == 1
    assert len(first['components']['tip']['bundle']['stations']) == 4
    assert second['components']['tip']['bundle'] is None
    assert len(second['components']['tip']['station_rows']) == 1
    assert first['comparison'] is None and second['comparison'] is None
    assert 'fixed:1<2' in first['diagnostics']
    assert 'tip:1<2' in second['diagnostics']


def test_parent_controls_applied_once_and_children_keep_result():
    doc = json.loads(generate(inputs=controls(chord_scale=1.1, twist_scale=.9)).canonical_json)
    assert doc['generation_controls']['chord_scale'] == 1.1
    assert doc['generation_controls']['twist_scale'] == .9
    assert doc['parent_bundle']['stations'][0]['chord'] == .028*1.1
    assert doc['parent_bundle']['stations'][0]['twist'] == math.radians(31)*.9
    assert all(r['status'] == 'EQUAL_SUPPLIED_VALUES' for p in doc['placements'] for r in p['comparison']['rows'])


def test_deterministic_across_calls_and_input_sequence_order():
    assert generate() == generate()
    doc = json.loads(generate((.1, .075)).canonical_json)
    assert [p['hinge_radius_m'] for p in doc['placements']] == [.1, .075]
    assert doc['parent_canonical_sha256'] == json.loads(generate().canonical_json)['parent_canonical_sha256']


@pytest.mark.parametrize('hinges', [(), (.1,), (.1, .1), (.075,.1,.11),
    (True,.1), (.075,float('nan')), (.075,float('inf')), (.018,.1), (.075,.125), ('75 mm',.1)])
def test_invalid_two_position_request(hinges):
    with pytest.raises(ParentGenerationError):
        generate(hinges)


def test_coordinate_identity_not_a_profile_name():
    with pytest.raises(ParentGenerationError, match='profile|coordinate'):
        generate(profile=load_project_airfoil('NACA0012'))
    foil = load_project_airfoil('NACA2412')
    with pytest.raises(ParentGenerationError, match='coordinate|SHA'):
        generate(profile=replace(foil, metadata={**foil.metadata, 'airfoil_coordinate_sha256':'0'*64}))


@pytest.mark.parametrize('old,new', [
    ('axial_offset = "0 mm"','axial_offset = "1 mm"'),
    ('axis_elevation = "90 deg"','axis_elevation = "80 deg"'),
    ('airfoil = "NACA2412"','airfoil = "NACA0012"'),
])
def test_unsupported_source_geometry_is_not_hidden_by_draft_controls(tmp_path, old, new):
    text = SOURCE.read_text().replace(old,new,1)
    if 'NACA0012' in new:
        text += '\n[[airfoils]]\nid="NACA0012"\nsource="analytic_naca_4_digit"\n'
    path = tmp_path/'source.toml'; path.write_text(text)
    with pytest.raises(ParentGenerationError, match='Unsupported'):
        generate(source=path)


def test_non_deployed_preview_is_unsupported():
    with pytest.raises(ParentGenerationError, match='deployed'):
        generate(inputs=controls(preview_fold_angle='-10 deg'))


def test_joint_declarations_are_preserved_without_shape_inference():
    modifications = ([dict(component='tip', child_index=None,
        description='Declared parametric gap; solid not generated', reference='internal joint declaration', revision='1')], [])
    doc = json.loads(generate(joint_reference='internal joint v1', joint_modifications=modifications).canonical_json)
    assert doc['joint_reference'] == 'internal joint v1'
    assert doc['placements'][0]['comparison']['joint_modifications'] == modifications[0]
    assert doc['placements'][1]['comparison']['joint_modifications'] == []
    assert doc['unestablished']['joint_solid_geometry'] is None


def test_cli_json_table_and_actual_emitted_inputs_are_replayable(tmp_path):
    script = ROOT/'examples/generate_parent_blade_cuts.py'
    base = [sys.executable, str(script), '--hinges', '75 mm', '100 mm']
    result = subprocess.run(base+['--output-dir',str(tmp_path/'outputs')], capture_output=True,text=True,check=True)
    doc = json.loads(result.stdout)
    assert len(doc['placements']) == 2
    parent = parse_station_bundle((tmp_path/'outputs/parent.json').read_bytes())
    assert parent.canonical_sha256 == doc['parent_canonical_sha256']
    replay = subprocess.run([sys.executable,str(ROOT/'examples/compare_parent_blade_stations.py'),
        str(tmp_path/'outputs/parent.json'),str(tmp_path/'outputs/cut-00-fixed.json'),
        str(tmp_path/'outputs/cut-00-tip.json'),str(tmp_path/'outputs/cut-00-declaration.json')],
        capture_output=True,text=True,check=True)
    assert json.loads(replay.stdout) == doc['placements'][0]['comparison']
    table = subprocess.run(base+['--format','table'],capture_output=True,text=True,check=True)
    assert 'synthetic' in table.stdout.lower() and 'cut-01' in table.stdout
    duplicate = subprocess.run(base+['--output-dir',str(tmp_path/'outputs')],capture_output=True,text=True)
    assert duplicate.returncode == 2  # do not overwrite prior evidence


def test_single_row_children_still_report_signed_endpoint_gaps():
    doc = json.loads(generate((.03, .11)).canonical_json)
    for cut in doc['placements']:
        for role, component in cut['components'].items():
            rows = component['station_rows']
            low, high = component['coverage']['required_span_m']
            assert component['coverage']['root_gap_m'] == rows[0]['radius']-low
            assert component['coverage']['tip_gap_m'] == high-rows[-1]['radius']
            assert component['coverage']['continuous_geometry_established'] is None
        assert cut['parent_coverage']['supplied_span_complete'] is False


def test_empty_children_are_explicit_without_fabricating_a_span():
    doc = json.loads(generate((.02, .124)).canonical_json)
    for cut, role in zip(doc['placements'], ('fixed','tip')):
        component = cut['components'][role]
        assert component['station_rows'] == []
        assert component['bundle'] is None
        assert component['coverage']['supplied_span_m'] is None
        assert component['coverage']['root_gap_m'] is None
        assert component['coverage']['supplied_span_complete'] is False


def test_invalid_joint_record_is_rejected_even_without_comparison():
    with pytest.raises(ParentGenerationError):
        generate((.03,.11), joint_modifications=([dict(component='fixed',child_index=1,
            description='gap',reference='declared',revision='1')], []))
