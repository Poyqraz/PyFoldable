# PR-06D fixed-limit equivalence evidence

## Decision

**PASS — pr06d_software_fixed_limit_passed**

The fully deployed fold-state path is exactly identical to the unchanged fixed-blade
BEM path over all 50 qualification-eligible points in the frozen
UIUC fixture. Maximum absolute thrust and torque deltas are both exactly zero.

## Evidence boundary

- Fixture: `uiuc-apcsf-10x4.7-volume1-v3-screening-v1`
- Fixture SHA-256: `c6f04a4d32ea9c4421db38ec67a2164be0b81b13c64b0a81718792dfd047531b`
- Fold state: `fully-deployed-fixed-limit`
- Projection model: `radial_cosine_v1`
- Annuli: 80
- Loading branch: `signed_nonreversed`
- Polar evidence: analytic proxy, non-representative
- Maximum |ΔT|: 0.0 N
- Maximum |ΔQ|: 0.0 N·m

## Interpretation

Exact software-path equivalence only. This does not pass the PR-06C physical-accuracy gates or qualify folded-state predictions. The result permits the PR-06D software foundation to begin while
the PR-06C physical qualification remains blocked.
