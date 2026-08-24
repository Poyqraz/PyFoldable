# PR-10 public experimental baseline

## Decision

Public data provide a defensible fixed-propeller and measurement-method foundation
until project measurements arrive. They do not qualify the foldable prototype and
cannot open the PR-10 physical gate.

## Accepted evidence

| Source | Classification | Extracted value | Qualification boundary |
| --- | --- | --- | --- |
| [UIUC Propeller Database](https://m-selig.ae.illinois.edu/props/propDB.html) and [Volume 1 V3](https://m-selig.ae.illinois.edu/props/volume-1/propDB-volume-1.html) | Published same-propeller baseline | APC SF 10x4.7: 16 static and 44 forward coefficient points; 50 positive-thrust points in the existing benchmark envelope | CT/CP/J/RPM only; no run-specific atmosphere, raw sensor stream, or calibration certificates |
| [Morgado and Pascoa et al. (2015)](https://www.naun.org/main/NAUN/mechanics/2015/a372003-136.pdf) | Independent same-propeller dynamic reference | APC 10x4.7SF at 4000 and 5000 RPM; 400 samples at 8 Hz; 50 s per point; sample-count study; in-situ thrust/torque and combined check loads | Cross-laboratory and method context only; not project hardware; uncertainty reported for another propeller is not transferred |
| [Brandt and Selig (2011)](https://m-selig.ae.illinois.edu/pubs/BrandtSelig-2011-AIAA-2011-1255-LRN-Propellers.pdf) | Primary low-Re propeller method | Direct thrust/load-cell and reaction-torque measurement, fixture effects, repeatability and coefficient conventions | Method and UIUC provenance; online corrected V3 data supersede old thesis tables |
| [NIST TN 1297](https://doi.org/10.6028/NIST.TN.1297) and [JCGM 100:2008](https://www.bipm.org/documents/20126/2071204/JCGM_100_2008_E.pdf) | Measurement-uncertainty guidance | Type A, Type B, combined and expanded uncertainty with an explicit coverage factor | Does not supply apparatus-specific uncertainty values |
| [ASTM E74](https://store.astm.org/e0074-18r26.html) and [ASTM E2428](https://store.astm.org/e2428-22.html) | Static calibration standards | Traceable force and torque calibration | Static calibration does not establish dynamic/high-speed adequacy |
| [PropDBTools](https://github.com/ramcdona/PropDBTools) | Open-source UIUC parser | Reusable UIUC-format ingestion; BSD-2-Clause code | Parser license does not relicense the UIUC data |

The official UIUC archive publishes MD5
`a41e484f1fd0fb6ff80b76e27410808b`. The repo also records the SHA-256 of its
packaged fixture. These identities are different: one binds the official archive,
the other binds the normalized project fixture.

Brandt's campaign-level apparatus estimates are efficiency 0.595%, power 0.240%,
RPM 0.100%, thrust 0.504%, torque 0.218%, and freestream velocity 0.207%. They are
retained as historical apparatus metadata, not assigned as per-point uncertainty bars
and not transferred to future project measurements.

## Project test requirements derived from the evidence

- Record thrust, torque, RPM, freestream speed, diameter and atmospheric inputs needed
  for CT, CP and J; retain voltage/current if electrical efficiency is evaluated.
- Preserve raw samples, timestamps, sample rate/count/window, pre/post zero values,
  calibration/check-load records and at least three independent repeats.
- Combine Type-A repeatability and Type-B calibration/drift components; report the
  coverage factor. Do not copy uncertainty percentages from a different propeller.
- Treat 400 samples at 8 Hz for 50 seconds as a documented literature precedent, not
  a universal standard. The project steady-state and drift limits remain versioned
  acceptance policy validated against its own raw data.
- Require separate bandwidth, vibration, aliasing and dynamic-use evidence because
  traceable static calibration alone is insufficient.

## Fail-closed boundary

UIUC `qualification_eligible` means only that a point lies in the fixed-propeller
benchmark's positive-thrust envelope. It never means PR-10 physical qualification.
Negative-thrust windmilling points remain in the benchmark evidence and are not
converted into the nonnegative project experiment sample schema. Dimensional T/Q
must not be reconstructed from CT/CP using the fixture's assumed atmosphere.

## Screened sources not admitted as qualification evidence

- [hnrosa/uiuc-propeller](https://github.com/hnrosa/uiuc-propeller) is useful MIT
  preprocessing code, but its license does not relicense upstream UIUC data.
- [Parser_UIUC_AeroData](https://github.com/pfreitas97/Parser_UIUC_AeroData) is a
  useful mirror/parser with no verified license; no code or data were copied.
- [Mendeley 30-inch propeller dataset](https://data.mendeley.com/datasets/69hhwc3fd3/1)
  is CC BY 4.0 and includes folding-propeller hover measurements, but the scale and
  regime mismatch restrict it to `cross_scale_screening`.
- [APC 10x4.5MR Canterbury study](https://doi.org/10.26021/15764) is an adjacent
  same-size forward-flight model-form reference, not the tested 10x4.7SF geometry.
