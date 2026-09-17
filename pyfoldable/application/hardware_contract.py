"""Strict source-bound hardware input. Dimensions are supplied, never inferred."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import math
import re

from pyfoldable.geometry.hardware import ConvexSolid, finite_cylinder, transform_solid, validate_transform

MAX_HARDWARE_BYTES=256*1024
MAX_HARDWARE_BODIES=16
SCHEMA_VERSION='pyfoldable.hardware.v1'


@dataclass(frozen=True)
class HardwareProvenance:
    kind: str
    source: str
    revision: str
    source_sha256: str


@dataclass(frozen=True)
class HardwareBody:
    name: str
    binding: str
    frame: str
    rotation: tuple
    translation_m: tuple
    tolerance_m: float
    solid: object


@dataclass(frozen=True)
class HardwareBundle:
    schema_version: str
    provenance: HardwareProvenance
    bodies: tuple[HardwareBody,...]
    raw_bytes: bytes
    raw_sha256: str
    canonical_json: str
    canonical_sha256: str

    @property
    def sha256(self): return self.canonical_sha256


def _keys(value,required):
    if not isinstance(value,dict) or set(value)!=set(required):
        raise ValueError('Hardware JSON contains missing or unsupported fields.')


def _num(v):
    if isinstance(v,bool) or not isinstance(v,(int,float)):
        raise ValueError('Hardware dimensions must be numeric.')
    try:v=float(v)
    except (ValueError,OverflowError) as exc:raise ValueError('Nonfinite hardware dimension.') from exc
    if not math.isfinite(v):raise ValueError('Nonfinite hardware dimension.')
    return v


def _text(value,limit=1024):
    if not isinstance(value,str) or not value.strip() or len(value)>limit:
        raise ValueError('Hardware source and identifiers require bounded text.')
    try:value.encode('utf8')
    except UnicodeError as exc:raise ValueError('Invalid hardware text.') from exc
    return value


def _pairs(pairs):
    result={}
    for k,v in pairs:
        if k in result:raise ValueError('Duplicate hardware JSON key.')
        result[k]=v
    return result


def _vector(value,factor):
    if not isinstance(value,list) or len(value)!=3:raise ValueError('Hardware vector must contain xyz.')
    return tuple(_num(x)*factor for x in value)


def load_hardware_json(raw):
    if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_HARDWARE_BYTES:
        raise ValueError('Hardware JSON must be 1..262144 bytes.')
    try:
        data=json.loads(raw.decode('utf8'),object_pairs_hook=_pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON constant.')))
    except (UnicodeError,json.JSONDecodeError,RecursionError) as exc:
        raise ValueError('Invalid hardware JSON.') from exc
    _keys(data,('schema_version','units','provenance','bodies'))
    if data['schema_version']!=SCHEMA_VERSION:raise ValueError('Unsupported hardware schema.')
    if data['units'] not in ('m','mm','cm'):raise ValueError('Hardware length units must be m, mm or cm.')
    factor={'m':1.,'mm':.001,'cm':.01}[data['units']]
    p=data['provenance'];_keys(p,('kind','source','revision','source_sha256'))
    if p['kind'] not in ('synthetic','literature','measurement','cad'):
        raise ValueError('Explicit hardware provenance kind required.')
    source=_text(p['source']);revision=_text(p['revision']);digest=p['source_sha256']
    if not isinstance(digest,str) or re.fullmatch('[0-9a-f]{64}',digest) is None:
        raise ValueError('Hardware provenance requires source SHA-256.')
    if not isinstance(data['bodies'],list) or not 1<=len(data['bodies'])<=MAX_HARDWARE_BODIES:
        raise ValueError('Hardware requires 1..16 bodies.')
    bodies=[];names=set()
    for b in data['bodies']:
        _keys(b,('name','binding','frame','transform','tolerance','geometry'))
        name=_text(b['name'],128)
        if name in names:raise ValueError('Hardware body names must be unique.')
        names.add(name)
        binding=b['binding']
        if not isinstance(binding,str) or re.fullmatch(r'(hub|blade_[1-8]_(root|tip))',binding) is None:
            raise ValueError('Hardware binding must be hub or blade_1..8_root/tip.')
        if b['frame']!='body_local':raise ValueError('Only body_local hardware frames are supported.')
        transform=b['transform'];_keys(transform,('rotation','translation'))
        rotation,translation=validate_transform(transform['rotation'],_vector(transform['translation'],factor))
        tolerance=_num(b['tolerance'])*factor
        if not 0<=tolerance<=.1:raise ValueError('Hardware tolerance must be explicit, within 0..0.1 m.')
        geometry=b['geometry']
        if not isinstance(geometry,dict):raise ValueError('Hardware geometry must be an object.')
        if geometry.get('kind')=='finite_cylinder':
            _keys(geometry,('kind','radius','height','segments','approximation_tolerance'))
            if binding!='hub':raise ValueError('Finite cylinder is supported for hub binding only.')
            solid=finite_cylinder(radius_m=_num(geometry['radius'])*factor,
                height_m=_num(geometry['height'])*factor,segments=geometry['segments'],
                approximation_tolerance_m=_num(geometry['approximation_tolerance'])*factor)
        elif geometry.get('kind')=='convex_polyhedron':
            _keys(geometry,('kind','vertices','faces'))
            if not isinstance(geometry['vertices'],list):raise ValueError('Hardware vertices must be a list.')
            solid=ConvexSolid(tuple(_vector(v,factor) for v in geometry['vertices']),geometry['faces'])
        else:raise ValueError('Unsupported hardware geometry kind.')
        bodies.append(HardwareBody(name,binding,b['frame'],rotation,translation,tolerance,solid))
    canonical=json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
    return HardwareBundle(SCHEMA_VERSION,HardwareProvenance(p['kind'],source,revision,digest),tuple(bodies),raw,
        hashlib.sha256(raw).hexdigest(),canonical,hashlib.sha256(canonical.encode()).hexdigest())


def body_to_solid(body):
    """Apply the declared geometry-to-body transform; motion is caller supplied."""
    if not isinstance(body,HardwareBody):raise ValueError('Expected a hardware body.')
    return transform_solid(body.solid,body.rotation,body.translation_m)
