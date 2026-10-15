# Intermediate-fold centerline screening, 50 mm hinge

Nominal centerline screening of one existing trial hinge. This does not establish surface clearance, controlled folding, strength, vibration, aerodynamic validity, or qualification.

physical_qualification: false
Qualified winner: none

Archived PR #100 study `56a3b52a439c408cbdd13ae3baf8c43fa577bf71` SHA-256 `f3c3e927c0ede938e5e770cce2eab405ca8413cec997eb17ab620b5fe22a7124`.
Parent SHA-256 `1a149afec4cb192703a597e86717e5040d15e3c7fcb1697b4898ea3d26b6eada`.

## Interval

The envelope root uses cosine `-0.42999999999999994`, the binary64 value of `(0.070^2 - 0.050^2 - 0.075^2) / (2*0.050*0.075)`. That quotient is -0.43 in exact decimal arithmetic. Unrounded fold angle: -115.46756014247238 deg. Rounded half up to 0.01 deg: -115.47 deg. The analytic interval is closed at that unrounded root, so envelope equality is included.

First contact solves `theta = -pi + asin(0.018 / 0.05)` because the 75 mm segment reaches the hub tangent. Unrounded fold angle: -158.899803975907 deg. Rounded half up to 0.01 deg: -158.90 deg. The unrounded root is excluded because clearance there is numerical zero, not strictly positive. The rounded label is slightly more folded than the root and is not the interval endpoint.

Open-closed interval of the unrounded roots: (first contact, envelope entry].
`inside_partial_fold_interval` follows that predicate. `tolerance_based_envelope_diagnostic` keeps the existing audit rule that a 140 mm margin of at least -1e-9 m passes.
Instant hub clearance can be positive inside the analytic interval while `full_stow_path_intersects_hub` and `surface_stations_do_not_cover_hub_to_tip` remain.

## Inert tolerance witness

Fold angle -115.46756004247239 deg is an inert regression, not a proposed stop.
It sits slightly less folded than the envelope root.
Tolerance-based envelope diagnostic: true.
Analytic interval membership: false.

## Deployment-to-stop minimum

From deployment at 0 deg to -90 deg, the perpendicular foot lies before the hinge, so the closest point on the movable centerline is the hinge and hub clearance is constant at hinge radius minus hub radius. From -90 deg to -180 deg, t = -hinge*cos(theta) stays on the 75 mm segment because the hinge radius is smaller than the tip length, and clearance is -hinge*sin(theta) - hub. Its derivative -hinge*cos(theta) is positive on that interval, so clearance increases as theta increases. The minimum from deployment to a stop is therefore the clearance at that stop. That continuous-path minimum is a different quantity from the instantaneous clearance at another angle and from the canonical full-stow diagnostic, which remains the separate -180 deg path finding.
The retained value on each proposed stop is that closed-form stop clearance. Sampled poses are not the proof.
Canonical full-stow clearance on every pose: -0.018 m.

## Reported poses

These three angles are proposed intermediate-stop alternatives. They do not replace the canonical -180 deg declaration.

| Pose deg | Centerline diameter m | Instant hub clearance m | Deployment-to-stop minimum m | Canonical full-stow clearance m | Analytic interval | Tolerance envelope diagnostic | Full-stow collision retained | Missing surface retained |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| -120 | 0.13228756555322954 | 0.02530127018922194 | 0.02530127018922194 | -0.018 | true | true | true | true |
| -135 | 0.10623933623853066 | 0.017355339059327384 | 0.017355339059327384 | -0.018 | true | true | true | true |
| -150 | 0.1 | 0.006999999999999999 | 0.006999999999999999 | -0.018 | true | true | true | true |

## Canonical -180 deg

Centerline diameter 0.1 m.
Instant hub clearance -0.017999999999999988 m.
Deployment-to-stop minimum if the stop were -180 deg: -0.01799999999999999 m.
Canonical full-stow clearance -0.018 m.
Reasons: full_stow_path_intersects_hub, surface_stations_do_not_cover_hub_to_tip, tip_centerline_intersects_hub.
This collision finding stays in force if an intermediate stop is later proposed.

## Still required for finite-surface clearance

- chord-bearing section surfaces or solids, not only the centerline
- joint thickness and exposed hardware, both absent
- explicit root-gap and tip-gap surface treatment
- both blade surfaces, the hub solid, and any interblade pair
- a declared clearance tolerance and frame for GEOM-03 or GEOM-04
- manufacturing tolerances or an explicit statement that they are absent
