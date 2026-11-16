# Attached-flow polars for all six catalog profiles (2026-11-16)

Genuine XFOIL 6.99 captures (the pinned local build of `reports/coupled_deploy_polars_20261112/build/`,
executable `d1076680…`) for the catalog profiles, installed as separate families in
`data/research_reference/axial_800_store`. Unqualified numerical evidence; attached flow only;
`physical_qualification` is false. More XFOIL coverage does not establish validity in separated flow.

| Profile | Declaration | Grid (Re × Mach) | α | Outcome |
|---|---|---|---|---|
| NACA0012 | `RESEARCH_AXIAL_800_CATALOG_NACA0012_V1` | 100k–400k (5) × 0.07, 0.10, 0.31 | −6…8° | 15/15, installed `2026-11-16-catalog-v1-naca0012` |
| NACA23012 | `…_NACA23012_V1` | 100k–330k (4) × 0.07–0.36 (4) | −6…8° | 16/16, installed |
| NACA63-412 | `…_NACA63412_V1` | 100k–400k (5) × 0.07, 0.10, 0.31 | −6…8° | 15/15, installed |
| NACA4412 | `…_NACA4412_V1` | 100k, 245k, 400k × 0.07–0.36 | −6…8° | **stopped at cell 1**: CL(−4°) ≥ 0, retained (`evidence_NACA4412_V1`) |
| NACA4412 | `…_NACA4412_V2` | 100k, 165k, 245k, 400k × 0.07, 0.10, 0.36 | −8…6° | 12/12, installed `2026-11-16-catalog-v2-naca4412` |
| NACA4415 | `…_NACA4415_V1` | 165k–330k (3) × 0.07–0.36 | −6…8° | **stopped at cell 1**: CL(−4°) ≥ 0, retained |
| NACA4415 | `…_NACA4415_V2` | 165k–400k (4) × 0.07, 0.10, 0.31 | −8…6° | 12/12, installed |

NACA2412 keeps its 2026-11-11 and deploy-v3 families.

* **Grid choice:** per profile, from the convergence pre-screens of this executable
  (`convergence_prescreen*.json`, diagnostic, never admitted): no non-converging state is a declared
  node. Inside the NACA4412 V2 table two non-converging states (Mach 0.31 at Re 100k and 165k) are
  bridged by linear interpolation between Mach 0.10 and 0.36 (coarse); the other tables contain none.
* **4 %-camber profiles:** their zero-lift angle is near −4°, so the retained lift-sign rule
  (CL(−6°), CL(−4°) < 0, which bounds the BEM's conditional scan) failed physically, not numerically.
  V2 declares the angle sequence −8…6° (8 angles; the BEM operating point near 5° stays inside) and the
  rule at −8/−6° and 2/4/6° (`lift_sign_check`); the scan guard follows the declared bound.
* **Check through the services** (`six_profile_check.json`): every family runs the BEM at the default
  800 mm point (2400 RPM, 14 m/s; NACA0012 33.42 N … NACA4415 54.62 N) and prepares the coupled C81
  table. NACA0012's new family reproduces its 2026-11-11 result exactly (separate build).
* **Evidence:** `evidence_*` are the complete operator folders (frozen plan, raw captures, outcomes,
  checksums); each re-verifies against its declaration (`tests/application/test_research_catalog_protocol.py`).
* **Reproduce:** `examples/research_catalog_polar_data.py --protocol <declaration> freeze|capture|install
  --evidence <dir> …` (thin launcher over the deploy-v3 operator); `scripts/make_declarations.py`.
