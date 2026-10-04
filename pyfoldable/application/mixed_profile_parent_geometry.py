"""Bounded caller-input mixed-profile sections; synthetic software scope only.

No network, catalog lookup, mesh/solid, source solver or qualification inference.
"""
from __future__ import annotations

import argparse
import _struct
from dataclasses import fields
from fractions import Fraction as F
import json
import math
from pathlib import Path
import platform
import sys
from datetime import datetime, timezone

from pyfoldable.core.airfoil import (AirfoilGeometryError, parse_airfoil_coordinates,
                                    validate_airfoil_definition, airfoil_coordinate_sha256)
from pyfoldable.core.models import AirfoilDefinition
from . import _mixed_profile_contract as contract
from ._mixed_profile_contract import (
    UseScopeV1, EndpointInputV1, ScalarKnotV1, ModelV1, MixedProfileParentRequestV1,
    GeometryExecutionV1, MixedProfileParentReportV1, MixedProfileDecodeError,
    MixedProfileInternalError, MixedProfileReportError, parse_mixed_profile_request,
    canonical_bytes, identified, sha, own_request, own_execution, request_wire, WireError,
)
from ._mixed_profile_exact import (
    GeometryBudgetV1, GeometryBlocked, rat, interpolate, rational_union, maximum, minimum,
    _prove_graphs, _round_certificate, _copied_certificate, trig_enclosures, placement_enclosures,
    rounding_cell, absq,
)

QUALIFICATION={'physical_qualification':False, **{k:'UNESTABLISHED' for k in
               ('manufacturer_equivalence','as_built','solid','clearance','strength','optimum_hinge')}}
SCALAR_FIELDS=('c','beta','tau','Y','Z')


def _scalars(knot):
    return (knot.point.chord_m,knot.point.twist_rad,knot.tau,knot.Y_m,knot.Z_m)


def _require(value, predicate, code='SCALAR_INVALID', field='/'):
    if not value: raise GeometryBlocked(code,predicate,field)


def _validate_model(req):
    m=req.model
    _require(m.method_id==contract.METHOD and m.frame=='shaft_radial_tangential_axial_v1'
             and m.stack_fraction.hex()==.25.hex()
             and all(v.hex()=='0x0.0p+0' for v in m.hardware_offset_m)
             and m.hinge_axis=='positive_shaft_axial' and m.deployed_transforms==('identity','identity')
             and m.actual_joint_modifications=='UNDEFINED'
             and req.endpoint_A.file_format==req.endpoint_B.file_format=='selig',
             'declared supported model/frame/offsets','UNSUPPORTED_MODEL','/model')
    _require(tuple(v.hex() for v in req.hinges_m)==tuple(v.hex() for v in contract.HINGES),
             'exact two declared hinge literals','UNSUPPORTED_HINGES','/hinges_m')


def _validate_scalars(req,b):
    prev_r=b.f(0); prev_index=-1
    lo,hi=map(b.f,req.model.domain_m); a,z=map(b.f,req.model.transition_m)
    for i,k in enumerate(req.scalars):
        r=b.f(k.point.radius_m)
        _require(k.index>prev_index,'strict increasing original indices',field=f'/scalars/{i}/index')
        _require(b.cmp(r,prev_r)>0,'strict increasing scalar radii',field=f'/scalars/{i}/point/radius_m')
        _require(b.cmp(r,F(1,5))<=0,'0 < radius <= 0.2 m',field=f'/scalars/{i}/point/radius_m')
        c,beta,tau,Y,Z=map(b.f,_scalars(k))
        _require(b.cmp(c,0)>0 and b.cmp(c,F(1,5))<=0,'0 < chord <= 0.2 m',field=f'/scalars/{i}/point/chord_m')
        _require(b.cmp(beta,-4)>=0 and b.cmp(beta,4)<=0,'abs(beta) <= 4 rad',field=f'/scalars/{i}/point/twist_rad')
        _require(b.cmp(tau,0)>0 and b.cmp(tau,1)<=0,'0 < tau <= 1',field=f'/scalars/{i}/tau')
        for n,v in (('Y',Y),('Z',Z)):
            _require(b.cmp(v,-F(1,5))>=0 and b.cmp(v,F(1,5))<=0,'abs(Y/Z) <= 0.2 m',field=f'/scalars/{i}/{n}_m')
        prev_r,prev_index=r,k.index
    _require(b.cmp(lo,b.f(req.scalars[0].point.radius_m))==0 and b.cmp(hi,prev_r)==0,
             'domain equals stored knot endpoints',field='/model/domain_m')
    _require(b.cmp(lo,a)<0 and b.cmp(a,z)<0 and b.cmp(z,hi)<0,
             'strict interior transition anchors',field='/model/transition_m')
    for h in req.hinges_m:
        _require(b.cmp(lo,b.f(h))<0 and b.cmp(b.f(h),hi)<0,'hinges strictly inside domain',field='/hinges_m')
    last=None
    for r in req.section_requests_m:
        q=b.f(r)
        _require(b.cmp(q,lo)>=0 and b.cmp(q,hi)<=0 and (last is None or b.cmp(q,last)>0),
                 'ordered section requests inside closed domain',field='/section_requests_m')
        last=q


def _endpoint(endpoint,role,b):
    """Bound before core parser; prove no hidden deduplication/reversal/repair."""
    path='/endpoint_'+role
    lines=[]
    for raw in endpoint.raw_bytes.decode('ascii').splitlines():
        line=raw.split('#',1)[0].strip()
        if line: lines.append(line)
    _require(bool(lines),'coordinate rows present','ENDPOINT_INVALID',path)
    try:
        # Explicit Selig header followed by pairs, or pairs without a header.
        first=lines[0].replace(',',' ').replace(';',' ').split()
        try: is_pair=len(first)==2 and all(math.isfinite(float(x)) for x in first)
        except ValueError: is_pair=False
        source=[]
        for line in lines[0 if is_pair else 1:]:
            tokens=line.replace(',',' ').replace(';',' ').split()
            if len(tokens)!=2: raise ValueError('pair')
            pair=tuple(float(t) for t in tokens)
            if not all(math.isfinite(x) for x in pair): raise ValueError('finite')
            source.append(pair)
            if len(source)>256: raise GeometryBlocked('INPUT_LIMIT','endpoint pair limit',path)
        if len(source)<5: raise ValueError('count')
        obj=parse_airfoil_coordinates(endpoint.raw_bytes.decode('ascii'),airfoil_id=endpoint.identity,
                                     source=endpoint.identity,file_format='selig')
        obj=validate_airfoil_definition(obj)
        xmin=min(x for x,_ in source); xmax=max(x for x,_ in source); chord=xmax-xmin
        if not math.isfinite(chord) or chord<=0: raise ValueError('chord')
        ys=[y for x,y in source if abs(x-xmin)<=chord*1e-7]
        leading=sum(ys)/len(ys)
        expected=tuple(((x-xmin)/chord,(y-leading)/chord) for x,y in source)
        returned=tuple(obj.coordinates)
        same=(len(expected)==len(returned) and all(tuple(x.hex() for x in a)==tuple(x.hex() for x in c)
                                                  for a,c in zip(expected,returned)))
        _require(same and obj.metadata['consecutive_duplicates_removed']==0,
                 'unchanged normalized source count/order/content','ENDPOINT_INVALID',path)
    except (ValueError,ArithmeticError) as exc:
        if isinstance(exc,GeometryBlocked): raise
        # Retain stable actual core boundary rather than its free-form exception text.
        pred='core parser/validator rejection' if isinstance(exc,AirfoilGeometryError) else 'source pair parsing/normalization'
        raise GeometryBlocked('ENDPOINT_INVALID',pred,path) from exc
    _require(all(abs(y)<=1 for _,y in returned),'normalized ordinate bound','ENDPOINT_INVALID',path)
    edges=[i for i,(x,_) in enumerate(returned) if x==0.]
    _require(len(edges)==1 and 0<edges[0]<len(returned)-1,'unique interior leading edge','ENDPOINT_INVALID',path)
    k=edges[0]
    upper=tuple((b.f(x),b.f(y)) for x,y in reversed(returned[:k+1]))
    lower=tuple((b.f(x),b.f(y)) for x,y in returned[k:])
    proofs=_prove_graphs(upper,lower,b,role)
    normalization={'kind':'normalization','content':{'role':role,'input_count':len(source),
                   'returned_count':len(returned),'raw_sha256':sha(endpoint.raw_bytes),
                   'normalized_sha256':airfoil_coordinate_sha256(obj),'reversed':False,'removed_count':0}}
    owned=AirfoilDefinition(id=obj.id,source=obj.source,coordinates=returned,metadata=dict(obj.metadata))
    return owned,upper,lower,normalization,proofs


def _scalar_proofs(req,b):
    records=[]
    for i,(old,new) in enumerate(zip(req.scalars,req.scalars[1:])):
        for field,u,v in zip(SCALAR_FIELDS,_scalars(old),_scalars(new)):
            q,t=b.f(u),b.f(v)
            records.append({'kind':'scalar_cell','content':{'cell_index':i,'field':field,
                            'lo':rat(minimum([q,t],b)),'hi':rat(maximum([q,t],b))}})
    return records


def _weight(r,a,z,b):
    if b.cmp(r,a)<=0: return b.f(0)
    if b.cmp(r,z)>=0: return b.f(1)
    q=b.div(b.sub(r,a),b.sub(z,a)); square=b.mul(q,q)
    return b.sub(b.mul(3,square),b.mul(2,b.mul(square,q)))


def _section(req,r,graphs,grid,parent_sha,b):
    a,z=map(b.f,req.model.transition_m); w=_weight(r,a,z,b)
    exact_knot=None; bracket=None
    for i,k in enumerate(req.scalars):
        if b.cmp(r,b.f(k.point.radius_m))==0: exact_knot=k; break
        if i and b.cmp(r,b.f(k.point.radius_m))<0:
            bracket=(req.scalars[i-1],k); break
    certs=[]; scalar={}; refs={}
    if exact_knot is not None:
        for name,v in zip(SCALAR_FIELDS,_scalars(exact_knot)):
            cert=_copied_certificate(v,b,'rad' if name=='beta' else 'dimensionless' if name=='tau' else 'm')
            certs.append(cert); scalar[name]=v.hex(); refs[name]=b.f(v)
    else:
        if bracket is None: raise GeometryBlocked('PROOF_UNRESOLVED','supported scalar bracket')
        old,new=bracket
        q=b.div(b.sub(r,b.f(old.point.radius_m)),b.sub(b.f(new.point.radius_m),b.f(old.point.radius_m)))
        for name,u,v in zip(SCALAR_FIELDS,_scalars(old),_scalars(new)):
            ref=b.add(b.f(u),b.mul(q,b.sub(b.f(v),b.f(u))))
            cert=_round_certificate(ref,ref,b,'rad' if name=='beta' else 'dimensionless' if name=='tau' else 'm',reference=ref)
            certs.append(cert); scalar[name]=cert['output_hex']; refs[name]=ref
    c,beta,tau,Y,Z=(refs[n] for n in SCALAR_FIELDS)
    blended=[]; gaps=[]
    one=b.sub(1,w)
    for x in grid:
        au,al,bu,bl=(interpolate(graph,x,b) for graph in graphs)
        # Camber and half-thickness, exactly the declared expression.
        m=b.add(b.mul(one,b.div(b.add(au,al),2)),b.mul(w,b.div(b.add(bu,bl),2)))
        h=b.add(b.mul(one,b.div(b.sub(au,al),2)),b.mul(w,b.div(b.sub(bu,bl),2)))
        blended.append((m,h)); gaps.append(b.mul(2,h))
    d=maximum(gaps,b)
    _require(b.cmp(d,0)>0,'positive continuous thickness denominator','PROOF_UNRESOLVED')
    points=[]; trig_cache={}
    for branch in ('upper','lower'):
        for x,(m,h) in zip(grid,blended):
            offset=b.div(b.mul(tau,h),d)
            v=b.add(m,offset) if branch=='upper' else b.sub(m,offset)
            for n in (80,96,112,128):
                if n not in trig_cache: trig_cache[n]=trig_enclosures(beta,n,b)
                xyz=placement_enclosures(r,c,beta,Y,Z,x,v,n,b,trig=trig_cache[n])
                try:
                    xyzcert=[_round_certificate(lo,hi,b,'m',reference=lo if b.cmp(lo,hi)==0 else None,
                                               terms=0 if b.cmp(beta,0)==0 or j==0 else n)
                             for j,(lo,hi) in enumerate(xyz)]
                    break
                except GeometryBlocked as exc:
                    if exc.code!='ROUNDING_UNRESOLVED' or n==128: raise
                    b.retry_count+=1
            points.append({'branch':branch,'x_hex':float(x).hex(),'v_reference':rat(v),
                           'xyz_hex':[cert['output_hex'] for cert in xyzcert],'xyz_certificates':xyzcert})
    content={'schema_id':'mixed_profile_section_v1','parent_sha256':parent_sha,'global_radius_m':float(r).hex(),
             'station_kind':'RETAINED_INPUT_STATION' if exact_knot else 'GENERATED_SECTION',
             'source_index':exact_knot.index if exact_knot else None,
             'bracketing_indices':None if exact_knot else [k.index for k in bracket],
             'scalar_hex':scalar,'scalar_certificates':certs,'blend_weight':rat(w),'points':points}
    return identified(content)


def _build_cuts(req,sections,parent_sha,b):
    """Only reference certified records; same owned budget and hinge identity."""
    results=[]
    for h in req.hinges_m:
        fixed=[]; tip=[]; hinge=None
        for record in sections:
            r=b.f(float.fromhex(record['content']['global_radius_m'])); cmp=b.cmp(r,b.f(h))
            if cmp<=0: fixed.append(record['sha256'])
            if cmp>=0: tip.append(record['sha256'])
            if cmp==0: hinge=record['sha256']
        _require(hinge is not None,'certified shared hinge','PROOF_UNRESOLVED')
        results.append(identified({'parent_sha256':parent_sha,'hinge_m':h.hex(),'hinge_section_sha256':hinge,
                     'fixed_section_sha256s':fixed,'tip_section_sha256s':tip,
                     'hardware_offset_m':[v.hex() for v in req.model.hardware_offset_m],
                     'deployed_transforms':list(req.model.deployed_transforms),
                     'actual_joint_modifications':req.model.actual_joint_modifications}))
    return results


def _content():
    return {'schema_id':'mixed_profile_parent_report_v1','request_sha256':None,'status':'BLOCKED','stage':'REQUEST',
            'diagnostics':[],'inputs':[],'proofs':[],'parent':None,'sections':[],'cuts':[],
            'budget':{},'completed_sections':0,'omitted_sections':0,'qualification':dict(QUALIFICATION)}


def _report(content,execution,b,input_bytes):
    content['budget']={'rational_limit':b.limit,'rational_used':b.used,'integer_bits_limit':b.bits_limit,
       'max_integer_bits':b.max_integer_bits,'max_trig_terms':b.max_trig_terms,'input_bytes':input_bytes,
       'output_bytes':None,'unique_sections':content['completed_sections'],
       'output_points':sum(len(s['content']['points']) for s in content['sections']), 'retry_count':b.retry_count}
    # No geometry recomputation, no per-pass rational/budget reset.
    for _ in range(69):
        content['budget']['output_bytes']=None
        content['budget']['output_bytes']=len(canonical_bytes(content))
        raw=canonical_bytes(content)
        if len(raw)<=contract.OUTPUT_LIMIT: break
        content['status']='BLOCKED'; content['stage']='SERIALIZATION'; content['cuts']=[]
        if not content['diagnostics']:
            content['diagnostics']=[{'code':'OUTPUT_LIMIT','field':'/','predicate':'serialized report limit','details':'serialized report limit'}]
        if not content['sections']: raise MemoryError('Bounded failure receipt exceeds report limit')
        content['sections'].pop(); content['omitted_sections']+=1
        content['budget']['output_points']=sum(len(s['content']['points']) for s in content['sections'])
    else: raise MemoryError('Bounded failure receipt cannot be serialized')
    digest=sha(raw); side=canonical_bytes({'execution':execution,'content_sha256':digest})
    return MixedProfileParentReportV1(raw,digest,side,sha(side))


def evaluate_mixed_profile_parent(request: MixedProfileParentRequestV1, *,
                                  execution: GeometryExecutionV1) -> MixedProfileParentReportV1:
    if type(request) is not MixedProfileParentRequestV1: raise TypeError('request must be MixedProfileParentRequestV1')
    if type(execution) is not GeometryExecutionV1: raise TypeError('execution must be GeometryExecutionV1')
    content=_content(); b=GeometryBudgetV1(); context=None; nbytes=0; snap=None
    try:
        try:
            context=own_execution(execution)
            snap=own_request(request)
        except WireError as exc:
            code=exc.code if exc.code in ('NONFINITE_INPUT','INPUT_LIMIT') else 'INVALID_REQUEST'
            raise GeometryBlocked(code,'valid owned finite request/execution fields',exc.field) from exc
        wire=request_wire(snap); raw=canonical_bytes(wire); nbytes=len(raw)
        _require(nbytes<=contract.REQUEST_LIMIT,'canonical request bytes limit','INPUT_LIMIT')
        content['request_sha256']=sha(raw)
        _validate_model(snap)
        content['stage']='HASHES'
        for role,e in (('A',snap.endpoint_A),('B',snap.endpoint_B)):
            actual=sha(e.raw_bytes)
            _require(actual==e.expected_raw_sha256,'claimed raw digest equals supplied bytes','RAW_HASH_MISMATCH','/endpoint_'+role)
            content['inputs'].append({'role':role,'raw_sha256':actual,'canonical_sha256':None,
                                      'point_or_row_count':0,'use_scope':{'kind':e.use_scope.kind,'reference':e.use_scope.reference}})
        content['stage']='SCALARS'; _validate_scalars(snap,b)
        content['inputs'].append({'role':'scalars','raw_sha256':None,'canonical_sha256':sha(canonical_bytes(wire['scalars'])),
                                  'point_or_row_count':len(snap.scalars),'use_scope':wire['scalar_use_scope']})
        endpoint_data=[]; norms=[]; branches=[]
        for role,e in (('A',snap.endpoint_A),('B',snap.endpoint_B)):
            content['stage']='ENDPOINT_'+role
            obj,up,low,norm,proofs=_endpoint(e,role,b)
            receipt=content['inputs'][0 if role=='A' else 1]
            receipt['canonical_sha256']=airfoil_coordinate_sha256(obj); receipt['point_or_row_count']=len(obj.coordinates)
            endpoint_data.append((obj,up,low)); norms.append(norm); branches.extend(proofs)
            content['proofs']=norms+branches
        content['stage']='PROOFS'
        content['proofs']=norms+branches+_scalar_proofs(snap,b)
        graphs=tuple(g for _,up,low in endpoint_data for g in (up,low))
        grid=rational_union([x for graph in graphs for x,_ in graph],b)
        _require(len(grid)<=512,'common grid point limit','INPUT_LIMIT')
        star=b.f(F(1,2)); ga=b.sub(interpolate(graphs[0],star,b),interpolate(graphs[1],star,b))
        gb=b.sub(interpolate(graphs[2],star,b),interpolate(graphs[3],star,b)); bound=minimum([ga,gb],b)
        _require(b.cmp(bound,0)>0,'uniform positive denominator bound','PROOF_UNRESOLVED')
        content['proofs'].append({'kind':'denominator','content':{'x_star':rat(star),'gap_A':rat(ga),'gap_B':rat(gb),'lower_bound':rat(bound)}})
        manifest={'schema_id':'mixed_profile_parent_manifest_v1','method_id':contract.METHOD,'policy_ids':list(contract.POLICIES),
                  'scalars':wire['scalars'],'scalar_provenance':wire['scalar_provenance'],
                  'scalar_use_scope':wire['scalar_use_scope'],'model':wire['model']}
        for role,e,(obj,_,_) in zip(('A','B'),(snap.endpoint_A,snap.endpoint_B),endpoint_data):
            manifest['endpoint_'+role]={'identity':e.identity,'raw_sha256':sha(e.raw_bytes),
                    'canonical_coordinate_sha256':airfoil_coordinate_sha256(obj),
                    'normalized_points_hex':[[x.hex(),y.hex()] for x,y in obj.coordinates],
                    'use_scope':wire['endpoint_'+role]['use_scope']}
        content['parent']=identified(manifest)
        radii=rational_union([b.f(k.point.radius_m) for k in snap.scalars]+[b.f(x) for x in
                     snap.model.transition_m+snap.hinges_m+snap.section_requests_m],b)
        _require(len(radii)<=68 and len(radii)*2*len(grid)<=69632,'section/output point limit','INPUT_LIMIT')
        content['stage']='SECTIONS'
        for r in radii:
            result=_section(snap,r,graphs,grid,content['parent']['sha256'],b)
            content['sections'].append(result); content['completed_sections']+=1
        content['stage']='CUTS'
        content['cuts']=_build_cuts(snap,content['sections'],content['parent']['sha256'],b)
        content['stage']='SERIALIZATION'
        content['status']='COMPLETE'; content['stage']='COMPLETE'
    except GeometryBlocked as exc:
        content['status']='BLOCKED'; content['cuts']=[]
        content['diagnostics']=[{'code':exc.code,'field':exc.field,'predicate':exc.predicate,'details':exc.predicate}]
    except (MemoryError,KeyboardInterrupt,SystemExit): raise
    except Exception as exc:
        content['status']='BLOCKED'; content['cuts']=[]
        content['diagnostics']=[{'code':'PROOF_UNRESOLVED','field':'/','predicate':'unexpected internal failure','details':'unexpected internal failure'}]
        raise MixedProfileInternalError(None if snap is None else _report(content,context,b,nbytes)) from exc
    return _report(content,context,b,nbytes)


def _validate_report_content(c):
    """Validate supplied report schema/content identities, not recompute geometry."""
    # A separate bounded report-audit transaction, never a reset/replay of
    # the recorded evaluator work budget and never a second parent evaluator.
    audit=GeometryBudgetV1()
    contract.keys(c,tuple(_content()),'/')
    stages=('REQUEST','HASHES','SCALARS','ENDPOINT_A','ENDPOINT_B','PROOFS','SECTIONS','CUTS','SERIALIZATION','COMPLETE')
    if c['schema_id']!='mixed_profile_parent_report_v1' or c['qualification']!=QUALIFICATION:
        raise ValueError('schema')
    if c['status'] not in ('COMPLETE','BLOCKED') or c['stage'] not in stages: raise ValueError('status')
    if (c['status']=='COMPLETE')!=(c['stage']=='COMPLETE'): raise ValueError('stage')
    if c['request_sha256'] is not None: contract.digest(c['request_sha256'],'/request_sha256')
    if c['status']=='COMPLETE' and c['request_sha256'] is None: raise ValueError('complete request identity')
    def integer(v,limit):
        if type(v) is not int or not 0<=v<=limit: raise ValueError('integer')
    def number(h): return contract.f64(h,'/report',True)
    def array(v,limit):
        if type(v) is not list or len(v)>limit: raise ValueError('array')
        return v
    def fraction(q):
        import re
        contract.keys(q,('n','d'),'/rational')
        def dec(s,positive):
            if type(s) is not str or len(s)>19731 or re.fullmatch(r'-?(0|[1-9][0-9]*)',s) is None or s=='-0': raise ValueError('rational')
            negative=s.startswith('-'); digits=s[1:] if negative else s; v=0
            for i in range(0,len(digits),9):
                chunk=digits[i:i+9]; v=v*10**len(chunk)+int(chunk)
                if v.bit_length()>65536: raise ValueError('rational bits')
            v=-v if negative else v
            if positive and v<=0: raise ValueError('denominator')
            return v
        n,d=dec(q['n'],False),dec(q['d'],True)
        if math.gcd(n,d)!=1: raise ValueError('unreduced rational')
        return audit.f(F(n,d))
    certificate_keys=('kind','unit','reference','enclosure_lo','enclosure_hi','output_hex','predecessor_hex',
                      'successor_hex','cell_lo','cell_hi','cell_lo_closed','cell_hi_closed','absolute_error_bound','trig_terms','zero_rule')
    def certificate(q):
        contract.keys(q,certificate_keys,'/certificate')
        if q['kind'] not in ('COPIED_INPUT','CERTIFIED_ROUNDING') or q['unit'] not in ('m','rad','dimensionless'): raise ValueError('certificate')
        values={n:number(q[n]) for n in ('output_hex','predecessor_hex','successor_hex')}
        exact={n:fraction(q[n]) for n in ('enclosure_lo','enclosure_hi','cell_lo','cell_hi','absolute_error_bound')}
        reference=fraction(q['reference']) if q['reference'] is not None else None
        if type(q['cell_lo_closed']) is not bool or type(q['cell_hi_closed']) is not bool: raise ValueError('ownership')
        integer(q['trig_terms'],128)
        if q['zero_rule'] not in ('PRESERVE_INPUT_SIGN','EXACT_ZERO_POSITIVE','SIGNED_UNDERFLOW','NOT_ZERO'): raise ValueError('zero')
        lo,hi=exact['enclosure_lo'],exact['enclosure_hi']; output=values['output_hex']; v=audit.f(output)
        if audit.cmp(lo,hi)>0 or audit.cmp(exact['absolute_error_bound'],0)<0: raise ValueError('certificate bounds')
        if reference is not None and (audit.cmp(lo,reference)>0 or audit.cmp(reference,hi)>0): raise ValueError('reference containment')
        if q['predecessor_hex']!=math.nextafter(output,-math.inf).hex() or q['successor_hex']!=math.nextafter(output,math.inf).hex(): raise ValueError('neighbors')
        if q['kind']=='COPIED_INPUT':
            if reference is None or any(audit.cmp(x,v)!=0 for x in (reference,lo,hi,exact['cell_lo'],exact['cell_hi'])) or audit.cmp(exact['absolute_error_bound'],0)!=0:
                raise ValueError('copied certificate')
            if q['trig_terms']!=0 or not q['cell_lo_closed'] or not q['cell_hi_closed']: raise ValueError('copied cell')
            if q['zero_rule']!=('PRESERVE_INPUT_SIGN' if output==0 else 'NOT_ZERO'): raise ValueError('copy zero')
        else:
            _,_,cl,ch,lc,hc=rounding_cell(output,audit)
            if audit.cmp(cl,exact['cell_lo'])!=0 or audit.cmp(ch,exact['cell_hi'])!=0 or lc!=q['cell_lo_closed'] or hc!=q['cell_hi_closed']: raise ValueError('actual rounding cell')
            l,h=audit.cmp(lo,cl),audit.cmp(hi,ch)
            if l<0 or h>0 or l==0 and not lc or h==0 and not hc: raise ValueError('cell ownership')
            err=maximum([absq(audit.sub(v,lo),audit),absq(audit.sub(v,hi),audit)],audit)
            if audit.cmp(err,exact['absolute_error_bound'])!=0: raise ValueError('error displacement')
            if output==0:
                exact_zero=audit.cmp(lo,0)==0 and audit.cmp(hi,0)==0
                if q['zero_rule']!=('EXACT_ZERO_POSITIVE' if exact_zero else 'SIGNED_UNDERFLOW') or exact_zero and output.hex().startswith('-'): raise ValueError('new zero')
            elif q['zero_rule']!='NOT_ZERO': raise ValueError('nonzero rule')
    diags=array(c['diagnostics'],1)
    if len(diags)!=(0 if c['status']=='COMPLETE' else 1): raise ValueError('diagnostic count')
    for d in diags:
        contract.keys(d,('code','field','predicate','details'),'/diagnostic')
        for v in d.values(): contract.text(v,'/diagnostic',2048)
    inputs=array(c['inputs'],3)
    roles=[]
    for q in inputs:
        contract.keys(q,('role','raw_sha256','canonical_sha256','point_or_row_count','use_scope'),'/input')
        roles.append(q['role']); integer(q['point_or_row_count'],256)
        for n in ('raw_sha256','canonical_sha256'):
            if q[n] is not None: contract.digest(q[n],'/input/'+n)
        contract._scope(q['use_scope'],'/input/use_scope',True)
    if roles!=sorted(set(roles),key=lambda r:('A','B','scalars').index(r)): raise ValueError('receipt order')
    proof_keys={'normalization':('role','input_count','returned_count','raw_sha256','normalized_sha256','reversed','removed_count'),
       'branch_cell':('role','cell_index','x_l','x_r','gap_l','gap_r'),
       'scalar_cell':('cell_index','field','lo','hi'),'denominator':('x_star','gap_A','gap_B','lower_bound')}
    proofs=array(c['proofs'],1400)
    for p in proofs:
        contract.keys(p,('kind','content'),'/proof')
        if p['kind'] not in proof_keys: raise ValueError('proof kind')
        contract.keys(p['content'],proof_keys[p['kind']],'/proof/content')
        pc=p['content']
        if p['kind']=='normalization':
            if pc['role'] not in ('A','B') or type(pc['reversed']) is not bool: raise ValueError('normalization role/flag')
            for n in ('input_count','returned_count','removed_count'): integer(pc[n],256)
            for n in ('raw_sha256','normalized_sha256'): contract.digest(pc[n],'/proof/'+n)
            if pc['reversed'] or pc['removed_count'] or pc['input_count']!=pc['returned_count']: raise ValueError('normalization correspondence')
        elif p['kind']=='branch_cell':
            if pc['role'] not in ('A','B'): raise ValueError('branch proof role')
            integer(pc['cell_index'],511)
            xl,xr,gl,gr=(fraction(pc[n]) for n in ('x_l','x_r','gap_l','gap_r'))
            if audit.cmp(xl,xr)>=0 or audit.cmp(xl,0)<0 or audit.cmp(xr,1)>0 or audit.cmp(gl,0)<0 or audit.cmp(gr,0)<0: raise ValueError('branch cell')
            if audit.cmp(xl,0)>0 and audit.cmp(gl,0)<=0 or audit.cmp(xr,1)<0 and audit.cmp(gr,0)<=0: raise ValueError('interior branch gap')
        elif p['kind']=='scalar_cell':
            integer(pc['cell_index'],62)
            if pc['field'] not in SCALAR_FIELDS: raise ValueError('scalar proof field')
            if audit.cmp(fraction(pc['lo']),fraction(pc['hi']))>0: raise ValueError('scalar proof bounds')
        else:
            for n in proof_keys[p['kind']]: fraction(pc[n])
            if audit.cmp(fraction(pc['x_star']),F(1,2))!=0 or audit.cmp(fraction(pc['lower_bound']),0)<=0: raise ValueError('denominator proof')
    parent=c['parent']
    if parent is not None:
        if c['stage'] not in ('PROOFS','SECTIONS','CUTS','SERIALIZATION','COMPLETE'):
            raise ValueError('parent admission stage')
        contract.keys(parent,('sha256','content'),'/parent')
        if identified(parent['content'])!=parent: raise ValueError('parent identity')
        contract.keys(parent['content'],('schema_id','method_id','policy_ids','endpoint_A','endpoint_B','scalars','scalar_provenance','scalar_use_scope','model'),'/parent/content')
        if parent['content']['schema_id']!='mixed_profile_parent_manifest_v1' or parent['content']['method_id']!=contract.METHOD or parent['content']['policy_ids']!=list(contract.POLICIES): raise ValueError('parent policy')
        pm=parent['content']; endpoints={}
        for role in ('A','B'):
            e=pm['endpoint_'+role]
            contract.keys(e,('identity','raw_sha256','canonical_coordinate_sha256','normalized_points_hex','use_scope'),'/parent/endpoint_'+role)
            contract.text(e['identity'],'/parent/identity')
            for n in ('raw_sha256','canonical_coordinate_sha256'): contract.digest(e[n],'/parent/'+n)
            coords=[]
            for pair in array(e['normalized_points_hex'],256):
                if len(array(pair,2))!=2: raise ValueError('coordinate pair')
                x,y=map(number,pair)
                if not 0<=x<=1 or not -1<=y<=1: raise ValueError('normalized coordinate bounds')
                coords.append((x,y))
            if len(coords)<5: raise ValueError('coordinate count')
            coord_hash=sha('\n'.join(f'{x:.17g},{y:.17g}' for x,y in coords).encode('ascii'))
            if coord_hash!=e['canonical_coordinate_sha256']: raise ValueError('coordinate identity')
            contract._scope(e['use_scope'],'/parent/use_scope',True)
            # Wire-schema audit only: this placeholder is not parsed, measured,
            # hashed as a source, or used by a geometry evaluator.
            endpoints['endpoint_'+role]={'identity':e['identity'],'raw_text':'report schema audit',
                    'file_format':'selig','expected_raw_sha256':e['raw_sha256'],'use_scope':e['use_scope']}
        audit_request=own_request({'schema_id':'mixed_profile_parent_request_v1','scenario_id':'report-schema-audit',
                 **endpoints,'scalars':pm['scalars'],'scalar_provenance':pm['scalar_provenance'],
                 'scalar_use_scope':pm['scalar_use_scope'],'model':pm['model'],
                 'hinges_m':[h.hex() for h in contract.HINGES],'section_requests_m':[]},decoding=True)
        _validate_model(audit_request); _validate_scalars(audit_request,audit)
        parent_knots=tuple(audit_request.scalars)

        # A parent is admitted only after all input/proof gates have completed.
        # Later BLOCKED stages retain that earlier admission evidence; earlier
        # parent-null failures retain their legitimately incomplete prefixes.
        if parent is not None:
            if roles!=['A','B','scalars']: raise ValueError('complete receipt coverage')
            receipts={q['role']:q for q in inputs}
            for role in ('A','B'):
                receipt=receipts[role]; endpoint=pm['endpoint_'+role]
                if (receipt['raw_sha256']!=endpoint['raw_sha256']
                    or receipt['canonical_sha256']!=endpoint['canonical_coordinate_sha256']
                    or receipt['point_or_row_count']!=len(endpoint['normalized_points_hex'])
                    or receipt['use_scope']!=endpoint['use_scope']):
                    raise ValueError('endpoint receipt correspondence')
            scalar_receipt=receipts['scalars']
            if (scalar_receipt['raw_sha256'] is not None
                or scalar_receipt['canonical_sha256']!=sha(canonical_bytes(pm['scalars']))
                or scalar_receipt['point_or_row_count']!=len(pm['scalars'])
                or scalar_receipt['use_scope']!=pm['scalar_use_scope']):
                raise ValueError('scalar receipt correspondence')

            pos=0
            for role in ('A','B'):
                if pos>=len(proofs): raise ValueError('normalization proof coverage')
                p=proofs[pos]; pc=p['content']; endpoint=pm['endpoint_'+role]
                if (p['kind']!='normalization' or pc['role']!=role
                    or pc['input_count']!=len(endpoint['normalized_points_hex'])
                    or pc['returned_count']!=len(endpoint['normalized_points_hex'])
                    or pc['raw_sha256']!=endpoint['raw_sha256']
                    or pc['normalized_sha256']!=endpoint['canonical_coordinate_sha256']
                    or pc['reversed'] or pc['removed_count']!=0):
                    raise ValueError('normalization proof correspondence')
                pos+=1

            branch_cells={}
            for role in ('A','B'):
                endpoint=pm['endpoint_'+role]
                # Audit the supplied proof against its retained represented
                # coordinates, never parse assets or evaluate parent sections.
                coords=tuple(tuple(audit.f(number(v)) for v in pair)
                             for pair in endpoint['normalized_points_hex'])
                leading=[i for i,(x,_) in enumerate(coords) if audit.cmp(x,0)==0]
                if len(leading)!=1 or not 0<leading[0]<len(coords)-1:
                    raise ValueError('branch leading edge')
                edge=leading[0]
                upper,lower=tuple(reversed(coords[:edge+1])),coords[edge:]
                for branch in (upper,lower):
                    if (audit.cmp(branch[0][0],0)!=0 or audit.cmp(branch[-1][0],1)!=0
                        or audit.cmp(branch[0][1],0)!=0):
                        raise ValueError('branch proof support')
                    for old,new in zip(branch,branch[1:]):
                        if audit.cmp(old[0],new[0])>=0: raise ValueError('branch coordinate ordering')
                xs=rational_union([x for branch in (upper,lower) for x,_ in branch],audit)
                cells=[]
                for cell_index,(xl,xr) in enumerate(zip(xs,xs[1:])):
                    if pos>=len(proofs): raise ValueError('branch proof coverage')
                    p=proofs[pos]; pc=p['content']
                    pl,pr,gl,gr=(fraction(pc[n]) for n in ('x_l','x_r','gap_l','gap_r'))
                    if (p['kind']!='branch_cell' or pc['role']!=role
                        or pc['cell_index']!=cell_index
                        or audit.cmp(pl,xl)!=0 or audit.cmp(pr,xr)!=0):
                        raise ValueError('branch proof correspondence')
                    for x,gap in ((xl,gl),(xr,gr)):
                        represented_gap=audit.sub(interpolate(upper,x,audit),interpolate(lower,x,audit))
                        if audit.cmp(gap,represented_gap)!=0:
                            raise ValueError('branch gap coordinate correspondence')
                    if cells and audit.cmp(cells[-1][3],gl)!=0:
                        raise ValueError('branch proof continuity')
                    cells.append((pl,pr,gl,gr))
                    pos+=1
                branch_cells[role]=cells

            for cell_index,(old,new) in enumerate(zip(parent_knots,parent_knots[1:])):
                for field,u,v in zip(SCALAR_FIELDS,_scalars(old),_scalars(new)):
                    if pos>=len(proofs): raise ValueError('scalar proof coverage')
                    p=proofs[pos]; pc=p['content']
                    lo,hi=sorted((audit.f(u),audit.f(v)))
                    if (p['kind']!='scalar_cell' or pc['cell_index']!=cell_index
                        or pc['field']!=field
                        or audit.cmp(fraction(pc['lo']),lo)!=0
                        or audit.cmp(fraction(pc['hi']),hi)!=0):
                        raise ValueError('scalar proof correspondence')
                    pos+=1

            if pos>=len(proofs) or proofs[pos]['kind']!='denominator':
                raise ValueError('denominator proof coverage')
            denominator=proofs[pos]['content']
            star=fraction(denominator['x_star'])
            gap_a,gap_b,lower=(fraction(denominator[n]) for n in ('gap_A','gap_B','lower_bound'))
            expected_gaps=[]
            for role in ('A','B'):
                expected_gap=None
                for xl,xr,gl,gr in branch_cells[role]:
                    if audit.cmp(star,xl)>=0 and audit.cmp(star,xr)<=0:
                        if audit.cmp(star,xl)==0: expected_gap=gl
                        elif audit.cmp(star,xr)==0: expected_gap=gr
                        else:
                            q=audit.div(audit.sub(star,xl),audit.sub(xr,xl))
                            expected_gap=audit.add(gl,audit.mul(q,audit.sub(gr,gl)))
                        break
                if expected_gap is None: raise ValueError('denominator cell coverage')
                expected_gaps.append(expected_gap)
            expected_lower=gap_a if audit.cmp(gap_a,gap_b)<=0 else gap_b
            if (audit.cmp(star,F(1,2))!=0
                or audit.cmp(gap_a,expected_gaps[0])!=0
                or audit.cmp(gap_b,expected_gaps[1])!=0
                or audit.cmp(lower,expected_lower)!=0 or audit.cmp(lower,0)<=0):
                raise ValueError('denominator proof correspondence')
            pos+=1
            if pos!=len(proofs): raise ValueError('proof ordering/coverage')
    if c['status']=='COMPLETE' and parent is None: raise ValueError('complete parent')
    known={}; total=0; prior_radius=None
    for record in array(c['sections'],68):
        contract.keys(record,('sha256','content'),'/section')
        if identified(record['content'])!=record: raise ValueError('section digest')
        s=record['content']
        contract.keys(s,('schema_id','parent_sha256','global_radius_m','station_kind','source_index','bracketing_indices','scalar_hex','scalar_certificates','blend_weight','points'),'/section/content')
        if s['schema_id']!='mixed_profile_section_v1' or parent is None or s['parent_sha256']!=parent['sha256']: raise ValueError('section lineage')
        r=audit.f(number(s['global_radius_m']))
        if prior_radius is not None and audit.cmp(r,prior_radius)<=0: raise ValueError('section radius order')
        if audit.cmp(r,audit.f(audit_request.model.domain_m[0]))<0 or audit.cmp(r,audit.f(audit_request.model.domain_m[1]))>0: raise ValueError('section domain')
        prior_radius=r
        if s['station_kind'] not in ('RETAINED_INPUT_STATION','GENERATED_SECTION'): raise ValueError('station kind')
        if s['source_index'] is not None: integer(s['source_index'],2**63-1)
        if s['bracketing_indices'] is not None:
            if len(array(s['bracketing_indices'],2))!=2: raise ValueError('bracket')
            for n in s['bracketing_indices']: integer(n,2**63-1)
        if (s['station_kind']=='RETAINED_INPUT_STATION')!=(s['source_index'] is not None) or (s['station_kind']=='GENERATED_SECTION')!=(s['bracketing_indices'] is not None): raise ValueError('station source labels')
        contract.keys(s['scalar_hex'],SCALAR_FIELDS,'/section/scalars')
        for h in s['scalar_hex'].values(): number(h)
        if len(array(s['scalar_certificates'],5))!=5: raise ValueError('scalar certificates')
        for name,q in zip(SCALAR_FIELDS,s['scalar_certificates']):
            certificate(q)
            if q['output_hex']!=s['scalar_hex'][name]: raise ValueError('scalar output correspondence')
            if q['unit']!=('rad' if name=='beta' else 'dimensionless' if name=='tau' else 'm') or q['kind']!=('COPIED_INPUT' if s['station_kind']=='RETAINED_INPUT_STATION' else 'CERTIFIED_ROUNDING'): raise ValueError('scalar certificate role')
        if s['station_kind']=='RETAINED_INPUT_STATION':
            matches=[k for k in parent_knots if audit.cmp(r,audit.f(k.point.radius_m))==0]
            if len(matches)!=1 or s['source_index']!=matches[0].index:
                raise ValueError('retained parent row')
            expected=tuple(v.hex() for v in _scalars(matches[0]))
            for name,q,h in zip(SCALAR_FIELDS,s['scalar_certificates'],expected):
                if s['scalar_hex'][name]!=h or q['output_hex']!=h:
                    raise ValueError('retained scalar correspondence')
        else:
            expected_bracket=None
            for old,new in zip(parent_knots,parent_knots[1:]):
                if (audit.cmp(audit.f(old.point.radius_m),r)<0
                    and audit.cmp(r,audit.f(new.point.radius_m))<0):
                    expected_bracket=[old.index,new.index]
                    break
            if expected_bracket is None or s['bracketing_indices']!=expected_bracket:
                raise ValueError('generated parent bracket')
        fraction(s['blend_weight'])
        points=array(s['points'],1024); total+=len(points)
        for p in points:
            contract.keys(p,('branch','x_hex','v_reference','xyz_hex','xyz_certificates'),'/point')
            if p['branch'] not in ('upper','lower'): raise ValueError('branch')
            number(p['x_hex']); fraction(p['v_reference'])
            if len(array(p['xyz_hex'],3))!=3 or len(array(p['xyz_certificates'],3))!=3: raise ValueError('point tuple')
            for h in p['xyz_hex']: number(h)
            for h,q in zip(p['xyz_hex'],p['xyz_certificates']):
                certificate(q)
                if q['output_hex']!=h or q['unit']!='m' or q['kind']!='CERTIFIED_ROUNDING': raise ValueError('coordinate output correspondence')
            radial=p['xyz_certificates'][0]
            if p['xyz_hex'][0]!=s['global_radius_m'] or radial['reference'] is None:
                raise ValueError('point radial correspondence')
            if (audit.cmp(fraction(radial['reference']),r)!=0
                or audit.cmp(fraction(radial['enclosure_lo']),r)!=0
                or audit.cmp(fraction(radial['enclosure_hi']),r)!=0
                or radial['trig_terms']!=0):
                raise ValueError('point radial certificate')
        known[record['sha256']]=s
    if total>69632: raise ValueError('point count')
    cuts=array(c['cuts'],2)
    if c['status']=='COMPLETE' and len(cuts)!=2 or c['status']=='BLOCKED' and cuts: raise ValueError('cuts')
    for cut_index,record in enumerate(cuts):
        contract.keys(record,('sha256','content'),'/cut')
        if identified(record['content'])!=record: raise ValueError('cut digest')
        q=record['content']; contract.keys(q,('parent_sha256','hinge_m','hinge_section_sha256','fixed_section_sha256s','tip_section_sha256s','hardware_offset_m','deployed_transforms','actual_joint_modifications'),'/cut/content')
        if parent is None or q['parent_sha256']!=parent['sha256']: raise ValueError('cut lineage')
        number(q['hinge_m'])
        if q['hinge_m']!=contract.HINGES[cut_index].hex() or q['hardware_offset_m']!=['0x0.0p+0']*3 or q['deployed_transforms']!=['identity']*2 or q['actual_joint_modifications']!='UNDEFINED': raise ValueError('cut model fields')
        for n in ('fixed_section_sha256s','tip_section_sha256s'):
            for h in array(q[n],68):
                if h not in known: raise ValueError('unknown section')
        if not q['fixed_section_sha256s'] or not q['tip_section_sha256s'] or q['fixed_section_sha256s'][-1]!=q['hinge_section_sha256'] or q['tip_section_sha256s'][0]!=q['hinge_section_sha256']: raise ValueError('shared hinge')
        fixed=[]; tip=[]; h=audit.f(number(q['hinge_m']))
        for identity,s in known.items():
            sign=audit.cmp(audit.f(number(s['global_radius_m'])),h)
            if sign<=0: fixed.append(identity)
            if sign>=0: tip.append(identity)
        if fixed!=q['fixed_section_sha256s'] or tip!=q['tip_section_sha256s']: raise ValueError('complementary restriction')
    contract.keys(c['budget'],('rational_limit','rational_used','integer_bits_limit','max_integer_bits','max_trig_terms','input_bytes','output_bytes','unique_sections','output_points','retry_count'),'/budget')
    for n,v in c['budget'].items(): integer(v,20_000_000 if n!='input_bytes' else 4*1024*1024)
    bv=c['budget']
    if bv['rational_limit']!=20_000_000 or bv['integer_bits_limit']!=65536 or bv['rational_used']>bv['rational_limit'] or bv['max_integer_bits']>bv['integer_bits_limit'] or bv['max_trig_terms'] not in (0,80,96,112,128): raise ValueError('budget limits')
    for n in ('completed_sections','omitted_sections'): integer(c[n],68)
    if len(c['sections'])+c['omitted_sections']!=c['completed_sections'] or total!=bv['output_points'] or bv['unique_sections']!=c['completed_sections']: raise ValueError('counts')
    projection={**c,'budget':{**c['budget'],'output_bytes':None}}
    if c['budget']['output_bytes']!=len(canonical_bytes(projection)): raise ValueError('byte count')


def render_mixed_profile_table(report: MixedProfileParentReportV1) -> str:
    if type(report) is not MixedProfileParentReportV1: raise TypeError('report must be MixedProfileParentReportV1')
    try:
        if type(report.canonical_json) is not bytes or len(report.canonical_json)>contract.OUTPUT_LIMIT:
            raise ValueError('bytes')
        c=json.loads(report.canonical_json)
        if canonical_bytes(c)!=report.canonical_json or sha(report.canonical_json)!=report.sha256:
            raise ValueError('digest')
        _validate_report_content(c)
        # 48 paths * 2048 ASCII bytes * 6 JSON escape bytes, plus digests,
        # bounded context fields and syntax, is below 1 MiB. ASCII controls
        # remain supported; a displayed-character count is not a byte bound.
        if type(report.execution_json) is not bytes or len(report.execution_json)>1024*1024:
            raise ValueError('sidecar bytes')
        side=json.loads(report.execution_json)
        if canonical_bytes(side)!=report.execution_json or sha(report.execution_json)!=report.execution_sha256 or side['content_sha256']!=report.sha256:
            raise ValueError('sidecar')
        contract.keys(side,('execution','content_sha256'),'/sidecar')
        if side['execution'] is not None:
            e=side['execution']
            contract.keys(e,tuple(f.name for f in fields(GeometryExecutionV1)),'/execution')
            pairs={}
            for key in ('code_sha256','binary_sha256'):
                if type(e[key]) is not list or len(e[key])>(32 if key=='code_sha256' else 16): raise ValueError('execution pairs')
                if any(type(pair) is not list or len(pair)!=2 for pair in e[key]): raise ValueError('execution pair')
                pairs[key]=tuple(tuple(pair) for pair in e[key])
            observed=own_execution(GeometryExecutionV1(**{**e,**pairs}))
            if canonical_bytes(observed)!=canonical_bytes(e): raise ValueError('execution schema')
        rows=['First-party/caller-declared generated geometry; physical_qualification=false',
              f"Status: {c['status']} ({c['stage']})",f"Content SHA-256: {report.sha256}",
              'radius_m | kind | source/bracket | chord_m | twist_rad | exact radius hex | chord hex | twist hex']
        for r in c['sections']:
            if identified(r['content'])!=r: raise ValueError('section digest')
            s=r['content']; sc=s['scalar_hex']
            def display(h):
                v=float.fromhex(h)
                return '-0 (negative zero)' if v==0 and h.startswith('-') else format(v,'.17g')
            rows.append(' | '.join((display(s['global_radius_m']),s['station_kind'],str(s['source_index'] if s['source_index'] is not None else s['bracketing_indices']),
                        display(sc['c']),display(sc['beta']),s['global_radius_m'],sc['c'],sc['beta'])))
        for cut in c['cuts']:
            if identified(cut['content'])!=cut: raise ValueError('cut digest')
            v=cut['content']
            rows.append(f"Cut {v['hinge_m']}: fixed={len(v['fixed_section_sha256s'])}, tip={len(v['tip_section_sha256s'])}; shared hinge={v['hinge_section_sha256']}")
        for d in c['diagnostics']: rows.append(f"BLOCKED: {d['code']} {d['field']} {d['predicate']}")
        rows.append('Solid, clearance, strength, manufacturer/as-built equivalence and optimum hinge: UNESTABLISHED')
        return '\n'.join(rows)+'\n'
    except (ValueError,KeyError,TypeError,RecursionError,OverflowError) as exc:
        raise MixedProfileReportError() from exc


def _main(argv=None):
    p=argparse.ArgumentParser(description='Local caller-input mixed-profile section report; no CAD/solver/qualification.')
    p.add_argument('request'); p.add_argument('--json',required=True); p.add_argument('--table',required=True); p.add_argument('--execution',required=True)
    a=p.parse_args(argv)
    # Trusted local paths, bounded transport read. No download or catalog fallback.
    with Path(a.request).open('rb') as f: raw=f.read(contract.REQUEST_LIMIT+1)
    req=parse_mixed_profile_request(raw)
    root=Path(__file__).resolve().parents[1]
    paths=(Path(__file__),Path(contract.__file__),Path(__file__).with_name('_mixed_profile_exact.py'),
           Path(__file__).with_name('blade_stations.py'),root/'core/airfoil.py',root/'core/models.py')
    code=tuple(sorted((str(x.relative_to(root)),sha(x.read_bytes())) for x in paths))
    runtime=Path(sys.executable)
    binaries=[runtime]
    for module in (math,_struct):
        module_path=getattr(module,'__file__',None)
        if module_path is not None: binaries.append(Path(module_path))
    binary_ids=tuple(sorted((str(x.resolve()),sha(x.read_bytes())) for x in binaries))
    context=GeometryExecutionV1('local-caller-input',datetime.now(timezone.utc).isoformat(),
              sys.version,platform.platform(),code,binary_ids,'nearest-ties-even-rational-certificate')
    report=evaluate_mixed_profile_parent(req,execution=context)
    Path(a.json).write_bytes(report.canonical_json); Path(a.execution).write_bytes(report.execution_json)
    Path(a.table).write_text(render_mixed_profile_table(report),encoding='ascii',newline='')
    return 0 if json.loads(report.canonical_json)['status']=='COMPLETE' else 2


if __name__=='__main__':
    raise SystemExit(_main())
