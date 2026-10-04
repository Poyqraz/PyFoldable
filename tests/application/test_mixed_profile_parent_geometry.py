"""First-party software checks, never manufacturer or physical evidence."""
import copy
from dataclasses import replace
from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

import pytest

from pyfoldable.application import mixed_profile_parent_geometry as g

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'docs/declarations/mixed_profile_parent_synthetic_fixtures_v1.json'


def wire(v):
    return json.dumps(v, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('ascii')


@pytest.fixture
def declaration():
    data = json.loads(MANIFEST.read_bytes())
    assert hashlib.sha256(wire(data)).hexdigest() == '4cd0305a09cb2a460f334d0508af45b5b93fccb239fe6b2ad06bc131d386be02'
    return data


@pytest.fixture
def geometry_request(declaration):
    return g.parse_mixed_profile_request(wire(declaration['positive_cases'][0]['request']))


@pytest.fixture
def execution():
    return g.GeometryExecutionV1('synthetic-check', '2026-10-04T00:00:00Z',
                                 'test-runtime', 'test-platform', (), (), 'nearest-ties-even')


@pytest.fixture
def report(geometry_request, execution):
    return g.evaluate_mixed_profile_parent(geometry_request, execution=execution)


def rational(v):
    return F(int(v['n']), int(v['d']))


def test_s01_identity_immutable_cuts(geometry_request, report, declaration):
    c = json.loads(report.canonical_json)
    assert c['status'] == 'COMPLETE', c['diagnostics']
    assert report.sha256 == '4384536470719379fc928d794533b528d7fd43388ed95490bb476303a2e1b2dd'
    assert c['request_sha256'] == declaration['positive_cases'][0]['request_sha256']
    assert c['budget']['input_bytes'] == len(wire(declaration['positive_cases'][0]['request']))
    sections = c['sections']
    assert len(sections) == 8
    assert c['budget']['output_points'] == 144
    assert c['qualification']['physical_qualification'] is False
    for knot in geometry_request.scalars:
        s = next(x['content'] for x in sections if float.fromhex(x['content']['global_radius_m']) == knot.point.radius_m)
        assert s['source_index'] == knot.index
        assert s['station_kind'] == 'RETAINED_INPUT_STATION'
        assert s['scalar_hex'] == dict(zip(('c', 'beta', 'tau', 'Y', 'Z'),
                                          (v.hex() for v in (knot.point.chord_m, knot.point.twist_rad, knot.tau, knot.Y_m, knot.Z_m))))
    for cut, fixed, tip in zip(c['cuts'], (range(4), range(6)), (range(3,8), range(5,8))):
        v = cut['content']
        assert v['fixed_section_sha256s'] == [sections[i]['sha256'] for i in fixed]
        assert v['tip_section_sha256s'] == [sections[i]['sha256'] for i in tip]
        assert v['fixed_section_sha256s'][-1] == v['hinge_section_sha256'] == v['tip_section_sha256s'][0]
    assert sections[3]['content']['bracketing_indices'] == [2,3]
    assert sections[5]['content']['bracketing_indices'] == [3,4]
    projected = copy.deepcopy(c)
    projected['budget']['output_bytes'] = None
    assert c['budget']['output_bytes'] == len(wire(projected))


def test_sections_exact_oracle(report, geometry_request):
    """Independent Fraction formula, no production interpolation/rounding helper."""
    for record in json.loads(report.canonical_json)['sections']:
        s = record['content']; r = F(float.fromhex(s['global_radius_m']))
        a,b = map(F, geometry_request.model.transition_m)
        q = (r-a)/(b-a)
        w = F(0) if r <= a else F(1) if r >= b else 3*q*q-2*q*q*q
        assert rational(s['blend_weight']) == w
        for cert in s['scalar_certificates']:
            out = F(float.fromhex(cert['output_hex']))
            assert rational(cert['absolute_error_bound']) >= abs(out-rational(cert['enclosure_lo']))
        # Invented polygon graphs' thickness maximum is exactly (3-w)/16.
        upper = {float.fromhex(p['x_hex']): rational(p['v_reference']) for p in s['points'] if p['branch']=='upper'}
        lower = {float.fromhex(p['x_hex']): rational(p['v_reference']) for p in s['points'] if p['branch']=='lower'}
        tau = rational(s['scalar_certificates'][2]['reference'])
        assert max(upper[x]-lower[x] for x in upper) == tau
        assert set(upper) == {i/8 for i in range(9)}
        for p in s['points']:
            for cert in p['xyz_certificates']:
                v = float.fromhex(cert['output_hex']); lo,hi = map(rational,(cert['enclosure_lo'],cert['enclosure_hi']))
                cl,ch = map(rational,(cert['cell_lo'],cert['cell_hi']))
                assert cl <= lo <= hi <= ch
                if cert['kind']=='CERTIFIED_ROUNDING' and v != 0:
                    assert cl == (F(math.nextafter(v,-math.inf))+F(v))/2
                    assert ch == (F(v)+F(math.nextafter(v,math.inf)))/2
                assert rational(cert['absolute_error_bound']) == max(abs(F(v)-lo),abs(F(v)-hi))


def test_content_execution_separation(geometry_request, execution, report):
    second = g.evaluate_mixed_profile_parent(geometry_request, execution=replace(execution, run_id='other'))
    assert second.canonical_json == report.canonical_json
    assert second.sha256 == hashlib.sha256(report.canonical_json).hexdigest()
    assert second.execution_sha256 != report.execution_sha256
    assert second.execution_sha256 == hashlib.sha256(second.execution_json).hexdigest()


def test_transport_canonical_and_limits(declaration, execution):
    d=declaration['positive_cases'][0]['request']
    a=g.evaluate_mixed_profile_parent(g.parse_mixed_profile_request(wire(d)),execution=execution)
    b=g.evaluate_mixed_profile_parent(g.parse_mixed_profile_request(json.dumps(d,indent=4).encode()),execution=execution)
    assert a.canonical_json==b.canonical_json
    with pytest.raises(g.MixedProfileDecodeError) as exc:
        g.parse_mixed_profile_request(b' '*(2*1024*1024+1))
    assert exc.value.code=='REQUEST_BYTES_LIMIT' and exc.value.raw_sha256 is None


@pytest.mark.parametrize('case_index',range(8))
def test_declared_rejections(declaration, execution, case_index):
    case=declaration['rejection_cases'][case_index]; d=copy.deepcopy(declaration['positive_cases'][0]['request'])
    for op in case['definition']['overlay']:
        parts=op['path'].strip('/').split('/'); target=d
        for p in parts[:-1]: target=target[int(p)] if isinstance(target,list) else target[p]
        target[int(parts[-1]) if isinstance(target,list) else parts[-1]]=op['value']
    req=g.parse_mixed_profile_request(wire(d))
    one=g.evaluate_mixed_profile_parent(req,execution=execution)
    two=g.evaluate_mixed_profile_parent(req,execution=execution)
    assert one.canonical_json==two.canonical_json
    c=json.loads(one.canonical_json); expected=case['expected']
    assert (c['status'],c['stage'],c['diagnostics'][0]['code'])==(expected['status'],expected['stage'],expected['code'])
    assert not c['cuts']
    assert 'Status: BLOCKED' in g.render_mixed_profile_table(one)


def test_r09_decoder(declaration):
    with pytest.raises(g.MixedProfileDecodeError) as exc:
        g.parse_mixed_profile_request(declaration['rejection_cases'][8]['raw_ascii'].encode())
    assert exc.value.code=='DUPLICATE_KEY'


def test_actual_budget_persistent_retry_child():
    b=g.GeometryBudgetV1(); b.used=19_999_999
    b.charge('add')
    for op in ('compare','add','compare'):
        with pytest.raises(g.GeometryBlocked) as exc: b.charge(op)
        assert exc.value.code=='BUDGET_EXHAUSTED'
        assert b.used==20_000_000


def test_stronger_support_independent_of_core():
    up=((F(0),F(0)),(F(1,2),F(1,8)),(F(1),F(0)))
    low=((F(0),F(0)),(F(1,2),F(-1,8)),(F(1),F(0)))
    assert g._prove_graphs(up,low,g.GeometryBudgetV1(),'test')
    for branch in (low[:-1]+((F(3,4),F(0)),), ((F(1,8),F(0)),)+low[1:]):
        with pytest.raises(g.GeometryBlocked,match='full graph support'):
            g._prove_graphs(up,branch,g.GeometryBudgetV1(),'test')
    with pytest.raises(g.GeometryBlocked,match='strict distinct'):
        g._prove_graphs(up[:2]+(up[1],)+up[2:],low,g.GeometryBudgetV1(),'test')
    with pytest.raises(g.GeometryBlocked,match='interior'):
        g._prove_graphs(up,up,g.GeometryBudgetV1(),'test')


def test_rounding_ties_subnormal_exponent_signed_zero():
    for ref,expect in ((F(1)+F(1,2**53),1.), (F(3,2**1075),float.fromhex('0x0.0000000000002p-1022')),
                       (F(1,2**1075),0.),(-F(1,2**1075),-0.)):
        cert=g._round_certificate(ref,ref,g.GeometryBudgetV1(),'m',reference=ref)
        assert cert['output_hex']==expect.hex()
    cert=g._copied_certificate(-0.,g.GeometryBudgetV1(),'m')
    assert cert['output_hex']=='-0x0.0p+0' and cert['zero_rule']=='PRESERVE_INPUT_SIGN'


def test_cli_direct_agreement(tmp_path, declaration):
    src=tmp_path/'request.json'; src.write_bytes(wire(declaration['positive_cases'][0]['request']))
    out=tmp_path/'out.json'; table=tmp_path/'out.txt'; side=tmp_path/'execution.json'
    p=subprocess.run([sys.executable,'-m','pyfoldable.application.mixed_profile_parent_geometry',str(src),
                      '--json',str(out),'--table',str(table),'--execution',str(side)],cwd=ROOT,capture_output=True)
    assert p.returncode==0,p.stderr
    context=json.loads(side.read_bytes())['execution']
    assert set(p for p,h in context['code_sha256'])=={'application/mixed_profile_parent_geometry.py',
      'application/_mixed_profile_contract.py','application/_mixed_profile_exact.py',
      'application/blade_stations.py','core/airfoil.py','core/models.py'}
    assert len(context['binary_sha256'])>=1
    e=g.GeometryExecutionV1(**{**context,'code_sha256':tuple(map(tuple,context['code_sha256'])),
                              'binary_sha256':tuple(map(tuple,context['binary_sha256']))})
    direct=g.evaluate_mixed_profile_parent(g.parse_mixed_profile_request(src.read_bytes()),execution=e)
    assert out.read_bytes()==direct.canonical_json
    assert table.read_text()==g.render_mixed_profile_table(direct)


def test_independent_complete_placement_enclosure(report):
    """Independent factorial/power oracle, not production recurrence or libm."""
    for record in json.loads(report.canonical_json)['sections']:
        s=record['content']
        c,beta,tau,Y,Z=(rational(cert['reference']) for cert in s['scalar_certificates'])
        r=F(float.fromhex(s['global_radius_m']))
        n=100
        sin=sum((-1)**k*beta**(2*k+1)/math.factorial(2*k+1) for k in range(n))
        cos=sum((-1)**k*beta**(2*k)/math.factorial(2*k) for k in range(n))
        sr=abs(beta)**(2*n+1)/math.factorial(2*n+1)
        cr=abs(beta)**(2*n)/math.factorial(2*n)
        for p in s['points']:
            x=F(float.fromhex(p['x_hex'])); v=rational(p['v_reference']); dx=x-F(1,4)
            target=(r,Y+c*(dx*cos-v*sin),Z+c*(dx*sin+v*cos))
            error=(F(0),abs(c)*(abs(dx)*cr+abs(v)*sr),abs(c)*(abs(dx)*sr+abs(v)*cr))
            for cert,q,e in zip(p['xyz_certificates'],target,error):
                lo,hi=rational(cert['enclosure_lo']),rational(cert['enclosure_hi'])
                assert lo<=q-e<=q+e<=hi


def test_actual_retry_keeps_exhausted_shared_budget(geometry_request,execution,monkeypatch):
    real=g._round_certificate
    seen=[]
    def unresolved(lo,hi,b,unit,**kw):
        if kw.get('terms')==80 and not seen:
            seen.append(b)
            b.used=19_999_999
            b.charge('add')
            raise g.GeometryBlocked('ROUNDING_UNRESOLVED','unit forced ambiguity')
        return real(lo,hi,b,unit,**kw)
    monkeypatch.setattr(g,'_round_certificate',unresolved)
    c=json.loads(g.evaluate_mixed_profile_parent(geometry_request,execution=execution).canonical_json)
    assert c['status']=='BLOCKED' and c['stage']=='SECTIONS'
    assert c['diagnostics'][0]['code']=='BUDGET_EXHAUSTED'
    assert c['budget']['retry_count']==1 and c['budget']['rational_used']==20_000_000
    assert not c['cuts']


def test_actual_child_work_uses_same_budget(geometry_request,execution,monkeypatch):
    real=g._build_cuts
    def exhausted(req,sections,parent,b):
        assert b.used>0
        b.used=19_999_999
        return real(req,sections,parent,b)
    monkeypatch.setattr(g,'_build_cuts',exhausted)
    report=g.evaluate_mixed_profile_parent(geometry_request,execution=execution)
    c=json.loads(report.canonical_json)
    assert c['stage']=='CUTS' and c['status']=='BLOCKED'
    assert c['diagnostics'][0]['code']=='BUDGET_EXHAUSTED'
    assert len(c['sections'])==8 and not c['cuts']
    assert c['budget']['rational_used']==20_000_000


def test_invalid_execution_and_unexpected_partial(geometry_request,execution,monkeypatch):
    report=g.evaluate_mixed_profile_parent(geometry_request,execution=replace(execution,run_id=''))
    assert json.loads(report.canonical_json)['stage']=='REQUEST'
    assert json.loads(report.execution_json)['execution'] is None
    def broken(*args): raise RuntimeError('unit unexpected fault')
    monkeypatch.setattr(g,'_section',broken)
    with pytest.raises(g.MixedProfileInternalError) as exc:
        g.evaluate_mixed_profile_parent(geometry_request,execution=execution)
    assert isinstance(exc.value.__cause__,RuntimeError)
    c=json.loads(exc.value.partial_report.canonical_json)
    assert c['stage']=='SECTIONS' and c['status']=='BLOCKED' and c['parent'] and not c['cuts']


def test_wire_rejects_float_unknown_hex_and_nested_mutability(declaration,geometry_request,execution):
    d=copy.deepcopy(declaration['positive_cases'][0]['request'])
    d['scalars'][0]['tau']=.1
    with pytest.raises(g.MixedProfileDecodeError): g.parse_mixed_profile_request(wire(d))
    d['scalars'][0]['tau']='0x1p-3'
    with pytest.raises(g.MixedProfileDecodeError) as exc: g.parse_mixed_profile_request(wire(d))
    assert exc.value.code=='INVALID_F64_HEX'
    invalid=replace(geometry_request,scalars=list(geometry_request.scalars))
    c=json.loads(g.evaluate_mixed_profile_parent(invalid,execution=execution).canonical_json)
    assert c['status']=='BLOCKED' and c['stage']=='REQUEST' and c['request_sha256'] is None


def test_rehashed_corrupt_report_schema_rejected(report):
    c=json.loads(report.canonical_json); c['status']='INVENTED_SUCCESS'
    raw=wire(c); digest=hashlib.sha256(raw).hexdigest()
    side=json.loads(report.execution_json); side['content_sha256']=digest
    side_raw=wire(side)
    invalid=g.MixedProfileParentReportV1(raw,digest,side_raw,hashlib.sha256(side_raw).hexdigest())
    with pytest.raises(g.MixedProfileReportError): g.render_mixed_profile_table(invalid)


def test_canonical_dto_and_endpoint_byte_limits(geometry_request,execution):
    e=replace(geometry_request.endpoint_A,raw_bytes=b'\0'*(256*1024))
    # Six-byte JSON control escapes in two individually bounded raw inputs.
    c=json.loads(g.evaluate_mixed_profile_parent(replace(geometry_request,endpoint_A=e,endpoint_B=e),execution=execution).canonical_json)
    assert c['stage']=='REQUEST' and c['diagnostics'][0]['code']=='INPUT_LIMIT'
    assert c['budget']['input_bytes']>2*1024*1024
    e=replace(e,raw_bytes=b' '*(256*1024+1))
    c=json.loads(g.evaluate_mixed_profile_parent(replace(geometry_request,endpoint_A=e),execution=execution).canonical_json)
    assert c['diagnostics'][0]['code']=='INPUT_LIMIT'


def test_rational_serialization_inside_declared_bits_above_python_digit_limit():
    q=F(1,2**15000)
    v=g.rat(q)
    assert len(v['d'])>4300
    rebuilt=0
    for char in v['d']: rebuilt=rebuilt*10+ord(char)-48
    assert rebuilt==q.denominator and v['n']=='1'


@pytest.mark.parametrize('change',('sidecar_extra','sidecar_bad_execution','negative_error','coordinate_mismatch'))
def test_review_corrupt_receipts_rejected(report,change):
    c=json.loads(report.canonical_json); side=json.loads(report.execution_json)
    old_section=c['sections'][0]['sha256']
    if change=='sidecar_extra': side['extra']='not allowed'
    elif change=='sidecar_bad_execution': side['execution']={'not':'GeometryExecutionV1'}
    elif change=='negative_error': c['sections'][0]['content']['scalar_certificates'][0]['absolute_error_bound']={'n':'-1','d':'1'}
    else: c['sections'][0]['content']['points'][0]['xyz_hex'][0]='0x0.0p+0'
    if change in ('negative_error','coordinate_mismatch'):
        s=c['sections'][0]
        s['sha256']=hashlib.sha256(wire(s['content'])).hexdigest()
        for cut in c['cuts']:
            for n in ('fixed_section_sha256s','tip_section_sha256s'):
                cut['content'][n]=[s['sha256'] if h==old_section else h for h in cut['content'][n]]
            cut['sha256']=hashlib.sha256(wire(cut['content'])).hexdigest()
        projected=copy.deepcopy(c); projected['budget']['output_bytes']=None
        c['budget']['output_bytes']=len(wire(projected))
    raw=wire(c); digest=hashlib.sha256(raw).hexdigest(); side['content_sha256']=digest
    side_raw=wire(side)
    invalid=g.MixedProfileParentReportV1(raw,digest,side_raw,hashlib.sha256(side_raw).hexdigest())
    with pytest.raises(g.MixedProfileReportError): g.render_mixed_profile_table(invalid)


def test_review_maximum_escaped_execution_context(geometry_request,execution):
    code=tuple((chr(1)*2046+f'{i:02}', '0'*64) for i in range(32))
    binary=tuple((chr(2)*2046+f'{i:02}', '0'*64) for i in range(16))
    report=g.evaluate_mixed_profile_parent(geometry_request,execution=replace(execution,code_sha256=code,binary_sha256=binary))
    assert len(report.execution_json)>128*1024
    assert json.loads(report.canonical_json)['status']=='COMPLETE'
    assert 'Status: COMPLETE' in g.render_mixed_profile_table(report)


def test_review_normalization_proof_scalar_schema(report):
    c=json.loads(report.canonical_json)
    c['proofs'][0]['content']['raw_sha256']='not-a-digest'
    projected=copy.deepcopy(c); projected['budget']['output_bytes']=None
    c['budget']['output_bytes']=len(wire(projected))
    raw=wire(c); h=hashlib.sha256(raw).hexdigest()
    side=json.loads(report.execution_json); side['content_sha256']=h
    sr=wire(side)
    with pytest.raises(g.MixedProfileReportError):
        g.render_mixed_profile_table(g.MixedProfileParentReportV1(raw,h,sr,hashlib.sha256(sr).hexdigest()))


def _coordinator_rehashed_report(report, content, sidecar, changed_sections=()):
    """Refresh all content identities so witnesses test correspondence, not stale hashes."""
    replacements = {}
    for section in changed_sections:
        old = section['sha256']
        section['sha256'] = hashlib.sha256(wire(section['content'])).hexdigest()
        replacements[old] = section['sha256']
    if replacements:
        for cut in content['cuts']:
            for name in ('fixed_section_sha256s', 'tip_section_sha256s'):
                cut['content'][name] = [replacements.get(h, h) for h in cut['content'][name]]
            cut['content']['hinge_section_sha256'] = replacements.get(
                cut['content']['hinge_section_sha256'], cut['content']['hinge_section_sha256'])
            cut['sha256'] = hashlib.sha256(wire(cut['content'])).hexdigest()
    projected = copy.deepcopy(content)
    projected['budget']['output_bytes'] = None
    content['budget']['output_bytes'] = len(wire(projected))
    raw = wire(content)
    digest = hashlib.sha256(raw).hexdigest()
    sidecar['content_sha256'] = digest
    sidecar_raw = wire(sidecar)
    return g.MixedProfileParentReportV1(
        raw, digest, sidecar_raw, hashlib.sha256(sidecar_raw).hexdigest())


@pytest.mark.parametrize('change', (
    'retained_parent_scalar',
    'retained_signed_zero',
    'retained_source_index',
    'generated_bracket',
    'point_radius',
    'complete_inputs_missing',
    'complete_input_correspondence',
    'complete_proofs_missing',
    'complete_proof_order',
    'complete_branch_coverage',
    'complete_denominator_correspondence',
    'complete_denominator_gap_correspondence',
))
def test_coordinator_renderer_correspondence_witnesses(report, change):
    content = json.loads(report.canonical_json)
    sidecar = json.loads(report.execution_json)
    changed_sections = []

    if change == 'retained_parent_scalar':
        dst, src = content['sections'][0], content['sections'][1]
        dst['content']['scalar_hex']['c'] = src['content']['scalar_hex']['c']
        dst['content']['scalar_certificates'][0] = copy.deepcopy(
            src['content']['scalar_certificates'][0])
        changed_sections = [dst]
    elif change == 'retained_signed_zero':
        dst = content['sections'][0]
        src = next(s for s in content['sections']
                   if s['content']['station_kind'] == 'RETAINED_INPUT_STATION'
                   and s['content']['source_index'] == 5)
        assert dst['content']['scalar_hex']['Y'] == '-0x0.0p+0'
        assert src['content']['scalar_hex']['Y'] == '0x0.0p+0'
        dst['content']['scalar_hex']['Y'] = src['content']['scalar_hex']['Y']
        dst['content']['scalar_certificates'][3] = copy.deepcopy(
            src['content']['scalar_certificates'][3])
        changed_sections = [dst]
    elif change == 'retained_source_index':
        dst = content['sections'][0]
        dst['content']['source_index'] = 9999
        changed_sections = [dst]
    elif change == 'generated_bracket':
        dst = next(s for s in content['sections']
                   if s['content']['station_kind'] == 'GENERATED_SECTION')
        dst['content']['bracketing_indices'] = [4, 1]
        changed_sections = [dst]
    elif change == 'point_radius':
        dst, src = content['sections'][0], content['sections'][1]
        dst_point, src_point = dst['content']['points'][0], src['content']['points'][0]
        dst_point['xyz_hex'][0] = src_point['xyz_hex'][0]
        dst_point['xyz_certificates'][0] = copy.deepcopy(src_point['xyz_certificates'][0])
        changed_sections = [dst]
    elif change == 'complete_inputs_missing':
        content['inputs'] = []
    elif change == 'complete_input_correspondence':
        content['inputs'][0]['point_or_row_count'] -= 1
    elif change == 'complete_proofs_missing':
        content['proofs'] = []
    elif change == 'complete_proof_order':
        content['proofs'][0], content['proofs'][1] = content['proofs'][1], content['proofs'][0]
    elif change == 'complete_branch_coverage':
        p = next(p for p in content['proofs'] if p['kind'] == 'branch_cell')
        p['content']['cell_index'] += 1
    elif change == 'complete_denominator_correspondence':
        p = next(p for p in content['proofs'] if p['kind'] == 'denominator')
        p['content']['lower_bound'] = {'n': '1', 'd': '1'}
    else:
        p = next(p for p in content['proofs'] if p['kind'] == 'denominator')
        p['content']['gap_A'] = {'n': '1', 'd': '1'}
        gap_b = rational(p['content']['gap_B'])
        p['content']['lower_bound'] = (
            p['content']['gap_B'] if gap_b < 1 else {'n': '1', 'd': '1'})

    invalid = _coordinator_rehashed_report(
        report, content, sidecar, changed_sections=changed_sections)
    with pytest.raises(g.MixedProfileReportError):
        g.render_mixed_profile_table(invalid)
