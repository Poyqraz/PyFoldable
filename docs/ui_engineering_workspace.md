# PyFoldable Engineering Workspace

## Amaç

Bu çalışma hattı, mevcut PyFoldable çekirdeğini yeniden yazmadan tasarım girdilerini,
sayısal çıktıları ve doğrulama kanıtlarını tek bir mühendislik arayüzünde birleştirir.
Arayüz fiziksel yeterlilik üretmez; yalnız sürümlü çekirdek ve kanıt dosyalarının
durumunu gösterir.

## Mimari sınır

1. `pyfoldable.core`: fizik, veri sözleşmeleri ve doğrulama kapıları.
2. `pyfoldable.application`: UI-bağımsız, tipli uygulama görünüm modelleri.
3. `apps/pyfoldable_dashboard.py`: Streamlit sunum katmanı.
4. `configs/ui/dashboard.toml`: kapıların kanıt dosyalarıyla makine-okunur bağı.

Sunum katmanı bir kapı kararını yeniden hesaplamaz. Manifestteki karar, bağlandığı
JSON kanıtıyla uyuşmazsa dashboard açılmaz. `qualified` durumu yalnız kanıt belgesinde
`passed=true` bulunduğunda kabul edilir. Kanıt yolları repo dışına çıkamaz ve her dosya
SHA-256 kimliğiyle gösterilir.

## PY-01 aktif tasarım hazırlığı

Tasarım Geometrisi ekranı, indirilen taslakla aynı geometri/ilk çalışma koşulundan
nominal istasyon Re/Mach/hücum açısı tablosu ve SHA bağlı JSON üretir. İndüksiyon
içermez, katlanmış pozun analizi değildir ve tam BEM polar kapsamını doğrulamaz.
Widget değişiminde BEM çağrılmaz. Python'daki ayrı `run_design_analysis` servisi
yalnız açıkça sağlanan polarlarda tam açık taslağı mevcut çözücüye bağlar.
PY-03 ile aynı ekranda strict JSON polar yükleme ve açık çalıştırma butonu aktiftir;
girdi/ayar değişimi veya hata eski sonucu ve indirmesini kaldırır. Eski 254 mm
benchmark değişmez. [PY-03 sözleşmesi](py03_active_design_polar_ui.md).
Ayrıntılar: [Python-first plan](python_research_execution_plan.md).

## PY-04A aktif taslak taraması

Doğrulanmış polar yüklemesinin altında ayrı açık butonla chord/twist çarpanları
taranır. Her aday aynı başlangıç taslağından mevcut BEM ile hesaplanır; en çok 25
aday ve toplam 400 annulus bütçesi vardır. Tekil analiz ve tarama sonuçları ayrı
tutulur; widget değişimleri solver çalıştırmaz ve eski tarama indirmesini kaldırır.
Aday tablosu, kısıt/hata kayıtları ve JSON indirilebilir. Bilinmeyen fiziksel/yapısal
kısıtlar nedeniyle uygun tasarım önerilmez. Minimum itki kullanıcının tarama
eşiğidir, proje için %85 tutunma doğrulaması değildir.
[Kapsam, limitler ve doğrulama](py04_deterministic_design_search.md).

## PY-02 profil kimliği

Kesit seçimi NACA0012/2412/23012/4415/63-412 kataloğuna bağlıdır. Kaynak ve
koordinat SHA-256 ekranda gösterilir; aynı koordinatlar taslak config, önizleme ve
polar kimliğinde korunur. NACA 5/6-serisi başka bir 4-haneli kesitle değiştirilmez.
Katalog hatası indirmeleri kaldırır; profil değişikliği BEM çalıştırmaz. Referans
koordinatlar üretim CAD'i veya fiziksel doğrulama değildir. Ayrıntılar:
[PY-02 kaynaklar ve sözleşmeler](py02_profile_coordinate_identity.md).

## Durum sözlüğü

| Durum | Kullanım |
| --- | --- |
| `qualified` | Tanımlı fiziksel/yazılım kabul kapısını geçen sonuç |
| `screening_only` | Mimari ve karşılaştırmalı tarama; tasarım kararı değildir |
| `pending` | Sözleşme hazır, dış girdi veya ölçüm bekleniyor |
| `failed` | Çalıştırılmış kabul kapısı başarısız |
| `blocked` | Zorunlu ön koşul eksik; ilerleme kapalı |

Durumlar yalnız renkle verilmez; Türkçe metin ve ikon birlikte kullanılır.

## Aşamalı teslim sırası

| Hat | Kapsam | Kabul kapısı |
| --- | --- | --- |
| UI-00 | Bilgi mimarisi, durum sözlüğü, görsel prototip | Nitelik sınırları görünür |
| UI-01 | Uygulama servis/görünüm modeli | Manifest–kanıt uyuşmazlığı fail-closed |
| UI-02 | Genel Bakış ve kanıt dashboard'u | Kanonik tasarım ve PR-06C–10 gerçek raporlarından okunur |
| UI-03A | Etkileşimli geometri önizlemesi | SI-bound mesh, menteşe dönüşümü ve fail-closed girdi kontrolü |
| UI-03B | Tasarım ve çalışma koşulu editörü | Birim kontrollü config round-trip ve kanonik dosyanın değişmezliği |
| UI-03C | Katlanma mekanizması review'u | Kinematik ölçü audit'i, hedef uyumu ve V02 screening moment ayrıştırması |
| UI-04 | Analiz çalıştırma ve sonuç gezgini | Ortak servis, sürümlü fixture ve arşivle byte/SHA eşdeğerliği |
| UI-05 | CFD/FEA/deney veri alımı | İlk dilim: referans/sözleşme raporu şema, birim ve SHA denetimi |
| UI-06 | Kanıt/rapor merkezi | Tekrar üretilebilir dışa aktarma |
| UI-07 | E2E, görsel regresyon ve paketleme | Temiz ortam smoke testi ve erişilebilirlik |

## Güncel artım

UI-00/01 temeli, UI-02 Genel Bakış, UI-03A geometri önizlemesi, UI-03B doğrulanmış
taslak config hattı ve UI-04 izin-listeli analiz koşumu aktiftir. Kanonik
geometri; seçili profil koordinatları, chord–twist istasyonları, kanat sayısı ve menteşe
yarıçapından etkileşimli bir 2.5D yüzeye dönüştürülür. Açık çap, göbek, menteşe,
kesit, chord/twist ölçeği ve katlanma açısı oturum içinde değiştirilebilir. Önizleme
değişiklikleri config dosyasına yazılmaz; CAD katısı, CFD/FEA ağı veya fiziksel sonuç
olarak sınıflandırılmaz. İlk çalışma koşulunun RPM, ileri hız ve atmosfer girdileri
taslak için düzenlenebilir. Uzunluk, açı, açısal hız, ileri hız, sıcaklık ve basınç
çıktı birimleri açıkça seçilir. İndirilen `*_DRAFT.toml` dosyası
`unqualified_design_draft` sınıfını, kanonik kaynak kimliğini ve SHA-256 değerini
taşır; kanonik dosyanın yanına veya üzerine yazılmaz. Her taslak indirmeye sunulmadan
önce mevcut katı config yükleyicisiyle geçici alanda tekrar okunur. Aynı SI değerleri
farklı desteklenen çıktı birimlerinde korunur. Çalışma koşulları ayrıca salt okunur
incelenebilir; 250 vakalık
açılma duyarlılığı da yalnız `screening_only` etiketiyle görüntülenir. UI-04 aynı
PR-06D hesap fonksiyonunu CLI ve Streamlit için ortak application servisinden çağırır.
Koşum yalnız açık buton eylemiyle başlar; dış solver/subprocess çalıştırmaz, sonucu
oturumda tutar ve repo, kanonik config veya `reports/` altına yazmaz. Yeni JSON'un
semantik içeriği, deterministik baytları ve SHA-256 değeri sürümlü arşiv raporuyla
eşleşmezse servis kapalı biçimde durur.

Bu ilk recipe aktif 250 mm taslağı çözmez; sabitlenmiş 254 mm UIUC APC 10×4.7
fixture'ını, 80 annulus ve analitik/non-representative proxy ile yeniden üretir.
İndirilen ayrı oturum manifesti istek/politika SHA'larını, fixture ve arşiv
provenance'ını, eşleşme kararını ve ham sonucu taşır. `session_screening_computation`,
`screening_only_until_pr06c_passes` ve
`physical_qualification=false` olarak kilitlidir. Oturum koşumu ile geçmiş sürümlü
kanıt farklı başlıklarda gösterilir. Ekranlar şu
girdilere bağlıdır:

Salt-okunur küçük tablolar Markdown, açılma taraması grafikleri doğrudan Plotly
`graph_objects` ile çizilir. Böylece karışık Anaconda ortamlarında eski PyArrow'ın
NumPy 2 ABI'siyle çakışması dashboard render yolunu düşürmez; önerilen kurulum yine
izole sanal ortam ve aynı yorumlayıcı üzerinden `python -m pip` kullanımıdır.

- `configs/designs/TIP_HINGED_250_CANONICAL.toml`
- `reports/pr06c_physical_gate.json`
- `reports/pr06d_opening_sensitivity.json`
- `reports/pr07_fully_coupled_evidence.json`
- `reports/pr06c_published_cfd_review.json`
- `reports/pr09_fea_contract_evidence.json`
- `reports/pr10_experiment_contract_evidence.json`

Mesh üreticisi Streamlit'ten bağımsızdır ve `pyfoldable.visualization.propeller_25d`
altında test edilir. Rotor düzlemi x–y, eksenel yön z'dir. Kök ve tip tarafında ayrı
menteşe kesitleri oluşturulur; aradaki açık seam sayesinde negatif katlanma açısı
yalnız dış yüzeyi deforme etmeden rijit döndürür. Göbek ve menteşe, tanımlı station
zarfını aşarsa önizleme kapalı biçimde hata verir.

Ekrandaki `Düzlemsel radyal projeksiyon çapı`, nominal uç merkez hattının menteşe
doğrultusundaki izdüşümünü sabit kök yarıçapının altına düşürmeden gösterir; PR-06D
performans hesabı değildir. `Merkez-hat zarf çapı`
ucun rotor eksenine gerçek Öklid uzaklığıdır; `Mesh zarf çapı` ise chord dahil çizilen
vertex planformunun ölçümüdür. Nominal açık çap ayrıca ölçü kılavuzu olarak çizilir.
Bu değerler birbirinin veya CFD/BEM performans çapının yerine kullanılmaz.

`Katlanma Davranışı` sayfası rijit uç-segmenti menteşe etrafında düzlemsel döndürür,
uç yolunu, seçili açı ve tam katlanma yolu göbek merkez-hat açıklıklarını gösterir.
Bu sayfanın girdileri Tasarım Geometrisi widget'larından bağımsızdır; yalnız varsayılanlar
aynı kanonik snapshot'tan gelir. Boyut tarama audit'i mevcut
kanonik veride iki blokaj üretir: yüzey station'ları göbekten başlamaz ve nominal uca
ulaşmaz; 100 mm sabit kök/menteşe yarıçapı nedeniyle teorik minimum merkez-hat zarfı
200 mm olup 140 mm gereksinimini karşılamaz. 140 mm yalnız hedef olarak korunur.
Moment grafiği SHA-256 ile sabitlenmiş `TIP_HINGED_250_V02` yazılım fixture'ından gelir;
öngörülmüş açılardaki statik ayrıştırmada θ̇ ve tip aerodinamik yükü sıfırdır. Hareket/
açılma tahmini, ANSYS gerilmesi/teması/ömrü veya fiziksel yeterlilik üretmez.

UI-05'in ilk dilimi; yayımlanmış CFD referans fixture'ı ve sürümlü
PR-09/PR-10 sözleşme raporlarını en çok 5 MiB olacak biçimde yalnız oturum belleğinde
denetler. Tür, şema, CAD/test-stand kimliği, birim, qualification veya SHA sınırı
bozulursa dosya reddedilir; repo'ya yazılmaz ve fiziksel yeterlilik üretmez. Sıradaki
kontrollü dilim gerçek ANSYS sonuç vakaları ile kalibre ham deney run/sample
bundle'larını typed çekirdeklere bağlamaktır. Henüz etkinleştirilmeyen sayfalar güvenli
placeholder'dır: analiz çalıştırmaz ve örnek mühendislik sonucu üretmez.

## Çalıştırma ve test

```bash
pip install -e ".[dev,plot,ui]"
streamlit run apps/pyfoldable_dashboard.py
pytest tests/application/test_dashboard.py tests/application/test_design_draft.py \
  tests/application/test_analysis_run.py \
  tests/visualization/test_propeller_25d.py \
  tests/ui/test_streamlit_dashboard.py -q
```

Lovable projesi yalnız UX prototipi olarak tutulur. Gerçek proje durumu ve sayısal
sonuçların tek kaynak noktası Git ile sürümlenen Python reposudur.
