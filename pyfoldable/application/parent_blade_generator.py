"""One declared internal station realization, two direct complementary cuts.

No continuous surface evaluation, missing-station synthesis or solver execution.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import tempfile

from .blade_stations import parse_station_bundle
from .design_draft import DesignDraftInputs, DraftUnitSelection, build_design_draft
from .parent_blade_comparison import compare_parent_blade_stations
from pyfoldable.core.airfoil import airfoil_coordinate_sha256, validate_airfoil_definition
from pyfoldable.core.config import load_design_config
from pyfoldable.core.models import AirfoilDefinition
from pyfoldable.core.units import normalize_quantity


class ParentGenerationError(ValueError):
    """Invalid request or unsupported parent geometry; no inferred replacement."""


@dataclass(frozen=True)
class ParentCutReport:
    canonical_json: str
    sha256: str
    comparison_table: str


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False)


def _bytes(value):
    return _json(value).encode('utf-8')


def _text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 2048:
        raise ParentGenerationError('Require bounded nonempty declaration text.')
    value.encode('utf-8')


def _supported(source):
    hinge = source.hinge
    if hinge is None or (hinge.axial_offset_m, hinge.tangential_offset_m,
            hinge.axis_azimuth_rad, hinge.axis_elevation_rad,
            hinge.deployed_angle_rad, hinge.stop_angle_rad) != (0., 0., 0., math.pi/2, 0., 0.):
        raise ParentGenerationError('Unsupported hinge offsets/axis/deployed transform.')
    if len({s.airfoil_id for s in source.blade.stations}) != 1:
        raise ParentGenerationError('Unsupported mixed-profile station geometry.')


def _coverage(rows, low, high):
    first = rows[0]['radius'] if rows else None
    last = rows[-1]['radius'] if rows else None
    return dict(required_span_m=[low, high],
        supplied_span_m=[first, last] if rows else None,
        root_gap_m=None if first is None else first-low,
        tip_gap_m=None if last is None else high-last,
        supplied_span_complete=bool(rows) and first == low and last == high,
        continuous_geometry_established=None)


def _modifications(value, counts):
    if not isinstance(value, (tuple, list)) or len(value) > 128:
        raise ParentGenerationError('Joint modifications require at most 128 rows.')
    for row in value:
        if not isinstance(row, dict) or set(row) != {'component', 'child_index', 'description', 'reference', 'revision'}:
            raise ParentGenerationError('Invalid joint-modification fields.')
        role, index = row['component'], row['child_index']
        if not isinstance(role, str) or role not in counts:
            raise ParentGenerationError('Invalid joint component.')
        if index is not None and (type(index) is not int or not 0 <= index < counts[role]):
            raise ParentGenerationError('Invalid joint child_index.')
        for key in ('description', 'reference', 'revision'):
            _text(row[key])
    return json.loads(_json(value))  # detach caller-owned records


def generate_parent_blade_cuts(source_path: str | Path, inputs: DesignDraftInputs,
    profile: AirfoilDefinition, *, hinge_radii_m: tuple[float, float],
    frame_id: str, evidence_label: str, joint_reference: str | None = None,
    joint_modifications=((), ())) -> ParentCutReport:
    """Generate once; copy stored SI stations into two independently reported cuts.

    Parent-generation controls apply once before the immutable station snapshot.
    Equal-to-hinge stations belong to both children. Sparse child rows are retained
    as diagnostics and are never padded to satisfy the existing two-row parser.
    Only a declared common identity deployed shaft frame is supported.
    """
    try:
        _text(frame_id); _text(evidence_label)
        if joint_reference is not None:
            _text(joint_reference)
        if not isinstance(inputs, DesignDraftInputs):
            raise ParentGenerationError('Require DesignDraftInputs.')
        if not isinstance(hinge_radii_m, (tuple, list)) or len(hinge_radii_m) != 2:
            raise ParentGenerationError('Declare exactly two hinge radii.')
        if any(isinstance(h, bool) or not isinstance(h, (int, float)) for h in hinge_radii_m):
            raise ParentGenerationError('Hinge radii require finite numeric SI.')
        hinges = tuple(float(h) for h in hinge_radii_m)
        if not all(math.isfinite(h) for h in hinges) or hinges[0] == hinges[1]:
            raise ParentGenerationError('Declare two distinct finite hinge radii.')
        if not isinstance(joint_modifications, (tuple, list)) or len(joint_modifications) != 2:
            raise ParentGenerationError('Declare joint modifications for each cut separately.')
        if normalize_quantity(inputs.preview_fold_angle, 'angle').si_value != 0:
            raise ParentGenerationError('Only the deployed zero-angle pose is supported.')
        profile = validate_airfoil_definition(profile)
        if profile.id != inputs.airfoil_id.strip() or len(profile.coordinates) > 601:
            raise ParentGenerationError('Selected profile identity/coordinate count is unsupported.')
        source_path = Path(source_path)
        original = source_path.read_bytes()
        source_sha = hashlib.sha256(original).hexdigest()
        _supported(load_design_config(source_path))
        draft = build_design_draft(source_path, inputs, airfoil_definition=profile,
            units=DraftUnitSelection(length='m', angle='rad', angular_speed='rad/s'))
        if source_path.read_bytes() != original or draft.source_sha256 != source_sha:
            raise ParentGenerationError('Source changed during parent generation.')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'parent.toml'; path.write_text(draft.toml, encoding='utf-8')
            model = load_design_config(path)
        _supported(model)
        diameter, hub = model.blade.diameter_m, model.blade.hub_radius_m
        if any(not hub < h < diameter/2 for h in hinges):
            raise ParentGenerationError('Hinges must be inside the declared hub-to-tip span.')
        reloaded_profile = next(p for p in model.airfoils if p.id == profile.id)
        coordinate_sha = airfoil_coordinate_sha256(profile)
        if airfoil_coordinate_sha256(reloaded_profile) != coordinate_sha:
            raise ParentGenerationError('Draft coordinate identity changed.')
        parent = parse_station_bundle(_bytes(dict(schema_version=1,
            units={'length': 'm', 'angle': 'rad'}, diameter=diameter, hub_radius=hub,
            airfoil_id=profile.id, airfoil_coordinate_sha256=coordinate_sha,
            provenance=dict(kind='declared_design', reference=model.id,
                locator='internal design draft '+draft.draft_sha256,
                revision='parent_station_realization_v1'),
            stations=[dict(radius=s.r_over_R*(diameter/2), chord=s.chord_m, twist=s.twist_rad)
                for s in model.blade.stations])))
        parent_doc = json.loads(parent.canonical_json)
        frame = dict(id=frame_id, radial_origin='shaft_axis', pose='deployed',
            transform='identity', radius_coordinate='global_shaft_radius')
        placements, tables = [], []
        for index, hinge in enumerate(hinges):
            cut_id = f'cut-{index:02d}'
            components, diagnostics, parsed = {}, [], {}
            for role in ('fixed', 'tip'):
                indices = [i for i, s in enumerate(parent.stations)
                    if (s.radius_m <= hinge if role == 'fixed' else s.radius_m >= hinge)]
                rows = [parent_doc['stations'][i].copy() for i in indices]
                bundle = None
                if len(rows) < 2:
                    diagnostics.append(f'{role}:{len(rows)}<2')
                else:
                    child = {**parent_doc, 'stations': rows, 'provenance': dict(
                        kind='derived_geometry', reference=parent.canonical_sha256,
                        locator=f'{cut_id}/{role}; hinge={hinge.hex()}',
                        revision='parent_station_realization_v1', parent_sha256=parent.canonical_sha256)}
                    parsed[role] = parse_station_bundle(_bytes(child))
                    bundle = json.loads(parsed[role].canonical_json)
                components[role] = dict(bundle=bundle, station_rows=rows, parent_indices=indices,
                    coverage=_coverage(rows, hub if role == 'fixed' else hinge, hinge if role == 'fixed' else diameter/2))
            modifications = _modifications(joint_modifications[index],
                {role: len(c['station_rows']) for role, c in components.items()})
            has_hinge = any(s.radius_m == hinge for s in parent.stations)
            if not has_hinge:
                diagnostics.append('HINGE_STATION_ABSENT')
            declaration = comparison = None
            if len(parsed) == 2:
                declaration = dict(schema_version=1, evidence_label=evidence_label,
                    hinge_radius_m=hinge, bundle_sha256={
                        'parent': parent.canonical_sha256,
                        **{role: b.canonical_sha256 for role, b in parsed.items()}},
                    frames={role: frame.copy() for role in ('parent', 'fixed', 'tip')},
                    correspondence=[dict(component=role, child_index=ci, parent_index=pi)
                        for role, c in components.items() for ci, pi in enumerate(c['parent_indices'])],
                    joint_modifications=modifications)
                report = compare_parent_blade_stations(parent.canonical_json.encode(),
                    parsed['fixed'].canonical_json.encode(), parsed['tip'].canonical_json.encode(), _bytes(declaration))
                comparison = json.loads(report.canonical_json)
                tables.append(f'## {cut_id}\n\n'+report.comparison_table)
            else:
                tables.append(f'## {cut_id}\n\nINSUFFICIENT_CHILD_ROWS: '+', '.join(diagnostics)+'\n')
            placements.append(dict(id=cut_id, hinge_radius_m=hinge, parent_canonical_sha256=parent.canonical_sha256,
                status='REPORTED' if comparison is not None else 'INSUFFICIENT_CHILD_ROWS',
                hinge_station_present=has_hinge, components=components,
                parent_coverage=_coverage(parent_doc['stations'], hub, diameter/2),
                diagnostics=diagnostics, declaration=declaration, comparison=comparison,
                joint_modifications=modifications))
        code_paths = ('application/parent_blade_generator.py', 'application/design_draft.py',
            'application/blade_stations.py', 'application/parent_blade_comparison.py',
            'core/config.py', 'core/airfoil.py', 'core/profile_catalog.py', 'core/units.py')
        package = Path(__file__).resolve().parents[1]
        doc = dict(schema_version=1, method='parent_station_realization_v1',
            artifact_class='unqualified_generated_station_cuts', evidence_label=evidence_label,
            source_sha256=source_sha, draft_sha256=draft.draft_sha256, parent_draft_toml=draft.toml,
            generation_controls=asdict(inputs), parent_canonical_sha256=parent.canonical_sha256,
            parent_bundle=parent_doc, profile=dict(id=profile.id, source=profile.source,
                coordinates=profile.coordinates, metadata=dict(profile.metadata)),
            code_sha256={p: hashlib.sha256((package/p).read_bytes()).hexdigest() for p in code_paths},
            frame=frame, joint_reference=joint_reference, placements=placements,
            physical_qualification=False, unestablished={key: None for key in (
                'complete_3d_surface_equivalence', 'joint_solid_geometry', 'joint_clearance',
                'movable_mass_cg_inertia', 'strength', 'safe_winner')})
        canonical = _json(doc)
        heading = '# Generated station cuts\n\n'+evidence_label+'\nphysical_qualification=false\n\n'
        return ParentCutReport(canonical, hashlib.sha256(canonical.encode()).hexdigest(), heading+'\n'.join(tables))
    except (ValueError, TypeError, AttributeError, OverflowError, OSError, StopIteration) as exc:
        if isinstance(exc, ParentGenerationError):
            raise
        raise ParentGenerationError(str(exc)) from exc
