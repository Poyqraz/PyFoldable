# GEOM-04 — yüzey mesafesi ve açık donanım geometrisi

Durum: **04A–04D uygulandı**; kapsam ve sınırlar [teslim belgesinde](geom04_surface_hardware.md).
04A: PR #62. Başlangıç: GEOM-03 / PR #61,
`943f5f3e5f950e4d2b2c18f5968e5b39f7cad710`. Tarih: 2026-09-16.

## Amaç ve sınır

Mevcut BVH kutuları yakın yüzeylerde örtüşünce sonuç çoğunlukla `unknown` kalıyor.
GEOM-04, bu durumları üçgen düzeyinde mesafe/kesişim hesabıyla azaltacak; ardından
kullanıcının açık verdiği göbek ve bağlantı geometrisini aynı denetime bağlayacak.
Python öncelikli; ilk iki artım ANSYS veya yeni ölçüm beklemez.

Mevcut hareket sözleşmesi korunur: senkron, düzlemsel, rijit uçlar. Açık kanat
yüzeyleri katı cisim sayılmaz. Eksik istasyonlar tamamlanmaz; bağlantı dışlamaları
silinmez; GEOM-01 adaylarına sonuç aktarılmaz. `physical_qualification=false` ve
`full_propeller_clearance=null` kalır. Literatür geometrisi kaynak/revizyonuyla
geçici referans olabilir; bu pervanenin ölçümü olarak sunulamaz.

## Sıralı teslimler

| Artım | Değişiklik | Kabul kapısı |
|---|---|---|
| **04A — ilk geliştirme** | `geometry/triangle_distance.py`: nokta–üçgen, doğru parçası–doğru parçası, doğru parçası–üçgen kesişimi ve üçgen–üçgen mesafe aralığı; en yakın noktalar ve geometrik özellik kimlikleri | Analitik mesafeler; yüzey içi kesişim; eşdüzlemli, paralel ve dejenere vakalar; sayısal belirsizlikte güvenli sonuç |
| **04B — sürekli yol** | Mevcut `surface_clearance.py` yapraklarında dar faz; yeni iş bütçesi, aralık alt sınırı ve gerçek en yakın nokta tanığı; sonsuz göbek için izdüşüm mesafesi inceltmesi | Kutuları örtüşen fakat ayrık yüzeylerin çözülmesi; yalnız ara açıda yaklaşma; iki hareketli pivot; hiçbir yanlış `separated` |
| **04C1 — donanım sözleşmesi** | Kaynak-bağlı sonlu göbek/bağlantı girdileri, birimler, koordinat çerçevesi, rijit parçaya bağlanma, transform, tolerans ve revizyon/hash | Bozuk/topolojik olarak geçersiz geometri reddi; dosya/iş sınırları; kaynak değiştirme ve eski sonuç iptali |
| **04C2 — donanım sorguları** | İlk destek: açık ölçülü sonlu silindir göbek ve kapalı, dışbükey çokyüzlü bağlantılar; yüzey–katı mesafesi ve içeride kalma denetimi | Kapak/yan yüzey/kenar yakınlığı; tamamen içeride kalma; iki katının iç içeliği; bağımsız hareket çerçeveleri; sayısal belirsizlikte `unknown` |
| **04D — arayüz ve tamamlama** | Dar faz nedeni, tanık noktaları/açısı, donanım kapsamı, bütçe kullanımı ve sürümlü JSON; aynı taslak otoritesi | AppTest, sayfa geçişleri, hatalı girdi, kaynak değişimi, başarısız tekrar çalıştırma ve gerçek sunucu açılışı |

04A ayrı ve küçük PR olur. 04B sonrasında mevcut arayüz yeni motoru kullanabilir;
donanım UI'sı 04C kapıları geçmeden etkinleştirilmez. Her artım kendi test/review/CI
kapısından geçer. 04A/B bitince GEOM-04 bütünü tamamlandı işaretlenmez.

## Sayısal sözleşme

1. Dar faz tek bir yaklaşık mesafeyi alt sınır diye sunmaz. Sonuç, mesafe için
   `lower_m`, `upper_m`, geçerli tanık noktaları ve `reason` taşır. Kesişim testi
   ayrıca yapılır: yalnız köşe–yüz ve kenar–kenar mesafeleri, bir kenarın üçgen
   içinden geçtiği bütün vakaları çözmez.
2. Gerçekten sıfır alanlı üçgen nokta/doğru parçasına indirgenebilir. Neredeyse
   dejenere üçgenin yüzeyi sessizce atılamaz; hata sınırı kurulamazsa alt sınır
   sıfır, karar `unknown` kalır. Ölçeğe ve koşulluluğa bağlı sayısal pay, donanım
   toleransı ve mesh yaklaşım hatası ayrı kaydedilir. 04A kabulü için dışa yuvarlanan
   aralık hesabı veya belirsiz geometrik kararlarda kesin/rasyonel geri dönüş ve
   mesafe dönüşümünde dışa yuvarlama tanımlanır; yalnız sabit/ölçekli epsilon yeterli
   sayılmaz. Geri dönüşün işlem limiti aşılırsa alt sınır sıfır korunur.
3. Orta pozdaki **güvenli mesafe alt sınırı** `d_low`, aralık genişliği `w` ve
   pivot uzaklıklarının üst sınırları `r_A`, `r_B` için önerilen inceltme:
   `L = max(0, d_low - 2*r_A*sin(w/4) - 2*r_B*sin(w/4))`.
   Sabit parçanın hareket terimi sıfırdır. Bu, küme mesafesinin nokta yer
   değiştirmelerine göre değişim sınırından türetilir; uygulamadan önce bağımsız
   matematik review'ü gerekir. Pozlar arasında örnekleme tek başına kabul değildir.
4. Her ilgili üçgen çifti veya onu kapsayan kutu için alt sınır geçmeli. Pozitif
   açıklıkta `upper_m < clearance - guard` bir ihlal tanığıdır; eşik çevresi
   `unknown`. Sıfır açıklıkta sıfır mesafe otomatik ihlal değildir: doğrulanmış
   temas/kesişim ayrı `contact_status` ile bildirilir. Rapor sürümü bu ayrımı
   açıklar; mevcut üç durumun anlamı sessizce değiştirilmez. Bu ayrım katıya
   nüfuzu gizlemez: sıfır istenen açıklıkta doğrulanmış iç bölgeye giriş yine
   `violation` olur. Sınır teması ve tamamen içeride kalma ayrı regresyonlardır.
5. Sonsuz silindir için üçgenin XY izdüşümüne orijinden en kısa mesafe, yarıçap
   çıkarılarak mevcut işaretli açıklıkla ilişkilendirilir. Merkezin izdüşümün
   içinde olması, çizgi/nokta izdüşümü ve aralık boyunca hareket ayrıca test edilir.
   Sonlu silindir seçilince bu eski zarf fiziksel göbekmiş gibi raporlanamaz.
6. Göbek yüksekliği/bağlantı ölçüleri bilinmiyorsa değer üretilmez. Sonlu silindirin
   doğrudan sorgusu veya iç/dış geometrik yaklaştırmalarının kanıtlanmış hata
   sınırları gerekir; kaba üçgenleme üzerinde ayrılma bulmak yeterli değildir.
   Dışbükey katı girdilerinde kapalılık, yönelim, pozitif hacim, dışbükeylik ve
   kesişen/bozuk yüzler doğrulanır. Genel içbükey CAD, otomatik mesh onarımı,
   STL/STEP dönüştürme ve asenkron hareket bu artımın dışındadır.

   Beklenen mekanik temas, bir parçanın tüm sorgularını kapatamaz. Temas/dışlama
   bölgeleri kaynak ve rijit parça kimliğiyle açık seçilir; varsayılan dışlama
   yoktur. Seçilmiş bölgenin dışındaki yüzeyler denetlenir, bölgenin kendisi
   `not_evaluated` kalır; montaj teması için otomatik fiziksel kabul verilmez.

## TDD ve doğrulama

- Önce başarısız test: örtüşen AABB/ayrık üçgen; örnek köşelerin kaçırdığı kenar–yüz
  kesişimi; eşdüzlemli iç içelik; çok ince üçgen; ortak kenar/köşe; sıfır açıklık.
- Analitik/rasyonel fixture'lar ve uygulanandan bağımsız yüksek hassasiyetli küçük
  referans çözüm. Parça değiş tokuşu, köşe sırası, rijit dönüşüm ve desteklenen
  ölçeklerde mesafe tutarlılığı. Rastgele testler analitik kabulün yerine geçmez.
- Sürekli yol: uç pozlar açıkken ara poz yakın; farklı pivotlar; kısmi yol;
  aralık kaydı bütçe kesilince de yolu kapsar. Bütçe artırımı yeni yanlış başarı
  yaratamaz; güvenilir tanık veya alt sınır bulunmadan durum değişmez.
- Aynı iş bütçesinde dondurulmuş zor fixture kümesinde 03'e göre bazı `unknown`
  vakalar çözülmeli. İncelenmeyen çiftler başarı sayılmaz. Küresel BVH bütçesine
  ek olarak sayılı ve üst sınırlı üçgen/özellik sorgu bütçesi konur; yaprak içindeki
  iş bedelsiz kabul edilmez. Limitler ölçülerek seçilir ve istek hash'ine bağlanır.
- Mevcut 8 kanat/12000 üçgen/depth 8 sınırları başlangıçta artırılmaz. Çalışma
  süresi ölçülür; CI'da donanıma bağlı sıkı süre yerine deterministik iş sayısı
  sınanır. BVH yeniden kullanımı ancak profil ölçümü gerektirirse eklenir.
- Servis: eski ve yeni rapor sürümü, geometri/hardware/tolerans değişimi, geçersiz
  transform, istek oynama, eksik kapsam, kaynak kimliği ve stale-state testleri.
  Girdi/çıktı sürümü ile yeni modül hash'leri güncellenir.

## Review ve entegrasyon akışı

RED → GREEN → gerekirse refactor → **ayrı otomatik reviewer** → düzeltme/etkilenen
testler → tam regresyon → PR → son GitHub review ve tam head CI → merge → tree eşliği.
Python 3.10/3.11 CI; UI için AppTest ve gerçek Streamlit başlangıcı korunur.

**Gemini bekleme kapısı yok.** Cursor Bugbot etkinse PR'nin güncel head'i için
çalıştırılır; bulgular çözülüp son GitHub kontrolünde tekrar incelenir. Cursor
yardımı erişim varsa sınırlı implementasyon/debug görevlerinde kullanılabilir;
aynı ajan kendi değişikliğinin bağımsız reviewer'ı sayılmaz. Erişim/kota yoksa
çalıştırılmış gibi yazılmaz; durum kaydedilir ve mevcut bağımsız reviewer + CI
akışı sürer. Bu plan hazırlanırken ayrı Cursor çalıştırma aracı görünmüyor;
geliştirme başlangıcında erişim ve Bugbot PR entegrasyonu yeniden kontrol edilir.

PR #3 ve kullanıcıya ait rapor değişiklikleri korunur. Gereksiz tüm-suite tekrarları
yapılmaz; matematik, hizmet ve UI görevleri yalnız bağımsız çalışabiliyorsa ayrılır.

## Başvuru kaynakları

- [FCL](https://github.com/flexible-collision-library/fcl): mesafe, temas ve sürekli
  hareket sorgularının ayrımı için yöntem referansı; zorunlu bağımlılık değil.
- [CGAL AABB Tree](https://doc.cgal.org/latest/AABB_tree/index.html): BVH ve geometrik
  sorgu ayrımı; dejenere girdiler için uyarılar. Hazır üçgen–üçgen sürekli çözüm
  olarak kabul edilmeyecek; bu paketin mesafe sorguları nokta sorgularıyla sınırlı.
- Repo temeli: [GEOM-03](geom03_surface_clearance.md),
  `geometry/surface_clearance.py`, `application/surface_clearance.py` ve mevcut
  geometri/servis/UI testleri. Kaynaklar 2026-09-16 tarihinde kontrol edildi.

## 04A teslim kaydı

Kesin rasyonel mesafe çekirdeği, dışa yuvarlanan sınırlar ve tanık özellik kimlikleri
uygulandı. 39 çekirdek testi geçti; bağımsız review
120 rasyonel KKT referansında aralıkları ve temas kararlarını doğruladı.
04A tek başına GEOM-04 tamamlanması değildir; hizmet ve arayüz değişikliği içermez.
