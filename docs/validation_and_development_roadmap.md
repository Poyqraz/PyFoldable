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

2026-11-05 tarihli [CAD gerektirmeyen kullanıcı akışı, kod tabanlı açıklar ve ilk
uygulama dilimi](#2026-11-05-cad-free-user-flow--code-audit-and-next-slice), aşağıdaki
tarihsel planların bugünkü ürün önceliğini günceller; yeni bir yol haritası değildir.

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
CMM-1 ilan edilen tarama modeli için uygulanmış ve sayısal olarak
doğrulanmıştır. Düzlemsel aerodinamik yük önkoşulu uygulanmış ve kabul
edilmiştir. CMM-2 PR-A izole eşlenik yük dinamiği uygulanmış, bağımsız olarak
incelenmiş ve PR #76 ile birleşmiştir. ADR-007 yalnız bu tarama dinamiği
yazılım sözleşmesi için kabul edilmiştir. Son incelenen head
`da4dcb2589c1a58f1cb97ceb285968a66036e97f`, birleştirme commit'i
`63c75346c09280ed4572784aca1a6f1014463744` şeklindedir. Sözleşme:
[CMM-2 PR-A](cmm2_coupled_transient_contract.md). CMM-2 PR-B kaynak bağlı
tarama servisi uygulanmış, bağımsız çekişmeli incelemeden geçmiş ve PR #78
ile birleşmiştir. ADR-008 yalnız bu yazılım entegrasyonu için kabul
edilmiştir. Son incelenen head
`653526bca79160a2ec41e2e2ebea802dd8b39d1c`, birleştirme commit'i
`6f72b28273b38334851df570b1c4cccbbc6b5140` şeklindedir. Ayrıntı:
[CMM-2 source-bound production binding](cmm2_source_bound_production_binding.md).
CMM-2 PR-C bağımsız sayısal doğrulamadır. Doğrulama sözleşmesi
`613072514f793f2a1bc65704f9158f536210707f` head'inde bağımsız olarak
incelenmiştir. Dar C2V-02 ilk ivme aritmetik değişikliği
`b840ec55b4d1dd57197b97e91e1a48a7fbe7da0d` teknik head'inde ayrı salt okunur
otomatik incelemede APPROVE almıştır. Bu, gönderilmiş bir GitHub incelemesi
değildir. Durum: REVIEWED / FROZEN FOR IMPLEMENTATION WITH C2V-02 ARITHMETIC
AMENDMENT. Değişiklik yalnız ilk ivme muhasebesini değiştirir. Olağan Q2
gerekli kalır. Yörünge kabul politikası hiç yeniden açılmamıştır. Bu
değiştirilmiş sözleşmeye karşı uygulama başlamamıştır:
[CMM-2 PR-C numerical verification contract](cmm2_numerical_verification_contract.md).
PR #81 üzerindeki doğrulama/kanıt denemesi dondurulmuş C2V-02/C2V-03 yörünge
kapılarında BLOCKED durumdadır; birleştirilmemiştir ve o yörünge sonuçları
FAIL kalır. Bağımsız sayısal doğrulama kabul edilmemiştir. Kabul edilmiş
bağımsız sayısal kanıt yoktur. PR-C
doğrulama kilometre taşı tamamlanmış değildir. Pano A/B/C sırasının dışındadır. Ayrıntı:
[CMM-1 sözleşmesi](cmm1_partial_coupled_transient.md) ve ADR-005.
Faz 4 sayısal kanıtı
[CMM-1 numerical verification](cmm1_numerical_verification.md)
belgesindedir. İlan edilen CMM-1 tarama modeli için sayısal doğrulama
tamamdır ve PR #72 ile birleşmiştir. Bu, fiziksel doğrulama değildir.
Fiziksel yeterlilik false kalır. PR-06C çözülmemiştir. GEOM kapısı
yükseltilmez. Kalibrasyon ve deneysel doğrulama yoktur. CMM-2 fiziksel
olarak doğrulanmamıştır. Kaynak bağlı tarama bağlaması ve mühürlü rapor
PR #78 ile birleşmiştir; bu fiziksel yeterlilik değildir. PR-C bağımsız
sayısal doğrulama uygulanmamıştır. PY-06D2 uygun ölçüm olmadan kapalı kalır; PR-A
tamamlanması PY-06D2'yi çözmez. Robust optimizasyon
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

**2026-10-03 kapsam açıklaması:** Aşağıdaki SolidWorks/ANSYS değişim planı dış
doğrulama yolunun tarihsel kapsamıdır; PyFoldable kullanımının evrensel CAD/STEP
önkoşulu değildir. Birincil ürün yolu iç tanımlı/üretilmiş parametrik pal ve bağlantı
geometrisidir. Bu açıklama PR-09'un gerçek yapısal kanıt sözleşmesini değiştirmez.

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

**Ayrı tasarım önerisi — PROPOSED / NOT IMPLEMENTED:**
[Dayanımı gözeten radyal menteşe konumu değerlendirmesi](strength_aware_radial_hinge_assessment_proposal.md)
250 mm proje tabanında kimliği belirli tek pal tasarımı ve tek beyan edilmiş bağlantı için sınırlı,
adaya bağlı geometri/kütle/aerodinamik/yük-vakası/FEA kanıt dosyası önerir.
İlk geometri karşılaştırması aynı ana palın iki menteşe konumunda kesilip yeniden
birleştirilmiş açık geometrisini özgün pal ile eşler; radyal kesit/twist eşleşmesi,
dönüşümler ve bağlantı bölgesi farkları açıkça kaydedilir. Ana palın varsayılan
optimumluğu yalnız beyan edilmiş çalışma koşuluna bağlı çalışma varsayımıdır.
Dar [istasyon karşılaştırma raporu](parent_blade_station_comparison.md) ayrı
birleştirilmiş uygulama dilimidir: kaynak bağlı açık eşleme ve sayısal farklar raporlanır;
tam 3B yüzey, bağlantı boşluğu/dayanımı veya güvenli aday kanıtı değildir.
Geniş tasarım önerisi PROPOSED / NOT IMPLEMENTED olarak kalır.
Birincil yol dış CAD/STEP gerektirmeyen iç parametrik tasarımdır; dış referans/içe
aktarım, üretim CAD dışa aktarımı ve dış doğrulama isteğe bağlı yollardır. Kimliği
belirli üretilmiş tasarım ilk dosyayı sağlayabilir; beyan edilmiş geometri üretilmiş
fiziksel numune/as-built kanıtı değildir. [Ayrı dar üretici uygulaması](parent_blade_station_generation.md) yeni Draft PR
içinde iki beyan edilmiş menteşe konumunda tamamlayıcı istasyon paketlerini tek
sabit iç ana istasyon tablosundan doğrudan kopyalayıp rapora besler.
Eksik menteşe/uç satırları boşluk olarak, yetersiz çocuk satırları tanı olarak kalır;
interpolasyon, twist sıfırlama veya çocuk ölçekleme yapılmaz. Eksik/uyumsuz geometri
açık kalır; tam katı, boşluk veya dayanım kanıtı türetilmez.
[Yerel PE0 kaynak-geometri raporu](local_apc_pe0_geometry_reporting.md) ayrı Draft
uygulamada tüm kaynak satır/sütunlarını ve nominal/footer/son-istasyon yarıçaplarını
korur; iki kesim aynı saklı satırları kopyalar. Karma profil ve bilinmeyen geçiş
geometrisi karşılaştırması desteklenmiş sayılmaz. Gerçek APC 13x5.5MR dosyası yerel
gösterim için bulunamadı; sentetik yazılım testi üretici sonucu yerine geçmez.
BEM, dayanım, optimum menteşe veya fiziksel nitelik iddiası yoktur.
13 inç ayrı senaryodur. Parametrik tasarım, yönsel PA-CF kuponları ve deney hazırlığı CMM-2
doğrulamasıyla paralel ilerleyebilir; bu öneri çözüm çalıştırmaz, PR-09/GEOM
kapılarını değiştirmez ve güvenli aday seçimi veya fiziksel nitelik vermez.

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

2026-10-03 açıklaması: iç parametrik geometri birincil ürün yoludur; aşağıdaki
SolidWorks rolü isteğe bağlı dış referans/üretim/değişim yoludur. Dış dosya
bulunmaması istasyon raporlama veya tanımlı tasarım hazırlığını engellemez;
bu durum fiziksel doğrulama kapılarını kaldırmaz.

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

## 2026-10-01 proposed numerical-feasibility amendment

The [numerical-feasibility proposal](cmm2_numerical_feasibility_amendment.md)
is PROPOSED / NOT FROZEN / NOT IMPLEMENTED. Main still ships CMM-2 RK45/v1;
Draft PR #84 Radau/v2 remains BLOCKED. Proposed C2V09-28 reaches real BEM
but fails mapper span coverage and is not selectable. Kabul edilmiş bağımsız
sayısal kanıt yoktur. Review, fixture-feasibility resolution and separate
freeze/implementation authorization precede new trajectories. Draft PR #81
remains BLOCKED; ADR-009 is not created/accepted; physical qualification
remains false. Historical phase and acceptance records are unchanged.

Prospective append-only [C2V09-29 declaration](cmm2_c2v09_candidate29_proposal.md) retains candidate28
and its mapper rejection, adding a first-party synthetic constant terminal
station under proposed selector v3 (00…27,28,29). Status remains **PROPOSED /
NOT FROZEN / NOT IMPLEMENTED**. Committed-declaration review precedes any
initial-only source/preflight measurement; no trajectory, freeze or acceptance
follows. Main RK45/v1 and unmerged PR81/84 identities are unchanged.

After separate committed-declaration review, [candidate29 initial preflight](cmm2_c2v09_candidate29_initial_preflight.md)
measured source/Q2/detectability/Q4 checks but retained a literal partition
predicate failure. Candidate29 remains BLOCKED / NOT SELECTED; candidate28
mapper rejection is preserved. No proposed-candidate trajectory was run,
no v2 seal exists, and this is not accepted independent numerical evidence.

A subsequent [prospective partition-policy declaration](cmm2_c2v09_partition_policy_proposal.md)
uses unchanged candidate29 and a whole stored-scale angle neighborhood. It
preserves literal v1 FAIL/raw zeros and every historical capture; no structural
alias is relabelled as passing v1. The separately versioned proposal and Q4
successor conjunction are **PROPOSED / NOT FROZEN / NOT IMPLEMENTED**.
Committed-declaration review precedes any new initial-only assessment; no
trajectory, ordered selection, v2 seal or acceptance is authorized.

The [prospective partition initial assessment](cmm2_c2v09_partition_initial_assessment.md)
keeps literal v1 FAIL and unchanged candidate29. Conditional source algebra
and conjunctive Q4 replay do not close the unresolved actual whole-neighborhood
runtime/source proof; prospective result BLOCKED / NOT SELECTED. No trajectories,
ordered selection, v2 seal, freeze or accepted independent numerical evidence.

## 2026-10-02 cumulative feasibility-design closure — design frozen

The [cumulative implementation subsection](cmm2_numerical_feasibility_amendment.md#7-cumulative-implementation-authority-and-live-eligibility)
is **REVIEWED / FROZEN FOR IMPLEMENTATION — CMM-2 NUMERICAL FEASIBILITY AMENDMENT**,
NOT IMPLEMENTED. Technical reviewed HEAD `fd55fa97676c84c896511765e94561a706252239`
received independent APPROVE FOR CONTRACT FREEZE and passed its documentation
checks and push/PR baseline CI before the separate status-only closure; fresh
closure-head CI is still required. It binds the unchanged timestamp
proposal, append-only selector00…27,28,29 and partition v2 narrowed by scope v3,
with mandatory **live** certificate/runtime eligibility before future successful
selection and separate-v2 sealing. Archived replay or baseline CI cannot supply
that eligibility. Earlier declarations/results above remain historical; design
freeze does not establish selection, trajectories or PR-C verification.
Candidate29 NOT SELECTED; literal v1 FAIL and historical v2 BLOCKED preserved.
Kabul edilmiş bağımsız sayısal kanıt yoktur. Main RK45/v1, pending Q5/runtime/
minimum-SciPy work and qualification boundaries remain; no implementation,
ADR-009 acceptance or physical qualification follows.


## 2026-10-03 CAD-free geometry workstream update — proposal only

PR #92 merged at `988a8524c4a8814eeee54071a86b6da67f0b150b`: bounded local PE0
source-retention/reporting is implemented, including the subsequently supplied
genuine-source receipt. Earlier Draft/unavailable statements are historical; this
update supersedes their current-status meaning without rewriting those records.
Mixed-profile coordinates/surfaces, joint strength and optimum-hinge selection
remain unestablished.

The separate [mixed-profile parent geometry proposal](generated_mixed_profile_parent_geometry_contract.md)
is **PROPOSED / NOT IMPLEMENTED**. Next bounded future scope: an identified
continuous internal section model, explicitly declared blend and thickness/frame
choices, complementary restrictions at two hinges and deterministic geometry
reports. Coordinate rights/identity and placement assumptions precede implementation;
no source/surface/BEM/FEA/trajectory execution or freeze is authorized by this
documentation proposal. External CAD/STEP is optional. 13-inch source conventions
remain separate from the 250 mm project baseline. Broader strength evidence and
physical gates remain unchanged; no ADR-009 acceptance or qualification promotion.

## 2026-11-05 CAD-free user flow — code audit and next slice

This is the current product integration priority within this roadmap. Source:
the owner's 2026-11-05 message reaffirming the normal CAD-free workflow. A separate
dated clarification attachment was not available to this execution; no attachment
reading or digest is claimed. The explicit message supplies the requirements here.
No DOCX intake or missing-document inventory is repeated.

Audited main: `022b466303c59b8c0adb02f935f9c2f065b0e2b5`, tree
`b8f943b0d37b2179f71aac47aa2a1cee57df594f`. Relevant live Draft/open/unmerged
heads: #103 `fc545b1584d679951fd28db0767cd71c790a7b06` (tree
`dd399acd98c87d45845f6976eea7c24da81a4e7c`), #104
`8ba282e49ecf3c7ac96ada100c2721fa28a5803f` (tree
`b354cc4318e5b864ff5886710cce81a3f5f06a10`), #105
`86d28805a469a495746f8a9cf5da344ffe0162e6` (tree
`6b8d532a7291dd903114c2c53c1384cdbcc5c10f`). They are not changed here.
Draft #96 (`19df53d080e1f74edea8f12aa84de79b3fc6ba17`) is a separate earlier
roadmap reconciliation; its prose is not treated as merged implementation.

### Required selections mapped to actual code

Paths below are on audited main unless explicitly marked Draft. Functions/tests
were read, not executed as a new numerical study. Widget ranges are input bounds,
not proof of an aerodynamically or mechanically supported design envelope.

| Requirement | Implemented source / current behavior | Specific remaining integration |
| --- | --- | --- |
| All five selectable profiles | [profile_catalog.py](../pyfoldable/core/profile_catalog.py)::`PROJECT_AIRFOIL_IDS`, `load_project_airfoil`; [dashboard](../apps/pyfoldable_dashboard.py)::`_render_design_geometry` supplies NACA0012, NACA2412, NACA23012, NACA4415, NACA63-412 and validates coordinate identities | Keep all five through generated geometry, provider lookup and saved results. Catalog coordinates do not supply matching polars. |
| Dimensions and explicit chord/twist | Dashboard diameter/hub/blade-count/chord/twist controls → [design_draft.py](../pyfoldable/application/design_draft.py)::`build_design_draft`, `_build_model`; parametrically scales the existing source stations once; `_station_editor` also works without upload | Expose a versioned blade-family/template identity with its station law, root datum, units and supported bounds. Current UI has one canonical seed, not a family selector. Profile plus diameter must never invent chord/twist. |
| Internally generated analysis geometry | Draft TOML is parsed back into `PropellerDesign`; preview uses those same stations. [parent_blade_generator.py](../pyfoldable/application/parent_blade_generator.py)::`generate_parent_blade_cuts` copies one immutable parent into two complementary cut reports | Connect family selection, parent/cut outputs and analysis request identity in the UI. Sparse station gaps are explicit; do not fabricate endpoints or reset distal chord/twist. |
| Generic mixed-profile sections | [mixed_profile_parent_geometry.py](../pyfoldable/application/mixed_profile_parent_geometry.py)::`evaluate_mixed_profile_parent`, `render_mixed_profile_table`, local CLI are implemented; [implementation scope](generic_mixed_profile_geometry_implementation.md) | Service consumes explicit endpoint/scalar/model DTOs, not catalog selections. Fixed supported hinge literals/model/frame and undefined actual joint modifications remain. No general catalog adapter, mesh/solid or BEM path for blended sections; endpoint polars cannot stand in for a new blended section. Historical proposal-only wording does not negate this bounded implementation. |
| Hub, hinge and folding | Draft exposes hub/hinge radii and preview angle; source TOML declares axis, offsets and stops. [folding_mechanism.py](../pyfoldable/application/folding_mechanism.py)::`audit_mechanism_geometry` and [geometry_search.py](../pyfoldable/application/geometry_search.py)::`prepare_geometry_search` provide bounded diagnostics/candidates | Complete explicit joint-template inputs and shared-parent candidate UI are missing. Current validation is `hub < hinge < tip`; it does not enforce longer proximal. For a declared blade-root datum `r_root` and tip `R`, require `h-r_root > R-h`; do not substitute shaft origin or an arbitrary first aerodynamic station. Historical candidate records remain historical. |
| Candidate comparison | Geometry search rebinds candidate hinge geometry and caps its grid at25 evaluations; parent generator accepts exactly two cuts from the same parent | Add the owner-required input filter and common parent identity. This is a candidate table, not an optimum. Fully-open BEM without a joint-loss model cannot rank hinge locations by fabricated losses. Opposed blades keep the same parent geometry. |
| Operating conditions | Dashboard supplies RPM, forward speed, rho, mu, temperature and pressure; [design_analysis.py](../pyfoldable/application/design_analysis.py)::`_load`, `_load_open` validates the first condition | Existing BEM path requires positive RPM, nonnegative forward speed, fully-open zero-offset geometry and one uniform profile. Folded preview and nominal station kinematics are not additional solved operating cases. |
| Integrated real-provider polars | [xfoil.py](../pyfoldable/providers/xfoil.py), [polar_family_generation.py](../pyfoldable/core/polar_family_generation.py)::`PolarFamilyGenerationPlan`, [polar_config.py](../pyfoldable/core/polar_config.py)::`PolarFamilyRuntime` exist | Main UI `_render_active_polar_run` still requires uploaded polar JSON. Missing application-owned admission/materialization of matching retained provider results. Generic orchestration defaults to retries; it must not silently replace #104's reviewed one-attempt/no-retry capture policy. |
| BEM and result attribution | [polar_upload.py](../pyfoldable/application/polar_upload.py)::`inspect_polar_bundle`, `prepare_polar_run`, `run_polar_run` → `run_design_analysis`; coordinate-bound family, bounds=`error`, complete retained request/settings/result and hashes | Feed the existing boundary internally, without asking the normal user to prepare a polar file. Nominal alpha/Re/Mach ranges do not prove actual BEM query coverage; reject coverage failures without partial totals. |
| Profile result history | [Draft #103 service](https://github.com/Poyqraz/PyFoldable/blob/fc545b1584d679951fd28db0767cd71c790a7b06/pyfoldable/application/profile_bem_comparison.py)::`snapshot_success`, `snapshot_failure`, `add_record`, `comparison_document`; corresponding draft UI saves immutable per-profile records | Still unmerged, upload-driven and deliberately `BLOCKED_no_matching_real_provider_polar_bundle`. It accepts inert/caller-unqualified evidence classes; do not relabel these as validated experiments or remove its genuine-comparison block merely because wiring exists. |
| Mechanical inputs and results | Dashboard `_render_bound_mechanism` → [mechanism_binding.py](../pyfoldable/application/mechanism_binding.py)::`bind_mechanism_draft` → [mechanism_transient.py](../pyfoldable/application/mechanism_transient.py)::`prepare_bound_mechanism_transient`, `run_bound_mechanism_transient`; explicit source-bound mass/drive JSON, no CAD requirement | Replace raw JSON entry with supported joint/material/mass/drive forms/templates and consistent identity handoff. Do not infer mass/inertia/strength from profile, diameter or air density. PY-05 prescribed drive and the separate CMM-2 screening service are not an already integrated, validated aero-mechanical UI. |
| Optional external evidence | Current file widgets are station/polar/hardware/evidence inputs; normal parametric drafting needs no CAD. #105 asks for the solid actually meshed to replay an external ANSYS report | That external evidence request is not a product input gate. Internal geometry may support analysis without native CAD; solid/contact, FEA, measured validation, joint losses and forced-vibration evidence retain their own missing prerequisites. |

Reading witnesses include existing tests for draft round-trip, idle UI edits,
invalidated downloads, wrong-coordinate rejection, BEM coverage failure, immutable
parent cuts and exact generic section placement:
[draft](../tests/application/test_design_draft.py),
[active UI](../tests/ui/test_active_design_polar_ui.py),
[BEM](../tests/application/test_design_analysis.py),
[parent cuts](../tests/application/test_parent_blade_generator.py),
[generic sections](../tests/application/test_mixed_profile_parent_geometry.py),
and [Draft #103 comparison witnesses](https://github.com/Poyqraz/PyFoldable/blob/fc545b1584d679951fd28db0767cd71c790a7b06/tests/application/test_profile_bem_comparison.py).
These are inspected software witnesses, not a claim of a new test/study run here.

### First bounded implementation slice: retained-provider data to active BEM/UI

**Proposed, not implemented or authorized to execute by this audit.** The next
deliverable is one reproducible numerical user path, rather than another status
document: select a supported explicit parent template/profile/condition, resolve
matching genuine provider records internally, explicitly run existing fully-open
BEM, retain the result and its source chain. No CAD or manual polar JSON upload
is required on that path. The existing manual upload remains an optional route.

1. **Base and files.** Use a separately agreed integration base containing reviewed
   #103 snapshot/UI code **and** #104's capture/request-binding boundary; the latter
   module is absent from audited main and #103. Do not edit either current branch
   or imply either is merged. Add a small
   planned `pyfoldable/application/provider_design_analysis.py` with preparation
   and run entry points; extend `_render_active_polar_run`/profile history in
   `apps/pyfoldable_dashboard.py`. Reuse `design_draft`, catalog, `polar_upload`
   and `design_analysis`, and #103 snapshot functions. No second BEM engine.
2. **Explicit geometry inputs.** Start with the existing canonical station seed as
   one clearly named/versioned template, retaining its source SHA and schema-example
   status; do not advertise a validated blade family. Inputs include all stored
   global station radii/chords/twists, selected catalog coordinate hash, diameter,
   hub/root datum, blade count, zero-offset hinge/axis/stops, one or two bounded
   hinge candidates and the explicit condition. Validate longer proximal before
   any run. A single candidate uses the existing draft; two distinct candidates
   can use `generate_parent_blade_cuts`, whose API requires exactly two cuts.
   Cuts share one parent; generated input geometry is distinct from manufactured
   geometry. Broader family/joint forms remain later integration.
3. **Provider input and admission.** Resolve an application-owned retained capture
   bundle by selected profile/coordinate identity and its exact declared request
   plan, rather than accepting a provider name or a claimed cache hit. Verify the
   returned result and retained canonical request against the launched request,
   provider identity, full usable ledger and available raw capture receipts, using
   the [#104 binding boundary](https://github.com/Poyqraz/PyFoldable/blob/8ba282e49ecf3c7ac96ada100c2721fa28a5803f/pyfoldable/application/polar_query_feasibility.py)::`_bind_returned_result`.
   Retain executable/build observations separately;
   hashes do not attest a process image. No inferred coefficients or unverified
   partial family may enter BEM.
4. **Concrete acquisition dependency.** The already prepared experiment remains
   unchanged: NACA0012 then NACA2412, declared positive grids,37 descending angles,
   at most8 cells, one90s attempt/cell, no retry/INIT/substitution/narrowing and stop
   before the next failed-cell successor; zero BEM in that probe. Its existing
   `result-XX.json` and `capture/cell-XX-PROFILE/` outputs are prospective inputs
   to the admission service, not present results. Separate owner authorization and
   independent review precede capture, then separate authorization precedes a
   genuine BEM acceptance run. Do not add on-demand scheduling or widen that probe
   to all five profiles in this slice. All five remain selectable/tested in the
   software path; profiles/conditions without a separately declared matching
   provider bundle show their specific missing coverage, with no substitution.
5. **Outputs and behavior.** Use admitted
   `PolarGenerationResult.to_polar_table(require_complete=True)` to materialize a complete internal
   `active_design_polar_bundle` with the selected coordinate identity, then reuse
   `prepare_polar_run`/`run_polar_run`. Keep provider-result/capture/plan references
   in the new wrapper artifact, alongside template/parent/candidate/draft/polar/
   condition/settings/source identities and runtime. Retain T/Q/shaft power and
   radial/query audit only on actual BEM success; append an immutable #103 record.
   Retain `station_span` and root/tip gaps; do not turn partial radial coverage
   into a complete physical-blade load claim.
   Preserve lower-layer unqualified classifications and the existing genuine-
   comparison block; actual provider origin is a separate source fact. One
   successful real-provider/BEM case is not a genuine two-profile comparison.
6. **Failures.** Preparation is side-effect free. Missing template inputs, invalid
   segment lengths, unsupported pose/offset/condition, profile/plan mismatch,
   unreadable/incomplete captures or missing provider coverage block before BEM.
   BEM coverage/nonconvergence fails without partial totals or the previous success
   remaining active. Selection/input changes invalidate active output/downloads;
   prior snapshots retain their original identities. No automatic provider launch,
   retry, INIT, clamp, proxy, extrapolation or policy narrowing. Mechanical results
   remain explicitly unavailable when their separate inputs are absent.

### Acceptance evidence and stopping point

- **Software integration:** planned `tests/application/test_provider_design_analysis.py`
  and the existing active-profile UI tests must cover all five coordinate identities,
  no-upload drafting, source-preserving template/candidate generation, longer-
  proximal rejection, no implicit solve on edits, complete receipt admission,
  stale/foreign/partial input rejection, BEM-not-called on admission failure, retained
  settings/provenance and immutable success/failure exports. Use inert seams; label
  their coefficients/results as software fixtures, never genuine comparison data.
- **Working numerical user-flow milestone:** after separate authorization, retain
  a complete attributable real-provider bundle and a successful existing BEM run
  for a declared supported case, with matching input/request/result hashes, raw
  capture references, actual query coverage and repeatable BEM replay from that
  retained bundle in its recorded environment; this does not mean retrying the
  provider probe. The UI must display that source-bound result without CAD or manual
  polar upload. Preparation, mocks or an old Re200000 qualification cannot satisfy
  this milestone. If provider/BEM fails, retain the failure and mark the numerical
  milestone incomplete; do not invent a narrower successful case.
- **Separate comparison/physics:** matched real results for distinct profiles,
  controlled conditions/geometry/policies and independent review are still needed
  for a genuine comparison. Joint loss/load transfer, clearance, material strength,
  forced vibration, controlled deployment and optimum design are not supplied by
  this first slice. Keep all five profiles, `qualified_winner=None` and
  `physical_qualification=false`; no scientific gate is promoted.

The 2026-11-05 XFOIL preflight archive remains unchanged (SHA-256
`058a91997442d42df0859a373df1bbb00005fcd882c86616ef5707590f45331a`), unexecuted and
under separate review. This documentation-only reconciliation runs no new
provider/BEM/CFD/FEA/clearance/transient engineering study and does not merge a PR.
