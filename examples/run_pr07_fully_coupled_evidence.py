"""Generate the PR-07 numerical motor/rotor equilibrium evidence."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping

from pyfoldable.core import (
    AeroLoadSample,
    CoupledEquilibriumEvidence,
    CoupledMultistartCase,
    CoupledSolverSettings,
    solve_coupled_operating_point,
)
from pythrust.propulsion.models import BatterySpec, MotorSpec, SystemSpec


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = PROJECT_ROOT / "reports" / "pr07_fully_coupled_evidence.json"
DEFAULT_MARKDOWN = PROJECT_ROOT / "reports" / "pr07_fully_coupled_evidence.md"
THROTTLES = (0.40, 0.55, 0.70, 0.85, 1.00)
INITIAL_GUESSES_RPM = (300.0, 2000.0, 4000.0)


def _analytic_aero_load(rpm: float) -> AeroLoadSample:
    torque_nm = 0.02 + 1.0e-9 * rpm * rpm
    omega_rad_s = rpm * math.pi / 30.0
    return AeroLoadSample(
        rpm=rpm,
        thrust_n=2.0e-7 * rpm * rpm,
        torque_nm=torque_nm,
        shaft_power_w=torque_nm * omega_rad_s,
        source_id="pr07-analytic-quadratic-load-v1",
        qualification="software_fixture_not_physical_evidence",
    )


def build_report() -> Mapping[str, Any]:
    motor = MotorSpec(
        kv_rpm_per_v=1000.0,
        resistance_ohm=0.05,
        no_load_current_a=1.0,
        current_max_a=30.0,
    )
    battery = BatterySpec(voltage_v=12.0, discharge_efficiency=0.98)
    system = SystemSpec(resistance_ohm=0.01)
    settings = CoupledSolverSettings(scan_points=161)
    cases = []
    multistart_cases = []
    for throttle in THROTTLES:
        case = solve_coupled_operating_point(
            motor=motor,
            battery=battery,
            system=system,
            throttle=throttle,
            aero_load=_analytic_aero_load,
            settings=settings,
        )
        cases.append(case)
        roots = tuple(
            solve_coupled_operating_point(
                motor=motor,
                battery=battery,
                system=system,
                throttle=throttle,
                aero_load=_analytic_aero_load,
                settings=settings,
                initial_guess_rpm=guess,
            ).rpm
            for guess in INITIAL_GUESSES_RPM
        )
        multistart_cases.append(
            CoupledMultistartCase(
                throttle=throttle,
                initial_guesses_rpm=INITIAL_GUESSES_RPM,
                converged_roots_rpm=roots,
            )
        )
    evidence = CoupledEquilibriumEvidence(
        evidence_id="pr07-fully-coupled-numerical-gate-v1",
        cases=tuple(cases),
        multistart_cases=tuple(multistart_cases),
    )
    return {
        **dict(evidence.as_mapping()),
        "case_count": len(cases),
        "throttles": list(THROTTLES),
        "maximum_absolute_torque_residual_nm": max(
            abs(case.torque_residual_nm) for case in cases
        ),
        "maximum_absolute_voltage_residual_v": max(
            abs(case.voltage_residual_v) for case in cases
        ),
        "maximum_absolute_energy_residual_w": max(
            abs(case.energy_residual_w) for case in cases
        ),
        "decision": "pr07_numerical_gate_passed_physical_correlation_pending",
        "scope": (
            "The analytic load qualifies software equilibrium, uniqueness and "
            "residual handling only. A measured motor-propeller correlation data "
            "set is required before physical qualification."
        ),
    }


def _markdown(report: Mapping[str, Any]) -> str:
    rows = [
        "# PR-07 fully coupled motor-propeller evidence",
        "",
        f"- Numerical gate: **{report['numerical_gate']}**",
        f"- Physical gate: **{report['physical_gate']}**",
        f"- Cases: {report['case_count']}",
        f"- Maximum multistart spread: {report['maximum_multistart_spread_rpm']:.3e} rpm",
        f"- Maximum torque residual: {report['maximum_absolute_torque_residual_nm']:.3e} N m",
        f"- Maximum voltage residual: {report['maximum_absolute_voltage_residual_v']:.3e} V",
        f"- Maximum energy residual: {report['maximum_absolute_energy_residual_w']:.3e} W",
        "",
        "| Throttle | RPM | Current (A) | Motor torque (N m) | Aero torque (N m) |",
        "| ---: | ---: | ---: | ---: | ---: |",
    ]
    for case in report["cases"]:
        rows.append(
            f"| {case['throttle']:.2f} | {case['rpm']:.2f} | "
            f"{case['motor_state']['current_a']:.3f} | "
            f"{case['motor_state']['torque_nm']:.6f} | "
            f"{case['aero']['torque_nm']:.6f} |"
        )
    rows.extend(("", str(report["scope"]), ""))
    return "\n".join(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()
    report = build_report()
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.markdown.write_text(_markdown(report), encoding="utf-8")


if __name__ == "__main__":
    main()
