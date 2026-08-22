# Third-party notices and data boundaries

The root `LICENSE` applies to first-party PyFoldable software, documentation,
configuration, examples, tests, and reports for which the Project has the necessary
rights. It does not relicense third-party material. The following boundaries are
material to this repository.

## APC Propellers user-local geometry

The Project does not distribute APC geometry or performance tables. The strict PE0
parser and screening example accept bytes supplied locally by a user and record the
source URL, version, date, and SHA-256 identity. APC source terms remain controlling;
the Project license does not grant rights to download, reproduce, or redistribute APC
material. APC product names and marks belong to their respective owner.

- Geometry index: <https://www.apcprop.com/propeller-technical-data/>
- Source terms: <https://www.apcprop.com/terms-conditions/>
- Performance-model description:
  <https://www.apcprop.com/technical-information/performance-data/>

The legacy `data/propellers/apc_202602/` path now contains only a first-party,
non-qualifying synthetic software fixture; the prior normalized APC derivative has
been removed from the current distribution.

## UIUC Propeller Database benchmark evidence

`tests/fixtures/rotor_benchmark/uiuc_apcsf_10x4.7_v1.json` contains a factual,
attributed subset of the UIUC Propeller Database: approximate digitized geometry and
wind-tunnel coefficient measurements for the APC Slow Flyer 10x4.7 propeller.

- Source and citation instructions:
  <https://m-selig.ae.illinois.edu/props/propDB.html>
- Volume 1, version 3:
  <https://m-selig.ae.illinois.edu/props/volume-1/propDB-volume-1.html>
- Recommended citation: J.B. Brandt, R.W. Deters, G.K. Ananda, O.D. Dantsker, and
  M.S. Selig, *UIUC Propeller Database*, Volumes 1–4, University of Illinois at
  Urbana-Champaign, Department of Aerospace Engineering.
- The measurements and geometry excerpt are excluded from the Project's PolyForm
  license; source terms and applicable law continue to govern them.

## XFOIL-derived qualification output

`tests/fixtures/polar_real_qualification/` contains numerical evidence generated with
MIT XFOIL 6.99 and NeuralFoil 0.3.3. The Project does not vendor either solver. Solver
names, versions, source URLs, configuration, and output provenance are preserved in
the fixture manifests and `docs/polar_real_backend_qualification.md`. Third-party
solver software remains under its own terms.

## Airfoil coordinates

`configs/airfoils/NACA0012_81.dat` is an analytic NACA 0012 coordinate realization;
`configs/airfoils/PYFOLDABLE_DEMO.dat` is a Project demo profile. A user-supplied or
future imported coordinate file remains subject to its own source terms even when the
PyFoldable parser normalizes it.

## Dependencies

NumPy, SciPy, tomli, matplotlib, pytest, NeuralFoil, and other install-time tools are
dependencies rather than vendored source. Each retains its own license.
