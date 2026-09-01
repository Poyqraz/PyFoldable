# Python-first research and execution plan

## Decision — 2026-09-01

Extend main `c26867d`; preserve existing BEM, polar-provider, motor, mechanism and
evidence contracts. PR #3 remains separate. Per the user's explicit decision,
implement numerical work in Python wherever possible rather than requiring
MATLAB. This records the implementation choice, not a claim of MATLAB parity or
a rewrite of the historical proposal.

Print orientation, print-batch scheduling and manufacturing DoE are **outside
this software workstream**. Preserve existing optional manufacturing fields for
compatibility. Unknown material properties do not become qualified by omission.

## Research before implementation

SciSpace natural-language searches covered (1) low-Re propeller BEM and numerical
optimization, (2) passive tip-hinge loads/deployment and parameter identification,
and (3) Acar's 2025 jointed-tip topology. The third search did not retrieve the
target reliably: retain the repo's existing review, not an inference of absence.

Consensus searches were `small propeller blade element momentum low Reynolds
number optimization experimental validation` and `NeuralFoil XFOIL airfoil
surrogate Reynolds confidence aerodynamic optimization`. Three selected records
were fetched. Loureiro et al.'s record had no abstract and supplies no new
numerical claim here. SciSpace methodology extraction returned `not_found` for
Hoyos and the elastic-deployment paper. These are targeted searches, **not** a
systematic review or a claim to have read inaccessible full texts.

| Primary source / inspected material | Application | Limit |
| --- | --- | --- |
| [Drela, QPROP (2006)](https://web.mit.edu/drela/Public/web/qprop/qprop_theory.pdf), velocity/polar/load equations inspected | Retain existing induction/swirl BEM; local Re/Mach/alpha depend on blade-relative velocity | Nominal external velocity is not converged or trial-query velocity |
| [Giljarhus, pyBEMT (2020)](https://joss.theoj.org/papers/10.21105/joss.02480), journal record and official theory docs | Direct Python BEM/SciPy precedent | No solver replacement or code copying; not prototype qualification |
| [MacNeill & Verstraete (2017)](https://doi.org/10.1017/aer.2017.32), abstract from both services and publisher record | Section geometry, alpha/Re coverage and rotation effects matter at low advance ratio | Published accuracy does not transfer to our rotor; no correction enabled from abstract alone |
| [Hoyos et al. (2022)](https://doi.org/10.3390/aerospace9030153), SciSpace abstract and publication metadata; full text unavailable | Stage BEM/polars, constrained PSO and independent validation | Do not invent structural limits, correction constants or hyperparameters |
| [Sharpe & Hansman, NeuralFoil (2025)](https://arxiv.org/abs/2503.16323), fetched Consensus record and arXiv abstract | Reuse Python provider/confidence/domain contracts | Preprint record; matching XFOIL is not matching our experiment |
| [Mashin et al. (2024)](https://doi.org/10.1016/j.ast.2024.108926), SciSpace abstract | Deployment and thrust need separate evidence | Elastic-buckling blades are not our rigid tip hinge |
| [SciPy optimization](https://docs.scipy.org/doc/scipy/reference/optimize.html), [ODE integration](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html), official docs | Python supports optimization, calibration and event-aware integration | Test minimum supported versions; no silent new API requirement |

The literature supports architecture, not a best profile, realized 140 mm envelope,
85% thrust retention, passive closing, structural safety or qualified optimum.
No aerodynamic dataset was fabricated from paper abstracts.

## Ordered slices

| Slice | Scope | Acceptance |
| --- | --- | --- |
| PY-01 — this change | Active-draft preparation + explicit-polar BEM Python service | Exact TOML identity; nominal station Re/Mach/alpha; strict bounds; full output/provenance; UI preparation only |
| PY-02 — next | Five-profile coordinate/polar identity | NACA0012/2412/23012/4415/63-412; reuse coordinate parser/provider/cache; no 4-series substitution for 5/6-series; preview–solver identity tests |
| PY-03 | Validated polar bundle UI + active-draft BEM run | Explicit action; bounded work; input-change invalidation; no benchmark/proxy substitution or metadata-based qualification |
| PY-04 / PR-11A | Deterministic sweeps and optimizer infrastructure | Reuse PY-01 callback; one algorithm first; bounds, seeds, budgets, failure accounting, analytic tests; unknown constraints cannot pass |
| PY-05 | Mechanism transient infrastructure | Coordinates/signs, mass/CG/inertia/friction, RPM history and acceleration/deceleration, stop events; synthetic limiting cases; PR #3 separate |
| PY-06 | Calibration, uncertainty, comparison reports | Extend PR-07/09/10; distinguish shaft/hinge moments and electrical/shaft power; matched-diameter/conditions thrust ratio; target fitting is not validation |

PR-11B physically supported Pareto recommendations, structural safety and passive
deployment qualification still require real evidence. Keep 250/140 mm geometry
requirements, 7100 RPM and 0.85 thrust-ratio target. The 254 mm UIUC benchmark is
not the project's reference denominator. Print orientation is not an optimizer
variable or a blocking prerequisite in this plan.

## PY-01 API and scientific boundary

`prepare_design_analysis(draft)` accepts the existing `DesignDraftArtifact`,
rehashes and reparses exact TOML through the canonical SI loader. It uses only
the **first operating condition** and **declared open-blade stations**:

```text
U0 = hypot(V_infinity, omega * r)
Re0 = rho * U0 * chord / mu
Ma0 = U0 / sqrt(1.4 * 287.05 * temperature)
alpha0 = twist - atan2(V_infinity, omega * r)
```

No induction, spanwise interpolation or thrust is computed by preparation.
Station extrema do not bound the continuous span or the solver's trial queries.
Zero RPM and negative inflow are outside this slice. The open-blade preparation
is explicitly distinguished from a nonzero preview pose.

`run_design_analysis(draft, polar_families, settings=...)` requires explicit
`PolarFamily` data for the single station profile and delegates to existing
`solve_bem_rotor`, with `bounds="error"` and `radial_domain="station_span"`.
Only fully-open geometry with zero deployed/preview angles and zero axial and
tangential hinge offsets is accepted. Hinge-axis elevation is not set to zero.
Mixed spanwise profiles,
folded states and automatic provider execution are deferred. No fake root/tip
geometry, proxy fallback, clamping or partial totals. Budget: at most 256 annuli,
512 bracket samples and 300 local iterations.

Reports retain exact TOML, complete polar tables/metadata, hashes, condition,
service/BEM versions, solver settings, full annulus outputs and actual query
envelope. Python/NumPy/SciPy versions and the participating source-file hashes
are recorded too. Source hashes describe disk files at request time, not a signed
build; restart a long-lived process after code edits for reproducible execution.
Nested polar data are snapshotted before hashing/solving. SHA identifies
content; it does not authenticate external sources or establish physical truth.
Caller polars stay `caller_supplied_unqualified`; all results retain
`physical_qualification=false`. Synthetic test tables are never demo predictions.

The UI recomputes preparation from the current geometry-page draft. It performs
no BEM solve on widget changes. Unsupported conditions remove preparation and its
download, without preventing geometry preview or schema-valid draft export.
Validated polar upload and a new active-design run button belong to PY-03.

## TDD and review

Test-first checks cover units/velocity arithmetic/scaling, input-sensitive hashes,
no source writes, real-kernel power closure with explicit synthetic test polars,
missing/foreign/narrow polars, folded/unsupported states and provenance. UI tests
cover edited dimensions, no automatic BEM invocation and no stale download after
RPM is set to zero. Independent review checks domain and provenance boundaries.
No archived gate or benchmark result is modified by this work.

Local verification on 2026-09-01: **858 passed, 9 skipped** in the complete
`tests/` suite, including 34 new service tests and two new Streamlit regressions.
`compileall` succeeded. TDD red stages were observed before adding the service
and before connecting its UI. Independent review found no blocking issue in the
supported domain. Skipped tests remain skipped; no new physical evidence is claimed.

Example use from a Python workflow (no implicit polar generation):

```python
from pyfoldable.application.design_analysis import (
    prepare_design_analysis, run_design_analysis,
)
from pyfoldable.core import BEMRotorSettings

# draft is the existing build_design_draft(...) return value.
# families is an explicit {airfoil_id: PolarFamily} from the caller's data pipeline.
preparation = prepare_design_analysis(draft)
result = run_design_analysis(draft, families, settings=BEMRotorSettings(annulus_count=40))
print(result.report_json)
```
