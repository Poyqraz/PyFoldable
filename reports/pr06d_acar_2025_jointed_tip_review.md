# PR-06D Acar 2025 jointed-tip methodology review

- Evidence class: `methodology_only_tip_jointed_system`
- Physical qualification: **false**
- Audited table points: 31
- Speed range: 0-30 m/s
- Maximum thrust closure error: 0.000800 N
- Maximum power closure error: 0.007000 W
- Reported efficiencies rejected by sign-safe rules: 83

## Transferable implementation

- `sign_safe_propulsor_mode_classification`
- `fail_closed_propulsive_efficiency`
- `typed_tip_mounted_effective_inflow_screening_relation`
- `machine_readable_table_closure_and_consistency_audit`

## Reproduction blockers

- `main_rotor_speed_not_reported`
- `tip_rotor_speed_or_torque_equilibrium_not_reported`
- `main_chord_distribution_not_tabulated`
- `main_twist_distribution_not_tabulated`
- `tip_chord_and_twist_distributions_not_tabulated`
- `hub_radii_not_reported`
- `air_density_not_reported`
- `element_count_not_reported`
- `iteration_tolerance_and_max_iterations_not_reported`
- `stall_and_reynolds_dependence_not_modeled`

## Gate decision

The paper is computational methodology evidence only. It does not change PR-06C or PR-06D physical qualification.
