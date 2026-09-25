# Handoff — CMM-1 partial coupled screening transient

## Purpose

Implement the reviewed CMM-1 screening transient as a new workflow. Do not
replace PY-05, change PR-07 equations, or promote GEOM clearance.

## Base

`origin/main` at `aadfeaccd7867645706221532c467498fde4720f`.

## What landed

- Pure dynamics in `pyfoldable/dynamics/coupled_transient.py`.
- Source-bound service in `pyfoldable/application/coupled_transient_service.py`.
- Public PR-07 adapter `algebraic_motor_state` with no equation change.
- Focused dynamics and application tests.
- ADR-005 and `docs/cmm1_partial_coupled_transient.md`.
- Short roadmap, execution-plan, current-state, and PY-05 boundary notes.

## What did not land

- Dashboard changes.
- CMM-2 aerodynamic hinge torque.
- A successful `model_domain_exit` event locator. Domain departure fails closed.
- Physical qualification, calibration, optimization, or GEOM `True`.
- Any change to PY-05, PR-07 equilibrium behavior, BEM equations, or GEOM #67–#69.

## 2026-09-24 merge-blocker correction

Previous request-changes head: `9cda75cfc1f25035253d7ddae229f18df08f513b`.

Four defects at that head are closed without changing the approved equations:

- Every accepted RK45 quartic is audited on its derivative roots. A hidden
  fold or shaft-speed excursion aborts. Contact remains terminal, and only
  the pre-contact interval is audited. v1 still publishes no
  `model_domain_exit` sample.
- The represented scaled mass pivot must resolve. Analytical positivity is
  not authorization. The residual test has no 1 Nm floor.
- `report_json` contains the exact canonical sealed request, and
  `input_sha256` recomputes from that object. Polar provenance metadata is
  inside the seal.
- `battery.discharge_efficiency` uses the PR-07 rule
  `0 < efficiency <= 1`.

## Review

Do not merge from this handoff. Exact-head Python 3.10 and 3.11 CI and the
later independent closure review are still required. CLA and third-party
source/license checkboxes stay manual.

## 2026-09-24 dense-root correction

The remaining blocker at `7d1cc584ca0cb26a808abf044c37855adbd64f60` was
companion-root classification of the RK45 derivative. Imaginary-part
tolerances are not an authorization rule. The audit now isolates real extrema
with an exact rational Sturm chain and a bounded bisection enclosure. A proven
domain exit is `CoupledDomainExit`. An unresolved bracket or an exhausted
isolation budget is `CoupledTransientFailure`. Neither returns a CMM-1
artifact. First contact still truncates the audited interval. No
`model_domain_exit` sample is emitted.

Represented mass pivots, standalone request provenance, and battery discharge
efficiency stay as closed at that previous head. PY-05 contact reconstruction
is unchanged.

## 2026-09-25 root-identity correction

The remaining blocker at `5de10863921001498a1a2d3488ad97e7046d79b0` was
closed-bracket gcd existence. A boundary-equal root at a bracket endpoint
authorized a different interior stationary root. Equality now requires that
unique interior root to be a root of the boundary-level polynomial. A
singleton is checked by exact evaluation. Unresolved identity is
`CoupledTransientFailure`. Proven exit remains `CoupledDomainExit`. Sturm
isolation and the value enclosure are unchanged.

## Next action

Keep PR #71 draft. PY-06D2 remains blocked without identifiable measurements.
