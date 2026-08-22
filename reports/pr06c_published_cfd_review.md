# PR-06C published CFD context review

## Decision

**PR-06C remains blocked.** Published results add independent model-form context,
but they are not an independent review of PyFoldable and do not replace the missing
representative polar chain or forward-flight validation.

## Exact APC Slow Flyer 10x4.7 static CP comparison

| rpm | model | cells | UIUC CP | published CFD CP | CFD error | PyFoldable proxy CP | proxy error |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 4319 | k-epsilon | 3,200,000 | 0.0474 | 0.0504 | +6.33% | 0.0426 | -10.22% |
| 4319 | k-omega | 3,200,000 | 0.0474 | 0.0486 | +2.53% | 0.0426 | -10.22% |
| 4319 | SST k-omega | 3,200,000 | 0.0474 | 0.0480 | +1.27% | 0.0426 | -10.22% |
| 6528 | k-epsilon | 3,200,000 | 0.0531 | 0.0536 | +0.94% | 0.0426 | -19.86% |
| 6528 | SST k-omega | 3,200,000 | 0.0531 | 0.0528 | -0.56% | 0.0426 | -19.86% |
| 6528 | k-epsilon | 7,000,000 | 0.0531 | 0.0525 | -1.13% | 0.0426 | -19.86% |

The strongest published static result is SST k-omega over two rpm values; its maximum
absolute error recomputed from the tabulated coefficients is
1.27%.
The existing analytic-proxy BEM path is materially worse at the same points, especially
at 6528 rpm. This supports prioritizing representative Reynolds-sensitive polars rather
than retuning the frozen acceptance thresholds.

## 5000 rpm ANSYS method sensitivity

Burak Sunan reports 2.020 N mean thrust with
0.23 N standard deviation across 14 selected
cases and 2.053 N from the periodic
half-domain check. Linear interpolation of the frozen UIUC CT data, converted with the
fixture's standard-atmosphere assumption, gives
4.353 N. The
53.6% gap is diagnostic,
not a validation statistic: CAD identity and run-specific atmospheric conditions are not
bound tightly enough.

## Evidence boundary

- Five primary publications were classified; nine tabulated numeric facts were retained.
- Figure-only FlowVision and oblique-flow results were not digitized.
- The APC 10x7 Fluent study is methodology-only because pitch/geometry do not match.
- No paper or figure is redistributed; only factual values, citations, and scope metadata
  are stored.
- `independent_project_review = false`; no PR-06C gate is changed.

## Primary sources

- [Numerical Study of Quad-Rotor Aircraft Performance under Adverse Situations](https://www.icas.org/icas_archive/ICAS2020/data/papers/ICAS2020_0482_paper.pdf) — Static single-rotor CP at 4319 and 6528 rpm; turbulence-model and y-plus comparison against UIUC experiment. Companion thesis DOI: 10.6846/TKU.2020.00377.
- [Computational Fluid Dynamics Analysis of a Quadrotor](https://hdl.handle.net/20.500.14719/1403) — 5000 rpm hover thrust sensitivity across domains, grids, boundary conditions, turbulence models, and a periodic half-domain check.
- [Computer Simulation of Propeller Aerodynamics in the Russian FlowVision Software Package](https://www.pressmk.ru/storage/pdf/RI_4_2024.pdf) — Thrust and power versus rpm compared graphically with experiment; wake pressure and acoustic spectrum.
- [A Simplified Model for Propeller Thrust in Oblique Flow](https://www.qeios.com/read/WG08LV) — APC Slow Flyer 10x4.7 oblique-flow experiment/model comparison; most conditions reported within 5 percent, with pure crossflow worst.
- [3D CFD Simulation and Experimental Validation of Small APC Slow Flyer Propeller Blade](https://www.mdpi.com/2226-4310/4/1/10) — APC Slow Flyer 10x7 methodology precedent; not target-geometry validation.
