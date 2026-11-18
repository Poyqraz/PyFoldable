# Calculation and assumption summary — 13in-F1S

Design identity `8f078b088d560217cfea4171240bd69f3175fada294e0a7a35277287b1ad65b4`. Section identity `NACA2412-te0.80mm-x0.50` (catalog NACA2412 with the trailing edge thickened to 0.8 mm: a new aerodynamic section; retained polars of the catalog profile apply only approximately and an XFOIL family for this section is required before aerodynamic conclusions).

Physical qualification: **false**. Exploratory material values: Keşif varsayımı: FFF %100 doluluk için tipik veri sayfası/literatür aralığının alt tarafı; sahibin yazıcısı, filamenti ve baskı süreci için ölçülmedi.

## Geometry

- Diameter 330.2 mm, blades 2, hinge (joint plane) r_j = 99.0 mm (proximal 84.0 mm > distal 66.1 mm).
- Planform from `project_250` scaled to the diameter, chord ×1.0, twist ×0.86: r 33.0: c 37.0, β 26.7°; r 54.0: c 35.3, β 22.8°; r 65.2: c 33.6, β 19.6°; r 66.0: c 33.5, β 19.3°; r 76.5: c 30.6, β 15.0°; r 87.8: c 27.7, β 11.0°; r 99.0: c 25.8, β 8.8°; r 99.1: c 25.8, β 8.8°; r 110.2: c 24.1, β 8.3°; r 121.5: c 23.1, β 8.4°; r 132.1: c 21.9, β 8.0°; r 132.8: c 21.7, β 8.0°; r 144.0: c 17.7, β 6.9°; r 161.8: c 10.6, β 4.3°
- Axial offset δ = 6.5 mm (plane A z = 0 proximal quarter-chord plane → plane B distal); deployed step at the joint 6.5 mm, face gap 0.3 mm, stop nose 4.0 mm ahead of the leading edge.
- Lug stack 10.84 mm (proximal 5.16, gap 0.3, distal 5.38; full-depth lugs: each spans its blade section over the boss); lug mid-planes 5.57 mm apart; pin Ø4.0, hole Ø4.20.

## Full-travel clearance (actual solids)

- Required travel 140° (owner decision; template declares 180°); clear to 140°. Folded stop (stop nose meets the proximal): 144°. Smallest vertical body clearance 0.58 mm at -106° (negative = interference depth).
- With worst-case joint play (tilt 3.13°, limited by lug yüz aralığı; tip droop 3.91 mm): -0.96 mm at -140°.
- Offset that clears the full travel: ≈ 6.5 mm nominal, ≈ 7.5 mm with play (estimated from the deficit; confirm by re-running at that offset).
- Method: sütun yöntemi 0.25 mm ızgara, 1.0° adım; tesselasyon 0,05 mm. Exact OpenCASCADE distance proximal–distal: 0° → 0.000 mm, -2° → 0.213 mm, -106° → 0.300 mm (0 at the open stop is the designed seat; the column gap is a vertical clearance ≥ the exact distance).
- Open-stop seat: zero nominal clearance between separately printed faces; the as-printed open angle varies by about ±0.1 mm / lever (≈ ±0.7° at 8 mm). Measure it on the fit test.

## Mass properties (estimate until weighed)

- proximal: 19.93 g, CG (2.67, 27.85, -0.80) mm — PLA ρ=1.24 g/cm³, doluluk 100%, duvar 1.2 mm
- distal: 3.53 g, CG (3.23, 120.55, 5.97) mm — PLA ρ=1.24 g/cm³, doluluk 100%, duvar 1.2 mm
- pin_set: 1.95 g, CG (-0.00, 99.00, 3.55) mm — pim seti (çelik)
- blade: 25.41 g, CG (2.55, 46.18, 0.47) mm — kanat (proksimal + distal + pim seti)
- Distal inertia about its CG [g·mm²]: [[1174.7,  -56.7,    4.1],  [ -56.7,  135.9,  -21.8],  [   4.1,  -21.8, 1294.7]]
- Distal CG 3.23 mm aft of the pin; centrifugal moment about the pin seats the segment on the open stop.

## Deployed loads and single-lug checks (what-if speeds; no owner maximum speed)

| RPM | case | seated | centrifugal [N] | stop [N] | pin [N] | couple [N·mm] | governing check | limit RPM (SF 2.0) | min margin |
|---|---|---|---|---|---|---|---|---|---|
| 3000 | what-if, centrifugal only | yes | 42 | 14 | 56 | 79 | Stop burnu kök eğilmesi | 4701 | +1.46 |
| 4000 | what-if, centrifugal only | yes | 75 | 24 | 99 | 141 | Stop burnu kök eğilmesi | 4701 | +0.38 |
| 5000 | what-if, centrifugal only | yes | 117 | 38 | 154 | 220 | Stop burnu kök eğilmesi | 4701 | -0.12 |
| 6000 | what-if, centrifugal only | yes | 168 | 54 | 222 | 317 | Stop burnu kök eğilmesi | 4701 | -0.39 |
| 7000 | what-if, centrifugal only | yes | 229 | 74 | 302 | 432 | Stop burnu kök eğilmesi | 4701 | -0.55 |
| 8000 | what-if, centrifugal only | yes | 299 | 96 | 395 | 564 | Stop burnu kök eğilmesi | 4701 | -0.65 |

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

- OK Delik çevresi et kalınlığı: 3.40 mm (≥ 2 çevre duvarı (2.4 mm))
- OK Lug kalınlığı (katman): 26 (≥ 10 katman)
- OK Lug–kanat bağlantısı (proksimal): 100% kesit kalınlığı (lug bandı, pim çevresinde kendi kanat kesitinin ≥ %60'ını kavramalı)
- OK Lug–kanat bağlantısı (distal): 100% kesit kalınlığı (lug bandı, pim çevresinde kendi kanat kesitinin ≥ %60'ını kavramalı)
- OK Firar kenarı kalınlığı (uç): 0.80 mm (≥ 0.8 mm (kesit NACA2412-te0.80mm-x0.50))
- OK Lug aralığı (katman): 1.5 (ayrı parçalar; aralık montajda donanımla kurulur)
- OK Burulmuş yüzeyler: azami 27° (rotor düzlemi tablada: alt yüzey destek ister (destek arayüzü alt yüzeyde))
- OK Tabla sığması: rotor_hub_proximal: 44.0×208.2×18.8 mm (tabla 256×256×256, döndürme 5.0°)
- OK Tabla sığması: distal: 71.6×29.5×10.8 mm (tabla 256×256×256, döndürme 85.0°)
- OK Tabla sığması: fit_proximal: 32.6×27.5×9.3 mm (tabla 256×256×256, döndürme 0.0°)
- OK Tabla sığması: fit_distal: 29.6×27.5×10.8 mm (tabla 256×256×256, döndürme 0.0°)
- OK Tabla sığması: hole_coupon: 54.0×16.0×5.2 mm (tabla 256×256×256, döndürme 0.0°)
