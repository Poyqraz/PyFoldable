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

Synthetic wide constant-coefficient trace: 1309 queries, minimum alpha -0.0061813744279 rad, totals withheld. The trace stopped above the potential terminal alpha. Synthetic coverage of -40 deg through +10 deg and not the first positive query: failed at annulus 0 after 1 query. A table that covers those negative angles and stops at +10 deg still fails on the conditional first query. That does not make the kinematic image, either profile, or the project infeasible.

The retained NACA0012 Re 200000 captures are real XFOIL and NeuralFoil outputs at about -6 deg to +10 deg and Mach 0. Raw capture review is separate from the later promotion record. That coverage is incompatible with this baseline and is not an active-design bundle.

The current NeuralFoil adapter rejects nonzero Mach. Its author documents compressible corrections as an AeroSandbox extension. It is not a replacement for this Mach image.

## Recommended experiment

The historical rectangle pads the image extrema to -40 deg and +32 deg. The image extrema are about -39.72917 deg and +30.65875 deg. A Mach 0 corner is not a correlated annulus state. Starting at +32 deg does not execute the +30.65875 deg conditional first query.

`xfoil_positive_first_potential_image_probe_v1` is not executed here. It requests 8 XFOIL cells, 37 descending angles, one 90 s attempt, no retry, no INIT, and no BEM call. The adapter submits each cell as one script and stops before the next cell after a failure. It does not interrupt a cell at the first bad angle. Mach 0 is not requested, so a difference from PR #97 is not evidence about sequencing alone.

### Can establish

Whether this declared eight-cell grid, descending order, kinematic Mach and Reynolds endpoints, and one-script-per-cell execution produce a complete usable ledger.

### Cannot establish

A genuine two-profile BEM comparison. A failure establishes failure of this grid, sequencing, and execution configuration only. It does not establish infeasibility of the correlated kinematic image, the actual solver path, either profile, or the project. Differences from PR #97 cannot be attributed only to sequencing because the Mach grid also changes. Starting at the padded +32 deg grid angle does not execute the +30.65875 deg conditional first query.
