# CMM-2 Radau remediation — contract amendment

Status: REVIEWED / FROZEN FOR IMPLEMENTATION — CMM-2 RADAU AMENDMENT.

Technical reviewed head:
`2ec4da9acdccc7508fab7c33f289ec9771b2ea65`.

Review result of that technical head: APPROVE FOR CONTRACT FREEZE.
That review was a separate read-only automated reviewer in the coordination
session. It is not a submitted GitHub review. A later status-closure commit
is not this technical reviewed head.

Freezing approves the design contract. It does not authorize production
implementation, demonstrate feasibility, establish PR-C verification, or
accept ADR-009.

Proposal base: `64eea154f72365b647a1cff4d3fc768e45578d0c`.
At that base, production CMM-2 uses SciPy RK45, the existing RK45 quartic
contact reconstruction, and the inherited continuous dense-domain audit.
Radau is not implemented. CMM-1 also continues to use its existing RK45 path.

The original independently reviewed PR-C contract head
`613072514f793f2a1bc65704f9158f536210707f` and the reviewed C2V-02 arithmetic
amendment head `b840ec55b4d1dd57197b97e91e1a48a7fbe7da0d` remain historical
provenance. This proposal does not change those review results or their scope.
Draft PR #81 remains a separate blocked evidence implementation attempt. Its
trajectory failures are not converted into passes by this proposal.

## 1. Motivation, scope, and identities

The preceding read-only diagnosis reproduced the C2V-02 and C2V-03 trajectory
failures without changing the fixtures or controls. At C2V-02, accepted RK45
steps can amplify a rapidly damped mode seeded by representation and rounding.
At C2V-03, accepted local RMS error control does not guarantee the frozen
componentwise global trajectory gate near a hinge-rate zero crossing. These
are distinct observations; fast-mode instability is not asserted to explain
both failures. The Radau experiment used an in-memory RHS mirror with SciPy
1.17.0. It is preliminary characterization, not a production run or evidence
for SciPy 1.15.3 or 1.17.1. No global-error or physical-error theorem is claimed.

If separately reviewed, frozen, and authorized, the amendment would change only
CMM-2 integration and its method-specific dense contact/domain adapter to
SciPy Radau. The equations, acceleration assembly, mass matrix, represented
pivot, residual gates, energy definitions, load signs, and load-map mathematics
remain unchanged. There is no equilibrium shortcut, case recognition, fitted
tolerance, fallback integrator, or oracle substitution.

Existing model and qualification identities remain:

| Identity | Preserved value |
| --- | --- |
| Model class | `coupled_aero_hinge_screening_only` |
| Load mapping | `planar_projected_material_load_v1` |
| Qualification | `screening_only_projected_rate_independent` |
| Hinge-rate aerodynamic model | `ignored_rate_independent_quasi_steady` |
| Projection model | `radial_cosine_v1` |

The proposed numerical implementation identity is separately
`cmm2_planar_projected_rate_independent_coupling_v2`; it is not the current
production identity. Current and archived `v1` records must not be relabeled.
The existing service identity is distinct from the dynamics identity.

CMM-1 RK45 behavior and its accepted dependencies remain unchanged. A new
CMM-2 cubic adapter does not inherit CMM-1 Phase-4 verification merely because
it reuses exact polynomial primitives. It needs its own behavioral checks.
The proposal adds no impact, bounce, latch continuation, dashboard, physical
qualification, or clearance assignment.

## 2. Proposed integration and segment policy

The initial proposed production configuration is `Radau` with `jac=None`,
`jac_sparsity=None`, `vectorized=False`, and `first_step=None`. The existing
request's `rtol`, three component `atol` values, and `max_step_s` are passed
without internal rescaling. Radau's Newton policy is not manually retuned.
No new user control is added. Method-specific initial step selection is part
of the disclosed method change, not a promise of RK45's former step sequence.

Each continuous piecewise-linear actuation segment gets a fresh solver whose
`t_bound` is that segment's endpoint. No accepted interval crosses a knot.
The final accepted state becomes the next segment's initial state unchanged;
the knot sample is not duplicated. The torque is the shared endpoint value,
and the next segment uses the next declared slope. Global RHS/sample budgets
and ledger indices do not reset on restart. `segment_boundary_times_s` retains
its current meaning; no unvisited boundary is published after terminal contact.

Accepted endings remain `completed` and `first_contact_terminal`. An integration
failure, nonfinite state/power, unresolved mass/residual, domain exit, unresolved
polynomial decision, or budget exhaustion does not return shortened success.

## 3. Radau's represented cubic and exact time normalization

For the genuine accepted-step `RadauDenseOutput`, require finite stored
`t_old`, `t`, `h > 0`, `y_old.shape == (3,)`, `Q.shape == (3, 3)`, and
`order == 2`. The state order is `theta`, `theta_dot`, `omega`. The real
representation in the two CI SciPy versions is

```text
x = (t - t_old) / h
y = y_old + Q @ [x, x**2, x**3]
```

Q already contains state-increment coefficients. Do not multiply Q by h again.
The derivative of a represented component with respect to physical time is
`(Q0 + 2 Q1 x + 3 Q2 x**2) / h`. In particular, the dense state component
`theta_dot` need not equal the derivative of the dense angle polynomial.
They have different roles in contact eligibility and root geometry.

Construct the audit representation directly from the stored binary64 values:

```text
T_old = Fraction.from_float(dense.t_old)
H     = Fraction.from_float(dense.h)
Y_i   = Fraction.from_float(dense.y_old[i])
q_ik  = Fraction.from_float(dense.Q[i, k])
X(T)  = (T - T_old) / H
P_i(x) = Y_i + q_i0*x + q_i1*x**2 + q_i2*x**3
```

For each supplied binary64 relative audit endpoint, first take its Fraction,
then subtract and divide exactly. Do not compute `(t - t_old) / h` in float
and convert the rounded result. Do not round an audit interval inward or clamp
its endpoints. Verify physical-time membership against the stored accepted
step endpoints before auditing. Because stored h is a rounded subtraction,
the exact normalization of stored `dense.t` need not equal exactly 1. Audit
the actual resulting rational interval, including that endpoint; do not discard
a sliver by imposing a synthetic `[0, 1]` clamp.

An unexpected representation, inconsistent accepted-step identity, reversed or
out-of-step physical endpoint, or nonrepresentable conversion fails closed.
No cubic is refitted from samples. No Radau object is disguised as an RK45
`RkDenseOutput`. Exact generic polynomial helpers may be reused with explicitly
documented cubic coefficients; that is not reuse of the RK45 representation.

## 4. Complete contact candidates and mechanical-stop breach guard

Search the entire exact normalized accepted interval. For each stop, construct
the rational stop-relative angle polynomial `P_theta - stop`. Include exact
endpoint roots and isolate all interior roots and all interior roots of its
derivative. Determine root counts and identities with exact rational polynomial
operations and bounded real-axis isolation, not complex-root filtering or
sampling. Exact roots of zero/constant polynomials are handled explicitly;
an identically stop-valued interval must resolve its earliest eligible point
or fail, not enter an unbounded root search.

The existing five normalized observation fractions remain
`[0, 0.25, 0.5, 0.75, 1]` for the contact scale. They span the actual accepted
step's physical endpoints. Their physical-time conversion must retain interval
membership under section 5. The production dense callable is evaluated there:

```text
scale_contact = max(1, abs(stop), abs(theta_dense(node_0)), ...,
                    abs(theta_dense(node_4)))
angle_tol_contact = max(8 * angle_atol_rad, 2 * ulp(scale_contact))
velocity_tol_contact = max(8 * hinge_velocity_atol_rad_s,
                           2 * ulp(scale_contact) / step_width)
```

These nodes calculate the existing contact tolerance scale only. They do not
decide whether roots, hidden crossings, or domain excursions exist.

Every interior stationary point is classified, separately for each stop:

| Class | Required proof and disposition |
| --- | --- |
| Exact contact | Its own isolated derivative root is also a root of the stop-relative polynomial; insert that contact candidate. |
| Tolerance contact | It is not an exact contact and its stationary stop distance is proven `<= 8 * angle_atol_rad`; insert that candidate obligatorily. |
| Excluded | Its stationary distance is proven `> angle_tol_contact`; exclude that stationary point as a tangent candidate. |
| Unresolved | The distance is between the two thresholds, or a threshold-straddling enclosure/identity cannot be resolved within the bounds; fail closed. |

Threshold equalities are evaluated with exact representations of the declared
thresholds; an enclosure crossing a threshold is not decided from its midpoint.
Refine it within the same search context, or fail. The exact and tolerance
classes retain the existing tangent policy; tolerance contact is not claimed
to prove an exact stop root. A merely near endpoint is not a tangent candidate.

Merge an exact/tangent discovery of the same event only after proving the same
root identity in its own bracket (including endpoint multiplicity handling).
Nearby distinct roots or stationary points must not be merged by proximity,
floating equality, or a shared rounded event time.

All proven exact and tolerance candidates enter direction eligibility and the
first-event selection. At a candidate, the original dense state's hinge rate
must satisfy `rate <= velocity_tol_contact` for the lower stop and
`rate >= -velocity_tol_contact` for the upper stop. A direction decision whose
root/state enclosure remains unresolved fails. Do not substitute
`d(P_theta)/dt` for the dense `theta_dot` in this test.

Determine outward stop breach from both endpoint values and every stationary
value. Lower breach is `lower_stop - P_theta > angle_tol_contact`; upper breach
is `P_theta - upper_stop > angle_tol_contact`. Refine a threshold-straddling
enclosure or fail. If a stop is breached and no direction-eligible contact for
that stop is proved, do not return no-contact success or hide the breach behind
another stop event. Fail closed. This guard matters because angle-polynomial
direction and the dense hinge-rate state can differ.

Select the earliest eligible candidate across both stops using proved root
ordering. Refinement cannot reset the search budget. Unresolved ordering fails
instead of selecting an arbitrary stop. Validate that no unclassified earlier
stationary point or unhandled earlier breach can invalidate that selection.
An exact endpoint contact is included once; a close endpoint is not invented
as a hit. Stop angle snapping occurs only after the pre-snap dense-state checks.

## 5. Root location, returned time, and continuous domain audit

For a transverse root, use its certified monotone bracket and Brent in
normalized coordinates with `xtol = rtol = 1e-14`. Keep the candidate's exact
root identity and enclosure. A tangent candidate uses bounded root refinement
of its stationary polynomial at the same normalized precision. Neither branch
claims a generic tangent-event timing theorem.

Event conversion is a checked operation, not an unchecked
`float(t_old + h * xi)`. From the identified candidate, form a rational relative
time with stored `T_old` and `H`, choose the representable relative time, and
form the actual returned absolute time using the existing origin. Check:

1. The relative and returned absolute times are finite and inside the accepted
   physical interval; the event does not precede the last published sample or
   create a duplicate/nonadvancing event.
2. Normalize the chosen relative time exactly. Also normalize the actual public
   time by first computing `Fraction(returned_time) - Fraction(origin)` and
   then subtracting `T_old` and dividing by `H`, all rationally.
3. Each normalized conversion remains within the existing normalized root
   allowance `1e-14 + 1e-14 * abs(xi_event)` of the identified candidate's
   certified location. Exact root-count/identity checks on the enclosure
   containing the candidate and converted points must exclude another distinct
   candidate; numeric closeness alone is insufficient.
4. Prove that the conversions preserve the selected event's order against all
   other candidates and its direction eligibility. If two distinct events
   collapse to one representable time or order cannot be proved, fail.
5. Re-evaluate the original dense callable at the actual chosen relative event
   time and enforce the existing pre-snap angle/rate/speed checks. Do not move
   an event into the interval by clamp or silently switch to another root.

Bounded conversion/refinement retries share the original contact budget.
If time quantization, a large absolute origin, or root clustering prevents these
checks, the conversion is unresolved and fails closed; no new allowance is fit.

Continuous domain audit covers the actual interval to the actual returned event
time, normalized from its exact public-time/origin subtraction. It also covers
the dense evaluation point used for the event state if rounding makes that
point later. It must not stop at an ideal unreturned rational root or a rounded
inward endpoint. With no contact it covers the entire accepted interval.

For theta and omega, check represented polynomial endpoints and all stationary
values, with bounded exact isolation and value enclosures. Check the actual
accepted/event state as well. Preserve the current fold coordinate, constants,
and state validation: fold equality is outside the strict fold domain; shaft
floor equality is inside the inclusive shaft domain only when the remaining
interval is also inside. At a stationary boundary straddle, equality requires
that this bracket's own stationary root is a root of that boundary-level
polynomial. A common root elsewhere does not authorize it. Unresolved value,
identity, or interval fails closed; there is no tolerance or sampling fallback.

This is an audit of the represented cubic, not a maximum dense interpolation
error bound for the ODE. Any RHS/Newton/Jacobian trial leaving the existing
state or source domain still raises immediately. A later reconstructable
contact cannot erase that failure, even when the trial would later be rejected.
No perturbation clamp, one-sided replacement, or exception-to-success retry is
authorized here.

## 6. Explicit root-work scope and limits

For each accepted interval create two separate internal root-work counters:
contact work `800`, covering both stops and every candidate/selection/conversion;
domain work `800`, covering theta and omega over all required audited portions.
They are not per-root allowances. Re-auditing a portion of the same interval,
retrying an enclosure, or converting the event again does not reset a counter.
A new accepted interval starts new counters. Neither is a user control.

Debit the applicable counter before each of these operations:

- a root-isolation node visit, root-count/Sturm-chain query, or root-identity
  polynomial-GCD query, including endpoint-root deflation;
- a subdivision or single-root bracket-refinement step;
- a stationary-value enclosure/classification query, direction enclosure query,
  or candidate-order refinement query;
- a Brent polynomial evaluation or an event-time conversion attempt and its
  associated identity/order verification (nested listed operations also debit);
- a repeated domain boundary-enclosure/equality query during refinement.

Finite-degree arithmetic within a single charged operation is not a separate
unit. There is no unmetered retry loop around those operations. Exhaustion of
either counter produces a CMM-2 failure and no shortened successful artifact.

Three different limits must not be conflated:

- **80 refinement iterations:** the cumulative maximum bisection/refinement
  steps for an identified root bracket, including its later accuracy, threshold,
  ordering, and conversion refinements. Restarting a helper does not provide
  another 80. A needed unresolved decision at this limit fails.
- **`2^-80` normalized width:** the existing isolation width target/floor. It is
  not 80 levels of recursion, a physical-time tolerance, or proof that a
  boundary value has been decided. If multiple roots or a required classification
  remain unresolved at that width, fail. Exact rational singleton roots have
  zero width. The width stopping rule can be reached before 80 iterations.
- **32 isolation recursion depth:** the current `_isolate_real_roots` check
  rejects `depth > 32` with initial depth 0. Keep that separate recursion bound;
  80 must not be described as the recursion limit.

The current CMM-1 primitives do not themselves implement every new charge and
shared refinement scope above. The future CMM-2 adapter must add the missing
accounting without weakening limits or changing CMM-1 helpers. This explicit
accounting is part of the proposed amendment, not a claim about current code.

## 7. C2V-07 observation and unchanged numerical acceptance

The verification wrapper must observe the actual new CMM-2 contact routine,
calling it unchanged, and capture its accepted-step endpoints, event time, and
original dense callable before the published angle is snapped. The old imported
RK45 `_first_contact` is not the observer target for a Radau implementation.

The existing fixture, lower stop, `t_c`, `v_min = 0.40 rad/s`, five contact-scale
nodes, and these gates remain:

```text
theta_dense_event = dense(t_contact_relative)[0]
theta_target_event = theta*(t_contact)
S_theta_event = angle_atol_rad + rtol * abs(theta_target_event)
D_event = abs(theta_dense_event - theta_target_event)
D_event <= S_theta_event
abs(theta_dense_event - stop) <= 4 * angle_tol_contact

step_width = step_end - step_start
xi_event = (t_contact_relative - step_start) / step_width
U_root_time = step_width * (1e-14 + 1e-14 * abs(xi_event))
T_allow = (S_theta_event + 4 * angle_tol_contact) / v_min + U_root_time
abs(t_contact - t_c) <= T_allow
```

The event time in the gate is the actual returned time. Relative and absolute
coordinates must use the same declared origin; section 5 also applies. This
root-time allowance is the existing numerical acceptance policy, not a Radau
time-conversion/global-error theorem. It is not a tangent timing allowance.
Large dense error cannot enlarge T_allow. Terminal pre-impact hinge rate and
shaft speed use the existing section-7 state scales; no later sample is allowed.
The dense-angle gate cannot be satisfied with the already snapped stop angle.
No measured requirement to loosen these numbers is asserted. Failure remains
failure or inconclusive, not permission to change the fixture or gate.

## 8. Actual calls, provenance, and unchanged independent reference

The existing `evaluate()` path accounts for all actual evaluations: initial
record, solver initialization/initial-step selection, stage/Newton iterations,
rejected trials, Jacobian finite-difference calls, and accepted/contact sample
records. Its counter increments before the existing ceiling check; the
ceiling-plus-one call fails before callbacks. It is global across segments.
SciPy `nfev`, `njev`, and `nlu` are diagnostics, not replacements for this counter.
`nfev` alone omits finite-difference RHS work in the supported SciPy path.

Every successful aerodynamic call passes through the existing evaluator and
the same BEM-to-map pipeline. Successful rejected-trial and Jacobian calls are
not removed from the ledger. Preserve:

```text
successful_bem_solves == successful_map_calls
                     == provenance_ledger_length
                     == result.aero_evaluations
```

Each published sample resolves its unique source id to the ledger's exact state
and loads. At contact, `record()` evaluates the published snapped-angle state;
pre-snap dense observations remain distinct. Source failures propagate without
load substitution. Q4's metadata/index-only IEEE-754 binary64 bit-identity
preflight, including signed zero, remains mandatory. Ledger lengths, id sequences,
and report hashes are not compared across different integrators/environments.
Same-input reproducibility is checked within one exact implementation and
recorded runtime environment. Older seals/artifacts are not relabeled as v2;
changed implementation identity must pass the existing prepare/seal validation.

DOP853 Reference A/B remains the independent oracle with test-owned M/RHS:

```text
A: rtol_prod/100,   atol_prod/100,   max_step_prod/4
B: rtol_prod/10000, atol_prod/10000, max_step_prod/8
S_j = atol_j + rtol * abs(y_ref_B,j)
abs(y_ref_B,j - y_ref_A,j) <= 0.1 * S_j
e_j = abs(y_prod_j - y_ref_B,j) / S_j
max e_j <= 1 for every component
```

Measure stabilization at all new actual production sample times, including the
terminal sample. Do not reuse stabilization at old RK45 times. References do
not consume production ledger loads as their equation oracle. Keep ordinary Q2,
the C2V-02 analytic bridge, Q1-Q4, critical fixtures, controls, ordered C2V-09
selection and detectability, energy gates, and characterization status unchanged.
Q5 remains open; a runtime problem cannot remove a critical case or select a
cheaper fixture. PR #81 is not changed or accepted by this proposal.

## 9. Proposed amendment locations and historical records

The current documents remain authoritative for the implemented RK45/v1 path.
This design freeze does not rewrite their production rules. The following
future changes would require a separately authorized CMM-2 v2 implementation:

| Existing document/section | Proposed change if separately approved |
| --- | --- |
| PR-A identity and Isolation from CMM-1 | Distinguish numerical v2 and CMM-2 Radau/cubic contact/domain from current inherited RK45 helpers; preserve equations and CMM-1. |
| PR-A Termination and Later slices | Include new cubic/conversion/budget failures and a separate amendment record; preserve PR #76/#78 historical acceptance. |
| PR-C header, section 1, section 18 | Add the new amendment's actual provenance/status; preserve original and arithmetic-amendment review records and absent verification acceptance. |
| PR-C section 3 | Keep verification-only work separate from an explicitly authorized production remediation PR. |
| PR-C section 4 | Inherited mass/energy/pivot/residual primitives remain dependencies; the new cubic adapter needs its own regressions, not inherited CMM-1 proof. |
| PR-C section 7 and C2V-05 | Name production Radau and method-independent limitations; keep DOP853 A/B and every state-scale constant. |
| PR-C C2V-07 | Observe the actual cubic contact routine and returned-time conversion; keep angle, root-time and T_allow gates. |
| PR-C C2V-08 and section 12 | Replace the inherited quartic dependency description with the tested cubic/domain/budget behavior and real stage/Jacobian failures. |
| PR-C C2V-09 | State that Radau/DOP853 call order differs; preserve Q4, source matching, selection and oracle independence. |
| PR-C C2V-10 | Explain Radau segment restart without changing the continuous actuation fixture or state gate. |
| PR-C sections 13-14 | Record method/runtime versions and real calls; execute the existing critical matrix in both specified CI environments. |
| PR-C section 17 | Keep the verification harness production-free; separately identify the approved remediation and updated observation target. |
| PR-B Identifiers and Seal and report | Identify numerical v2 and the new helper in the implementation manifest; preserve mapping/ledger semantics and archived v1 seals. |

No mathematical or acceptance change is proposed to PR-C section 2, C2V-01
through C2V-04, C2V-06 represented gates, sections 10-11, Q1-Q4 in section 15,
or section 16's frozen manifest. No historical current-state snapshot or
ADR-006/007/008 acceptance entry is rewritten. This proposed document is not
an ADR-009 acceptance record.

## 10. Future bounded implementation and acceptance plan

After separate contract review/freeze and implementation authorization, the
proposed production scope is `pyfoldable/dynamics/cmm2_coupled_transient.py`, a
new `pyfoldable/dynamics/cmm2_radau_dense.py`, and only the necessary numerical
manifest/provenance join in
`pyfoldable/application/cmm2_coupled_transient_service.py`. Current CMM-1
production files, aero mapping, motor law, equations, and user controls remain
unchanged. These are proposed paths; the new helper does not exist at the base.

Required future behavioral regressions, with RED before implementation:

- genuine Radau Q representation/no extra h; malformed/nonfinite representation;
  exact endpoint normalization that would be rounded inward by float arithmetic;
- hidden crossing, exact/tolerance tangent completeness, threshold straddle,
  same-root merging versus distinct nearby roots, direction disagreement,
  mechanical-stop breach guard, earliest event, and time-quantization/order failure;
- fold equality exit, shaft-floor equality safe, hidden domain excursion, same
  stationary-root identity, audit through actual returned time, and no fallback;
- both root counters, cross-stop/component scope, no reset during retry,
  refinement/width/recursion distinctions and exhaustion;
- actual constructor/stage/Jacobian/rejected/sample call counts, budget+1 failure,
  and ledger/sample/source-state matching, Q4 bit identity, seal/manifest identity;
- segment continuity and terminal sample/boundary behavior; unchanged CMM-1;
- frozen C2V-02/C2V-03/C2V-05 trajectories and new-time A/B stabilization, then
  all other merge-critical cases, including C2V-07 through C2V-10.

Extra polynomial regressions must not modify the frozen critical fixtures.
No PR #81 evidence commit is part of this docs-only proposal branch.

The current Tests workflow has Python 3.10/3.11 and floating dependency ranges.
Observed CI environments use Python 3.10/SciPy 1.15.3 and Python 3.11/SciPy
1.17.1. The future implementation must measure both exact combinations and
record Python/NumPy/SciPy versions, actual checkout and PR-source heads, method,
real call counts, and exact-head CI. The SciPy 1.17.0 diagnosis cannot stand in
for either. Official dense sources:
[1.15.3](https://github.com/scipy/scipy/blob/v1.15.3/scipy/integrate/_ivp/radau.py)
and [1.17.1](https://github.com/scipy/scipy/blob/v1.17.1/scipy/integrate/_ivp/radau.py).
Green CI on this documentation proposal is regression evidence for the existing
RK45 tree, not evidence that Radau has been implemented or passes PR-C.

Pending measurements/questions: real source-bound Newton/finite-difference
runtime and budgets; partition/domain behavior of those probes; returned-time
quantization feasibility under the strict conversion checks; the new cubic
adapter's actual regressions; Q4 preflight measurement; and minimum-SciPy
compatibility under the currently declared `scipy>=1.7` range. Two tested
versions cannot establish support for that entire range. None is resolved by
fixture/threshold retuning. Q5 stays OPEN RUNTIME CHARACTERIZATION.

`physical_qualification` remains false. Independent CMM-2 numerical verification
is NOT ESTABLISHED. ADR-009 is NOT CREATED / NOT ACCEPTED. PR-06C remains
unresolved; GEOM promotion, calibration, and experimental validation remain
NONE. Neither the proposal nor a future production fix accepts PR #81 or the
complete PR-C evidence package.

Related current contracts: [PR-A](cmm2_coupled_transient_contract.md),
[PR-B](cmm2_source_bound_production_binding.md), and
[PR-C](cmm2_numerical_verification_contract.md).
