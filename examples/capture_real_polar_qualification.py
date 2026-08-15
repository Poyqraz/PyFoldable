"""Capture an unreviewed XFOIL/NeuralFoil qualification artifact bundle."""

from __future__ import annotations

import argparse
import math
import platform
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

from pyfoldable import NeuralFoilProvider, XfoilProvider
from pyfoldable.core import (
    PolarAcceptanceCriteria,
    PolarErrorTolerance,
    PolarGenerationRequest,
    ProviderIdentity,
    capture_real_polar_qualification,
    load_airfoil_coordinates,
    write_polar_real_qualification_failure_bundle,
    write_polar_real_qualification_bundle,
)


EXPECTED_XFOIL = ProviderIdentity(
    "xfoil-subprocess", "1", "XFOIL", "6.99"
)
EXPECTED_NEURALFOIL = ProviderIdentity(
    "neuralfoil", "1", "NeuralFoil", "0.3.3"
)


def main() -> int:
    args = _arguments()
    airfoil = load_airfoil_coordinates(args.airfoil, airfoil_id="NACA0012")
    request = PolarGenerationRequest(
        airfoil=airfoil,
        alpha_rad=tuple(math.radians(value) for value in range(-6, 12, 2)),
        reynolds=200_000.0,
        mach=0.0,
        n_crit=9.0,
        xtr_upper=1.0,
        xtr_lower=1.0,
        scenario_id="naca0012-re200k-natural-transition",
    )
    captured_at_utc = (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
    environment = {
        "python": sys.version,
        "platform": platform.platform(),
        "xfoil_debian_package": args.xfoil_package_version,
        "packages": _installed_package_versions(),
    }
    try:
        capture = capture_real_polar_qualification(
            (XfoilProvider(args.xfoil), NeuralFoilProvider()),
            request,
            expected_providers=(EXPECTED_XFOIL, EXPECTED_NEURALFOIL),
            reference_provider=EXPECTED_XFOIL,
            case_name="naca0012_re200k_real_v1",
            source_revision=args.source_revision,
            captured_at_utc=captured_at_utc,
            criteria=PolarAcceptanceCriteria(
                cl=PolarErrorTolerance(absolute=0.05, relative=0.02),
                cd=PolarErrorTolerance(absolute=0.002, relative=0.10),
                cm=PolarErrorTolerance(absolute=0.01, relative=0.05),
                minimum_coverage=1.0,
                require_usable_match=True,
            ),
            environment=environment,
        )
    except Exception as error:
        destination = write_polar_real_qualification_failure_bundle(
            case_name="naca0012_re200k_real_v1",
            source_revision=args.source_revision,
            captured_at_utc=captured_at_utc,
            expected_providers=(EXPECTED_XFOIL, EXPECTED_NEURALFOIL),
            reference_provider=EXPECTED_XFOIL,
            request=request,
            environment=environment,
            error=error,
            output_directory=args.output_dir,
        )
        print(
            f"Qualification failure evidence written to {destination}: "
            f"{type(error).__name__}: {error}",
            file=sys.stderr,
        )
        return 2
    destination = write_polar_real_qualification_bundle(capture, args.output_dir)
    outcome = "passed" if capture.benchmark.passed else "requires review"
    print(f"Qualification capture written to {destination} ({outcome}).")
    return 0


def _arguments() -> argparse.Namespace:
    repository_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Run pinned real backends and write unreviewed evidence."
    )
    parser.add_argument(
        "--airfoil",
        type=Path,
        default=repository_root / "configs" / "airfoils" / "NACA0012_81.dat",
    )
    parser.add_argument("--xfoil", default="xfoil")
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--xfoil-package-version", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def _installed_package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for distribution in metadata.distributions():
        name = distribution.metadata.get("Name")
        if isinstance(name, str) and name:
            versions[name] = distribution.version
    return dict(sorted(versions.items(), key=lambda item: item[0].casefold()))


if __name__ == "__main__":
    raise SystemExit(main())
