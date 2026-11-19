# Calculation and assumption summary — 13in-B

Design identity `eb1c40c24c2d6cd22269d156a86f687bb1bf7d2fbe32e75fe7428a440ac78f9e`. Section identity `NACA2412-te0.80mm-x0.50` (catalog NACA2412 with the trailing edge thickened to 0.8 mm: a new aerodynamic section; retained polars of the catalog profile apply only approximately and an XFOIL family for this section is required before aerodynamic conclusions).

Physical qualification: **false**. Exploratory material values: Keşif varsayımı: FFF %100 doluluk için tipik veri sayfası/literatür aralığının alt tarafı; sahibin yazıcısı, filamenti ve baskı süreci için ölçülmedi.

## Geometry

- Diameter 330.2 mm, blades 2, hinge (joint plane) r_j = 99.0 mm (proximal 84.0 mm > distal 66.1 mm).
- Planform from `project_250` scaled to the diameter, chord ×1.0, twist ×0.6: r 33.0: c 37.0, β 18.6°; r 66.0: c 34.3, β 14.4°; r 99.1: c 30.4, β 10.2°; r 132.1: c 22.5, β 6.0°; r 161.8: c 10.6, β 3.0°
- Axial offset δ = 9.5 mm (plane A z = 0 proximal quarter-chord plane → plane B distal); deployed step at the joint 9.5 mm, face gap 0.3 mm, stop nose 2.0 mm ahead of the leading edge.
- Lug stack 14.12 mm (proximal 6.72, gap 0.3, distal 7.10; full-depth lugs: each spans its blade section over the boss); lug mid-planes 7.21 mm apart; pin Ø3.0, hole Ø3.20.

## Full-travel clearance (actual solids)

- Required travel 140° (owner decision; template declares 180°); clear to 140°. Folded stop (stop nose meets the proximal): 144°. Smallest vertical body clearance 2.18 mm at -103° (negative = interference depth).
- With worst-case joint play (tilt 3.13°, limited by lug yüz aralığı; tip droop 3.91 mm): 0.64 mm at -104°.
- Offset that clears the full travel: ≈ 9.5 mm nominal, ≈ 9.5 mm with play (estimated from the deficit; confirm by re-running at that offset).
- Method: sütun yöntemi 0.25 mm ızgara, 1.0° adım; tesselasyon 0,05 mm. Exact OpenCASCADE distance proximal–distal: 0° → 0.000 mm, -2° → 0.213 mm, -103° → 0.300 mm (0 at the open stop is the designed seat; the column gap is a vertical clearance ≥ the exact distance).
- Open-stop seat: zero nominal clearance between separately printed faces; the as-printed open angle varies by about ±0.1 mm / lever (≈ ±0.7° at 8 mm). Measure it on the fit test.

## Mass properties (estimate until weighed)

- proximal: 21.20 g, CG (3.04, 29.99, -0.56) mm — PLA ρ=1.24 g/cm³, doluluk 100%, duvar 1.2 mm
- distal: 4.33 g, CG (3.48, 118.39, 8.82) mm — PLA ρ=1.24 g/cm³, doluluk 100%, duvar 1.2 mm
- pin_set: 1.33 g, CG (-0.00, 99.00, 5.09) mm — pim seti (çelik)
- blade: 26.85 g, CG (2.96, 47.65, 1.23) mm — kanat (proksimal + distal + pim seti)
- Distal inertia about its CG [g·mm²]: [[1367.1,  -48.1,    4.9],  [ -48.1,  200.9,  -42.6],  [   4.9,  -42.6, 1537.1]]
- Distal CG 3.48 mm aft of the pin; centrifugal moment about the pin seats the segment on the open stop.

## Deployed loads and single-lug checks (what-if speeds; no owner maximum speed)

| RPM | case | seated | centrifugal [N] | stop [N] | pin [N] | couple [N·mm] | governing check | limit RPM (SF 2.0) | min margin |
|---|---|---|---|---|---|---|---|---|---|
| 3000 | what-if, centrifugal only | yes | 51 | 19 | 69 | 144 | Stop burnu kök eğilmesi | 3012 | +0.01 |
| 4000 | what-if, centrifugal only | yes | 90 | 34 | 123 | 255 | Stop burnu kök eğilmesi | 3012 | -0.43 |
| 5000 | what-if, centrifugal only | yes | 140 | 52 | 193 | 399 | Stop burnu kök eğilmesi | 3012 | -0.64 |
| 6000 | what-if, centrifugal only | yes | 202 | 75 | 278 | 575 | Stop burnu kök eğilmesi | 3012 | -0.75 |
| 7000 | what-if, centrifugal only | yes | 275 | 103 | 378 | 782 | Stop burnu kök eğilmesi | 3012 | -0.81 |
| 8000 | what-if, centrifugal only | yes | 359 | 134 | 494 | 1022 | Stop burnu kök eğilmesi | 3012 | -0.86 |

Ön analitik tahmin: tek lug/tek kesme el formülleri, keşif malzeme değerleri ve güvenlik katsayısı; gerilme yığılması (düzlem içi FE ayrı), temas, sürtünme, yorulma ve baskı anizotropisi yok. Parça niteliklendirmesi değildir.

Pin steel: Keşif varsayımı: ISO 2341 pim çeliği (ör. 4.6 sınıfı) için düşük taraf; tedarikçi verisiyle değiştirin.

## Owner inputs still missing

- azami devir
- gerekli itki
- motor
- yazıcı modeli/malzeme sınıfı/süreç (keşif varsayımı kullanılıyor)
- motor bağlantısı (göbek yer tutucu)
- gerekli katlanma açısı (varsayım 140°; şablon 180° bildirir)

## Printability

- OK Delik çevresi et kalınlığı: 3.90 mm (≥ 2 çevre duvarı (2.4 mm))
- OK Lug kalınlığı (katman): 34 (≥ 10 katman)
- OK Lug–kanat bağlantısı (proksimal): 100% kesit kalınlığı (lug bandı, pim çevresinde kendi kanat kesitinin ≥ %60'ını kavramalı)
- OK Lug–kanat bağlantısı (distal): 100% kesit kalınlığı (lug bandı, pim çevresinde kendi kanat kesitinin ≥ %60'ını kavramalı)
- OK Firar kenarı kalınlığı (uç): 0.80 mm (≥ 0.8 mm (kesit NACA2412-te0.80mm-x0.50))
- OK Lug aralığı (katman): 1.5 (ayrı parçalar; aralık montajda donanımla kurulur)
- OK Burulmuş yüzeyler: azami 19° (rotor düzlemi tablada: alt yüzey destek ister (destek arayüzü alt yüzeyde))
- OK Tabla sığması: rotor_hub_proximal: 53.0×206.0×17.4 mm (tabla 256×256×256, döndürme 10.0°)
- OK Tabla sığması: distal: 70.6×32.8×14.2 mm (tabla 256×256×256, döndürme 77.5°)
- OK Tabla sığması: fit_proximal: 33.7×27.5×10.6 mm (tabla 256×256×256, döndürme 0.0°)
- OK Tabla sığması: fit_distal: 32.9×27.5×14.2 mm (tabla 256×256×256, döndürme 0.0°)
- OK Tabla sığması: hole_coupon: 54.0×16.0×6.7 mm (tabla 256×256×256, döndürme 0.0°)
