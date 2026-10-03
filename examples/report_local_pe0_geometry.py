# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
"""Report caller-supplied local PE0 geometry; no download or solver execution."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(PROJECT_ROOT))

from pyfoldable.application.apc_pe0_geometry_report import (  # noqa: E402
    MAX_PE0_BYTES, PE0ReportError, report_pe0_geometry,
)
from pyfoldable.core.units import normalize_quantity  # noqa: E402


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('--source-reference',required=True)
    parser.add_argument('--expected-sha256')
    parser.add_argument('--archive-sha256',help='Declared provenance only; member bytes do not verify archive identity')
    parser.add_argument('--member-name')
    parser.add_argument('--nominal-diameter',default='13 in')
    parser.add_argument('--hinges',nargs=2,default=['101.6 mm','127.0 mm'])
    parser.add_argument('--format',choices=('json','table'),default='json')
    args=parser.parse_args()
    try:
        with args.source.open('rb') as stream:
            raw=stream.read(MAX_PE0_BYTES+1)
        result=report_pe0_geometry(raw,source_reference=args.source_reference,
            nominal_diameter_m=normalize_quantity(args.nominal_diameter,'length').si_value,
            hinge_radii_m=tuple(normalize_quantity(h,'length').si_value for h in args.hinges),
            expected_sha256=args.expected_sha256,archive_sha256=args.archive_sha256,member_name=args.member_name)
    except (PE0ReportError,ValueError,OSError) as exc:
        parser.exit(2,f'Geometry report unavailable: {exc}\n')
    print(result.canonical_json if args.format=='json' else result.comparison_table,
        end='\n' if args.format=='json' else '')


if __name__=='__main__':
    main()
