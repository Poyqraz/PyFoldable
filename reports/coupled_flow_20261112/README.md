# Coupled flow-and-response evidence (2026-11-12)

Evidence for the *Akış ve tepki* view: DUST wake and induced velocity shown with the hinge
response and loads of the same accepted windows. Software and model evidence only; mechanical
inputs are declared demonstration assumptions and `physical_qualification` is false.

| File | Content |
|---|---|
| `main_flow_companion_manifest.json` | Manifest of the flow companion of the main `continuous_rbf` record `20261112T071200_20d4a1092d` (110 frames; every source DUST file with the sha256 the sealed record lists; `dust_post` identity and input; array digest). The 34.5 MB array file stays in the run folder. |
| `split_rigid_flow_companion_manifest.json` | Same for the earlier two-line record `20261112T005547_39a32f06ef` (same case). |
| `wake_comparison.txt`, `.json` | Near-wake particle strength (within 0.5 R below the disk) in the hinge band (r_h ± 15 mm), inboard and at the tip, particle counts, thrust, θ and the largest downward velocity half a radius below the disk, per frame, for both records. |
| `vtk_validation.txt` | The ParaView export of the main record read back with VTK 9.3.1 legacy readers (particles, velocity plane, rotor; first, middle and last time steps of each collection). |
| `scripts/` | `wake_compare.py` and `vtk_validate.py`, as run. |

Key observation: the hinge band carries ≈ 2 % of the near-wake strength in the continuous-line
record and 46–60 % in the two-line record, where it grows after release together with the
inboard strength and the thrust rise (37.2 → 42.8 N) — the junction vortex pair that led to the
continuous topology, visible in the genuine particle wake. In the continuous record, first stop
contact gives a short thrust peak (38.7 N) and a ≈ 0.7–0.8 m/s faster slipstream at z = −R/2,
both back near settled values about a revolution later; the tip-band strength keeps growing
(1.43 → 1.76), mixing the opening response with ongoing wake development. Circulation-derived
quantities carry the located rbf bias (design doc §9). The first wake row lies 0.250 c behind
the drawn trailing edge (DUST lifting-line convention; measured, design doc §12).

Reproduce (WSL, repository root): build the companions in the app (*Akış ve tepki → Akış
verisini hazırla*) or with `coupled_analysis.build_flow`, then
`./venv/bin/python reports/coupled_flow_20261112/scripts/wake_compare.py`.
