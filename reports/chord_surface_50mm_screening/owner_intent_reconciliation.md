# Owner-intent reconciliation for the 50 mm screening

This note records the owner's stated design intent beside the existing trials. It does not select a hinge, a stop, or a qualified design.

The original proposal file `2209_B_arastirma_onerisi_formu_18112025 (1).pdf` SHA-256 `e16db4182fe5171dc7d06bb05c74875e0e80fac726cd8be52df366c29a7e1541` is not in this environment. These sentences do not come from a fresh reading of that PDF. The hash is the one already cited in the 2026-09-09 roadmap entry. The owner's follow-up states the 250 mm deployed and 140 mm folded concept, rotor-parallel hinge axes, and passive opening and folding. Those intents stay distinct from the schema example. The example hub radius, the 50 mm and 100 mm hinge trials, and the -180 deg stop are not proposal requirements.

In the owner's wording, the proximal main segment of one rotor blade is longer than its hinged distal segment. "First blade" and "second blade" name those two segments. They do not name the two opposed rotor blades.

The intended product deploys into aligned, load-transferring blade geometry and produces thrust. It maintains acceptable rotating vibration and deformation, folds in a controlled manner, and accounts for joint and distal-segment losses with applicable models, calibration, and uncertainty. It supports reproducible profile comparisons and user-facing outputs. No acceptance number for vibration, deformation, loss, or thrust is supplied here.

Lengths below use the axis-to-axis convention. `h` is the motor-axis-to-hinge length. `R-h` is the hinge-to-nominal-tip length. `h-b` is the exposed proximal span. Retained surface coverage is the parent station span and is shorter than those axis lengths.

Retained deployed radius R = `0.125` m.
Retained hub radius b = `0.018000000000000002` m.
Folded requirement = `0.14` m.
Retained stations run from `0.025` m to `0.1225` m.
Root gap `0.006999999999999999` m. Tip gap `0.0025000000000000022` m.

Long-main geometry requires h greater than `0.0625` m.
Opposed hinge points fit the folded requirement only when h is at most `0.07` m.
The resulting necessary geometric condition is 62.5 mm < h <= 70 mm. It is not a selected hinge and it is not a clearance result.

Under the additional schema assumptions of zero hinge offset, this hub radius, and a -180 deg centerline fold, positive hub clearance requires h greater than `0.07150000000000001` m. That threshold lies outside 62.5 mm < h <= 70 mm. The incompatibility belongs to those combined assumptions. It does not show that the folded 140 mm concept is impossible under a different hub radius, stop angle, or offset.

| Trial | h m | Main m | Distal m | Exposed proximal m | Long main | Opposed-point span m | Fits 140 mm | Zero-offset -180 deg centerline hub clearance m |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 100 mm | 0.1 | 0.1 | 0.024999999999999994 | 0.082 | true | 0.2 | false | 0.05700000000000001 |
| 50 mm | 0.05 | 0.05 | 0.075 | 0.032 | false | 0.1 | true | -0.018000000000000002 |

In exact millimetre arithmetic on a 125 mm radius, the 50 mm hinge has a 50 mm main segment and a 75 mm distal segment. The 100 mm hinge has a 100 mm main segment and a 25 mm distal segment. The table keeps the retained floating-point subtraction. The 50 mm trial has a distal segment longer than its main segment. The 100 mm trial meets the long-main comparison, and its opposed hinge points span 0.2 m, which is already larger than the 140 mm folded requirement. Neither trial is replaced, rescaled, or given a new twist or stop.

The archived canonical stow remains -180 deg with reasons: full_stow_path_intersects_hub, surface_stations_do_not_cover_hub_to_tip, tip_centerline_intersects_hub.

Own-root/tip findings on the original surface reports remain UNKNOWN. The separated interblade bounds cover only the retained triangle pairs on the synchronous path from 0 deg to -135 deg. A -150 deg picture does not extend that query. full_propeller_clearance remains null. physical_qualification remains false.

This geometry note does not resume the blocked real-polar comparison in Draft PR #97.

Next inputs, with no invented measurements or acceptance limits:

- an owner-declared motor-axis-to-hinge length, or an explicit revision of the long-main or 140 mm intent
- a proposal hub radius, hinge offset, and fold-stop angle, recorded separately from the schema example
- joint gap, step, hardware, and offsets; these remain absent
- source, method, applicability, and uncertainty for joint and distal-segment loss models
- rotating vibration and deformation evidence
- controlled-fold actuation history, completion, contact, latch, and release evidence
