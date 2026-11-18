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

### Required offset: a limit of the blade shape, not of the mechanism

A backward fold about a pin near the quarter chord carries every distal point through the direction straight
inboard of the pin, so the whole distal must pass above (δ > 0) or below the proximal.

**The governing contact.** Beyond about 105–110° of fold, the distal trailing-edge root passes over the proximal
leading-edge region about one chord inboard of the pin. In the CAD sweep, this point lies about 22 mm from the pin,
near y ≈ 77 mm. Positive twist lifts the leading edge, so:

- the trailing edge is the lowest edge of the upper segment, at z_B − 0.75 c sin β;
- the leading edge is the highest edge of the lower segment, at +0.25 c sin β.

The offset must therefore clear the **whole** vertical extent of the sections near the joint. Half of it is not
enough; an earlier version of this note said half, and that was wrong. The budget, checked against every swept
variant in `reports/prototype_13in_20261118/study/offset_study.csv`:

    δ_req ≈ H_j + c_b + r        H_j = vertical extent of the joint section ≈ c_j sin β_j + t_j cos β_j

Here c_b is the required body clearance (0.5 mm). The residual r is a few tenths of a millimetre, because the
proximal section one chord inboard is taller. Split into two parts:

- **mechanism floor**, t_j cos β_j + c_b plus the joint play: what this topology needs even for a flat blade.
  It is about 4.1 mm with the 3.7 mm thick printable NACA2412 section at the joint. The flat-blade variant
  (twist 0) confirms it in CAD: 4.1 mm for a 140° fold, with a blade term of about 0.
- **blade term**, c_j sin β_j + r: set by the chord and pitch near the joint. On the template planform (30.4 mm
  chord, 17° at r_j, 7.5 in local pitch) it is about 7 mm, which gives 11.2 mm. The 5–6 mm target is therefore a
  limit of the template blade, not of the one-lug, one-pin mechanism.

**What does not help:**

- **Pin chordwise position.** The crossing happens for any pin ahead of mid-chord. Moving the pin 3 mm aft lowers
  the requirement by only about 0.2 mm, but the centrifugal seating moment at 6000 RPM falls from about 600 to
  33 N·mm. At 6 mm aft the distal no longer seats. Moving the pin forward leaves no room for the stop ahead of the
  relief ring. The pin stays at the quarter chord.
- **A narrow hinge-zone change** (±30 mm). The proximal section about one chord inboard keeps its height.
- **An asymmetric zone with a short outboard side.** At 120–140° the distal sections 20–45 mm from the joint also
  cross the proximal.

**What does help:**

- **Lower pitch over the crossing region, on both sides of the joint.** On a 13×5.5-class blade (twist ×0.86), a
  ±45 mm cosine-blended zone with chord ×0.85 and twist ×0.45 brings the 140° requirement to 5.9 mm (5.2 mm for
  90°). This is candidate E, set at δ = 6.0 mm. The cost is the local pitch: about 2.8 in at the joint, rising to about 4.1 in at 0.75R.
  The aerodynamic screening ([prototype_13in_aero.md](prototype_13in_aero.md)) puts a number on it. It uses real
  XFOIL polars of the printable sections and BEM, for the blade shape only; the joint step is unresolved:
  - fail-closed, at J = 0.2 E gives 40–48 % less thrust than the unmodified 13×5.5-class blade, for 40–43 % less
    power;
  - at J = 0.3 E gives 58–71 % less thrust;
  - static (diagnostic tier), E needs about ×1.18 the RPM and ×1.07 the power for the same thrust.
- **A shorter required fold.** The offset needed at each fold is plotted per candidate in
  `study/alignment_envelope_*.png`.
- **A larger joint radius.** At r_j = 110 mm the template blade needs 9.3 mm, at the cost of a larger folded
  radius.

**Joint play** adds about 1.0–1.2 mm at 140° with the worst-case model (φ = 3.1°), and up to 3 mm near 180°. The measured play from the fit pair replaces
that model; see *Measurement prototype*.

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

  This model is a worst case: it adds the axial float to the full tilt. When a fit record is applied, the measured a
  and φ replace it, and the page and summary name the source.
- **Solid construction robustness (this revision):**
  - The loft sections are evenly spaced, about 4 mm apart. Irregular station-plus-grid spacing with steep twist
    gradients made OpenCASCADE booleans with the bosses return an empty intersection.
  - Full-depth lug faces stand 0.2 mm proud of the blade's extreme point. A face tangent to the blade surface did
    not fuse.
  - In both failures the separate-body check (one valid solid per part) stopped the build; nothing was exported.
  - Candidates A–D were generated before this change at commit `8dac1dc`. Regenerating them now gives slightly
    different solids, with lugs 0.2 mm thicker.
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

Candidate E against the unmodified 13×5.5-class blade is screened in [prototype_13in_aero.md](prototype_13in_aero.md).
The polars are real XFOIL output for the chord-dependent printable-section family. The BEM covers the blade-shape
effect only. The joint-step effect is unresolved: the DUST route rejects an axial offset, and strip theory cannot
represent the step. The decisive next step is a printed A/B thrust-stand test, continuous E against stepped E. The
bullets below record the first increment's state.

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

## Measurement prototypes (before any full-size print)

Two kits are committed. Each holds:

- the hole coupon;
- the short joint-fit pair at CAD hole clearances 0.1/0.2/0.3 mm, with a clamp block on the proximal stub and a load
  tab on the distal stub, its hole 30 mm from the pin axis;
- the protocol (`README.md`), the model predictions (`predictions.json`) and the record template.

The kits:

- `reports/prototype_13in_20261118/fit_kit_E/`: **E's own joint**, the next compact candidate. δ 6.0 mm, lugs
  4.72/5.05 mm, a pin of 12.5 mm under the head, E's stop nose and pad, printed with the rotor plane on the bed.
- `reports/prototype_13in_20261118/fit_kit_B/`: B's joint (δ 9.5 mm, lugs 6.92/7.30 mm), kept as a reference.

Choosing a kit does not select that candidate as the powered propeller. Each kit measures pin fit, axial float,
tilt, break-away friction, open-stop seating, the folded-stop angle and the part masses. Measure the axial float and
Δ at least three times (reassembling between repeats; over two printed pairs if possible). Record the count, the means,
the ranges and the instrument resolution.

**The record.** Load it in *Prototip → Ölçüm prototipi* (choose the kit), or with `fit.parse` / `fit.apply`:

- It is refused if anything is missing, out of range, unknown or hostile, or if it belongs to another kit (design
  SHA-256).
- Applying it sets the hole clearance to the printed one. It stores in the design record the measured axial float a,
  the tilt φ = max(0, Δ − a)/(2L), their standard uncertainties, the print variation, the record's SHA-256 and the
  **basis**.

**Direct versus transferred play:**

- **Direct:** the record comes from this design's own kit, with the same identity apart from the hole clearance. The
  measured play then **sets the print-clearance verdict**, with an expanded uncertainty margin. The worst-case gap at
  distance s from the pin is

      g(s) − a − φ s − k √(u_a² + (s u_φ)² + 2 u_print²),   k = 2

  where:
  - u_a and u_Δ each combine the reading resolution (r/√12·√2 for a difference of two readings) with the repeat range
    R / d₂(n), the variation a new print can show, so it is not divided by √n;
  - u_φ = √(u_Δ² + u_a²)/(2L);
  - u_print = max(layer/√12, largest lug-thickness deviation/√3) is the print variation of each of the two facing
    surfaces.

  With typical inputs the margin is about 0.17 mm, and the print variation dominates. Typical inputs here: a 0.01 mm
  dial, three repeats with 0.02/0.05 mm ranges, 0.2 mm layers.

  The margin is slightly conservative. φ is computed from a, so treating a and φ as independent overstates the
  variance by about u_a²·s/L.
- **Generated kits.** A kit generated in the page for the editor's design can be selected as the record source. Its
  record is then direct evidence for exactly that design.
- **Transferred:** the record comes from any other design, for example B's kit applied to E, or E's kit after δ
  changes. The measured play is shown **for exploration only**, as "aktarılmış". The verdict keeps the worst-case
  model.

A change of δ, lug thickness, pin, boss or planform is a different joint. Measure its own fit pair: the kit generator
in the page writes one in a minute or two.

Warnings name:

- a design that is not the kit's;
- a stop that does not seat;
- a coupon that disagrees with the printed clearance;
- zero play, or Δ smaller than a;
- a folded stop short of the required travel;
- a mass more than 15 % off the model.

The break-away torque gives the speed at which the centrifugal stop moment overcomes zero-load friction.

## Next full-size prototype: from the measurements to the print

1. **Coupon (E kit).** Rate the holes and pick the smallest running fit.
2. **Fit pair (E kit)** at that clearance: assemble it and measure a, Δ (≥ 3 repeats), friction, stop seating, the
   folded-stop angle and the masses. Fill the record.
3. **Apply the record** with kit E selected. The basis is direct. Build E and read the clearance tab.
   - **At δ = 6.0 mm**, E's nominal gap at the governing point is about 0.6 mm at about 24 mm from the pin. The
     verdict needs roughly a + 24 mm · φ ≤ 0.6 mm − margin; with the typical margin, a + 24 mm · φ ≤ 0.44 mm, for
     example a = 0.1 mm and φ ≤ 0.8°.
   - **If it passes**, export E from the page with the record applied. Its `design.json` carries the measured play and
     its basis. Print the full rotor: the hub with both proximal segments, two distal segments and two pin sets.
   - **If it fails**, the page reports the with-play offset. Choose δ' (rounded up to 0.5 mm), generate the fit kit for
     E at δ' in the page, print and measure it, and repeat this step. The record from δ = 6.0 mm is only transferred
     evidence for δ'.
4. **Stop.** If the stop does not seat, or the folded stop is short of the required travel, correct the stop
   geometry and repeat steps 2 and 3 before any full-size print.
5. **Blade shape: the main trade-off.**
   - E's compact step costs aerodynamics. In the static diagnostic, E gives about 28 % less thrust at equal RPM,
     and needs about ×1.18 the RPM for equal thrust.
   - Before E reaches structurally safe speeds, the stop-nose root limits it to about 3300 RPM at SF 2.
   - If the owner does not accept that, the alternative is the unmodified 13×5.5-class blade, at about 10 mm for
     140°; it needs its own fit kit.
   - Either way, a thrust-stand A/B test (continuous E against stepped E, and E against the reference) resolves
     what the strip-theory model cannot (`docs/prototype_13in_aero.md`).

**Compactness by fold angle.** The *Prototip* page lists, for each fold angle:

- the envelope diameter of the folded rotor, and its length and width;
- whether the 4 mm nose, as the folded stop at 144°, allows that angle;
- the offset needed, nominal and with play.

The table is in the *Açık hizalama ve katlı zarf* tab, and is also given in the PR.

Owner decisions remain: the required fold travel, the pitch, the speed, the motor and the thrust.

## Measurement plan for the first print (before operating tests)

1. Hole coupon and fit pair: follow `fit_kit_E/README.md`. E is the next compact candidate; `fit_kit_B/` is the
   reference. The coupon picks the running fit; the fit pair gives play, friction and stop seating.
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
- **Accepted deployed step and blade shape:**
  - 6.0 mm with lower pitch near the joint (E);
  - about 10 mm on a 13×5.5-class blade without shaping;
  - 9.5 mm on a flatter blade (B, 3.8 in at 0.75R);
  - 12.5 mm on the template blade (6.3 in at 0.75R);
  - 5.5 mm with a 50° fold (A).
- **Hub/motor interface:** the hub is a placeholder (Ø30 × 12 mm, Ø5 bore).
- **Pin procurement:** a turned ISO 2341-A pin with a DIN 6799 groove, or an alternative (for example a grooved
  Ø3 shaft with two E-clips).
