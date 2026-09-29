# CMM-2 PR-C numerical verification contract

Status: PROPOSED / CONTRACT UNDER INDEPENDENT REVIEW.

Exact design base: `f739ded3d712e42b61a47bf5ef4170c7dfdb7ea8`.

PR-C implementation: NOT STARTED.

`physical_qualification`: false.

This document freezes the verification claims for the declared CMM-2 screening
model. It does not record evidence. No case below has a measured PASS. A
future ADR-009 may accept independent numerical verification of that screening
software model after implementation, exact-head CI, independent review, and
evidence closure. ADR-009 is not created and is not accepted here.

## 1. Scope

PR-C verifies the numerical implementation of the already accepted CMM-2
screening model: the paired-load mass matrix and right-hand side, the
integrator trajectory, first-contact termination, fail-closed domain behavior,
and one real source-bound join of PR-07, FoldableBEM, and the accepted planar
map.

The model under verification is `coupled_aero_hinge_screening_only`,
implementation id `cmm2_planar_projected_rate_independent_coupling_v1`.
Dynamics contract: [CMM-2 PR-A](cmm2_coupled_transient_contract.md).
Source binding: [CMM-2 PR-B](cmm2_source_bound_production_binding.md).

## 2. Mathematical model under verification

State order is `(theta, theta_dot, omega)`. Acceleration order is
`(omega_dot, theta_ddot)`.

```text
C = m R c
A = J + m R^2 + 2 C cos(theta)
B = J + C cos(theta)

M(theta) = [[I0 + N A, N B],
            [N B,      N J]]
```

Shaft row:

```text
Qm + Q_phi + N C sin(theta) (2 omega theta_dot + theta_dot^2)
```

Hinge row:

```text
N [
    Qh
    + q_theta
    - k (theta - theta_rest)
    - b theta_dot
    - tau_c tanh(theta_dot / v)
    - C omega^2 sin(theta)
]
```

`Q_phi` is the signed whole-rotor aerodynamic shaft generalized load. It is
not multiplied by `N` again. `q_theta` is the signed one-tip aerodynamic hinge
generalized load. The collective hinge row multiplies it by `N` exactly once.
Raw positive BEM resisting torque is not `Q_phi`.

Mechanical energy keeps the inherited definition. Kinetic energy uses the
represented mass matrix:

```text
T = 0.5 M00 omega^2 + M01 omega theta_dot + 0.5 M11 theta_dot^2
E = T + 0.5 N k (theta - theta_rest)^2
```

Instantaneous generalized-work identity:

```text
E_dot = Qm omega + Q_phi omega + N q_theta theta_dot
        + N Qh theta_dot - N b theta_dot^2
        - N tau_c theta_dot tanh(theta_dot / v)
```

Spring storage is inside `E`. Net gyroscopic and centrifugal power cancels
when the generalized equations are combined. Aerodynamic power
`Q_phi omega + N q_theta theta_dot` is counted once inside `E_dot`. There is
no battery-energy conservation claim.

## 3. Explicit non-goals

PR-C does not establish physical qualification, dynamic-stall or finite-rate
aerodynamic validity, PR-06C closure, GEOM qualification, calibration,
experimental correlation, design readiness, or dashboard completion.
`physical_qualification` stays false. The three clearance fields stay null.

It does not verify impact, bounce, or latch continuation. It does not
transfer CMM-1 Phase-4 status into CMM-2. It does not reopen ADR-006, ADR-007,
or ADR-008. It does not change equations or production behavior in order to
obtain a pass.

## 4. Accepted dependency boundary

PR-C may rely on these accepted layers without re-proving each of them:

- ADR-006 / PR #74 planar load map
- ADR-007 / PR-A dynamics contract
- ADR-008 / PR-B source-bound binding
- PR-07 motor algebra where the production path reuses it
- FoldableBEM under its accepted repository contracts
- CMM-1 numerical helpers that CMM-2 explicitly inherits, including the
  represented mass matrix, mechanical energy, dense-quartic audit, and
  first-contact reconstruction

An accepted dependency is not an independent PR-C oracle. Calling the same
production helper twice does not create independence.

## 5. Oracle-independence rules

An independent oracle assembles the quantities it claims to check with
test-owned arithmetic.

Forbidden as an independent equation oracle:

- `cmm2_coupled_accelerations`
- the production CMM-2 Schur solve
- the PR-B private request builder

A second integrator that still calls `cmm2_coupled_accelerations` is only a
secondary integration-only characterization. It is not the equation oracle.

Production `cumulative_work_j` is diagnostic. It is not the independent
integration oracle for energy.

## 6. Verification evidence classes

Primary classes, with no aggregate score:

- `MATHEMATICAL`
- `INDEPENDENT_NUMERICAL`
- `CROSS_MODEL`
- `PRODUCTION_PATH`
- `REGRESSION_CONTRACT`
- `EMPIRICAL_CHARACTERIZATION`

A failure in a merge-critical mathematical or numerical layer is not
compensated by another layer passing.

## 7. Reference levels and state-scale policy

Q1 is CLOSED by this contract.

Component order is `theta`, `theta_dot`, `omega`.

```text
S_j(t) = atol_j + rtol * abs(y_ref_j(t))
e_j(t) = abs(y_prod_j(t) - y_ref_j(t)) / S_j(t)
```

`atol_j` and `rtol` are the frozen production controls of the case:
`angle_atol_rad`, `hinge_velocity_atol_rad_s`, `shaft_speed_atol_rad_s`, and
`rtol`. For every merge-critical trajectory, the maximum of `e_j` over all
production sample times is at most 1 for every state component.

The primary critical independent integrator is DOP853. Another integrator is
future secondary characterization only, and only if this contract is
independently reopened.

Two reference levels are frozen against the production controls. They are not
retuned after a result is seen.

```text
Reference A:
  rtol_ref_A = rtol_prod / 100
  atol_ref_A,j = atol_prod,j / 100
  max_step_ref_A = max_step_prod / 4

Reference B:
  rtol_ref_B = rtol_prod / 10000
  atol_ref_B,j = atol_prod,j / 10000
  max_step_ref_B = max_step_prod / 8
```

Both dense references are evaluated at the actual production sample times.
`S_j` uses Reference B and the production controls. Reference B is usable only
when, at every production sample time and every component,

```text
abs(y_ref_B,j - y_ref_A,j) <= 0.1 S_j
```

Otherwise the reference is `REFERENCE NOT STABILIZED` and the critical case
does not pass. A third integrator is not chosen. The tightening factors and
`0.1 S_j` are not relaxed. The fixture is not retuned. If a tighter control
falls below a supported numerical range, the reference is contract-blocked and
inconclusive. It is not silently clamped.

These gates apply to the recorded evidence domain. They are not an RK45
global-error theorem, not a physical error bar, and not a transfer of CMM-1
evidence.

Policy id: `prc_state_scale_v1`. Reference policy id: `prc_dop853_ab_v1`.

## 8. Normative critical matrix

These identities are merge-critical. None has been executed under this
contract. Literal inputs are in the frozen critical-fixture manifest.

### C2V-01 — matrix and paired-load algebra

Purpose: show that the represented `M` and both right-hand sides use `Q_phi`
and `q_theta` with the declared `N` accounting.

Features: the fixture set uses `N` in `{1, 2, 4}`, nonzero off-diagonal
coupling, both load signs, and a state at which `q_theta` is not structurally
zero. Not every `N`-multiplication mutant is distinguishable at `N = 1`.
Those mutants must be discriminated by at least one case with `N > 1`.

Oracle class: `MATHEMATICAL`.

Independence: `M` and `b` are assembled outside the production acceleration
function. Every binary64 entry is converted with `Fraction.from_float`. The
2×2 system is solved by exact rational determinant algebra. That solution is
the exact solution of the independently assembled represented system. Decimal
arithmetic may be a secondary diagnostic. It is not the primary reference.

Required metrics: `x_ref`, `x_prod`, absolute forward error, row backward
errors, and `kappa_inf`.

Acceptance basis: the represented backward-error rule and the
conditioning-aware forward bound in section 10. A small residual is not proof
of a small forward error.

Local mutants, and only these:

- A. `Q_phi` multiplied by `N`
- B. `q_theta` missing the collective `N`
- C. `N q_theta` supplied as the one-tip `q_theta`
- D. `q_theta` sign reversed

Raw positive resisting torque is not a C2V-01 mutant. It belongs to C2V-09.

For each mutant, the infinity-norm difference between the exact represented
accelerations of the correct system and of the mutant must exceed the C2V-01
forward-uncertainty envelope of the correct system. With an exact `Fraction`
reference, that residual against `x_ref` is zero, so the envelope is zero and
any nonzero exact acceleration difference discriminates. A zero difference
does not. A mutant that is not discriminated is not evidence for that mutant.

Limitations: this case does not integrate a trajectory and does not qualify
FoldableBEM.

### C2V-02 — nonzero-load exact equilibrium

Purpose: a manufactured constant state with both accelerations equal to zero.

A constant state has `theta_dot = 0`. Therefore `-b theta_dot = 0` and
`-tau_c tanh(theta_dot / v) = 0`. This case does not exercise nonzero damping
or friction. Nonzero dissipation is C2V-03 and C2V-04.

It does exercise `C != 0`, `theta != 0`, `N > 1`, nonzero `Qm`, nonzero
`Q_phi`, nonzero `q_theta`, the spring term, and centrifugal balance. `Q_phi`
and `q_theta` are the unique values that make both right-hand sides zero for
the frozen primitives. They are not taken from a production residual.

Oracle class: `INDEPENDENT_NUMERICAL`.

Acceptance basis, in acceleration units `rad/s^2`: the independently predicted
`omega_dot = 0` and `theta_ddot = 0` must lie inside the applicable C2V-01
absolute represented-error envelope. The short returned trajectory is a
different metric. It is compared with the exact constant state under section 7,
`max e_j <= 1`. Section 7 state scales are not applied to the accelerations.

Limitations: one equilibrium does not verify transient coupling.

### C2V-03 — genuinely coupled manufactured trajectory

Purpose: prescribed `theta*(t)` and `omega*(t)` with resolvable coupling.

The manifest freezes every primitive and the production controls. `Qm(t)` and
`Qh(t)` are frozen. `Q_phi*(t)` and `q_theta*(t)` are then the unique solution
of the target equations at the target state and target accelerations, using
test-owned arithmetic. They are functions of target time and target state.
They are not recomputed from the production trajectory.
`Cmm2AeroEvaluation` metadata may name the queried production state so the
state-bound contract can be checked. The force values stay on the target.

The manufactured trajectory contains nonzero `C`, `theta_dot`, `omega_dot`,
`theta_ddot`, `Q_phi`, `q_theta`, spring, and damping. This is synthetic
equation evidence, not planar-aero physical evidence.

Oracle class: `INDEPENDENT_NUMERICAL`.

Acceptance basis: section 7 after Reference A/B stabilization.

Limitations: the manufactured force is not the planar map. That map is C2V-09.

### C2V-04 — independent work and energy balance

Purpose: separate instantaneous work and integrated energy. Nonzero
dissipation is in this case. Section 7 state scales do not apply to watts or
joules.

Oracle class: `INDEPENDENT_NUMERICAL`.

Instantaneous residual, from the independent target:

```text
P = Qm omega + Q_phi omega + N q_theta theta_dot
    + N Qh theta_dot - N b theta_dot^2
    - N tau_c theta_dot tanh(theta_dot / v)
R_P = (dE/dt)_independent - P
```

```text
P_scale = abs((dE/dt)_independent)
        + abs(Qm omega) + abs(Q_phi omega)
        + abs(N q_theta theta_dot) + abs(N Qh theta_dot)
        + abs(N b theta_dot^2)
        + abs(N tau_c theta_dot tanh(theta_dot / v))
```

If `P_scale == 0`, then `R_P` must be exactly zero. Otherwise

```text
abs(R_P) / P_scale <= max(1.0e-8, 64 * ulp(P_scale) / P_scale)
```

This reuses the accepted represented-arithmetic residual policy.

Integrated energy uses the manufactured target, not production
`cumulative_work_j`. The primary quadrature is `scipy.integrate.quad` at two
predetermined levels. Tolerances are not changed after the result:

```text
quad A: epsabs = 0, epsrel = 1.0e-10
quad B: epsabs = 0, epsrel = 1.0e-12
U_quad = max(reported_error_B, abs(I_B - I_A))
R_E = E_target(t1) - E_target(t0) - I_B
E_scale = abs(E_target(t1)) + abs(E_target(t0)) + abs(I_B)
```

If `E_scale == 0`, the non-quadrature residual is exactly zero subject to
`U_quad`. Otherwise

```text
U_round_E = max(1.0e-8 * E_scale, 64 * ulp(E_scale))
abs(R_E) <= U_quad + U_round_E
```

`U_quad` and `U_round_E` are recorded separately. Production
`cumulative_work_j` is diagnostic only. There is no battery-energy claim.

### C2V-05 — DOP853 comparison

Purpose: compare the production RK45 trajectory with the frozen DOP853
Reference A and Reference B on the C2V-03 right-hand side.

Oracle class: `INDEPENDENT_NUMERICAL`.

The merge-critical oracle is only that DOP853 pair. There is no later
substitution of another integrator. Another integrator is characterization
only after this contract is reopened.

Stabilization is dense Reference A against dense Reference B at every actual
production RK45 sample time. Failure of `abs(A - B) <= 0.1 S_j` is
`REFERENCE NOT STABILIZED`. It is not permission to try another oracle.

The reference right-hand side is assembled independently. It does not call
`cmm2_coupled_accelerations`.

### C2V-06 — zero-hinge CMM-1 cross-model limit

Purpose: at `q_theta = 0` and `Q_phi = -Qa`, the represented CMM-1 and CMM-2
mass matrix and right-hand side coincide. `Qa` is CMM-1's positive resisting
shaft aerodynamic torque. The state, system, motor, and actuation are the same.

Oracle class: `CROSS_MODEL`.

For each corresponding represented matrix, right-hand side, and acceleration
scalar at the one frozen finite fixture, the ULP distance is at most 1. Exact
zeros match exact zeros. The 1 ULP rule is repository numerical policy for
this represented limit. It is not a universal floating-point theorem. The
historical 21,062-state sweep is not repeated. CMM-1 Phase-4 status does not
transfer.

If the short trajectory is also compared, its states use section 7. The 1 ULP
rule is not applied to that state comparison, and section 7 is not applied to
the matrix or acceleration comparison.

### C2V-07 — analytic first-contact timing

Purpose: one manufactured transverse crossing of a declared stop at analytic
time `t_c`.

Neighborhood, using the frozen production maximum step:

```text
I_c = [max(t0, t_c - max_step_prod), t_c]
v_min = min over I_c of abs(theta_dot*(t))
```

The fixture is valid only when `v_min > 0` is true from the analytic target
before any production result is used.

```text
A_theta = max over I_c of (angle_atol_rad + rtol * abs(theta*(t)))
```

The contact solver inherited by `_first_contact` uses Brent tolerances
`xtol_brent = 1e-14` and `rtol_brent = 1e-14`.

```text
U_root = xtol_brent + rtol_brent * abs(t_c)
T_allow = A_theta / v_min + U_root
```

The production contact must satisfy `abs(t_contact - t_c) <= T_allow`, the
correct stop, the correct pre-impact sign and state, and no later sample.
From the analytic target and the state-error envelope, the fixture must remain
inside the fold and speed domains on `[t0, t_c]`. If a right-hand side stage
leaves the declared model domain before contact can be reconstructed, the case
does not demand a success artifact. It is invalid or inconclusive for C2V-07
and does not continue. The frozen fixture is not replaced.

Time is compared with `T_allow` in seconds. State samples that are part of the
terminal check use section 7. Those scales are not used as the time tolerance.

### C2V-08 — representative fail-closed boundary

Purpose: CMM-2 fails closed on representative exits and returns no shortened
success.

Exits, using production control names:

- fold-domain exit
- shaft speed below `OMEGA_MIN` (100 rpm)
- `max_rhs_evaluations` exhaustion
- one hard failure raised by the synthetic aerodynamic callback

`max_samples` may be recorded as a separate regression. There is no separate
configurable work budget. The production message may still say that the work
budget was exhausted when `max_rhs_evaluations` is hit.

Oracle class: `REGRESSION_CONTRACT`.

Shared dense-quartic isolation remains a CMM-1 dependency. This case shows that
CMM-2 invokes fail-closed behavior. It does not reimplement that proof and
does not repeat every lower-layer exception test.

### C2V-09 — real source-bound trajectory

Purpose: one sealed PR-B trajectory using `Pr07MotorEvaluator`, FoldableBEM,
and the accepted PR #74 planar map.

Oracle class: `PRODUCTION_PATH` for the join, and `INDEPENDENT_NUMERICAL` for
the trajectory.

The DOP853 reference evaluates fresh PR-07, FoldableBEM, and planar-map calls
at the reference's own states. It does not use production sample `Q_phi`,
production sample `q_theta`, or production ledger loads as its force oracle.
At selected common production states, a fresh lower-layer evaluation is
compared for thrust, mapped `Q_phi`, mapped one-tip `q_theta`, and generalized
aerodynamic power. The mapper remains an accepted dependency. This does not
re-prove PR #74.

DOP853 and RK45 have different evaluation counts and sequences. Evaluation
index, `source_id` sequence, ledger length, and report hash are not compared
across integrators. Numerical comparison is same state to lower-layer loads,
and same time to trajectory state.

The reference may consume the same sealed mechanical parameters. It assembles
`M` and the right-hand side itself. It does not call
`cmm2_coupled_accelerations`, the production Schur solve, or the PR-B private
request builder as the equation oracle.

Raw-torque mutant, on the same real BEM evaluation that produced the mapped
load: substituting the raw positive resisting rotor torque for mapped signed
`Q_phi` must change the exact represented acceleration by more than the C2V-01
forward-uncertainty envelope. Otherwise this fixture is not valid evidence.

Selection, detectability, and the pre-result record are section 11. Trajectory
acceptance, after those gates, is section 7.

Limitations: one fixture does not qualify the rotor, the map, or the motor.

### C2V-10 — continuous piecewise-linear actuation

The repository hinge history is continuous piecewise-linear torque. An
interior knot changes slope. The torque value at the knot is the shared
endpoint of the two neighboring segments.

This case verifies segment selection, the interior slope change, segment
restart, state continuity at the knot, nonzero paired aerodynamic loads, and
unchanged `N` accounting across the restart.

For interior knot `t_k`,

```text
delta = 0.25 * min(t_k - t_(k-1), t_(k+1) - t_k)
```

Probes are `t_k - delta`, `t_k`, and `t_k + delta`. Expected `Qh` is the
declared piecewise-linear formula, in newton-metres. At `t_k` the left and
right values are identical. At the finite probes the neighboring slopes are
distinguishable. Section 7 applies only to the state trajectory.

## 9. Characterization-only matrix

### C2V-11 — solver-setting sensitivity

Classification: `CHARACTERIZATION ONLY`.

Records trajectory movement when tolerance or maximum step changes. It does
not certify global RK order or monotonic convergence. No decreasing-difference
gate is added.

### C2V-12 — BEM annulus and spatial sensitivity

Classification: `CHARACTERIZATION ONLY`.

Records source-bound load movement under a modest annulus or spatial sweep.
It does not certify rotor accuracy or physical validity. No
decreasing-difference gate is added.

If either characterization shows that a merge-critical assumption is false,
for example a source discontinuity inside the smooth domain claimed for
C2V-09, that critical case is blocked. Characterization-only is not permission
to ignore that contradiction.

## 10. C2V-01 represented forward-error policy

Q2 is CLOSED by this contract. Policy id: `prc_represented_forward_v1`.

No forward tolerance is chosen from observed production acceleration error.

Assemble binary64 `M` and `b` independently. For production acceleration
`x_prod`, each row uses the existing residual scale

```text
row_scale_i = abs(b_i) + sum_j abs(M_ij * x_prod_j)
eta_i = abs(r_i) / row_scale_i
```

If `row_scale_i == 0`, then `eta_i = 0` when `r_i == 0`, and the row fails
when `r_i != 0`. Otherwise each represented row must satisfy the existing
repository constants `_RESIDUAL_REL = 1.0e-8` and
`_RESIDUAL_ROUND_ULPS = 64`:

```text
eta_i <= max(1.0e-8, 64 * ulp(row_scale_i) / row_scale_i)
```

No other residual threshold is introduced.

`x_ref` is the exact rational solution of the `Fraction.from_float`
represented system. Report `x_ref`, `x_prod`, the absolute forward error, the
row backward errors, and `kappa_inf`.

Infinity norm:

```text
||M||_inf = max row sum of abs(M_ij)
||M^-1||_inf = infinity norm of the inverse of that represented M
kappa_inf = ||M||_inf * ||M^-1||_inf
```

The inverse and the norms are those of the exact rational matrix obtained from
`Fraction.from_float` on the represented entries. The residual is the same
exact arithmetic:

```text
r = b - M x_prod
rho_inf = ||r||_inf / (||M||_inf * ||x_prod||_inf + ||b||_inf)
```

If the denominator is zero, `rho_inf = 0` when `r` is zero and the state is
numerically inconclusive when `r` is not zero.

When `kappa_inf * rho_inf < 1`,

```text
B_rel = (kappa_inf * rho_inf) / (1 - kappa_inf * rho_inf)
```

The measured relative forward error against `x_ref` must not exceed `B_rel`.
The `Fraction` reference adds no further uncertainty. Where a relative metric
is undefined because the exact reference component or norm is zero, use

```text
B_abs = ||M^-1||_inf * ||r||_inf
```

and compare in absolute acceleration units.

When `kappa_inf * rho_inf >= 1`, the state is `NUMERICALLY INCONCLUSIVE` for
forward-error evidence. It is not accepted as C2V-01 evidence. No other
forward envelope is chosen after seeing `x_prod`.

## 11. C2V-09 selection and detectability

Q3 is CLOSED by this contract. Policy id:
`prc_c2v09_ordered_candidates_v1`.

The ordered list below is complete. It is the committed sealed-binding inputs
in `tests/application/test_cmm2_coupled_transient_service.py`, in source
order. No candidate is added, removed, or reordered after a preflight or a
trajectory result. Trajectory acceptance metrics are not computed before
selection. If none pass, the contract is blocked. A new candidate is not
invented.

Base inputs, candidate `C2V09-00`, are the `_binding()` literals:

- draft built from `configs/designs/TIP_HINGED_250_CANONICAL.toml` with
  diameter `220 mm`, hub radius `16 mm`, hinge radius `85 mm`, blade count 3,
  airfoil `NACA0012`, chord scale 1, twist scale 1, preview fold `-60 deg`,
  angular speed `4000 rpm`, forward speed `4 m/s`, density `1.18 kg/m^3`,
  viscosity `1.79e-5 Pa*s`, temperature `20 degC`, pressure `100 kPa`
- one radial mass sample at `0.01 m`, mass `0.01 kg`, source
  `synthetic tip mass`, distribution id `synthetic-tip`, classification
  `synthetic_test_fixture`
- `I0 = 1.0e-4`, source `fixture inertia`, inventory `motor rotor`, `shaft`,
  `hub`, `fixed blade roots`
- spring `0`, rest angle `-0.2 rad`, damping `0`, friction mode `none`
- initial angle `-0.2 rad`, initial hinge rate `0`, initial shaft speed
  `400 * pi / 30 rad/s`
- actuation knots `(0, 0.004)` s and torques `(0, 0)` N·m, source
  `no actuation`
- motor `(kv, R, I0, Imax) = (1000, 0.05, 1, 80)`, battery `(12 V, 0.98)`,
  system resistance `0.01 ohm`, throttle `0.1`
- environment id `screen`, forward speed `4 m/s`, density `1.18`, viscosity
  `1.79e-5`, temperature `293.15 K`, pressure `100000 Pa`
- polar schedule `cmm2-span`, anchors `0.2` and `1.0`, one table `NACA0012` /
  `cmm2` / Reynolds `1e5` / Mach `0` / alpha `(-0.5, 0.5)` / `cl = (0.6, 0.6)`
  / `cd = (0.02, 0.02)` / `cm = (0, 0)` / source `cmm2-fixture` / empty metadata
- BEM annulus count `4`, `bracket_samples = 16`, `loading_branch = positive_only`,
  bounds `error`
- mechanical source `explicit fixture`
- production controls are the repository `CoupledSolverControls` defaults:
  `rtol = 1e-6`, `angle_atol_rad = 1e-8`,
  `hinge_velocity_atol_rad_s = 1e-8`, `shaft_speed_atol_rad_s = 1e-6`,
  `max_step_s = 0.002`, `max_duration_s = 2`, `max_samples = 5000`,
  `max_rhs_evaluations = 12000`, `max_input_knots = 256`

Later candidates change exactly one of those fields, in this order:

1. `I0 = 2.0e-4`, same source and inventory
2. inertia source `other inertia`
3. inventory without `fixed blade roots`
4. motor `kv = 1100`
5. battery voltage `14.8 V`
6. battery efficiency `0.97`
7. system resistance `0.02 ohm`
8. throttle `0.2`
9. environment forward speed `5 m/s`
10. polar `cl = (0.7, 0.7)`
11. polar source `other-fixture`
12. polar metadata `{"tag": "b"}`
13. annulus count `6`
14. `loading_branch = signed_nonreversed`
15. tip mass `0.02 kg`
16. spring `0.001 N·m/rad`
17. rest angle `-0.1 rad`
18. damping `0.0001 N·m·s/rad`
19. `DryFriction("regularized_coulomb", 0.001, 0.04, source="fixture friction")`
20. mechanical source `other fixture`
21. actuation torques `(0, 0.001)` N·m
22. initial angle `-0.15 rad`
23. initial hinge rate `0.01 rad/s`
24. initial shaft speed `500 * pi / 30 rad/s`
25. `rtol = 1.0e-7`
26. initial shaft speed `13000 * pi / 30 rad/s`
27. motor `current_max_a = 5`, throttle `1`, initial shaft speed
    `1000 * pi / 30 rad/s`

Selection evaluates that order. For each candidate it performs only the
initial-state preflight. The first candidate that satisfies every rule is
selected. No trajectory metric is computed before that selection.

Detectability, fixed before any trajectory error is known:

- `q_theta` is resolvable when the exact represented acceleration difference
  between the mapped `q_theta` and `q_theta = 0` exceeds the C2V-01
  forward-uncertainty envelope
- the raw-torque mutant is resolvable when the exact represented acceleration
  difference between mapped signed `Q_phi` and the raw positive resisting
  torque from that same BEM evaluation exceeds the same envelope
- aerodynamic hinge work is resolvable when `abs(N q_theta theta_dot)` exceeds
  the C2V-04 instantaneous power allowance at that state

Domain margins use the frozen production scales at the initial state.
Fold-domain distance must exceed `S_theta(0)`. Distance of shaft speed above
`OMEGA_MIN` must exceed `S_omega(0)`.

Partition margin: from the initial mapped field, measure the distance from the
projected hinge radius and from each mapped interval edge to the nearest
hinge-cell boundary and radial midpoint boundary. Radius uncertainty is
`abs(s_tip sin(theta0)) S_theta(0)` plus `64` ULPs of the larger of the
projected radius and the hinge radius. `s_tip` is the mapped material distance
from the hinge to the projected tip. The boundary distance must exceed that
uncertainty. Both numbers are recorded.

If the selected fixture later enters an unresolved partition neighborhood, it
is blocked or inconclusive and returns to contract review. It is not replaced.

Before the production trajectory, write a canonical selection record:

- contract head SHA
- ordered-list identity `prc_c2v09_ordered_candidates_v1`
- candidate input digests
- frozen controls
- preflight rules
- preflight metrics in list order for every candidate inspected
- selected index
- selected sealed-request digest
- Q2 uncertainty values
- `q_theta`, hinge-work, and raw-versus-mapped detectability
- domain margins and partition margin

`selection_record_sha256` is the SHA-256 of that canonical JSON, computed
before trajectory acceptance. The evidence JSON includes that digest. A file
that contains only the selected request digest is not enough.

Q4 remains open as an implementation preflight, not as an open acceptance
policy. Identical physical and numerical BEM inputs with a changed evaluation
index must keep thrust, `Q_phi`, and `q_theta` numerically identical under
this case's equality rule. Identifiers may differ. A numerical difference is
a production defect or a contract block. C2V-09 does not pass, and no other
candidate is substituted.

## 12. Failure and domain policy

Accepted successful endings remain `completed` and `first_contact_terminal`.
Domain exit, unresolved audit, unresolved mass, residual failure, nonfinite
power, and budget exhaustion do not return a shortened success. C2V-08 is the
representative evidence.

## 13. Evidence artifact contract

A future implementation emits structured finite JSON. It does not write an
external database. Fields:

- repository head
- `contract_head`
- `case_id`
- primary evidence class
- purpose
- fixture identity and digest
- `critical_fixture_manifest_sha256`
- `selection_record_sha256` where a selection exists
- `pre_result_freeze_status`
- `threshold_policy_id`
- `reference_policy_id`
- `conditioning_policy_id`
- `fixture_selection_policy_id`
- model identifiers
- dependency identifiers
- oracle method
- independence limit
- controls
- metrics with units
- component order
- reference stabilization
- acceptance rule
- threshold basis
- classification
- limitations

The policy identifiers name this procedure. They are not new model
identifiers. Classification is `PASS`, `FAIL`, or `CHARACTERIZATION ONLY`.
A critical failure is still recorded. There is no aggregate score. This
contract does not contain those artifacts.

## 14. CI and runtime policy

- C2V-01 through C2V-08 and C2V-10: fast or moderate CI
- C2V-09: the one selected real source-bound fixture in ordinary CI
- C2V-11: bounded characterization
- C2V-12: a modest sweep in ordinary CI only if measured cost is acceptable; a
  broader sweep may be a separate reproducible characterization

Q5 is open runtime characterization. It may place the broader C2V-12 sweep
outside ordinary CI. It must not remove or weaken C2V-09 or any C2V-01
through C2V-10 gate. A cheaper C2V-09 fixture is not acceptable when
`q_theta` or aerodynamic hinge work is numerically invisible.

## 15. Contract questions

Q1. CLOSED. State accuracy and DOP853 Reference A/B stabilization are frozen
in section 7.

Q2. CLOSED. Represented backward error, conditioning, and the forward-error
bound are frozen in section 10.

Q3. CLOSED. The ordered C2V-09 list, detectability definitions, and
pre-result selection record are frozen in section 11.

Q4. OPEN FOR IMPLEMENTATION PREFLIGHT. It is mandatory. Failure blocks C2V-09
and does not permit a substitute fixture.

Q5. OPEN RUNTIME CHARACTERIZATION. It may affect only where C2V-12 runs.

No other merge-critical numerical threshold is left undefined.

## 16. Frozen critical-fixture manifest

Values below are frozen before any production acceptance result. A critical
fixture is either these literals or a formula whose inputs are these literals
or the ordered C2V-09 list. Manifest id: `prc_critical_fixture_manifest_v1`.

Shared synthetic mechanism, unless a case names an override:

```text
m = 0.02 kg
R = 0.08 m
c = 0.03 m
J = 2.0e-5 kg m^2
I0 = 1.0e-4 kg m^2
k = 0.01 N m/rad
theta_rest = -0.2 rad
b = 0.002 N m s/rad
tau_c = 0.001 N m
v = 0.05 rad/s
lower_stop = -1.2 rad
upper_stop = 0.2 rad
```

Shared production controls, unless a case names an override, are the
`CoupledSolverControls` defaults listed for C2V-09.

C2V-01. State `theta = -0.4 rad`, `theta_dot = 0.2 rad/s`, `omega = 40 rad/s`.
`Qm = 0.05 N m`, `Qh = 0.001 N m`. Load pair P: `Q_phi = -0.02`,
`q_theta = 0.004`. Load pair M: `Q_phi = 0.015`, `q_theta = -0.003`.
Each pair is repeated at `N = 1`, `N = 2`, and `N = 4`. Mutants A through D
are applied to each of those six rows. No duration. No raw BEM torque.

C2V-02. `N = 2`, `theta = -0.4 rad`, `theta_dot = 0`, `omega = 40 rad/s`,
`Qm = 0.05 N m`, `Qh = 0.001 N m`. `Q_phi = -Qm`. `q_theta` is the unique
value that zeros the hinge bracket after spring and centrifugal terms. Short
trajectory duration `0.02 s` with those loads held constant. Damping and
friction torques are identically zero because `theta_dot = 0`.

C2V-03 and C2V-04 and C2V-05 share one target on `t in [0, 0.2] s`, `N = 2`:

```text
theta*(t) = -0.30 + 0.05 * sin(2 * pi * t / 0.2)
omega*(t) = 40 + 2 * t
Qm(t) = 0.04
Qh(t) = 0.001
```

`Q_phi*(t)` and `q_theta*(t)` are solved from the target equations at
`theta*`, its derivatives, `omega*`, and `omega_dot* = 2`. C2V-05 advances
that same independent right-hand side with DOP853 Reference A and Reference B.

C2V-06. One finite state: `N = 2`, `theta = -0.3 rad`, `theta_dot = 0.1 rad/s`,
`omega = 40 rad/s`, `Qa = 0.02 N m`, `q_theta = 0`, `Q_phi = -Qa`,
`Qm = 0.04 N m`, `Qh = 0.001 N m`. Optional trajectory duration `0.05 s` with
those loads held constant. No 21,062-state sweep.

C2V-07. `N = 2`, `lower_stop = -0.50 rad`, `upper_stop = 0.20 rad`,
`theta*(t) = -0.20 - 0.40 * t`, `omega*(t) = 40`, `Qm = 0.04`, `Qh = 0`,
`q_theta = 0`, `Q_phi = -0.01`. Then `t_c = 0.75 s` and `theta_dot* = -0.40`.
Duration `1.0 s`. `max_step_prod = 0.002 s`. The analytic target is the
authority for `v_min` and domain membership on `[0, t_c]`.

C2V-08, four frozen subcases, shared mechanism except as written:

- fold exit: `theta0 = -1.20 rad`, `theta_dot0 = -1.0 rad/s`, `omega0 = 40`,
  stops `(-2.0, 0.5)`, duration `0.5 s`
- speed exit: `omega0 = 10.0 rad/s`, which is below `OMEGA_MIN`,
  `theta0 = -0.3`, `theta_dot0 = 0`
- `max_rhs_evaluations = 1`, interior state `theta0 = -0.3`,
  `theta_dot0 = 0.1`, `omega0 = 40`, duration `0.2 s`
- hard failure: the synthetic aerodynamic callback raises
  `Cmm2TransientFailure` with message `hard failure` on the first call

C2V-09. The ordered candidate list in section 11. No other inputs.

C2V-10. `N = 2`, duration `0.8 s`, knots `(0, 0.4, 0.8)` s, torques
`(0, 0.002, -0.001)` N·m. Initial state `theta = -0.3 rad`,
`theta_dot = 0.1 rad/s`, `omega = 40 rad/s`. Constant manufactured
`Q_phi = -0.02 N m` and `q_theta = 0.004 N m`. `Qm = 0.04 N m`. Probe offset
is the section formula, which is `0.1 s` for these equal segment widths.

## 17. Implementation boundary

Implementation has not started. This pull request adds no test, fixture, or
production change. Expected production-code changes for the later
implementation are none. If rigorous verification needs a production change,
stop and report the missing observability or defect separately. Do not change
equations to obtain a pass.

## 18. Acceptance boundary

Review of this contract is not verification acceptance. Passing tests do not
yet exist. Status remains PROPOSED / CONTRACT UNDER INDEPENDENT REVIEW.
ADR-009 is not created and is not accepted. `physical_qualification` stays
false. PR-06C stays unresolved. No GEOM gate is promoted. There is no
calibration and no experimental validation.

Dynamics contract link:
[CMM-2 PR-A](cmm2_coupled_transient_contract.md).
