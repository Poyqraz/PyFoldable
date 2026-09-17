"""Source-bound declared hardware and continuous-motion application gates."""
import json
from dataclasses import replace
import pytest
from test_hardware_contract import payload
from test_polar_upload import draft
from pyfoldable.application.surface_clearance import SurfaceClearanceInputs, prepare_surface_clearance, run_surface_clearance


def raw(radius=18., revision='v1'):
    data = payload()
    data['provenance']['revision'] = revision
    data['bodies'][0]['geometry'].update(radius=radius, approximation_tolerance=.5)
    return json.dumps(data).encode()


def request(**kwargs):
    return prepare_surface_clearance(draft(), SurfaceClearanceInputs(end_angle_deg=-10., **kwargs), hardware_json=raw())


def test_optional_finite_hub_is_source_bound_and_replaces_only_infinite_hub():
    req = request(max_hardware_queries=32)
    context = json.loads(req.context_json)
    assert context['hardware']['provenance']['kind'] == 'synthetic'
    assert context['hub_obstacle'] == 'declared_finite_cylinder'
    doc = json.loads(run_surface_clearance(req).report_json)
    assert doc['hardware_queries'] <= 32
    assert all(q['kind'] != 'hub' for q in doc['queries'])
    assert any(q['kind'] == 'hardware_surface' for q in doc['queries'])
    assert doc['full_propeller_clearance'] is None and not doc['physical_qualification']
    assert doc['hardware_status'] in ('unknown','separated','violation')
    assert req != prepare_surface_clearance(req.draft,req.inputs,hardware_json=raw(revision='v2'))


def test_zero_hardware_budget_retains_unknown_queries_and_is_deterministic():
    req = request(max_hardware_queries=0)
    a = run_surface_clearance(req)
    assert a == run_surface_clearance(req)
    doc = json.loads(a.report_json)
    assert doc['hardware_queries'] == 0 and doc['hardware_status'] == 'unknown'
    assert all(q['result']['status']=='unknown' for q in doc['queries'] if q['kind'].startswith('hardware'))


def test_hardware_geometry_must_match_active_hub_and_valid_blade_binding():
    with pytest.raises(ValueError,match='radius'):
        prepare_surface_clearance(draft(),SurfaceClearanceInputs(),hardware_json=raw(radius=10.))
    data=json.loads(raw());data['bodies'][0]['transform']['translation'][0]=1.
    with pytest.raises(ValueError,match='axis'):
        prepare_surface_clearance(draft(),SurfaceClearanceInputs(),hardware_json=json.dumps(data).encode())


def test_hardware_bytes_cannot_be_replaced_after_preparation():
    req=request()
    with pytest.raises(ValueError,match='identity'):
        run_surface_clearance(replace(req,hardware_json=raw(revision='changed')))


def test_hardware_motion_static_separation_and_penetration():
    from pyfoldable.application.hardware_clearance import MotionShape, query_motion_pair
    from pyfoldable.geometry.hardware import ConvexSolid
    from pyfoldable.geometry.surface_clearance import SurfacePart
    vertices=((0.,0.,0.),(1.,0.,0.),(0.,1.,0.),(0.,0.,1.))
    faces=((0,2,1),(0,1,3),(0,3,2),(1,2,3))
    solid=MotionShape('tetra',solid=ConvexSolid(vertices,faces))
    point=SurfacePart('inside',(((.1,.1,.1),)*3,))
    inside=MotionShape.from_part(point)
    r=query_motion_pair(inside,solid,angle_min_rad=-1.,angle_max_rad=0.,clearance_m=0.,max_queries=100,max_depth=2,max_intervals=7)
    assert r['status']=='violation' and r['contact_status']=='penetrating'
    outside=MotionShape.from_part(SurfacePart('outside',(((2.,2.,2.),)*3,)))
    r=query_motion_pair(outside,solid,angle_min_rad=-1.,angle_max_rad=0.,clearance_m=.1,max_queries=10,max_depth=2,max_intervals=7)
    assert r['status']=='separated' and r['lower_bound_m']>.1


def test_motion_interval_budget_preserves_full_unknown_path():
    from pyfoldable.application.hardware_clearance import MotionShape, query_motion_pair
    from pyfoldable.geometry.hardware import finite_cylinder
    from pyfoldable.geometry.surface_clearance import SurfacePart
    solid=MotionShape('c',solid=finite_cylinder(radius_m=1.,height_m=2.,segments=8,approximation_tolerance_m=.1))
    part=MotionShape.from_part(SurfacePart('p',(((1.,0.,0.),)*3,), moving=True))
    r=query_motion_pair(part,solid,angle_min_rad=-1.,angle_max_rad=0.,clearance_m=0.,max_queries=1,max_depth=2,max_intervals=7)
    rows=sorted(r['intervals'],key=lambda x:x['angle_min_rad'])
    assert r['status']=='unknown' and r['hardware_queries']<=1
    assert rows[0]['angle_min_rad']==-1 and rows[-1]['angle_max_rad']==0
    assert all(a['angle_max_rad']==b['angle_min_rad'] for a,b in zip(rows,rows[1:]))


def test_second_blade_hardware_uses_azimuth_and_tip_hinge_origin(monkeypatch):
    from pyfoldable.application import surface_clearance as service
    import copy
    data = payload()
    original = data['bodies'][0]
    original.update(name='joint_root',binding='blade_2_root',tolerance=0.)
    original['transform']['translation'] = [10.,0.,0.]
    original['geometry'] = dict(kind='convex_polyhedron',
        vertices=[[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]],
        faces=[[0,2,1],[0,1,3],[0,3,2],[1,2,3]])
    tip = copy.deepcopy(original)
    tip.update(name='joint_tip',binding='blade_2_tip')
    data['bodies'].append(tip)
    req = prepare_surface_clearance(draft(),SurfaceClearanceInputs(end_angle_deg=0.,max_hardware_queries=0),
                                   hardware_json=json.dumps(data).encode())
    captured = {}
    query = service.query_motion_pair
    def inspect(a,b,**kwargs):
        for shape in (a,b):
            if shape.solid is not None:
                captured[shape.name] = shape
        return query(a,b,**kwargs)
    monkeypatch.setattr(service,'query_motion_pair',inspect)
    run_surface_clearance(req)
    model,_,_ = service._inputs(req.draft)
    h = model.hinge.radius_m
    assert captured['joint_root'].solid.vertices[0] == pytest.approx((-.01,0.,0.))
    assert captured['joint_tip'].solid.vertices[0] == pytest.approx((-h-.01,0.,0.))
    assert captured['joint_tip'].pivot == pytest.approx((-h,0.,0.))
    assert not captured['joint_root'].moving and captured['joint_tip'].moving
