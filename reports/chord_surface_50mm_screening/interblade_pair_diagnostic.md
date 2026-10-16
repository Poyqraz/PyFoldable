# Interblade pair diagnostic, 50 mm hinge, 0 deg to -135 deg

Additional pair-level diagnostic on the retained surfaces. This is not the original globally budgeted GEOM-03 report, and it does not select a stop or a hinge.

physical_qualification: false
Qualified winner: none
Selected stop: none
Selected hinge: none
full_propeller_clearance: null

Reviewed surface head `284a2e4f3b33f999fddcb9d8eb0b3a98ebf53c26`.
Study draft SHA-256 `89dfdd1907e9fe2221adea7ffa193f1849fbc1d6052dced1dafe5d20279c07d1`.
Parent canonical SHA-256 `1a149afec4cb192703a597e86717e5040d15e3c7fcb1697b4898ea3d26b6eada`.
Requested clearance remains 0 m. Attachment exclusions remain 0 m. Each pair is allowed one call and at most 50000 node comparisons, 2048 feature tests, depth 6 and 127 intervals. The additional aggregate ceiling is 200000 comparisons and 8192 feature tests. There is no retry and no automatic increase.

## Preserved original -135 deg findings

Original study SHA-256 `ae2f3434fea0687f79fbbe9a9b5d7e0e4efe488c276e53d5fb3423e411738718`.
modeled_surface_status: unknown
classification: blocked
station_span_complete: false
root_gap_m: 0.006999999999999999
tip_gap_m: 0.0025000000000000022
own_root_tip blade_1_root / blade_1_tip: unknown; unresolved boxes or subdivision/comparison budget; no collision conclusion
own_root_tip blade_2_root / blade_2_tip: unknown; global_budget_exhausted

## Pair results

Aggregate node comparisons: 7648
Aggregate feature tests: 2048
Pair calls: 4

| A | B | Status | Contact | Nodes | Feature tests | Intervals | Lower bound m | Witness m | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| blade_1_root | blade_2_root | separated | separated | 1 | 0 | 1 | 0.04999999982537702 |  | continuous conservative mesh bounds against mesh surface |
| blade_1_root | blade_2_tip | separated | separated | 9 | 0 | 1 | 0.005843301527710933 |  | continuous conservative mesh bounds against mesh surface |
| blade_1_tip | blade_2_root | separated | separated | 9 | 0 | 1 | 0.00619576112130861 |  | continuous conservative mesh bounds against mesh surface |
| blade_1_tip | blade_2_tip | separated | separated | 7629 | 2048 | 3 | 0.0004699207959556334 |  | continuous conservative mesh bounds against mesh surface |

The JSON file retains every interval. A separated row is a continuous lower bound between those two retained triangle sets on the synchronous path from 0 deg to -135 deg. It leaves the original own-root/tip result UNKNOWN, leaves the station span incomplete, and leaves full_propeller_clearance null.

## Views and the deployed shared boundary

assembly_view.png and hinge_closeup.png are historical XY projections. assembly_oblique.png is the historical oblique assembly of both blades. hinge_region_views.png is the earlier hinge figure: its panels still received every blade part, and the axis limits did not remove the opposed blade. Its YZ projection can superimpose that opposed blade after the X axis is suppressed.

hinge_region_views_blade1.png is the corrected close-up. It draws blade 1's fixed root and moving tip only. The faces are complete hinge-neighborhood triangles. Faces omitted from that selection are absent from the panel; they are not sliced into display endcaps. Both blades remain in the assembly views.

The preview mesh copies the hinge station twice, once onto the fixed root and once onto the moving tip. At 0 deg the tip rotation is the identity, so those copies occupy one section. That coincidence is the deployed shared boundary of the open mesh.

A nonzero fold rotates only the moving copy about the hinge pivot's z axis. The fixed copy stays in place. Where an XY projection shows the tip outline crossing the root outline, that crossing is a projection. It is not a contact finding and it is not a separation finding. The own-root/tip queries remain UNKNOWN. The four separated interblade bounds cover only the named retained pairs on the synchronous path from 0 deg to -135 deg. A picture at -150 deg does not extend that query. The canonical -180 deg collision finding remains the archived full-stow result. No joint relief, offset, hardware, endcap, or permitted-contact exclusion is added. Hub height remains absent.
