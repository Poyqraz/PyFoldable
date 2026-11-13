# Captured numerical research reference — 2026-11-11

axial_800_store/ is an immutable ProviderRecordStore registered from the independently
declared configs/polars/RESEARCH_AXIAL_800_V1.json protocol. It contains actual retained
XFOIL6.99 results/captures for NACA0012 and NACA2412: six complete Re/Mach cells and
eight alpha points per profile,96/96 overall. No inert production fixtures.
This is unqualified numerical evidence, not experimental data, process-image
attestation or physical approval.

The release entry point selects this store by default. PYFOLDABLE_PROVIDER_STORE
can explicitly override it; a missing/corrupt override fails without substitution.
Loading reconstructs typed records and reuses current strict admission; no persisted
approved Boolean replaces the checks. Never edit blobs/manifests. No solver
executable is required to consume the retained data.

Store content hashes:
- NACA0012:18fd52a7fc5dbd45c0736103ef876fccf044f9eb779fdfc123c317b04c33abd3
- NACA2412:5841e000f7885350756d73803a9a0506b1f895e2b336c7cad3a831b592ced3f0

Original coordinate assets/attribution remain in the existing catalog and coordinate
documentation. Input coordinates and original raw output bytes survive in blobs.
These first-party results use the retained catalog coordinates, without manufacturer
lookup, symmetry substitution, point repair or stitched family.
See docs/research_application.md, reports/research_release_20261111/ and the separate
execution archive. Historical250mm/7100RPM and35/37 negative evidence are unchanged.

## Added 2026-11-12: deployment grid (separate family)

`research_axial_800_deploy_xfoil_v3:NACA2412`, version `2026-11-12-deploy-v3`, content
418d7d65d227df9f9bdcd9195f86531dd99fa29e6c23b8804f5223425748c222: attached-flow NACA2412 cells
at Re 100k/165k/245k/330k/400k x Mach 0.07/0.10/0.31/0.36, alpha -6...8 deg (20 cells, 160/160
points), declared by configs/polars/RESEARCH_AXIAL_800_DEPLOY_V3.json and captured with a
separately built XFOIL 6.99 (executable d1076680...136a7). Registration only added files; the
2026-11-11 records and blobs are unchanged. At the six cells shared with the 2026-11-11 family
the coefficients are identical. The two NACA2412 versions are never mixed; the application asks
the user to choose one. Evidence, failed declarations and the convergence map:
reports/coupled_deploy_polars_20261112/. Unqualified numerical evidence, not experimental data.
