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
| UI-03 | Tasarım ve çalışma koşulu editörü | Birim kontrollü config round-trip |
| UI-04 | Analiz çalıştırma ve sonuç gezgini | CLI ile sayısal eşdeğerlik |
| UI-05 | CFD/FEA/deney veri alımı | Mevcut sözleşmelerle şema, birim ve SHA doğrulaması |
| UI-06 | Kanıt/rapor merkezi | Tekrar üretilebilir dışa aktarma |
| UI-07 | E2E, görsel regresyon ve paketleme | Temiz ortam smoke testi ve erişilebilirlik |

## Güncel artım

UI-00/01 temeli ve UI-02'nin Genel Bakış ekranı aktiftir. Kanonik geometri ve çalışma
koşulları salt okunur incelenebilir; 250 vakalık açılma duyarlılığı da yalnız
`screening_only` etiketiyle görüntülenir. Ekranlar şu girdilere bağlıdır:

- `configs/designs/TIP_HINGED_250_CANONICAL.toml`
- `reports/pr06c_physical_gate.json`
- `reports/pr06d_opening_sensitivity.json`
- `reports/pr07_fully_coupled_evidence.json`
- `reports/pr06c_published_cfd_review.json`
- `reports/pr09_fea_contract_evidence.json`
- `reports/pr10_experiment_contract_evidence.json`

Henüz etkinleştirilmeyen sayfalar güvenli placeholder'dır: analiz çalıştırmaz ve örnek
mühendislik sonucu üretmez.

## Çalıştırma ve test

```bash
pip install -e ".[dev,plot,ui]"
streamlit run apps/pyfoldable_dashboard.py
pytest tests/application/test_dashboard.py tests/ui/test_streamlit_dashboard.py -q
```

Lovable projesi yalnız UX prototipi olarak tutulur. Gerçek proje durumu ve sayısal
sonuçların tek kaynak noktası Git ile sürümlenen Python reposudur.
