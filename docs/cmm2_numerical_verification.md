# CMM-2 PR-C numerical verification

Status: BLOCKED. This is not an accepted verification package.

The evidence writer records these identities separately:

- amended reviewed technical head:
  `b840ec55b4d1dd57197b97e91e1a48a7fbe7da0d`
- original reviewed provenance:
  `613072514f793f2a1bc65704f9158f536210707f`
- merged contract source:
  `64eea154f72365b647a1cff4d3fc768e45578d0c`
- `pr_source_head`: GitHub pull-request or push SHA when that event is present
- `git_rev_parse_head` and `evidence_checkout_head`: `git rev-parse HEAD`

`evidence_checkout_head` is the real checkout. It is not replaced by
`pr_source_head` when those SHAs differ. The same JSON records
`worktree_dirty`, `dirty_paths`, and the Python, NumPy, and SciPy versions.
The figures below belong to that run context. They are not the measurements
previously reported for head `370c1647ced896b6a79cff0870d985fc02874fa7`.

The case recording boundary covers setup, freeze, production/oracle calls,
and final assertions. An unexpected exception is recorded as FAIL with its
cause and all available partial metrics, then re-raised. Successful freeze
snapshots are retained even when a later row fails to freeze; such an incomplete
case reports PARTIALLY_FROZEN, never frozen_before_measurement. A failure before
any successful freeze reports NOT_FROZEN.

Premeasurement digests are fixed from the real system, controls, and case
inputs before any measurement. C2V-01 freezes all six count/load rows before
its first production acceleration. C2V-06 and C2V-07 freeze their actual
state/load/control inputs. C2V-08 freezes fold, speed, budget, and hard-failure
subcases separately, including each duration, state, actuation, load policy and
control override, and records their snapshots and combined digest. Its case
digest therefore represents all four subcases rather than only the fold run.
Shared C2V-03/C2V-05 execution retains distinct case-specific snapshots and
digests on both success and the cached failure path.

The following digest values describe the earlier writer format, retained as
historical measurement provenance; they do not identify the expanded snapshots.
Current digests must be read from the matching execution's evidence JSON. C2V-02, C2V-03, and C2V-05 below were
measured with this writer; their checkout is the `evidence_checkout_head` of
that evidence JSON, not a later documentation edit.

`critical_fixture_manifest_sha256`:
`265d531f51f08d45139313cd81b0239de0c2e9dd8926e12ded66d2011d83c1f7`.

Premeasurement digests from the real inputs, fixed from the earlier writer:

- C2V-02: `8e2cf00c546a2b9fdcf7678670fb2c305aa66d37407abd1255a5533629dbfbf3`
- C2V-03: `842213980ff41e1a91bde91c9a9386e7e9a0fb57852cdd5d49ccfadac75fedaf`
- C2V-05: `affa3dc34528cd95a697723ac2967fb5e4ab70cd3cac555e5ea35184e29dc293`

The manifest is hashed at import, before measurement. Case fixture digests
include the inputs passed to that case. Production equations and production
behavior are unchanged. ADR-009 is not created and is not accepted.
`physical_qualification` remains false. PR #81 stays draft and is not merged.

## Coverage

| Case | Coverage | Classification |
| --- | --- | --- |
| C2V-01 | MEASURED | PASS |
| C2V-02 | MEASURED | FAIL |
| C2V-03 | MEASURED | FAIL |
| C2V-04 | MEASURED | PASS |
| C2V-05 | MEASURED | FAIL |
| C2V-06 | MEASURED | PASS |
| C2V-07 | MEASURED | PASS |
| C2V-08 | MEASURED | PASS |
| C2V-09 | NOT_MEASURED | none |
| C2V-10 | NOT_MEASURED | none |
| C2V-11 | NOT_MEASURED | none |
| C2V-12 | NOT_MEASURED | none |

C2V-09 through C2V-12 were not executed. They are not PASS and they are not
CHARACTERIZATION ONLY.

## C2V-02

Ordinary Q2 passed on the relative branch (`q2_pass` true). The analytic
bridge is recorded separately and also passed:

- `B_assembly` = `6.189916701000075e-13 rad/s^2`
- `B_solve` = `1.0883784195041056e-27 rad/s^2`
- `E_analytic` = `6.189916701000075e-13 rad/s^2`
- `E_analytic <= B_assembly + B_solve`

The short trajectory remains a separate gate. It failed. At
`t = 0.017695437355687033` s the hinge-rate absolute error is
`1.360980699749481e-8 rad/s`. The reference rate is zero, so
`S = 1.0e-8 rad/s` and `e = 1.3609806997494809`. Duration `0.02` s, the
frozen controls, and `max e_j <= 1` were not changed. Case classification:
FAIL.

## C2V-03 and C2V-05

Both records were written. C2V-03's failure did not drop C2V-05.

DOP853 A/B stabilization passed and is not treated as a whole-case pass:

- `max_abs_A_minus_B_over_S` = `0.0010267375746728096`, limit `0.1`
- `max_abs_A_minus_B_over_0_1_S` = `0.010267375746728096`, limit `1`

Production versus Reference B failed. At `t = 0.04988983484797112` s the
hinge-rate absolute error is `3.802853771554121e-8 rad/s`,
`S = 1.5436421493564893e-08 rad/s`, and `e = 2.46355916955199`.
C2V-03 and C2V-05 are both FAIL.

## Other measured cases

C2V-01, C2V-04, C2V-06, C2V-07, and C2V-08 passed their existing gates.
Those passes are not PR-C acceptance and do not accept ADR-009.

## Harness closure regressions

Regression baselines first pass complete valid inputs, then drift only the
specified field. They verify that the field is named and production is not
called. Real C2V-01/02/04/06/07 and the first C2V-08 freeze are fault-injected
at setup/freeze entry, with FAIL retained in written JSON. Separate regressions
cover all six algebra rows, all four fail-closed subcase snapshots, partial
freeze status, and C2V-03/C2V-05 snapshot/digest identity on shared failure.

This repair changes recording and input validation only. The normative contract,
production code, fixtures, controls, Q2, analytic bridge and DOP853 oracle remain
unchanged. C2V-02/C2V-03/C2V-05 trajectory gates remain actual pytest failures;
no xfail, skip or acceptance promotion is introduced. C2V-09 through C2V-12
remain unmeasured.
