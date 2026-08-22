# PR-06C closure and PR-06D entry execution plan

## Objective

Reach the PR-06D implementation stage without weakening the frozen UIUC benchmark,
inventing aerodynamic evidence, redistributing restricted source material, or fitting
model parameters to the target coefficients. PR-06D may start only after the PR-06C
decision is explicit and machine-enforced.

## Current baseline

- PR-06A/06B numerical foundations and PR-06C full propulsive coverage are complete.
- Representative-polar evidence, root-search query provenance and Snel-1993 ablation
  contracts are implemented.
- The unchanged UIUC gates still reject the current proxy screens.
- The current APC PE0 geometry and E63 coordinates remain caller-supplied inputs; they
  are not vendored by the project.

## Execution status

- The final PR-06C physical gate is now implemented and executed as a single,
  fail-closed decision. See
  [`reports/pr06c_physical_gate.json`](../reports/pr06c_physical_gate.json) and the
  [review summary](../reports/pr06c_physical_gate.md). The fixture and frozen-policy
  identities pass; physical accuracy, representative provider evidence and the
  independent model-form review remain blocked.
- Stage 1: the evidence/provenance contracts are merged; the caller-supplied,
  representative E63→APC12 family and its two-capture promotion remain outstanding.
- Stage 2: the rotational-ablation foundation is merged; the real-family ablation
  and independent tip/wake comparison remain outstanding.
- Stage 3: the current closure decision is an explicit failure. No benchmark
  threshold or evidence class was weakened.
- Stage 4: implemented on the PR-06D branch. The fixed and fully deployed paths are
  exactly equal over all 50 frozen qualification points; fold-state projection,
  polar-anchor identity, invalid-domain failures and geometry provenance are covered
  by tests. See the [machine-readable report](../reports/pr06d_fixed_limit_equivalence.json)
  and [review summary](../reports/pr06d_fixed_limit_equivalence.md).
- Remaining boundary: folded-state outputs are screening-only until PR-06C passes.

## Execution sequence

### Stage 1 — close the PR-06C evidence boundary

1. Merge the reviewed evidence/provenance foundation after CI passes.
2. Add a user-local real-family builder that consumes SHA-pinned E63 and APC PE0
   inputs and produces the exact spanwise schedule used by both benchmark and radial
   convergence runs.
3. Derive the polar grid from the complete BEM root-search envelope, including alpha,
   Reynolds and Mach margins. Unsupported cells fail closed.
4. Preserve provider identity, coordinate identity, section transform identity,
   confidence/convergence, post-stall source and table cache keys.

Acceptance:

- no input is silently downloaded or committed;
- two identical captures compare reproducibly;
- every final annulus and root-search query is covered with `bounds="error"`;
- no boolean can independently promote representative status.

### Stage 2 — model-form ablation

Run the same frozen fixture and policy for:

1. qualified 2-D spanwise polars;
2. qualified 2-D polars plus rotational augmentation;
3. the preceding model plus each independently declared tip/wake candidate.

The correction-off case must remain bit-for-bit compatible. Model configuration and
local corrections must appear in JSON provenance. Proxy `alpha_0`, lift limit and drag
terms must not be fitted to UIUC CT/CP.

Acceptance:

- overall and per-regime solution coverage at least 95%;
- overall CT/CP WMAPE at most 15%/20%;
- every static and forward regime CT/CP WMAPE at most 15%/20%;
- normalized CT/CP bias within ±10%/±15%;
- terminal radial delta at most 0.5%;
- representative polar evidence passes;
- an independent model-form comparison is recorded.

### Stage 3 — PR-06C closure decision

If every gate passes, publish the reviewed promotion bundle and mark PR-06C complete.
If any gate fails, preserve the failure artifact, identify the unresolved physical
mechanism and keep accuracy qualification blocked. No threshold may be changed inside
the remediation pull request.

The preserved decision currently follows the failure branch. Re-running
`examples/run_pr06c_physical_gate.py` reproduces that decision; `--require-pass`
provides a non-zero automation gate for a future complete evidence bundle.

### Stage 4 — PR-06D fixed-limit foundation (implemented)

PR-06D begins with a narrow compatibility target:

1. introduce an explicit fold/opening state at the rotor-geometry boundary;
2. prove that fully open state is identical to the qualified fixed-blade solution;
3. propagate opening angle to effective radius and local station geometry without
   changing polar identity implicitly;
4. record geometry-state provenance in every rotor result;
5. add opening-angle continuity and invalid-domain failures before sensitivity plots.

Acceptance:

- fully open thrust, torque, CT and CP match the fixed solver within numerical
  roundoff;
- zero/invalid effective radius and self-intersecting/unsupported states fail closed;
- result mappings include nominal and effective geometry plus opening state;
- all existing fixed-blade tests remain green;
- CI passes on the PR-06D branch.

### Stage 5 — PR-06D opening sensitivity (implemented, screening-only)

The frozen 50-point propulsive matrix is evaluated at 0/15/30/45/60-degree fold
states. The exact deployed endpoint remains identical to the fixed solver and all 250
state/condition combinations are retained in a deterministic report. The evidence is
hard-coded as `screening_only_until_pr06c_passes`; it does not satisfy Stage 6 physical
qualification or permit a final design decision.

## Stop conditions

Scientific non-qualification is not a software failure to hide. Work stops short of
an accuracy claim when required third-party inputs, provider coverage, independent
reference results or frozen benchmark gates are absent. The code may still advance to
the PR-06D *software foundation and screening sweep* only when both are explicitly
labelled non-qualifying and cannot bypass the PR-06C accuracy gate.
