# 13in-F1S ölçüm protokolü (delik kuponu + uyum çifti)

Pim geçmesi, mafsal boşluğu, sürtünme ve stop oturması için bir ölçüm prototipidir. Bu adayı motorlu pervane olarak
seçmez ve fiziksel olarak hiçbir şeyi nitelendirmez. Tüm ölçüler mm. Kit kimliği `052b3fe9578cbd22a5dba6e70e1354dd087e43dd9c3b8560d4f4ac31cf5f114a`;
ölçüm kaydı aynı kimliği taşımalıdır.

## Parçalar ve donanım

- `01_kupon`: proksimal lug kalınlığında (5.16 mm) delikli plaka.
- `02_cift_cX`: CAD çap boşluğu X mm olan mafsal. Proksimal parçanın iç ucunda düz bir **mengene bloğu**, distal
  parçanın dış ucunda düz bir **yük dili** vardır; dildeki Ø3,2 **yük deliği**, pimden geçen açıklık çizgisi
  üzerinde pim ekseninden 30.0 mm uzaktadır.
- Tüm parçalarda pim ekseni yazıcının Z ekseninde; proksimal lug'ının pul yüzü tablada, distal **ters çevrilmiş**
  (pul yüzü tablada) basılır (`BASKI_REHBERI.md`).
- Çift başına donanım: bir pim (ISO 2341-A Ø4 (kafa Ø6×1) + DIN 6799 kanalı (Ø3,2 × 0,64); kafa altı boy 13.3 mm), iki DIN 433 pul
  (Ø4.3 × Ø8 × 0.5 mm), bir DIN 6799
  segman. Pimin gerçek çapını ölçün; pim uygunluğu `MONTAJ_VE_DONANIM.md` kontrolleri bitmeden kabul edilmez.

## Gerekenler

Gerçek pim (çapı ölçülmüş), 2 pul, segman (ve gerekirse şim); kumpas; komparatör veya sentil takımı (0,05 mm dahil);
mengene; ≈ 2 N yük (≈ 200 g ağırlık) veya el dinamometresi; yaylı el kantarı; açıölçer; 0,01 g hassasiyetli terazi.

## Ölçümler ve sıra

1. **Kupon.** Kupon 5.16 mm kalınlıkta, delikleri Ø4.0, Ø4.1, Ø4.2, Ø4.3, Ø4.4 mm (k. deliğin yanında k çentik). Gerçek pimi her
   deliğe elle itin ve değerlendirin: `girmez`, `sıkı` (yalnız zorla döner), `akıcı` (serbest döner, gözle görülür
   boşluk yok), `boşluklu` (gözle görülür boşluk). İsterseniz her deliği pim mastarı veya matkap sapıyla ölçün.
2. **Uyum çifti: tek karar.** CAD boşluğu **en küçük `akıcı` adıma** eşit olan çifti basın; her kupon adımı için bir
   çift hazırdır (`3mf/sonra_secilecek_ciftler/`). Hiçbir delik `akıcı` değilse (hepsi `sıkı`/`girmez`) komşu çifti seçmeyin:
   proje sahibi daha büyük boşluklu tam çifti PyFoldable'da üretir (*Prototip → Bu tasarımın ölçüm kitini
   oluştur*, o delik boşluğuyla, veya `fit.export_kit(d, klasör, clearances=(c,))`) ve gönderir. 0,0 adımı bile boşluklu ise c0.00 çiftini basın ve not edin. Basılan çifti kayda yazın
   (`fit_pair_clearance_mm`).
3. **Boyutlar.** İki lug kalınlığını göbek bölgesinde kumpasla ölçün (model 5.16 / 5.38 mm). Pim çapını,
   tutma boyunu (kafa altından kanalın yakın kenarına) ve pul + şim yığınının toplam kalınlığını ölçün.
4. **Eksenel boşluk a.** Proksimal bloğu mengeneye sıkın, rotor düzlemi yatay. Distal lug'ı pim boyunca aşağı yukarı
   hareket ettirin; göbekteki serbest hareketi komparatör veya sentille ölçün. Model: 0.30 mm.
5. **Eğilme.** Yük deliğine bilinen bir yükü (≈ 2 N) önce yukarı, sonra aşağı uygulayın; deliğin toplam düşey
   hareketi Δ'yı ölçün. Eğilme φ = max(0, Δ − a) / (2 L), L = 30.0 mm. Model (en kötü durum):
   3.13°.
   **a ve Δ'yı en az üç kez tekrarlayın** (tekrarlar arasında sökün ve yeniden takın; iki çift basıldıysa ikisini de
   ölçün). Tekrar sayısını, ortalamaları ve her birinin aralığını (en büyük − en küçük) aletin çözünürlüğüyle birlikte
   yazın. Karar, en kötü durum aralığından k = 2 kat birleşik belirsizliği (çözünürlük, tekrar aralığı, lug
   kalınlıklarından baskı değişkenliği) düşer.
6. **Sürtünme.** Rotor düzlemi yatay, distal açık stopunda. Yük deliğinden yaylı kantarla, yatay ve kola dik olarak,
   katlanma yönüne (firar kenarına doğru) çekin; katlanmanın başladığı kuvveti yazın. Moment T = F L.
7. **Stop oturması.** Distal'i elle açık tutun; burun–ped temasını 0,05 mm sentille ve ışığa karşı kontrol edin.
   Aralığı ve yüzlerin düz oturup oturmadığını yazın.
8. **Katlanmış stop.** Burun durana kadar katlayın; katlanma hareketini (açıyı) açıölçerle ölçün (model 144°).
9. **Kütleler.** İki parçayı donanımsız tartın (model 7.76 / 2.56 g, PLA,
   duvar 1.2 mm, doluluk %100).

## Baskı bilgisi

Ölçümler, onları üreten baskıya bağlıdır. Gerçek yazıcı, nozul, tabla, filament (üretici, ürün, renk/parti),
dilimleyici ve sürümü, katman, duvar, doluluk ve önerilen ayarlardan **her farkı** `BASKI_VE_OLCUM_KAYDI.md` ile
`olcum_kaydi.json` dosyasına yazın. Ölçüm, yalnız aynı yazıcı, nozul, malzeme, filament, katman, duvar ve doluluk ile ve
ayar değişikliği olmadan basılmışsa bu tasarıma **doğrudan** kanıt sayılır; aksi halde **aktarılmış** sayılır ve
boşluk kararı en kötü durum modelinde kalır. ASA veya değişmiş bir süreç ayrı bir deneydir.

## Kayıt

`olcum_kaydi.json` dosyasını (kitteki kayıt şablonu) doldurun; proje sahibi onu *Prototip → Ölçüm prototipi*
sayfasına yükler. Bilinmeyen alanlar, eksik veya aralık dışı değerler ve başka bir kite ait kayıt reddedilir. Doğrudan
kanıt sayılan ölçülmüş boşluk, tam hareket açıklık kontrolünde en kötü durum model boşluğunun yerine geçer ve
ölçülen boşluk tasarımın delik boşluğu olur. Bilinmeyen değerleri tahminle doldurmayın; boş
(`null`) bırakın.

| Alan | Zorunlu | Anlam |
|---|---|---|
| `schema` | evet | kayıt şeması |
| `kit_design_sha256` | evet | ölçüm kitinin tasarım kimliği (predictions.json) |
| `print_printer` | evet | yazıcı modeli |
| `print_material_family` | evet | malzeme ailesi: PLA / ASA / ABS / PETG / other |
| `print_filament_product` | evet | filament ürünü (ör. Eco Smart Standard PLA) |
| `print_filament_manufacturer` | hayır | filament üreticisi (doğrulanmadıysa null) |
| `print_filament_lot` | hayır | renk / parti numarası |
| `print_plate` | hayır | baskı tablası (ör. Textured PEI) |
| `print_slicer` | evet | dilimleyici ve sürümü |
| `print_project_sha256` | hayır | basılan Bambu Studio projesinin SHA-256 özeti |
| `print_nozzle_mm` | evet | nozul çapı [mm] |
| `print_layer_mm` | evet | katman yüksekliği [mm] |
| `print_walls` | evet | çevre duvarı sayısı |
| `print_infill_fraction` | evet | doluluk oranı (0–1) |
| `pin_measured_diameter_mm` | evet | pimin ölçülen çapı [mm] |
| `coupon_fit` | evet | kupon deliği başına geçme: girmez / sıkı / akıcı / boşluklu |
| `coupon_hole_mm` | hayır | kupon deliği başına ölçülen çap [mm] (pim mastarı; bilinmiyorsa null) |
| `fit_pair_clearance_mm` | evet | basılan uyum çiftinin CAD delik boşluğu [mm] |
| `lug_thickness_proximal_mm` | evet | proksimal lug ölçülen kalınlığı [mm] |
| `lug_thickness_distal_mm` | evet | distal lug ölçülen kalınlığı [mm] |
| `axial_float_mm` | evet | distal lugun pim boyunca serbest hareketi a [mm] |
| `tilt_load_n` | evet | eğilme ölçümündeki ± yük [N] |
| `tilt_range_at_tab_mm` | evet | yük deliğinde toplam düşey serbest hareket Δ [mm] |
| `friction_breakaway_n` | evet | katlanmayı başlatan kuvvet, delikte kola dik [N] |
| `stop_gap_mm` | evet | distal elle açık tutulurken burun–ped aralığı [mm] (sentil) |
| `stop_seats` | evet | burun pede tam yüzeyle oturuyor mu (ışık testi) |
| `folded_stop_deg` | hayır | katlanmış stop açısı [°] (açıölçer) |
| `pin_grip_length_mm` | evet | pimin kafa altından kanalın yakın kenarına ölçülen boyu [mm] |
| `washer_stack_mm` | evet | yığındaki pul + şim toplam ölçülen kalınlığı [mm] |
| `hardware_source` | hayır | pim/pul/segman tedarikçisi ve parça numaraları |
| `print_changes` | hayır | önerilen ayarlardan farklar (destek, brim, telafiler, hız, profil) |
| `measurement_resolution_mm` | evet | boşluk ölçümünde kullanılan aletin çözünürlüğü [mm] |
| `repeat_count` | evet | eksenel boşluk ve Δ ölçümlerinin tekrar sayısı (birden çok uyum çiftinde toplam) |
| `axial_float_spread_mm` | hayır | tekrarlar arasında eksenel boşluğun aralığı (en büyük − en küçük) [mm] |
| `tilt_range_spread_mm` | hayır | tekrarlar arasında Δ'nın aralığı [mm] |
| `mass_fit_proximal_g` | hayır | uyum çifti proksimal kütlesi [g] |
| `mass_fit_distal_g` | hayır | uyum çifti distal kütlesi [g] |
| `notes` | hayır | serbest not |

Sınırlar: yalnız yüksüz sürtünme (merkezkaç yükü altındaki pim sürtünmesi ölçülmez); statik boşluk, yorulma veya
sünme değil; tek baskı, tek pim. Fiziksel yeterlilik: yok.
