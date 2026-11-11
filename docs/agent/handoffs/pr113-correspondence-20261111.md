# Astra-B handoff: PR #113 deterministic restoration correspondence

Goal: close the remaining saved-result correspondence finding before the Claude
integration handoff. Keep PR #113 Draft/open/unmerged; do not start DUST.

## Identity and scope

Requested baseline: `9ab4a685432ca9358603789481b171d2c0c536e6`.
The live branch had legitimately advanced to direct child
`9bab1be651323b0ad22e5498782217371e51cdf4`, tree
`78503437ba92ece2bee05db35a9261c6ffff4087`; work continues from that implementation.
Branch: `cursor/astra-a-research-release-20261111`; base #112 remains
`d86ce3b2cd790ff37c8d5e806959352c86aa505d`.
The delivery evidence records the final publication SHA/tree and exact-head CI;
this handoff does not claim to contain its own future commit identity.

The existing increment shares the exact effective-coefficient force projection
between BEM and restoration. It binds retained differential thrust/torque to
section state, retains annulus integration, rotor totals, coefficients and shaft
power checks. PY-05 shares pure drive, torque, sample-output and accumulated-output
arithmetic. Restoration checks drive derivative and applied hinge moment,
algebraically derived channels, and trapezoidal accumulated work/dissipation.
Ordinary knots use the outgoing segment; terminal first contact uses the segment
that reached the stop, including contact exactly at a knot.

The follow-up changes only restoration's effective-energy rounding allowance and
its tests/documentation. Near the open pose, subtraction in `1-cos(theta)` can
amplify a neighboring libm cosine result by millions of energy ULPs. Propagating
four cosine ULPs through `m*r_h*c_g*omega**2` bounds that arithmetic difference.
Other channels retain the original output-ULP gates. Equations, physical
assumptions, ODE integration, force model and output quadrature are unchanged.

## Counterexamples and valid boundaries

The baseline validator was replayed against the current fully resealed witnesses:

| Witness (dependent values and all enclosing hashes resealed) | 9ab4a685 | Final implementation |
| --- | --- | --- |
| Differential thrust + annular/rotor loads, coefficients, efficiency | accepted | rejected |
| Differential torque + annular/rotor loads, shaft power, coefficients, efficiency | accepted | rejected |
| Zero ramp derivative + Euler torque and acceleration | accepted | rejected |
| Altered applied hinge torque + applied power, accumulated work, acceleration | accepted | rejected |
| Altered spring torque + acceleration | accepted | rejected |
| Altered accumulated viscous loss + total dissipated energy | accepted | rejected |

Valid completed/contact histories and knot-side cases pass. The wrong derivative
side at the knot rejects. Near-open energy tests at 0 and +/-1e-5 rad failed at
9bab1be, pass after the fix, and reject changes beyond the propagated allowance.
These are internal correspondence tests, not trajectory replay, authentication,
measurement validation or physical validation.

## Original exports and observed application behavior

The exact original UI downloads were copied from the owner's retained
`PyFoldable_PR113_WSL_Usability_2026-11-11.zip`, without re-solving:

| Export | Bytes | SHA-256 |
| --- | ---: | --- |
| NACA0012 | 466924 | `340ace35430caf1364b2da96f73cc3dbe447d3bbcb6128c20751eb2e1f60c32c` |
| NACA2412 | 452770 | `31ac57ba261c252d34cb1a2b66be1dd193594397372f1dff16999bb73f4b75ec` |

Both restored and re-exported byte-identically, retained all 40 radial rows, and
reproduced the original comparison assessment. Current defaults were changed to
7100 RPM; the store override named a nonexistent directory. Store construction,
repository lookup, XFOIL generation, BEM entry points and mechanism solve/sample
entry points were blocked: zero calls. Retained results remain 2400 RPM/14 m/s,
144–388 mm span; 33.421707752866034 N / 2.4880853705679464 N m /
625.3240577344399 W and 43.647174413635845 N / 3.277371908165304 N m /
823.6934007818944 W. Shaft powers differ.

The normal Streamlit entry point started and returned HTTP 200 for `/` and
`/_stcore/health`. Focused UI tests ran with the application suites. Approved
button styling and original numerical/provider evidence have no patch changes.

## Verification and review

- Focused WSL Python 3.12.3 run: 125 passed, including restoration, research
  design/reference, BEM, mechanism/service regressions and research UI tests.
- Baseline replay: six expected `DID NOT RAISE ValueError` failures, proving all
  six fully resealed contradictions were accepted. Current validator: six passed.
- Cancellation red/green: three expected baseline energy failures, then three
  passing boundary/regression cases after the fix.
- Full ordinary WSL suite: 2172 passed, 9 skipped, 37 subtests passed in
  284.67 seconds. Skips concern unavailable generated motor-coupled/foldable CSVs.
  Exact push-HEAD Python 3.10/3.11 CI is recorded in the delivery evidence's
  `exact-head-ci.json` and final SHA/tree manifest alongside `full.log`.
- Separate read-only automated reviewer inspected baseline..9bab1be and the final
  rounding patch/tests. No further concrete blocker. The reviewer did not run
  tests; execution outcomes above were checked by the implementing agent.
- Native Windows collection fails on the existing POSIX `os.O_DIRECTORY` store
  requirement; tests used WSL as documented. The RTK pytest wrapper also failed
  with Windows error 623; direct WSL execution avoids that wrapper.

Useful focused command from a configured Linux checkout:

```bash
python -m pytest tests/application/test_research_restore.py tests/application/test_research_design.py tests/application/test_research_reference_protocol.py tests/dynamics/test_mechanism_transient.py tests/dynamics/test_mechanism_transient_regressions.py tests/application/test_mechanism_transient_service.py tests/application/test_mechanism_transient_service_regressions.py tests/core/test_bem.py tests/core/test_bem_rotor.py tests/ui/test_research_release_ui.py -q -rs
python -m pytest tests/ -q -rs
python -m streamlit run apps/pyfoldable_research.py
```

## Receiving-agent action and limits

Astra-B: inspect the final SHA/tree, pure helper/model correspondence, resealed
counterexamples, original-export compatibility and exact-head CI in the delivery
bundle. Return an independent release assessment. Internal review is not Astra-B
approval. Claude integration/DUST work remains separate and has not started.

Reference agreement remains NOT_ASSESSED; joint loss NOT_MODELED;
physical_qualification=false. No new provider acquisition or engineering study,
no qualification/reproducibility workflow, no merge and no physical claim.
The historical 250 mm case and four other profiles remain numerically unresolved.

Changed follow-up paths: `pyfoldable/application/research_result_checks.py`,
`tests/application/test_research_restore.py`, `docs/research_application.md`,
`docs/agent/current-state.md`, and this handoff. The preceding 9bab1be increment
also changes `pyfoldable/core/bem.py`,
`pyfoldable/dynamics/mechanism_transient.py`, and
`tests/application/research_inert_support.py`.

The local Windows clone has an unrelated archived CSV newline-only dirty status
and untracked Serena setup; neither belongs in the patch. No other agent edits.
Rollback by reverting the specific follow-up commit, preserving 9bab1be; reverting
9bab1be reopens the six correspondence counterexamples. Keep all evidence intact.
