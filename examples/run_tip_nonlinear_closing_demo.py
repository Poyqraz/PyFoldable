"""Nonlineer uç açılması + aero kapanma momenti demo.

Opt-in iki fizik eklentisini gösterir:
- ``kinematics_mode = "nonlinear_saturation"``: eşik civarı keskin/eksponansiyel açılma
- ``aero_closing``: eksenel akışa bağlı kapanma momenti -> kısmi açılma

Örnek config: ``configs/foldable/TIP_HINGED_250_V03.json``. Herhangi bir ön koşul
script'i gerektirmez; yalnızca stdout'a yazar.
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pyfoldable import (  # noqa: E402
    closing_moment_nm,
    load_config,
    theta_deg_from_rpm,
    theta_deg_nonlinear_saturation,
)


def main() -> None:
    config_path = PROJECT_ROOT / "configs" / "foldable" / "TIP_HINGED_250_V03.json"
    config = load_config(config_path)
    rpm_values = [float(rpm) for rpm in range(0, 8001, 1000)]

    print(f"Config : {config_path}")
    print(
        f"Mode   : {config.kinematics.kinematics_mode} "
        f"(curve_sharpness={config.kinematics.curve_sharpness})"
    )
    print(f"Aero   : {config.aero_closing}")
    print()

    print("1) Nonlineer açılma yasası vs doğrusal referans (k=0):")
    print(f"{'rpm':>8} {'nonlinear_deg':>14} {'linear_deg':>12}")
    linear_kin = dataclasses.replace(config.kinematics, curve_sharpness=0.0)
    for rpm in rpm_values:
        nonlinear = theta_deg_from_rpm(rpm, config)
        linear = theta_deg_nonlinear_saturation(rpm, config.hinge, linear_kin)
        print(f"{rpm:8.0f} {nonlinear:14.2f} {linear:12.2f}")
    print()

    print("2) Aero kapanma momentinin kısmi açılma etkisi (moment_based denge):")
    moment_based = dataclasses.replace(
        config,
        kinematics=dataclasses.replace(config.kinematics, kinematics_mode="moment_based"),
    )
    closing_off = dataclasses.replace(
        moment_based,
        aero_closing=dataclasses.replace(
            moment_based.aero_closing, close_moment_gain=0.0
        ),
    )
    print(f"{'rpm':>8} {'theta_off_deg':>14} {'theta_on_deg':>13} {'M_close_Nm':>12}")
    for rpm in rpm_values:
        theta_off = theta_deg_from_rpm(rpm, closing_off)
        theta_on = theta_deg_from_rpm(rpm, moment_based)
        # Kuazi-statik denge theta'dan bağımsız (tam-açık referans) M_close kullanır.
        m_close = closing_moment_nm(
            rpm, moment_based.hinge.theta_max_deg, moment_based
        )
        print(f"{rpm:8.0f} {theta_off:14.2f} {theta_on:13.2f} {m_close:12.5f}")


if __name__ == "__main__":
    main()
