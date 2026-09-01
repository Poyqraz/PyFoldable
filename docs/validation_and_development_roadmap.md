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
| Rotor aerodinamiği | QPROP-tabanlı indüksiyon/swirl, uç/kök kaybı, radyal integrasyon ve üretici-geometri taraması mevcut | Temsili Reynolds-duyarlı spanwise polarlara dayalı rotor seviyesi doğrulama |
| Motor–pervane etkileşimi | PR-07 kapalı çevrim sayısal çekirdeği ve BEM callback sınırı mevcut | Ölçülmüş motor–pervane korelasyonu |
| Katlanır mekanizma | PR-06D fold-state sınırı, etkin yarıçap projeksiyonu ve sabit-limit kanıtı mevcut | Fiziksel nitelikli açılma duyarlılığı ve yük–performans geri beslemesi |
| CFD korelasyonu | Seviye-1 hazırlık/çıktı sözleşmeleri | Ağ bağımsızlığı ve BEM–CFD korelasyonu |
| Yapısal doğrulama | PR-09 CAD/malzeme/yük-vaka ve FEA sonuç sözleşmesi mevcut | Gerçek CAD, malzeme kartları ve ANSYS Mechanical kanıtı |
| Deneysel doğrulama | PR-10 kalibrasyon/ham veri/tekrar/belirsizlik sözleşmesi mevcut | Kalibre edilmiş standdan gerçek sabit ve katlanır ölçümleri |
| Optimizasyon | Parametrik tarama ve karar tabloları | Doğrulanmış modellerle robust çok amaçlı optimizasyon |

Bu nedenle mevcut sonuçlar mimari ve karşılaştırmalı geliştirme için değerlidir;
henüz nihai itki, verim, gerilme veya ömür garantisi olarak kullanılmamalıdır.

## Paralel UI hattı — PyFoldable Engineering Workspace

Fiziksel PR-06C/07/08/09/10 kapıları dış mühendislik ve deney girdilerini beklerken,
kanıt zincirini görünür ve kullanılabilir hale getiren ayrı bir UI hattı başlatıldı.
Bu hat bilimsel aşamaların sırasını veya geçiş eşiklerini değiştirmez.

- **UI-00/01 — aktif temel:** Streamlit kabuğu, uygulama görünüm modeli, sürümlü
  dashboard manifesti ve manifest–kanıt uyuşmazlığında fail-closed davranış.
- **UI-02 — ilk artım aktif:** kanonik 250 mm tasarım, beyan edilmiş 140 mm
  katlanmış zarf gereksinimi, 7100 rpm kontrol noktası ve PR-06C–PR-10 kapıları gerçek
  JSON kanıtlarından gösterilir. 140 mm değer elde edilmiş sonuç gibi sunulmaz;
  UI-03C geometrik uyumluluk kapısına bağlıdır.
- **UI-03A — 2.5D geometri önizlemesi aktif:** çap, göbek, kanat sayısı, NACA kesiti,
  chord–twist dağılımı ve menteşe açısı etkileşimli yüzeye bağlıdır. Çıktı açıkça
  `geometry_preview_not_cad_or_physical_result` olarak sınıflandırılır; config'e yazmaz.
  Kontrol review'i sonrasında tip yüzeyi çift menteşe kesitli rijit seam ile
  sertleştirilmiş, radyal merkez-hat ve gerçek mesh zarfı ayrı metriklere bölünmüştür.
- **UI-03B — aktif:** geometri ve ilk çalışma koşulu girdileri açık birimlerle ayrı
  `*_DRAFT.toml` çıktısına dönüştürülür. Taslak kaynak tasarım SHA-256 kimliğini ve
  `unqualified_design_draft` sınıfını taşır, kanonik dosyaya yazmaz ve indirmeden önce
  mevcut katı yükleyiciyle round-trip edilir.
- **UI-03C — tamamlandı:** girilen açık çap, göbek,
  menteşe, katlanma açısı ve zarf hedefi düzlemsel rijit uç-segment kinematiğiyle
  denetlenir. Görselleştirmeye ait düzlemsel radyal projeksiyon, eksene gerçek merkez-hat
  uzaklığı ve chord dahil mesh zarfı ayrı gösterilir; ilki PR-06D performans sonucu
  olarak etiketlenmez. Seçili açı ile tam katlanma yolu göbek teması ayrı kapılardır.
  Kanonik station'ların 0.20R–0.98R ile sınırlı
  olması göbekte 7 mm ve uçta 2,5 mm tanımsız yüzey bırakır. 100 mm sabit menteşe
  yarıçapı da en az 200 mm merkez-hat zarfı oluşturduğu için 140 mm hedef mevcut
  topolojiyle uyumsuzdur; arayüz bunu fail-closed hata olarak gösterir. V02 moment
  ayrıştırması yalnız SHA-256 ile sabitlenmiş sentetik yazılım fixture'ı, öngörülmüş
  açılarda ve aerodinamik menteşe yükü olmadan, `physical_qualification=false`
  sınırında sunulur. CAD katı temas/kalınlık modeli ile gerçek dinamik açılma ve ANSYS
  yükleri veri/geometry sözleşmeleri gelene kadar açık takip konularıdır.
- **UI-04 — aktif:** izin-listeli PR-06D recipe'si, sabitlenmiş 254 mm UIUC fixture'ını
  CLI ve Streamlit'in paylaştığı aynı application servisiyle oturum içinde yeniden
  çalıştırır. Analiz açık buton eylemi dışında başlamaz, repo/rapor yazmaz ve yeni
  sonuç `session_screening_computation`, `screening_only_until_pr06c_passes`,
  `physical_qualification=false` olarak arşiv kanıtından ayrı gösterilir. Semantik,
  deterministik JSON ve SHA eşdeğerliği arşivle uyuşmazsa koşum fail-closed durur.
  İndirilen oturum manifesti hesap politikası ve istek SHA'larını, fixture/arşiv
  provenance'ını ve ham oturum sonucunu ayrı sınıflandırmayla birlikte taşır.
- **UI-05A — tamamlandı:** yayımlanmış CFD referans fixture'ları ile sürümlü
  PR-09 FEA ve PR-10 deney sözleşme raporları oturum içinde yüklenir; tür, şema,
  kimlik, birim, qualification ve SHA denetimleri uyuşmazlıkta fail-closed durur.
  Dosya repo'ya yazılmaz ve hiçbir yükleme fiziksel yeterlilik üretmez.
- **UI-05B — sıradaki kontrollü dilim:** gerçek ANSYS sonuç vakaları ve kalibre
  edilmiş ham deney run/sample bundle'ları typed sözleşmelere ayrıştırılıp mevcut
  değerlendirme çekirdeklerine bağlanacaktır.
- **UI-06–07 — sonraki artımlar:** rapor merkezi,
  uçtan uca/görsel regresyon ve paketleme.

Arayüzde `qualified`, `screening_only`, `pending`, `failed` ve `blocked` durumları
ayrıdır. PR-06C geçmeden katlanmış durum `screening_only` dışında sunulamaz. Ayrıntılı
sözleşme ve teslim sırası [UI çalışma alanı belgesindedir](ui_engineering_workspace.md).

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

### Python öncelikli geliştirme — 2026-09-01 kapsam kararı

Kullanıcı kararıyla MATLAB'da planlanan sayısal işler, mümkün olan yerde mevcut
Python çekirdeği üzerinde geliştirilecektir. Baskı yönü/üretim DoE bu yazılım
hattının önceliği veya engeli değildir; mevcut malzeme doğrulama kapıları korunur.
SciSpace + Consensus araştırması, kaynak erişim sınırları ve kabul ölçütleri
[Python araştırma/yürütme planındadır](python_research_execution_plan.md).

1. **PY-01 — tamamlandı (PR #49):** tam taslak TOML'den nominal yerel Reynolds/Mach/hücum
   açısı hazırlığı ve açıkça verilen polarlarla mevcut BEM çözücüsünü çağıran ayrı
   Python servisi. UI hazırlığı gösterir; BEM butonu henüz eklenmez. İndüksiyonsuz
   hazırlık tam solver sorgu zarfı değildir. 254 mm sabit benchmark değişmez.
2. **PY-02 — uygulandı:** beş proje profilinin kaynak/hash kayıtlı çevrimdışı
   koordinatları, taslak round-trip, aynı koordinatlarla önizleme ve her polar
   tablosunda koordinat kimliği kontrolü. [Kaynaklar ve kabul](py02_profile_coordinate_identity.md).
   **PY-03 — sıradaki:** doğrulanmış polar bundle'ıyla aktif taslak UI analizi.
   Eksik polar yerine otomatik proxy veya clamp yoktur.
3. **PY-04 / PR-11A:** deterministik tarama ve optimizasyon altyapısı; sentetik
   doğruluk testleri, sınırlı hesap bütçesi, açık başarısızlık kaydı. Fiziksel
   optimum tasarım önerisi değildir.
4. **PY-05/06:** mekanizma geçiş dinamiği, kalibrasyon/belirsizlik ve eşleştirilmiş
   referans raporları; mevcut sözleşmeleri genişletir. PR #3 ayrı tutulur.

Bu sıra, veri bekleyen fiziksel PR-06C–PR-10 kapılarının açıldığını göstermez.

### PR-06 — rotor aerodinamiği

- **PR-06A — yerel indüklenmiş-akış çekirdeği (tamamlandı ve review edildi).** Hover'da tekillik
  üretmeyen QPROP akış açısı parametrelemesiyle bir pal annulusunda eksenel indüksiyon,
  swirl, değiştirilmiş Prandtl uç kaybı ve diferansiyel itki/tork çözülür. Çözüm
  yakınsamazsa kapalı biçimde hata verir; tam rotor BEM iddiası taşımaz.
- **PR-06B — radyal rotor integrasyonu (tamamlandı).** Annulus orta noktaları,
  chord/twist enterpolasyonu, açık radial-domain politikası, seçilebilir kök/uç
  kayıpları, rotor toplamları ve boyutsuz performans katsayıları eklendi. Fiziksel
  doğruluk iddiası PR-06C benchmark kapısına bağlıdır.
- **PR-06C — sabit pervane benchmark'ı (nihai fiziksel kapı yürütüldü ve fail-closed;
  üretici-geometri altyapısı tamamlandı;
  kanıt/dönel-model temeli tamamlandı; polar/ileri-uçuş kapıları başarısız).** UIUC APC SF 10×4.7 rüzgâr-tüneli verisi üzerinde 60
  ham/50 propulsif nokta ve değişmeyen CT/CP politikası korunuyor. İncelenmiş
  `signed_nonreversed` dalı yerel negatif yüklemeyi ters akışa izin vermeden çözüyor;
  toplam/ileri-uçuş kapsamı %46/%20,6'dan %100/%100'e çıktı. Tam zarf artık proxy
  modelin CT/CP'yi sırasıyla %26,40/%28,28 eksik tahmin ettiğini gösterdi. Kullanıcı-
  yerel, SHA sabitlenmiş güncel APC PE0 geometrisiyle proxy taraması toplam CT/CP
  WMAPE'yi %16,23/%16,98'e indirdi; ancak CT biası −%14,07, ileri-uçuş CT/CP WMAPE
  %25,68/%23,19 ve temsili spanwise polar kanıtı hâlâ kapı dışıdır. Bu nedenle PR-06D
  fiziksel doğruluk iddiası blokludur; ancak bu başarısız karar açıkça korunarak
  yazılım temeli başlatılmıştır. Ayrıntı [geometri/polar remediation](pr06c_geometry_polar_remediation.md)
  ve [kritik kapı review](pr06c_critical_gate_review.md) belgelerindedir. Temsili polar
  statüsü artık koordinat/provider sürümü, tam solver sorgu zarfı ve iki-capture
  promotion kaydı olmadan üretilemez. Snel-1993 düzeltmesi varsayılan tam no-op ve
  açık provenance ile eklendi; proxy ablation statik hatayı azaltırken ileri-uçuş
  hatasını kapatmadığı için fiziksel niteleme iddiası oluşturmadı.
- **PR-06D — katlanır geometri bağlantısı (yazılım temeli aktif).** Typed açılma
  durumu, menteşe sınırı, etkin yarıçap ve malzeme-istasyonu projeksiyonu rotor
  çözücüsüne taşındı. Tam açık yol, donmuş UIUC matrisindeki 50/50 propulsif noktada
  sabit çözücüyle bit düzeyinde aynı sonuç verdi (maksimum |ΔT| ve |ΔQ| = 0).
  Geçersiz/çökmüş durumlar kapalı biçimde hata veriyor; polar kimliği malzeme
  yarıçapıyla taşınıyor ve sonuçlar nominal/etkin geometri provenance'ı içeriyor.
  Bu [sabit-limit kanıtı](../reports/pr06d_fixed_limit_equivalence.md) yalnız yazılım
  eşdeğerliğidir; katlanmış durumun fiziksel doğruluğu PR-06C geçmeden nitelikli değildir.
  Açılma duyarlılığı yazılım adımı da tamamlandı: donmuş 50 propulsif nokta üzerinde
  0/15/30/45/60 derece için 250 vakalık eksiksiz tarama üretildi ve tam açık uç yeniden
  birebir doğrulandı. Sonuç [açılma taraması](../reports/pr06d_opening_sensitivity.md)
  içinde `screening_only_until_pr06c_passes` olarak kilitlidir; tasarım kararı veya
  fiziksel niteleme değildir.

  Acar'ın 2025 mafsallı uç-pervane BEM çalışması da yöntem kanıtı olarak tersine
  mühendislikle incelendi. Otuz bir sayısal nokta işaret güvenli rejim denetimine,
  birleşik tip-akış bağıntısına ve verim fail-closed kurallarına dönüştürüldü. Ayrı
  bir uç rotoru ile katlanan ana-pal devamı aynı fiziksel topoloji olmadığı için
  makale sonuçları PR-06D doğrulama hedefi yapılmadı. Ayrıntılar
  [Acar 2025 review belgesindedir](pr06d_acar_2025_reverse_engineering.md).

Yayımlanmış APC 10x4.7 CFD taraması da makine-okunur bir kapsam sözleşmesine bağlandı.
ICAS Fluent SST k-omega sonuçları, aynı UIUC statik CP noktalarında yeniden hesaplanan
en çok %1,27 hata gösterirken mevcut analitik-proxy BEM yolu yaklaşık %10,22 ve %19,86
eksik kalıyor. Bu bulgu eşikleri değiştirmiyor; temsili Reynolds-duyarlı polar zincirini
öncelikli tutuyor. Ayrıntılar [yayımlanmış CFD review](../reports/pr06c_published_cfd_review.md)
ve [bağımsız ANSYS isterinde](independent_aerodynamic_review_request.md) kayıtlıdır.

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

**Yazılım/nümerik kapı tamamlandı.** Global RPM taraması benzersiz ortak kökü bulur;
birden fazla kökü, köksüz aralığı, geçersiz aerodinamik yükü ve elektriksel sınır
ihlallerini kapalı biçimde raporlar. Sabit veya katlanır BEM çözücüsü her aday RPM'de
yeni çalışma koşuluyla çağrılır. Beş donmuş analitik yük vakasında tork, gerilim ve
şaft-enerji kalıntıları ile üç ayrı başlangıç kontrolü geçmiştir. Bu kanıt yalnız
yazılım davranışını niteler; fiziksel kapı ölçülmüş motor–pervane korelasyonu gelene
kadar `pending_measured_correlation` durumundadır. Ayrıntılar
[PR-07 yürütme planı](pr07_fully_coupled_execution_plan.md) ve
[kanıt raporundadır](../reports/pr07_fully_coupled_evidence.md).

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

**Yazılım/hazırlık kapısı tamamlandı.** CAD revizyonu ve SHA-256 kimliği,
izotropik/ortotropik malzeme kapsamı, beş zorunlu yük vakası, üç seviyeli mesh
yakınsaması, kuvvet dengesi, birim kontrollü sonuç metrikleri ve proje tarafından
tanımlanacak kabul limitleri fail-closed sözleşmeye bağlandı. Birinci-taraf sentetik
fixture yalnız doğrulayıcının davranışını kanıtlar. Gerçek proje durumu; revizyonlu
CAD, PA-CF/pim/kilit/stop malzeme kartları, onaylı limitler ve ANSYS sonuçları gelene
kadar `blocked_waiting_for_real_structural_inputs` olarak kalır. Ayrıntılar
[PR-09 yürütme planı](pr09_fea_contract_execution_plan.md) ve
[kanıt raporundadır](../reports/pr09_fea_contract_evidence.md).

### PR-10 — deneysel doğrulama

İtki/tork/devir/elektrik gücü veri şeması, sensör kalibrasyonu, sıfır kayması,
tekrarlı ölçüm ve belirsizlik yayılımı sürümlenir. En az bir sabit referans pervane ve
katlanır prototip aynı düzenekte ölçülür; BEM ve CFD farkları belirsizlik bantlarıyla
raporlanır.

**Yazılım/hazırlık kapısı tamamlandı.** Yedi zorunlu sensör kanalı; sertifika
kimliği, SHA-256, geçerlilik aralığı ve standart belirsizlikle bağlandı. Sabit referans
ve katlanır prototip rolleri, en az üç tekrar, ham veri kimliği, deney öncesi/sonrası
sıfır kayması ve Type-A + kalibrasyon + drift belirsizlik yayılımı fail-closed olarak
uygulandı. Sentetik fixture yalnız şema ve matematiği doğrular. Fiziksel kapı gerçek
kalibrasyon kayıtları ve ham tekrar ölçümleri gelene kadar
`blocked_waiting_for_calibrated_raw_measurements` durumundadır. Ayrıntılar
[PR-10 yürütme planı](pr10_experiment_contract_execution_plan.md) ve
[kanıt raporundadır](../reports/pr10_experiment_contract_evidence.md). UIUC APC Slow
Flyer 10x4.7 için 60 noktalı yayımlanmış harici referans ve bağımsız aynı-pervane
Morgado/Pascoa yöntem karşılaştırması bağlandı. Bunlar model/doğrulama bağlamıdır;
proje katlanır prototipinin kalibrasyonlu ham ölçümü sayılmaz.

### PR-11 — robust çok amaçlı optimizasyon

**PR-11A yazılım altyapısı** gerçek veriden önce sentetik/analitik testlerle
ilerleyebilir; Python-first planda PY-04'e bağlıdır. **PR-11B fiziksel tasarım
kararı** ise aşağıdaki doğrulama koşullarına bağlı kalır.

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
| 3 | PR-06C referans benchmark | Nihai kapı kodu ve yeniden üretilebilir karar tamamlandı; donmuş fixture/politika geçiyor, gerçek E63→APC12 sağlayıcı zinciri, ileri-uçuş doğruluğu ve bağımsız model-form review başarısız |
| 4 | PR-06D katlanır bağlantı | **Yazılım taraması tamamlandı:** sabit-limit ve 250-vaka açılma duyarlılığı kanıtı mevcut; fiziksel nitelikli açılma duyarlılığı PR-06C'ye bağlı |
| 5 | PR-07 motor bağlantısı | **Sayısal kapı tamamlandı:** tork/gerilim/enerji dengesi, benzersiz kök ve çoklu başlangıç; fiziksel kapı ölçüm korelasyonunu bekliyor |
| 6 | PR-08/09 CFD ve FEA | PR-08 CFD gerçek ANSYS çıktısını bekliyor; PR-09 yazılım/hazırlık sözleşmesi tamamlandı, gerçek yapısal kanıt bekleniyor |
| 7 | PR-10 deney | Yazılım/hazırlık ve kamuya açık aynı-pervane referans temeli tamamlandı; kalibrasyonlu gerçek sabit/katlanır ham ölçümler bekleniyor |
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
aldı; PR-06A/06B kod ve integrasyon temelini kurdu. PR-06C düzeltmesi ileri uçuşta
yerel negatif yüklenen annulus dalını tamamladı ve tüm propulsif noktaları çözdü.
Kritik yol artık **tested blade'i temsil eden E63→APC12 spanwise, Reynolds-duyarlı polar kanıtı**,
**dönel/model-form hata düzeltmesi** ve **bağımsız aerodinamik review**dur. Aynı
dondurulmuş UIUC fixture/politika üzerindeki tüm kapılar geçmeden PR-06D'nin fiziksel
doğruluk iddiasına veya nitelikli açılma duyarlılığına ilerlenmez. Sabit-limit yazılım
eşdeğerliği bu sınırı değiştirmeden PR-06D uygulama aşamasına giriş sağlamıştır.
