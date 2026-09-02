# PY-04A / PR-11A — deterministic design search

## Scope and retrospective — 2026-09-02

Build on merged PY-03 (PR #51, main `100636d`), without repeating the existing
`design_sweep.py` reference-scaled sweep. The new adapter evaluates **the current
draft with the uploaded, coordinate-matched polars and the existing BEM kernel**.
No solver replacement, new dependency, polar generation or proxy substitution.

The independent PY-01–03 retrospective passed 116 targeted tests and identified
two numerical edge cases. Regression tests first reproduced overflowing derived
sound speed (incorrectly allowing zero Mach) and underflowing rotor normalization
(an uncaught division error). Preparation now rejects nonfinite sound-speed
arithmetic; expected arithmetic failures become controlled analysis failures
without partial rotor totals.

## First algorithm and acceptance

`finite_grid_minimize_v1` enumerates an explicitly finite Cartesian grid in
canonical axis/value order. It minimizes a finite scalar among **observed,
known-feasible grid points only**. Ties choose the first canonical point.
It makes no continuous/global-optimum claim; failed evaluations may hide better
points. Every attempted point has one ledger row, even on expected failure.

The [official SciPy brute-force documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.brute.html)
motivates guarding Cartesian-grid growth and distinguishing grid evaluation from
subsequent polishing. This implementation uses serial `itertools.product`, not
SciPy's optimizer or its default polishing step, to retain an explicit ledger and
reject over-budget grids **before any callback**. No stochastic operations are
used; reports explicitly record `random_seed=null`.

| Contract | Generic engine | Active-draft BEM adapter |
| --- | --- | --- |
| Variables | 1–4 named axes; 1–9 unique finite points each | Chord and twist multipliers, both 0.5–1.5 |
| Budget | Complete grid fits declared budget, at most 81 points | At most 25 points, 40 annuli each, 400 annuli total |
| Objective | Explicit callback scalar, minimized | Shaft power, with user-declared minimum thrust |
| Unknown constraint | `null`; cannot select candidate | Physical validation and structural evidence always unknown |
| Expected failure | Null objective, error text, no penalty score | No partial rotor totals or fallback polar |
| Unexpected failure | Programming errors/cancellation propagate | No partially completed search report |

The adapter reloads the **same baseline** for every candidate. Chord and twist
changes never compound. Diameter, hub, hinge, profile coordinates, RPM and first
operating condition remain fixed. Candidate TOML is round-tripped through the
existing strict SI parser before analysis. Only PY-03's fully-open supported
domain is accepted. No target-fitting or implicit 85% thrust-retention threshold.

Statuses are numerical evaluation states, not evidence classes:

- `failed`: expected evaluation or output-validation failure.
- `infeasible`: at least one declared constraint is false.
- `blocked`: no false constraints, but at least one is unknown.
- `feasible`: all declared constraints passed; still **not physically qualified**.

The stowed-geometry check is only the existing necessary planar centerline bound.
An impossible declared envelope may set it false; satisfying the bound leaves it
unknown because surface clearance is not proven. Missing/invalid requirements or
unsupported hinge elevation also leave it unknown. The existing 140 mm conflict
is not relaxed. Since physical/structural evidence is missing, the active adapter
never recommends a candidate: `best_candidate=null`, `physical_qualification=false`.

## API, provenance and UI

`design_search.py` supplies `SearchAxis`, `GridSearchPlan`, `Evaluation`,
`EvaluationFailure` and `run_grid_search`. `active_design_search.py` supplies
`prepare_active_search` and `run_active_search` around a current `PolarRunRequest`.
Preparation validates budgets and identities without running BEM; execution
rebuilds and compares the prepared request before evaluating anything.

Reports store exact baseline TOML, raw uploaded polar JSON and base runtime/source
context once. Each successful row retains its exact candidate TOML/hash, full
annulus/rotor output and analysis request/report hashes. The search plan, algorithm,
source-file hashes and geometry constraint reasoning are retained. Generic caller
identity is explicitly unauthenticated. SHA identifies content, not physical truth;
source hashes reflect disk files, so restart the app after source changes.
Identity/details are bounded at 4 MiB/256 KiB respectively. No saved source file,
archived benchmark or evidence gate is rewritten.

The geometry page offers a separate explicit search button below validated polar
upload. UI factors are 0.8, 0.9, 1.0, 1.1, 1.2; defaults are a 3×3 grid. The existing
annulus setting applies, so excessive aggregate work disables the search with an
explanation. Changing inputs does not invoke BEM. Single-run and search results
have separate identities; ordinary rerenders preserve current results, while
changed/invalid inputs, removed uploads or a failed rerun remove stale downloads.
The UI shows per-candidate metrics/status, a constraint/error ledger and JSON
download, not a best-design banner.

## Verification and next boundary

TDD red stages were observed for the generic engine, active adapter, UI connection
and retrospective regressions. Independent review added regressions for malformed
prepared plans and unsupported hinge orientation. Coverage includes an analytic
quadratic minimum, tie order, budgets before callbacks, all-failed/unknown cases,
noncompounding station changes, strict polar identity, exact report hashes, real
BEM calls with explicitly synthetic test polars, and Streamlit state invalidation.

Final local verification: **1063 passed, 9 skipped** (full `tests/`, Python 3.12),
including 73 added tests. The independent final reviewer passed 188 targeted
application/UI tests and found no remaining blocker after corrections. Syntax
compilation and whitespace checks passed; a launched Streamlit process returned
HTTP 200 `ok` on its health endpoint. UI behavior was checked with AppTest, not a
claim of manual visual inspection. CI on Python 3.10/3.11 and the final GitHub
review check remain required before merge.

This completes the first bounded PY-04A/PR-11A software slice, **not all robust
optimization work**. Broader variables, adaptive/stochastic methods and Pareto
search are deferred; PR-11B physical recommendations remain gated on real evidence.
Next ordered slice: PY-05 mechanism transient contracts and synthetic limiting
cases, reusing the existing dynamics and keeping PR #3 separate. Confirm coordinate
signs, explicit mass/CG/inertia/friction, RPM history and stop-event policy before
implementation; do not invent missing material data or claim passive closure.
Print orientation/manufacturing DoE remains outside this workstream.
