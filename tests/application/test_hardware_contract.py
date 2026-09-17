"""Strict source-bound hardware software fixtures."""
import copy
import hashlib
import json
import pytest
from pyfoldable.application.hardware_contract import load_hardware_json


def payload():
    return {'schema_version':'pyfoldable.hardware.v1','units':'mm',
        'provenance':{'kind':'synthetic','source':'Analytical test fixture','revision':'v1','source_sha256':'a'*64},
        'bodies':[{'name':'hub','binding':'hub','frame':'body_local',
          'transform':{'rotation':[[1,0,0],[0,1,0],[0,0,1]],'translation':[0,0,0]},
          'tolerance':.01,'geometry':{'kind':'finite_cylinder','radius':10,'height':20,'segments':16,'approximation_tolerance':.3}}]}


def load(p):
    return load_hardware_json(json.dumps(p).encode())


def test_units_identity_and_immutable_source_bound_bundle():
    p=payload();r=load(p)
    assert r.bodies[0].tolerance_m == .00001
    assert r.bodies[0].solid.approximation_error_m < .0003
    assert r.raw_sha256 == hashlib.sha256(json.dumps(p).encode()).hexdigest()
    p['provenance']['revision']='v2'
    assert load(p).canonical_sha256 != r.canonical_sha256


@pytest.mark.parametrize('change',[
    lambda p:p.update(extra=1), lambda p:p.update(units='inch?'),
    lambda p:p['provenance'].update(source=''),lambda p:p['provenance'].update(source_sha256='bad'),
    lambda p:p['bodies'][0].update(binding='blade_99_tip'),
    lambda p:p['bodies'][0].update(frame='world'),lambda p:p['bodies'][0].update(tolerance=True),
    lambda p:p['bodies'][0]['geometry'].update(radius=float('nan')),
    lambda p:p['bodies'][0]['geometry'].update(height=-1),
    lambda p:p['bodies'][0]['transform'].update(rotation=[[1,0,0],[0,1,0],[0,0,-1]]),
    lambda p:p['bodies'].append(copy.deepcopy(p['bodies'][0])),
])
def test_invalid_contract_rejected(change):
    p=payload();change(p)
    with pytest.raises(ValueError):load(p)


def test_duplicate_keys_and_byte_budget_rejected():
    with pytest.raises(ValueError):load_hardware_json(b'{"schema_version":1,"schema_version":2}')
    with pytest.raises(ValueError):load_hardware_json(b' '*262145)


def test_polyhedron_binding_and_declared_transform_are_applied():
    from pyfoldable.application.hardware_contract import body_to_solid
    p=payload();body=p['bodies'][0]
    body['binding']='blade_1_tip'
    body['geometry']={'kind':'convex_polyhedron','vertices':[[0,0,0],[1,0,0],[0,1,0],[0,0,1]],
        'faces':[[0,2,1],[0,1,3],[0,3,2],[1,2,3]]}
    body['transform']['translation']=[10,0,0]
    bundle=load(p)
    assert body_to_solid(bundle.bodies[0]).vertices[0] == (.01,0.,0.)
    body['binding']='blade_0_tip'
    with pytest.raises(ValueError):load(p)


def test_no_implicit_tolerance_and_invalid_frame_binding():
    p=payload();del p['bodies'][0]['tolerance']
    with pytest.raises(ValueError):load(p)
    p=payload();p['bodies'][0]['binding']='blade_1_root'
    with pytest.raises(ValueError):load(p)
