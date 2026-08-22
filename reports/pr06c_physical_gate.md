# PR-06C physical qualification gate

## Decision

**BLOCKED.** The gate execution is complete and reproducible, but the physical
qualification claim is not accepted. The frozen fixture identity and policy pass;
six evidence or accuracy gates remain closed. The machine-readable decision is
[`pr06c_physical_gate.json`](pr06c_physical_gate.json).

This is a scientific non-qualification, not an incomplete software run. PR-06D's
fixed-limit software equivalence remains valid, while folded-state physical accuracy
continues to be labelled screening-only.

## Re-executed manufacturer-geometry screen

The caller-supplied APC `10x47SF-PERF.PE0` file was verified at SHA-256
`f38bdb92f65053a7791a6ba492a89da69651f1a11983724953272211db5d39c8` and parsed as
version `v2025-1001`, simulation date `2026-02-24`, with 51 radial stations. It
declares an E63-to-APC12 transition over 4.90–5.00 inches and states that APC12 is
equivalent to NACA 4412. The file remains a caller-supplied input and is not
redistributed.

The unchanged 50-point UIUC policy produced:

| Metric | Overall | Static | Forward | Limit | Result |
|---|---:|---:|---:|---:|---|
| Solution coverage | 100% | 100% | 100% | at least 95% | Pass |
| CT WMAPE | 16.23% | 6.03% | 25.68% | at most 15% | Fail |
| CP WMAPE | 16.98% | 6.47% | 23.19% | at most 20% | Fail (forward) |
| CT normalized bias | -14.07% | -1.56% | -25.68% | within ±10% | Fail |
| CP normalized bias | -13.42% | +3.10% | -23.19% | within ±15% | Fail (forward) |

The manufacturer geometry materially improves the analytic-proxy baseline, but it
does not cure the forward-flight model-form/polar error and cannot supply
representative polar evidence by itself.

## Gate result

| Gate | Status | Evidence |
|---|---|---|
| Frozen UIUC fixture | Pass | Pinned fixture digest matches |
| Frozen thresholds | Pass | No limit changed |
| Qualification benchmark identity | Fail | Available artifact remains explicitly `screening-v1` |
| Overall and per-regime accuracy | Fail | CT and forward-flight metrics above |
| Representative E63→APC12 evidence | Fail | No reviewed APC12/NACA-4412 coordinate capture, complete XFOIL family, or approved two-capture promotion is bound |
| Full annulus-query binding | Fail | No passing typed polar evidence exists for all 50 × 80 final queries |
| Independent model-form review | Fail | No approved independent comparison artifact supplied |
| Review-to-result digest binding | Fail | Cannot bind an absent review |

## Exact remaining promotion inputs

Promotion requires all of these in one new qualification artifact:

1. a reviewed APC12/NACA-4412 coordinate document with a pinned digest, alongside
   the official UIUC E63 coordinates;
2. complete XFOIL 6.99 tables covering every alpha/Reynolds/Mach root-search query,
   with `bounds="error"` and no clamping;
3. two reproducible captures plus an approved promotion record;
4. the unchanged benchmark passing overall and static/forward regime gates;
5. an independent, no-target-fitting comparison of qualified 2-D,
   rotational-augmentation, and tip/wake variants, bound to the winning benchmark
   digest.

Until those external evidence and physics conditions exist, changing a label,
substituting an analytic proxy, or relaxing a threshold cannot pass the gate.
