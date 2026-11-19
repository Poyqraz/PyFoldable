# Calculation and assumption summary — 13in-D

Design identity `4ad25a2ced13d0ead45c2e029d1de060742f8287dbeb782633b624373a7532e9`. Section identity `NACA2412-te0.80mm-x0.50` (catalog NACA2412 with the trailing edge thickened to 0.8 mm: a new aerodynamic section; retained polars of the catalog profile apply only approximately and an XFOIL family for this section is required before aerodynamic conclusions).

Physical qualification: **false**. Exploratory material values: Keşif varsayımı: FFF %100 doluluk için tipik veri sayfası/literatür aralığının alt tarafı; sahibin yazıcısı, filamenti ve baskı süreci için ölçülmedi.

## Geometry

- Diameter 330.2 mm, blades 2, hinge (joint plane) r_j = 99.0 mm (proximal 84.0 mm > distal 66.1 mm).
- Planform from `project_250` scaled to the diameter, chord ×1.0, twist ×0.35: r 33.0: c 37.0, β 10.8°; r 66.0: c 34.3, β 8.4°; r 99.1: c 30.4, β 6.0°; r 132.1: c 22.5, β 3.5°; r 161.8: c 10.6, β 1.8°
- Axial offset δ = 6.0 mm (plane A z = 0 proximal quarter-chord plane → plane B distal); deployed step at the joint 6.0 mm, face gap 0.3 mm, stop nose 2.0 mm ahead of the leading edge.
- Lug stack 10.07 mm (proximal 4.58, gap 0.3, distal 5.19; full-depth lugs: each spans its blade section over the boss); lug mid-planes 5.18 mm apart; pin Ø3.0, hole Ø3.20.

## Full-travel clearance (actual solids)

- Required travel 140° (owner decision; template declares 180°); clear to 140°. Folded stop (stop nose meets the proximal): 144°. Smallest vertical body clearance 0.65 mm at -99° (negative = interference depth).
- With worst-case joint play (tilt 3.13°, limited by lug yüz aralığı; tip droop 3.91 mm): -0.91 mm at -99°.
- Offset that clears the full travel: ≈ 6.0 mm nominal, ≈ 7.4 mm with play (estimated from the deficit; confirm by re-running at that offset).
- Method: sütun yöntemi 0.25 mm ızgara, 1.0° adım; tesselasyon 0,05 mm. Exact OpenCASCADE distance proximal–distal: 0° → 0.000 mm, -2° → 0.213 mm, -99° → 0.300 mm (0 at the open stop is the designed seat; the column gap is a vertical clearance ≥ the exact distance).
- Open-stop seat: zero nominal clearance between separately printed faces; the as-printed open angle varies by about ±0.1 mm / lever (≈ ±0.7° at 8 mm). Measure it on the fit test.

## Mass properties (estimate until weighed)

- proximal: 21.03 g, CG (3.15, 29.13, -0.24) mm — PLA ρ=1.24 g/cm³, doluluk 100%, duvar 1.2 mm
- distal: 4.05 g, CG (3.86, 119.66, 5.82) mm — PLA ρ=1.24 g/cm³, doluluk 100%, duvar 1.2 mm
- pin_set: 1.11 g, CG (-0.00, 99.00, 3.44) mm — pim seti (çelik)
- blade: 26.19 g, CG (3.12, 46.08, 0.85) mm — kanat (proksimal + distal + pim seti)
- Distal inertia about its CG [g·mm²]: [[1250.8,  -18.5,    4.7],  [ -18.5,  179.9,  -18. ],  [   4.7,  -18. , 1418. ]]
- Distal CG 3.86 mm aft of the pin; centrifugal moment about the pin seats the segment on the open stop.

## Deployed loads and single-lug checks (what-if speeds; no owner maximum speed)

| RPM | case | seated | centrifugal [N] | stop [N] | pin [N] | couple [N·mm] | governing check | limit RPM (SF 2.0) | min margin |
|---|---|---|---|---|---|---|---|---|---|
| 3000 | what-if, centrifugal only | yes | 48 | 20 | 67 | 89 | Pim eğilmesi (P·a/2) | 3697 | +0.52 |
| 4000 | what-if, centrifugal only | yes | 85 | 35 | 120 | 158 | Pim eğilmesi (P·a/2) | 3697 | -0.15 |
| 5000 | what-if, centrifugal only | yes | 133 | 54 | 187 | 247 | Pim eğilmesi (P·a/2) | 3697 | -0.45 |
| 6000 | what-if, centrifugal only | yes | 191 | 78 | 269 | 356 | Pim eğilmesi (P·a/2) | 3697 | -0.62 |
| 7000 | what-if, centrifugal only | yes | 260 | 106 | 367 | 484 | Pim eğilmesi (P·a/2) | 3697 | -0.72 |
| 8000 | what-if, centrifugal only | yes | 340 | 139 | 479 | 632 | Pim eğilmesi (P·a/2) | 3697 | -0.79 |

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
- OK Lug kalınlığı (katman): 23 (≥ 10 katman)
- OK Lug–kanat bağlantısı (proksimal): 100% kesit kalınlığı (lug bandı, pim çevresinde kendi kanat kesitinin ≥ %60'ını kavramalı)
- OK Lug–kanat bağlantısı (distal): 100% kesit kalınlığı (lug bandı, pim çevresinde kendi kanat kesitinin ≥ %60'ını kavramalı)
- OK Firar kenarı kalınlığı (uç): 0.80 mm (≥ 0.8 mm (kesit NACA2412-te0.80mm-x0.50))
- OK Lug aralığı (katman): 1.5 (ayrı parçalar; aralık montajda donanımla kurulur)
- OK Burulmuş yüzeyler: azami 11° (rotor düzlemi tablada: alt yüzey destek ister (destek arayüzü alt yüzeyde))
- OK Tabla sığması: rotor_hub_proximal: 54.1×206.0×12.9 mm (tabla 256×256×256, döndürme 10.0°)
- OK Tabla sığması: distal: 70.6×33.0×10.2 mm (tabla 256×256×256, döndürme 77.5°)
- OK Tabla sığması: fit_proximal: 34.2×27.5×6.5 mm (tabla 256×256×256, döndürme 0.0°)
- OK Tabla sığması: fit_distal: 33.2×27.5×10.2 mm (tabla 256×256×256, döndürme 0.0°)
- OK Tabla sığması: hole_coupon: 54.0×16.0×4.6 mm (tabla 256×256×256, döndürme 0.0°)
