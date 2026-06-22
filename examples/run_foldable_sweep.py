"""Katlanabilir pervane RPM sweep örneği.

Örnek config dosyasını okuyarak belirli RPM aralığında performans tablosu üretir
ve ``outputs/foldable/sweep_results.csv`` dosyasına yazar.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Proje kökünü sys.path'e ekle
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pyfoldable import (  # noqa: E402
    evaluate_sweep_row,
    load_config,
    write_sweep_csv,
)
from pythrust.propellers import PropellerDatabase  # noqa: E402

RHO = 1.225


def reference_thrust_n(rpm: float, prop_entry) -> float:
    """Hover (J=0) referans pervane itkisi — reference_scaled sweep girdisi."""
    if rpm <= 0.0:
        return 0.0
    ct, _ = prop_entry.get_coefficients(rpm, 0.0)
    n = rpm / 60.0
    diameter_m = prop_entry.diameter_m
    return ct * RHO * (n**2) * (diameter_m**4)


def main() -> None:
    config_path = PROJECT_ROOT / "configs" / "foldable" / "TIP_HINGED_250_V01.json"
    output_path = PROJECT_ROOT / "outputs" / "foldable" / "sweep_results.csv"

    config = load_config(config_path)

    db = PropellerDatabase()
    db.load(PROJECT_ROOT / "data" / "propellers" / "apc_202602", strict=False)
    prop_entry = db.get(config.reference_propeller_id)
    if prop_entry is None:
        raise SystemExit(
            f"Reference propeller '{config.reference_propeller_id}' not found in database."
        )

    # Örnek RPM aralığı: 0 → 10000, 500 RPM adımlarla
    rpm_values = [float(rpm) for rpm in range(0, 10001, 500)]
    rows = [
        evaluate_sweep_row(
            rpm,
            config,
            fixed_thrust_n=reference_thrust_n(rpm, prop_entry),
        )
        for rpm in rpm_values
    ]

    written = write_sweep_csv(output_path, rows)
    print(f"Config : {config_path}")
    print(f"Output : {written}")
    print(f"Rows   : {len(rows)}")
    print()
    print("İlk 5 satır:")
    print(f"{'rpm':>8} {'theta_deg':>10} {'D_eff_m':>10} {'thrust_N':>10}  model_note")
    for row in rows[:5]:
        print(
            f"{row.rpm:8.0f} {row.theta_deg:10.2f} "
            f"{row.effective_diameter_m:10.4f} {row.thrust_n:10.4f}  {row.model_note}"
        )


if __name__ == "__main__":
    main()
