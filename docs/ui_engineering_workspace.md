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
| UI-04 | Analiz çalıştırma ve sonuç gezgini | CLI ile sayısal eşdeğerlik |
| UI-05 | CFD/FEA/deney veri alımı | Mevcut sözleşmelerle şema, birim ve SHA doğrulaması |
| UI-06 | Kanıt/rapor merkezi | Tekrar üretilebilir dışa aktarma |
| UI-07 | E2E, görsel regresyon ve paketleme | Temiz ortam smoke testi ve erişilebilirlik |

## Güncel artım

UI-00/01 temeli, UI-02 Genel Bakış, UI-03A geometri önizlemesi ve UI-03B doğrulanmış
taslak config hattı aktiftir. Kanonik
geometri; NACA 4-haneli kesit, chord–twist istasyonları, kanat sayısı ve menteşe
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
açılma duyarlılığı da yalnız `screening_only` etiketiyle görüntülenir. Ekranlar şu
girdilere bağlıdır:

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

Ekrandaki `Radyal zarf çapı`, nominal uç merkez hattının menteşe projeksiyonunu sabit
kök yarıçapının altına düşürmeden gösterir. `Mesh zarf çapı` ise chord dahil çizilen
vertex planformunun ölçümüdür. Bu değerler birbirinin veya CFD/BEM performans çapının
yerine kullanılmaz. Bir sonraki UI artımı UI-04'tür: mevcut CLI yollarıyla aynı girdiyi
ve aynı sonucu kullanan, yeni sonucu kanıt durumundan ayıran analiz çalıştırma/sonuç
gezgini. Henüz etkinleştirilmeyen sayfalar güvenli placeholder'dır: analiz çalıştırmaz
ve örnek mühendislik sonucu üretmez.

## Çalıştırma ve test

```bash
pip install -e ".[dev,plot,ui]"
streamlit run apps/pyfoldable_dashboard.py
pytest tests/application/test_dashboard.py tests/application/test_design_draft.py \
  tests/visualization/test_propeller_25d.py \
  tests/ui/test_streamlit_dashboard.py -q
```

Lovable projesi yalnız UX prototipi olarak tutulur. Gerçek proje durumu ve sayısal
sonuçların tek kaynak noktası Git ile sürümlenen Python reposudur.
