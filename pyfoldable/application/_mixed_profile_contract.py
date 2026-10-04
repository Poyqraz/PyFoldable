"""Owned generic geometry records and strict local wire codec (no asset lookup)."""
from __future__ import annotations

from dataclasses import dataclass, fields
import hashlib
import json
import math
import re
from typing import Any

from .blade_stations import StationPoint, StationProvenance

REQUEST_LIMIT = 2 * 1024 * 1024
ENDPOINT_LIMIT = 256 * 1024
OUTPUT_LIMIT = 16 * 1024 * 1024
METHOD = 'mixed_profile_pwl_smoothstep_vertical_thickness_v1'
POLICIES = ('mixed_profile_parent_generic_api_v1', 'mixed_profile_parent_use_scope_v1',
            'mixed_profile_parent_endpoint_model_v1')
HINGES = (float.fromhex('0x1.a027525460aa6p-4'), float.fromhex('0x1.04189374bc6a8p-3'))


@dataclass(frozen=True, slots=True)
class UseScopeV1:
    kind: str
    reference: str


@dataclass(frozen=True, slots=True)
class EndpointInputV1:
    identity: str
    raw_bytes: bytes
    file_format: str
    expected_raw_sha256: str
    use_scope: UseScopeV1


@dataclass(frozen=True, slots=True)
class ScalarKnotV1:
    index: int
    point: StationPoint
    tau: float
    Y_m: float
    Z_m: float


@dataclass(frozen=True, slots=True)
class ModelV1:
    method_id: str
    domain_m: tuple[float, float]
    transition_m: tuple[float, float]
    frame: str
    stack_fraction: float
    hardware_offset_m: tuple[float, float, float]
    hinge_axis: str
    deployed_transforms: tuple[str, str]
    actual_joint_modifications: str


@dataclass(frozen=True, slots=True)
class MixedProfileParentRequestV1:
    schema_id: str
    scenario_id: str
    endpoint_A: EndpointInputV1
    endpoint_B: EndpointInputV1
    scalars: tuple[ScalarKnotV1, ...]
    scalar_provenance: StationProvenance
    scalar_use_scope: UseScopeV1
    model: ModelV1
    hinges_m: tuple[float, float]
    section_requests_m: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class GeometryExecutionV1:
    run_id: str
    started_utc: str
    python_build: str
    platform: str
    code_sha256: tuple[tuple[str, str], ...]
    binary_sha256: tuple[tuple[str, str], ...]
    rounding_mode: str


@dataclass(frozen=True, slots=True)
class MixedProfileParentReportV1:
    canonical_json: bytes
    sha256: str
    execution_json: bytes
    execution_sha256: str


class MixedProfileDecodeError(ValueError):
    def __init__(self, code: str, field: str, raw_sha256: str | None):
        self.code, self.field, self.raw_sha256 = code, field, raw_sha256
        super().__init__(f'{code}: {field}')


class MixedProfileInternalError(RuntimeError):
    def __init__(self, partial_report: MixedProfileParentReportV1 | None):
        self.partial_report = partial_report
        super().__init__('Unexpected generic geometry failure; inspect original cause')


class MixedProfileReportError(ValueError):
    def __init__(self, code='INVALID_REPORT', field='/'):
        self.code, self.field = code, field
        super().__init__(f'{code}: {field}')


class WireError(ValueError):
    def __init__(self, code: str, field: str):
        self.code, self.field = code, field
        super().__init__(f'{code}: {field}')


def canonical_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('ascii')


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def identified(content: dict) -> dict:
    return {'sha256': sha(canonical_bytes(content)), 'content': content}


def keys(d: Any, names: tuple | list, path: str) -> dict:
    if type(d) is not dict:
        raise WireError('FIELD_TYPE', path)
    if set(d) != set(names):
        raise WireError('FIELD_SET', path)
    return d


def text(v: Any, path: str, limit=256) -> str:
    if type(v) is not str:
        raise WireError('FIELD_TYPE', path)
    if not v or len(v) > limit:
        raise WireError('FIELD_TYPE', path)
    try:
        v.encode('ascii')
    except UnicodeError as exc:
        raise WireError('INVALID_ASCII', path) from exc
    return v


def digest(v: Any, path: str) -> str:
    if type(v) is not str or re.fullmatch('[0-9a-f]{64}', v) is None:
        raise WireError('FIELD_TYPE', path)
    return v


def f64(v: Any, path: str, decoding: bool) -> float:
    if decoding:
        if type(v) is not str or len(v) > 32:
            raise WireError('INVALID_F64_HEX', path)
        try:
            result = float.fromhex(v)
        except ValueError as exc:
            raise WireError('INVALID_F64_HEX', path) from exc
        if not math.isfinite(result) or result.hex() != v:
            raise WireError('INVALID_F64_HEX', path)
        return result
    if type(v) is not float:
        raise WireError('FIELD_TYPE', path)
    if not math.isfinite(v):
        raise WireError('NONFINITE_INPUT', path)
    return v


def seq(v: Any, path: str, decoding: bool, lo: int, hi: int) -> tuple:
    if type(v) is not (list if decoding else tuple) or not lo <= len(v) <= hi:
        raise WireError('FIELD_TYPE', path)
    return tuple(v)


def _scope(d: Any, path: str, dec: bool) -> UseScopeV1:
    if not dec:
        if type(d) is not UseScopeV1: raise WireError('FIELD_TYPE', path)
        d = {'kind': d.kind, 'reference': d.reference}
    keys(d, ('kind', 'reference'), path)
    k = text(d['kind'], path+'/kind')
    if k not in ('FIRST_PARTY_SYNTHETIC','CALLER_LOCAL_DECLARED_PERMITTED','CALLER_LOCAL_UNCLEARED'):
        raise WireError('FIELD_TYPE', path+'/kind')
    return UseScopeV1(k, text(d['reference'], path+'/reference', 2048))


def _endpoint(d: Any, path: str, dec: bool) -> EndpointInputV1:
    if not dec:
        if type(d) is not EndpointInputV1 or type(d.raw_bytes) is not bytes:
            raise WireError('FIELD_TYPE', path)
        if len(d.raw_bytes)>ENDPOINT_LIMIT:
            raise WireError('INPUT_LIMIT',path+'/raw_text')
        try: raw = d.raw_bytes.decode('ascii')
        except UnicodeError as exc: raise WireError('INVALID_ASCII',path+'/raw_text') from exc
        d = {'identity':d.identity,'raw_text':raw,'file_format':d.file_format,
             'expected_raw_sha256':d.expected_raw_sha256,'use_scope':d.use_scope}
    keys(d, ('identity','raw_text','file_format','expected_raw_sha256','use_scope'), path)
    raw = text(d['raw_text'], path+'/raw_text', ENDPOINT_LIMIT)
    return EndpointInputV1(text(d['identity'],path+'/identity'),raw.encode('ascii'),
                           text(d['file_format'],path+'/file_format'),
                           digest(d['expected_raw_sha256'],path+'/expected_raw_sha256'),
                           _scope(d['use_scope'],path+'/use_scope',dec))


def _provenance(d: Any, dec: bool) -> StationProvenance:
    path='/scalar_provenance'
    if not dec:
        if type(d) is not StationProvenance: raise WireError('FIELD_TYPE',path)
        d={f.name:getattr(d,f.name) for f in fields(d)}
    keys(d, ('kind','reference','locator','revision','parent_sha256'),path)
    k=text(d['kind'],path+'/kind')
    if k not in ('declared_design','literature_geometry','project_measurement','derived_geometry'):
        raise WireError('FIELD_TYPE',path+'/kind')
    parent=d['parent_sha256']
    if parent is not None: digest(parent,path+'/parent_sha256')
    if k=='derived_geometry' and parent is None: raise WireError('FIELD_TYPE',path+'/parent_sha256')
    return StationProvenance(k,*(text(d[n],path+'/'+n,2048) for n in ('reference','locator','revision')),parent)


def own_request(value: Any, decoding=False) -> MixedProfileParentRequestV1:
    """Structural finite snapshot only; numerical/domain admission is later."""
    if not decoding:
        if type(value) is not MixedProfileParentRequestV1: raise WireError('FIELD_TYPE','/')
        value={f.name:getattr(value,f.name) for f in fields(value)}
    keys(value, tuple(f.name for f in fields(MixedProfileParentRequestV1)), '/')
    if value['schema_id']!='mixed_profile_parent_request_v1': raise WireError('UNSUPPORTED_SCHEMA','/schema_id')
    scalar=[]
    for i,k in enumerate(seq(value['scalars'],'/scalars',decoding,2,64)):
        p=f'/scalars/{i}'
        if not decoding:
            if type(k) is not ScalarKnotV1: raise WireError('FIELD_TYPE',p)
            k={f.name:getattr(k,f.name) for f in fields(k)}
        keys(k, ('index','point','tau','Y_m','Z_m'),p)
        if type(k['index']) is not int or not 0<=k['index']<=2**63-1: raise WireError('FIELD_TYPE',p+'/index')
        pt=k['point']
        if not decoding:
            if type(pt) is not StationPoint: raise WireError('FIELD_TYPE',p+'/point')
            pt={f.name:getattr(pt,f.name) for f in fields(pt)}
        keys(pt,('radius_m','chord_m','twist_rad'),p+'/point')
        point=StationPoint(*(f64(pt[n],p+'/point/'+n,decoding) for n in ('radius_m','chord_m','twist_rad')))
        scalar.append(ScalarKnotV1(k['index'],point,*(f64(k[n],p+'/'+n,decoding) for n in ('tau','Y_m','Z_m'))))
    m=value['model']
    if not decoding:
        if type(m) is not ModelV1: raise WireError('FIELD_TYPE','/model')
        m={f.name:getattr(m,f.name) for f in fields(m)}
    keys(m,tuple(f.name for f in fields(ModelV1)),'/model')
    model=ModelV1(text(m['method_id'],'/model/method_id'),
                  *(tuple(f64(x,'/model/'+n,decoding) for x in seq(m[n],'/model/'+n,decoding,size,size))
                    for n,size in (('domain_m',2),('transition_m',2))),
                  text(m['frame'],'/model/frame'),f64(m['stack_fraction'],'/model/stack_fraction',decoding),
                  tuple(f64(x,'/model/hardware_offset_m',decoding) for x in seq(m['hardware_offset_m'],'/model/hardware_offset_m',decoding,3,3)),
                  text(m['hinge_axis'],'/model/hinge_axis'),
                  tuple(text(x,'/model/deployed_transforms') for x in seq(m['deployed_transforms'],'/model/deployed_transforms',decoding,2,2)),
                  text(m['actual_joint_modifications'],'/model/actual_joint_modifications'))
    return MixedProfileParentRequestV1(value['schema_id'],text(value['scenario_id'],'/scenario_id'),
              _endpoint(value['endpoint_A'],'/endpoint_A',decoding),_endpoint(value['endpoint_B'],'/endpoint_B',decoding),
              tuple(scalar),_provenance(value['scalar_provenance'],decoding),_scope(value['scalar_use_scope'],'/scalar_use_scope',decoding),model,
              tuple(f64(x,'/hinges_m',decoding) for x in seq(value['hinges_m'],'/hinges_m',decoding,2,2)),
              tuple(f64(x,'/section_requests_m',decoding) for x in seq(value['section_requests_m'],'/section_requests_m',decoding,0,68)))


def request_wire(request: MixedProfileParentRequestV1) -> dict:
    def encode(v):
        if type(v) is float: return v.hex()
        if type(v) is bytes: return v.decode('ascii')
        if type(v) is tuple: return [encode(x) for x in v]
        if hasattr(v,'__dataclass_fields__'):
            return {('raw_text' if f.name=='raw_bytes' else f.name):encode(getattr(v,f.name)) for f in fields(v)}
        return v
    return encode(request)


def own_execution(v: GeometryExecutionV1) -> dict:
    d={}
    for f in fields(v):
        item=getattr(v,f.name)
        if f.name in ('code_sha256','binary_sha256'):
            pairs=seq(item,'/'+f.name,False,0,32 if f.name=='code_sha256' else 16)
            result=[]
            for pair in pairs:
                pair=seq(pair,'/'+f.name,False,2,2)
                result.append((text(pair[0],'/'+f.name,2048),digest(pair[1],'/'+f.name)))
            if result!=sorted(result) or len({x[0] for x in result})!=len(result): raise WireError('FIELD_TYPE','/'+f.name)
            d[f.name]=result
        else: d[f.name]=text(item,'/'+f.name)
    return d


def parse_mixed_profile_request(raw: bytes) -> MixedProfileParentRequestV1:
    if type(raw) is not bytes: raise TypeError('raw must be bytes')
    if len(raw)>REQUEST_LIMIT: raise MixedProfileDecodeError('REQUEST_BYTES_LIMIT','/',None)
    raw_sha=sha(raw)
    def obj(pairs):
        d={}
        for k,v in pairs:
            if k in d: raise WireError('DUPLICATE_KEY','/'+k)
            d[k]=v
        return d
    def invalid(_): raise WireError('INVALID_JSON','/')
    try:
        data=json.loads(raw.decode('ascii'),object_pairs_hook=obj,parse_float=invalid,parse_constant=invalid)
        return own_request(data,decoding=True)
    except WireError as exc: raise MixedProfileDecodeError(exc.code,exc.field,raw_sha) from exc
    except UnicodeError as exc: raise MixedProfileDecodeError('INVALID_ASCII','/',raw_sha) from exc
    except (ValueError, RecursionError, OverflowError) as exc:
        raise MixedProfileDecodeError('INVALID_JSON','/',raw_sha) from exc
