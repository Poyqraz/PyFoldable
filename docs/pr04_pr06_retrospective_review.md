# PR-04–PR-06 retrospective review and PR-06C gate

## Scope and method

This review covers the repository history from PR #4 through PR #28, the promoted
real-polar evidence, PR-06A/06B equations and integration contracts, the available
propeller data, and the license-change branch proposed in PR #26. It was performed
before freezing the PR-06C benchmark result.

Evidence reviewed:

- Git commits from the canonical SI model through radial BEM integration;
- PR descriptions and all GitHub review submissions/inline threads for PRs #4–#28;
- the full test suite and promoted XFOIL/NeuralFoil fixture chain;
- QPROP's velocity/circulation/load formulation and Ning's bracketed BEM method;
- APC's own description of its performance files;
- UIUC Volume 1 geometry and wind-tunnel coefficient files for APC SF 10x4.7;
- root license, package metadata, Git author history, and third-party data scope.

No submitted GitHub review or inline review thread existed for PRs #4–#28 at the time
of this review. Automated tests and evidence bundles are extensive, but they are not a
substitute for independent aerodynamic or legal review.

## Historical maturity review

| Layer | Delivered foundation | Retrospective assessment | Remaining gate |
| --- | --- | --- | --- |
| PR-04 configuration/geometry | SI boundary, strict airfoil parsing, polar table interpolation | Strong fail-closed contracts; source hashes and bounds policy prevent silent input drift | Imported geometry/data rights still require explicit provenance |
| PR-04 providers/cache/orchestration | XFOIL/NeuralFoil adapters, typed errors, deterministic cache, coalescing, health/circuit breaker | Strong software reliability and negative-path coverage | Provider agreement is not rotor accuracy |
| PR-04H acceptance | Versioned golden fixture, coefficient/coverage gates, non-gating timing | Correctly separates deterministic regression from performance telemetry | The original golden data was adapter evidence, not a propeller experiment |
| PR-05 family integration | Complete/partial grid policies, runtime config, section consumer | Complete-axis and rejection policies prevent sparse/interpolated ambiguity | Blade-level airfoil changes remain unsupported in PR-06B |
| PR-05E real qualification | Pinned XFOIL 6.99 build, NeuralFoil 0.3.3, repeat capture, semantic comparison, promotion record | Strong reproducibility chain; the XFOIL append EOF incident was diagnosed and fixed with preserved failure evidence | NACA 0012 at one Re/Mach envelope is not representative of APC SF 10x4.7 spanwise aerodynamics |
| PR-06A annulus | QPROP flow-angle parameterization, typed convergence/domain failures, residual and loss evidence | Equations and numerical residual gate remain sound in the declared positive-loading branch | Locally unloaded/negative-loaded annuli are outside the branch |
| PR-06B rotor | Midpoint integration, explicit radial domain, rotor coefficients, per-annulus provenance | Numerical integration is traceable and convergent; no partial totals are returned | Whole-rotor physical qualification and broader forward-flight branch were absent |

## Findings and dispositions

| Severity | Finding | Evidence | Disposition |
| --- | --- | --- | --- |
| High | The repository APC 202602 table could be mistaken for experiment. | APC states that its performance files are produced by proprietary vortex analysis using actual geometry. | Metadata now marks it `manufacturer_vortex_model_prediction`, `experimental=false`; PR-06C uses UIUC measurements. |
| High | PR-06B had no measured whole-rotor accuracy gate. | Prior tests covered equations, convergence, totals, and a real polar consumer only. | A frozen 60-point UIUC fixture, 50-point propulsive envelope, policy, runner, JSON/Markdown report, and regression were added. |
| High | Positive total thrust does not imply every annulus has positive loading. | 27 of 50 propulsive benchmark points fail when an inner annulus has no positive-loading solution. | Failure is retained by point/type; coverage is 46%, below 95%; PR-06D is blocked. |
| High | The tested APC blade's exact spanwise polar family is unavailable in-repo. | APC says its dominant shapes are only *similar* to NACA 4412/Clark-Y and may vary with span. | The analytic proxy is labeled non-qualifying; the representative-polar gate fails regardless of coefficient fit. |
| Medium | UIUC coefficient files do not encode run-specific atmosphere. | The downloaded files contain RPM/J/CT/CP/eta, not tunnel density, viscosity, temperature, or pressure. | Standard atmosphere is declared as a modeling assumption and included in fixture/report provenance. |
| Medium | Geometry is approximate and starts at r/R=0.15. | UIUC Volume 1 identifies some geometry as approximate digitization. | Default `station_span` is retained; hub/tip geometry is not invented. |
| Medium | Loss-model choice was unqualified. | PR-06B left root loss opt-in pending benchmark selection. | Baseline, root-loss, no-loss, low-drag, and higher-camber variants are reported; none bypasses coverage/polar gates. |
| Medium | Review independence is limited. | GitHub reports no review submissions or inline threads for PRs #4–#28. | This retrospective is recorded, but future physical promotion should require an independent aerodynamic reviewer. |

## Frozen PR-06C result

The benchmark uses UIUC Volume 1 version 3 wind-tunnel measurements and approximate
digitized geometry for APC Slow Flyer 10x4.7. All negative-thrust/windmilling rows are
kept in the raw fixture but excluded from the declared positive-thrust qualification
envelope because PR-06A explicitly rejects windmilling.

| Gate | Result | Observation | Policy |
| --- | --- | ---: | ---: |
| Solution coverage | Fail | 23/50 = 46.0% | ≥95% |
| CT WMAPE on solved points | Pass | 14.73% | ≤15% |
| CP WMAPE on solved points | Pass | 14.13% | ≤20% |
| CT normalized bias | Fail | −14.73% | ±10% |
| CP normalized bias | Pass | −14.13% | ±15% |
| Maximum 80→160 annulus delta | Pass | 0.0213% | ≤0.5% |
| Representative polar evidence | Fail | analytic proxy | required |
| Static / forward coverage | Pass / Fail | 100% / 20.6% | each ≥95% |
| Worst regime CT / CP WMAPE | Fail / Fail | 22.99% / 20.35% | ≤15% / ≤20% |

Coefficient-error gates are diagnostic on the solved subset. They cannot override low
coverage or nonrepresentative aerodynamic inputs. The correct conclusion is therefore:

> PR-06B passes its code and numerical-integration gate, but the current rotor model is
> not physically qualified for the declared APC forward-flight envelope. PR-06D remains
> blocked.

The complete evidence is in
[`reports/pr06c_fixed_propeller_benchmark.json`](../reports/pr06c_fixed_propeller_benchmark.json)
and its human-readable
[`Markdown summary`](../reports/pr06c_fixed_propeller_benchmark.md).

## License review

The proposed PolyForm Noncommercial license can cover first-party Project material
controlled by the owner. It cannot relicense APC/UIUC data or external solver software.
Activation therefore includes:

- official PolyForm Noncommercial 1.0.0 text and a required copyright notice;
- PEP 639/SPDX package metadata and a 0.3.0 version boundary;
- explicit third-party notices and data evidence classes;
- a contributor license agreement that preserves contributor copyright while granting
  the Project commercial and sublicensing rights;
- a prospective-license statement preserving Apache-2.0 rights already granted for
  earlier copies.

See [`docs/licensing.md`](licensing.md) for the full engineering scope review. Legal
counsel should review the commercial agreement before a material transaction.

## Required next increment

PR-06D must not start until a PR-06C remediation increment:

1. implements and reviews a branch that permits locally unloaded/negative-loaded
   annuli within an overall propulsive rotor solution;
2. supplies a span-representative, Reynolds-aware polar family with source/version
   evidence instead of tuning the analytic proxy to the target coefficients;
3. reruns the frozen fixture and unchanged policy;
4. obtains independent aerodynamic review before physical promotion.

Primary references:

- Mark Drela, [QPROP formulation](https://web.mit.edu/drela/Public/web/qprop/qprop_theory.pdf)
- Andrew Ning, [A Simple Solution Method for the Blade Element Momentum Equations with Guaranteed Convergence](https://scholarsarchive.byu.edu/facpub/1673/)
- [UIUC Propeller Database](https://m-selig.ae.illinois.edu/props/propDB.html)
- [UIUC Volume 1](https://m-selig.ae.illinois.edu/props/volume-1/propDB-volume-1.html)
- [APC performance-data description](https://www.apcprop.com/technical-information/performance-data/)
- [APC engineering/airfoil description](https://www.apcprop.com/technical-information/engineering/)
- [PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0)
