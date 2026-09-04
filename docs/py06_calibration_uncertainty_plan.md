# PY-06 — calibration, uncertainty and matched-comparison plan

## Decision boundary

PY-06 extends the merged PY-05 tree and the existing PR-07/09/10 contracts. It
does not replace PR-10 calibration certificates, repeat aggregation or Type-A /
Type-B uncertainty calculations. It adds the missing comparison and correlation
layer without fitting a model to the 0.85 project target. PR #3 remains separate.

No software fixture, literature baseline or successful numerical gate may set
`physical_qualification=true`. Real project promotion still requires source-bound
raw measurements, valid calibration identities and independent engineering review.

### PR-10 compatibility boundary

PY-06A requires the PR-10 decision envelope schema v2. The v2 assessment persists
the canonical test-stand-manifest digest and, for every run, the raw-data digest,
design id, experiment date and assessed-summary digest. The test-stand manifest
itself remains schema v1 because its calibration/policy shape did not change.
Legacy decision objects remain source-constructible through trailing optional
fields, but PY-06A rejects decisions without the v2 identities; legacy evidence
must be reassessed before comparison.

## Ordered tasks

| Task | Scope | Acceptance |
| --- | --- | --- |
| PY-06A — matched experiment comparison | Compare one fixed-reference and one foldable PR-10 summary at explicit open diameter, RPM, forward speed, temperature and pressure | Exact role/run/stand identity; bounded matching tolerances; uncertainty-propagated thrust, rotor-shaft-torque and DC electrical-input-power ratios; target interval classification; no target fitting; physical false |
| PY-06B — source-bound comparison service | Strict JSON loader and immutable report envelope for PY-06A | Duplicate/unknown/nonfinite/oversized input rejection; implementation/input hashes; stale-request rejection; software fixtures cannot promote |
| PY-06C — PR-07 motor correlation | Compare measured DC electrical input, independently established motor efficiency/shaft power and aerodynamic rotor torque | Electrical and shaft power remain distinct; motor/rotor equilibrium residuals; missing efficiency or dynamometer evidence blocks correlation |
| PY-06D — PY-05 mechanism identification | Calibrate mass/friction/spring parameters only from measured transition histories | Train/holdout split, parameter bounds, identifiability diagnostics and residuals; target fitting is labelled calibration, never validation |
| PY-06E — PR-09 structural correlation | Compare source-bound ANSYS and test observations at matched geometry/material/load case | Unit/load/hash matching, measurement and mesh uncertainty retained; no safety factor or material value inferred |
| PY-06F — UI and consolidated report | Read-only comparison tables/intervals and evidence status | Explicit run, stale-state invalidation, downloadable source-bound report; qualified/screening/pending/blocked states remain separate |

### PY-06B1 bounded service slice

PY-06B starts with one application-only service. A single bounded UTF-8 JSON
document carries the PR-10 manifest v1, PR-10 decision v2, both run contexts,
the comparison policy and a bounded source statement for every policy field.
The service converts those values to the immutable core types and delegates all
matching, covariance, interval and target decisions to
`build_matched_experiment_comparison`; it must not duplicate that mathematics.

The prepared identity separates the exact input-byte SHA-256 from the canonical
request SHA-256. The latter also binds the application service, PY-06A core and
PR-10 contract source-file hashes. Running with an older prepared identity is a
stale-request error and cannot publish a partial report. The delivered report is
deterministic JSON with an exact byte hash and explicit false values for physical
qualification and target fitting.

PY-06B1 excludes UI work, persistence, motor correlation, mechanism parameter
identification and structural correlation. Those remain PY-06C--F.

#### TDD gates for PY-06B1

- reject oversized, invalid UTF-8, deeply nested, duplicate-key and non-finite
  JSON before constructing core objects;
- require exact root, manifest, decision, summary, metric, context, policy and
  policy-source field sets, with bounded collection sizes and strings;
- recompute derived PR-10 `passed`, `state` and `software_gate_passed` fields plus
  manifest and summary digests; syntax/date-window validate and source-bind the
  declared raw-data digest, design id and experiment date (their absent source
  artifacts cannot be independently recomputed by this service);
- require a nonempty source statement for all five match tolerances, all three
  correlation assumptions and the thrust-ratio target;
- preserve input, request and implementation identities separately and reject a
  stale expected request hash;
- match direct PY-06A numerical output exactly, including controlled blocked
  comparisons with empty metrics;
- keep the request collections immutable and every report at `screening_only`,
  `physical_qualification=false` and `target_fitting_performed=false`.

## PY-06A first-slice contract

The caller must select exact run ids from an already assessed
`ExperimentBundleDecision` and provide one `RunComparisonContext` per selected
run. The context declares the open diameter, forward speed, torque-channel
meaning and source. RPM, temperature and pressure are taken from the PR-10
summary rather than repeated as user declarations.

The comparison recomputes the manifest and summary identities, requires exact
PR-10 metric keys, checks each direct calibration component against the bound
manifest, and verifies that DC electrical input power retains the PR-10
voltage-current product and uncertainty propagation.

Only `rotor_shaft_torque` is accepted for the experiment torque channel. The
derived `voltage * current` quantity is labelled `dc_electrical_input_power`; it
is not motor shaft power. Hinge-axis torque belongs to the separate PY-05
mechanism model and cannot be substituted.

For an output ratio `r = y_foldable / y_fixed`, the caller must declare a
bounded correlation coefficient `rho` for each compared quantity. Standard
uncertainties are propagated as:

`u(r)^2 = (u_foldable/y_fixed)^2 +
(y_foldable*u_fixed/y_fixed^2)^2 -
2*rho*(u_foldable/y_fixed)*(y_foldable*u_fixed/y_fixed^2)`.

This avoids silently treating calibration components from a shared test stand as
independent. A declared `rho=0` is an explicit assumption, not a default evidence
claim; its source is retained by the later PY-06B report envelope.

The expanded interval uses the explicit PR-10 coverage factor. The 0.85 target
is reported as met only when the interval lower bound reaches it, not met when
the upper bound is below it, and otherwise indeterminate. These are screening
classifications, not physical qualification.

## TDD gates for PY-06A

- exact fixed/foldable role plus raw-data/design/date/summary identity;
- same test-stand id and manifest digest plus software-pass prerequisite;
- each selected run date inside every bound calibration validity window;
- explicit, finite, positive diameter and nonnegative forward speed;
- diameter, RPM, forward-speed, temperature and pressure match gates;
- positive denominators and finite uncertainty arithmetic;
- analytic ratio/difference uncertainty checks;
- explicit `[-1, 1]` uncertainty-correlation inputs and covariance checks;
- boundary tests for met/not-met/indeterminate target intervals;
- rejection of hinge torque, generic torque and mislabeled electrical/shaft power;
- exact PR-10 metric set, manifest-bound calibration components and verified
  voltage-current electrical-power derivation;
- immutable machine-readable result with `target_fitting_performed=false` and
  `physical_qualification=false`.

The comparison feature in the first slice is core-only; the existing evidence
importer changes only enough to consume the PR-10 v2 fixture safely. New
PY-06 JSON/service/UI work starts only after this contract passes independent
review, preventing an interface from freezing incorrect measurement semantics.
