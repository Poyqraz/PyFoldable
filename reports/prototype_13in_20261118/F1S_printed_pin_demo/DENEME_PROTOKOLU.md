# 13in-F1S basılı pim gösterici — elle deneme protokolü

Açı işareti: açık konum θ = 0°. Distal dönüş yönünün tersine geri katlanır; bu yön **negatif θ** ile gösterilir (θ = −103° = 103° katlanma). Kayıtta katlanma açısını pozitif yazın (ör. 140).

Motorsuz, elle montaj ve katlanma denemesi. Kuvvet ölçümü bu denemenin parçası **değildir**. Metal kitin yük, eğilme
ve sürtünme protokolü burada kullanılmaz. Ölçülmeyen alanları boş (`null`) bırakın; tahminle doldurmayın.

## Gerekenler

Kumpas (0,01–0,02 mm), sentil takımı (isteğe bağlı), açıölçer, telefon kamerası, kalem.

## Adımlar

1. **Ölçüler.** Üç pimin çapını iki dik yönde ölçün; isterseniz lug kalınlıklarını ve kanal–kafa altı boyunu da
   ölçün. Kullanılan pimi kaydedin (`pin_variant_mm`, `pin_diameter_a_mm`, `pin_diameter_b_mm`). Kafa altından
   kanalın kafaya **yakın** kenarına boyu kumpasın derinlik ucuyla ölçün (`pin_head_to_groove_near_mm`; CAD
   10,99 mm; uzak kenar CAD 12,79 mm).
2. **Geçme.** Kullanılan pimle kupon deliklerini (`coupon_fit`) ve mafsal deliklerini (`insertion_fit`) değerlendirin.
   Pimin elle çıkıp çıkmadığını yazın (`removal_by_hand`).
3. **Klips.** Takma (`clip_installs`) ve tırnakla çıkarma (`clip_removes`). Deneme boyunca yerinde kalıp kalmadığı
   (`clip_retains`).
4. **Serbest dönüş.** Distal açık stoptan katlı konuma kadar takılmadan dönüyor mu (`rotation_free`)? Takıldığı açıyı
   ve yeri yazın.
5. **Açık stop.** Burun pede oturuyor mu (ışık testi, `open_stop_seats`); sentil varsa aralık (`stop_gap_mm`).
   **Uçtan uca eksenel boşluk** (sentil varsa): distal'i proksimal lug'a bastırın, klipsi kanalın uzak kenarına itin
   ve distal üst yüzü ile klips arasındaki aralığı ölçün (`end_play_total_mm`). CAD: uçtan uca
   0,65 mm = nominal lug arası 0,30 mm + tek taraflı klips tarafı payı
   0,35 mm. Bu, metal kitin eksenel boşluk ölçümü değildir.
6. **Katlanma.** Elle ulaşılan katlanma açısı (`folded_stop_deg`). Model: yararlı hareket ≈ 143°,
   en dar ara konum θ ≈ -103° (nominal dikey açıklık 0,48 mm, pimden 19 mm uzakta). Distal tam sallandığında model bu konumda temas bekler: ihtiyatlı sınırla (yüz sınırı, 4,4–6,8°) tahmini açıklık -1,42 ile -0,85 mm; klipste dayanma varsayımıyla (4,4–4,5°) -0,87 ile -0,85 mm. Önce distal'i bastırmadan, kendi
   ağırlığıyla katlayın; sonra distal ucunu hafifçe proksimale doğru bastırarak tekrarlayın. Görülen temas veya
   sürtünmeyi, bastırarak mı bastırmadan mı olduğunu belirterek yeriyle yazın (`interference_observed`) ve
   fotoğraflayın. Bu geometrik bir gözlemdir.
7. **Çevrimler.** Açık → katlı → açık bir çevrimdir. Beyan edilen sayıda çevrim yapın (öneri: 10, sonra toplam 50,
   sonra toplam 200) ve her aşamada şunları kontrol edin:
   - aşınma, beyazlama ve toz (`wear_observed`);
   - boşluk değişimi (`play_change_observed`);
   - hasar (`damage_observed`).

   Son toplamı yazın (`cycle_count`).
8. **Fotoğraflar.** Montaj, açık, katlı, temas yerleri ve deneme sonrası pim ile klips; dosya adlarını `photos`
   alanına yazın.

## Bu denemeden ne öğrenilir

- Basılı parçaların bu baskı süreciyle elle takılıp sökülebildiği ve pim seçiminin delik ile pim hatasına göre
  nereye düştüğü.
- Mafsalın elle tam katlanma hareketi (model ≈ 143°), açık stop oturması ve görülen temas
  yerleri (geometrik gözlem).
- Klips tutmasının ve PLA yüzeylerinin beyan edilen çevrim sayısından sonra nasıl değiştiği.

## Bu denemeden ne öğrenilmez

- Bu bir **basılı PLA pim gözlemidir**: metal pimli montajın boşluğu, sürtünmesi, dayanımı, temas yükleri ve izin verilen devri için kanıt değildir.
- Görülen temas **geometrik bir gözlemdir**; nicel açıklık kabulü değildir. Basılı pimin eğilmesi ve yüzey pürüzlülüğü hissedilen boşluğu etkiler.
- Göstericinin onaylı bir motorlu çalışma zarfı **yoktur**; metal pim veya PLA için hesaplanan devir sınırları buna aktarılmaz. Motorla döndürmeyin.
- Metal pime, başka bir tutma yöntemine veya ASA'ya geçiş ilgili ölçümlerin yeniden yapılmasını gerektirir.
- Fiziksel yeterlilik: yok.
