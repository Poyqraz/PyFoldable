# Measurement kit: 13in-E joint (hole coupon + fit pair)

A measurement prototype for pin fit, joint play, friction and stop seating. It is **not** a selection of this candidate
as the powered propeller, and it qualifies nothing physically. All files are in millimetres. Kit design identity:
`befda1e67be870e3de644afb8b24329fa85a9d444054146b036431cdc62dc9bd`; the record must carry the same identity.

## Parts and print

- `hole_coupon`: a plate of the proximal lug thickness (4.72 mm) with holes Ø3.0, Ø3.1, Ø3.2, Ø3.3, Ø3.4 (k notches beside hole k).
- `fit_proximal_cX` / `fit_distal_cX`: the joint with a CAD diametral hole clearance of X mm (0.0, 0.1, 0.2, 0.3, 0.4). The proximal stub
  has a flat clamp block; the distal stub has a flat load tab with a Ø3.2 hole 30.0 mm from the pin axis
  on the span line through the pin.
- Pin axis along printer Z for every part, with the settings you will use for the full blade. The proximal prints
  upright on its lug's washer-seat face (the stub is trimmed to that plane); the distal prints **inverted** on its
  lug's washer-seat face, so the running face between the lugs is a free top surface and needs no support. Record
  printer, nozzle, plate, filament, layer, walls, infill and every change from the proposed settings.
- Hardware per fit pair: one pin ISO 2341-A Ø3 (kafa Ø5×1) + DIN 6799 kanalı (Ø2,3 × 0,64), two DIN 433 washers (Ø3.2 ×
  Ø6 × 0.5 mm), one DIN 6799 E-clip; pin length under the head
  12.5 mm. Measure the actual pin diameter.
- Print orientation (as the full parts): Rotor düzlemi tablada (z yukarı); pim ekseni yazıcı z ekseninde, lug yükü katmanlar boyunca.
- Joint of this kit: δ 6 mm, lugs 4.72 / 5.05 mm (full depth, 0.2 mm proud of the
  blade), lug gap 0.3 mm, boss radius 5.5 mm, pin Ø3;
  stop nose 4 mm deep reaching 2 mm ahead of the leading edge onto a
  4 mm pad.
- Play measured on this kit is **direct** evidence only for this design (same identity apart from the hole
  clearance) and then sets its print-clearance verdict with the expanded uncertainty. Applied to any other design it
  is **transferred**: shown for exploration, while that design's verdict keeps the worst-case model.

## Sequence and measurements

1. **Coupon.** Push the real pin through every hole by hand. Rate each hole: `girmez` (does not enter), `sıkı` (turns
   only with force), `akıcı` (turns freely, no visible wobble), `boşluklu` (visible wobble). Optionally measure each hole
   with pin gauges or drill blanks.
2. **Fit pair: one decision.** Print the pair whose clearance equals the **smallest `akıcı` step**; a pair exists for
   every coupon step. If no hole is `akıcı` (all `sıkı`/`girmez`), do not pick a neighbour: generate the exact pair
   with a larger clearance (page *Prototip → Bu tasarımın ölçüm kitini oluştur* with that hole clearance, or
   `fit.export_kit(d, folder, clearances=(c,))`). If even step 0.0 wobbles, print c0.00 and note it. Record which pair
   you printed (`fit_pair_clearance_mm`).
3. **Dimensions.** Measure both lug thicknesses at the boss with calipers (model 4.72 / 5.05 mm).
4. **Axial float a.** Clamp the proximal block in a vise, rotor plane level. Move the distal lug up and down along the pin;
   measure the free movement at the boss (dial indicator or feeler gauges). Model: 0.30 mm.
5. **Tilt.** Hang/push a known load (about 2 N) up and then down at the tab hole; measure the total vertical movement Δ
   of the tab at the hole. Tilt φ = max(0, Δ − a) / (2 L), L = 30.0 mm. Model (worst case):
   3.13°.
   **Repeat a and Δ at least three times** (reassemble between repeats; if you print two fit pairs, measure both) and
   record the count, the mean values and the range (largest − smallest) of each, with the instrument resolution. The
   verdict subtracts k = 2 times the combined uncertainty (resolution, repeat range, print variation from the lug
   thicknesses) from the worst-case gap.
6. **Friction.** Rotor plane level, distal open on its stop. Pull at the tab hole with a spring scale, horizontally and
   perpendicular to the lever, toward the fold direction (toward the trailing edge); record the force at which folding
   starts. Torque T = F L.
7. **Stop seating.** Hold the distal open by hand; check the nose–pad contact with a 0.05 mm feeler and against light.
   Record the gap and whether the faces seat flat.
8. **Folded stop.** Fold until the nose stops; measure the travel with a protractor (model
   144.0°).
9. **Masses.** Weigh both fit parts without hardware (model 7.78 / 2.46 g
   with PLA, walls 1.2 mm, infill
   100%).

## Record

Copy `fit_record_template.json`, fill every required field and load it in *Prototip → Ölçüm prototipi* (or call
`pyfoldable.prototype.fit.parse` / `apply`). Unknown keys, missing or out-of-range values and a record of another kit are
refused. The measured play then replaces the worst-case model play in the full-travel clearance check of the design the
record is applied to; the measured clearance becomes its hole clearance.

| Field | Meaning |
|---|---|
| `schema` | kayıt şeması |
| `kit_design_sha256` | ölçüm kitinin tasarım kimliği (predictions.json) |
| `print_printer` | yazıcı modeli |
| `print_material_family` | malzeme ailesi: PLA / ASA / ABS / PETG / other |
| `print_filament_product` | filament ürünü (ör. Eco Smart Standard PLA) |
| `print_filament_manufacturer` | filament üreticisi (doğrulanmadıysa null) |
| `print_filament_lot` | renk / parti numarası |
| `print_plate` | baskı tablası (ör. Textured PEI) |
| `print_slicer` | dilimleyici ve sürümü |
| `print_project_sha256` | basılan Bambu Studio projesinin SHA-256 özeti |
| `print_nozzle_mm` | nozul çapı [mm] |
| `print_layer_mm` | katman yüksekliği [mm] |
| `print_walls` | çevre duvarı sayısı |
| `print_infill_fraction` | doluluk oranı (0–1) |
| `pin_measured_diameter_mm` | pimin ölçülen çapı [mm] |
| `coupon_fit` | kupon deliği başına geçme: girmez / sıkı / akıcı / boşluklu |
| `coupon_hole_mm` | kupon deliği başına ölçülen çap [mm] (pim mastarı; bilinmiyorsa null) |
| `fit_pair_clearance_mm` | basılan uyum çiftinin CAD delik boşluğu [mm] |
| `lug_thickness_proximal_mm` | proksimal lug ölçülen kalınlığı [mm] |
| `lug_thickness_distal_mm` | distal lug ölçülen kalınlığı [mm] |
| `axial_float_mm` | distal lugun pim boyunca serbest hareketi a [mm] |
| `tilt_load_n` | eğilme ölçümündeki ± yük [N] |
| `tilt_range_at_tab_mm` | yük deliğinde toplam düşey serbest hareket Δ [mm] |
| `friction_breakaway_n` | katlanmayı başlatan kuvvet, delikte kola dik [N] |
| `stop_gap_mm` | distal elle açık tutulurken burun–ped aralığı [mm] (sentil) |
| `stop_seats` | burun pede tam yüzeyle oturuyor mu (ışık testi) |
| `folded_stop_deg` | katlanmış stop açısı [°] (açıölçer) |
| `pin_grip_length_mm` | pimin kafa altından kanalın yakın kenarına ölçülen boyu [mm] |
| `washer_stack_mm` | yığındaki pul + şim toplam ölçülen kalınlığı [mm] |
| `hardware_source` | pim/pul/segman tedarikçisi ve parça numaraları |
| `print_changes` | önerilen ayarlardan farklar (destek, brim, telafiler, hız, profil) |
| `measurement_resolution_mm` | boşluk ölçümünde kullanılan aletin çözünürlüğü [mm] |
| `repeat_count` | eksenel boşluk ve Δ ölçümlerinin tekrar sayısı (birden çok uyum çiftinde toplam) |
| `axial_float_spread_mm` | tekrarlar arasında eksenel boşluğun aralığı (en büyük − en küçük) [mm] |
| `tilt_range_spread_mm` | tekrarlar arasında Δ'nın aralığı [mm] |
| `mass_fit_proximal_g` | uyum çifti proksimal kütlesi [g] |
| `mass_fit_distal_g` | uyum çifti distal kütlesi [g] |
| `notes` | serbest not |

Limits: zero-load friction only (pin friction under centrifugal load is not measured); static play, not fatigue or
creep; one print, one pin. Physical qualification: false.
