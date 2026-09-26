# PyFoldable validation and development roadmap

Bu belge, birleşmiş GEOM-01–04 ve PR #67–#69 tarama/kanıt zinciri ile ayrı duran
BEM, motor dengesi ve PY-05 alt modellerinden sonraki teknik konumu tanımlar.
Hedef hâlâ katlanabilir pervane için **deneyle doğrulanmış, tasarım kararı
vermeye elverişli** bir analiz zinciridir. Yüzde cinsinden tek bir "tamamlanma"
değeri verilmez. Yazılım altyapısı, tanı çıktısı ve fiziksel tahmin doğruluğu
aynı şey değildir. Matematiksel model tamamlanmış değildir.

Kod/CI tabanlı tarihli durum, dokümantasyon farkları ve yeni ajan başlangıcı:
[güncel repo hafızası](agent/current-state.md). Ayrıntılı özellik sözleşmeleri
bu yol haritasındaki bağlantılarda kalır.

## Güncel konum

PR-04 ve PR-05 serileri tamamlandı. XFOIL ve NeuralFoil gerçek regresyonları,
tekrarlanabilirlik kontrolü, polar ailesi üretimi ve iki boyutlu kesit tüketimi artık
korunan bir temel oluşturuyor. Aktif taslak BEM/tarama arayüzü, PY-05 terminal
temaslı mekanizma çözümü ve PY-06A–C karşılaştırma altyapısı da mevcut.
**Yazılım kapsamı genişledi; rotor, mekanizma ve yapı için proje ölçümleriyle
fiziksel doğrulama tamamlanmadı.**

| Alan | Bugünkü durum | Hedefe göre açık |
| --- | --- | --- |
| Polar sağlayıcı altyapısı | Gerçek XFOIL/NeuralFoil regresyonlarıyla nitelikli | Yeni airfoil ve çalışma zarfı büyüdükçe yeniden niteleme |
| 2B kesit aerodinamiği | Reynolds/Mach enterpolasyonu ve izlenebilir kesit yükleri mevcut | 3B dönel akış ve stall düzeltmeleri |
| Rotor aerodinamiği | QPROP-tabanlı indüksiyon/swirl, uç/kök kaybı, radyal integrasyon ve üretici-geometri taraması mevcut | Temsili Reynolds-duyarlı spanwise polarlara dayalı rotor seviyesi doğrulama |
| Motor–pervane etkileşimi | PR-07 cebirsel tork dengesi duruyor. CMM-1 bunu zaman domeninde, sabit gaz ve bütün rotor BEM şaft torku ile kullanır. Bu, fiziksel motor doğrulaması değildir | Gerçek dinamometre/rotor ölçümleri ve fiziksel korelasyon |
| Katlanır mekanizma | PY-05 öngörülen tahrikli modeli duruyor. CMM-1 ayrı bir kısmi bağlaşık tarama geçişidir: ortak `theta`, dinamik `omega`, aerodinamik menteşe momenti yok. GEOM-01–04 + PR #67–#69 ayrı bir sayısal tarama/kanıt zinciridir | Derin katlanma, sıfır devirden kalkış, çarpışma/kilit, kalibrasyon ve fiziksel açıklık niteliği açık |
| CFD korelasyonu | Seviye-1 hazırlık/çıktı sözleşmeleri | Ağ bağımsızlığı ve BEM–CFD korelasyonu |
| Yapısal doğrulama | PR-09 CAD/malzeme/yük-vaka ve FEA sonuç sözleşmesi mevcut | Gerçek CAD, malzeme kartları ve ANSYS Mechanical kanıtı |
| Deneysel doğrulama | PR-10 v2 provenance zinciri ve PY-06A eş-koşul karşılaştırma çekirdeği mevcut | Kalibre edilmiş standdan gerçek sabit ve katlanır ölçümleri |
| Optimizasyon | Parametrik tarama ve karar tabloları | Doğrulanmış modellerle robust çok amaçlı optimizasyon |

Bu nedenle mevcut sonuçlar mimari ve karşılaştırmalı geliştirme için değerlidir;
henüz nihai itki, verim, gerilme veya ömür garantisi olarak kullanılmamalıdır.
CI, içerik hash'i, sayısal yakınsama, readiness tanısı ve sentetik fixture
fiziksel doğruluk değildir. İlgili sözleşmelerde `physical_qualification=false`
korunur.

## Mevcut model konumu — 2026-09-23

Bu bölüm beş soruyu ayırır: hangi sayısal yetenek vardır, ne yalnız tarama/tanıdır,
ne fiziksel olarak nitelenmemiştir, sonraki matematiksel dilim nedir ve hangi
işler veri gelmeden otomatik sonraki uygulama sayılmaz.

### GEOM tarama ve kanıt zinciri

GEOM-01–04 ile PR #67, #68 ve #69 birlikte sınırlı bir sayısal tarama/kanıt
zinciri oluşturur. Geometri özelliği genişletmesi burada duraklatılacak kadar
olgunlaşmıştır. Geometri kalıcı olarak bitmiş değildir. Zincir fiziksel açıklık
niteliği vermez.

Katmanlar birbirinin yerine geçmez:

1. GEOM-04 adaya özel açıklık kanıtı üretir.
2. PR #67 bu kanıtı adaya bağlı, kimliği doğrulanmış ve değiştirilmeden ekler.
3. PR #68 isteğe bağlı ve yalnız negatiftir. Uygun bir ihlal tanığı
   `surface_path_clearance=False` veya `interblade_clearance=False` yapabilir.
   Hiçbir sonuç `True` olmaz.
4. PR #69 isteğe bağlı pozitif-hazırlık tanısıdır. Sonuç
   `preconditions_satisfied`, `blocked` veya `not_applicable` olur. Kısıt atamaz,
   seçimi değiştirmez ve `True` yetkisi vermez.

`preconditions_satisfied`, `clearance=True` değildir. Mevcut açık-yüzey modelinde
yüzey-yolu hazırlığı `shared_hinge_contact_domain_unresolved` ile bloklu kalır.
Uygun tam açıklıklı sentetik/sayısal kanıtta interblade hazırlığı gelecekteki
pozitif önkoşulları karşılayabilir; GEOM-01 kapısı yine `None` kalır. Negatif
politika bağımsız olarak `False` yazmışsa o değer durur.

Politika veya tanı yokken iki yüzey kapısı bilinmez kalır. Bilinmezlik artık
tek davranış değildir.

Duraklatılan geometri işi, sonraki model dilimi değildir:

- kapıların `True` yapılması
- paylaşılan menteşe için izinli temas semantiği
- keyfi CAD veya dışbükey olmayan katılar
- asenkron hareket
- ikili sıfır genişlik tekil yaprak için yapısal sıkılaştırma
- tam pervane fiziksel açıklık niteliği

Yinelenen ikili sıfır genişlik tekil, bilinen ve engellemeyen teknik borçtur.
Sonraki kilometre taşı yapılmaz. `True` promosyonu ancak ayrı review sonrası
ertelenmiş iştir. PR #69 onu hemen uygulama izni değildir.

Ayrıntı [GEOM-01](geom01_feasibility_plan.md),
[GEOM-03](geom03_surface_clearance.md) ve
[GEOM-04](geom04_surface_hardware.md) sözleşmelerindedir.

### Sayısal alt modeller

PyFoldable'ın birkaç matematiksel alt modeli vardır. Bütünleşik sistem modeli
yoktur.

| Alt model | Durum | Sınır |
| --- | --- | --- |
| Geometri taraması | implemented, diagnostic | GEOM-01–04 + #67–#69. Olgun sınırlı tarama; fiziksel açıklık değil |
| Rotor aerodinamiği | implemented | Sayısal BEM var. Proje rotoru fiziksel olarak eksik. PR-06C kapısı bloklu |
| Motor–rotor dengesi | implemented | Ortak devirde tork dengesi. Zaman domeninde mekanizma bağlaşımı değil |
| Mekanizma geçişi | implemented | PY-05 öngörülen tahrik. Tam bağlaşık açılma modeli değil |
| Bütünleşik aero–motor–mekanizma | proposed next slice | Uygulanmadı. Kabul edilmiş ADR değil |
| Deneyle doğrulanmış öngörü sistemi | blocked on evidence | Ulaşılmadı |

PY-05 gerçek bir sayısal geçiş modelidir: tek düzlemsel rijit uç cismi,
öngörülen devir geçmişi, öngörülen menteşe torku, RK45, ilk durdurucu temasında
durma, yay, sönüm, isteğe bağlı düzgün kuru sürtünme, merkezkaç ve Euler tork
terimleri. Çarpışma devamı, mandal, statik tutunma, iki yönlü BEM/motor geri
beslemesi ve kalibre aerodinamik menteşe momenti yoktur. Ayrıntı
[PY-05 tamamlanma sınırı](py05_completion.md).

Motor ve BEM kodu rotor aerodinamik çözümünü, motor/rotor tork dengesini ve
katlanır rotorun sayısal geometri yollarını destekler. Bu, zaman domeninde
motor ile mekanizmanın birbirini sürmesi değildir. PR-06C fiziksel sınır
görünür kalır: sayısal çalışma veya yakınsama, proje rotorunun fiziksel
doğrulaması değildir. Başarısız ve bloklu benchmark durumu silinmez.

### Üç olgunluk düzlemi

Bu üç düzlem karıştırılmaz.

**A. Sayısal model tamamlama.** Sonraki önerilen dilim, Coupled
Aero–Motor–Mechanism modelinin önce davranış/matematik sözleşmesi, ancak
ondan sonra sınırlı uygulamasıdır. Bu belge o sözleşmeyi yazmaz.

**B. Parametre kestirimi.** PY-06D2, bağımsız ölçülmüş ve tanımlanabilir veri
yokken blokludur. Kütle/atalet, yay, sönüm/sürtünme, devir/zaman, mekanizma
açı geçmişi ve ilgili tork/yük bilgisi örnekleridir. Yalnız optimizasyon
yakınsaması doğrulama değildir. Literatür değerleri proje kalibrasyonu yapılmaz.

**C. Fiziksel yeterlilik.** Proje rotoru aerodinamik korelasyonu, motor/rotor
ölçümü, yapısal CAD/malzeme/FEA ve deneysel mekanizma/açılma kanıtı ayrı
kapılardır. Sentetik fixture, CI ve readiness bu kapıları açmaz.

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
- **UI-05B — sonraki UI dilimi:** gerçek ANSYS sonuç vakaları ve kalibre
  edilmiş ham deney run/sample bundle'ları typed sözleşmelere ayrıştırılıp mevcut
  değerlendirme çekirdeklerine bağlanacaktır. Bu, arayüz hattındaki sonraki
  kontrollü dilimdir. Sonraki sayısal model kilometre taşı değildir.
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

## Önerilen sonraki matematiksel dilim

**2026-09-24 düzeltmesi.** PR #70 bu dilimi henüz uygulanmamış bir öneri olarak
kaydetmişti. CMM-1 artık ayrı bir kısmi tarama geçişi olarak uygulanmıştır.
Bu, modelin tamamlandığı veya fiziksel olarak doğrulandığı anlamına gelmez.
CMM-1 aerodinamik menteşe momentini hâlâ yayınlamaz. Düzlemsel izdüşüm yük
önkoşulu uygulanmış, bağımsız olarak incelenmiş ve PR #74 ile birleşmiştir:
[CMM-2 planar aero-load prerequisite](cmm2_planar_aero_load_prerequisite.md).
Bu tarama adaptörüdür. Kabul edilen parça, mevcut izdüşüm katlanır-BEM kuvvet
alanının eşlenik tarama genelleştirilmiş yüklerine yazılım sözleşmesidir.
CMM-2'nin izole eşlenik yük dinamiği kodlanmıştır ve bağımsız inceleme altındadır.
Kabul edilmiş değildir. Üretim FoldableBEM kaynak bağlaması, mühürlü istek ve
pano yoktur. CMM-2 fiziksel olarak doğrulanmamıştır. Sözleşme:
[CMM-2 PR-A](cmm2_coupled_transient_contract.md). Ayrıntı:
[CMM-1 sözleşmesi](cmm1_partial_coupled_transient.md) ve ADR-005.
Faz 4 sayısal kanıtı
[CMM-1 numerical verification](cmm1_numerical_verification.md)
belgesindedir. İlan edilen CMM-1 tarama modeli için sayısal doğrulama
tamamdır ve PR #72 ile birleşmiştir. Bu, fiziksel doğrulama değildir.
Fiziksel yeterlilik false kalır. PR-06C çözülmemiştir. GEOM kapısı
yükseltilmez. Kalibrasyon ve deneysel doğrulama yoktur. CMM-2 kabul edilmiş
değildir; üretim aerodinamik kaynak bağlaması yoktur. PY-06D2 uygun ölçüm olmadan kapalı kalır. Robust optimizasyon
erken kalır. Faz 5, Faz 6 ve Faz 7 uygulanmış değildir.

**Coupled Aero–Motor–Mechanism Model**, PR #70 sırasında önerilen sonraki model
dilimiydi. O belgede nihai denklem yazılmadı. CMM-1, review edilmiş kısmi
tarama sözleşmesinin sınırlı uygulamasıdır.

Ayrı ayrı duran parçalar korunur: rotor BEM, katlanır geometri projeksiyonu,
PR-07 motor dengesi, öngörülen tahrikli PY-05 ve GEOM tarama/kanıt zinciri.
CMM-1 bunları değiştirmez. Ortak çevrim yalnız CMM-1'in ilan ettiği ekran
sınırları içindedir: donmuş katlanma aerodinamiği, sabit gaz, senkron palalar,
100 rpm yazılım tabanı ve ilk temas terminali. Kabul edilen her RK45 yoğun
aralığı, sürekli kuartiği üzerinde gerçek eksende denetlenir. Sınır eşitliği
yalnız aynı izole durağan kökle kabul edilir. Kök kimliği, kök veya aralık
sınıflaması kanıtlanamazsa denetim kapalı başarısız olur. v1, domen
çıkışından sonra devam etmez ve uydurma bir `model_domain_exit` noktası
yayımlamaz.

<a id="sirali-teknik-fazlar"></a>

## Sıralı teknik fazlar

Her faz tek bir PR olmak zorunda değildir.

| Faz | İçerik | Durum |
| --- | --- | --- |
| 0 | Birleşmiş taban. GEOM #67–#69 birleşti. BEM, motor dengesi ve PY-05 ayrı ayrı var | implemented |
| 1 | Bu yol haritası hizalaması | docs reconciliation, bu PR |
| 2 | Kısmi bağlaşık tarama sözleşmesi. Uygulama bu fazın kendisi değildir | reviewed; ADR-005 records the accepted CMM-1 scope |
| 3 | CMM-1 kısmi bağlaşık tarama geçişi. Aerodinamik menteşe momenti, fiziksel yeterlilik, GEOM `True` ve kalibrasyon yoktur | implemented screening boundary |
| 4 | Bağımsız sayısal doğrulama: analitik sınır halleri, kalıntı, yakınsama/duyarlılık ve ayrık modellerle regresyon | numerical verification complete for the declared CMM-1 screening model; merged in PR #72 |
| 5 | PY-06D2 kalibrasyonu. Yalnız uygun ve tanımlanabilir ölçüm varken | blocked on evidence |
| 6 | Fiziksel korelasyon, CFD, FEA ve deney | blocked on evidence |
| 7 | Robust sistem optimizasyonu. Yalnız uygun biçimde doğrulanmış modeller üzerinde | deferred |

Faz 5, ölçüm yokken Faz 2'nin önüne geçmez. Faz 7; model bağlaşımı, aerodinamik
doğrulama, parametre kestirimi ve yapısal/deneysel kanıttan önce gelmez.
PY-04 sonlu ızgara yararlı yazılım altyapısıdır, nihai tasarım optimizasyonu
değildir.

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
   **PY-03 — uygulandı:** doğrulanmış polar bundle'ıyla aktif taslak UI analizi;
   açık buton, sınırlı hesap ve girdi değişiminde eski sonucu kaldırma aktiftir.
   [Veri sözleşmesi ve plan](py03_active_design_polar_ui.md).
   Eksik polar yerine otomatik proxy veya clamp yoktur.
3. **PY-04A / PR-11A — ilk dilim uygulandı:** sonlu deterministik ızgara, aktif taslak
   chord/twist BEM taraması ve açık UI butonu; analitik testler, aday/annulus bütçesi,
   başarısızlık kaydı ve girdi kimliği. Bilinmeyen kısıtlar aday seçtirmez; fiziksel
   optimum veya tamamlanmış robust optimizasyon değildir.
   [Sözleşmeler ve geriye dönük review](py04_deterministic_design_search.md).
4. **PY-05A — uygulandı:** açık SI girdili tek rijit-cisim düzlemsel menteşe,
   parçalı doğrusal RPM/menteşe torku, RPM düğümlerinde RK45 yeniden başlatma ve ilk
   durdurucu temasında temas öncesi hızla terminal olay. Kaynak/uygulama hash'li JSON
   servisi ve ayrı çalıştırma butonlu mekanizma çalışma alanı eklendi; tüm çıktılar
   `physical_qualification=false`. Yang literatür değerleri yalnız türetilmiş modal
   örnektir, prototip ölçümü değildir. [PY-05A sınırı](py05_mechanism_transient_plan.md).
   **PY-05B — PR #53 içinde uygulandı:** hash ile bağlı aktif taslak,
   açık kaynaklı tek uç kütle dağılımı, düzenlileştirilmiş sürtünme ve terminal
   temas sözleşmesi. Adım içi temas kaçırma ve UI sonuç geçersizleştirme hataları
   TDD ile giderildi. [Tamamlanma sınırı ve doğrulama](py05_completion.md).
   **PY-06A — PR #54 ile birleştirildi:** manifest/ham-veri/özet kimlikli
   eş-koşul sabit–katlanır karşılaştırma ve korelasyonlu belirsizlik yayılımı.
   **PY-06B1 — PR #55 ile birleştirildi:** strict JSON girişli, kaynak ve uygulama hash'li,
   stale-request korumalı rapor servisi. UI ve fiziksel korelasyon bu küçük dilime
   dahil değildir. [PY-06 planı ve kapıları](py06_calibration_uncertainty_plan.md).
   **PY-06C — PR #56 ile birleştirildi:** tek PR-10 çalışma noktasını SHA-bağlı PR-07 sonucu
   ve bağımsız motor dinamometre/verim kanıtıyla karşılaştıran fail-closed çekirdek;
   rotor-tork semantiği, motor-terminal güç sınırı, geometri/ileri-hız ve elektriksel
   koşul eşlemesi ile kanonik dinamometre özet kimliği zorunludur.
   **PY-06D1 — uygulandı:** kaynak-beyanlı ölçüm/devir sözleşmesi, ölçüm zamanlarında
   RK45 yoğun çıktı karşılaştırması, eksik temas kapsamı ve fiziksel run/hash bazlı
   eğitim–holdout ayrımı. Gerçek ölçüm henüz yok; kalibrasyon yapılmadı.
   [Kapsam, testler ve veri gereksinimleri](py06d1_mechanism_observation.md).
   Statik tutunma, çarpışma tepkisi ve BEM/motor tam bağlaşımı tamamlandı iddiası
   yoktur; PR #3 ayrıdır. CI fiziksel doğrulama kapılarını açmaz.

Bu sıra, veri bekleyen fiziksel PR-06C–PR-10 kapılarının açıldığını göstermez.

### 2026-09-09 Astra hedef–roadmap değerlendirmesi

Yüklenen TÜBİTAK önerisi yeniden karşılaştırıldı: 250 mm açık / 140 mm katlı çap,
7100 rpm'de aynı çaplı referansa göre en az %85 itki, profil/geometri iyileştirmesi,
geçiş dinamiği ve PA-CF yapısal kanıtı birlikte hedefleniyor. Önerideki %70 ön test
beyanı kalibre ham veri içermediğinden PY-06'ya ölçüm olarak taşınmadı. 500/1000 mm
ölçekler sonraki araştırmadır. MATLAB işleri Python'da yürütülür; baskı yönü bu
yazılım hattının kapsamında değildir. Kaynak PDF SHA-256:
`e16db4182fe5171dc7d06bb05c74875e0e80fac726cd8be52df366c29a7e1541`.

| Öncelik | Şimdi yapılabilecek iş | Karar kapısı |
| --- | --- | --- |
| Bu artım: PY-06D1 | Ölçüm geçmişlerini mevcut PY-05 ile karşılaştır, kaynak ve bağımsız run ayrımını koru | Analitik/sentetik testler; fiziksel yeterlilik false; gerçek veri bekleniyor |
| **GEOM-01 — uygulandı; kanıt katmanları PR #67–#69** | Menteşe/katlı-açı taraması. PR #67 adaya bağlı GEOM-04 kanıtını doğrular. PR #68 uygun ihlalde kapıyı yalnız `False` yapabilir. PR #69 tanı üretir, kapı atamaz | Kanonik 100 mm menteşe başarısız; tam 180° için 143 mm merkez-hat alt sınırı durur. `preconditions_satisfied` seçim veya `True` değildir. Yüzey hazırlığı paylaşılan menteşe nedeniyle blokludur |
| **GEOM-02 — birleştirildi, PR #59/#60** | Kaynak-bağlı istasyon JSON içe aktarma, tablo düzenleme, açık uygula/yeniden bağla ve ortak etkin taslak | Fiziksel ölçüler ölçeklenmez; eksik kapsam görünür; kaynak/hash ve sonuç geçerliliği korunur; tam kapsam yüzey teması doğrulaması değildir |
| **GEOM-03 — uygulandı** | Açık bağlantı bantları, korunmuş üçgen yüzeylerde sürekli BVH açıklık sınırları, göbek zarfı/örnek ihlal kayıtları ve açı aralığı arayüzü | Senkron düzlemsel hareket; çözülemeyen aralıklar unknown; dışlanan bağlantı ve tam pervane/katı cisim çarpışmasızlığı doğrulanmaz |
| **[GEOM-04 — uygulandı](geom04_surface_hardware.md); tüketim PR #67–#69** | Kesin üçgen mesafesi, sürekli yol inceltmesi, sonlu göbek/dışbükey donanım. Kanıt ekleme, negatif politika ve pozitif hazırlık tanısı ayrı katmanlardır | 04A: PR #62; B/C/D: PR #63; kanıt PR #67; negatif politika PR #68; readiness PR #69. Tam pervane veya fiziksel yeterlilik üretilmez. Özellik genişletmesi duraklatıldı |
| Paralel aerodinamik bağımlılık | Beş profilin çalışma zarfında temsili polar/rotor nitelemesi ve mevcut chord–twist taramasının kanıtı | PR-06C başarısızlığı görünür; 254 mm referans 250 mm proje ölçümü yerine geçmez |
| Veri gelince PY-06D2 | Önceden dondurulmuş fiziksel run ayrımıyla tanımlanabilir parametre/parametre bileşimi kestirimi | Bağımsız kütle/atalet ölçümü, sınırlar, uyarım yeterliliği, identifiability ve holdout; yalnız optimizasyon yakınsaması yetmez |
| PY-06E/F ve UI-05B | Aynı tasarım revizyonunda itki/güç, geçiş ve PA-CF kanıtını birleştir; kararlı sözleşmeleri UI'da kullan | Birim/yük/koşul/revizyon eşliği, belirsizlik, kaynak kimliği ve stale-state kontrolü |

PY-06D2 gerçek ve tanımlanabilir veri yokken otomatik bir sonraki iş değildir.
Geometri tarama zinciri de otomatik olarak `True` promosyonuna veya bağlaşık
açılma modeline ilerlemiş sayılmaz. Geometrik uyumsuzluk ve aerodinamik doğruluk,
kalibrasyon veya arayüz tamamlanmasıyla çözülmüş sayılmaz. Sonraki matematiksel
dilim yukarıdaki bağlaşık model sözleşmesidir; o sözleşme bu tablonun tarihi
değildir.
[GEOM-01 uygulaması](geom01_feasibility_plan.md) fizik modelini büyütmeden mevcut
denetim ve arama bütçelerini kullanır; yeni topoloji ancak açık geometri girdisi ve
ayrı kabul testleriyle eklenir.

[GEOM-02 sözleşmesi ve arayüzü](geom02_station_contract.md) mevcut kanat istasyonlarını
otomatik tamamlamadan düzenler. Önizleme, etkin istasyon tablosu, TOML, GEOM-01 ve
BEM hazırlığı aynı taslaktan beslenir. İstasyon düzenleme, geçersiz dosya veya
başarısız uygulama eski geometri/analiz sonuçlarını kaldırır. Kütle/atalet ve polar
uygunluğu yeni geometri için yeniden doğrulanır; geometri girişi bu kanıtları üretmez.

[GEOM-03 yüzey denetimi](geom03_surface_clearance.md) yalnız etkin taslağın açık
mesh yüzeylerine uygulanır; GEOM-01 taramasındaki farklı adaylara otomatik
başarı aktarılmaz. RPM=0 geometri kontrolünü engellemez; BEM koşulları korunur.
Arayüzde sayfa değişimi etkin istasyon kaynağını ve bekleyen düzenlemeleri korur.

**Literatür ölçüm hattı — 2026-09-09:** SciSpace/Consensus taramaları ve birincil
yayın/veri deposu denetimiyle [geçici ölçüm kayıt dizini](literature_measurement_registry.md)
eklendi. UIUC'nin mevcut 254 mm deneysel katsayı fixture'ı yeniden kullanılır.
Yang'ın beş deneylik modal tablosu Python ile sistem/tek-menteşe sönümü ayrımında
incelenir; ivme verisi açı geçmişi gibi sunulmaz. 30 inç katlanan pervane kampanyası
ölçek dışı kaynak olarak tutulur. Ham Mendeley dosyaları alınamadığından otomatik
model kalibrasyonu açılmaz. Mühendislerin verileri geldiğinde ayrı ham-veri/run/
kalibrasyon kimlikleriyle eklenir; literatür kaynak kimlikleri değiştirilmez.

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

PR-10 karar zarfı PY-06A için v2'ye yükseltilmiş; manifest SHA-256 ile her run'ın
ham-veri, tasarım, tarih ve özet kimliği kalıcı hale getirilmiştir. Test-stand
manifest şeması v1 kalır. Eski karar nesneleri Python çağrıları açısından
oluşturulabilir olsa da kimlik alanları olmadan PY-06A karşılaştırmasına alınmaz.

### PR-11 — robust çok amaçlı optimizasyon

**PR-11A yazılım altyapısının ilk dilimi (PY-04A)** sınırlı deterministik tarama,
aktif taslak BEM adaptörü ve UI ile uygulandı. Daha geniş/adaptif/Pareto arama
yöntemleri henüz uygulanmadı. **PR-11B fiziksel tasarım
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
| 8 | PY-06 karşılaştırma | A/B1/C sırasıyla PR #54/#55/#56 ile birleştirildi; D1 gözlem karşılaştırması uygulandı; D2 gerçek veri ve tanımlanabilirlik kapısını bekliyor |
| 9 | PR-11/12 optimizasyon ve sürüm | Robust Pareto kararı ve temiz yeniden üretim. Doğrulanmış modelden önce nihai tasarım optimizasyonu değildir |

Tarihli PR-06–PR-12 sırası korunur. Güncel bilimsel sıra bu tablonun yerine
[sıralı teknik fazlar](#sirali-teknik-fazlar) bölümündedir. UI-05B arayüz
sırasını değiştirmez.

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
Bu aerodinamik fiziksel kapı açık kalır. Ondan ayrı olarak geometri tarama
zinciri PR #67–#69 ile duraklatılmıştır ve sonraki model dilimi, henüz
yazılmamış bağlaşık aero–motor–mekanizma sözleşmesidir. PY-06D2 ve robust
optimizasyon veri ve doğrulama kapılarının önüne alınmaz.
