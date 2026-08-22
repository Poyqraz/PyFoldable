# PR-06D opening-angle sensitivity

## Decision

**Software sweep complete; physical qualification remains blocked.** The exact deployed
endpoint matches the fixed path over all 50 frozen propulsive
points, and 5 ordered opening states produced a complete
250-case grid.

| fold angle (deg) | radial projection | effective D (m) | median static T/T0 | median forward T/T0 | median static Q/Q0 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| -0 | 1.0000 | 0.2540 | 1.000 | 1.000 | 1.000 |
| -15 | 0.9659 | 0.2518 | 0.982 | 0.981 | 0.981 |
| -30 | 0.8660 | 0.2455 | 0.932 | 0.928 | 0.929 |
| -45 | 0.7071 | 0.2354 | 0.857 | 0.850 | 0.851 |
| -60 | 0.5000 | 0.2223 | 0.765 | 0.757 | 0.761 |

## Evidence boundary

- Fixture: `uiuc-apcsf-10x4.7-volume1-v3-screening-v1` (50 points)
- Annuli: 80; loading branch: `signed_nonreversed`
- Polar: analytic proxy, explicitly non-representative
- Qualification: `screening_only_until_pr06c_passes`
- Physical qualification: `false`

Geometry/solver sensitivity only. Folded-state physical accuracy remains blocked by PR-06C and these ratios must not drive a final design decision.
