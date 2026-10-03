"""Report four supplied JSON inputs; no solvers, CAD changes or inferred stations."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pyfoldable.application.parent_blade_comparison import (  # noqa: E402
    MAX_DECLARATION_BYTES, StationComparisonError, compare_parent_blade_stations,
)
from pyfoldable.application.blade_stations import MAX_STATION_UPLOAD_BYTES  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'fixed', 'tip', 'declaration'):
        parser.add_argument(name, type=Path)
    parser.add_argument('--format', choices=('json', 'table'), default='json')
    args = parser.parse_args()
    try:
        raw = []
        for name in ('parent', 'fixed', 'tip', 'declaration'):
            limit = MAX_DECLARATION_BYTES if name == 'declaration' else MAX_STATION_UPLOAD_BYTES
            with getattr(args, name).open('rb') as stream:
                raw.append(stream.read(limit+1))
        result = compare_parent_blade_stations(*raw)
    except (OSError, StationComparisonError) as exc:
        parser.exit(2, f'Comparison unavailable: {exc}\n')
    print(result.canonical_json if args.format == 'json' else result.comparison_table, end='\n' if args.format == 'json' else '')


if __name__ == '__main__':
    main()
