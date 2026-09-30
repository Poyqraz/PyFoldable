# CMM-2 PR-C numerical verification

Status: BLOCKED. This is not an accepted verification package.

The evidence writer records four different identities:

- amended reviewed technical head:
  `b840ec55b4d1dd57197b97e91e1a48a7fbe7da0d`
- original reviewed provenance:
  `613072514f793f2a1bc65704f9158f536210707f`
- merged contract source:
  `64eea154f72365b647a1cff4d3fc768e45578d0c`
- `evidence_checkout_head`: the commit actually checked out when the evidence
  JSON is written

The figures in this file come from a local run of this evidence writer on
parent checkout `706586ee2ed85b868d5c22d48e6ff7b85dc8b792`. They are not the
measurements previously reported for head
`370c1647ced896b6a79cff0870d985fc02874fa7`. CI records its own
`evidence_checkout_head`.

`critical_fixture_manifest_sha256` for that run:
`265d531f51f08d45139313cd81b0239de0c2e9dd8926e12ded66d2011d83c1f7`.

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
