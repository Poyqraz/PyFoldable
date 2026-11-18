# Printable 13-inch segmented propeller — first physical prototype

Status: assembly and mechanism prototype (fit, motion, stops, play, mass properties). It is not qualified for
powered operation: physical qualification is false, maximum speed, motor and thrust are not supplied, and the
printed-material values are exploratory.

Code: `pyfoldable/prototype/` (manufacturing geometry, optional `[cad]` extra: build123d 0.9.1 on OpenCASCADE).
App: research app → *Prototip*. Outputs: `reports/prototype_13in_20261118/`.

## Owner design intent (2026-11-18)

- Deployed diameter 13 in = 330.2 mm. The proximal segment is longer than the distal (joint plane r_j = 99 mm:
  proximal 84 mm from the hub, distal 66.1 mm).
- One lug per segment and one common pin parallel to the shaft. The distal folds backward (toward the trailing
  edge, opposite the rotation) in the rotor plane.
- An axial offset lets the segments pass above and below each other. Initial target 5–6 mm, to be evaluated
  against the solids. The 30 mm offset of the 800 mm demonstration is not carried over.
- This supersedes the earlier out-of-plane interpretation. The existing code (display loft, coupled model, fold
  cycle) already used a shaft-parallel pin through the quarter-chord line, so the frames agree.

## Three geometry roles

| Role | Module | What it is |
|---|---|---|
| Display mesh | `visualization/blade_surface.py` | Lofted triangles for plots; no joint design |
| Mechanical model | `dynamics/fold_cycle.py` | Rigid distal about the pin with a scalar CG distance |
| Manufacturing geometry | `prototype/` | B-rep solids, assembly, STEP/STL/3MF |

The prototype feeds the mechanical model through `mass.fold_mechanism_equivalent`: mass, CG distance, inertia about
the pin direction, the e_t–e_z product and the lug mid-plane offset. Fold-cycle v1 puts the CG on the span line
through the pin. It cannot represent the chordwise CG offset, which `prototype/loads.py` therefore treats separately.

## Frame, reference planes, offset

Blade-1 frame: x is chordwise (leading edge at −x; it leads in rotation +Ω about +z), y is spanwise, z is along the
shaft (+z is the thrust side for positive twist). Lengths are in mm.

- **Plane A** (z = 0): the proximal reference plane through the quarter-chord line of the proximal sections.
- **Plane B** (z = δ): the distal reference plane through the quarter-chord line of the distal sections.
- **Axial offset** δ = z_B − z_A. It is a rigid translation along the pin and adds no angular degree of freedom.
  The deployed blade therefore has a step δ at the joint.
- **Lug stack:** proximal lug [z_i − g/2 − t_p, z_i − g/2], distal lug [z_i + g/2, z_i + g/2 + t_d], with the
  interface plane z_i = δ/2 by default.
- Pin diameter, lug thicknesses t_p and t_d, the running gap g and the total stack t_p + g + t_d are separate
  inputs. The lug mid-plane distance (t_p + t_d)/2 + g is derived from them.

## Joint design (one design, all features)

- **Lugs:** each segment carries one boss of radius R_b about the pin, in its own band, with 0.4 mm edge rounds.
  The bosses are fused to the bodies.
  - By default the lugs are full depth: each spans from its blade's far surface over the boss disk to the lug
    interface. Lug thickness therefore grows with the offset: more mass, a lower bearing stress, and a more
    eccentric load path.
  - Explicit thinner lugs are allowed. The check flags any lug that engages less than 60 % of its blade section
    (a thin, eccentric neck). The first independent review of an earlier draft found exactly this at δ = 9.5 mm
    with 4 mm lugs.
- **Swept reliefs:** inside R_b + c_r, the proximal is cut away above its band and the distal below its band.
  Either boss therefore turns over the other through the whole travel.
- **Spot faces:** these clear the washers, the pin head and the E-clip.
- **Pin set:** ISO 2341-A Ø3 clevis pin (head Ø5×1), two DIN 433 3.2 washers and a DIN 6799 size 2.3 E-clip in a
  turned groove. The groove position follows from the stack (see `hardware_list.csv`).
- **Hole:** pin Ø plus the diametral clearance, with 0.4 mm entry chamfers. The clearance is calibrated with the
  hole coupon.
- **Printable sections:** the catalog profile with its trailing edge thickened to 0.8 mm from 50 % chord. This is a
  new section identity (`NACA2412-te0.80mm-x0.50`; see *Aerodynamic evidence*).

### Where the open stop has to be

Centrifugal force seats the distal against forward rotation when its CG lies aft of the radial line through the
pin. For a pin near the quarter chord this holds: the CG is 3.9 mm aft in the default design. The open stop must
therefore block forward rotation (+θ) and leave the backward fold (−θ) free.

For a rotation about the pin, a point at angle α measured from the pin moves along that circle:

- Points ahead of the pin on the joint plane (α ≈ 180°) move inboard on forward rotation. On a backward fold they
  sweep only the outboard half-plane.
- Every other point either moves away from the proximal on forward rotation, or its circle crosses the proximal
  on the backward fold.

The only rigid stop that blocks forward rotation without blocking the fold is therefore a contact ahead of the pin
on the joint plane. The design uses a **stop nose** on the distal root that reaches down into the proximal band and
seats flat on a **stop pad** of the proximal. The seat is a flat face pair with a spanwise normal. Under forward
rotation the nose moves straight inboard onto the pad. A rear stop or hook was rejected because it would block the
backward fold.

Near 180° the nose returns over the proximal and meets it. **The nose doubles as the folded stop.** With a 4 mm nose
that happens at about 144° for offsets up to about 10 mm. A shallower nose folds further, but its root bending then
governs the strength (2 mm nose: about 2050 RPM at SF 2).

### Why 5–6 mm does not clear the template blade

A backward fold about a pin near the quarter chord carries every distal point through the direction straight
inboard of the pin. Each one passes over the proximal planform, so the whole distal must pass above (δ > 0) or
below the proximal. The required δ is about half the summed height of the overlapping twisted sections, plus the
clearance. On the template planform (twist 31° at the root, 17° at the joint, 37–30 mm chord) these sections are
12–22 mm tall.

The check runs on the actual solids (see *Method*). At δ = 5.5 mm the bodies clash from 57°, with a worst
interference of 5.2 mm at −105°. Clearing the fold needs δ ≈ 11.2 mm nominally (11.5 mm rechecked, 0.81 mm clear), or
≈ 12.5 mm with worst-case joint play.

Flatter blades (lower pitch) need less offset: twist ×0.6 clears with play at 9.5 mm, and 5–6 mm clears a 140° fold
only at twist ×0.25–0.35 (2–2.5 in pitch; with worst-case play 6.7–7.4 mm). On the template blade, 5–6 mm
clears about 55–60°. The smallest practical adjustments are listed under *Results*.

## Method

- **Full-travel clearance (`checks.sweep`):**
  - Both solids are tessellated at 0.05 mm and rasterised on a 0.25 mm grid. The proximal gives its top surface
    (dilated by one cell, which is conservative) and the distal gives its bottom surface.
  - For every degree of fold, the vertical gap is evaluated between the turned distal columns and the proximal.
  - Because the segments pass above and below each other, the vertical gap is the relevant clearance, and its
    deficit is directly the extra offset needed.
  - The rotation-invariant joint ring (relief radius + 0.5 mm) and the stop seat below 2° are designed contacts.
    They are checked with exact OpenCASCADE distances at fold 0 (seat contact, pin radial play 0.1 mm, washers on
    their faces) and at 2° off the stop (0.21 mm).
  - Exact distances also confirm the governing angle: an exact distance of 0 wherever the grid shows
    interference, and a positive exact distance below the vertical gap where it shows clearance (tests).
- **Coverage limits of the sweep:**
  - Only blade 1 and its hub sector are checked. The folded distal stays on its own side of the hub for two blades;
    more blades need a check against the neighbour.
  - 0–2° is covered by the exact checks only.
  - The open-stop seat has zero nominal clearance between separately printed faces. The as-printed open angle
    varies by about ±0.7° at an 8 mm lever and must be measured.
  - v1 accepts δ > 0 only: the distal passes above, on the thrust side.
- **Joint play:** the distal can rock about an in-plane axis by φ = min(c_h/t_d + c_h/t_p, g/R_b), and slide along
  the pin by g. The worst-case gap at distance s from the pin is the gap minus g minus φ·s. The default joint
  (c_h 0.2, g 0.3, R_b 5.5) gives φ = 3.1° and a 3.9 mm droop at the tip. This is a significant result for the
  print: tighten g and the hole fit after the coupon test.
- **Mass properties (`mass`):**
  - Solid volume, CG and inertia tensor from OCC (GProp), with a declared print model:
    m = ρ (V_shell + f (V − V_shell)), where V_shell = min(V, A·w). The thin blades are all perimeter walls, so
    infill does not affect them.
  - Steel hardware is included. Printed parts must be weighed to replace these estimates.
- **Loads (`loads`):**
  - Rotating-frame equilibrium of the distal on its stop: the centrifugal field Ω²(x, y, 0)dm with first and
    second mass moments, optional thrust/drag, the stop force (fixed by the z-moment, since the pin carries no
    moment about its axis) and the pin/lug-stack resultant (force plus the in-plane couple from the offset path).
  - Hinge-local components follow the fold-cycle convention.
- **Strength (`strength`):** single-lug, single-shear checks, not the clevis–tang formulas:
  - pin shear;
  - pin bending P·a/2;
  - lug edge bearing including half the couple;
  - net section and shear-out;
  - stop seat pressure and nose root bending;
  - an **FE plane-stress peak** at the hole edge (`lug_fea`).
  
  The FE uses Q9 elements and a frictionless cosine pin bearing. It is verified with a patch test, against Kirsch
  (Heywood W/d = 10 within 0.62 %), and by convergence (0.09 %). The FE gives an in-plane peak about 4× the
  net-section average: the hand net-section value alone is not conservative.
  
  All centrifugal stresses scale with Ω², so each check reports the speed at which it reaches allowable/SF.

## Results

See `reports/prototype_13in_20261118/README.md` for the four exported alternatives (A: 5.5 mm with a 50° fold;
B: 9.5 mm, twist ×0.6; C: 12.5 mm on the template blade; D: 6 mm, twist ×0.35, rejected with play), the exploration
grid and the required-offset table. Each candidate folder holds a calculation summary with every number used.

The governing check is the stop-nose root (about 2540–3220 RPM at SF 2) or Ø3 pin bending, because the full-depth
lugs place the lug mid-planes 6–9 mm apart. A Ø4 pin and a wider nose are the next levers. Joint play gives a tip
droop of 3.2–3.9 mm.

## Aerodynamic evidence

- The aero sections remain catalog `NACA2412`. The printable trailing edge (0.8 mm) makes them
  `NACA2412-te0.80mm-x0.50`.
- The retained NACA2412 polar families apply only approximately. An XFOIL family for the modified section, with
  Re about 50–200 k at 13-inch scale, is required before performance or aerodynamic hinge-load conclusions.
- The joint region (bosses, nose, the δ step) is not represented in BEM or DUST. A step of 9–13 mm at the joint is
  a large disturbance at this scale.
- The existing small-fold DUST evidence (800 mm demonstrator) says nothing about this rotor.
- **BEM in *Analiz*:** the planform is the research template `project_250` at diameter 330.2 mm with the same
  chord/twist scales and hinge, so BEM can run on it once the polar coverage fits the operating point (inputs not
  supplied).

## Measurement plan for the first print (before operating tests)

1. Hole coupon: choose the running fit for the real pin and record the printed hole diameters.
2. Weigh each printed part and the hardware. Measure the distal CG (balance on a knife edge in two directions) and
   its inertia about the pin (bifilar or compound-pendulum swing). Compare with `summary.md`.
3. Measure lug thicknesses, the assembled gap g and the radial play. Measure the tip droop and wobble with the pin
   horizontal and vertical, and compare with the play model.
4. Friction: torque to start and keep folding (a spring scale at a known radius), dry and lubricated, pin axis
   vertical and horizontal.
5. Stops: the open-stop seat (flatness, contact witness with marking paste), the folded-stop angle (the nose) and
   whether the travel matches the clearance check. Note any rubbing location and angle.
6. Only then: static centrifugal-equivalent pull test of the joint, then a spin test with a guard at a speed well
   below the reported limits. Both need the owner's motor and target speed.

## Decisions that depend on the owner

- **Maximum speed, motor and required thrust.** These set the operating loads, the strength verdicts and the BEM
  point. They are not supplied; the what-if speeds are used.
- **Printer model, material grade and process.** These replace the exploratory allowables and the default
  256 mm bed.
- **Required fold travel:** assumed 140°; the template declares 180°. A deeper fold needs a shallower nose (weaker
  stop) or a different stop.
- **Accepted deployed step:** 5.5 mm with a 50° fold, 9.5 mm on a flatter blade (3.8 in pitch), or 12.5 mm on the
  template blade (6.3 in pitch).
- **Hub/motor interface:** the hub is a placeholder (Ø30 × 12 mm, Ø5 bore).
- **Pin procurement:** a turned ISO 2341-A pin with a DIN 6799 groove, or an alternative (for example a grooved
  Ø3 shaft with two E-clips).
