# Lofted 3-D blade: demonstration records (2026-11-13)

Inputs that demonstrate the lofted blade view (`docs/blade_3d_view.md`) with genuine results.
Reconstructed geometry and display screening; `physical_qualification` is false.

| File | Content |
|---|---|
| `bem_naca2412_axial800_2026-11-11-v1.json` | Genuine saved BEM result: default 800 mm research design, NACA2412, retained family `research_axial_800_attached_xfoil_v1` (2026-11-11), produced by the same service call as the application's *BEM'i çalıştır* button (`research_design.run_research` with the retained store). T = 43.647 N, Q = 3.2774 N·m (as reported in `reports/research_release_20261111/observed-results.json`). Opens in *Karşılaştırma / kayıtlar → Önceki sonuç JSON'unu aç*; the result page then shows "Kanat üzerinde sonuç (3B)". |
| `fold_contacts_axial800_naca2412.json` | Fold-contact report of that design (display screening): with the display joint relief, last clear angle −66.58°, first contact distal ↔ own proximal at −66.6° on the trailing side 26 mm inboard of the hinge (a property of the display construction, not of a declared joint); possible contacts with the tip placeholder near −153°; no blade-to-blade or hub contact. Split at the hinge plane as the analyses split it, the parts interlock immediately (first contact −0.03°, last clear angle 0°). |
| `scripts/make_demo_records.py` | Produces both (needs `PYFOLDABLE_PROVIDER_STORE` pointing at `data/research_reference/axial_800_store`, as the research app sets by default). |

Coupled demonstration: the retained deployment record `20261112T220252_1f1a7bf962` (−22.5°, 2400 RPM,
deploy-v3 table; `reports/coupled_deployment_20261112/`), opened from its run folder: *3B oynatma* and
*Akış ve tepki* show the coloured blades posed from the window's MBDyn states with that window's wake.
