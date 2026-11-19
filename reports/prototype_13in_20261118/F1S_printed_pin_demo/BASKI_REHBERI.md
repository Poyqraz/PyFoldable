# 13in-F1S basılı pim gösterici — baskı rehberi

Bu paket **dilimlenmedi**. Aşağıdaki ayarlar **önerilen** ayarlardır. Gerçekten kullanılan ayarları
`BASKI_VE_DENEME_KAYDI.md` formuna yazın.

## Birim, ölçek, yön

- Birim **mm**, ölçek **%100**. Nesneler baskı yönünde ve tablaya (z = 0) oturtulmuş gelir. Döndürmeyin, otomatik
  yönlendirme kullanmayın; yalnız tabla üzerinde yer değiştirebilirsiniz.
- **Pimler dik, kafası tablada.** Yatırmayın: yatık basılan pim yuvarlak çıkmaz ve dönmesi pürüzlü olur.
- **Klipsler düz** (1,6 mm, 8 katman), kupon düz.
- Proksimal lug'ının pul yüzü tablada; distal **ters çevrilmiş** (pul yüzü tablada).

## Plaka 01A: `3mf/01A_kucuk_parcalar.3mf` (destek yok, brim yok)

| Nesne | Boyut X × Y × Z [mm] |
|---|---|
| `F1S_kupon_D4+0.0-0.4` | 54,0 × 16,0 × 5,2 |
| `F1S_pim_D3.80_1centik` | 8,0 × 8,0 × 15,6 |
| `F1S_pim_D3.90_2centik` | 8,0 × 8,0 × 15,6 |
| `F1S_pim_D4.00_3centik` | 8,0 × 8,0 × 15,6 |
| `F1S_klips_1` | 8,3 × 5,7 × 1,6 |
| `F1S_klips_2` | 8,3 × 5,7 × 1,6 |
| `F1S_klips_3` | 8,3 × 5,7 × 1,6 |

## Plaka 01B: `3mf/01B_mafsal_cifti.3mf` (ağaç destek yalnız tabladan, 3 mm brim)

| Nesne | Boyut X × Y × Z [mm] |
|---|---|
| `F1S_gosterici_proksimal` | 28,0 × 27,5 × 5,2 |
| `F1S_gosterici_distal` | 29,6 × 27,5 × 10,8 |

Dilimleyicideki boyutlar bu tablolardan farklıysa ölçek veya birim yanlış içe aktarılmıştır.

## Önerilen ayarlar (P1S, 0,4 mm nozul)

| Ayar | Önerilen | Not |
|---|---|---|
| Nozul | 0,4 mm | takılı nozulu doğrulayın (0,2–0,8 mm mevcut) |
| Tabla | PEI (düz veya dokulu: doğrulayın) | hangisi kullanıldıysa yazın |
| Filament | Eco Smart Standard PLA | etiketi doğrulayın; profil adını yazın |
| Katman | 0,20 mm | |
| Duvar | 3 döngü | Ø4 pimde neredeyse tamamı duvardır |
| Doluluk | %100 | |
| X-Y delik / kontur telafisi | 0 / 0 | telafi kullanırsanız değeri yazın |
| Destek | 01A: kapalı. 01B: ağaç, yalnız tabladan | 01B'de ters distalin stop burnunun altına destek beklenir; deliklere, lug yüzlerine ve stop temas yüzlerine destek gelmemeli |
| Brim | 01A: yok. 01B: 3 mm dış brim | |
| Katman soğutması için yavaşlama | açık (varsayılan) | küçük pim katmanlarının soğuması için; üç pim aynı plakada |
| Ütüleme | kapalı | |

## Dilimleme önizlemesinde kontrol (basmadan önce)

1. Boyutlar tablolarla aynı.
2. Pimler dik; pim kanalının üst kenarı (0,4–0,5 mm çıkıntı) **desteksiz** basılıyor; pimlerde destek yok.
3. Klips ağzı açık (köprülenmemiş, dolmamış); klips 8 katman.
4. Kupon ve mafsal deliklerinin çevresinde tam duvar var.
5. 01B'de destek yalnız ters distalin stop burnunun altında; deliklerde ve lug yüzlerinde destek yok.

Önizlemenin ekran görüntüsünü alın ve formda belirtin. Delikleri delmeyin, raybalamayın, zımparalamayın; pimleri
zımparalamayın: parçalar basıldığı gibi denenir.
