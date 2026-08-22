# PyFoldable validation and development roadmap

Bu belge, PR-05E sonrasındaki teknik konumu ve katlanabilir pervane için
**deneyle doğrulanmış, tasarım kararı vermeye elverişli** bir analiz zincirine giden
yolu tanımlar. Yüzde cinsinden tek bir "tamamlanma" değeri verilmez: yazılım
altyapısının olgunluğu ile fiziksel tahmin doğruluğu aynı şey değildir.

## Güncel konum

PR-04 ve PR-05 serileri tamamlandı. XFOIL ve NeuralFoil gerçek regresyonları,
tekrarlanabilirlik kontrolü, polar ailesi üretimi ve iki boyutlu kesit tüketimi artık
korunan bir temel oluşturuyor. Proje, **altyapı ve 2B aerodinamik kanıt aşamasının
sonunda; rotor fiziği doğrulamasının başında** bulunuyor.

| Alan | Bugünkü durum | Hedefe göre açık |
| --- | --- | --- |
| Polar sağlayıcı altyapısı | Gerçek XFOIL/NeuralFoil regresyonlarıyla nitelikli | Yeni airfoil ve çalışma zarfı büyüdükçe yeniden niteleme |
| 2B kesit aerodinamiği | Reynolds/Mach enterpolasyonu ve izlenebilir kesit yükleri mevcut | 3B dönel akış ve stall düzeltmeleri |
| Rotor aerodinamiği | İndüksiyonsuz kesit integrasyonu mevcut | İndüksiyon, swirl, uç/kök kaybı ve rotor seviyesi doğrulama |
| Motor–pervane etkileşimi | Referans-yük son işlemesi | Tork–devir denge noktasını birlikte çözen kapalı çevrim |
| Katlanır mekanizma | Geometri/kinematik modeller ve karşılaştırma akışı mevcut | Açılma durumu–yük–performans geri beslemesi |
| CFD korelasyonu | Seviye-1 hazırlık/çıktı sözleşmeleri | Ağ bağımsızlığı ve BEM–CFD korelasyonu |
| Yapısal doğrulama | Malzeme ve menteşe veri modelleri | FEA, yorulma, kilit/menteşe yükleri ve balans |
| Deneysel doğrulama | Henüz birincil doğrulama verisi yok | Kalibre edilmiş itki standı, belirsizlik bütçesi, korelasyon |
| Optimizasyon | Parametrik tarama ve karar tabloları | Doğrulanmış modellerle robust çok amaçlı optimizasyon |

Bu nedenle mevcut sonuçlar mimari ve karşılaştırmalı geliştirme için değerlidir;
henüz nihai itki, verim, gerilme veya ömür garantisi olarak kullanılmamalıdır.

## Hedef ve başarı ölçütü

Nihai hedef; aynı sürüm altında aşağıdakileri yeniden üretebilen bir karar destek
zinciridir:

1. Gerçek polar girdilerinden rotor itki/tork/verim tahmini.
2. Motor çalışma noktası ve katlanır mekanizma durumuyla kapalı çevrim çözüm.
3. Kritik tasarımlar için BEM–CFD–deney korelasyonu ve açık belirsizlik bütçesi.
4. Menteşe, kilit ve pal için statik/yorgunluk güvenlik kanıtı.
5. Performans, kompaktlık, dayanım ve üretilebilirliği birlikte ele alan robust
   optimizasyon.

Bir aşama yalnız kodu birleştiğinde değil; tanımlı kabul eşiği, tekrar üretilebilir
kanıt paketi ve başarısızlığı görünür kılan regresyonu bulunduğunda tamamlanır.

## Sonraki aşamalar

### PR-06 — rotor aerodinamiği

- **PR-06A — yerel indüklenmiş-akış çekirdeği (tamamlandı ve review edildi).** Hover'da tekillik
  üretmeyen QPROP akış açısı parametrelemesiyle bir pal annulusunda eksenel indüksiyon,
  swirl, değiştirilmiş Prandtl uç kaybı ve diferansiyel itki/tork çözülür. Çözüm
  yakınsamazsa kapalı biçimde hata verir; tam rotor BEM iddiası taşımaz.
- **PR-06B — radyal rotor integrasyonu (tamamlandı).** Annulus orta noktaları,
  chord/twist enterpolasyonu, açık radial-domain politikası, seçilebilir kök/uç
  kayıpları, rotor toplamları ve boyutsuz performans katsayıları eklendi. Fiziksel
  doğruluk iddiası PR-06C benchmark kapısına bağlıdır.
- **PR-06C — sabit pervane benchmark'ı (karakterizasyon tamamlandı; doğruluk kapısı
  başarısız).** UIUC APC SF 10×4.7 rüzgâr-tüneli verisi üzerinde 60 ham/50 propulsif
  nokta, önceden ilan edilmiş CT/CP eşikleri, 20–160 annulus yakınsaması ve beş
  loss/polar varyantı yayımlandı. Sayısal yakınsama geçti; çözüm kapsamı %46 ve temsili
  polar kanıtı bulunmadığı için fiziksel yeterlilik geçmedi. PR-06D, PR-06C düzeltme
  artımına kadar blokludur.
- **PR-06D — katlanır geometri bağlantısı.** Açılma açısı, etkin yarıçap ve yerel
  kinematik rotor çözücüsüne taşınır; sabit–katlanır farkı fizik tabanlı hale gelir.

PR-06A'nın denklemsel temeli Mark Drela'nın
[QPROP formulation](https://web.mit.edu/drela/Public/web/qprop/qprop_theory.pdf)
notudur. Daha geniş çalışma rejimleri ve garantili kök bulma tasarımı için Andrew
Ning'in [BEM solution method](https://scholarsarchive.byu.edu/facpub/1673/) çalışması
PR-06B/06C'de referans alınacaktır.

PR-06A/06B denklem, sayısal davranış ve kapsam incelemesi
[PR-06 foundation review](pr06_foundation_review.md) belgesinde kayıtlıdır.
PR-04–PR-06 retrospektifi, benchmark kararı ve lisans sınırı
[retrospective review](pr04_pr06_retrospective_review.md) belgesindedir.

### PR-07 — tam bağlı motor–pervane çözümü

Motor tork eğrisi, gerilim/akım sınırları ve pervane torku ortak bir devir noktasında
çözülür. Kabul kapısı; enerji/tork kalıntısı, çoklu başlangıçtan aynı çözüm ve ölçülmüş
en az bir motor–pervane eşleşmesiyle korelasyondur.

### PR-08 — CFD korelasyonu

Önce doğrulama vakaları ve otomatik geometri/çalışma koşulu aktarımı, sonra ağ ve
zaman-adımı bağımsızlığı yapılır. ANSYS çalışması; sürüm, ağ metrikleri, sınır
koşulları ve yakınsama geçmişiyle kanıt paketi üretmelidir. CFD, deneyin yerine değil
BEM'in model-form hatasını ayırmak için kullanılır.

### PR-09 — yapısal ve mekanik doğrulama

SolidWorks ana geometrisi için revizyonlu CAD değişim sözleşmesi oluşturulur. ANSYS
ile pal, kök, pim, kilit ve stop temasları; maksimum devir/açılma geçişi ve dengesizlik
yüklerinde incelenir. Statik emniyet, deplasman, temas basıncı, yorulma ve doğal
frekans kapıları ayrı raporlanır.

### PR-10 — deneysel doğrulama

İtki/tork/devir/elektrik gücü veri şeması, sensör kalibrasyonu, sıfır kayması,
tekrarlı ölçüm ve belirsizlik yayılımı sürümlenir. En az bir sabit referans pervane ve
katlanır prototip aynı düzenekte ölçülür; BEM ve CFD farkları belirsizlik bantlarıyla
raporlanır.

### PR-11 — robust çok amaçlı optimizasyon

Yalnız doğrulanmış çalışma zarfında; itki/verim, katlanmış hacim, gerilme, ömür,
motor sınırları ve üretim toleransları birlikte optimize edilir. Pareto adayları CFD,
FEA ve deney kapılarından geçmeden önerilen tasarım olmaz.

### PR-12 — karar paketi ve sürümleme

Girdi kimlikleri, solver sürümleri, ham veri, belirsizlik, karşılaştırma ve tasarım
kararı tek bir tekrar üretilebilir raporda bağlanır. Temiz ortamda yeniden üretim ve
arşiv bütünlüğü sürüm kapısıdır.

## Yakın dönem yürütme sırası ve kapılar

| Sıra | Teslimat | Tamamlanma kapısı |
| --- | --- | --- |
| 1 | PR-06A yerel annulus çözücüsü | Tamamlandı: hover, denklem kalıntısı, loss-model ve açık kapsam regresyonları |
| 2 | PR-06B rotor integrasyonu | Tamamlandı: radyal yakınsama, yük/toplam tutarlılığı ve provenance |
| 3 | PR-06C referans benchmark | Karakterizasyon tamamlandı; kapsam/polar kapıları başarısız, düzeltme gerekli |
| 4 | PR-06D katlanır bağlantı | **Bloklu:** PR-06C tüm kapıları geçtikten sonra sabit-limit eşdeğerliği ve açılma duyarlılığı |
| 5 | PR-07 motor bağlantısı | Tork/enerji dengesi ve ölçüm korelasyonu |
| 6 | PR-08/09 CFD ve FEA | Bağımsızlık, izlenebilir solver kanıtı, güvenlik kapıları |
| 7 | PR-10 deney | Kalibrasyonlu veri ve belirsizlik içinde korelasyon |
| 8 | PR-11/12 optimizasyon ve sürüm | Robust Pareto kararı ve temiz yeniden üretim |

## İşbirliği sınırları

- **PyFoldable:** kanonik SI girdileri, çözüm sözleşmeleri, otomatik regresyonlar,
  model-form varsayımları ve kanıt paketlerinin bütünlüğü.
- **SolidWorks:** revizyonlu CAD ana modeli, üretilebilir geometri, kütle özellikleri
  ve değişim formatı; geometri değişikliği analiz kimliğini değiştirmelidir.
- **ANSYS:** açık solver/ağ/sınır koşulu kaydı, yakınsama ve bağımsızlık çalışmaları;
  yalnız ekran görüntüsü doğrulama kanıtı sayılmaz.
- **Deney:** kalibrasyon kayıtları, ham veri, çevre koşulları, tekrarlar ve belirsizlik
  bütçesi; işlenmiş özet ham verinin yerini alamaz.

## Karar özeti

Gerçek polar regresyonları temel veri hattının tekrar üretilebilirliğini kontrol altına
aldı; PR-06A/06B kod ve integrasyon temelini kurdu. PR-06C karakterizasyonu ise kritik
yolun artık **ileri uçuşta yerel negatif yüklenen annulus dalı** ve **temsili,
Reynolds-duyarlı pervane polarları** olduğunu gösterdi. Bu iki kapı aynı dondurulmuş
UIUC fixture/politika üzerinde geçmeden PR-06D'ye veya doğruluk iddiasına ilerlenmez.
