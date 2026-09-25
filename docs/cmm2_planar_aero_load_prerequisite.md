# CMM-2 planar aerodynamic load prerequisite

This document is the screening contract for
`planar_projected_material_load_v1`. It is not CMM-2. Transient coupling is
not implemented. CMM-1 is unchanged, including
`aerodynamic_hinge_torque_status = unavailable_omitted_by_cmm1`.

The adapter is pending independent review.

`physical_qualification` is false.
`qualification` is `screening_only_projected_rate_independent`.
`projection_model` is `radial_cosine_v1`.
`load_mapping_model` is `planar_projected_material_load_v1`.
`distributed_couple_model` is `none`.
`hinge_rate_aerodynamic_model` is `ignored_rate_independent_quasi_steady`.
`full_propeller_clearance` stays null. PR-06C stays unresolved. No GEOM gate
is promoted. There is no calibration and no experimental validation.

The adapter does not establish actual folded-tip aerodynamics, a validated
aerodynamic hinge torque, a physical prediction, or finite-rate aerodynamic
validity.

Implementation: `pyfoldable/core/foldable_aero_load.py`.

## Geometry

The existing planar hinge convention is unchanged. For one movable tip:

```text
x = R e_r(phi) + s e_r(phi + theta)
x_phi = R e_t(phi) + s e_t(phi + theta)
x_theta = s e_t(phi + theta)
```

`R` is the hinge radius, `s` is material distance from the hinge, `theta` is
the hinge angle from deployed, and `phi` is the shaft angle.

The current foldable BEM radius is the projected radius

```text
r_p(s) = R + s cos(theta)
dr_p/ds = cos(theta)
s = (r_p - R) / cos(theta)
```

This is valid only for `|theta| < pi/2` and a strictly positive projection
factor. The foldable screen rejects a factor at or below `1e-12`. v1 uses
that same limit. It does not replace `r_p` with the shaft-axis distance of
the same planar point,

```text
sqrt(R^2 + s^2 + 2 R s cos(theta))
```

Those two radii agree at `theta = 0`. Their difference starts at `O(theta^2)`.
That limit is a geometric relation of this screen. It is not physical
first-order accuracy.

## Densities and force basis

Current BEM stores whole-rotor projected densities. `blade_count` is already
inside them.

| Symbol | Source field | Measure |
| --- | --- | --- |
| `T` | `differential_thrust_n_m` | newton per projected radial metre, whole rotor |
| `D` | `differential_torque_nm_m` | newton-metre per projected radial metre, whole rotor |

For `N` identical blades the v1 reconstruction on the movable tip, per
material metre, is

```text
f_z,one = (T / N) cos(theta)
f_t,one = -(D / (N r_p)) cos(theta)
f_r,one = 0
r_p = R + s cos(theta)
```

The force basis is `e_z` and `e_t(phi)`, not the folded section basis.
`cos(theta)` is `dr_p/ds`. The material density is per material metre, so the
Jacobian multiplies the projected density. The inverse Jacobian is not applied.

Distributed aerodynamic couple is none. This is a model assumption, not a
physical inference.

## Generalized loads

For one blade,

```text
q_phi,1 = integral f · x_phi ds
q_theta,1 = integral f · x_theta ds
```

`x_phi · e_z = 0` and `x_theta · e_z = 0`, so projected axial thrust does no
planar `+z` shaft work and no planar `+z` hinge work. Thrust is retained on
the interval record. It is not converted into hinge torque.

On `e_t(phi)`, `x_phi · e_t(phi) = r_p`, so

```text
f · x_phi = f_t r_p = -(D / N) cos(theta)
```

A projected midpoint cell `a <= r_p <= b` has constant `D`. With
`ds = dr_p / cos(theta)`,

```text
q_phi,1 = -(D / N) (b - a)
```

For movable material `a >= R > 0`, substitute
`s = (r_p - R) / cos(theta)`:

```text
q_theta,1 = -(D / N) [(b - a) - R ln(b / a)]
```

`D` positive is resisting shaft torque in the current BEM sign. Then
`q_phi,1 < 0` and, on a deployed movable tip, `q_theta,1 < 0`. The
aerodynamic hinge load tends toward negative, folded `theta`. Hinge load is
not required to be zero at `theta = 0`.

Units: `D` times a length is newton-metre; division by `N` leaves
newton-metre. `ln(b / a)` is dimensionless.

## Fixed root, movable tip, and a crossing cell

Material with `r_p <= R` is fixed to the shaft. It contributes to the shaft
generalized load and contributes exactly zero to the one-tip hinge load. A
movable-tip lever arm is not applied to root loading.

If a midpoint cell has `a < R < b`, it is split into `[a, R]` and `[R, b]`.
Both pieces keep the cell's midpoint `T` and `D`. The split does not re-solve
BEM. The outer piece absorbs the rounding residual of the original cell
integrals `T (b - a)` and `D (b - a)`, so the two pieces reconstruct that
midpoint-rule cell. The shared boundary has no width.

## Whole-rotor shaft load

The whole-rotor aerodynamic shaft load is derived from the same partition:

```text
Q_phi,aero = -math.fsum(piece resisting torques)
Q_a = -Q_phi,aero
```

Each unsplit piece resisting torque is `D` times the piece width, the same
product as `BEMRotorElement.torque_nm`. Existing rotor torque is
`math.fsum` of those element torques. `Q_a` is therefore the reconstructed
BEM shaft torque, not a second multiply by `blade_count`. On the checked
foldable fixtures the reconstruction residual against
`BEMRotorResult.torque_nm` is zero. A split that is not exactly representable
remains bounded by a few units in the last place of that torque, not by an
engineering tolerance.

The published one-tip hinge field is

```text
one_tip_hinge_generalized_torque_nm
```

There is no field named only `hinge_torque_nm`. The diagnostic

```text
synchronous_n_times_one_tip_hinge_generalized_torque_nm
= N * one_tip_hinge_generalized_torque_nm
```

is the common-coordinate sum. Future CMM-2, if separately accepted, would
insert the one-tip value inside the existing hinge-row parentheses that are
already multiplied by `N`. This prerequisite does not do that insertion.

For the same whole-rotor density `D`, one-tip loads scale as `1/N`.
`N * q_theta,1` is unchanged by that bookkeeping. The whole-rotor shaft load
is not multiplied by `N` twice.

## Power and hinge rate

For one synchronous rotor the mapped screening power is

```text
P_aero = Q_phi,aero * omega + N * q_theta,1 * theta_dot
```

When `theta_dot != 0` this is not `-Q_a * omega` alone. It is a screening
diagnostic, not a measured aerodynamic power.

`hinge_rate_rad_s` must be finite. It is stored and may enter `P_aero`. The
v1 force law ignores it. A nonzero supplied rate is not replaced by zero. No
maximum valid hinge rate is invented.

`D = 0` gives `q_phi = 0`, `q_theta = 0`, and `P_aero = 0` for every finite
`theta` and `theta_dot` inside the projection domain, including nonzero thrust.

## Sectional Cm

`PolarQueryResult.cm` is not an input. The repository does not establish the
folded 3D moment orientation needed to turn a 2D section `Cm` into a `+z`
hinge couple. v1 declares `sectional_aerodynamic_couple = excluded_in_v1`.
There is no hidden `Cm q c^2` hinge term.

## Coverage and failure

A usable one-tip hinge load requires the BEM radial domain to cover the hinge
radius through the projected effective tip. A gap, an overlap, a hinge outside
that domain, or an uncovered movable interval raises
`PlanarProjectedMaterialLoadError`. The result is not a zero hinge load.

The same error is raised for nonfinite radii, densities, `theta`, or hinge
rate; `blade_count < 1`; `R <= 0`; an invalid projection factor; `|theta| >=
pi/2`; a non-positive radius; or a non-positive interval width. Invalid
geometry is not clamped.

`hub_to_tip` remains an allowed existing BEM screening choice. Its
`geometry_extended` flag and any per-element extrapolation flag are copied
onto the mapped result. Extrapolated geometry is not hidden. `station_span`
that starts outboard of the hinge fails closed.

Requesting the map does not change the BEM thrust, torque, solution, or polar
queries. BEM annulus, rotor, and foldable projection mathematics are not
modified. No new induction model or momentum closure is introduced.

## Provenance

The JSON mapping records the model and schema version, qualification,
`physical_qualification = false`, blade count, hinge radius, `theta`, the
declared hinge rate, projection factor, operating-condition id, BEM settings,
polar schedule / airfoil / scenario / source identity already present on the
foldable result, the projected intervals, the fixed-root versus movable-tip
partition, the source densities, the reconstructed shaft load, the resisting
shaft torque, and the one-tip hinge load. A hash is not added at this layer.
A hash would not authenticate physical truth. A later source-bound CMM-2
service would seal the complete request.

## What remains unapproved

CMM-2 transient coupling is not accepted implementation work. PY-06D2 remains
blocked without suitable identifiable measurements. Robust optimization remains
premature. Phase 5, Phase 6, and Phase 7 of the validation roadmap are not
advanced.
