"""Build the final fail-closed PR-06C physical-qualification decision."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from pyfoldable.core import (
    PR06CPhysicalGatePolicy,
    assess_pr06c_physical_gate,
    canonical_json_sha256,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BENCHMARK = PROJECT_ROOT / "reports" / "pr06c_fixed_propeller_benchmark.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "reports" / "pr06c_physical_gate.json"
FIXTURE_SHA256 = "c6f04a4d32ea9c4421db38ec67a2164be0b81b13c64b0a81718792dfd047531b"


def _read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def build_report(
    benchmark_path: Path = DEFAULT_BENCHMARK,
    model_form_review_path: Path | None = None,
) -> Mapping[str, Any]:
    benchmark = _read_json(benchmark_path)
    review = (
        None if model_form_review_path is None else _read_json(model_form_review_path)
    )
    policy = PR06CPhysicalGatePolicy(
        benchmark_id="pr06c-uiuc-apcsf-10x4.7-qualification-v1",
        fixture_sha256=FIXTURE_SHA256,
        required_airfoil_ids=("E63", "APC12"),
        allowed_provider_names=("xfoil-subprocess",),
        required_model_variants=(
            "qualified_2d",
            "rotational_augmentation",
            "tip_wake_candidate",
        ),
    )
    decision = assess_pr06c_physical_gate(benchmark, review, policy=policy)
    report = dict(decision.as_mapping())
    report.update(
        {
            "benchmark_report": {
                "path": benchmark_path.relative_to(PROJECT_ROOT).as_posix(),
                "sha256": canonical_json_sha256(benchmark),
            },
            "evidence_inventory": {
                "e63_coordinates": {
                    "status": "official_public_caller_supplied_input_available",
                    "source": "https://m-selig.ae.illinois.edu/ads/coord_seligFmt/e63.dat",
                    "sha256": "eb90138d5e0b2476c99e431651475e3a6b058872b368e0793e3b5e0383988f9d",
                },
                "apc_pe0_geometry": {
                    "status": "official_caller_supplied_input_verified",
                    "source": "https://www.apcprop.com/technical-information/file-downloads/",
                    "sha256": "f38bdb92f65053a7791a6ba492a89da69651f1a11983724953272211db5d39c8",
                    "version": "v2025-1001",
                    "simulation_date": "2026-02-24",
                    "section_note": "PE0 declares APC12 equivalent to NACA 4412.",
                },
                "apc12_coordinate_identity": {
                    "status": "required_not_captured",
                    "reason": "No reviewed APC12/NACA-4412 coordinate document and digest is bound to a provider capture.",
                },
                "representative_provider_capture": {
                    "status": "required_not_captured",
                    "required_backend": "XFOIL 6.99 via xfoil-subprocess adapter 2",
                },
                "independent_model_form_review": {
                    "status": "required_not_supplied" if review is None else "supplied",
                },
            },
            "reviewed_manufacturer_geometry_screen": {
                "input_sha256": "f38bdb92f65053a7791a6ba492a89da69651f1a11983724953272211db5d39c8",
                "variant_id": "apc-pe0-v2025-1001_proxy-screening",
                "point_count": 50,
                "solution_coverage": 1.0,
                "overall": {
                    "ct_wmape": 0.16226950219319236,
                    "cp_wmape": 0.16976253779131012,
                    "ct_normalized_bias": -0.14073505165828132,
                    "cp_normalized_bias": -0.13418960462057053,
                },
                "static": {
                    "ct_wmape": 0.060339267927450244,
                    "cp_wmape": 0.06472539470118317,
                },
                "forward": {
                    "ct_wmape": 0.2567939730710669,
                    "cp_wmape": 0.2319212605223408,
                },
                "passed": False,
                "qualification": "manufacturer_geometry_with_nonrepresentative_analytic_proxy",
            },
            "qualification_boundary": (
                "PR-06D software equivalence remains usable, but folded-state physical "
                "accuracy remains screening-only until this report passes."
            ),
        }
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--model-form-review", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--require-pass", action="store_true")
    arguments = parser.parse_args()
    report = build_report(arguments.benchmark, arguments.model_form_review)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        "PR-06C physical gate: "
        + ("PASS" if report["passed"] else "BLOCKED")
        + f"; evidence: {arguments.output}"
    )
    return 2 if arguments.require_pass and not report["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
