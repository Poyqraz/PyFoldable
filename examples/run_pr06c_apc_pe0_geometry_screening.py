"""Screen caller-supplied APC PE0 geometry against the frozen PR-06C fixture.

The APC file is intentionally not distributed by PyFoldable. Download it for your
own permitted use, then pass its local path explicitly to this script.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pyfoldable.core import (
    BEMAnnulusSettings,
    BEMRotorSettings,
    RotorBenchmarkPolicy,
    build_rotor_benchmark_proxy_polar_family,
    evaluate_rotor_benchmark_variant,
    load_rotor_benchmark_fixture,
    parse_apc_pe0,
    radial_convergence_evidence,
    run_rotor_benchmark_cases,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "rotor_benchmark"
    / "uiuc_apcsf_10x4.7_v1.json"
)
SOURCE_URL = (
    "https://www.apcprop.com/propeller-technical-data-files/"
    "10x47SF-PERF.PE0"
)
EXPECTED_SHA256 = "f38bdb92f65053a7791a6ba492a89da69651f1a11983724953272211db5d39c8"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pe0", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--accept-source-update",
        action="store_true",
        help="Parse a changed APC file while recording its observed digest.",
    )
    arguments = parser.parse_args()

    geometry = parse_apc_pe0(
        arguments.pe0.read_bytes(),
        source_url=SOURCE_URL,
        expected_sha256=None if arguments.accept_source_update else EXPECTED_SHA256,
    )
    fixture = load_rotor_benchmark_fixture(FIXTURE)
    family = build_rotor_benchmark_proxy_polar_family()
    blade = geometry.blade(airfoil_id=family.airfoil_id)
    annulus = BEMAnnulusSettings(loading_branch="signed_nonreversed")
    settings = BEMRotorSettings(80, "station_span", annulus)
    convergence = radial_convergence_evidence(
        fixture,
        family,
        point_ids=(
            "static-6528",
            "forward-6512-j0199",
            "forward-6020-j0623",
        ),
        annulus_settings=annulus,
        blade=blade,
    )
    predictions = run_rotor_benchmark_cases(
        fixture, family, settings=settings, blade=blade
    )
    result = evaluate_rotor_benchmark_variant(
        fixture,
        predictions,
        RotorBenchmarkPolicy(),
        variant_id="apc-pe0-v2025-1001_proxy-screening",
        representative_polar_evidence=False,
        radial_terminal_delta=convergence["maximum_terminal_relative_delta"],
        settings=settings,
        polar_contract={
            "evidence_class": "manufacturer_geometry_with_analytic_polar_proxy",
            "representative_polar_evidence": False,
            "geometry_source_url": geometry.source_url,
            "geometry_sha256": geometry.source_sha256,
            "geometry_version": geometry.version,
            "geometry_simulation_date": geometry.simulation_date.isoformat(),
            "revision_limitation": (
                "The current APC geometry revision is not proven identical to the "
                "historical UIUC wind-tunnel specimen."
            ),
        },
    )
    report = {
        "passed": result["passed"],
        "geometry": {
            "title": geometry.title,
            "version": geometry.version,
            "simulation_date": geometry.simulation_date.isoformat(),
            "source_url": geometry.source_url,
            "sha256": geometry.source_sha256,
            "station_count": len(geometry.stations),
            "airfoil_transitions": [
                {
                    "station_m": transition.station_m,
                    "airfoil_id": transition.airfoil_id,
                }
                for transition in geometry.airfoil_transitions
            ],
        },
        "radial_convergence": convergence,
        "variant": result,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(rendered, end="")
    else:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
        print(f"PR-06C APC PE0 screening evidence: {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
