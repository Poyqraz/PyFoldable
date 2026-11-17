# Complete opening–closing cycle and folding-connection loads

Application: *Analiz → Tam açılma–kapanma çevrimi ve bağlantı yükleri*; results under *Sonuçlar → Açılma–kapanma
çevrimi*; saved cycles under *Karşılaştırma / kayıtlar*; coupled records gain *Bağlantı yükleri*. Code:
`pyfoldable/dynamics/fold_cycle.py`, `pyfoldable/dynamics/pin_lug.py`, `pyfoldable/coupled/hinge_loads.py`,
`pyfoldable/application/fold_cycle_ui.py`, `fold_cycle_views.py`. `physical_qualification` stays false.

## 1. Analysis modes (what is calculated in each)

| Mode | Fold motion | Shaft | Aerodynamics | Range |
|---|---|---|---|---|
| Mechanical cycle + explicit aero model | predicted (1-DOF hinge dynamics per blade) | prescribed speed history | exploratory quasi-steady strip model on the distal segment (no induction, no retained polar data) | full travel, stowed → open → stowed |
| Mechanical cycle, no aero | predicted | prescribed | none | full travel |
| Coupled DUST–MBDyn–preCICE (existing) | predicted (MBDyn) | prescribed | DUST vortex wake with retained attached-flow polars | small folds (≥ −23°) opening only. Tested from ≥ 1600 RPM on the NACA2412 deploy-v3 table only (release during a 1600→2400 RPM ramp); estimated floor ≈ 1500 RPM, untested; the 2026-11-11 NACA2412 table needs ≈ ≥ 2200 RPM; other families follow their own envelope ([coupled note §13](coupled_dynamic_analysis.md)). No closing |

A reversed deployment is never shown as a closing: every frame is a solved state. Explanatory playbacks of a steady
BEM solution remain separately labelled.

## 2. Mechanism: what opens and what closes the blade

Pin parallel to the shaft at the hinge radius (the coupled model's axis; a clevis–tang/pin-and-lug connection with
the pin parallel to the shaft is the same kinematics). θ = 0 open, negative folded toward the trailing side.

* **Opening:** the centrifugal moment −m c_g r_h Ω² sin θ always drives θ → 0. Folded beyond 90° (cos θ < 0) shaft
  acceleration also opens the blade, because the Euler term −(J_h + m c_g r_h cos θ) Ω̇ changes sign. Deployment from
  a deep fold therefore starts during spin-up even before the centrifugal moment beats the preload.
* **Deceleration presses the blade onto the open stop**; with an axial free stream there is no reliable
  aerodynamic moment about this pin that folds it back. **The passive mechanism does not return to the stowed
  position** (shown by the *Pasif* preset: the blade stays open as the shaft stops).
* **Return options (explicit, editable exploratory values):** a preloaded torsion spring toward stowed (default
  0.30 N·m preload, 0.05 N·m/rad), or a latch at the open stop released on command plus an actuator torque.
* Consequence of the spring: the spring still pulls at the open position while the centrifugal moment vanishes at
  θ = 0, so the blade floats at an equilibrium angle (≈ −0.8…−1.4° at 2400 RPM for the defaults) and touches the
  open stop only during the opening swing. A detent latch cannot engage unless the blade reaches the stop.
* Stops: unilateral linear spring with a Kelvin–Voigt dashpot from a declared restitution (the coupled model's law;
  default 200 N·m/rad, e = 0.5). The dashpot term is not clipped, so the stop **pulls** (tensile torque) briefly
  before the blade separates. This is kept on purpose for parity with the MBDyn law. Each contact row carries its
  `tensile_peak_torque_nm`, and the record notes `stop_law = kelvin_voigt_tensile_at_separation`. The pull is
  included in the impulse, the effective restitution and the M_pin and connection-load histories during rebound. A
  load reversal at separation is therefore a property of this law, not of hardware.
* Latch: engages at the open stop, or on arrival within an optional capture band `latch_capture_rad` (default 0)
  below it. It locks 1 mrad past the engagement angle and acts only below that angle (it stops fold-back), so a band
  neither pulls the blade onto the stop nor holds it off it. Release is on command. Friction is tanh-regularised: a stationary joint dissipates no continuous
  power.
* Distal inertia: `inertia_cg_kg_m2` is isotropic about the CG, as in the coupled model. An optional declared
  product of inertia `inertia_tz_kg_m2` (default 0) adds −I_tz ω² about e_s (the centrifugal twisting moment) and
  I_tz ω̇ about e_t, with ω = (Ω + θ̇) e_z. Neither acts about the pin, so the fold motion is unchanged. With the
  default 0 the inertial torsion is exactly zero: M_s then comes from aerodynamics and gravity only, and the
  centrifugal twisting moment of a twisted blade is missing. The coupled model's distal body is also isotropic
  (`diag` J, J, J in the MBDyn deck) and has no I_tz input. A flat-plate estimate for the
  default 30 g distal part (c ≈ 50 mm, β ≈ 14°, 2400 RPM) gives Ω²·(m c²/12)·sin 2β / 2 ≈ 0.09 N·m. That estimate
  is not a run result, and it can exceed the aerodynamic torsion. I_tz is declared, not derived from the loft
  (record note `inertia_tz`). Mass, CG and inertia are editable UI defaults, also not derived from the loft.
* Inflow at rest: `AeroModel.rest_inflow` is `design` by default, so the free stream also acts while Ω = 0. With
  `zero` there is no inflow until the shaft turns. If a blade leaves the stowed stop before spin-up, the event
  `left_stowed_before_spinup` states that the stowed state is not an equilibrium.
* Gravity optional (shaft vertical: weight along the pin; shaft horizontal: once-per-revolution fold moment).

## 3. Geometry consistency

The analyses keep both segments in one plane; the lofted surfaces then interlock beyond ≈ −66.6° (display joint
zone) and immediately with a plain hinge-plane split. The pin-and-lug concept needs an **axial offset δ** of the
distal segment and tang along the pin. `BladeSpec.distal_axial_offset_m` (default 0, so earlier records keep
their meaning) lifts the distal part in the loft and in the interference scan through the full travel: 30 mm
clears −180° for the 800 mm NACA2412 design, 2 mm still interlocks. The cycle run scans the selected geometry
and warns when the stowed stop lies beyond the interference-free angle. Pin, clevis plates and tang are not
scanned (their geometry is not declared). The aerodynamic models ignore δ.

## 4. Connection loads

Reference: force and moment the proximal part transmits to the distal part; moment about the pin point H and
reported about the tang mid-plane H + δz (M_P = M_H − δ z × F). Hinge-local axes: e_s along the distal span, e_t =
e_z × e_s (in the rotor plane toward the leading side), e_z along the pin. Reported: N = −F·e_s (tension +), V_t,
V_z, M_s (torsion), M_t (bending), M_z (pin axis).

* Mechanical cycle: Newton–Euler of the distal body with its kinematics (a_G, θ̈, Ω, Ω̇): F = m a_G − F_aero − m g,
  M_H = J α ẑ + r × m a_G − M_aero,H − r × m g. Contributions (shaft centripetal, shaft Euler, fold motion incl.
  Coriolis, aerodynamic, gravity) explain the total; they are not added again. M_z equals the sum of the hinge
  elements (spring, damper, friction, stops, latch, actuator); F, M_s and M_t are revolute constraint reactions.
  The drive torque per distal segment is (x_H × F + M)_z (not the rotor shaft torque).
* Coupled records: MBDyn's own reactions — revolute 400+b `f_global`/`m_global` act on the distal node; the
  deformable hinge 500+b and latch 600+b moments are written for the proximal node, so M = m_rev − m_hinge − m_latch.
  Verified on recorded runs: β̇ = F_aero + F_rev to rounding; bending matches exactly; the pin moment matches within
  1–4 % (finite differences in contact). The companion check (central differences of retained states) passes at
  0.8–1.9 %. MBDyn's constraint reactions start with a decaying numerical transient (≈ 0.7× per window, first
  ≈ 10 windows); those windows are flagged and excluded from peaks. Blade b's moments are reported about its
  blade-plane point on the pin (the 0.01·b m preCICE label offset is shifted back). Peaks are taken over all blades
  and name the blade. A release or first contact inside the excluded start-up span is listed as a start-up overlap.
  The companion `hinge_loads.json` carries `extractor_version` (now 4), the record digest and the sha256 of the
  sealed `out.jnt`. A companion from another extractor version, or one whose joint file differs, is ignored, and
  the loads must be derived again on request (*Bağlantı yüklerini türet*).

## 5. Contacts, sensitivity, energy

Each stop contact: entry/exit (crossings on the dense solution), duration, peak stop torque, tensile peak (§2),
angular impulse, arrival rate, effective restitution, impact vs resting contact.

Sensitivity is opt-in in the UI. The governing contacts are recomputed on the real schedule: the largest-|peak|
open contact and the largest stowed impact, over all blades. The variants are a tighter integration (rtol/100,
step/4, integrated only up to the open target) and half/double stop stiffness. The result states the spread it
computed across the variants, separately for impulse and for peak stop torque. Each spread reads *kararlı* below
10 % and *varyanta duyarlı* otherwise. The change from the reference to the tighter integration is reported on its
own. No fixed spread is claimed here: read the computed values for the case at hand. **The peak is a property of
the assumed stop law, not a hardware design load.** Impulse and arrival speed are the more robust outputs only when
their computed spread says so.

Energy: shaft work through the connection + aerodynamic + gravity + actuator work − dissipation = Δ(kinetic +
spring/stop energy), ≤ 1e-3 relative. The latch-engagement snap energy is accounted. The check grid is uniform at
0.1 ms or finer (ω_n·dt ≤ 0.03 for the open hinge at operating speed). It is sampled on both sides of every switch
and refined to a twentieth of the stop half-period inside impacts. The finite-difference pin-balance check
(≤ 1e-2) excludes stop contacts, the latch snap and ±2 samples around switches.

Budgets fail closed instead of truncating. The cycle may last at most 20 s (`MAX_CYCLE_DURATION_S`). Check samples
× checked blades may not exceed 10⁶, and contact refinement may not exceed 20 000 stored samples. Stored series
use 10 ms steps away from events, the 1 ms output step within ±50 ms of events, knots and contacts, and refinement
inside every impact. Peaks are maxima over all blades and name the blade. Records are schema 2; schema-1 records
still verify read-only.

## 6. Connection pre-check (pin-and-lug)

Inputs: pin diameter, tang and plate thickness, gap, optional tang width and edge distance, allowables with their
source. Plate force P/2 ± (M_n × e_z)/s, s = t_tang + t_plate + 2 gap; pin double shear, pin bending (arm t_plate/2
+ gap + t_tang/4), plate bearing, and shear-out. Two tang checks include the moment terms. Tang edge bearing is
|P|/(d t_tang) + 6·hypot(M_s, M_t)/(d t_tang²), because the tang passes the plate couple into the pin across its
thickness. Tang net section is max(N, 0)/((w − d) t_tang) + 6|M_t|/((w − d) t_tang²). An allowable without a source
gives no margin and no verdict (status *girdi gerekli (kaynak)*). The checks run over all blades. Without
dimensions no check is shown.
Hand estimates only: no stress field, no concentration, fits, fatigue or anisotropy; the colour of a blade is never
a structural result.

## 7. What remains open

* Full aerodynamic validity over the cycle. The coupled route's tables are attached-flow only (α −6…8°; −8…6° for
  NACA4412/NACA4415). Coupled opening is tested from 1600 RPM on the NACA2412 deploy-v3 table; ≈ 1500 RPM is an
  untested estimate. Deep folds and low speed need a declared post-stall/deep-fold aerodynamic model or measured
  data. The continuous lifting line through a deep fold is limited by the enforced −23° envelope (junction chord
  bound and sweep, `pyfoldable/coupled/envelope.py`); beyond it the lifting line is not verified.
* Measured mass, CG, inertia (including the product of inertia I_tz, or a loft-based estimate with a declared
  density), stop stiffness and restitution, spring and friction of the real connection. A smooth (non-pulling)
  stop law is held back for parity with MBDyn.
* Declared pin, clevis and tang geometry for component interference and for the pre-check.
* Experimental validation of opening/closing times and impact loads (see the prototype measurement plan).
