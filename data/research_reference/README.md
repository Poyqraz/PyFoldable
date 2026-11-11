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
