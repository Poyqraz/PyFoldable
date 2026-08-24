"""Generate the screening-only PR-06D opening-angle sweep."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from pyfoldable.application.analysis_run import (
    DEFAULT_PR06D_FIXTURE,
    build_pr06d_opening_sensitivity_report,
    render_pr06d_opening_sensitivity_markdown,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = DEFAULT_PR06D_FIXTURE
DEFAULT_JSON = PROJECT_ROOT / "reports" / "pr06d_opening_sensitivity.json"
DEFAULT_MARKDOWN = PROJECT_ROOT / "reports" / "pr06d_opening_sensitivity.md"


build_report = build_pr06d_opening_sensitivity_report
render_markdown = render_pr06d_opening_sensitivity_markdown


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()
    report = build_report(args.fixture, provenance_root=PROJECT_ROOT)
    report_json = json.dumps(
        report,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_bytes(report_json.encode("utf-8"))
    args.markdown.write_bytes(render_markdown(report).encode("utf-8"))


if __name__ == "__main__":
    main()
