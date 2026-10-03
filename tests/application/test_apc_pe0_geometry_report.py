# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
"""First-party invented PE0-shaped software inputs; no APC numeric dataset."""
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

import pytest

from pyfoldable.application.apc_pe0_geometry_report import (
    PE0ReportError, MAX_PE0_BYTES, report_pe0_geometry,
)
from pyfoldable.core.apc_pe0 import APCPE0Geometry


# Deliberately a six-inch toy, not the requested APC 13x5.5MR member.
TOY = b'''PYFOLDABLE_TOY
v-synthetic-only
Simulation Date: 01/02/2020
 STATION CHORD PITCH_A PITCH_B PITCH_C SWEEP RAKE THICKNESS TWIST MAX_THICK AREA ZHIGH CGY CGZ
 (IN) (IN) (IN) (IN) (DEG) (IN) (IN) (RATIO) (DEG) (IN) (IN**2) (IN) (IN) (IN)
 0.200 0.500 1.001 1.002 9.003 -0.01 0.02 0.1 30.0 0.050 0.015 0.05 -0.02 0.01
 0.500 0.600 1.101 1.102 8.003 -0.02 0.03 0.1 25.0 0.060 0.018 0.06 -0.03 0.02
 1.020 0.550 1.201 1.202 7.003 -0.03 0.04 0.1 20.0 0.055 0.016 0.05 -0.04 0.03
 1.400 0.500 1.301 1.302 6.003 -0.04 0.05 0.1 15.0 0.050 0.014 0.04 -0.05 0.04
 2.200 0.400 1.401 1.402 5.003 -0.05 0.06 0.1 10.0 0.040 0.010 0.03 -0.06 0.05
 2.910 0.200 1.501 1.502 4.003 -0.06 0.07 0.1 5.0 0.020 0.005 0.02 -0.07 0.06
 RADIUS: 2.90
 HUBRAD: 0.30
 HUBTRA: 0.90
 BLADES: 2
 AIRFOIL1: 1.40, TOY_A
 AIRFOIL2: 2.80, TOY_B
 THICKNESS NOTE: invented constant toy ratio, not vendor geometry
 PITCH NOTE: three distinct invented fields; supplied TWIST is authoritative here
'''
ROOT = Path(__file__).resolve().parents[2]


def report(raw=TOY, **kwargs):
    return report_pe0_geometry(raw, source_reference='first-party synthetic software check',
        nominal_diameter_m=.1524, hinge_radii_m=(.0254,.0508), **kwargs)


def test_complete_table_source_columns_and_final_row_retained(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('single-profile blade shortcut is not a faithful reporter')
    monkeypatch.setattr(APCPE0Geometry,'blade',forbidden)
    result = report()
    d = json.loads(result.canonical_json)
    assert result.sha256 == hashlib.sha256(result.canonical_json.encode()).hexdigest()
    assert d['source']['sha256'] == hashlib.sha256(TOY).hexdigest()
    assert d['source']['version'] == 'v-synthetic-only'
    assert d['source']['simulation_date'] == '2020-01-02'
    assert d['parent']['station_count'] == 6
    rows = d['parent']['rows']
    assert [r['parent_index'] for r in rows] == list(range(6))
    assert all(len(r['lexemes']) == len(r['values']) == 14 for r in rows)
    assert rows[-1]['lexemes'][0] == '2.910'
    assert rows[-1]['si']['radius_m'] > d['radii']['footer_radius']['si_m']
    assert rows[0]['si']['twist_rad'] == math.radians(30)
    assert rows[0]['values'][2:5] == [1.001,1.002,9.003]
    assert [c['key'] for c in d['columns']][2:5] == ['pitch_1','pitch_2','pitch_3']
    assert [c['supplied_unit'] for c in d['columns']][2:5] == ['(IN)','(IN)','(DEG)']
    assert rows[0]['source_section']['thickness_ratio'] == .1
    assert rows[0]['source_section']['section_area_source'] == .015
    assert 'RADIUS_CONVENTIONS_DIFFER' in d['diagnostics']
    assert 'LAST_STATION_BEYOND_FOOTER_RADIUS' in d['diagnostics']
    assert d['physical_qualification'] is False


def test_hub_and_aerodynamic_applicability_are_descriptive_not_filtered():
    rows=json.loads(report().canonical_json)['parent']['rows']
    assert rows[0]['applicability']['region'] == 'HUB'
    assert rows[1]['applicability']['region'] == 'HUB_TRANSITION'
    assert rows[2]['applicability']['region'] == 'DECLARED_AERODYNAMIC_SPAN'
    assert rows[-1]['applicability']['region'] == 'BEYOND_FOOTER_RADIUS'
    assert not rows[-1]['applicability']['inside_footer_radius']
    assert rows[-1]['applicability']['inside_nominal_radius']
    assert all(r['source_section']['coordinate_identity'] is None for r in rows)


def test_direct_complementary_copies_index_lineage_and_missing_hinges():
    d=json.loads(report().canonical_json)
    assert [p['components']['fixed']['parent_indices'] for p in d['cuts']] == [[0,1],[0,1,2,3]]
    assert [p['components']['tip']['parent_indices'] for p in d['cuts']] == [[2,3,4,5],[4,5]]
    for cut in d['cuts']:
        assert cut['hinge_station_present'] is False
        assert 'HINGE_STATION_ABSENT' in cut['diagnostics']
        assert cut['components']['fixed']['coverage']['hinge_gap_m'] > 0
        assert cut['components']['tip']['coverage']['hinge_gap_m'] > 0
        for role, child in cut['components'].items():
            assert child['parent_sha256'] == d['parent_sha256']
            for row, index in zip(child['rows'],child['parent_indices']):
                assert row == d['parent']['rows'][index]
                assert row['si']['twist_rad'].hex() == d['parent']['rows'][index]['si']['twist_rad'].hex()
        assert cut['station_comparison']['status'] == 'UNSUPPORTED_UNRESOLVED_SECTION_IDENTITY'
        assert cut['station_comparison']['numeric_copy_identity'] is True
        assert cut['station_comparison']['coordinate_identity_established'] is None
    assert all(v is None for v in d['unestablished'].values())


def test_existing_hinge_row_shared_and_insufficient_rows_are_explicit():
    d=json.loads(report_pe0_geometry(TOY,source_reference='synthetic',nominal_diameter_m=.1524,
        hinge_radii_m=(1.4*.0254,.01)).canonical_json)
    assert d['cuts'][0]['hinge_station_present']
    assert 3 in d['cuts'][0]['components']['fixed']['parent_indices']
    assert 3 in d['cuts'][0]['components']['tip']['parent_indices']
    assert d['cuts'][1]['components']['fixed']['diagnostics'] == ['INSUFFICIENT_STATION_ROWS:1<2']


def test_parent_identity_independent_of_cut_order_and_reports_deterministic():
    assert report() == report()
    reversed_result=report_pe0_geometry(TOY,source_reference='first-party synthetic software check',
        nominal_diameter_m=.1524,hinge_radii_m=(.0508,.0254))
    assert json.loads(reversed_result.canonical_json)['parent_sha256'] == json.loads(report().canonical_json)['parent_sha256']


@pytest.mark.parametrize('change',[
    lambda r:r.replace(b'1.001 1.002 9.003',b'nan 1.002 9.003'),
    lambda r:r.replace(b'1.001 1.002 9.003',b'1.001 1.002'),
    lambda r:r.replace(b'1.001 1.002 9.003',b'1.001 1.002 9.003 4.0'),
    lambda r:r.replace(b'RADIUS: 2.90',b'RADIUS: 2.90\n RADIUS: 2.91'),
    lambda r:r.replace(b'BLADES: 2',b'BLADES: 2.5'),
    lambda r:r.replace(b'1.020 0.550',b'0.100 0.550'),
    lambda r:r.replace(b'(IN) (IN) (IN)',b'(MM) (IN) (IN)',1),
])
def test_no_silent_row_omission_or_semantic_override(change):
    with pytest.raises(PE0ReportError): report(change(TOY))


def test_metadata_definitions_retained_without_transition_invention():
    raw=TOY+b' APC12 is equivalent to NACA4412 (synthetic test statement, not evidence)\n'
    d=json.loads(report(raw).canonical_json)
    assert len(d['parent']['airfoil_declarations']) == 2
    assert [a['airfoil_id'] for a in d['parent']['airfoil_declarations']] == ['TOY_A','TOY_B']
    assert 'invented' in '\n'.join(d['parent']['thickness_metadata'])
    assert d['parent']['vendor_equivalence_statements'][-1].endswith('(synthetic test statement, not evidence)')
    assert d['parent']['transition_geometry'] is None
    assert any('PITCH NOTE:' in row['text'] for row in d['parent']['nonstation_lines'])


def test_digest_and_bounded_finite_request_validation():
    with pytest.raises(PE0ReportError): report(expected_sha256='0'*64)
    with pytest.raises(PE0ReportError): report(b'x'*(MAX_PE0_BYTES+1))
    for hinges in [(),(.02,),(.02,.02),(True,.05),(.02,float('nan')),(.02,.09)]:
        with pytest.raises(PE0ReportError):
            report_pe0_geometry(TOY,source_reference='synthetic',nominal_diameter_m=.1524,hinge_radii_m=hinges)
    with pytest.raises(PE0ReportError): report(expected_sha256=12)


def test_archive_identity_is_declared_not_verified_by_member_bytes():
    d=json.loads(report(archive_sha256='a'*64,member_name='toy/member.PE0').canonical_json)
    assert d['source']['archive_sha256'] == 'a'*64
    assert d['source']['archive_verification'] == 'DECLARED_NOT_VERIFIED'
    assert d['source']['member_name'] == 'toy/member.PE0'


def test_local_cli_reports_only_supplied_bytes_and_preserves_them(tmp_path):
    path=tmp_path/'toy.PE0';path.write_bytes(TOY)
    script=ROOT/'examples/report_local_pe0_geometry.py'
    cmd=[sys.executable,str(script),str(path),'--nominal-diameter','6 in','--hinges','25.4 mm','50.8 mm',
        '--source-reference','synthetic software check','--expected-sha256',hashlib.sha256(TOY).hexdigest()]
    result=subprocess.run(cmd,capture_output=True,text=True,check=True)
    d=json.loads(result.stdout);assert d['parent']['station_count']==6
    assert path.read_bytes()==TOY
    table=subprocess.run(cmd+['--format','table'],capture_output=True,text=True,check=True)
    assert 'pitch_1' in table.stdout and 'UNSUPPORTED' in table.stdout
    assert '2.910' in table.stdout and 'cut-01' in table.stdout
    bad=subprocess.run(cmd+['--expected-sha256','0'*64],capture_output=True,text=True)
    assert bad.returncode==2 and not bad.stdout


def test_malformed_transition_cannot_disappear_from_structured_declarations():
    with pytest.raises(PE0ReportError):
        report(TOY.replace(b'AIRFOIL1: 1.40, TOY_A',b'AIRFOIL1: nan, TOY_A'))


def test_complete_51_row_synthetic_table_is_not_a_vendor_demonstration():
    lines=TOY.decode().splitlines()
    rows=[]
    for i in range(51):
        values=[.2+i*(2.91-.2)/50,.5,1.1,1.2,11.3,-.01,.02,.1,20.,.05,.015,.04,-.02,.01]
        rows.append(' '+' '.join(format(x,'.17g') for x in values))
    raw=('\n'.join(lines[:5]+rows+lines[11:])+'\n').encode()
    d=json.loads(report(raw).canonical_json)
    assert d['parent']['station_count']==51
    assert len(d['parent']['rows'][-1]['values'])==14
    assert d['parent']['rows'][-1]['parent_index']==50
    assert d['source']['title']=='PYFOLDABLE_TOY'


def test_unbound_header_units_are_visible_without_invented_binding():
    raw=TOY.replace(TOY.splitlines()[4],b'Unit definitions supplied in separate prose; no positional unit row')
    d=json.loads(report(raw).canonical_json)
    assert 'SOURCE_UNIT_HEADER_BINDING_UNRESOLVED' in d['diagnostics']
    assert all(c['supplied_unit'] is None for c in d['columns'])
    assert any('separate prose' in r['text'] for r in d['parent']['nonstation_lines'])


@pytest.mark.parametrize('nominal',[True,0.,float('inf')])
def test_nominal_product_declaration_must_be_finite_positive_si(nominal):
    with pytest.raises(PE0ReportError):
        report_pe0_geometry(TOY,source_reference='synthetic',nominal_diameter_m=nominal,hinge_radii_m=(.0254,.0508))


@pytest.mark.parametrize('old,new',[(b'RADIUS: 2.90',b'RADIUS: 2.90e1'),
    (b'RADIUS: 2.90',b'RADIUS: 2.90BAD'),(b'BLADES: 2',b'BLADES: 2e1'),
    (b'0.200 0.500',b'INVALID 0.500')])
def test_review_regressions_full_footer_lexemes_and_invalid_first_cell(old,new):
    with pytest.raises(PE0ReportError):report(TOY.replace(old,new))


def test_conflicting_named_header_cannot_override_radius_chord_or_twist():
    for old,new in [(b'STATION CHORD',b'CHORD STATION'),
        (b'THICKNESS TWIST',b'TWIST THICKNESS')]:
        with pytest.raises(PE0ReportError):report(TOY.replace(old,new))


def test_nonnumeric_row_inside_identified_table_is_not_metadata():
    raw=TOY.replace(TOY.splitlines()[5],b'INVALID ROW DATA')
    with pytest.raises(PE0ReportError):report(raw)


@pytest.mark.parametrize('old,new',[(b'TWIST MAX_THICK AREA ZHIGH',b'TWIST AREA MAX_THICK ZHIGH'),
    (b'BLADES: 2',b'BLADES: 9007199254740993'),
    (b'BLADES: 2',b'BLADES: 2.0000000000000000001')])
def test_review_followup_section_header_and_exact_blade_integer(old,new):
    with pytest.raises(PE0ReportError):report(TOY.replace(old,new))
