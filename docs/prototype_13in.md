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

- `reports/prototype_13in_20261118/fit_kit_F1S/`: **the strengthened F1 joint, the kit to print.**
  - δ 6.5 mm, a Ø4 pin of 13.28 mm under the head, lugs 5.16/5.38 mm;
  - a stop nose 4 mm deep, reaching 4 mm ahead of the leading edge;
  - a Ø4.0–4.4 mm coupon.

  It is the default kit in the page. See *Strengthened F1 candidate* below.
- `reports/prototype_13in_20261118/fit_kit_E/`: E's joint (δ 6.0 mm, Ø3 pin, lugs 4.72/5.05 mm). It is now used for
  printer calibration only: hole shrinkage, face flatness, the friction trend. It is not evidence about F1S.
- `reports/prototype_13in_20261118/fit_kit_B/`: B's joint (δ 9.5 mm, lugs 6.92/7.30 mm), kept as a reference.
- All three kits were regenerated in this revision. The design record gained the pin-set field (`pin_nominal_mm`),
  which changes every design identity. A record made from an older copy of a kit would be refused as "another kit";
  nothing has been printed or measured yet.

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

## F1S measurement print: operator handoff (Bambu Lab P1S, Eco Smart Standard PLA)

The P1S belongs to a printer operator. `reports/prototype_13in_20261118/F1S_print_handoff/` is therefore a
**geometry-and-instructions package, not a sliced Bambu Studio project**. Nothing in it has been opened or sliced in
Bambu Studio. The operator slices with their own P1S configuration and records what they actually used. The package
contains:

- **Geometry:**
  - `3mf/01_kupon.3mf`, the **first plate**: the Ø4.0–4.4 mm hole coupon;
  - `3mf/sonra_secilecek_ciftler/02_cift_cXpXX.3mf`, one fit pair per coupon step 0.00–0.40 mm, each with two
    named parts. They sit in a separate "select later" folder: only one is printed, after the coupon test.
  - STL copies of every part in `stl/` (the coupon at the top, the pairs in the same subfolder).

  The files are in millimetres and placed in print orientation on z = 0, with the pin axis along printer Z. The
  proximal prints upright on its lug's washer-seat face. Its stub is trimmed to that plane, away from the joint. The
  distal prints **inverted** on its washer-seat face, so the running face between the lugs is a free top surface with
  no support. The guide lists each object's expected bounding box, so the operator can check scale.
- **Instructions:**
  - `BASKI_REHBERI.md`: a Turkish guide covering units, scale, orientation and the **proposed** settings. These are a
    0.4 mm nozzle, 0.20 mm layers, 3 wall loops (≈ 1.2 mm), 100 % infill, no X-Y hole or contour compensation,
    supports only from the build plate (support under the inverted distal's stop nose is expected) and never on
    holes, lug faces or the stop contact faces, and no ironing.
  - `MONTAJ_VE_DONANIM.md`: hardware requirements and the assembly checklist.
  - `BASKI_VE_OLCUM_KAYDI.md`: a proposed-versus-used settings form.
  - `00_ONCE_BENI_OKU.md`: the start-here note. It names `3mf/01_kupon.3mf` as the only part to print first and keeps
    the Ø4×14 pin decision open.
  - `OLCUM_PROTOKOLU.md`: the complete measurement protocol in Turkish, with the record fields. The package does not
    depend on the kit README.
- **Record and model data:**
  - `olcum_kaydi.json`: the measurement record (schema /2). The kit identity and the confirmed setup (printer, PLA,
    filament product) are prefilled. Nozzle, plate, manufacturer, process values and every physical measurement are
    empty.
  - `predictions.json`, `design.json`, `SHA256SUMS`.

**Coupon to pair, one decision:** print the pair at the **smallest `akıcı` coupon step**. A pair exists for every
step, so "nearest" no longer applies. If no hole runs freely, the exact pair is generated, either in the page (kit
generator with that hole clearance) or with `fit.export_kit(d, folder, clearances=(c,))`.

**Hardware stays open.** The proposed A4/316 Ø4×14 mm pin is not yet confirmed. Before assembly, check:

- **Pin diameter:** Ø4.
- **Head:** larger than the washer bore, 4.3 mm, and at most about 8.6 mm across.
- **Retention:** a DIN 6799 size 3.2 groove, or a split-pin hole.
- **Usable grip:** from under the head to the groove, at least 11.84 mm. That is the stack: two washers, both lugs
  and the 0.3 mm gap.
- **Excess grip:** target 0.1–0.4 mm over the measured stack, closed with DIN 988 shims or extra washers.

The record now carries `pin_grip_length_mm` and `washer_stack_mm`. `fit.apply` warns when the grip is too short (by more
than max(0.05 mm, 2 × resolution)), and when the float predicted from the hardware disagrees with the measured float
by more than max(0.15 mm, 4 × resolution). That tolerance covers four readings and the clip-groove slack.

**Evidence is bound to the process.** A measurement is direct evidence only when all three hold:

- the CAD identity, including the declared process, matches the kit;
- no change from the proposed settings is reported (`print_changes` is blank; hole compensation, say, makes it
  transferred);
- the specimen's actual printer, nozzle, material family, filament product, layer, wall loops and infill all match
  the process the design declares (F1S declares P1S, 0.4 mm, PLA, Eco Smart Standard PLA).

Otherwise it is "transferred": shown for exploration, while the clearance verdict keeps the worst-case model. The
reasons are listed, and the specimen's process is stored on the design (`measured_process`). A later ASA print, or a
changed process, is therefore its own experiment, even with identical CAD. Earlier record files keep their schema
and kit identity, so their applicability stays readable. A schema /1 record is refused by the current parser rather
than silently reinterpreted. A design saved with measured play before this change
(no `measured_process`) loads as transferred, with its process marked unknown.

## F1S printed-pin hinge demonstrator (temporary, hand-operated)

Before any metal pin is bought, `pyfoldable/prototype/printed_pin.py` builds a fully printable demonstrator of the
F1S short joint for hand assembly and folding trials. The package is in
`reports/prototype_13in_20261118/F1S_printed_pin_demo/`. It is a geometry-and-instructions package and has **not**
been sliced.

**Selected arrangement:**

- **Pin:** PLA with an integral head (Ø8 × 1.6 mm, inside the lugs' Ø8.6 spot face). It prints upright with the
  head on the bed, so the bearing surface is round and the layer rings run with the rotation.
- **Retention:** a flat PLA C-clip pushed sideways into a groove above the distal lug, entirely outside the bearing
  span. The clip prints flat, so its arms flex within the layers. It is sized for PLA (1.6 mm thick, 1.3 mm arms,
  0.3 mm snap on a Ø3.0 groove root) and is not a scaled DIN 6799. One clip fits all three pins.
- **No washers.** The head and the clip bear on the lugs' washer-seat faces, which print on the bed.
- **Joint:** the F1S fit-test section (same pivot, lugs, stop, blade sections, and the metal-design hole Ø4.2),
  trimmed like the metal kit's fit pair but without its clamp block and load tab
  (`cad.print_trimmed_stubs`, shared with `cad.fit_fixture`).

**Derived from the regenerated solids:**

- lug stack q1 − p0 = 10.84 mm;
- groove 0.15 mm above the stack, 1.8 mm wide;
- grip references from the head underside: groove near flank 10.99 mm (the value measured in the trial), far flank
  12.79 mm;
- pin length 15.59 mm.

**End play** (open assembly, proximal on the head), reproduced from the solids by translating the distal:

- **total end play: 0.65 mm**;
- of which the **nominal inter-lug gap is 0.30 mm**. This is the metal design's running gap, and the only travel
  toward the proximal;
- and the **one-sided, clip-side assembly allowance is 0.35 mm** above the nominal pose: 0.15 mm for thicker printed
  lugs plus 0.20 mm of clip slack in the groove.

The clip still fits if the printed lugs are up to 0.35 mm thicker in total (end play then shrinks by as much). The
clip-side room lets the distal rock more than in the metal model (3.1°). The bounds:

- the conservative face limit (the metal model's convention, total end play / R_b) gives up to 4.4–6.8° depending on
  the pin;
- assuming the distal pivots under the clip, (g + a)/(R_b + r_clip), it gives 4.4–4.5°.

At the tightest pose the nominal 0.48 mm gap becomes negative under full rocking with either bound (estimated with the
tip tilted down, dropping the inter-lug gap at the boss edge). So contact is expected when the distal is pressed or
tilted. The trial records whether contact occurs with and without pressing; this is a
geometric observation.

The metal reference stack (about 11.84 mm with two washers) is a separate configuration and is not copied.

**Fit experiment:** three pins, Ø3.80, Ø3.90 and Ø4.00 (1, 2 and 3 notches on the head), plus the Ø4.0–4.4 hole
coupon. The joint hole stays at the metal design clearance: the pin is chosen to fit the hole, and neither the hole
nor the metal clearance is changed because a printed pin fits.

**Checks** (`printed_pin.check`, on the actual solids):

- no interference between pin, clip and either stub at the open, tightest and folded poses;
- the pin's path from below and the clip's sideways path are free;
- hand-fold travel is 143° by the column sweep, ending one step before the stop nose meets the proximal at 144°;
- the tightest intermediate pose is θ = −103°, with a 0.48 mm vertical gap.

**Package:**

- **First print**, two plates and nothing else:
  - `3mf/01A_kucuk_parcalar.3mf`: the coupon, the three pins and three clips; no supports, no brim;
  - `3mf/01B_mafsal_cifti.3mf`: the joint pair, with tree supports from the plate and a 3 mm brim.
- **Geometry files:** STL per part in print orientation, and STEP per part in the assembly frame.
- **Views:** exploded assembly, a section through the pivot, and plan views at open, tightest and folded.
- **Turkish documents:** start-here, print guide, assembly, a hand-trial protocol (insertion and removal, rotation,
  stop seating, fold, interference, clip retention, declared cycles, photos; no force measurement), and the
  proposed-versus-used form.
- **Record:** a trial record template (`pyfoldable.prototype.printed_pin_trial/1`).

**Evidence:** `printed_pin.classify` labels a trial record a **printed-pin observation**.

- It is shown on the *Prototip* page and never applied to a design.
- It is not evidence for the metal-pin assembly's play, friction, strength, contact loads or allowable RPM.
- Observed contact is geometric, not a quantitative clearance acceptance.
- The metal kit's record and this record cannot be swapped: the schemas differ, and both parsers fail closed.
- The demonstrator has no operating envelope (`operating_envelope` and `rpm_limit` are null) and inherits no RPM
  limit.
- A metal pin, another retention method or ASA needs the relevant measurements again.

Physical qualification: false.

## Next full-size prototype: from the measurements to the print

1. **Coupon (F1S kit, Ø4.0–4.4 mm).** Rate the holes and pick the smallest running fit. E's coupon may also be
   printed to calibrate the printer; it is not required.
2. **Fit pair (F1S kit)** at that clearance: assemble it with the Ø4 pin set, and measure a, Δ (≥ 3 repeats),
   friction, stop seating, the folded-stop angle and the masses. Fill the record.
3. **Apply the record** with kit F1S selected. The basis is direct. Build F1S and read the clearance tab.
   - **At δ = 6.5 mm**, F1S's nominal gap at the governing point is 0.58 mm. The verdict needs roughly
     a + 24 mm · φ ≤ 0.58 mm − margin; with the typical margin, a + 24 mm · φ ≤ 0.41 mm, for example a = 0.1 mm and
     φ ≤ 0.75°.
   - **If it passes**, export F1S from the page with the record applied. Its `design.json` carries the measured play
     and its basis. Print the full rotor: the hub with both proximal segments, two distal segments and two Ø4 pin
     sets.
   - **If it fails**, the page reports the with-play offset (at most about 7.5 mm with the worst-case model). Choose δ'
     (rounded up to 0.5 mm), generate the fit kit for F1S at δ' in the page, print and measure it, and repeat this
     step. The record from δ = 6.5 mm is only transferred evidence for δ'.
4. **Stop.** If the stop does not seat, or the folded stop is short of the required travel, correct the stop
   geometry and repeat steps 2 and 3 before any full-size print.
5. **Blade shape: the main trade-off** (equal thrust at equal inflow, fail-closed BEM; see the decision section in
   `docs/prototype_13in_aero.md`):
   - E (6.0 mm) needs about ×1.22 the RPM and ×1.11 the power of the unmodified 13×5.5-class blade.
   - F1 (6.5 mm; zone chord ×0.85, twist ×0.6) needs about ×1.15 and ×1.06.
   - F2 (8.5 mm; zone twist ×0.7) needs about ×1.10 and ×1.04.
   - The reference needs 10 mm.
   - All four fold to about 206 mm at 140° (89 mm wide), and the offset needed is the same at 110° and 140° except
     for E.
6. **Structure first.** Every useful operating point is above every option's SF 2 limit (about 2800–3300 RPM) with
   the Ø3 pin and the 4 mm nose. A stronger joint is the next mechanical change, whatever offset is chosen.
7. **Recommended next full-size candidate:** F1, at δ 6.5 mm with a 140° fold; its strengthened joint is F1S (below).
   - **Why F1:** it is 0.5 mm above the 5–6 mm target, keeps the 206 mm folded envelope, and halves E's
     aerodynamic penalty. Structurally it is close to E.
   - **Measurement:** E's kit stays the first physical experiment, because its joint is nearly F1's (same pin, boss
     and gap; δ 6.0 against 6.5). Its play transfers to F1 for exploration only. Before a full F1 rotor, print F1's
     own fit pair (the page's kit generator) for the direct verdict.
   - **If the owner rejects F1:** F2 is the choice if a larger step is acceptable; E if the step must stay ≤ 6 mm.
   - **Not settled by the model:** the static performance (diagnostic only) and the joint-step flow effect
     (unresolved). A printed A/B thrust test settles both.

## Strengthened F1 candidate (F1S): one coherent joint

**Aerodynamic baseline: F1.** Twist ×0.86, with a ±45 mm hinge zone (chord ×0.85, twist ×0.6), at δ = 6.5 mm and a
140° required fold. 6.5 mm is a **nominal** offset:

- the nominal requirement is 6.42 mm, a 0.58 mm gap at 106°;
- with the worst-case play model it is 7.46 mm (−0.96 mm at 140°, `compromise_options.csv`).

That with-play verdict is decided only by play measured directly on F1S's own fit pair. At 6.5 mm it needs roughly
a + 24 mm · φ + k·u ≤ 0.58 mm.

**Sizing in the actual assembly** (`study.joint_sizing`, `F1S_sizing/joint_sizing.csv`): 29 variants, each built
and swept over the full fold. Each row records:

- every single-lug check and its speed limit at SF 2;
- the folded stop;
- the clearance needed;
- the centrifugal seating, the stop force, mass and printability.

What the grid shows:

- **Nose depth breaks the fold.** A deeper stop nose (5 or 6 mm instead of 4 mm) is stronger in bending, but it
  meets the proximal earlier. The folded stop falls from 144° to 138° and 134°, so it would block the required 140°.
  **The nose depth stays at 4 mm.**
- **Nose extension works.** Extending the nose and pad 4 mm ahead of the leading edge, instead of 2 mm, doubles the
  nose width. It also lengthens the lever from the pin, so the stop force drops from 66 N to 54 N at 6000 RPM. The
  nose-root limit rises from 3100 to 4700 RPM, and the fold is unaffected (144°).
- **Then the pin governs.** With the stronger stop, the Ø3 pin limits the joint in bending (about 3900 RPM). A Ø4 pin
  raises that to about 6050 RPM.
- **Ø5 gains nothing.** The bigger hole in the same boss lowers the lug's hole-edge peak limit (5540 against
  5750 RPM), and it adds 2 g.
- **A larger boss (R_b 6.5 mm) cannot be built.** It leaves no blade under the stop pad at the joint's leading edge.

**The chosen joint (F1S)**, `study.F1S_PARAMS`, in `F1S_candidate/` and `fit_kit_F1S/`:

| Item | F1S | F1 (Ø3 pin, nose 2 mm ahead) |
|---|---|---|
| Pin set | ISO 2341-A Ø4 (head Ø6 × 1), 13.28 mm under the head; 2 × DIN 433 4.3 × 8 × 0.5; DIN 6799 size 3.2 | Ø3 set |
| Hole, boss, relief | Ø4.2 (clearance 0.2, chosen from the coupon), R_b 5.5, relief 6.1 mm | Ø3.2, 5.5, 6.1 |
| Lugs, gap, stack | 5.16 / 5.38 mm, g 0.3, stack 10.84 mm | about 4.9 / 5.1 mm |
| Stop | nose 4 mm deep, 4 mm ahead of the LE; pad 4 mm | nose 4 mm deep, 2 mm ahead |
| Folded stop / required travel | 144° / 140° | 144° / 140° |
| Seating | distal CG 3.23 mm aft of the pin: seated at every speed | seated |
| Mass | blade 25.41 g (distal 3.53 g, pin set 1.95 g) | 24.5 g |
| Limits at SF 2, centrifugal only | nose root 4700, lug FE peak 5750, pin bending 6050, bearing 6380, net section 7880 RPM | nose root 3100, pin bending 3840 RPM |

**Tolerances:**

- The hole clearance comes from the F1S coupon (Ø4.0–4.4 mm). The fit pair is exported at 0.1, 0.2 and 0.3 mm.
- The lug gap stays at 0.3 mm. With about ±0.1 mm z variation per printed face, a 0.2 mm gap could bind.
- The verdict margin adds k = 2 times the measured play uncertainty and the print variation.

E's kit can calibrate the printer (hole shrinkage, face flatness, friction trend). It is neither a prerequisite for
F1S nor evidence about it.

**Operating envelope** (`F1S_candidate/operating_envelope.csv`): the highest speed at which every check holds at SF 2
and the distal stays seated. The loads are centrifugal plus the distal's own BEM thrust and in-plane drag. The
assumptions are the declared exploratory PLA allowables, the steel pin values and ISA sea-level air; the table is
for one rotor with two blades.

| Condition | F1S max RPM | Inflow V | Rotor thrust | Shaft power | Limited by | F1 baseline max RPM / thrust |
|---|---|---|---|---|---|---|
| J 0.20 (fail-closed) | 4750 | 5.2 m/s | 3.61 N | 39 W | stop-nose root | 3125 / 1.42 N |
| J 0.25 (fail-closed) | 4740 | 6.5 m/s | 2.86 N | 35 W | stop-nose root | 3125 / 1.04 N |
| J 0.30 (fail-closed) | 4730 | 7.8 m/s | 2.00 N | 29 W | stop-nose root | 3120 / 0.65 N |
| static (clamp diagnostic, **not supported**) | 4760 | 0 | 5.94 N | 46 W | stop-nose root | below polar coverage |

Notes on the envelope:

- **Supported band.** The polar data starts at about 3000 RPM, so the fail-closed band is 3000–4750 RPM.
- **Distal loads at the limit.** At 4750 RPM the distal carries about 1.0 N of thrust and 0.18 N of drag per blade,
  and the stop carries 33 N.
- **Not included.** Fatigue, creep, impact, gusts and the joint-step flow effect are not in these numbers.

### Remaining trade-off

- **Offset.** 6.5 mm nominal. It becomes about 7.5 mm if the measured play is as large as the worst-case model.
  The measured play decides; a design at 7.5 mm would make the measurement moot but is 1.5 mm above the target.
- **Folding.** 140° is kept, because the nose depth is fixed at 4 mm. Strengthening further by nose depth would cost
  travel (138° at 5 mm); by extension it adds a larger bump ahead of the leading edge.
- **Performance.** F1's blade needs about ×1.15 the RPM and ×1.06 the power of the unshaped 13×5.5-class blade at
  equal thrust and inflow. The strengthened joint lifts the structural speed from about 3100 to about 4700 RPM, so
  F1S can reach roughly 2.5 times F1's thrust within the same safety factor. The 4 mm nose ahead of the leading edge
  is a local aerodynamic disturbance that no model here resolves.

### Owner information needed to turn the what-if cases into an operating requirement

- **Motor and drive:**
  - the motor model and KV;
  - its rated and peak current or power;
  - the ESC and the battery (cell count and voltage range).

  With these, `core.motor_bem_coupling` gives the loaded RPM and torque on F1S's BEM model.
- **Thrust requirement:**
  - the required thrust per rotor for static or hover, and for the flight case(s);
  - the aircraft mass;
  - the number of rotors;
  - the thrust-to-weight margin.
- **Flight conditions:** the forward-speed range, so J; altitude or temperature; the duty cycle (time at maximum
  power).
- **RPM limit:** the maximum RPM, including fault or over-speed cases the controller allows.
- **Folding scenario:** whether the blade folds in flight or only for stowage, and the minimum deploy RPM the
  friction measurement must meet.
- **Structural policy:** the required safety factor, the fatigue life (cycles or hours), and the printer and
  filament data that replace the exploratory allowables.

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
