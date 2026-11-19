# 13in-F1S ölçüm baskısı — operatör rehberi

Bu paket **geometri ve talimat paketidir**: Bambu Studio'da açılıp dilimlenmedi. Dilimlemeyi kendi P1S yapılandırmanızla
siz yapacaksınız; aşağıdaki ayarlar **önerilen** ayarlardır, **kullanılan** ayarları `BASKI_VE_OLCUM_KAYDI.md` formuna yazın.

## İlk basılacak plaka: `3mf/01_kupon.3mf`

Kupon: 5.16 mm kalınlıkta plaka, delikler Ø4.0, Ø4.1, Ø4.2, Ø4.3, Ø4.4 mm (deliğin yanında k adet çentik = k. delik). **İlk baskıda
yalnız bu kuponu basın.** `3mf/sonra_secilecek_ciftler/` klasöründeki çiftleri şimdi basmayın: kupon gerçek pimle denendikten sonra
bunlardan **yalnız biri** seçilip basılır.

## Birim, ölçek, yön

- Birim **mm**, ölçek **%100**. Dosyalar baskı yönünde ve tabla düzlemine (z = 0) oturtulmuş olarak gelir; döndürmeyin,
  otomatik yönlendirme (auto-orient) kullanmayın. Yalnız tabla üzerinde yerini değiştirebilirsiniz.
- Pim ekseni yazıcının **Z** ekseninde. Proksimal parça lug'ının pul yüzü tablada, düz; distal parça **ters çevrilmiş**
  (pul yüzü tablada), böylece iki lug arasındaki çalışma yüzü desteksiz üst yüzey olur.
- Beklenen boyutlar (X × Y × Z, mm) — dilimleyicide aynı değilse ölçek veya birim yanlış içe aktarılmıştır:

| Nesne | Boyut |
|---|---|
| `F1S_kupon_D4+0.0-0.4` | 54.0 × 16.0 × 5.2 |
| `F1S_cift_c0.00_proksimal` | 32.6 × 47.5 × 8.0 |
| `F1S_cift_c0.00_distal` | 29.6 × 41.5 × 10.8 |
| `F1S_cift_c0.10_proksimal` | 32.6 × 47.5 × 8.0 |
| `F1S_cift_c0.10_distal` | 29.6 × 41.5 × 10.8 |
| `F1S_cift_c0.20_proksimal` | 32.6 × 47.5 × 8.0 |
| `F1S_cift_c0.20_distal` | 29.6 × 41.5 × 10.8 |
| `F1S_cift_c0.30_proksimal` | 32.6 × 47.5 × 8.0 |
| `F1S_cift_c0.30_distal` | 29.6 × 41.5 × 10.8 |
| `F1S_cift_c0.40_proksimal` | 32.6 × 47.5 × 8.0 |
| `F1S_cift_c0.40_distal` | 29.6 × 41.5 × 10.8 |

## Önerilen ayarlar (P1S, 0,4 mm nozul varsayımı)

| Ayar | Önerilen | Not |
|---|---|---|
| Nozul | 0,4 mm | gerçek nozulu doğrulayın |
| Tabla | Textured PEI (P1S standart) | gerçek tablayı doğrulayın |
| Filament | Eco Smart Standard PLA | üretici ve etiketi doğrulayın; listede yoksa Generic PLA profili |
| Katman | 0.2 mm (ilk katman 0.2 mm) | |
| Duvar | 3 döngü (≈ 1.2 mm) | dilim önizlemesinde delik çevresindeki duvar genişliğini kontrol edin |

**Dilimleme önizlemesi (basmadan önce):** boyutların yukarıdaki tabloyla aynı olduğunu, deliklerin çevresinde
tam duvar olduğunu ve deliklere, lug yüzlerine ve stop temas yüzlerine destek gelmediğini kontrol edin; önizlemenin
ekran görüntüsünü alın ve `BASKI_VE_OLCUM_KAYDI.md` formuna yazın.
| Doluluk | %100 | |
| X-Y delik telafisi | 0 | kupon ham süreci ölçer; telafi kullanırsanız aynı değeri çiftte de kullanın ve yazın |
| X-Y kontur telafisi | 0 | |
| Fil ayağı telafisi | varsayılan | değeri yazın |
| Destek | kupon: yok. Çift: ağaç destek, yalnız tabladan | ters basılan distalde stop burnunun altına tabladan destek gelmesi beklenir; deliklere, lug yüzlerine ve stop burnu/pedinin temas yüzlerine destek gelmemeli |
| Brim | kupon: yok. Çift: 3 mm dış brim | brim kalıntısını lug çevresinden dikkatle alın |
| Ütüleme | kapalı | |
| Dikiş | arka veya hizalı | delik içinde dikiş izi varsa temizlemeyin, kayda yazın |

Delikleri matkap/raybayla açmayın, zımparalamayın: ölçüm, basıldığı haliyle yapılır.

## Kupondan çift seçimi (tek kural)

Kuponu **proje sahibine** teslim edin: pimle deneme ve çift seçimi onun kararıdır; hangi çiftin basılacağı size bildirilir.

Proje sahibi gerçek pimi her deliğe elle iter ve not eder: `girmez` / `sıkı` (zorla döner) / `akıcı` (serbest döner,
gözle görülür boşluk yok) / `boşluklu`. **En küçük `akıcı` adım** s ise `3mf/sonra_secilecek_ciftler/02_cift_c` + s dosyası
basılır. Hazır çiftler: `02_cift_c0p00`, `02_cift_c0p10`, `02_cift_c0p20`, `02_cift_c0p30`, `02_cift_c0p40`. Hiç `akıcı` yoksa komşu bir çift seçilmez; proje sahibi tam boşluklu çift dosyasını
ayrıca gönderir.

Kit kimliği `052b3fe9578c` — ölçüm kaydı bu kimliği taşır.
