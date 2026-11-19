# Calculation and assumption summary — 13in-E

Design identity `05421f7bdb1be0c8983142899e39eb78951381367998ecdb689874ecc20074aa`. Section identity `NACA2412-te0.80mm-x0.50` (catalog NACA2412 with the trailing edge thickened to 0.8 mm: a new aerodynamic section; retained polars of the catalog profile apply only approximately and an XFOIL family for this section is required before aerodynamic conclusions).

Physical qualification: **false**. Exploratory material values: Keşif varsayımı: FFF %100 doluluk için tipik veri sayfası/literatür aralığının alt tarafı; sahibin yazıcısı, filamenti ve baskı süreci için ölçülmedi.

## Geometry

- Diameter 330.2 mm, blades 2, hinge (joint plane) r_j = 99.0 mm (proximal 84.0 mm > distal 66.1 mm).
- Planform from `project_250` scaled to the diameter, chord ×1.0, twist ×0.86: r 33.0: c 37.0, β 26.7°; r 54.0: c 35.3, β 22.8°; r 65.2: c 33.6, β 19.1°; r 66.0: c 33.5, β 18.8°; r 76.5: c 30.6, β 13.6°; r 87.8: c 27.7, β 8.9°; r 99.0: c 25.8, β 6.6°; r 99.1: c 25.8, β 6.6°; r 110.2: c 24.1, β 6.7°; r 121.5: c 23.1, β 7.6°; r 132.1: c 21.9, β 7.8°; r 132.8: c 21.7, β 7.8°; r 144.0: c 17.7, β 6.9°; r 161.8: c 10.6, β 4.3°
- Axial offset δ = 6.0 mm (plane A z = 0 proximal quarter-chord plane → plane B distal); deployed step at the joint 6.0 mm, face gap 0.3 mm, stop nose 2.0 mm ahead of the leading edge.
- Lug stack 10.07 mm (proximal 4.72, gap 0.3, distal 5.05; full-depth lugs: each spans its blade section over the boss); lug mid-planes 5.19 mm apart; pin Ø3.0, hole Ø3.20.

## Full-travel clearance (actual solids)

- Required travel 140° (owner decision; template declares 180°); clear to 140°. Folded stop (stop nose meets the proximal): 144°. Smallest vertical body clearance 0.61 mm at -140° (negative = interference depth).
- With worst-case joint play (tilt 3.13°, limited by lug yüz aralığı; tip droop 3.91 mm): -1.05 mm at -140°.
- Offset that clears the full travel: ≈ 6.0 mm nominal, ≈ 7.1 mm with play (estimated from the deficit; confirm by re-running at that offset).
- Method: sütun yöntemi 0.25 mm ızgara, 1.0° adım; tesselasyon 0,05 mm. Exact OpenCASCADE distance proximal–distal: 0° → 0.000 mm, -2° → 0.213 mm, -140° → 0.300 mm (0 at the open stop is the designed seat; the column gap is a vertical clearance ≥ the exact distance).
- Open-stop seat: zero nominal clearance between separately printed faces; the as-printed open angle varies by about ±0.1 mm / lever (≈ ±0.7° at 8 mm). Measure it on the fit test.

## Mass properties (estimate until weighed)

- proximal: 19.89 g, CG (2.71, 27.63, -0.77) mm — PLA ρ=1.24 g/cm³, doluluk 100%, duvar 1.2 mm
- distal: 3.43 g, CG (3.60, 121.10, 5.65) mm — PLA ρ=1.24 g/cm³, doluluk 100%, duvar 1.2 mm
- pin_set: 1.11 g, CG (-0.00, 99.00, 3.30) mm — pim seti (çelik)
- blade: 24.43 g, CG (2.71, 43.99, 0.31) mm — kanat (proksimal + distal + pim seti)
- Distal inertia about its CG [g·mm²]: [[1133.5,  -31.3,    7. ],  [ -31.3,  117.1,  -11.2],  [   7. ,  -11.2, 1240.1]]
- Distal CG 3.60 mm aft of the pin; centrifugal moment about the pin seats the segment on the open stop.

## Deployed loads and single-lug checks (what-if speeds; no owner maximum speed)

| RPM | case | seated | centrifugal [N] | stop [N] | pin [N] | couple [N·mm] | governing check | limit RPM (SF 2.0) | min margin |
|---|---|---|---|---|---|---|---|---|---|
| 3000 | what-if, centrifugal only | yes | 41 | 17 | 58 | 68 | Stop burnu kök eğilmesi | 3286 | +0.20 |
| 4000 | what-if, centrifugal only | yes | 73 | 30 | 103 | 121 | Stop burnu kök eğilmesi | 3286 | -0.33 |
| 5000 | what-if, centrifugal only | yes | 114 | 46 | 160 | 189 | Stop burnu kök eğilmesi | 3286 | -0.57 |
| 6000 | what-if, centrifugal only | yes | 164 | 67 | 231 | 272 | Stop burnu kök eğilmesi | 3286 | -0.70 |
| 7000 | what-if, centrifugal only | yes | 223 | 91 | 314 | 371 | Stop burnu kök eğilmesi | 3286 | -0.78 |
| 8000 | what-if, centrifugal only | yes | 292 | 118 | 410 | 484 | Stop burnu kök eğilmesi | 3286 | -0.83 |

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
- OK Lug kalınlığı (katman): 24 (≥ 10 katman)
- OK Lug–kanat bağlantısı (proksimal): 100% kesit kalınlığı (lug bandı, pim çevresinde kendi kanat kesitinin ≥ %60'ını kavramalı)
- OK Lug–kanat bağlantısı (distal): 100% kesit kalınlığı (lug bandı, pim çevresinde kendi kanat kesitinin ≥ %60'ını kavramalı)
- OK Firar kenarı kalınlığı (uç): 0.80 mm (≥ 0.8 mm (kesit NACA2412-te0.80mm-x0.50))
- OK Lug aralığı (katman): 1.5 (ayrı parçalar; aralık montajda donanımla kurulur)
- OK Burulmuş yüzeyler: azami 27° (rotor düzlemi tablada: alt yüzey destek ister (destek arayüzü alt yüzeyde))
- OK Tabla sığması: rotor_hub_proximal: 42.5×207.3×18.8 mm (tabla 256×256×256, döndürme 7.5°)
- OK Tabla sığması: distal: 71.6×27.6×10.1 mm (tabla 256×256×256, döndürme 85.0°)
- OK Tabla sığması: fit_proximal: 30.7×27.5×8.5 mm (tabla 256×256×256, döndürme 0.0°)
- OK Tabla sığması: fit_distal: 27.7×27.5×10.1 mm (tabla 256×256×256, döndürme 0.0°)
- OK Tabla sığması: hole_coupon: 54.0×16.0×4.7 mm (tabla 256×256×256, döndürme 0.0°)
