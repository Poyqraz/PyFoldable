# Printable 13-inch prototype: aerodynamic screening of candidate E (2026-11-18)

Unqualified numerical screening. `physical_qualification` is false.

No blade or solver parameter was tuned to a result. The polar grid (Reynolds levels, angle range) was
revised only for solver convergence and coverage; see [Grid history](#grid-history).

Code: `pyfoldable/prototype/aero.py`. Tests: `tests/prototype/test_prototype_aero.py`.
Outputs: `reports/prototype_13in_20261118/aero/`. Prototype context: [prototype_13in.md](prototype_13in.md).

## Summary

- **The blade-shape effect is computed. The joint-step effect is not.** Both blades are modelled fully
  deployed (fold 0) as continuous strip-theory blades. The 6 mm deployed step at the joint is outside
  strip theory: its effect is unresolved, not zero (see [Joint step](#joint-step-unresolved)).
- **The polars are real XFOIL runs of the printable section, not a proxy.** They come from the repository's
  provider route with the pinned XFOIL 6.99 executable. They are numerical evidence only.
- **Fail-closed, the BEM answers only J = 0.2–0.4, at every what-if RPM from 3000 to 8000.** In that range:
  - at J = 0.2, E gives 40–48 % less thrust than the reference for 40–43 % less shaft power, and the two
    efficiencies are within ±0.04;
  - at J = 0.3, E gives 58–71 % less thrust for 51–55 % less power, and E's η is 0.09–0.20 lower;
  - E reaches zero thrust near J ≈ 0.36–0.38. The reference's thrust is still positive at J = 0.4.
- **Static and low-J points are not fail-closed.** They come from the clamp diagnostic, where the
  selected roots lie inside the polar data but the choice of branch is unverified. At equal RPM
  (4000–8000), that diagnostic gives E about 28 % less static thrust for 33–36 % less power. Static
  figure of merit is 0.65–0.70 for E and 0.71–0.74 for the reference.
- **Matching the reference's static thrust (diagnostic):** E at 7000 RPM gives 2 % less thrust than the
  reference at 6000 RPM, for 2.5 % more power. Scaling to exactly equal thrust with C_T and C_P gives
  n ×1.18 and power ×1.07.
- **The whole difference comes from the reshaped span, 54–144 mm (0.33R–0.87R).** Both blades are
  identical outside it.
- **The what-if speeds are not structurally cleared.** The prototype's governing strength check is the
  stop-nose root, at about 2540–3220 RPM at SF 2 (see [prototype_13in.md](prototype_13in.md)). Every
  speed here (3000–8000 RPM) is a what-if, at or above that limit.

## Geometries

Both blades are built exactly as `study.run_report` builds them (`aero.designs`):

- `base = with_changes(default_design(root), connection.axial_offset_mm = 6.0)`;
- **E** = `explore.candidate_design(base, root, study.E_PARAMS)`;
- **reference** = `candidate_design(base, root, {"planform.twist_scale": 0.86})`.

Common to both: diameter 330.2 mm, 2 blades, section `NACA2412-te0.80mm-x0.50`.

| r [mm] | r/R | chord E / ref [mm] | twist E / ref [°] | local pitch E / ref [in] |
|---:|---:|---:|---:|---:|
| 33.0 | 0.20 | 36.98 / 36.98 | 26.66 / 26.66 | 4.10 / 4.10 |
| 54.5 | 0.33 | 35.23 / 35.26 | 22.67 / 22.74 | 5.63 / 5.65 |
| 76.5 | 0.46 | 30.60 / 33.09 | 13.58 / 18.73 | 4.57 / 6.42 |
| 99.0 (joint) | 0.60 | 25.83 / 30.39 | 6.58 / 14.63 | 2.83 / 6.39 |
| 123.8 | 0.75 | 22.85 / 24.44 | 7.68 / 10.11 | 4.13 / 5.46 |
| 143.6 | 0.87 | 17.83 / 17.85 | 6.91 / 6.93 | 4.30 / 4.32 |
| 161.8 | 0.98 | 10.57 / 10.57 | 4.30 / 4.30 | 3.01 / 3.01 |

`aero.blade_geometry` converts the stations (mm, mm, °) to the SI `BladeGeometry` the BEM uses:
r/R, chord in m, twist in rad. The BEM interpolates linearly between stations, as `design.section(r)` does.

## Section polars (real XFOIL)

### Route and provenance

XFOIL is not on `PATH`. The repository's configured route is `XfoilProvider` with an explicit executable,
the same route the operator launchers use (`examples/research_deploy_polar_data.py`). The executable is
the pinned XFOIL 6.99 build in the operator bundle `~/pyf-work/xfoil/preflight`.

Before any launch, `aero.xfoil_provider` checks three files against
`configs/polars/RESEARCH_AXIAL_800_DEPLOY_V3.json`:

| File | SHA-256 |
|---|---|
| executable | `d1076680…b136a7` |
| `osmapDP.dat` | `2f6b3c63…45d948c4` |
| build record | `da2c4a20…dd22121` |

It refuses to run if any of them differs, if the platform is not Linux x86_64, or if `LD_PRELOAD` or
`LD_LIBRARY_PATH` is set. Nothing from an upload or from outside the repository builds the command. The adapter's argument-list subprocess, its
temporary directory and its timeout are unchanged.

Solver settings come from the same declaration:

- n_crit 9, free transition (`xtr` 1/1), 160 iterations, 30 s timeout, repanelling;
- one attempt per cell, a cold process per cell, angle sweep ascending;
- α = −6…12° in 2° steps.

Each family is generated with `generate_polar_family_batch` (collect_all / complete_axes), one plan per
Mach level. A failed cell is retained in the record and never repaired.

`polars_printable_section.json` records, for every family:

- the coordinates, the coordinate SHA-256 and t_TE/c;
- the planned cells and every failure, with the failing angle;
- the complete tables, the provider identity and the pinned hashes;
- the settings, and the SHA-256 of the declaration, the adapter, the generator and `cad.py` at generation time.

Each table also carries the operator executable path, as the retained catalog evidence in `reports/` does.

When the record is reused, two checks run:

- **`check_record`** compares the record with the current route: the declaration and adapter bytes, the
  pinned hashes, the provider, the settings, and every table's source (`xfoil-subprocess:6.99`), scenario
  and grid. A synthetic, foreign or stale-settings record is refused.
- **`families_from_record`** compares each family with the current `cad.printable_profile` coordinates. If
  the section has changed, the file is refused; regenerate it.

The generator and `cad.py` hashes describe the sources at generation time, so they are recorded but not
compared. Hashes identify content; they do not authenticate it.

`xfoil_provider` re-checks the pinned bytes after the runs. It sets `OSMAP` only while it is in use.

### A chord-dependent family

The trailing edge has a fixed physical thickness of 0.8 mm, so t_TE/c grows as the chord shrinks. XFOIL
therefore ran five sections, each with its own identity `NACA2412-te0.80mm-x0.50@c<chord>mm`. The chords
are the shared root and tip station chords plus three interior chords.

| Chord [mm] | t_TE/c | Coordinates SHA-256 | Cells complete / planned | Re covered per Mach row (M 0 / 0.15 / 0.30 / 0.45) |
|---:|---:|---|---:|---|
| 36.98 | 2.2 % | `b2a66f2d74fb…` | 50 / 60 | 25–250k / 25–200k / 25–250k / 25–300k |
| 30.00 | 2.7 % | `055351e0d9ac…` | 52 / 60 | 25–300k in every row |
| 23.00 | 3.5 % | `78a660d05c80…` | 49 / 60 | 25–250k / **50**–300k / 25–300k / 25–300k |
| 16.50 | 4.8 % | `3a9e8bb16450…` | 48 / 60 | 25–300k / 25–300k / 25–**185k** / 25–300k |
| 10.57 | 7.6 % | `ad2d7cad70be…` | 49 / 60 | 25–300k / 25–300k / 25–300k / **50**–300k |

The planned grid has 15 Reynolds levels (25k–300k) × 4 Mach levels (0, 0.15, 0.30, 0.45) × 5 chords, so
300 cells. Of these, 248 are complete and 52 failed. Each failure is a single non-converged angle,
usually 12° (stall onset at low Re) or an isolated angle; all are listed in the record.

The chord dependence matters. At Re 90k and M 0.15, c_d(4°) is:

- 0.0189 at c = 36.98 mm (c_l/c_d 38.6);
- 0.0206 at 23 mm (35.9);
- 0.0295 at the 10.57 mm tip chord (25.7).

The spanwise schedule (`aero.schedule`, the core `SpanwisePolarSchedule`) anchors each family at the
radius where the blade's own chord equals the family chord:

- **E:** 33.02, 78.82, 122.53, 146.96, 161.80 mm;
- **reference:** 33.02, 100.64, 129.80, 146.96, 161.80 mm.

The two blades therefore use the same section family consistently: E's ×0.85 chord in the joint zone gets
the thicker-TE sections. The coefficients are blended linearly in radius between anchors. Where a station
kink lies between two anchors, this blend is only approximately linear in chord.

### Reynolds and Mach the rotor sees

These are `aero.envelope_rows`: no induction, W = √((Ωr)² + V²), ISA sea level (ρ 1.225 kg/m³,
μ 1.789e-5 Pa·s, 288.15 K). The rows are the reference at J = 0; E differs only inside the zone.

| r/R | chord [mm] | 3000 RPM: Re / M | 6000 RPM: Re / M | 8000 RPM: Re / M |
|---:|---:|---|---|---|
| 0.20 | 37.0 | 26k / 0.030 | 53k / 0.061 | 70k / 0.081 |
| 0.33 | 35.3 | 41k / 0.050 | 83k / 0.101 | 110k / 0.134 |
| 0.60 | 30.4 | 65k / 0.091 | 129k / 0.183 | 173k / 0.244 |
| 0.75 | 24.4 | 65k / 0.114 | 130k / 0.229 | 174k / 0.305 |
| 0.98 | 10.6 | 37k / 0.149 | 74k / 0.299 | 98k / 0.398 |

Over 3000–8000 RPM and J ≤ 0.5, the envelope is Re 26k–179k and Mach up to 0.40. A test asserts that
the polar grid contains this envelope.

### Grid history

Selection was made by solver convergence only, never by coefficient values. XFOIL is deterministic, and
cells shared between runs are bit-identical:

- attempts 2 and 3: 97 of 97;
- attempt 3 and the final grid: 213 of 213;
- the final grid regenerated after the review fixes: 248 of 248.

Only attempt 1's record is retained, because its angle sweep differs. The cells of attempts 2 and 3 are
reproduced exactly inside the final grid, so their records were not kept.

1. **Attempt 1:** one rectangular plan per chord, α −8…14°, 6 Re levels. It lost 5–9 cells per chord,
   mostly at the −8° cold start or at 12–14°. Because the plan was rectangular, whole rows were dropped.
   The record is retained as `polars_attempt1_rectangular_failed.json`, and no BEM run used it.
2. **Attempt 2:** α −6…12°, one plan per Mach row, 6 Re levels. Isolated failures left some rows short
   (for example 60–250k). Every 3000 and 7000–8000 RPM point in the J = 0.2–0.4 window failed on
   Reynolds bounds.
3. **Attempt 3:** 13 levels. The 16.5 mm family's M 0.30 row ended at 140k, so 7000–8000 RPM still failed.
4. **Final:** 155k and 185k added. Its record and outputs are the ones reported here.

## BEM method

- **Solver:** `pyfoldable.core.bem_rotor.solve_bem_rotor`, unchanged.
  - 40 midpoint annuli over the declared station span, 33.02–161.80 mm (0.20R–0.98R). The hub
    (15–33 mm) and the last 3.3 mm to the tip are outside the span. They are identical for both blades.
  - Prandtl tip loss on, root loss off, rotational augmentation disabled.
  - `loading_branch = "signed_nonreversed"`. As J rises, the outer and joint sections unload first. With
    `positive_only`, the whole rotor would fail at the first locally negative annulus.
- **Speeds:** what-if 3000–8000 RPM (`design.operating.what_if_rpm`). The owner has supplied no maximum
  RPM. J = V/(nD) = 0…0.5. Atmosphere is ISA sea level, an assumption.
- **Fail-closed tier (`bounds="error"`):** this is what the application uses. A point fails as soon as any
  polar query leaves the data, including the bracket scan. It stays in the table with its reason
  (`bem_comparison.csv`).
- **Clamp diagnostic (`bounds="clamp"`):** not fail-closed. It is reported separately
  (`bem_clamp_diagnostic.csv`). A point counts as usable only if no converged annulus state is clamped
  (`solution_clamped_elements == 0`). In that case only the bracket scan left the data. The scan starts at
  the no-induction angle, α = twist − atan(V/Ωr), which is 26.4° at the first annulus when static. A
  stalled-branch root above 12° cannot be excluded there, because XFOIL gives no data above 12°.

## Results

### Fail-closed tier: what ran and what did not

60 of 120 points are usable: every RPM at J = 0.2–0.4. All 60 failures are "alpha outside polar data"
(`aero_summary.json`):

- **J ≤ 0.15:** the first annulus's scan starts above 12° (26.4° at J = 0, 17.7° at J = 0.1, 13.5° at
  J = 0.15).
- **J ≥ 0.45:** the root's no-induction angle is below −6°.

A fail-closed point stops at its first violation, so these counts show only the first bound each failed
point hit. Where evidence exists:

- **The 60 usable points:** no annulus failed to converge and no Reynolds, Mach or span bound was queried.
- **The clamp diagnostic:** no converged state was clamped in Reynolds, Mach or span; every clamp there is
  in α.

The CSVs leave η blank where thrust is not positive. They leave percent deltas blank where the reference
value is not positive.

Nondimensional results at 6000 RPM (what-if):

| J | C_T E / ref | C_P E / ref | η E / ref |
|---:|---|---|---|
| 0.20 | 0.0347 / 0.0576 | 0.0142 / 0.0239 | 0.488 / 0.482 |
| 0.25 | 0.0263 / 0.0496 | 0.0124 / 0.0223 | 0.530 / 0.556 |
| 0.30 | 0.0167 / 0.0408 | 0.0099 / 0.0201 | 0.507 / 0.609 |
| 0.35 | 0.0066 / 0.0313 | 0.0067 / 0.0173 | 0.341 / 0.634 |
| 0.40 | −0.0038 / 0.0210 | 0.0030 / 0.0137 | (T < 0) / 0.615 |

Dimensional thrust and shaft power at several RPMs (what-if):

| RPM | J | Thrust E / ref [N] | ΔT | Power E / ref [W] | ΔP | η E / ref |
|---:|---:|---|---:|---|---:|---|
| 3000 | 0.2 | 1.06 / 2.02 | −47.7 % | 8.6 / 15.1 | −42.9 % | 0.405 / 0.443 |
| 3000 | 0.3 | 0.39 / 1.35 | −71.1 % | 5.6 / 12.3 | −54.5 % | 0.344 / 0.541 |
| 6000 | 0.2 | 5.05 / 8.39 | −39.8 % | 68.3 / 114.9 | −40.6 % | 0.488 / 0.482 |
| 6000 | 0.3 | 2.43 / 5.95 | −59.1 % | 47.5 / 96.8 | −50.9 % | 0.507 / 0.609 |
| 8000 | 0.2 | 8.99 / 14.98 | −40.0 % | 157.9 / 269.6 | −41.4 % | 0.501 / 0.489 |
| 8000 | 0.3 | 4.44 / 10.60 | −58.1 % | 110.6 / 225.7 | −51.0 % | 0.530 / 0.620 |

Reynolds effect: E's C_T at J = 0.2 rises from 0.0290 at 3000 RPM to 0.0347 at 6000–8000 RPM. The
reference's rises from 0.0555 to 0.0579. Results at other RPMs and J are in `bem_comparison_deltas.csv`.

### Clamp diagnostic: static and low J

106 of 120 points are usable. The 14 that are not are:

- J = 0.5 at every RPM: one root annulus below −6°;
- J = 0 at 3000 RPM: two root annuli converge above 12°.

At 4000–8000 RPM static, every selected converged state lies inside the data; at 6000 RPM the highest
angle is 9.1°. This is not fail-closed: a stalled root above 12° on another branch cannot be excluded.

| RPM (J = 0) | Thrust E / ref [N] | Power E / ref [W] | C_T E / ref | C_P E / ref | FM E / ref |
|---:|---|---|---|---|---|
| 4000 | 3.84 / 5.33 | 25.5 / 38.1 | 0.0594 / 0.0823 | 0.0179 / 0.0267 | 0.645 / 0.705 |
| 5000 | 6.02 / 8.35 | 48.2 / 73.2 | 0.0595 / 0.0826 | 0.0173 / 0.0263 | 0.667 / 0.720 |
| 6000 | 8.67 / 12.07 | 81.8 / 125.5 | 0.0596 / 0.0829 | 0.0170 / 0.0261 | 0.681 / 0.729 |
| 7000 | 11.84 / 16.50 | 128.7 / 198.9 | 0.0597 / 0.0833 | 0.0169 / 0.0260 | 0.690 / 0.736 |
| 8000 | 15.54 / 21.70 | 191.5 / 297.8 | 0.0600 / 0.0838 | 0.0168 / 0.0261 | 0.698 / 0.740 |

FM = T^1.5 / (P √(2ρA)), with A the full disk area, although the BEM covers only 0.20R–0.98R. Both
blades share that bias.

Matching the reference's static thrust at 6000 RPM (12.07 N, 125.5 W): E at 7000 RPM gives 11.84 N for
128.7 W. Scaling to exactly equal thrust with C_T and C_P gives n ×1.18 and P ×1.07. Re effects make the
scaling approximate.

### Spanwise loading

The full distributions are in `spanwise_loading.csv`; the figure panel shows 6000 RPM.

| Case (6000 RPM) | dT/dr at r_j, E / ref [N/m] | α at r_j, E / ref [°] | Thrust from 54–144 mm, E / ref [N] | Total, E / ref [N] |
|---|---|---|---|---|
| J = 0 (diagnostic) | 50.8 / 130.9 | 1.2 / 5.9 | 6.32 / 9.72 | 8.67 / 12.07 |
| J = 0.3 (fail-closed) | −7.6 / 74.4 | −2.0 / 2.1 | 1.66 / 5.17 | 2.43 / 5.95 |

- **The thrust loss is confined to the zone.** The zone loss (3.40 N static, 3.52 N at J = 0.3) equals
  the total loss to within 0.001 N. The residue comes from the annuli that straddle the zone edges. The
  blades are identical outside 54–144 mm, and BEM annuli do not interact.
- **E's joint region unloads first.** At J = 0.3 it carries negative lift around r_j.
- **In the static case the loss is moderate.** Inflow there lowers the angle of every section, so E's
  joint sections still carry about 40 % of the reference's local loading.

`aero_comparison.png` shows C_T, C_P and η against J at 3000, 6000 and 8000 RPM. Its markers are:

- **x:** failed fail-closed;
- **open circle:** usable only in the clamp diagnostic.

It also shows the spanwise thrust loading, the angle of attack against geometric twist, and the section
polars at the five chords.

## Joint step: unresolved

In both blades the deployed distal sits δ = 6 mm higher along the shaft than the proximal. This makes an
axial step at r_j = 99 mm, together with the lug bosses (r 5.5 mm about the pin), a stop nose that reaches
2 mm ahead of the leading edge, and a 0.3 mm spanwise face gap.

**Why the current model cannot see it.**

- BEM is strip theory. Each annulus is an independent 2-D section on one rotor plane, so a rigid
  translation of the distal along the shaft changes nothing in it.
- The step's real effects are three-dimensional:
  - trailed vorticity from the two segment ends at r_j, which act as two tips;
  - flow through the 0.3 mm face gap;
  - bluff-body drag and separation on the bosses and nose;
  - the proximal end's wake meeting the displaced distal root.
- None of these is modelled. The application's BEM service even refuses a non-zero hinge offset
  (`design_analysis._load_open`).

**What is separated.**

- **Blade-shape effect (computed above):** E against the reference as continuous blades, same section
  family, same settings.
- **Joint-step effect (unknown):** both blades carry the same step. The E-versus-reference difference
  therefore excludes it, but both blades' absolute performance includes it.
- **A possible interaction (unknown):** E's lower loading at r_j would weaken any junction vortex.

**What could resolve it.**

1. **DUST in the repository: not usable as is.**
   - `pyfoldable/coupled/model.py::case_geometry` rejects a non-zero hinge axial offset
     (`unsupported_hinge_axis`).
   - The route generates only DUST parametric lifting-line components (`el_type = l`; `continuous_rbf`,
     or the legacy `split_rigid`, one line per segment).
   - It needs a `ResearchDesign` with a catalog profile and an admitted stored polar version. The
     printable section family is neither.
   - A lifting line cannot represent bosses, the nose or the gap.

   The pinned DUST source (`~/pyf-work/src/dust`, `mod_build_geo.f90`) also accepts surface-panel (`p`)
   and vortex-ring (`v`) components. A two-segment panel or vortex-lattice model with the 6 mm offset
   could estimate the **inviscid** junction interaction: two segment tips at different heights.

   That would need:
   - a meshed stepped geometry, from the exported STEP files;
   - new deck generation for `p`/`v` components and the offset;
   - relaxing the offset check;
   - admitting the printable section's polars, for any viscous correction.

   It would still miss gap flow and boss separation.
2. **CFD.** A steady RANS calculation in a rotating frame (one blade, periodic) of the stepped E against
   a continuous E (δ = 0, no bosses) isolates the step. The same calculation for the stepped reference
   checks the blade-shape result. At Re 25–180k it needs a transition model (for example γ–Re_θ). The
   geometry would come from `reports/prototype_13in_20261118/E_offset6_ts0p86_zone45_travel140/step/`.

   OpenFOAM 12 is installed in this WSL (`/opt/openfoam12`), but the repository has no CFD case route.
   Results would enter as external evidence through the CFD reference contract
   (`pyfoldable/core/cfd_reference.py`), not as qualification.
3. **A printed A/B thrust-stand test.** This is the cheapest decisive step. Use one printer, material and
   orientation, the same hub and motor, and static thrust plus torque (or electrical power with a motor
   map) over an RPM sweep. Run each blade at least three times, in alternating order, and log temperature
   and pressure for density.
   - **Step effect:** the same blade in two versions, one-piece continuous E (δ = 0, no joint) against
     stepped E (δ = 6 mm with bosses, nose and gap). Any difference beyond repeatability is the step
     effect.
   - **Blade-shape check:** stepped E against stepped reference. Compare the measured thrust and power
     ratios at equal RPM with the prediction above (static: thrust ×0.72, power ×0.64–0.67 at
     4000–8000 RPM).
   - **The speed limit governs the test.** A safe stand test stays below about 2500 RPM (strength limit,
     SF 2). At that speed root Re is about 22k, below this polar grid (25k). Extend the XFOIL grid down
     to about 15k first. XFOIL is least reliable there.

## Proxy and real

- **Real (numerical):** XFOIL 6.99 polars of the five printable sections, through the pinned executable.
  The BEM ran on these families only.
- **Not used:** the retained catalog NACA2412 families (`2026-11-11-v1`, `2026-11-12-deploy-v3`). They
  cover Re 100–400k, M 0.07–0.36 and α −6…8°, which would fail most points here. Their coordinates are
  not the printable section. Since XFOIL ran, no proxy was needed.
- **Diagnostic, not proxy:** the clamp tier. It uses the same real polars with clamped bounds, and is
  accepted only when the converged states are inside the data.

## Limits

- **XFOIL is 2-D and numerical.** Free transition at n_crit 9, and Re 25–300k (laminar separation
  bubbles). The blunt trailing edge is handled by XFOIL's TE-gap model. Rows at 10–12° at low Re are near
  stall and are solver output, not data. No post-stall data exist above 12°.
- **The BEM is axisymmetric.** No 3-D stall delay, and no blade deflection: the printed blade is assumed
  rigid and as designed. There is no hub or spinner, no root region inside 33 mm, no tip beyond 161.8 mm,
  and no motor or fuselage blockage.
- **The spanwise blend is approximate.** It is linear in radius between five chord anchors.
- **The speeds are what-if and above the structural limit.** ISA atmosphere is assumed.
- **What was not run:** the joint step, fold angles other than 0, and any validation against
  measurement. No physical qualification follows from these numbers.

## Reproduce

```bash
./venv/bin/python -m pytest tests/prototype/test_prototype_aero.py -q
./venv/bin/python -m pyfoldable.prototype.aero reports/prototype_13in_20261118/aero
```

The report command reuses `polars_printable_section.json` once `check_record` and the coordinate check
pass. Delete that file to regenerate it through XFOIL; this needs the operator bundle
`~/pyf-work/xfoil/preflight` and takes about 1.5 minutes. When the bundle is missing, the XFOIL cell test
is skipped, so CI does not exercise the XFOIL route.
