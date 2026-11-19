# Assembly instructions — 13in-C

Units: millimetres. Fit and mechanism prototype only; not qualified for powered operation.

1. Print the hole coupon in the same material and orientation as the lugs (rotor plane on the bed). Push the real
   Ø3.0 pin through each hole (k notches mark hole k). Pick the hole that runs freely without
   wobble; set `hole_clearance_mm` to that step and re-export before printing the segments.
2. Print the fit-test pair (`fit_proximal`, `fit_distal`). Support the twisted lower surfaces; keep supports out of
   the lug faces and holes. Remove supports and deburr the hole entries (0.4 mm chamfers are modelled).
3. Stack from below: pin head → washer → proximal lug → distal lug → washer → E-clip. The distal lug sits above
   the proximal lug with the running gap g = 0.3 mm (the gap is set by the hardware stack; do not
   clamp it closed). Seat the E-clip in the groove with pliers.
4. Rotate the distal through the full travel by hand. Check: it seats flat on the open stop at θ = 0 (nose on the
   proximal pad ahead of the pin), it folds backward (toward the trailing edge) without touching the proximal
   outside the joint, and the pin turns freely. Record any contact location and angle.
5. Measure (see `docs/prototype_13in.md`, measurement plan): masses and CG of each part, hole diameters, lug
   thicknesses, gap, wobble at the distal tip, friction torque, and the stop seat. Only then print the full rotor.
6. Full rotor: assemble each blade as in 3. Do not spin it under power: maximum speed, motor and thrust are not
   yet specified and the strength estimates use exploratory material data.
