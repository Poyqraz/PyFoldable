# CMM-2 PR-C numerical verification

Status: BLOCKED. This is not an accepted verification package.

Exact implementation base: the branch created from
`f47968529eeb17e99c4ecb0072a82ca22e55bb80`.

Frozen contract technical head:
`613072514f793f2a1bc65704f9158f536210707f`.

The frozen contract file is unchanged. Production equations and production
behavior are unchanged. ADR-009 is not created and is not accepted.
`physical_qualification` remains false.

## What was executed

`tests/verification/test_cmm2_numerical_verification.py` builds the frozen
synthetic fixtures and compares them with test-owned arithmetic. It does not
import the CMM-1 verification module as an oracle.

Passed against the frozen rules:

- C2V-01 represented algebra, row backward error, factor-of-two forward bound,
  and mutant separation for `N > 1`
- C2V-04 instantaneous watt gate and quadrature reliability gate
- C2V-06 zero-hinge cross-model comparison within 1 ULP
- C2V-07 manufactured contact gates
- C2V-08 four distinct failure layers

## Blocker

The frozen trajectory rule `max e_j <= 1` is not met. Fixtures, controls, and
thresholds were not changed.

C2V-02 compares the short production trajectory with the exact constant state.
At `t = 0.017695437355687033` s the hinge-rate error is
`1.360980699749481e-8 rad/s`. The reference rate is exactly zero, so
`S = 1.0e-8 rad/s` and `e = 1.3609806997494809`. The Q2 acceleration check at
the initial equilibrium passes.

C2V-03 compares production RK45 with stabilized DOP853 Reference B. Reference
A/B stabilization ratio is `0.010267375746728096`, inside `0.1`. At
`t = 0.04988983484797112` s the hinge-rate absolute error is
`3.802853771554121e-8 rad/s` and `e = 2.46355916955199`. A single-state
acceleration comparison at the target matches the independent solve.

C2V-05, C2V-09, C2V-10, C2V-11, and C2V-12 were not accepted as evidence
because this gate failed first.

Classification: frozen acceptance gate not met. This is not a license to
retune the fixture or the tolerance.
