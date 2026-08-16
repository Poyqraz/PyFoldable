"""Compare two hash-manifested real-backend qualification bundles."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pyfoldable.core import write_polar_real_qualification_comparison


def main() -> int:
    args = _arguments()
    try:
        destination, report = write_polar_real_qualification_comparison(
            args.first_bundle,
            args.second_bundle,
            args.output,
        )
    except Exception as error:
        if args.output.exists():
            print(f"Qualification comparison failed: {error}", file=sys.stderr)
            return 2
        args.output.parent.mkdir(parents=True, exist_ok=True)
        failure = {
            "schema_version": 1,
            "kind": "polar-real-backend-qualification-comparison-failure",
            "reproducible": False,
            "promotion_allowed": False,
            "error_type": type(error).__name__,
            "error_message": " ".join(str(error).split())[:512],
        }
        args.output.write_text(
            json.dumps(failure, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Qualification comparison failed: {error}", file=sys.stderr)
        return 2
    outcome = "reproducible" if report["reproducible"] else "different"
    print(f"Qualification comparison written to {destination} ({outcome}).")
    return 0 if report["reproducible"] else 2


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify and compare two real-backend qualification bundles."
    )
    parser.add_argument("first_bundle", type=Path)
    parser.add_argument("second_bundle", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
