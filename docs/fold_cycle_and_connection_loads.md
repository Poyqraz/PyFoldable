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
| Coupled DUST–MBDyn–preCICE (existing) | predicted (MBDyn) | prescribed | DUST vortex wake with retained attached-flow polars | demonstrated: small folds (≥ −23°) opening at ≥ ≈1500 RPM; no closing |

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
  default 200 N·m/rad, e = 0.5). The latch neutral angle lies 1 mrad inside the open stop (a detent presses the blade
  onto its stop). Friction is tanh-regularised: a stationary joint dissipates no continuous power.
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
  ≈ 10 windows); those windows are flagged and excluded from peaks.

## 5. Contacts, sensitivity, energy

Each stop contact: entry/exit (crossings on the dense solution), duration, peak stop torque, angular impulse,
arrival rate, effective restitution, impact vs resting contact. The first open-stop impact is recomputed with a
tighter integration and with half/double stop stiffness: numerics change nothing, the peak scales with stiffness
(e.g. −17.2 / −24.8 / −35.6 N·m) while the impulse stays within ±4 %. **The peak is a property of the assumed
stop law, not a hardware design load**; impulse and arrival speed are the robust outputs. Energy: shaft work through
the connection + aerodynamic + gravity + actuator work − dissipation = Δ(kinetic + spring/stop energy), checked on a
0.1 ms grid (≤ 1e-3 relative).

## 6. Connection pre-check (pin-and-lug)

Inputs: pin diameter, tang and plate thickness, gap, optional tang width and edge distance, allowables with their
source. Plate force P/2 ± (M_n × e_z)/s, s = t_tang + t_plate + 2 gap; pin double shear, pin bending (arm t_plate/2
+ gap + t_tang/4), tang and plate bearing, tang net tension and shear-out. Without dimensions no check is shown.
Hand estimates only: no stress field, no concentration, fits, fatigue or anisotropy; the colour of a blade is never
a structural result.

## 7. What remains open

* Full aerodynamic validity over the cycle: the coupled route's data cover α −6…8° and ≥ ≈1500 RPM; deep folds and
  low speed need a declared post-stall/deep-fold aerodynamic model or measured data, and the continuous lifting
  line through a deep fold (the RBF junction) is unverified beyond small angles.
* Measured mass, CG, inertia, stop stiffness and restitution, spring and friction of the real connection.
* Declared pin, clevis and tang geometry for component interference and for the pre-check.
* Experimental validation of opening/closing times and impact loads (see the prototype measurement plan).
