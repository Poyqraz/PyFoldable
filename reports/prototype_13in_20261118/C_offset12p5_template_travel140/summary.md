# Calculation and assumption summary — 13in-C

Design identity `4c2c3b5c380458dd8a13a8c1fe9a30d7e34c7de62d517a7c048b5f8f4cf93458`. Section identity `NACA2412-te0.80mm-x0.50` (catalog NACA2412 with the trailing edge thickened to 0.8 mm: a new aerodynamic section; retained polars of the catalog profile apply only approximately and an XFOIL family for this section is required before aerodynamic conclusions).

Physical qualification: **false**. Exploratory material values: Keşif varsayımı: FFF %100 doluluk için tipik veri sayfası/literatür aralığının alt tarafı; sahibin yazıcısı, filamenti ve baskı süreci için ölçülmedi.

## Geometry

- Diameter 330.2 mm, blades 2, hinge (joint plane) r_j = 99.0 mm (proximal 84.0 mm > distal 66.1 mm).
- Planform from `project_250` scaled to the diameter, chord ×1.0, twist ×1.0: r 33.0: c 37.0, β 31.0°; r 66.0: c 34.3, β 24.0°; r 99.1: c 30.4, β 17.0°; r 132.1: c 22.5, β 10.0°; r 161.8: c 10.6, β 5.0°
- Axial offset δ = 12.5 mm (plane A z = 0 proximal quarter-chord plane → plane B distal); deployed step at the joint 12.5 mm, face gap 0.3 mm, stop nose 2.0 mm ahead of the leading edge.
- Lug stack 18.30 mm (proximal 8.92, gap 0.3, distal 9.08; full-depth lugs: each spans its blade section over the boss); lug mid-planes 9.30 mm apart; pin Ø3.0, hole Ø3.20.

## Full-travel clearance (actual solids)

- Required travel 140° (owner decision; template declares 180°); clear to 140°. Folded stop (stop nose meets the proximal): 144°. Smallest vertical body clearance 1.81 mm at -105° (negative = interference depth).
- With worst-case joint play (tilt 2.55°, limited by delik boşluğu; tip droop 3.24 mm): 0.54 mm at -105°.
- Offset that clears the full travel: ≈ 12.5 mm nominal, ≈ 12.5 mm with play (estimated from the deficit; confirm by re-running at that offset).
- Method: sütun yöntemi 0.25 mm ızgara, 1.0° adım; tesselasyon 0,05 mm. Exact OpenCASCADE distance proximal–distal: 0° → 0.000 mm, -2° → 0.213 mm, -105° → 0.300 mm (0 at the open stop is the designed seat; the column gap is a vertical clearance ≥ the exact distance).
- Open-stop seat: zero nominal clearance between separately printed faces; the as-printed open angle varies by about ±0.1 mm / lever (≈ ±0.7° at 8 mm). Measure it on the fit test.

## Mass properties (estimate until weighed)

- proximal: 21.50 g, CG (2.83, 30.83, -1.06) mm — PLA ρ=1.24 g/cm³, doluluk 100%, duvar 1.2 mm
- distal: 4.60 g, CG (3.14, 117.29, 11.23) mm — PLA ρ=1.24 g/cm³, doluluk 100%, duvar 1.2 mm
- pin_set: 1.56 g, CG (0.00, 99.00, 6.49) mm — pim seti (çelik)
- blade: 27.66 g, CG (2.72, 49.05, 1.41) mm — kanat (proksimal + distal + pim seti)
- Distal inertia about its CG [g·mm²]: [[1476.6,  -72.4,   10.5],  [ -72.4,  222.1,  -65.7],  [  10.5,  -65.7, 1635.6]]
- Distal CG 3.14 mm aft of the pin; centrifugal moment about the pin seats the segment on the open stop.

## Deployed loads and single-lug checks (what-if speeds; no owner maximum speed)

| RPM | case | seated | centrifugal [N] | stop [N] | pin [N] | couple [N·mm] | governing check | limit RPM (SF 2.0) | min margin |
|---|---|---|---|---|---|---|---|---|---|
| 3000 | what-if, centrifugal only | yes | 53 | 18 | 72 | 187 | Stop burnu kök eğilmesi | 2543 | -0.28 |
| 4000 | what-if, centrifugal only | yes | 95 | 33 | 127 | 332 | Stop burnu kök eğilmesi | 2543 | -0.60 |
| 5000 | what-if, centrifugal only | yes | 148 | 51 | 199 | 519 | Stop burnu kök eğilmesi | 2543 | -0.74 |
| 6000 | what-if, centrifugal only | yes | 213 | 73 | 286 | 747 | Stop burnu kök eğilmesi | 2543 | -0.82 |
| 7000 | what-if, centrifugal only | yes | 290 | 100 | 390 | 1017 | Stop burnu kök eğilmesi | 2543 | -0.87 |
| 8000 | what-if, centrifugal only | yes | 378 | 131 | 509 | 1328 | Stop burnu kök eğilmesi | 2543 | -0.90 |

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
- OK Lug kalınlığı (katman): 45 (≥ 10 katman)
- OK Lug–kanat bağlantısı (proksimal): 100% kesit kalınlığı (lug bandı, pim çevresinde kendi kanat kesitinin ≥ %60'ını kavramalı)
- OK Lug–kanat bağlantısı (distal): 100% kesit kalınlığı (lug bandı, pim çevresinde kendi kanat kesitinin ≥ %60'ını kavramalı)
- OK Firar kenarı kalınlığı (uç): 0.80 mm (≥ 0.8 mm (kesit NACA2412-te0.80mm-x0.50))
- OK Lug aralığı (katman): 1.5 (ayrı parçalar; aralık montajda donanımla kurulur)
- OK Burulmuş yüzeyler: azami 31° (rotor düzlemi tablada: alt yüzey destek ister (destek arayüzü alt yüzeyde))
- OK Tabla sığması: rotor_hub_proximal: 46.6×207.3×24.3 mm (tabla 256×256×256, döndürme 7.5°)
- OK Tabla sığması: distal: 71.1×32.2×18.3 mm (tabla 256×256×256, döndürme 80.0°)
- OK Tabla sığması: fit_proximal: 32.4×27.5×15.6 mm (tabla 256×256×256, döndürme 0.0°)
- OK Tabla sığması: fit_distal: 32.2×27.5×18.3 mm (tabla 256×256×256, döndürme 0.0°)
- OK Tabla sığması: hole_coupon: 54.0×16.0×8.9 mm (tabla 256×256×256, döndürme 0.0°)
