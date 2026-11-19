# 13in-F1S uyum çifti — montaj ve donanım

## Donanım kararı açık

Önerilen A4/316 Ø4×14 mm pim: uygunluğu **doğrulanmadı; karar açıktır**. Pimin teknik çizimi veya ölçümüyle aşağıdakiler
doğrulanmadan montaj yapılmaz.

| Ölçü | Gereken | Neden |
|---|---|---|
| Pim çapı | Ø4 mm (ölçülen değeri yazın) | kupon ve çift bu çapa göre |
| Kafa çapı | > pul iç çapı 4.3 mm, ≤ 8.6 mm | pulu tutmalı; tam pervanede havşa içine girmeli |
| Tutma özelliği | DIN 6799 boyut 3,2 kanalı (kanal Ø3,2, genişlik ≈ 0,64) **veya** pim deliği (kopilya) | tasarım segman + pul varsayar; kopilya delikli pimde boy kuralı deliğin kenarına göre uygulanır |
| Tutma boyu (kafa altı → kanalın yakın kenarı) | ≥ 11.84 mm (= pul 0.5 + lug 5.16 + aralık 0.3 + lug 5.38 + pul 0.5) | kısa pim monte edilemez; lugları zımparalamayın |
| Fazla boy | tutma boyu − (ölçülen lug + pul) = 0,1–0,4 mm hedef | fazlası şim (DIN 988 4×8, 0,1/0,2/0,3) veya ek DIN 433 pul ile kapatılır; şimler yığına yazılır |
| Pul | 2 × DIN 433 4,3 × 8 × 0,5 | kalınlıkları ölçün |
| Segman | DIN 6799 3,2 (OD ≈ 7,3) | kanala tam oturmalı; pim ucu segmandan ≥ 0.8 mm taşmalı |

Ø4×14 için varsayımsal örnek (pim hakkında bir bulgu değildir): kafa altı boy 14 mm ise kanal/delik konumu tedarikçi çiziminden okunmalı; tutma boyu ≈ 12,5 mm çıkarsa nominal yığında eksenel boşluk ≈ 0,96 mm olur ve ≈ 0,71 mm şim gerekir (hedef 0,25 mm).

## Montaj sırası (alttan üste)

1. Destek ve brim kalıntılarını temizleyin; delik, lug yüzleri, stop burnu ve pedine dokunmayın (zımpara yok).
2. Pim kafası → pul → proksimal lug → distal lug → pul (+ şim) → segman. Distal, proksimalin üstünde (itki tarafı).
3. Distal elle açık stopa (burun pede) dayanmalı; katlanmada ~144°'de burun tekrar temas eder.
4. Zorlayarak montaj yapmayın: pim deliğe girmiyorsa kupon kararını tekrar kontrol edin.

## Kontrol listesi

- [ ] Kupon basıldı, her delik değerlendirildi, en küçük `akıcı` adım seçildi
- [ ] Seçilen boşluktaki çift basıldı (dosya adı kayda yazıldı)
- [ ] Pim çapı, kafa, tutma boyu, kanal, pul ve segman ölçüldü ve kayda yazıldı
- [ ] Lug kalınlıkları ölçüldü (model 5.16 / 5.38 mm)
- [ ] Şim kullanıldıysa toplam kalınlık `washer_stack_mm` içine yazıldı
- [ ] Ölçüm protokolü (`OLCUM_PROTOKOLU.md`) uygulandı; eksenel boşluk ve Δ en az 3 kez
