# Prototype measurement and identification plan (folding propeller)

Status: plan, 2026-11-13. Nothing here has been measured. It lists what the physical prototype must
provide so the coupled deployment results (`docs/coupled_dynamic_analysis.md` §13–§14) stop resting on
demonstration assumptions, ranked by influence on the existing results. Influence figures are
log-sensitivities at the declared demonstration values (30 g distal part, CG 55 mm from the hinge,
J_cg 3e-5 kg·m², stop 500 N·m/rad, e = 0.5, r_h 270 mm, 2400 RPM) from
`reports/coupled_engineering_20261113/engineering_assessment.json`.

Each measured value enters the application's mechanism inputs as a declared hardware property
(`declaration_kind = "declared_hardware_property"`, with the measurement named in the source field);
it does not qualify the rotor by itself (`physical_qualification`
stays false until a validation comparison exists).

## Priority 1: distal static moment m·c_g (mass and centre of gravity)

* **Why:** impact energy ∝ m·c_g (sensitivity 1 each), shaft angular impulse ≈ 1, peak stop torque
  0.5, hinge-pin centrifugal load m Ω² r_cg (≈ 616 N at 2400 RPM with 30 g). The energy result is
  independent of inertia, so this pair alone fixes the main preliminary sizing quantity.
* **How:** weigh each distal part with the hinge hardware that moves with it (±0.05 g). CG along and
  across the span by two-point support (two scales) or suspension from two points; report the CG
  relative to the pin axis, ±0.5 mm. Both blades, to see imbalance.

## Priority 2: stop response (stiffness, restitution, travel)

* **Why:** sets the peak stop torque (√k), the contact duration (≈ 1.7 ms now) and therefore the peak
  drive/shaft torque, plus the rebound (e enters the shaft impulse as (1+e), sensitivity 0.33). All are
  "illustrative" today.
* **How:** static torque–angle curve of the stop in a fixture (preload, contact stiffness, any
  nonlinearity, permanent set). Impact tests filmed at ≥ 10 kfps (≥ 15 frames per contact) or with an
  angle encoder; restitution from rebound/impact rate, repeated for wear. A gravity pendulum about the
  pin reaches only ≈ √(2 m g c_g / J_h) ≈ 16 rad/s even from 90°, while the runs impact at
  39–184 rad/s, and stop stiffness and restitution are usually speed-dependent: use it for low-speed
  points only, and reach operating rates with a spun release rig (the real hub at reduced RPM) or a
  drop-weight / launched-mass test; state the speed range achieved. Record the actual open-stop angle and the
  available fold travel (the mechanism's travel, which the application does not limit; its −23° is an
  aerodynamic-representation limit).

## Priority 3: hinge friction and free play

* **Why:** not modelled, so its influence rests on an assumed value: a friction moment M_f removes
  ≈ M_f |θ₀| of impact energy (an assumed 0.5 N·m from −20° ≈ 13 %) and can delay or prevent release; under centrifugal load the pin friction is load-dependent.
* **How:** breakaway and running torque at the hinge versus a known radial pin load (dead weight or
  spring, up to the operating ≈ 600 N if the rig allows); free decay of the distal pendulum: linear
  amplitude decay indicates Coulomb friction, exponential indicates viscous damping. Free play by dial
  gauge at the tip.

## Priority 4: distal inertia (J_cg or J_h directly)

* **Why:** J_cg has sensitivity ±0.12 on impact rate and release-to-contact time (±0.5 for J_h as a
  whole, which priority 1 already largely fixes through m c_g²); no effect on impact energy.
* **How:** compound pendulum about the actual pin: T = 2π √(J_h / (m g c_g)) gives J_h directly and
  cross-checks c_g (with priority 1). Bifilar suspension for J_cg if the pin cannot be used.

## Priority 5: drive characteristics

* **Why:** the prescribed infinitely stiff drive makes peak torque illustrative. With rotor + hub +
  motor inertia I, the shaft impulses of the runs become speed changes ΔΩ ≈ ΔL / I: +0.05…+0.24 N·m·s
  during the opening swing (≈ 3–5 ms) and −0.07…−0.32 N·m·s across the stop contact (≈ 1.7 ms; the
  latter scales with 1 + e). A torque-driven shaft needs the motor law for spin-up.
* **How:** spin-down test (inertia and drag torque); motor torque–speed–current map on a torque cell;
  ESC/controller step response (RPM logging ≥ 1 kHz); shaft/coupling torsional stiffness if a compliant
  coupling is used.

## Priority 6: release and static aerodynamic loads

* **Release:** latch release time and simultaneity across blades (high-speed video).
* **Static spin-up loads:** thrust and torque versus RPM from rest, fully folded and at intermediate
  folds, at representative inflow. Needed to identify and validate a post-stall treatment for
  deployment from a more fully folded state; no XFOIL extension substitutes for this.

## As-built geometry (alongside priority 1)

Hinge radius and pin-axis orientation (the model assumes the axis parallel to the shaft), chord/twist
at the declared stations, distal length. Deviations change r_h (energy ∝ r_h) and the sweep envelope.

## Clevis–tang connection: a design direction to evaluate

Not an established geometry or a measured mechanism. What the present results imply for evaluating it
(preliminary, scales with the measured mass and CG): the pin carries ≈ m Ω² r_cg radially (≈ 616 N at
2400 RPM for 30 g), ≈ 0.1–2.0 J of kinetic energy is delivered to the stop per deployment at 2400 RPM
for releases from −5…−22.5° (≈ 0.85–0.95 × m Ω² r_h c_g (1 − cos θ₀); with e ≈ 0.5 the stop
dissipates ≈ 1 − e² of it and returns the rest to the rebound), and the shaft sees +0.05…+0.24 N·m·s
during the swing and −0.07…−0.32 N·m·s across the contact.
What it cannot yet give: stop forces, pin bearing stresses or friction moments (need the stop law,
geometry and friction measurements above), and any strength or fatigue statement (not solved).
Evaluation should compare candidate clevis–tang layouts on pin load path, stop location and lever arm,
friction under load, free play and travel, using the measured values from priorities 1–3.

## Order of work

1. Priorities 1 and 4 together (one fixture, one day): replaces the mass properties in the app.
2. Priority 2 and 3 rig: replaces the stop law and adds the friction requirement for a model change.
3. Rerun the existing deployment cases with measured inputs (same tables) and compare against
   high-speed video of a bench deployment at reduced speed; this is the first validation comparison.
4. Priority 5, then priority 6 static loads, before any spin-up or deeper-fold model is attempted.
