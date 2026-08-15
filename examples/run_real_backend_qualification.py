"""Run PR-05E against installed, version-pinned XFOIL/NeuralFoil backends."""

from __future__ import annotations

import argparse

from pyfoldable import (
    ProviderIdentity,
    load_polar_family_config,
    qualify_real_polar_backends,
)


EXPECTED_PROVIDERS = (
    ProviderIdentity("xfoil-subprocess", "1", "XFOIL", "6.99"),
    ProviderIdentity("neuralfoil", "1", "NeuralFoil", "0.3.3"),
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Produce an auditable real-backend polar qualification artifact."
    )
    parser.add_argument("config", help="PR-05C polar-family TOML/JSON configuration")
    parser.add_argument("fixtures", nargs="+", help="Reviewed golden fixture JSON files")
    parser.add_argument("--output", required=True, help="Qualification report JSON path")
    arguments = parser.parse_args()

    config = load_polar_family_config(arguments.config)
    qualification = qualify_real_polar_backends(
        config,
        arguments.fixtures,
        expected_providers=EXPECTED_PROVIDERS,
    )
    qualification.write_json(arguments.output)
    print(
        f"Wrote {arguments.output}: "
        f"{'PASS' if qualification.passed else 'FAIL'}"
    )
    return 0 if qualification.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
