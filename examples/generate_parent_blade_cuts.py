"""Synthetic software demonstration: one internal parent, two sparse station cuts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pyfoldable.application.design_draft import DesignDraftInputs  # noqa: E402
from pyfoldable.application.parent_blade_generator import (  # noqa: E402
    ParentGenerationError, generate_parent_blade_cuts,
)
from pyfoldable.core.config import load_design_config  # noqa: E402
from pyfoldable.core.units import normalize_quantity  # noqa: E402
from pyfoldable.core.profile_catalog import load_project_airfoil  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=PROJECT_ROOT/'configs/designs/TIP_HINGED_250_CANONICAL.toml')
    parser.add_argument('--hinges', nargs=2, required=True, metavar=('FIRST', 'SECOND'), help='Two explicit length quantities, e.g. "75 mm" "100 mm"')
    parser.add_argument('--format', choices=('json', 'table'), default='json')
    parser.add_argument('--output-dir', type=Path, help='New directory only; never overwrite inputs or previous reports')
    args = parser.parse_args()
    try:
        model = load_design_config(args.source)
        if model.hinge is None or not model.operating_conditions:
            raise ParentGenerationError('Require an identified hinge and operating condition.')
        condition = model.operating_conditions[0]
        def si(value, unit):
            return {'value': value, 'unit': unit}
        inputs = DesignDraftInputs(si(model.blade.diameter_m, 'm'), si(model.blade.hub_radius_m, 'm'),
            si(model.hinge.radius_m, 'm'), model.blade.blade_count, model.blade.stations[0].airfoil_id,
            1., 1., '0 rad', si(condition.angular_speed_rad_s, 'rad/s'), si(condition.forward_speed_m_s, 'm/s'),
            si(condition.air_density_kg_m3, 'kg/m^3'), si(condition.dynamic_viscosity_pa_s, 'Pa*s'),
            si(condition.temperature_k, 'K'), si(condition.pressure_pa, 'Pa'))
        result = generate_parent_blade_cuts(args.source, inputs,
            load_project_airfoil(inputs.airfoil_id),
            hinge_radii_m=tuple(normalize_quantity(h, 'length', field='hinge').si_value for h in args.hinges),
            frame_id='declared-deployed-shaft', evidence_label='synthetic software check; declared internal design')
        if args.output_dir is not None:
            args.output_dir.mkdir(parents=True, exist_ok=False)
            doc = json.loads(result.canonical_json)
            files = {'parent.json': doc['parent_bundle']}
            for cut in doc['placements']:
                for role, component in cut['components'].items():
                    if component['bundle'] is not None:
                        files[f"{cut['id']}-{role}.json"] = component['bundle']
                if cut['declaration'] is not None:
                    files[f"{cut['id']}-declaration.json"] = cut['declaration']
            for name, value in files.items():
                (args.output_dir/name).write_text(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False),encoding='utf-8')
            (args.output_dir/'report.json').write_text(result.canonical_json,encoding='utf-8')
            (args.output_dir/'report.md').write_text(result.comparison_table,encoding='utf-8')
            (args.output_dir/'parent.toml').write_text(doc['parent_draft_toml'],encoding='utf-8')
    except (ValueError, OSError) as exc:
        parser.exit(2, f'Generation unavailable: {exc}\n')
    print(result.canonical_json if args.format == 'json' else result.comparison_table,
        end='\n' if args.format == 'json' else '')


if __name__ == '__main__':
    main()
