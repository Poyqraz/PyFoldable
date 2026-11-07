<!-- SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0 -->
# Astra-B handoff: stopped startup/history diagnostic, 2026-11-07

## Decision and immutable lineage

The authorized `xfoil_naca0012_startup_history_repeatability_v1` completed its
first whole-process script, then stopped: **P1 12/13 usable, +6° unavailable**.
P2/N1/N2 were not launched. One native process, one attempt, no retry, zero BEM.
This is a separate Draft stacked on PR #110 HEAD
`ccf91375221a9a31c51bf83b5c579858f9a23927`, tree
`10336a520f5a19e06fb31255ce3ebbcab77d4836`; previous branches remain unchanged.
Main was rechecked at `022b466303c59b8c0adb02f935f9c2f065b0e2b5`.

Executed source tree `d09094e1c23694d24371f399c6e4d04877489824` is retained at
published prelaunch commit `6c816e5aa77d279d19b2370140b16df25b74ebe2`
(local execution commit `b7aecd4306a9a6beaaf892f5db9ed8e21106a254`).
Caller SHA-256: `be1c1722dfcac4db34ed1e013cb4704546bd5d8aaed4c169e0069844ddaea310`.
The final documentation/evidence commit and exact-head CI are recorded in the
Draft PR body; they are not a claim that a different caller was executed.

## Frozen protocol and actual execution

[Plan](../../decisions/xfoil-startup-history-v1/plan.json) SHA-256:
`1321b28508a34ebfab7cd97acdae695dbe3b4a8f594e168fb0c62e566c29b153`.
The exact retained one-degree radians, including positive zero, are reused.
P1/P2 have identical scientific request bytes; N1/N2 likewise. Invocation
identities and destinations are separate, without artificial scientific changes.

| Invocation | Declared sequence | Attempts | Actual outcome |
| --- | --- | --- | --- |
| P1 | 0°, +1°, …, +12° | 1 | FAILED completeness: 12/13, +6° unavailable |
| P2 | Exact scientific replicate of P1 | 0 | NOT_LAUNCHED after P1 |
| N1 | 0°, −1°, …, −12° | 0 | NOT_LAUNCHED after P1 |
| N2 | Exact scientific replicate of N1 | 0 | NOT_LAUNCHED after P1 |

NACA0012, Re `26030.624179244653`, Mach `0.040507164718475736`, ITER160,
Ncrit9, XTR1/1 and PANE are unchanged. Each declared process had a 90 s timeout;
the absolute ceiling was four calls. No INIT/VACCEL/panel-setting change,
replacement attempt, banner call or model change. The retained binary SHA-256 is
`2b952bd21705d4d4147aa6b3e7db14f833a91dd9e1c9279261203f1cef1432ce`.

Actual wrapper UTC interval: `2026-11-07T13:45:48.397848+00:00` to
`2026-11-07T13:45:49.546408+00:00`. Native P1 exit 0, elapsed
`0.39232360599999083` s, no timeout; caller exit 1. Request, header, metadata,
provider, capture, executable and per-invocation event bindings passed.
Completeness failed **after the whole script**, preventing P2. Stdout line 2104
reports `VISCAL: Convergence failed` at +6° after iteration 160. Intermediate
printed coefficients there are not usable polar coefficients. Stderr retains an
`IEEE_DIVIDE_BY_ZERO` notice. Per-point confidence/iteration metadata remain
unavailable; the raw trace is a separate observation.

## Fresh-process evidence and its limits

The reviewed adapter/capture implementation and all historical callers are
unchanged. The small new caller uses a verified CPython audit-hook registration
handshake and checks each pre-spawn event against its invocation, request,
pinned argv, executable bytes and airfoil input receipt. The fresh temporary
working directory contained only the expected airfoil file, no default/solution
files. Pinned XFOIL source inspection records startup INIT and relative
`xfoil.def` lookup; this internal initialization is not an added menu INIT.

A pre-spawn event alone is intent, not proof of a started process. Here it is
paired with the reviewed direct call and completed native capture. File hashes
before/after are not process-image attestation. Runtime records retain CPython
3.12.14, NumPy 2.3.5, SciPy 1.17.0, Linux 6.18.57/glibc 2.41 and resolved library
hashes. Measured interpreter/package/platform/native-library identities match
the three earlier runs; the worktree/PYTHONPATH changed. This does not isolate
every possible causal variable.

## Shared observations, not a replacement family

Each triple below is **(Cl, Cd, Cm)** from the retained printed polar.

| Angle | ITER80 descending 2° | ITER160 descending 2° | Descending 1° | New diagnostic |
| --- | --- | --- | --- | --- |
| +6° | (0.6416, 0.04919, −0.0134) | same | (0.5261, 0.04835, −0.0113) | P1 unavailable |
| +8° | (0.5951, 0.07753, 0.0023) | same | (0.4484, 0.08229, −0.0007) | P1 (0.5703, 0.07907, 0.0008) |
| +10° | (0.4140, 0.11602, −0.0182) | same | (0.3505, 0.11929, −0.0123) | P1 (0.3505, 0.11930, −0.0123) |
| −6° | (−0.6416, 0.04920, 0.0134) | same | same | N1/N2 NOT_LAUNCHED |
| −8° | (−0.6279, 0.07556, −0.0037) | (−0.5698, 0.07908, −0.0008) | (−0.5811, 0.07838, −0.0015) | N1/N2 NOT_LAUNCHED |
| −10° | (−0.4131, 0.11601, 0.0181) | same | same | N1/N2 NOT_LAUNCHED |

[Full comparison](../../decisions/xfoil-startup-history-v1/history-comparison.csv)
has 81 coefficient entries. Against each old 2° sweep: 12 unchanged, 6 larger
than one displayed increment, 3 unavailable. Against the 1° sweep: 21 unchanged,
3 one-increment differences, 12 larger differences, 3 unavailable. Displayed
increments describe output precision, not an invented acceptance tolerance.
For example +8° versus the 1° sweep changes Cl by +0.1219, Cd by −0.00322 and
Cm by +0.0015. +10° differs only in Cd by +0.00001.

**Startup/traversal-history sensitivity remains in these numerical observations.**
Startup and traversal history changed together; no physical hysteresis or unique
causal mechanism is established. **Within-protocol agreement or disagreement is
UNASSESSED:** neither pair exists, so exact coefficient/byte and printed-precision
replicate comparisons cannot be performed. The explicit
[replicate assessment](../../decisions/xfoil-startup-history-v1/replicate-assessment.json)
retains both unavailable pairs. No symmetry substitution or stitching occurs.
The ±12° diagnostic does not satisfy the baseline −40°…+32° family or conditional
first BEM query. Historical 35/37, 36/37 and 68/73 records are untouched.

## Retained evidence and checks

[Run summary](../../decisions/xfoil-startup-history-v1/RUN-SUMMARY.json) and
[52-slot ledger](../../decisions/xfoil-startup-history-v1/diagnostic-points.csv)
are exact copies of derived files in the owner-relayed raw archive:
`PyFoldable_XFOIL_Startup_History_2026-11-07.tar.gz` (82,927 bytes), SHA-256
`592bc73eb29fe0077f3751e502e0a56590ff8cc6cdb6690b56bb2ada8b458112`.
It contains 66 individually hashed payloads: exact invocation, frozen requests,
scripts, source/runtime checks, streams, raw polar, outcomes, capture receipts,
comparison source/results and explicit unlaunched records. Missing values stay
null/unavailable. Original archives were rehashed before and after:

- ITER80: `e779bb00158571541a10419ecccb011fc1c8a5ea32cad40a59e005c59f9082e9`.
- ITER160: `78de64539024d9b146400618f70dbdc3469e8b0be882f83553427aa6cd22c7e6`.
- One-degree: `7cc5d67d9f265e10d27e203fb630e99c56ff4eb9d231b959fde5664fd1ab75e1`.

TDD includes missing-caller RED, audit-hook silent-refusal RED and three
pre-spawn attribution RED cases, repaired before launch. **22 new inert tests**
cover ordering, four-call ceiling, identical replicate requests, first-call
incompleteness, exceptions, timeouts, persistence failures and own-launch
attribution. The focused caller/predecessor/application set passed **59 tests**.
Separate automated prelaunch review checked the final source hashes and 22
inert tests, including actual CPython observer refusal/registration behavior
without a solver. Additional post-run automated review was unavailable because
that reviewer reached its usage limit. Neither is Astra-B approval.

Only ordinary exact-head push Tests is applicable on the new `cursor/**` branch.
The stacked target is not main, so there is no main-target PR merge-result job.
Final job URLs/results and final GitHub feedback check belong in the PR body.
No qualification/reproducibility dispatch, provider rerun or BEM test was added.

Review focus: frozen-node/request identity; own-launch and stop-before-next-call
binding; raw +6° absence; comparison categories; absence of any replicate pair.
No production family admission, new UI/store, root/hinge choice or optimization.
The 250 mm / 7100 RPM baseline, five profiles, no CAD/polar-upload user route,
explicit root declaration and longer-proximal intent remain; APC 13-inch stays
separate. Genuine single-case BEM and two-profile comparison **UNESTABLISHED**;
`physical_qualification=false`. No merge.
