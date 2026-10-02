# CMM-2 PR-C numerical verification contract

Status: REVIEWED / FROZEN FOR IMPLEMENTATION WITH C2V-02 ARITHMETIC AMENDMENT.

Prior independently reviewed contract head:
`613072514f793f2a1bc65704f9158f536210707f`.

Review result of that prior head: APPROVE.

Reviewed amended technical head:
`b840ec55b4d1dd57197b97e91e1a48a7fbe7da0d`.

Review result of that amended technical head: APPROVE. The reviewer was a
separate read-only automated reviewer in the coordinating chat. That result
is not a submitted GitHub review. PR #82 has no GitHub review at this status
closure.

Reason for the narrow amendment: C2V-02 analytic-zero versus
represented-system solve-envelope mismatch found during PR #81 forensic
verification.

The C2V-02 amendment changes only initial-acceleration accounting. Ordinary
Q2 remains required. The analytic bridge is an accounting bound. The
trajectory acceptance policy was never reopened.

Exact design base: `f739ded3d712e42b61a47bf5ef4170c7dfdb7ea8`.

Implementation against this amended contract has not started. Draft PR #81
remains a separate blocked evidence attempt. Its C2V-02 and C2V-03 trajectory
results remain FAIL. No accepted PR-C evidence exists. PR #81 is unchanged
here.

`physical_qualification`: false.

The prior freeze still covers C2V-01, C2V-03 through C2V-12, the
merge-critical fixture and control construction, the closed Q1, Q2, and Q3
policies, and Q4's closed acceptance policy. Q4's measurement remains an
implementation preflight. Q5 remains open runtime characterization and cannot
weaken a critical gate.
Implementation must not retune thresholds, fixtures, oracle choices, or
candidate order from observed PR-C results.

The C2V-02 amendment changes only the initial-acceleration comparison, and
only to separate analytic continuous zero from the binary64 represented-system
solution. Q2 itself is not changed. The short-trajectory rule, duration,
tolerances, fixture values, `Q_phi`, and `q_theta` are not changed. This
amendment does not convert an observed C2V-02 trajectory failure into PASS.

This status does not mean that PR-C verification has passed, that accepted
evidence exists, that ADR-009 is accepted, that CMM-2 is physically
validated, or that `physical_qualification` is true.

This document records the verification claims for the declared CMM-2 screening
model. It does not record evidence. No case below has a measured PASS. A
future ADR-009 may accept independent numerical verification of that screening
software model after implementation, evidence closure, exact-head CI, and
independent review. ADR-009 is not created and is not accepted here.

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

The rational reference has no arithmetic uncertainty. That does not make the
production forward-error allowance zero. The allowance is the frozen section
10 policy. For each local mutant define

```text
G_mut = ||x_ref_mutant - x_ref_correct||_inf
B_abs_correct = ||M^-1||_inf * ||b - M x_prod||_inf
```

using the correct production evaluation. Both reference accelerations are
exact represented solutions. The row separates that mutant only when
`G_mut > B_abs_correct`. Otherwise that row is not evidence for that mutant.
The fixture is not retuned after the result. `N`-multiplication mutants need
be separated only on a row with `N > 1`, not at `N = 1`. `B_abs_correct` is
an acceleration magnitude. Dimensionless `B_rel` is not that threshold.

Limitations: this case does not integrate a trajectory and does not qualify
FoldableBEM.

### C2V-02 — nonzero-load exact equilibrium

Purpose: a manufactured constant state whose continuous analytic accelerations
are exactly zero.

A constant state has `theta_dot = 0`. Therefore `-b theta_dot = 0` and
`-tau_c tanh(theta_dot / v) = 0`. This case does not exercise nonzero damping
or friction. Nonzero dissipation is C2V-03 and C2V-04.

It does exercise `C != 0`, `theta != 0`, `N > 1`, nonzero `Qm`, nonzero
`Q_phi`, nonzero `q_theta`, the spring term, and centrifugal balance. `Q_phi`
and `q_theta` are the unique values that make both continuous analytic
right-hand sides zero for the frozen primitives. They are not taken from a
production residual. Binary64 assembly of those same frozen values may leave
a represented right-hand side that is not exactly zero.

Oracle class: `INDEPENDENT_NUMERICAL`.

The continuous C2V-02 target remains an exact equilibrium. Q2 validates the
production solve against the represented system. The C2V-02 bridge separately
accounts for the represented-system displacement from the analytic target.
This amendment does not weaken or alter the trajectory gate.

Initial acceleration requires both of the following. The analytic bridge does
not replace Q2.

A. Ordinary Q2 represented-system solver audit, unchanged. Policy id
`prc_represented_forward_v1` stays. Apply section 10 exactly, with

```text
x_repr = exact Fraction solution of M_repr x = b_repr
r_repr = b_repr - M_repr x_prod
B_solve = ||M_repr^-1||_inf * ||r_repr||_inf
```

`M_repr` and `b_repr` are the independently assembled binary64 system.
`x_analytic` is not substituted for `x_repr` inside Q2. Row backward-error
gates and the factor-of-two relative branch stay as written in section 10.

B. Analytic-equilibrium bridge, for C2V-02 only. In acceleration units
`rad/s^2`:

```text
x_analytic = [0, 0]
x_repr = exact rational solution of the independently assembled binary64 M_repr, b_repr
B_assembly = ||x_repr - x_analytic||_inf
B_solve = ||M_repr^-1||_inf * ||b_repr - M_repr x_prod||_inf
E_analytic = ||x_prod - x_analytic||_inf
```

`B_assembly` is the exact acceleration displacement caused by representation
and assembly of the frozen binary64 system relative to the analytic continuous
equilibrium. It is not a fitted tolerance. `B_solve` is the production-solve
contribution: it bounds production solve error relative to the exact
represented system. It does not by itself bound analytic continuous zero
versus that represented-system solution. Record `B_assembly`, `B_solve`, and
`E_analytic` separately. Do not merge them into an unexplained tolerance.

The C2V-02 initial acceleration gate is

```text
E_analytic <= B_assembly + B_solve
```

This follows from

```text
x_prod - x_analytic = (x_prod - x_repr) + (x_repr - x_analytic)
```

and the triangle inequality. Analytic zero is not required to lie inside
`B_solve` alone.

The short returned trajectory is a different metric and is not reopened. The
reference trajectory remains the exact constant state. Section 7 applies
exactly:

```text
S_j(t) = atol_j + rtol * abs(y_ref_j(t))
e_j(t) = abs(y_prod_j(t) - y_ref_j(t)) / S_j(t)
```

and `max e_j <= 1` for every state component. Duration `0.02 s`, the section
11 default controls (`rtol = 1e-6`, hinge-rate atol `1e-8`, angle atol
`1e-8`, shaft-speed atol `1e-6`, `max_step = 0.002`), the section 16 fixture
values, `Q_phi`, and `q_theta` stay unchanged. An observed trajectory failure
remains a legitimate PR-C failure. This amendment does not convert that
failure into PASS. Section 7 state scales are not applied to the accelerations.

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

The watt allowance is

```text
U_P = 0
      if P_scale == 0
      otherwise max(1.0e-8 * P_scale, 64 * ulp(P_scale))
```

and the identity requires `abs(R_P) <= U_P`. `U_P` is in watts. This is the
same represented-arithmetic residual policy, named so later cases can reuse it.

Integrated energy uses the manufactured target, not production
`cumulative_work_j`. The primary quadrature is `scipy.integrate.quad` at two
predetermined levels. Tolerances are not changed after the result:

```text
quad A: epsabs = 0, epsrel = 1.0e-10
quad B: epsabs = 0, epsrel = 1.0e-12
U_quad = max(reported_error_B, abs(I_B - I_A))
R_E = E_target(t1) - E_target(t0) - I_B
E_scale = abs(E_target(t1)) + abs(E_target(t0)) + abs(I_B)
U_round_E = max(1.0e-8 * E_scale, 64 * ulp(E_scale))
```

`E_scale`, `R_E`, `U_quad`, and `U_round_E` are in joules. The frozen fixture
requires `E_scale > 0`. Every quadrature value and reported error must be
finite. An `IntegrationWarning`, an explicit convergence or failure message, or
a nonfinite value or reported error is `QUADRATURE REFERENCE NOT RELIABLE`.
C2V-04 then fails and is not evidence.

Before the energy comparison, require `U_quad <= 0.1 * U_round_E`. The factor
`0.1` is frozen and reserves at most ten percent of the represented energy
budget for quadrature uncertainty. Only after that gate,

```text
abs(R_E) <= U_round_E + U_quad
```

A large `U_quad` cannot manufacture a pass. `U_quad` and `U_round_E` are
recorded separately. Production `cumulative_work_j` is diagnostic only. There
is no battery-energy claim.

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

Purpose: one manufactured transverse crossing of the lower stop at analytic
time `t_c`.

The target on `t in [0, 1]` s, with `N = 2`, is

```text
theta*(t) = -0.20 - 0.40 t
theta_dot*(t) = -0.40
theta_ddot*(t) = 0
omega*(t) = 40
omega_dot*(t) = 0
Qm*(t) = 0.04 N m
Qh*(t) = 0
```

`lower_stop = -0.50 rad` and `upper_stop = 0.20 rad`, so `t_c = 0.75 s`.
The aerodynamic loads are the unique synthetic values that realize those
target accelerations. They are not FoldableBEM or PR #74 loads.

```text
Q_phi*(t) = -Qm*(t)
            - N C sin(theta*(t))
              (2 omega*(t) theta_dot*(t) + theta_dot*(t)^2)

q_theta*(t) = -Qh*(t)
              + k (theta*(t) - theta_rest)
              + b theta_dot*(t)
              + tau_c tanh(theta_dot*(t) / v)
              + C omega*(t)^2 sin(theta*(t))
```

The shaft formula is the zero-acceleration shaft row. The hinge formula is
the zero-acceleration hinge bracket. Metadata may name the queried state.
The force values stay these target-time functions. On `[0, t_c]` the target
stays inside the fold domain and above the 100 rpm floor.

For this frozen target, `v_min = 0.40 rad/s` on the event neighborhood. The
target stays inside the fold domain and above the 100 rpm floor on `[0, t_c]`.

The future harness may wrap the imported `_first_contact` for observation
only. The wrapper calls that function unchanged. It does not replace the
solver, change a load, change an exception, or alter a numerical return. When
the real function returns an event, the wrapper keeps the accepted RK45 step
start, step end, event time, and the production dense callable. It evaluates
that dense output at the event time before the externally returned angle is
replaced by the exact stop:

```text
theta_dense_event = dense(t_contact)[0]
omega_dense_event = dense(t_contact)[2]
theta_target_event = theta*(t_contact)
S_theta_event = angle_atol_rad + rtol * abs(theta_target_event)
D_event = abs(theta_dense_event - theta_target_event)
```

Require `D_event <= S_theta_event`. This is a direct dense-output check at the
event time. It is not inferred from stored samples, and `S_theta_event` is not
claimed to be a proved maximum dense-interpolation error.

On the accepted step, reconstruct the production contact scale from the five
fixed normalized nodes:

```text
scale_contact = max(1, abs(stop), abs(theta_dense(node_0)), ..., abs(theta_dense(node_4)))
angle_tol_contact = max(8 * angle_atol_rad, 2 * ulp(scale_contact))
```

Require `abs(theta_dense_event - stop) <= 4 * angle_tol_contact`. This records
the post-root acceptance condition before the stop value hides the dense angle.
Both angle comparisons are in radians.

The Brent solve is in normalized step coordinates. With
`step_width = step_end - step_start` and
`xi_event = (t_contact - step_start) / step_width`,

```text
U_root_time = step_width * (1e-14 + 1e-14 * abs(xi_event))
T_allow = (S_theta_event + 4 * angle_tol_contact) / v_min + U_root_time
```

`T_allow` and `U_root_time` are in seconds. This is a frozen numerical
acceptance policy, not an RK45 dense-error theorem. Because `D_event` has its
own gate, a large dense error does not enlarge `T_allow`.

Require the lower stop, `abs(t_contact - t_c) <= T_allow`, the terminal
pre-impact hinge rate against `theta_dot*` under its section 7 state scale,
the terminal shaft speed against `omega*` under its section 7 state scale, and
no later sample. If a right-hand-side stage leaves the declared model domain
before contact can be reconstructed, the case is invalid or inconclusive. It
is not a success, and the frozen fixture is not replaced.

### C2V-08 — representative fail-closed boundary

Purpose: CMM-2 fails closed on representative exits and returns no shortened
success.

Oracle class: `REGRESSION_CONTRACT`.

Shared dense-quartic isolation remains a CMM-1 dependency. This case shows that
CMM-2 invokes fail-closed behavior. It does not reimplement that proof and
does not repeat every lower-layer exception test. There is no separate
configurable work budget. The production message may still say that the work
budget was exhausted when `max_rhs_evaluations` is hit. `max_samples` may be
recorded as a separate regression.

Unless a subcase overrides them, every subcase uses the shared synthetic
mechanism, `N = 2`, that fixture's `I0`, zero hinge actuation on two knots
that span the subcase duration, a finite synthetic motor sample `Qm = 0.04 N m`,
and a finite synthetic aerodynamic sample `Q_phi = -0.02 N m`,
`q_theta = 0.004 N m`, finite thrust, and the accepted CMM-2 mapping and
qualification metadata. Production controls are the repository defaults except
the one control the subcase changes.

Fold exit is manufactured, not constant forcing. On `t in [0, 0.5] s`,

```text
theta*(t) = -1.20 - 1.00 t
theta_dot* = -1.00 rad/s
theta_ddot* = 0
omega* = 40 rad/s
omega_dot* = 0
lower_stop = -2.0 rad
upper_stop = 0.5 rad
Qm* = 0.04 N m
Qh* = 0
```

`Q_phi*(t)` and `q_theta*(t)` use the same zero-acceleration formulas as
C2V-07. The initial angle is inside the fold domain. The target reaches
`theta = -pi/2` at `t_fold = pi/2 - 1.20`, before the lower stop at `t = 0.8 s`.
The expected result is an integration-time `Cmm2DomainExit` for the fold
domain and no successful shortened artifact. This subcase does not claim
mechanical contact.

Speed exit uses `omega0 = 10 rad/s`, which is below `OMEGA_MIN`, with
`theta0 = -0.3 rad` and `theta_dot0 = 0`. It fails while
`Cmm2TransientRequest` is constructed, before integration and before either
callback. The expected class is `Cmm2TransientError` for the screening-minimum
speed contract. The callables are still the valid finite callables required by
the request, and they are not invoked. This is request-time validation, not an
integration-time domain exit.

The budget subcase uses `theta0 = -0.3 rad`, `theta_dot0 = 0.1 rad/s`,
`omega0 = 40 rad/s`, duration `0.2 s`, the shared finite loads, and
`max_rhs_evaluations = 1`. The initial record consumes evaluation 1. The first
integration right-hand side attempts evaluation 2 and raises
`Cmm2TransientFailure` with message `CMM-2 work budget exhausted.` There is no
successful shortened artifact.

The hard-failure subcase uses the same interior request and duration, and the
frozen finite motor sample. The aerodynamic callback raises
`Cmm2TransientFailure` with message `hard failure` on the first aerodynamic
call during the initial record. That failure propagates. There is no
successful result and no continued trajectory.

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
load: the infinity-norm gap between the exact represented accelerations for
mapped signed `Q_phi` and for that raw positive resisting torque must exceed
`B_abs_correct` from section 10, in acceleration units. Otherwise this fixture
is not valid evidence. Dimensionless `B_rel` is not that threshold.

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
represented system. Each production acceleration component is converted the
same way, `x_prod_fraction_j = Fraction.from_float(x_prod_float_j)`. The exact
represented residual is only

```text
r_fraction = b_fraction - M_fraction * x_prod_fraction
```

`Fraction` is not built from `str(x_prod)`, decimal formatting, JSON text, or
a rounded decimal literal. `||r||_inf`, `rho_inf`, `B_abs`, and the forward
bound use `r_fraction`. Report the row backward errors, `kappa_inf`, the
measured forward error, and the theoretical bound. No value is fitted to
production output.

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

If the denominator is zero and `r` is zero, `rho_inf = 0`. If the denominator
is zero and `r` is not zero, `rho_inf` is undefined and the relative bound is
not used. The absolute branch does not depend on `rho_inf`.

If `||x_ref||_inf == 0`, the absolute branch applies directly:

```text
E_abs = ||x_prod - x_ref||_inf
B_abs = ||M^-1||_inf * ||r||_inf
```

and the case requires `E_abs <= B_abs`, in acceleration units. That branch is
not inconclusive merely because a separately computed
`kappa_inf * rho_inf >= 1`.

If `||x_ref||_inf > 0` and `kappa_inf * rho_inf < 1`,

```text
E_rel = ||x_prod - x_ref||_inf / ||x_ref||_inf
B_rel = 2 * kappa_inf * rho_inf / (1 - kappa_inf * rho_inf)
```

and the case requires `E_rel <= B_rel`. The factor of two belongs to this
normwise residual definition. The one-factor quotient is not the bound.
`B_rel`, `rho_inf`, `kappa_inf`, `eta_i`, and `e_j` are dimensionless.
`B_rel` is not an acceleration threshold.

If `||x_ref||_inf > 0` and `kappa_inf * rho_inf >= 1`, the state is
`NUMERICALLY INCONCLUSIVE` for the relative forward bound. It is not C2V-01
evidence. The row backward-error gate remains a separate check. No other
forward envelope is chosen after seeing `x_prod`. The `Fraction` reference
adds no further reference uncertainty.

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

`C2V09-00` is that unmodified base. `C2V09-01` through `C2V09-25` are the
ordered single-field seal variants in
`test_seal_tracks_declared_inputs`. `C2V09-26` and `C2V09-27` are appended, in
committed source order, from the separate motor-domain test. They are not all
single-field changes. `C2V09-27` changes three fields together: motor
`current_max_a = 5`, throttle `1`, and initial shaft speed `1000 * pi / 30`.
The order itself stays frozen:



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

Selection walks that order. Phase A reconstructs the candidate exactly. If
construction, sealing, or binding validation fails, the result is
`CONTRACT BLOCKED` and the next candidate is not tried. These candidates are
claimed to reproduce committed bindings. Phase B performs only the frozen
initial-state preflight. An expected motor, BEM, or map domain or convergence
rejection for that candidate is `CANDIDATE REJECTED: SOURCE DOMAIN`, and
selection continues. A failed detectability predicate or an insufficient
domain or partition margin is `CANDIDATE REJECTED: PREFLIGHT PREDICATE`, and
selection continues. An unexpected exception or a provenance or seal
inconsistency is `CONTRACT BLOCKED`. A Q4 failure is
`PRODUCTION DEFECT / CONTRACT BLOCK`, and selection stops. No trajectory
metric is computed for a rejected candidate. The first candidate that passes
every rule is selected. After selection, no other candidate is substituted.
If none pass, the result is `CONTRACT BLOCKED`.

Detectability, fixed before any trajectory error is known:

- `q_theta` is resolvable when
  `||x_ref(q_theta) - x_ref(q_theta = 0)||_inf > B_abs_correct`,
  with `B_abs_correct` in `rad/s^2`
- the raw-torque mutant is resolvable when
  `||x_ref(mapped Q_phi) - x_ref(raw positive rotor torque)||_inf > B_abs_correct`
  for that same BEM evaluation, again in `rad/s^2`
- aerodynamic hinge work uses a one-state power scale, not the C2V-04
  manufactured `dE/dt`. Fresh mapped loads and the motor sample are assembled
  into `M` and the right-hand side. The exact represented solve of section 10
  supplies `omega_dot_ref` and `theta_ddot_ref`. `(dE/dt)_ref` is the
  independent derivative of the declared mechanical energy at that same state.
  Production `power_identity` is not that derivative. Then

```text
P_scale_09 = abs((dE/dt)_ref)
           + abs(Qm omega) + abs(Q_phi omega)
           + abs(N q_theta theta_dot) + abs(N Qh theta_dot)
           + abs(N b theta_dot^2)
           + abs(N tau_c theta_dot tanh(theta_dot / v))
U_P09 = 0 if P_scale_09 == 0
        otherwise max(1.0e-8 * P_scale_09, 64 * ulp(P_scale_09))
```

  Hinge work is resolvable when `abs(N q_theta theta_dot) > U_P09`. Both
  `P_scale_09` and `U_P09` are in watts.

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

- `contract_head`
- `critical_fixture_manifest_sha256`
- ordered-list identity `prc_c2v09_ordered_candidates_v1`
- candidate input digests
- candidate disposition codes in order
- frozen controls
- preflight rules
- all preflight metrics
- selected index
- selected sealed-request digest
- Q2 uncertainty values
- `q_theta`, hinge-work, and raw-versus-mapped detectability
- domain margin and partition margin, in metres
- Q4 result

`selection_record_sha256` is the SHA-256 of that canonical JSON, computed
before the trajectory acceptance routine is called. The later evidence JSON
contains both `critical_fixture_manifest_sha256` and
`selection_record_sha256`. The implementation test must show that the
selection digest exists before that routine runs. A file that contains only
the selected request digest is not enough.

Q4 is closed as an acceptance policy and measured during the implementation
preflight. The same physical and numerical BEM and mapper inputs, with only
the evaluation index or source metadata changed, must produce identical finite
IEEE-754 binary64 bit patterns for `thrust_n`, mapped `Q_phi`, and mapped
one-tip `q_theta`. The comparison is the eight-byte pattern equivalent to
`struct.pack("!d", value)`. It distinguishes `+0.0` from `-0.0`. There is no
tolerance: that metadata is not an input to the numerical calculation, so a
different floating-point operation sequence is not allowed. Identifier strings
may differ. Any differing numerical bit pattern is
`PRODUCTION DEFECT / CONTRACT BLOCK`. No replacement candidate is used. Test-only
wrappers may observe the index variants. They call the real production
functions unchanged and do not replace the solver, change a load, change an
exception, or alter a numerical return.

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

Q4. CLOSED AS ACCEPTANCE POLICY. The binary64 bit-identity rule is frozen.
The measurement itself is executed during the implementation preflight.
Failure blocks C2V-09 and does not permit a substitute fixture.

Q5. OPEN RUNTIME CHARACTERIZATION. It may affect only where C2V-12 runs. It
cannot weaken C2V-01 through C2V-10 or remove C2V-09.

No other merge-critical acceptance policy is undefined.

State scales are radians and radians per second. `B_abs` and the mutation and
load-detectability gaps are radians per second squared. `B_rel`, `rho_inf`,
`kappa_inf`, `eta_i`, and `e_j` are dimensionless. Torques are newton-metres.
`U_P` and `U_P09` are watts. `R_E`, `U_quad`, and `U_round_E` are joules.
`T_allow` is seconds. Partition margins are metres. Q4 equality is binary64
bit identity and has no physical-unit tolerance. A state scale does not gate
watts, joules, acceleration, torque, or time.

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
duration `1.0 s`, `max_step_prod = 0.002 s`. Target:
`theta*(t) = -0.20 - 0.40 t`, `theta_dot* = -0.40`, `theta_ddot* = 0`,
`omega* = 40`, `omega_dot* = 0`, `Qm* = 0.04 N m`, `Qh* = 0`. Then
`t_c = 0.75 s`. `Q_phi*(t)` and `q_theta*(t)` are the section 8 target
formulas, not constant loads. The analytic target is the authority for
`v_min` and domain membership on `[0, t_c]`.

C2V-08. Shared mechanism, `N = 2`, and that fixture's `I0`, unless a subcase
overrides them. Zero actuation uses two knots spanning the subcase duration.
Default controls apply except the named override. Fold exit: manufactured
`theta*(t) = -1.20 - 1.00 t`, `theta_dot* = -1`, `theta_ddot* = 0`,
`omega* = 40`, `omega_dot* = 0`, stops `(-2.0, 0.5)`, duration `0.5 s`,
`Qm* = 0.04 N m`, `Qh* = 0`, and the C2V-07 zero-acceleration load formulas.
Expected layer: integration-time `Cmm2DomainExit`, not mechanical contact.
Speed exit: `omega0 = 10 rad/s < OMEGA_MIN`, `theta0 = -0.3`,
`theta_dot0 = 0`. Expected layer: `Cmm2TransientError` during request
construction, before callbacks. Budget exit: `theta0 = -0.3`,
`theta_dot0 = 0.1`, `omega0 = 40`, duration `0.2 s`, shared finite loads
`Qm = 0.04`, `Q_phi = -0.02`, `q_theta = 0.004`, `max_rhs_evaluations = 1`.
Expected layer: `Cmm2TransientFailure` with message
`CMM-2 work budget exhausted.` on evaluation 2. Hard failure: the same
interior request; the aerodynamic callback raises `Cmm2TransientFailure`
with message `hard failure` on the first aerodynamic call of the initial
record. Expected layer: that failure, with no continued trajectory.

C2V-09. The ordered candidate list in section 11. No other inputs.

C2V-10. `N = 2`, duration `0.8 s`, knots `(0, 0.4, 0.8)` s, torques
`(0, 0.002, -0.001)` N·m. Initial state `theta = -0.3 rad`,
`theta_dot = 0.1 rad/s`, `omega = 40 rad/s`. Constant manufactured
`Q_phi = -0.02 N m` and `q_theta = 0.004 N m`. `Qm = 0.04 N m`. Probe offset
is the section formula, which is `0.1 s` for these equal segment widths.

## 17. Implementation boundary

Implementation against this amended contract has not started. Draft PR #81
is an existing blocked evidence attempt and is not an implementation of this
amended contract. This pull request adds no test, fixture, or
production change. Expected production-code changes for the later
implementation are none. Test-only wrappers may observe the pre-snap dense
contact state, evaluation-index variants, and selection sequencing. They call
the real production functions unchanged. They do not replace the solver,
change a load, change an exception, or alter a numerical return. No production
observability change is authorized. If rigorous verification needs a
production change, stop and report the missing observability or defect
separately. Do not change equations to obtain a pass.

## 18. Acceptance boundary

Review of this contract is not verification acceptance. Passing tests do not
yet exist. Status is REVIEWED / FROZEN FOR IMPLEMENTATION WITH C2V-02
ARITHMETIC AMENDMENT. The trajectory acceptance policy was never reopened.
Prior independently reviewed contract head:
`613072514f793f2a1bc65704f9158f536210707f`. Reviewed amended technical head:
`b840ec55b4d1dd57197b97e91e1a48a7fbe7da0d`. That amended-head review is
APPROVE from a separate read-only automated reviewer and is not a submitted
GitHub review. Draft PR #81 remains unmerged and BLOCKED. Its C2V-02 and
C2V-03 trajectory results remain FAIL. No accepted PR-C evidence exists.
That status does not record evidence and does not accept ADR-009.
ADR-009 is not created and is not accepted. `physical_qualification` stays
false. PR-06C stays unresolved. No GEOM gate is promoted. There is no
calibration and no experimental validation.

Dynamics contract link:
[CMM-2 PR-A](cmm2_coupled_transient_contract.md).

## Frozen Radau design amendment — not in force for this RK45 contract

[CMM-2 Radau remediation contract](cmm2_radau_remediation_contract.md) is
REVIEWED / FROZEN FOR IMPLEMENTATION — CMM-2 RADAU AMENDMENT at technical
reviewed head `2ec4da9acdccc7508fab7c33f289ec9771b2ea65`. This contract's
production-RK45 requirements remain in force. The freeze does not change the
normative gates above and does not authorize a production implementation.
Current production remains RK45/v1. The frozen amendment governs a separately
authorized future CMM-2 v2 implementation. Radau is not implemented. Q1–Q4,
DOP853 A/B, fixtures, controls and the trajectory gates remain unchanged; Q5
and runtime/partition/minimum-SciPy measurements remain pending. Historical
technical-contract acceptance records above remain unchanged. Draft PR #81
remains BLOCKED; no independent CMM-2 numerical verification is established.
ADR-009 is not created or accepted. `physical_qualification` remains false.

## Proposed numerical-feasibility amendment — not frozen

The [numerical-feasibility proposal](cmm2_numerical_feasibility_amendment.md)
proposes a separately versioned C2V-07 returned-time policy and an appended
C2V-09 source candidate. Its candidate is not selectable on current evidence.
Status is PROPOSED / NOT FROZEN / NOT IMPLEMENTED; this contract, existing
fixture manifest and historical reviews remain unchanged. No PR-C verification
is established, and Draft PR #81 remains BLOCKED.

Prospective append-only [C2V09-29 declaration](cmm2_c2v09_candidate29_proposal.md) retains candidate28
and its mapper rejection, adding a first-party synthetic constant terminal
station under proposed selector v3 (00…27,28,29). Status remains **PROPOSED /
NOT FROZEN / NOT IMPLEMENTED**. Committed-declaration review precedes any
initial-only source/preflight measurement; no trajectory, freeze or acceptance
follows. Main RK45/v1 and unmerged PR81/84 identities are unchanged.

A subsequent [prospective partition-policy declaration](cmm2_c2v09_partition_policy_proposal.md)
uses unchanged candidate29 and a whole stored-scale angle neighborhood. It
preserves literal v1 FAIL/raw zeros and every historical capture; no structural
alias is relabelled as passing v1. The separately versioned proposal and Q4
successor conjunction are **PROPOSED / NOT FROZEN / NOT IMPLEMENTED**.
Committed-declaration review precedes any new initial-only assessment; no
trajectory, ordered selection, v2 seal or acceptance is authorized.
