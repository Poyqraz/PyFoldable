# CMM-2 PR-A — isolated paired-load screening dynamics

This document is the software contract for the isolated CMM-2 dynamics path.
It is under independent review. It is not an accepted physical model, not
physical qualification, and not the production aerodynamic source binding.

`model_class` is `coupled_aero_hinge_screening_only`.
`implementation_id` is `cmm2_planar_projected_rate_independent_coupling_v1`.
`load_mapping_model` remains `planar_projected_material_load_v1`.
`qualification` is `screening_only_projected_rate_independent`.
`hinge_rate_aerodynamic_model` is `ignored_rate_independent_quasi_steady`.
`projection_model` is `radial_cosine_v1`.
`physical_qualification` is false.
`full_propeller_clearance`, `surface_path_clearance`, and
`interblade_clearance` stay null.

PR-A does not implement a FoldableBEM evaluator, a sealed design-draft
request, a production report hash, a dashboard, or a Phase-style numerical
verification. Those are later slices. CMM-1 Phase-4 evidence does not transfer
to this solver.

## Isolation from CMM-1

CMM-1 stays in `pyfoldable/dynamics/coupled_transient.py`. Its model class,
omitted-hinge status, `AeroEvaluation` positive-resisting shaft torque, sample
schema, and `solve_coupled_transient` behavior are unchanged.

CMM-2 reuses, without modifying, the CMM-1 mass matrix, mechanical energy,
represented-pivot and backward-residual checks, solver ceilings, knot
segmentation, RK45 step, first-contact reconstruction, and continuous
dense-domain audit. CMM-1 exceptions raised by those unchanged helpers are
re-voiced as CMM-2 failures. CMM-1 is not refactored into a shared
abstraction.

`Cmm2AeroEvaluation` is a distinct type. It does not reuse CMM-1
`AeroEvaluation`, because that shaft field is positive resisting torque.

## States and signs

The dynamic state is exactly `(theta, theta_dot, omega)`. There is no current,
aerodynamic, wake, or hinge-rate aerodynamic state.

- `omega = phi_dot > 0` is positive shaft rotation about `+z`.
- `Qm > 0` drives that rotation.
- `theta = 0` is deployed. `theta < 0` is folded.
- `theta_dot > 0` opens the tip.
- `Q_phi_aero < 0` resists positive shaft rotation.
- `q_theta_aero > 0` is an opening hinge load. `q_theta_aero < 0` folds.

CMM-1 compatibility at zero hinge load is `Q_phi_aero = -Qa`, where `Qa` is
CMM-1's positive-resisting `aero_shaft_torque_nm`.

The fold domain remains `abs(theta) < pi/2`. The shaft floor remains 100 rpm.
`theta_dot` must be finite. No physical hinge-rate validity range is declared.
The aerodynamic load law is rate-independent: the same paired loads may be
reused at two hinge rates, while aerodynamic power still changes through
`N q_theta_aero theta_dot`.

## Mass matrix and equations

`C = m R c`, `A = J + m R^2 + 2 C cos(theta)`, and `B = J + C cos(theta)`.
For `N` identical synchronous tips and sourced base inertia `I0`:

```text
M(theta) = [[I0 + N A,  N B],
            [N B,       N J]]
```

No aerodynamic term and no added mass enter `M`. The matrix is the existing
`coupled_mass_matrix` result, including its represented-pivot and
backward-residual gates.

Signed loads:

```text
(I0 + N A) omega_dot + N B theta_ddot
  = Qm + Q_phi_aero + N C sin(theta) (2 omega theta_dot + theta_dot^2)

N B omega_dot + N J theta_ddot
  = N [Qh + q_theta_aero - k (theta - theta_rest) - b theta_dot
       - tau_c tanh(theta_dot / v) - C omega^2 sin(theta)]
```

`Q_phi_aero` is the whole-rotor shaft generalized load. It is never multiplied
by `N`. `q_theta_aero` is the one-tip hinge generalized load. The outer hinge
factor `N` multiplies it once. The already-collective quantity
`synchronous_n_times_one_tip_hinge_generalized_torque_nm` is not an input.

At `theta = 0` a nonzero `q_theta_aero` remains in the hinge row. It is not
forced to zero. With `q_theta_aero = 0` and `Q_phi_aero = -Qa`, the right-hand
side matches CMM-1. With both aerodynamic loads zero, the motor and mechanism
terms remain and `omega` is still dynamic; that is not a PY-05 prescribed-drive
identity.

## State-bound loads

Before a paired evaluation is used, its `blade_count`, `hinge_radius_m`,
`theta_rad`, and `hinge_rate_rad_s` must equal the current system and state.
The comparison is exact. There is no engineering tolerance. A mismatched,
nonfinite, or wrong-type evaluation fails closed. Invalid hinge load is not
replaced by zero, and a paired-load failure does not fall back to shaft-only
aerodynamics.

Analytic tests may construct `Cmm2AeroEvaluation` without a BEM solve. The
trust-bearing numbers must still be finite, and the screening identifiers
above must match.

## Energy and aerodynamic power

Mechanical energy keeps the existing definition:

```text
E = T + 0.5 N k (theta - theta_rest)^2
```

The instantaneous power identity is:

```text
E_dot = Qm omega + Q_phi_aero omega + N q_theta_aero theta_dot
        + N Qh theta_dot - N b theta_dot^2
        - N tau_c theta_dot tanh(theta_dot / v)
```

Spring power is absent because spring energy is stored in `E`. Net
gyroscopic and centrifugal power is absent when the generalized equations are
combined. Aerodynamic power is the separate diagnostic

```text
Q_phi_aero omega + N q_theta_aero theta_dot
```

and is counted once inside `E_dot`.

## Termination

Accepted endings are `completed` and `first_contact_terminal`. Domain exit,
unresolved dense audit, unresolved mass, residual failure, nonfinite power,
and budget exhaustion fail closed and do not return a shortened success.
No result assigns clearance, calibration, PR-06C, or design readiness.

## Later slices

- PR-A, this contract: isolated dynamics and analytic evaluators.
- PR-B: one production FoldableBEM solve and one planar-load map per accepted
  right-hand side, plus PR-07 motor binding.
- PR-C: sealed request, report hash, and any dashboard surface.

Code: `pyfoldable/dynamics/cmm2_coupled_transient.py`.
Tests: `tests/dynamics/test_cmm2_coupled_transient.py`.
Prerequisite load map, already accepted and unchanged here:
[planar aero-load prerequisite](cmm2_planar_aero_load_prerequisite.md).
CMM-1 boundary: [CMM-1](cmm1_partial_coupled_transient.md) and ADR-005.
Decision record for this slice: ADR-007, proposed and not accepted.
