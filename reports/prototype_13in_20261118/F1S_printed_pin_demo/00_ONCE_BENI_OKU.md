# 13in-F1S basılı pim gösterici — önce beni okuyun

Bu paket, metal pim alınmadan önce elle montaj ve katlanma denemesi için **tamamen basılabilir, geçici bir mafsal
göstericisidir**. Bambu Studio'da açılıp dilimlenmedi; geometri ve talimat paketidir. Dilimlemeyi operatör kendi
P1S yapılandırmasıyla yapar. Metal pimli ölçüm paketi ayrı bir pakettir: bu gösterici onun yerine geçmez ve onun
ölçümlerini üretmez.

## İlk baskı: yalnız bu iki dosya

1. `3mf/01A_kucuk_parcalar.3mf`: delik kuponu, üç pim (Ø3,80 / Ø3,90 / Ø4,00 mm; kafa kenarında 1 / 2 / 3 çentik)
   ve üç klips. **Destek yok, brim yok.**
2. `3mf/01B_mafsal_cifti.3mf`: kısa F1S mafsal çifti (proksimal dik, distal ters çevrilmiş). **Ağaç destek yalnız
   tabladan, 3 mm brim.**

İki dosya aynı işte, ayrı plakalarda basılabilir. Başka hiçbir dosya basılmaz. Tam boy kanat baskısı bu kompakt
denemenin parçası değildir; ayrı ve sonraki bir iştir.

## Sonra

Parçalar proje sahibine teslim edilir. Pim seçimi ve montaj `MONTAJ.md`, elle deneme `DENEME_PROTOKOLU.md` ile yapılır.
Gözlemler `deneme_kaydi.json` ve `BASKI_VE_DENEME_KAYDI.md` formuna yazılır.

## Seçilen düzen (kısaca)

Başlı PLA pim, **dik ve kafası tablada** basılır: taşıma yüzeyi yuvarlak çıkar, katman halkaları dönme yönündedir.
Distal lug'ın üstünde, taşıma bölgesinin dışında kalan bir kanala **düz basılan bir PLA klips** yandan takılır. Klips
PLA için boyutlandırıldı (1,6 mm kalınlık, 1,3 mm kol); metal segmanın
küçültülmüş kopyası değildir. Pul yoktur. Mafsal deliği metal tasarımdaki çaptadır (Ø4,20 mm):
pim deliğe göre seçilir, delik pime göre değiştirilmez.

## Bu deneme neyi göstermez

- Bu bir **basılı PLA pim gözlemidir**: metal pimli montajın boşluğu, sürtünmesi, dayanımı, temas yükleri ve izin verilen devri için kanıt değildir.
- Görülen temas **geometrik bir gözlemdir**; nicel açıklık kabulü değildir. Basılı pimin eğilmesi ve yüzey pürüzlülüğü hissedilen boşluğu etkiler.
- Göstericinin onaylı bir motorlu çalışma zarfı **yoktur**; metal pim veya PLA için hesaplanan devir sınırları buna aktarılmaz. Motorla döndürmeyin.
- Metal pime, başka bir tutma yöntemine veya ASA'ya geçiş ilgili ölçümlerin yeniden yapılmasını gerektirir.
- Fiziksel yeterlilik: yok.

## Dosyalar

| Dosya | İçerik |
|---|---|
| `BASKI_REHBERI.md` | birim, ölçek, yön, beklenen boyutlar, önerilen ayarlar, dilimleme önizlemesi kontrolleri |
| `BASKI_VE_DENEME_KAYDI.md` | önerilen ve **gerçekten kullanılan** ayarlar, doğrulamalar, deneme gözlem formu |
| `MONTAJ.md` | parça listesi, pim seçimi, montaj ve söküm, klips takma/çıkarma |
| `DENEME_PROTOKOLU.md` | elle deneme adımları, çevrimler, fotoğraflar, bu denemeden ne öğrenilir |
| `deneme_kaydi.json` | deneme kaydı (yazıcı, malzeme, filament önceden dolduruldu; etiketle farklıysa düzeltin) |
| `gorseller/` | patlatılmış montaj, pim ekseninden kesit, açık / en dar / katlı konumlar; iki plakanın ve montajın CAD önizlemesi (`onizleme_*.png`, dilimleyici önizlemesi değil) |
| `3mf/`, `stl/` | baskı yönünde geometri (mm, %100 ölçek); `step/`: montaj konumunda CAD (açık) |
| `predictions.json`, `design.json`, `SHA256SUMS` | model değerleri, tasarım kaydı, dosya özetleri |

Paket kimliği `9b023c27de8a` (tasarım 052b3fe9578c).
