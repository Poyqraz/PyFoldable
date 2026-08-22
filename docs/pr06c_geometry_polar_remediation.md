# PR-06C manufacturer-geometry and polar remediation

## Decision

PR-06C remains blocked under the unchanged qualification policy. Manufacturer
geometry materially improves the result, but it does not supply representative
section polars and it does not bring the full or forward-flight CT error within the
frozen thresholds. PR-06D therefore does not start.

## Evidence boundary

APC's current `10x47SF-PERF.PE0` file identifies version `v2025-1001`, simulation
date `2026-02-24`, 51 geometry stations, two blades, and these section transitions:

| Radius | Section identity |
| ---: | --- |
| 4.90 in | E63 |
| 5.00 in | APC12 |

The observed file SHA-256 is
`f38bdb92f65053a7791a6ba492a89da69651f1a11983724953272211db5d39c8`.
The current manufacturer revision is not proven identical to the historical UIUC
wind-tunnel specimen. It is consequently a traceable geometry screen, not a statement
of specimen identity.

APC source terms do not establish redistribution permission for the downloaded file.
PyFoldable therefore does not vendor or silently download it. `parse_apc_pe0()` accepts
caller-supplied bytes, can require the pinned digest, and records URL/version/date/hash
provenance. The screening example requires an explicit local path. The former
normalized APC performance derivative was removed from the current distribution and
replaced by a clearly non-qualifying, first-party synthetic software fixture.

## Unchanged-policy screening result

The PE0 geometry was evaluated with the existing analytic polar proxy and the reviewed
`signed_nonreversed` loading branch. No threshold or reference point changed.

| Metric | Approximate UIUC geometry baseline | PE0 geometry screen | Policy | Gate |
| --- | ---: | ---: | ---: | --- |
| Solution coverage | 100% | 100% | ≥95% | Pass |
| CT WMAPE | 26.40% | 16.23% | ≤15% | Fail |
| CP WMAPE | 28.28% | 16.98% | ≤20% | Pass |
| CT normalized bias | −26.40% | −14.07% | ±10% | Fail |
| CP normalized bias | −28.28% | −13.42% | ±15% | Pass |
| Static CT / CP WMAPE | — | 6.05% / 6.47% | ≤15% / ≤20% | Pass / Pass |
| Forward CT / CP WMAPE | 40.31% / 38.35% | 25.68% / 23.19% | ≤15% / ≤20% | Fail / Fail |
| Maximum terminal radial delta | 0.0213% | 0.0453% | ≤0.5% | Pass |
| Representative polar evidence | No | No | Required | Fail |

The geometry correction explains a substantial part of the former bias. The remaining
failure is concentrated in forward flight and cannot be promoted by calibrating the
analytic proxy against the target coefficients.

## Implemented foundation

- strict, digest-aware APC PE0 local parser with dimensional validation;
- manufacturer-geometry injection into the frozen benchmark and radial convergence
  path, with diameter/blade-count identity checks;
- fail-closed spanwise polar schedule with coefficient blending, radial bounds policy,
  and combined source provenance;
- rotor integration support for a different local polar family at every annulus while
  retaining the original constant-airfoil API;
- synthetic parser/schedule regressions that distribute no APC content.
- complete root-search polar query envelopes (alpha, Reynolds, Mach, source,
  interpolation and clamp state) aggregated to each rotor result;
- typed, fail-closed representative-polar evidence tied to exact coordinate/provider,
  operating-condition, query-count and reviewed promotion identities;
- an opt-in Snel-1993 rotational-lift correction with default exact no-op behavior,
  published-formula regression, explicit domain failure and annulus provenance.

The approximate-geometry proxy ablation changed overall CT/CP WMAPE from
26.40%/28.28% to 25.81%/27.83%. Static CT/CP improved to 10.00%/9.91%, while
forward CT/CP remained 40.47%/38.44%. Therefore the correction is retained as a
reviewable model component, not promoted as the PR-06C solution.

## Remaining critical path

1. Obtain an E63 coordinate/polar evidence chain under terms suitable for the intended
   use, then qualify Reynolds/Mach/angle coverage for the actual annulus query envelope.
2. Represent the short E63-to-APC12/NACA-4412 tip transition with the spanwise schedule;
   reject or visibly clamp every unsupported query.
3. Rerun the unchanged UIUC fixture and report errors by RPM, advance ratio, and static/
   forward regime. A low-confidence exploratory NeuralFoil screen is not evidence.
4. Only after all frozen gates pass, obtain independent aerodynamic review and begin
   PR-06D fixed-limit equivalence and opening-angle sensitivity.

Primary references are the APC
[geometry index](https://www.apcprop.com/propeller-technical-data/),
[PE0 file](https://www.apcprop.com/propeller-technical-data-files/10x47SF-PERF.PE0),
[source terms](https://www.apcprop.com/terms-conditions/), and the
[UIUC Airfoil Data Site](https://m-selig.ae.illinois.edu/ads/coord_database.html).
