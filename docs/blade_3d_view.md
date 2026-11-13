# Lofted 3-D blade: geometry, results on the surface, fold contacts (2026-11-13)

A blade surface reconstructed from the catalog profile and the declared stations — no CAD input, and not
CAD — used in the design preview, on saved BEM results and in coupled playback. A hinge axis other than
the shaft-parallel quarter-chord axis (offsets, tilt) is refused rather than drawn wrongly.

## Geometry (`pyfoldable/visualization/blade_surface.py`)

* **Inputs:** the selected catalog profile's coordinates (Selig order; the catalog's trailing-edge
  thickness is kept), the design stations (radius, chord, twist), hub radius, declared physical root,
  hinge radius, tip radius and blade count. Saved records use their own geometry: a BEM result its
  retained draft (checksum-verified), a coupled record its case sections, with the catalog profile
  checked against the record's coordinate sha256 (fails closed on a mismatch;
  `pyfoldable/application/blade_geometry.py`).
* **Construction:** each side of the profile is resampled with cosine spacing (exact leading-edge and
  trailing-edge points kept), sections are stacked on the quarter-chord line and twisted about it; chord
  and twist are linear in radius between stations, as in the BEM (`linear_chord_twist`). Spanwise
  sampling 2 mm plus every station and the hinge. The analysed surface is closed: upper and lower
  surfaces, the trailing-edge face, end caps at the first and last station.
* **Frame and fold convention:** the coupled model's (`pyfoldable/coupled/frames.py`): blade body x along
  the chord LE→TE, y along the span, z lift normal; shaft +Z, rotation +Ω about +Z, so the leading edge
  leads; the hinge axis is parallel to the shaft through the quarter-chord point of the hinge section,
  and a negative fold turns the distal part back toward the trailing side. *Aligned 2026-11-13 (owner
  decision):* the 2.5-D preview builder (`visualization/propeller_25d.py`), which GEOM-01 geometry search
  and GEOM-03/04 surface and hardware clearance reuse, used to place a mirrored section (leading edge on −y,
  positive twist lowering it), so its negative fold went toward the leading edge. It now places the same
  physical section as the coupled model with the span on x (x_p = y_c, y_p = −x_c, z_p = z_c); its fold
  rotation is unchanged and now turns the distal part back toward the trailing side. Pinned by
  `tests/visualization/test_propeller_25d.py` and a preview-vs-loft cross-check in
  `tests/visualization/test_blade_surface.py`. Clearance reports archived before this change were computed
  with the mirrored section and stay as they are (historical evidence, not regenerated). Folded values that
  depend on which edge leads also shift for new runs: GEOM-01 `mesh_envelope_diameter_m` /
  `mesh_envelope_target` (the trailing edge, 0.75 c from the quarter chord, now swings outward instead of
  the leading edge at 0.25 c), and GEOM-03/04 witness points and contact angles. New requests get new
  identities, because the clearance service binds the source hash of `propeller_25d.py`. All preview faces
  are outward-wound after the change (checked).
* **Regions:** analysed surface (proximal and distal parts); *joint zone*; *placeholders* where no
  surface data exist (physical root → first station, last station → tip): translucent, extruded from the
  nearest declared section, never coloured with results. The hub is a dotted outline of its radius (no
  axial length or shape is declared). The hinge axis is drawn; no joint geometry is declared.

## Fold contacts and interlocking (`pyfoldable/visualization/fold_interference.py`)

Synchronous fold of all blades scanned from 0° to the declared lower limit; the first contact of every
pair (distal vs own proximal, other blades, hub cylinder; placeholders and the hub — only its radius is
declared — as *possible* contacts; static parts of different blades are checked once in the open
position) is refined by bisection to 0.05° and reported with its points; overlaps already present when
open are reported as such. The step keeps the distal tip's motion per step below half the thinnest
section thickness. Solids are exact for the loft, but detection tests surface sample points, so thin-edge
crossings smaller than the sampling can still be missed: this is screening.

* Split at the hinge plane, as the analyses split the geometry, the distal root's trailing region swings
  into the proximal part at once (−0.03° for the 800 mm design): that is the contact the joint must
  avoid. The display therefore uses a *joint zone*: the inboard half-disk of the analysed surface about
  the pivot (radius = in-plane extent of the sections it covers + 2 %) moves with the distal part, so the
  two parts cannot interlock at the joint for any fold (a disk rotating about its centre stays inside
  itself). The joint zone is drawn as such and labelled "eklem geometrisi tanımlı değil".
* With that display relief the 800 mm design folds without contact of its defined surfaces to **−66.6°**
  (a property of this construction, whose joint radius is chosen by the display, not of a declared joint); there the distal part's
  trailing region meets the proximal trailing region about 26 mm inboard of the hinge — an in-plane fold
  about an interior pivot always does this for a blade of finite chord. Deeper folding needs a declared
  joint design (e.g. a clevis–tang with axial offset). Possible contacts with the tip placeholder appear
  near −153°; no blade-to-blade or hub contact occurs. The deployment runs (≤ −22.5°) are clear.
* **No interlocked defined surfaces are drawn:** a requested preview angle beyond the first certain
  contact is shown at the last clear angle of the bisection, with a warning and the contact points marked.
  Placeholders and the hub do not clamp the pose (their contacts are only possible).
* This is display screening, not GEOM-03/04 qualification evidence.

## Results on the surface (`pyfoldable/visualization/blade_results.py`)

A sectional value belongs to a radial interval and is drawn as one colour across the whole chord of its
strip — never a chordwise pressure distribution (stated next to every coloured view). Kinds are kept
apart: *per unit span* (BEM dT/dr, dQ/dr; coupled element axial force / element width), *element total*
(BEM annulus thrust/torque; coupled element axial force dF_z), *section state* (α, cl, cd, Re, Mach,
induced velocity).  Element widths are rebuilt with the deck's own allocation
(`coupled.deck._allocate_elements`: one continuous line over the station intervals for continuous_rbf,
each segment's sections for split_rigid) and accepted only when they reproduce the recorded element
centres; otherwise midpoint widths are used and the field is labelled approximate. Caps, joint cuts and placeholders carry no result (grey).

## In the application

* **Tasarım → Geometri önizlemesi:** *3B* (cameras) and *Plan* (top orthographic of the same surface),
  with the fold-contact summary. *Profil* unchanged.
* **Sonuçlar → BEM:** "Kanat üzerinde sonuç (3B)": quantity, colour scale (this result or manual limits
  for comparing cases), inspected section r with its strip value, linked radial plot, exports.
* **Sonuçlar → Dinamik bağlaşık → 3B oynatma:** accepted window, quantity, frame (*rotor-relative*:
  azimuth removed; *rotating*: laboratory), colour scale fixed over all windows of the record (or manual),
  blades posed from that window's MBDyn body states, linked radial plot and response timeline at the same
  window, short coloured playback on request (coarse mesh). The previous uncoloured playback is kept in an
  expander.
* **Akış ve tepki:** the 3-D scene uses the same coloured blades; blades, colours, vortex particles,
  panel wake and velocity plane belong to the same accepted window; the rotor-relative frame rotates them
  all together.
* **Exports:** STL of the analysed surfaces (mm), legacy VTK with region/part/blade ids and the selected
  quantity per cell (NaN where no data) for ParaView, strip values as CSV.
