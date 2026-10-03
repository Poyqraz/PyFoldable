# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
"""Bounded local PE0 source-table reporting, never a single-profile blade model.

Retains all fourteen fields and source definitions; no download, blend, station
synthesis, performance calculation or qualification occurs here.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json
import math
import re
from pathlib import Path

from pyfoldable.core.apc_pe0 import INCH_TO_M, parse_apc_pe0

MAX_PE0_BYTES = 1024 * 1024
MAX_STATIONS = 1024
COLUMN_KEYS = ('station', 'chord', 'pitch_1', 'pitch_2', 'pitch_3', 'sweep',
    'rake', 'thickness_ratio', 'twist', 'max_thickness', 'section_area', 'zhigh', 'cgy', 'cgz')
_FOOTER = re.compile(r'^\s*(RADIUS|HUBRAD|HUBTRA|BLADES):\s*(.*)$')
_AIRFOIL = re.compile(r'^\s*AIRFOIL\d+:\s*([0-9.]+)\s*,\s*(\S+)', re.I)
_HEADER_ALIASES = ({'STATION'}, {'CHORD'}, {'PITCH','PITCH_A','PITCH_1'},
    {'PITCH','PITCH_B','PITCH_2'}, {'PITCH','PITCH_C','PITCH_3'}, {'SWEEP','SWEEP(Y)'},
    {'RAKE','RAKE(Z)'}, {'THICKNESS','THICKNESS_RATIO'}, {'TWIST'}, {'MAX_THICK','MAX-THICK'},
    {'AREA','CROSS-SECTION'}, {'ZHIGH'}, {'CGY'}, {'CGZ'})
_HEADER_POSITIONS = {name:position for position,names in enumerate(_HEADER_ALIASES)
    for name in names if name != 'PITCH'}


class PE0ReportError(ValueError):
    """Unsupported, malformed or unbound local reporting input."""


@dataclass(frozen=True)
class PE0GeometryReport:
    canonical_json: str
    sha256: str
    comparison_table: str


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False)


def _text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 2048:
        raise PE0ReportError('Require bounded nonempty source reference/member text.')
    value.encode('utf-8')


def _sha(value):
    if not isinstance(value, str) or re.fullmatch('[0-9a-fA-F]{64}', value) is None:
        raise PE0ReportError('Require a SHA-256 hexadecimal digest.')
    return value.lower()


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PE0ReportError('Require finite numeric SI dimensions.')
    result = float(value)
    if not math.isfinite(result):
        raise PE0ReportError('Require finite numeric SI dimensions.')
    return result


def _source_table(lines):
    """Validate the declared table region, complete tokens and named positions."""
    rows, other, footer, units, header = [], [], {}, None, None
    table_open = False
    for line_number, line in enumerate(lines, 1):
        parts = line.split()
        upper = [p.upper() for p in parts]
        is_header = 'STATION' in upper and 'CHORD' in upper
        if is_header:
            if header is not None or upper[:2] != ['STATION', 'CHORD']:
                raise PE0ReportError('Conflicting or repeated STATION/CHORD header.')
            header = parts
            for index, name in enumerate(upper):
                if ((name in _HEADER_POSITIONS and _HEADER_POSITIONS[name] != index)
                        or (name == 'PITCH' and index not in (2,3,4))):
                    raise PE0ReportError('Conflicting named PE0 column position.')
            # The header establishes the boundary before any numeric station,
            # independently of whether a positional units row is supplied.
            table_open = True
        match = _FOOTER.match(line)
        if match:
            key, remainder = match.groups()
            if key in footer:
                raise PE0ReportError('Duplicate scalar footer field.')
            if not remainder.strip():
                raise PE0ReportError('Missing scalar footer value.')
            token = remainder.split()[0]
            if re.fullmatch(r'(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)', token) is None:
                raise PE0ReportError('Unsupported complete footer number; no prefix truncation.')
            footer[key] = token
        if re.match(r'^\s*AIRFOIL\d*\s*:', line, re.I) and not _AIRFOIL.match(line):
            raise PE0ReportError('Malformed airfoil transition declaration.')
        is_units = bool(parts) and all((p.startswith('(') and p.endswith(')'))
            or p.upper() == 'RATIO' for p in parts)
        if is_units and len(parts) == 14:
            if units is not None:
                raise PE0ReportError('Ambiguous repeated units row.')
            units = parts
            if ((upper[0], upper[1], upper[8]) != ('(IN)', '(IN)', '(DEG)')
                    or upper[7] not in ('RATIO','(RATIO)')):
                raise PE0ReportError('Units disagree with supported PE0 radius/chord/thickness/TWIST layout.')
            table_open = True
        numeric = []
        for part in parts:
            try:
                float(part); numeric.append(True)
            except ValueError:
                numeric.append(False)
        numeric_start = bool(parts) and line_number > 1 and numeric[0]
        row_like = not match and sum(numeric) >= 3
        if numeric_start or row_like:
            if len(parts) != 14 or not all(numeric):
                raise PE0ReportError(f'Station line {line_number} requires all 14 numeric columns.')
            values = [float(v) for v in parts]
            if not all(math.isfinite(v) for v in values):
                raise PE0ReportError('Every source column must be finite.')
            rows.append(dict(line_number=line_number, raw_line=line, lexemes=parts, values=values))
            table_open = True
            if len(rows) > MAX_STATIONS:
                raise PE0ReportError('Station work limit exceeded.')
        else:
            # A labeled footer ends the table. Unknown text inside its active
            # region cannot silently become metadata (even if every cell is bad).
            labeled = bool(re.match(r'^\s*[A-Za-z][A-Za-z0-9_ /()-]*:', line))
            separator = not parts or set(line.strip()) <= {'-', '='}
            if table_open and not (is_header or is_units or separator or labeled):
                raise PE0ReportError(f'Unrecognized line {line_number} inside station table.')
            if labeled:
                table_open = False
            other.append(dict(line_number=line_number, text=line))
    if set(footer) != {'RADIUS', 'HUBRAD', 'HUBTRA', 'BLADES'}:
        raise PE0ReportError('Require exactly one complete dimensional footer.')
    blades = Decimal(footer['BLADES'])
    if blades != blades.to_integral_value():
        raise PE0ReportError('BLADES must be an integer; no truncation.')
    return rows, other, footer, units, header


def _extent(rows, hinge, role):
    if not rows:
        return dict(supplied_span_m=None, hinge_gap_m=None, hinge_endpoint_present=False)
    first, last = rows[0]['si']['radius_m'], rows[-1]['si']['radius_m']
    endpoint = last if role == 'fixed' else first
    return dict(supplied_span_m=[first, last],
        hinge_gap_m=hinge-endpoint if role == 'fixed' else endpoint-hinge,
        hinge_endpoint_present=endpoint == hinge)


def report_pe0_geometry(raw: bytes, *, source_reference: str, nominal_diameter_m: float,
    hinge_radii_m: tuple[float, float], expected_sha256: str | None = None,
    archive_sha256: str | None = None, member_name: str | None = None) -> PE0GeometryReport:
    """Copy complete local source rows at two declared global shaft radii.

    Nominal product diameter is a caller declaration, independent of footer and
    terminal station. Supplied TWIST is used directly. All source section fields,
    transition statements and definitions remain visible; no transition geometry
    or coordinate identity is manufactured. Archive identity is declared only:
    member bytes cannot verify an archive's hash. Reports are private derivatives
    subject to source terms, not redistributable Project geometry fixtures.
    """
    try:
        if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_PE0_BYTES:
            raise PE0ReportError('Require bounded local PE0 bytes.')
        _text(source_reference)
        if member_name is not None:
            _text(member_name)
        expected = None if expected_sha256 is None else _sha(expected_sha256)
        archive = None if archive_sha256 is None else _sha(archive_sha256)
        diameter = _number(nominal_diameter_m)
        if diameter <= 0:
            raise PE0ReportError('Nominal diameter must be positive.')
        if not isinstance(hinge_radii_m, (tuple, list)) or len(hinge_radii_m) != 2:
            raise PE0ReportError('Declare exactly two hinge radii.')
        hinges = tuple(_number(h) for h in hinge_radii_m)
        if hinges[0] == hinges[1]:
            raise PE0ReportError('Hinge positions must be distinct.')
        lines = raw.decode('utf-8-sig').splitlines()
        records, other, footer, units, header = _source_table(lines)
        geometry = parse_apc_pe0(raw, source_url=source_reference, expected_sha256=expected)
        if (float(footer['RADIUS'])*INCH_TO_M, float(footer['HUBRAD'])*INCH_TO_M,
                float(footer['HUBTRA'])*INCH_TO_M, int(Decimal(footer['BLADES']))) != (
                geometry.radius_m, geometry.hub_radius_m, geometry.hub_transition_m, geometry.blade_count):
            raise PE0ReportError('Full footer/core represented correspondence failed.')
        if len(records) != len(geometry.stations):
            raise PE0ReportError('Core/table station correspondence is incomplete.')
        if any(not geometry.hub_radius_m < h < diameter/2 for h in hinges):
            raise PE0ReportError('Cuts must be inside declared hub-to-nominal-tip span.')
        airfoils = []
        for line in other:
            if match := _AIRFOIL.match(line['text']):
                token, name = match.groups()
                airfoils.append(dict(source_line=line['text'], source_line_number=line['line_number'],
                    station_lexeme_in=token, station_m=float(token)*INCH_TO_M, airfoil_id=name))
        if len(airfoils) != len(geometry.airfoil_transitions):
            raise PE0ReportError('Incomplete transition-declaration correspondence.')
        for index, (record, point) in enumerate(zip(records, geometry.stations)):
            values = record['values']
            si = dict(radius_m=point.station_m, chord_m=point.chord_m, twist_rad=point.twist_rad)
            if (values[0]*INCH_TO_M, values[1]*INCH_TO_M, math.radians(values[8])) != tuple(si.values()):
                raise PE0ReportError('Core/table represented operation correspondence failed.')
            radius = point.station_m
            region = ('HUB' if radius < geometry.hub_radius_m else
                'HUB_TRANSITION' if radius < geometry.hub_transition_m else
                'BEYOND_FOOTER_RADIUS' if radius > geometry.radius_m else 'DECLARED_AERODYNAMIC_SPAN')
            record.update(parent_index=index, si=si, applicability=dict(region=region,
                inside_footer_radius=radius <= geometry.radius_m, inside_nominal_radius=radius <= diameter/2,
                at_or_outside_hub=radius >= geometry.hub_radius_m,
                in_declared_aerodynamic_span=geometry.hub_transition_m <= radius <= geometry.radius_m,
                nonzero_chord=point.chord_m > 0,
                aerodynamic_usability_established=None),
                source_section=dict(thickness_ratio=values[7], max_thickness_source=values[9],
                    section_area_source=values[10], coordinate_identity=None,
                    assigned_profile=None, transition_geometry=None,
                    declaration_indices_inboard=[i for i, a in enumerate(airfoils) if a['station_m'] <= radius],
                    declaration_indices_outboard=[i for i, a in enumerate(airfoils) if a['station_m'] > radius]))
        def dimension(token, value):
            return dict(source_lexeme_in=token, source_unit='in', si_m=value)
        radii = dict(nominal_product_diameter=dict(si_m=diameter, authority='CALLER_DECLARED'),
            nominal_product_radius=dict(si_m=diameter/2, authority='HALF_NOMINAL_DIAMETER'),
            footer_radius=dimension(footer['RADIUS'], geometry.radius_m),
            last_station_radius=dimension(records[-1]['lexemes'][0], records[-1]['si']['radius_m']),
            hub_radius=dimension(footer['HUBRAD'], geometry.hub_radius_m),
            hub_transition=dimension(footer['HUBTRA'], geometry.hub_transition_m))
        parent = dict(station_count=len(records), rows=records, airfoil_declarations=airfoils,
            nonstation_lines=other, source_column_header=header, radii=radii, blade_count=geometry.blade_count,
            source_sha256=geometry.source_sha256, version=geometry.version,
            simulation_date=geometry.simulation_date.isoformat(),
            transition_geometry=None, airfoil_coordinate_identity=None,
            thickness_metadata=[line['text'] for line in other if 'THICK' in line['text'].upper()],
            vendor_equivalence_statements=[line['text'] for line in other
                if 'APC12' in line['text'].upper() and re.search(r'NACA\s*[- ]?\s*4412', line['text'], re.I)])
        parent_sha = hashlib.sha256(_canonical(parent).encode()).hexdigest()
        diagnostics = ['UNRESOLVED_SECTION_COORDINATES_AND_TRANSITION_GEOMETRY']
        last = records[-1]['si']['radius_m']
        if not geometry.radius_m == last == diameter/2:
            diagnostics.append('RADIUS_CONVENTIONS_DIFFER')
        if last > geometry.radius_m:
            diagnostics.append('LAST_STATION_BEYOND_FOOTER_RADIUS')
        if units is None:
            diagnostics.append('SOURCE_UNIT_HEADER_BINDING_UNRESOLVED')
        if (header is None or len(header) != 14 or
                any(name.upper() not in allowed for name, allowed in zip(header, _HEADER_ALIASES))):
            diagnostics.append('SOURCE_COLUMN_HEADER_BINDING_PARTIAL_OR_UNRESOLVED')
        cuts = []
        for index, hinge in enumerate(hinges):
            components = {}
            present = any(row['si']['radius_m'] == hinge for row in records)
            for role in ('fixed', 'tip'):
                selected = [row for row in records if (row['si']['radius_m'] <= hinge
                    if role == 'fixed' else row['si']['radius_m'] >= hinge)]
                components[role] = dict(rows=selected, parent_indices=[r['parent_index'] for r in selected],
                    parent_sha256=parent_sha, provenance='DIRECT_STORED_PARENT_ROW_COPY',
                    coverage=_extent(selected, hinge, role),
                    diagnostics=[] if len(selected) >= 2 else [f'INSUFFICIENT_STATION_ROWS:{len(selected)}<2'])
            cuts.append(dict(id=f'cut-{index:02d}', hinge_radius_m=hinge,
                hinge_station_present=present, components=components,
                diagnostics=[] if present else ['HINGE_STATION_ABSENT'],
                station_comparison=dict(status='UNSUPPORTED_UNRESOLVED_SECTION_IDENTITY',
                    numeric_copy_identity=True, coordinate_identity_established=None,
                    reason='The single-coordinate station comparison service cannot represent these unresolved section/transition declarations.')))
        doc = dict(schema_version=1, method='local_pe0_source_geometry_report_v1',
            artifact_class='unqualified_source_geometry_report',
            source=dict(reference=source_reference, sha256=geometry.source_sha256,
                expected_sha256=expected, version=geometry.version,
                simulation_date=geometry.simulation_date.isoformat(), title=geometry.title,
                archive_sha256=archive, archive_verification='DECLARED_NOT_VERIFIED' if archive else 'NOT_SUPPLIED',
                member_name=member_name, evidence_class='CALLER_SUPPLIED_GEOMETRY_NOT_EXPERIMENTAL_PERFORMANCE'),
            columns=[dict(index=i,key=key, supplied_unit=None if units is None else units[i],
                unit_binding='PRESERVED_SOURCE_CELL' if units else 'UNRESOLVED_SOURCE_HEADER',
                definition='See preserved nonstation lines; pitch columns are distinct source fields, not inferred TWIST.')
                for i,key in enumerate(COLUMN_KEYS)],
            parent=parent, parent_sha256=parent_sha, radii=radii, cuts=cuts,
            diagnostics=diagnostics, performance_comparison=None,
            si_conversion_basis='EXISTING_CORE_PE0_INCH_DEG_LAYOUT; unresolved header bindings remain diagnostics',
            code_sha256={key:hashlib.sha256(path.read_bytes()).hexdigest() for key,path in (
                ('application/apc_pe0_geometry_report.py',Path(__file__)),
                ('core/apc_pe0.py',Path(__file__).resolve().parents[1]/'core/apc_pe0.py'))},
            physical_qualification=False, unestablished={key:None for key in (
                'complete_3d_surface_equivalence','joint_clearance','strength','safe_winner','bem_performance')})
        canonical = _canonical(doc)
        return PE0GeometryReport(canonical, hashlib.sha256(canonical.encode()).hexdigest(), _table(doc))
    except (ValueError, TypeError, UnicodeError, OverflowError, OSError, IndexError) as exc:
        if isinstance(exc, PE0ReportError):
            raise
        raise PE0ReportError(str(exc)) from exc


def _table(doc):
    def text(value):
        return str(value).replace('|','\\|').replace('\r',' ').replace('\n',' ')
    lines = ['# Local PE0 source geometry', '', 'Source: '+text(doc['source']['reference']),
        'Member SHA-256: '+doc['source']['sha256'], 'Parent SHA-256: '+doc['parent_sha256'],
        'All source stations retained. No performance, strength or safe-location acceptance.',
        'physical_qualification=false', '', '## Radius conventions', '']
    lines += [key+': '+text(value) for key,value in doc['radii'].items()]
    lines += ['', '## Complete source table (source units, plus explicitly converted SI fields)', '',
        '| parent index | '+ ' | '.join(COLUMN_KEYS)+' | r_m | chord_m | twist_rad | region |',
        '| '+ ' | '.join(['---']*19)+' |']
    for row in doc['parent']['rows']:
        cells = [row['parent_index'], *row['lexemes'], *row['si'].values(), row['applicability']['region']]
        lines.append('| '+' | '.join(text(v) for v in cells)+' |')
    lines += ['', '## Source units / declarations / definitions (unchanged text)', '']
    lines += ['> '+text(row['text']) for row in doc['parent']['nonstation_lines']]
    for cut in doc['cuts']:
        lines += ['', '## '+cut['id'], '', 'Global hinge radius m: '+str(cut['hinge_radius_m']),
            'Diagnostics: '+text(cut['diagnostics']), 'Comparison: '+cut['station_comparison']['status']]
        for role, child in cut['components'].items():
            lines.append(role+': parent indices='+text(child['parent_indices'])+'; coverage='+text(child['coverage'])+'; diagnostics='+text(child['diagnostics']))
    lines += ['', 'Diagnostics: '+text(doc['diagnostics']),
        'Section coordinates/blending, complete surface, joint strength and optimum hinge remain unresolved.']
    return '\n'.join(lines)+'\n'
