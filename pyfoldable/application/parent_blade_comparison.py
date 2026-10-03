"""Descriptive, source-bound station comparison; no geometric or safety acceptance.

Only declared identity transforms in one deployed shaft frame are supported.
Indices are zero-based, radii are global shaft-based SI values. No interpolation,
span rescaling, twist resetting or solver calls occur here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math

from .blade_stations import StationBundleError, parse_station_bundle


MAX_DECLARATION_BYTES = 128 * 1024
_ROLES = ('parent', 'fixed', 'tip')


class StationComparisonError(ValueError):
    """Invalid identity/correspondence or an unsupported frame/transform."""


@dataclass(frozen=True)
class StationComparisonReport:
    canonical_json: str
    sha256: str
    comparison_table: str


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False)


def _keys(doc, required):
    if not isinstance(doc, dict) or set(doc) != set(required):
        raise StationComparisonError('Missing or unsupported declaration fields.')


def _text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 2048:
        raise StationComparisonError('Declaration text must be bounded and nonempty.')
    try:
        value.encode('utf-8')
    except UnicodeError as exc:
        raise StationComparisonError('Invalid declaration Unicode.') from exc


def _unique(pairs):
    doc = {}
    for key, value in pairs:
        if key in doc:
            raise StationComparisonError('Duplicate declaration key.')
        doc[key] = value
    return doc


def _nonfinite(_value):
    raise StationComparisonError('Nonfinite declaration value.')


def _declaration(raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_DECLARATION_BYTES:
        raise StationComparisonError('Declaration must be bounded UTF-8 bytes.')
    try:
        doc = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique,
            parse_constant=_nonfinite)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise StationComparisonError('Invalid finite unique-key declaration JSON.') from exc
    _keys(doc, ('schema_version', 'evidence_label', 'hinge_radius_m', 'bundle_sha256',
        'frames', 'correspondence', 'joint_modifications'))
    if type(doc['schema_version']) is not int or doc['schema_version'] != 1:
        raise StationComparisonError('Unsupported comparison schema_version.')
    _text(doc['evidence_label'])
    return doc


def _index(value, count):
    if type(value) is not int or not 0 <= value < count:
        raise StationComparisonError('Correspondence index is out of range or not an integer.')


def _component(value):
    if not isinstance(value, str) or value not in ('fixed', 'tip'):
        raise StationComparisonError('Component must be fixed or tip.')


def _coverage(bundle, low, high):
    first, last = bundle.stations[0].radius_m, bundle.stations[-1].radius_m
    return {'required_span_m': [low, high], 'supplied_span_m': [first, last],
        'root_gap_m': first-low, 'tip_gap_m': high-last,
        'supplied_span_complete': first == low and last == high,
        'continuous_geometry_established': None}


def _point(bundle, index):
    return {**asdict(bundle.stations[index]), 'airfoil_id': bundle.airfoil_id,
        'airfoil_coordinate_sha256': bundle.airfoil_coordinate_sha256}


def compare_parent_blade_stations(parent_raw: bytes, fixed_raw: bytes,
    tip_raw: bytes, declaration_raw: bytes) -> StationComparisonReport:
    """Compare supplied stations and declared lineage, retaining gaps/differences.

    Child provenance must be derived_geometry with parent_sha256 equal to the
    parent's canonical station digest. A profile label cannot establish lineage.
    A value match means exact equality of supplied normalized binary64 values,
    not tolerance acceptance, interpolation, authentication or surface equivalence.
    """
    try:
        bundles = dict(zip(_ROLES, map(parse_station_bundle, (parent_raw, fixed_raw, tip_raw))))
    except StationBundleError as exc:
        raise StationComparisonError(str(exc)) from exc
    declaration = _declaration(declaration_raw)
    _keys(declaration['bundle_sha256'], _ROLES)
    for role, bundle in bundles.items():
        if declaration['bundle_sha256'][role] != bundle.canonical_sha256:
            raise StationComparisonError(f'{role} bundle identity does not match declaration.')
    parent = bundles['parent']
    for role in ('fixed', 'tip'):
        child = bundles[role]
        if child.provenance.kind != 'derived_geometry' or child.provenance.parent_sha256 != parent.canonical_sha256:
            raise StationComparisonError(f'{role} parent identity must explicitly bind the supplied parent.')
        if (child.diameter_m, child.hub_radius_m) != (parent.diameter_m, parent.hub_radius_m):
            raise StationComparisonError('Complementary bundles require the same global envelope.')

    _keys(declaration['frames'], _ROLES)
    frame_id = None
    for role in _ROLES:
        frame = declaration['frames'][role]
        _keys(frame, ('id', 'radial_origin', 'pose', 'transform', 'radius_coordinate'))
        _text(frame['id'])
        if frame_id is None:
            frame_id = frame['id']
        if (frame['id'] != frame_id or frame['radial_origin'] != 'shaft_axis'
                or frame['pose'] != 'deployed' or frame['transform'] != 'identity'
                or frame['radius_coordinate'] != 'global_shaft_radius'):
            raise StationComparisonError('Unsupported frame/transform: require the same declared deployed shaft frame.')

    hinge = declaration['hinge_radius_m']
    if isinstance(hinge, bool) or not isinstance(hinge, (int, float)):
        raise StationComparisonError('hinge_radius_m must be finite numeric SI.')
    try:
        hinge = float(hinge)
    except OverflowError as exc:
        raise StationComparisonError('hinge_radius_m must be finite numeric SI.') from exc
    if not math.isfinite(hinge) or not parent.hub_radius_m < hinge < parent.diameter_m/2:
        raise StationComparisonError('Hinge must be inside the parent hub-to-tip span.')
    if any(s.radius_m > hinge for s in bundles['fixed'].stations) or any(s.radius_m < hinge for s in bundles['tip'].stations):
        raise StationComparisonError('Noncomplementary global station span; no rescaling or local-tip conversion is supported.')

    correspondence = declaration['correspondence']
    if not isinstance(correspondence, list) or len(correspondence) > 128:
        raise StationComparisonError('Correspondence requires at most 128 explicit rows.')
    mapping, parent_indices = {}, {'fixed': set(), 'tip': set()}
    for row in correspondence:
        _keys(row, ('component', 'child_index', 'parent_index'))
        role = row['component']; _component(role)
        ci, pi = row['child_index'], row['parent_index']
        _index(ci, len(bundles[role].stations)); _index(pi, len(parent.stations))
        if (role, ci) in mapping or pi in parent_indices[role]:
            raise StationComparisonError('Duplicate/ambiguous station correspondence.')
        pr = parent.stations[pi].radius_m
        if (role == 'fixed' and pr > hinge) or (role == 'tip' and pr < hinge):
            raise StationComparisonError('Parent correspondence is not in the complementary span.')
        mapping[role, ci] = pi
        parent_indices[role].add(pi)

    modifications = declaration['joint_modifications']
    if not isinstance(modifications, list) or len(modifications) > 128:
        raise StationComparisonError('Joint modifications require at most 128 declared rows.')
    modified = set()
    for mod in modifications:
        _keys(mod, ('component', 'child_index', 'description', 'reference', 'revision'))
        role = mod['component']; _component(role)
        if mod['child_index'] is not None:
            _index(mod['child_index'], len(bundles[role].stations))
        for key in ('description', 'reference', 'revision'):
            _text(mod[key])
        if mod['child_index'] is not None:
            modified.add((role, mod['child_index']))

    rows = []
    for role in ('fixed', 'tip'):
        child = bundles[role]
        for ci in range(len(child.stations)):
            pi = mapping.get((role, ci))
            child_values = _point(child, ci)
            parent_values = None if pi is None else _point(parent, pi)
            differences = None if pi is None else {key: child_values[key]-parent_values[key]
                for key in ('radius_m', 'chord_m', 'twist_rad')}
            # Extremely large but finite supplied twists can overflow a difference.
            if differences is not None and not all(math.isfinite(x) for x in differences.values()):
                raise StationComparisonError('A supplied station difference is not finite.')
            label_equal = None if pi is None else child.airfoil_id == parent.airfoil_id
            coordinate_equal = None if pi is None else child.airfoil_coordinate_sha256 == parent.airfoil_coordinate_sha256
            equal = differences is not None and all(x == 0 for x in differences.values()) and label_equal and coordinate_equal
            rows.append({'component': role, 'child_index': ci, 'parent_index': pi,
                'child': child_values, 'parent': parent_values, 'differences': differences,
                'airfoil_label_equal': label_equal, 'airfoil_coordinate_identity_equal': coordinate_equal,
                'declared_joint_modification': (role, ci) in modified,
                'status': 'NO_DECLARED_CORRESPONDENCE' if pi is None else 'EQUAL_SUPPLIED_VALUES' if equal else 'DIFFERENT'})

    missing = {role: [i for i, s in enumerate(parent.stations)
        if (s.radius_m <= hinge if role == 'fixed' else s.radius_m >= hinge) and i not in parent_indices[role]]
        for role in ('fixed', 'tip')}
    coverage = {'parent': _coverage(parent, parent.hub_radius_m, parent.diameter_m/2),
        'fixed': _coverage(bundles['fixed'], parent.hub_radius_m, hinge),
        'tip': _coverage(bundles['tip'], hinge, parent.diameter_m/2)}
    matches = all(row['status'] == 'EQUAL_SUPPLIED_VALUES' for row in rows) and not any(missing.values()) and all(x['supplied_span_complete'] for x in coverage.values())
    doc = {'schema_version': 1, 'artifact_class': 'unqualified_station_comparison',
        'evidence_label': declaration['evidence_label'], 'hinge_radius_m': hinge,
        'units': {'length': 'm', 'angle': 'rad'}, 'frames': declaration['frames'],
        'sources': {role: {'raw_sha256': b.raw_sha256, 'canonical_sha256': b.canonical_sha256,
            'provenance': asdict(b.provenance), 'supplied_units': json.loads(b.raw_bytes)['units'],
            'canonical_bundle': json.loads(b.canonical_json)} for role, b in bundles.items()},
        'declaration': declaration,
        'declaration_raw_sha256': hashlib.sha256(declaration_raw).hexdigest(),
        'declaration_canonical_sha256': hashlib.sha256(_canonical(declaration).encode()).hexdigest(),
        'rows': rows, 'missing_parent_stations': missing, 'coverage': coverage,
        'joint_modifications': modifications,
        'station_comparison': 'SUPPLIED_STATIONS_MATCH' if matches else 'DIFFERENCES_OR_GAPS',
        'physical_qualification': False,
        'unestablished': {key: None for key in ('complete_3d_surface_equivalence',
            'joint_clearance', 'strength', 'safe_winner')},
        'limitations': ['Frame, lineage, coordinate digests and joint modifications are supplied declarations, not authenticated CAD.',
            'Station equality and endpoint coverage do not establish continuous 3D surface geometry.',
            'No interpolation, twist reset, rescaling, tolerance acceptance or solver execution.']}
    canonical = _canonical(doc)
    return StationComparisonReport(canonical, hashlib.sha256(canonical.encode()).hexdigest(), _table(doc))


def _table(doc):
    def show(value):
        return '—' if value is None else str(value).replace('|', '\\|').replace('\n', ' ').replace('\r', ' ')

    lines = ['# Station-level comparison', '', 'Evidence: '+show(doc['evidence_label']),
        'Result: '+doc['station_comparison'],
        'Station values only; complete 3D surface, clearance, strength and safe winner remain unestablished.',
        'physical_qualification=false', '']
    for role, source in doc['sources'].items():
        lines.append(f"{role}: canonical={source['canonical_sha256']}; raw={source['raw_sha256']}; parent={source['provenance']['parent_sha256']}")
        bundle = source['canonical_bundle']
        lines.append(f"  frame={show(doc['frames'][role]['id'])}; profile={show(bundle['airfoil_id'])}; coordinates={bundle['airfoil_coordinate_sha256']}")
    lines += ['', '| component | child | parent | parent r_m | child r_m | delta r_m | parent chord_m | child chord_m | delta chord_m | parent twist_rad | child twist_rad | delta twist_rad | airfoil label equal | coordinate identity equal | joint declared | status |',
        '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for row in doc['rows']:
        values = [row['component'], row['child_index'], row['parent_index']]
        for key in ('radius_m', 'chord_m', 'twist_rad'):
            values += [None if row['parent'] is None else row['parent'][key],
                row['child'][key], None if row['differences'] is None else row['differences'][key]]
        values += [row['airfoil_label_equal'], row['airfoil_coordinate_identity_equal'], row['declared_joint_modification'], row['status']]
        lines.append('| '+ ' | '.join(map(show, values))+' |')
    lines += ['', '## Coverage / missing parent stations', '']
    for role, coverage in doc['coverage'].items():
        lines.append(f"{role}: required span={coverage['required_span_m']}; supplied span={coverage['supplied_span_m']}; root gap={coverage['root_gap_m']}; tip gap={coverage['tip_gap_m']}; endpoint complete={coverage['supplied_span_complete']}; missing={doc['missing_parent_stations'].get(role, [])}")
    lines += ['', '## Declared joint modifications (not inherited-geometry evidence)', '']
    lines.extend(show(_canonical(m)) for m in doc['joint_modifications'])
    if not doc['joint_modifications']:
        lines.append('None supplied; this does not establish an unchanged joint region.')
    return '\n'.join(lines)+'\n'
