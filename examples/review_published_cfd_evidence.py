"""Compare published APC 10x4.7 CFD facts with frozen project evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from pyfoldable.core import (
    load_cfd_reference_fixture,
    load_rotor_benchmark_fixture,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CFD_FIXTURE = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "cfd_reference"
    / "apcsf_10x4.7_published_v1.json"
)
DEFAULT_UIUC_FIXTURE = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "rotor_benchmark"
    / "uiuc_apcsf_10x4.7_v1.json"
)
DEFAULT_BEM_REPORT = PROJECT_ROOT / "reports" / "pr06c_fixed_propeller_benchmark.json"
DEFAULT_JSON = PROJECT_ROOT / "reports" / "pr06c_published_cfd_review.json"
DEFAULT_MARKDOWN = PROJECT_ROOT / "reports" / "pr06c_published_cfd_review.md"


def _relative_error_percent(value: float, reference: float) -> float:
    return 100.0 * (value - reference) / reference


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_report(
    cfd_fixture_path: Path = DEFAULT_CFD_FIXTURE,
    uiuc_fixture_path: Path = DEFAULT_UIUC_FIXTURE,
    bem_report_path: Path = DEFAULT_BEM_REPORT,
) -> Mapping[str, Any]:
    cfd = load_cfd_reference_fixture(cfd_fixture_path)
    uiuc = load_rotor_benchmark_fixture(uiuc_fixture_path)
    bem = json.loads(bem_report_path.read_text(encoding="utf-8"))
    uiuc_static = {
        int(point.rpm): point
        for point in uiuc.points
        if point.regime == "static"
    }
    bem_by_id = {
        prediction["point_id"]: prediction
        for prediction in bem["selected_variant"]["predictions"]
    }

    comparisons = []
    for point in cfd.points:
        if point.quantity != "power_coefficient":
            continue
        reference = uiuc_static[int(point.rpm)].power_coefficient
        prediction = bem_by_id[f"static-{int(point.rpm)}"]["power_coefficient"]
        comparisons.append(
            {
                "point_id": point.id,
                "rpm": point.rpm,
                "cells": point.cells,
                "turbulence_model": point.turbulence_model,
                "uiuc_cp": reference,
                "published_cfd_cp": point.value,
                "published_cfd_error_percent_recomputed": _relative_error_percent(
                    point.value, reference
                ),
                "published_cfd_deviation_percent_reported": (
                    point.reported_deviation_percent
                ),
                "pyfoldable_proxy_cp": prediction,
                "pyfoldable_proxy_error_percent": _relative_error_percent(
                    prediction, reference
                ),
                "qualification_eligible": False,
            }
        )

    bau_points = {
        point.id: point
        for point in cfd.points
        if point.source_id == "sunan-bau-2014"
    }
    lower = uiuc_static[4880]
    upper = uiuc_static[5147]
    weight = (5000.0 - lower.rpm) / (upper.rpm - lower.rpm)
    interpolated_ct = lower.thrust_coefficient + weight * (
        upper.thrust_coefficient - lower.thrust_coefficient
    )
    rho = uiuc.air_density_kg_m3
    rotations_per_second = 5000.0 / 60.0
    uiuc_interpolated_thrust = (
        interpolated_ct
        * rho
        * rotations_per_second**2
        * uiuc.diameter_m**4
    )
    bau_mean = bau_points["bau-5000-mean"].value
    bau_periodic = bau_points["bau-5000-periodic-half-domain"].value

    return {
        "schema_version": 1,
        "kind": "pr06c-published-cfd-context-review",
        "decision": "literature_context_integrated_pr06c_still_blocked",
        "qualification": cfd.qualification,
        "independent_project_review": False,
        "target_geometry_id": cfd.target_geometry_id,
        "source_count": len(cfd.sources),
        "numeric_point_count": len(cfd.points),
        "inputs": {
            "cfd_fixture": {
                "path": str(cfd_fixture_path.relative_to(PROJECT_ROOT)),
                "sha256": _sha256(cfd_fixture_path),
            },
            "uiuc_fixture": {
                "path": str(uiuc_fixture_path.relative_to(PROJECT_ROOT)),
                "sha256": _sha256(uiuc_fixture_path),
            },
            "bem_report": {
                "path": str(bem_report_path.relative_to(PROJECT_ROOT)),
                "sha256": _sha256(bem_report_path),
            },
        },
        "sources": [vars(source) for source in cfd.sources],
        "static_cp_comparisons": comparisons,
        "strongest_static_cp_result": {
            "source_id": "wan-tsai-icas2020",
            "turbulence_model": "SST k-omega",
            "comparison_count": 2,
            "maximum_absolute_recomputed_error_percent": max(
                abs(item["published_cfd_error_percent_recomputed"])
                for item in comparisons
                if item["turbulence_model"] == "SST k-omega"
            ),
        },
        "bau_5000_rpm_context": {
            "published_mean_thrust_n": bau_mean,
            "published_standard_deviation_n": (
                bau_points["bau-5000-standard-deviation"].value
            ),
            "published_periodic_half_domain_thrust_n": bau_periodic,
            "uiuc_ct_linearly_interpolated": interpolated_ct,
            "uiuc_thrust_n_derived_with_fixture_standard_atmosphere": (
                uiuc_interpolated_thrust
            ),
            "published_mean_error_percent_against_derived_uiuc": (
                _relative_error_percent(bau_mean, uiuc_interpolated_thrust)
            ),
            "interpretation": (
                "The nominal propeller name matches, but the large difference and "
                "missing run-specific atmosphere/CAD identity prevent qualification."
            ),
        },
        "gate_effect": {
            "pr06c_physical_gate_changed": False,
            "independent_review_gate_passed": False,
            "reason": (
                "External publications did not review PyFoldable and do not supply "
                "the representative E63-to-APC12 polar chain or full forward envelope."
            ),
        },
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    rows = "\n".join(
        "| {rpm:.0f} | {model} | {cells:,} | {uiuc:.4f} | {cfd:.4f} | "
        "{cfd_error:+.2f}% | {bem:.4f} | {bem_error:+.2f}% |".format(
            rpm=item["rpm"],
            model=item["turbulence_model"],
            cells=item["cells"],
            uiuc=item["uiuc_cp"],
            cfd=item["published_cfd_cp"],
            cfd_error=item["published_cfd_error_percent_recomputed"],
            bem=item["pyfoldable_proxy_cp"],
            bem_error=item["pyfoldable_proxy_error_percent"],
        )
        for item in report["static_cp_comparisons"]
    )
    bau = report["bau_5000_rpm_context"]
    sources = "\n".join(
        f"- [{source['title']}]({source['url']}) — {source['result_scope']}"
        for source in report["sources"]
    )
    return f"""# PR-06C published CFD context review

## Decision

**PR-06C remains blocked.** Published results add independent model-form context,
but they are not an independent review of PyFoldable and do not replace the missing
representative polar chain or forward-flight validation.

## Exact APC Slow Flyer 10x4.7 static CP comparison

| rpm | model | cells | UIUC CP | published CFD CP | CFD error | PyFoldable proxy CP | proxy error |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
{rows}

The strongest published static result is SST k-omega over two rpm values; its maximum
absolute error recomputed from the tabulated coefficients is
{report['strongest_static_cp_result']['maximum_absolute_recomputed_error_percent']:.2f}%.
The existing analytic-proxy BEM path is materially worse at the same points, especially
at 6528 rpm. This supports prioritizing representative Reynolds-sensitive polars rather
than retuning the frozen acceptance thresholds.

## 5000 rpm ANSYS method sensitivity

Burak Sunan reports {bau['published_mean_thrust_n']:.3f} N mean thrust with
{bau['published_standard_deviation_n']:.2f} N standard deviation across 14 selected
cases and {bau['published_periodic_half_domain_thrust_n']:.3f} N from the periodic
half-domain check. Linear interpolation of the frozen UIUC CT data, converted with the
fixture's standard-atmosphere assumption, gives
{bau['uiuc_thrust_n_derived_with_fixture_standard_atmosphere']:.3f} N. The
{abs(bau['published_mean_error_percent_against_derived_uiuc']):.1f}% gap is diagnostic,
not a validation statistic: CAD identity and run-specific atmospheric conditions are not
bound tightly enough.

## Evidence boundary

- Five primary publications were classified; nine tabulated numeric facts were retained.
- Figure-only FlowVision and oblique-flow results were not digitized.
- The APC 10x7 Fluent study is methodology-only because pitch/geometry do not match.
- No paper or figure is redistributed; only factual values, citations, and scope metadata
  are stored.
- `independent_project_review = false`; no PR-06C gate is changed.

## Primary sources

{sources}
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cfd-fixture", type=Path, default=DEFAULT_CFD_FIXTURE)
    parser.add_argument("--uiuc-fixture", type=Path, default=DEFAULT_UIUC_FIXTURE)
    parser.add_argument("--bem-report", type=Path, default=DEFAULT_BEM_REPORT)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()
    report = build_report(args.cfd_fixture, args.uiuc_fixture, args.bem_report)
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.markdown.write_text(render_markdown(report), encoding="utf-8")


if __name__ == "__main__":
    main()
