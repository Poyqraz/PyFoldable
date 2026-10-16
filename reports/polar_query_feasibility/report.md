# Polar-query feasibility

This is an offline diagnostic. It is not a BEM comparison and not a qualification.
physical_qualification: false
Genuine query coverage: unavailable
Genuine two-profile numerical comparison: UNESTABLISHED

## Cause map

The unchanged baseline is the 250 mm, 7100 rpm, fully-open, zero-offset rotor, 40 station-span annuli, bounds error, and the default positive-only annulus policy.
For this hover condition the inflow angle is half the QPROP psi, so alpha decreases as psi increases and Reynolds and Mach decrease along the same interval.

Conditional first query at annulus 0: alpha 0.535096132046 rad, Reynolds 36812.8617495, Mach 0.0572857817153. It is issued only if the solver reaches that annulus. It is not an observed genuine query.
Conditional first query at annulus 39: alpha 0.0919933959905 rad, Reynolds 51798.5893057, Mach 0.264989414585.
Potential terminal alpha, the far psi endpoint and not an observed query: -0.693404767357 rad.
PR #97 rectangle reconstructed from those endpoints: alpha -0.693404767357 to 0.535096132046 rad, Reynolds 26030.6241792 to 88107.314882, Mach image 0.0405071647185 to 0.264989414585. Its Mach grid also includes 0, which is outside that image. Alpha samples: 37.

PR #97 retained two observed provider failures and zero BEM calls. NACA0012, Mach 0, Reynolds 26030.6: usable fraction 0.756757, angles -40 deg through -24 deg not_converged. NACA2412, same cell: 90 s timeout and no per-angle disposition. Those angles sit at the negative end of the rectangle. They are not the conditional first query, which is about +30.7 deg at annulus 0.

Synthetic wide constant-coefficient trace: 1309 queries, minimum alpha -0.0061813744279 rad, totals withheld. The trace stopped above the potential terminal alpha. Synthetic coverage of -40 deg through +10 deg and not the first positive query: failed at annulus 0 after 1 query. Removing the historical negative-alpha failures does not make the baseline executable.

The current NeuralFoil adapter rejects nonzero Mach. Its author documents compressible corrections as an AeroSandbox extension. It is not a replacement for this Mach image.

## Recommended experiment

`xfoil_positive_first_potential_image_probe_v1` is not executed here. It requests 8 XFOIL cells, one attempt each, 90 s, no retry, alpha descending from the high positive grid angle, at the kinematic Mach and Reynolds endpoints. Mach 0 is not requested. BEM calls: 0.
A point ledger for the potential-image rectangle when XFOIL starts at the high positive grid angle and steps downward, at the kinematic Mach and Reynolds endpoints rather than at Mach 0.
A genuine two-profile BEM comparison. Actual solver queries remain unavailable, and success of this probe still requires a separate decision to attempt BEM. Failure means the unchanged potential image is not provider-feasible under positive-first sequencing either.
The unchanged positive_only policy can query the whole psi image, whose negative endpoint is inside this request. This probe does not authorize a narrower search, a Mach-0 family, coefficient substitution, or a NeuralFoil replacement.
