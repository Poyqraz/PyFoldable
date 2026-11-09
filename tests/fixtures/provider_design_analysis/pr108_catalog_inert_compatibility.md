# Pre-sixth-profile compatibility fixture

`pr108_catalog_inert_compatibility.tar.gz` SHA-256:
`bfbbdd66e6e0c4cc0f16026d5c5aa27605d1e9e39e762514b50fac285e861440`.

Created before catalog mutation with reviewed PR108 HEAD
`df9571542594c5f51206a4bce3cc5ff9bf107b63`, tree
`1773d9bb2146efda7b90a284654410779b09b9eb`, using the existing
`test_provider_design_analysis.scenario("NACA2412")` inert records and
`install_inert_bem` seam. Provider/banner/native BEM entry points were blocked.
One inert seam call generated a saved success snapshot and CSV. No numerical
provider/rotor study occurred. Not production data or physical evidence.

The archive retains the old draft, saved snapshot/CSV, provider store blobs and
manifest, plus provenance with old catalog hash and ordered request hashes.
The original temporary store path remains in the historical snapshot; reopening
at another path requires a fresh application preparation identity. The test
copies exact bytes into an isolated store, uses the actual loader and proves
historical attribution and provider identities survive catalog append.

The separate genuine `partial_xfoil_20261106.tar.gz` fixture is unchanged; it is
not derived from these inert records and remains a 35/37 rejection witness.
