# Astra-B handoff: NACA0012 one-degree continuation

Review this separate stacked Draft against PR #109
`a83afb642001c17c58c660e12ce9f1d530b639ae` (tree
`bbcb687e9ebf914d17cbedf7e21e69ef7123c4b8`). The execution checkout was
`622ad1bcb8fd78eb47018f83a5f3827749a8c05d`, tree
`97fd628561a0f9e4f75f2bbfd1c8abf2a21d4d6a`; the first follow-up commit
`1c6e03863d4adb7e0b9d16f7c00663ca749a3008` has that exact tree. The next
commit records the outcome. No prior branch, adapter, admission rule, or
historical recipe changed.

The [frozen plan](../../decisions/xfoil-one-degree-continuation-v1/plan.json)
has SHA-256 `0e082cea4e485f664d259f669cd75f5f17615550553d984de4b41a854569d342`.
Its [manifest](../../decisions/xfoil-one-degree-continuation-v1/SHA256SUMS)
binds four request/script pairs, ordered by ascending Mach then Re.
The 250 mm / 7100 RPM baseline, catalog coordinate hash, geometry, condition,
provider and BEM policy identities come from the
[original control declaration](../../decisions/xfoil-cell00-iter160-v1/proposal.json).
The explicit blade-root declaration remains absent. Each new cold XFOIL 6.99
session has Ncrit 9, XTR 1/1, PANE, ITER 160 and a 90 s timeout. The only
numerical change relative to that control is interleaving 36 odd-degree
nodes into the exact 37 original radians, descending +32° through −40°.
No INIT, VACCEL, panel-setting change, retry, substitution, or fallback.

| Cell | Mach | Reynolds | Attempts | Retained outcome |
| --- | ---: | ---: | ---: | --- |
| 00 | 0.040507164718475736 | 26030.624179244653 | 1 | 68/73 usable; +29°, −25°, −38°, −39°, −40° unavailable |
| 01 | 0.040507164718475736 | 88107.31488200535 | 0 | NOT_LAUNCHED |
| 02 | 0.2649894145852458 | 26030.624179244653 | 0 | NOT_LAUNCHED |
| 03 | 0.2649894145852458 | 88107.31488200535 | 0 | NOT_LAUNCHED |

The invocation ran from 07:30:43.775869 to 07:30:50.957127 UTC. The native
call completed in about 5.34 s with exit 0, no timeout. Request/provider,
raw output, rounded header (Mach 0.041, Re 0.026 e 6), returned metadata,
and both executable observations bound successfully. The caller exited 1
because the result was incomplete and capture readiness was false. There
were zero BEM calls, no registration and no second experiment. At −38°,
iterations 156–160 in both ITER160 traces print rms `0.2767E-01`, max
`0.8838E-01` followed by a failure line. This is trace evidence, not a
saved coefficient, per-angle confidence or a new per-angle iteration field.

The [point ledger](../../decisions/xfoil-one-degree-continuation-v1/cell00-returned-points.csv)
retains all 73 statuses. The [comparison CSV](../../decisions/xfoil-one-degree-continuation-v1/cell00-shared-comparison.csv)
covers all 37 exact common radians and all three printed coefficients
against both older archives. One displayed increment means one unit of
the last common printed decimal; it is a descriptive category, not an
acceptance tolerance.

| Angle | ITER80 (Cl, Cd, Cm) | ITER160 (Cl, Cd, Cm) | 1° ITER160 (Cl, Cd, Cm) |
| --- | --- | --- | --- |
| +32° | Unavailable | 0.7272, 0.37300, −0.1061 | 0.7272, 0.37300, −0.1061 |
| +30° | 0.7050, 0.34561, −0.0930 | 0.7050, 0.34560, −0.0930 | 0.7050, 0.34560, −0.0930 |
| −8° | −0.6279, 0.07556, −0.0037 | −0.5698, 0.07908, −0.0008 | −0.5811, 0.07838, −0.0015 |
| −36° | −1.1466, 0.38372, 0.1772 | −1.1466, 0.38372, 0.1772 | −1.1466, 0.38373, 0.1772 |
| −37° | Not requested | Not requested | −1.1619, 0.38854, 0.1869 |
| −38° | Unavailable | Unavailable | Unavailable |
| −39° | Not requested | Not requested | Unavailable |
| −40° | −0.7740, 0.48435, 0.1578 | −0.7740, 0.48435, 0.1578 | Unavailable |

Of the 111 coefficient comparisons per history, versus ITER160 there
are 84 unchanged, 8 one-increment, 13 larger and 6 unavailable; versus
ITER80 there are 80 unchanged, 9 one-increment, 13 larger and 9 unavailable.
The largest shared absolute changes versus either history occur at +8°
for Cl (−0.1467) and Cd (+0.00476), and at +10° for Cm (+0.0059).
These are solution-path differences in the recorded runs. The ITER80
comparison also changes iteration budget. This neither measures physical
hysteresis nor establishes impossibility for the correlated potential
query image. Conditional initial BEM queries remain distinct; actual
genuine BEM queries are unavailable.

Owner-relayed raw evidence: `PyFoldable_XFOIL_One_Degree_Continuation_2026-11-07.tar.gz`,
SHA-256 `7cc5d67d9f265e10d27e203fb630e99c56ff4eb9d231b959fde5664fd1ab75e1`.
The [run summary](../../decisions/xfoil-one-degree-continuation-v1/RUN-SUMMARY.json)
binds the result, receipt, raw streams and analysis files. The archive has
67 checked payload digests, original capture files and all four frozen
requests, actual command, UTC times, launcher streams and status, build
records, runtime differences, and read-only comparison source. Original
ITER80 `e779bb00158571541a10419ecccb011fc1c8a5ea32cad40a59e005c59f9082e9`
and ITER160 `78de64539024d9b146400618f70dbdc3469e8b0be882f83553427aa6cd22c7e6`
archives were verified before and after execution. Measured Python, NumPy,
SciPy, platform and all ten resolved native library hashes match both
histories; Python path/bytecode settings differ as recorded. The binary
SHA-256 is `2b952bd21705d4d4147aa6b3e7db14f833a91dd9e1c9279261203f1cef1432ce`.
File observations do not attest a process image or physical applicability.

Review the exact interleaving, per-cell budget, binding and persistence gate
in the [separate caller](../../../pyfoldable/application/xfoil_one_degree_continuation.py).
If directory fsync were to fail after writing a readable per-cell outcome,
it would still stop the caller; a readable file is not the durability
acknowledgment. There was no such reported failure in this run. The
[focused tests](../../../tests/application/test_xfoil_one_degree_continuation.py)
passed with the admission/store regressions (64 total); separate automated
prelaunch review ran the 10 inert controls and found no blocking defect.
It independently checked the actual capture bindings and recomputed all
111 shared coefficient rows and all 73 point-ledger rows. That review is
not Astra-B approval. Ordinary Tests run on the pushed
`cursor/**` head; the stacked base has no main-target PR check.

Review this stopped experiment without launching it again. There is no
complete family and no older point repair, stitching or authorized follow-up.
Later acquisition, registration and fresh admission must preserve explicit
source-bound geometry and root declarations before an explicit genuine BEM
run. Five catalog profiles and the CAD/polar-upload-free UI are unchanged;
the APC 13-inch case is separate. Genuine single-case BEM and genuine
two-profile comparison remain **UNESTABLISHED**; `physical_qualification=false`.
