# 13in-F1S ölçüm baskısı — önce beni okuyun

Bu klasör bir **geometri ve talimat paketidir**; Bambu Studio'da açılıp dilimlenmedi. Dilimlemeyi kendi P1S
yapılandırmanızla siz yapacaksınız.

## Şimdi basılacak tek parça: `3mf/01_kupon.3mf`

İlk aşamada **yalnız** delik kuponunu basın (STL karşılığı: `stl/01_kupon.stl`). Kupon gerçek pimle denenip sonucu
belli olmadan başka hiçbir parça basılmaz. Kuponu **proje sahibine** teslim edin: pimle deneme ve çift seçimi onun kararıdır; hangi çiftin basılacağı size bildirilir.

## Sonra, kupon sonucuna göre: `3mf/sonra_secilecek_ciftler/`

Bu klasördeki uyum çiftleri (`02_cift_c0p00`, `02_cift_c0p10`, `02_cift_c0p20`, `02_cift_c0p30`, `02_cift_c0p40`) **şimdi basılmaz**. Proje sahibi kuponu gerçek pimle dener ve **yalnız bir
çift** seçer: pimin serbest döndüğü (`akıcı`) en küçük adıma ait olan (`BASKI_REHBERI.md` → “Kupondan çift
seçimi”). Hiçbir delik `akıcı` değilse komşu çift basılmaz; proje sahibi tam boşluklu yeni çift dosyasını ayrıca
gönderir.

## Pimin uygunluğu doğrulanmadı (karar açık)

Önerilen A4/316 Ø4×14 mm pimin bu montaja uygunluğu **doğrulanmadı; karar açıktır**: kafası, tutma özelliği (segman kanalı veya kopilya
deliği) ve kullanılabilir tutma boyu, pimin teknik çizimi veya ölçümüyle doğrulanmadan karar verilmez
(`MONTAJ_VE_DONANIM.md`). Kupon denemesi için pimin gerçek çapı yeterlidir.

## Dosyalar

| Dosya | İçerik |
|---|---|
| `BASKI_REHBERI.md` | birim, ölçek, yön, beklenen boyutlar, **önerilen** baskı ayarları, kupondan çift seçimi |
| `BASKI_VE_OLCUM_KAYDI.md` | önerilen ve **gerçekten kullanılan** ayarlar formu, değişiklikler |
| `OLCUM_PROTOKOLU.md` | kupon ve uyum çifti ölçüm protokolü, kayıt alanları |
| `MONTAJ_VE_DONANIM.md` | pim/pul/segman gereksinimleri, montaj sırası, kontrol listesi |
| `olcum_kaydi.json` | ölçüm kaydı (proje sahibi PyFoldable'a yükler; yazıcı, malzeme ve filament proje sahibinin bildirdiği değerlerle önceden dolduruldu, etiketle farklıysa düzeltin) |
| `3mf/`, `stl/` | baskı yönünde geometri (mm, %100 ölçek) |
| `predictions.json`, `design.json`, `SHA256SUMS` | model tahminleri, tasarım kaydı, dosya özetleri |

Kit kimliği `052b3fe9578c`. Fiziksel yeterlilik: yok — bu bir ölçüm denemesidir.
