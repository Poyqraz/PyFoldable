# Acar 2025 jointed-tip BEM reverse-engineering review

## Source and decision

The 13-page paper, [Aerodynamic Performance Analysis of a Main Propeller with
Jointed Tip-Mounted Blades Using Extended Blade Element Momentum
Theory](https://as-proceeding.com/index.php/ijanser/article/view/2790), was downloaded
from the publisher and bound to SHA-256
`030d485df45a22a1c67c3e004597218a8a5d87163c135e92ec3d4327ec6ad134`.
The PDF itself is not redistributed.

The paper is classified as `methodology_only_tip_jointed_system`. It is closely
related to the project concept, but it is a computational study of a separate
tip-mounted rotor rather than the current PyFoldable tip-hinged blade projection.
Its numerical table is therefore audited for transferable behavior and never used as
physical qualification or as a target for fitting.

## Reverse-engineered model

Reported assumptions are a two-bladed 0.25 m main propeller, a 0.05 m tip-rotor
radius, NACA 2412, linear lift slope `2*pi/rad`, `CD0=0.01`, assumed aspect ratio 8,
Prandtl tip loss and fixed-point inflow iteration. The most transferable relation is

\[
V_{\mathrm{eff,tip}}=\sqrt{V_\infty^2+(\Omega_{main}R_{main})^2}.
\]

PyFoldable implements this as an explicitly screening-only vector relation. It is not
injected into the current foldable solver because a separately rotating tip rotor and
a folding continuation of the main blade are different physical topologies.

## Table audit

All 31 Table 1 points from 0 to 30 m/s are retained as factual audit data. Component
closure is good within table rounding: maximum `|Ttotal-Tmain-Ttip|` is 0.0008 N and
maximum `|Ptotal-Pmain-Ptip|` is 0.007 W. The table is therefore useful for testing
sign handling even though the underlying simulation is not reproducible.

The sign-safe audit finds:

| Component | Propulsive | Powered drag | Energy-extracting drag |
| --- | ---: | ---: | ---: |
| Main | 7 | 8 | 16 |
| Tip | 0 | 10 | 21 |
| Combined | 2 | 12 | 17 |

Eighty-three reported efficiency values are rejected as propulsive efficiency because
their points have negative thrust, negative power, or both. They remain available as
raw signed ratios for audit, not as performance efficiency.

## Internal consistency findings

- The text states that main-propeller thrust remains positive across the full speed
  range, while Table 1 becomes negative from 7 m/s onward.
- `Omega` is introduced as angular speed and used in `Vrel=Omega*r`, but the power
  integral is written with an additional `2*pi` factor. If `Omega` is rad/s, power
  should be `Omega*Q`; if it is revolutions/s, the velocity equation needs `2*pi`.
- The methods and discussion present two non-identical effective-inflow equations.
- The abstract claims high predictive accuracy, but no experiment or CFD comparison
  is reported.
- Main/tip RPM, passive tip torque equilibrium, chord/twist tables, hub radii, air
  density, element count and convergence controls are missing.

These findings prevent numerical reproduction and explain why the paper table is not
a validation benchmark.

## Project contribution

The paper produced four concrete additions:

1. Signed operating modes: `propulsive`, `powered_drag`,
   `energy_extracting_drag`, `energy_extracting_thrust`, and `near_neutral`.
2. Propulsive efficiency is fail-closed outside positive-thrust/positive-power
   operation, at static conditions, and above the physical upper bound.
3. The combined tip-flow relation has typed provenance and input validation.
4. The paper table, closure errors, contradictions and reproduction blockers are
   regenerated as machine-readable evidence.

Its design conclusions remain hypotheses: active pitch or stowing may avoid parasitic
tip drag; energy recovery needs an explicit generator and net-drag balance; added tip
mass/load requires flutter, fatigue and vibration assessment. These hypotheses feed
PR-08/09/10 planning but cannot pass those physical gates.

## Missing information for a future reproduction

The original MATLAB implementation or, at minimum, main/tip rotational speeds,
torque-equilibrium rule, exact chord/twist stations, hub radii, density, radial element
count, convergence tolerance/max iterations and the exact power convention are needed.
With those inputs, the frozen 31-point table can become a software-reproduction test;
it would still require independent CFD or experiment before physical promotion.
