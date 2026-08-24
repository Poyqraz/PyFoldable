# PyFoldable

![Tests](https://github.com/Poyqraz/PyFoldable/actions/workflows/tests.yml/badge.svg)

**Uçtan eklemli katlanabilir pervane için sayısal analiz ve mühendislik raporlama paketi**

PyFoldable; uçtan mafsallı (tip-hinged) katlanabilir pervane geometrisinin kinematik modelini,
menteşe dinamiğini, kalibrasyonlu itki bölünmesini ve motor bağlantılı performans
değerlendirmesini tek bir doğrulanabilir iş akışında birleştirir. Paket; tasarım varyantı
taramasından 7100 dev/dak mühendislik kontrol noktasına, oradan mühendislik tasarım raporu ve
Seviye-2 CFD hazırlık tablolarına kadar uçtan uca sayısal ön tasarım çıktıları üretir.

## Projenin amacı

Mühendislik tasarımı bağlamında şu sorulara model tabanlı yanıt üretmek:

1. **Katlanabilir düzenleme**, **20 cm temel pervane** (`root-only` / `compact root`) itkisine göre ne kadar **itki kazancı** sağlar?
2. **Katlanabilir düzenleme** (`foldable pretest`), **sabit 25 cm referans pervane** (`fixed reference`) performansına ne kadar yaklaşır; **itki açığı** nedir?
3. 7100 dev/dak kontrol noktasında motor akımı, gücü ve tork marjı kabul edilebilir mi?
4. Tasarım varyantları ve dağıtım senaryoları tekrarlanabilir CSV ve rapor dosyalarıyla belgelenebilir mi?

## Terimler (kod etiketi → rapor dili)

| Kod / CSV etiketi | Türkçe karşılık |
|-------------------|-----------------|
| `root-only`, `compact root`, `root_only_20cm` | **20 cm temel pervane** |
| `foldable`, `foldable pretest`, `pretest_70_fixed` | **Katlanabilir düzenleme** |
| `fixed reference`, `fixed 25cm`, `25 cm reference` | **Sabit 25 cm referans pervane** |
| `gain`, `gain_vs_compact_20cm_root` | **İtki kazancı** (20 cm temel pervaneye göre, %) |
| `loss`, `loss_vs_25cm_reference` | **İtki açığı** (sabit 25 cm referansa göre, %) |
| `reference_load_postprocess` | Referans pervane yüküyle motor dengesi; katlanabilir aerodinamik yük sonradan işlenir |

Ayrıntılı eşleme: `reports/foldable_v2_engineering_design/terminology_tr.md`

## Kanonik tasarım dosyası

Yeni BEM/CAD/CFD geliştirmeleri için birim kontrollü, sürümlenmiş TOML giriş modeli
`pyfoldable.core` altında bulunur. Kullanıcı girdileri `mm`, `in`, `deg` ve `rpm` gibi
mühendislik birimleriyle yazılabilir; çözücü modelleri yalnızca SI değerleri alır.

```python
from pyfoldable.core import load_design_config

design = load_design_config("configs/designs/TIP_HINGED_250_CANONICAL.toml")
```

Şema, model listesi ve geriye dönük uyumluluk sınırı:
`docs/canonical_design_config.md`.
Polar provider platformundan provider-backed `PolarFamily` entegrasyonuna geçiş haritası:
`docs/development_roadmap.md`.
PR-05 sonrası güncel hedef, doğrulama açıkları ve PR-06–PR-12 yürütme kapıları:
`docs/validation_and_development_roadmap.md`.

PR-07 tam bağlı motor–rotor sayısal kapısı ve yeniden üretilebilir kanıtı için
`examples/run_pr07_fully_coupled_evidence.py` çalıştırılabilir. Bu çıktı yazılım
niteliğindedir; ölçülmüş motor–pervane korelasyonu olmadan fiziksel doğrulama sayılmaz.
Sürümlü polar grid/provider/runtime ayarları ve güvenlik kuralları:
`docs/polar_configuration.md`.

İlk generated-polar tüketicisi `analyze_generated_polar_sections()` ile her kanat
istasyonunun kinematiğini ve iki boyutlu yüklerini hesaplar. Varsayılan polar sınır
politikası fail-closed `error`dır; açıkça seçilen `clamp` işlemleri tanı, uyarı ve
`SimulationResult` provenance kayıtlarında korunur. Bu model tam BEM değildir:
indüksiyon, swirl, Prandtl kök/uç kaybı, dinamik stall ve sıkıştırılabilirlik düzeltmesi
uygulamaz.

PR-06A/06B akışı için `solve_bem_annulus()` ve `solve_bem_rotor()` ayrı, fail-closed
sözleşmelerdir. Rotor çözücüsü varsayılan olarak yalnız blade station aralığını midpoint
kuralıyla integre eder; hub-tip geometri uzatması ve Prandtl kök faktörü açıkça seçilir.
PR-06C, UIUC APC 10×4.7 rüzgâr-tüneli verisiyle 60 noktalı benchmark, ağ ve model/polar
duyarlılığı üretir. İmzalı, ters-akışsız yerel yükleme dalı ileri-uçuş çözüm kapsamını
%20,6'dan %100'e çıkardı. Bununla birlikte dondurulmuş tam zarfta CT/CP hataları ve
temsili polar kanıtı kapıları geçmediği için fiziksel doğruluk ve PR-06D'nin fiziksel
niteleme geçişi kapalıdır. Sabit-limit yazılım eşdeğerliği ve 250-vaka açılma taraması
tamamlanmıştır; açılma sonuçları screening-only kalır. Denklem/kapsam incelemesi
`docs/pr06_foundation_review.md`, geçmiş review
`docs/pr04_pr06_retrospective_review.md`, üretici-geometrisi/polar remediation kaydı
`docs/pr06c_geometry_polar_remediation.md`, çıktı ise
`reports/pr06c_fixed_propeller_benchmark.md`, yayımlanmış CFD karşılaştırması
`reports/pr06c_published_cfd_review.md` ve açılma taraması
`reports/pr06d_opening_sensitivity.md` altındadır.

## Kurulum

```bash
git clone https://github.com/Poyqraz/PyFoldable.git
cd PyFoldable
pip install -e ".[dev,plot,ui]"
```

Gereksinimler: Python ≥ 3.10, NumPy, SciPy. Grafik örnekleri için `matplotlib`
(`plot` extra), mühendislik çalışma alanı için Streamlit ve Plotly (`ui` extra).

### Mühendislik çalışma alanı

```bash
streamlit run apps/pyfoldable_dashboard.py
```

Çalışma alanı kanonik tasarım ve sürümlü raporlarla bağlı bir proje/kanıt dashboard'udur.
Tasarım Geometrisi ekranı, NACA kesit ve chord–twist istasyonlarından etkileşimli 2.5D
pervane önizlemesi üretir; bu görsel CAD/CFD/FEA veya performans sonucu değildir ve
config'e yazılmaz. Geometri ve ilk çalışma koşulu girdileri, seçilen çıktı birimleriyle
kaynak SHA-256 kimlikli ve `unqualified_design_draft` sınıflı ayrı bir TOML taslağına
indirilebilir; taslak katı config yükleyicisiyle round-trip edilir ve kanonik dosyanın
üzerine yazılmaz. Henüz analiz çalıştırmayan sayfalar bunu açıkça belirtir; katlanma
sonuçları PR-06C fiziksel kapısı geçene kadar `Tarama amaçlı` kalır. Mimari ve
geliştirme sırası: `docs/ui_engineering_workspace.md`.

## Hızlı çalıştırma

Aşağıdaki komutlar bağımsız çalışır (önceki çıktı gerektirmez):

```bash
# 1) V1 RPM taraması — kinematik + efektif çap + itki tablosu
python3 examples/run_foldable_sweep.py

# 2) V2 işletim noktası — motor denge + katlanabilir son-işleme
python3 examples/run_foldable_operating_point.py

# 3) V2 prescribed-RPM fizik tanıları ve debug CSV/şekilleri
python3 examples/run_prescribed_rpm_physics.py

# 4) Seviye-1 CFD hazırlık tabloları (işletim noktası ve sınır koşulu girdisi)
python3 examples/run_cfd_preparation.py
```

Mühendislik raporu üretimi (önce motor bağlantılı tanı CSV'leri gerekir):

```bash
python3 examples/run_deployment_diagnostics.py
python3 examples/generate_foldable_engineering_report.py
```

Testler:

```bash
pytest tests/ -q
```

## Ana çıktı dosyaları

**Türkçe rapor referansları (öncelikli):**

| Yol | Açıklama |
|-----|----------|
| `reports/foldable_v2_engineering_design/README.md` | Rapor paketi girişi |
| `reports/foldable_v2_engineering_design/report_conclusion_tr.md` | **Türkçe sonuç metni** |
| `reports/foldable_v2_engineering_design/report_key_results.csv` | 7100 dev/dak özet metrikleri |
| `reports/foldable_v2_engineering_design/terminology_tr.md` | Terim sözlüğü |
| `reports/foldable_v2_engineering_design/docx/` | Final Word raporu (teslim) |
| `reports/foldable_v2_engineering_design/pdf/` | Final PDF çıktısı (teslim) |
| `reports/foldable_v2_engineering_design/figures/` | Rapora gömülecek nihai şekiller |

**Teknik ekler (İngilizce):**

| Yol | Açıklama |
|-----|----------|
| `reports/foldable_v2_engineering_design/foldable_v2_engineering_design_report.md` | Tam mühendislik raporu (Markdown) |
| `reports/foldable_v2_engineering_design/model_assumptions_and_limits.md` | Model varsayımları |
| `reports/foldable_v2_engineering_design/figure_index.md` | Şekil envanteri |
| `configs/foldable/TIP_HINGED_250_V02.json` | V2 referans konfigürasyonu |
| `outputs/foldable/` | Örnek betiklerin ürettiği ara CSV ve şekiller (gitignore) |

## 7100 dev/dak ana sonuçları

Motor bağlantılı katmanda interpolasyonla elde edilen mühendislik kontrol noktası
(`CHECKPOINT_RPM` = 7100 dev/dak):

| Karşılaştırma | Değer |
|---------------|-------|
| 20 cm temel pervane | **3.73 N** |
| Katlanabilir düzenleme | **6.37 N** |
| Sabit 25 cm referans pervane | **9.10 N** |
| 20 cm temele göre itki kazancı | **+%70.9** |
| Sabit 25 cm referansa göre itki açığı | **%30.0** |

Ek kontrol noktası verileri: gaz **0.768**, akım **17.0 A**, güç **150 W**
(kaynak: `reports/foldable_v2_engineering_design/report_key_results.csv`).

## Geçerlilik kapsamı

Bu aşama **sayısal ön tasarım ve model tabanlı değerlendirme** üretir. Paket;

- kinematik model, menteşe dinamiği, kalibrasyonlu itki bölünmesi ve motor bağlantılı
  performans katmanını bir arada sunar;
- Seviye-1 **CFD hazırlık tabloları** ile işletim noktası ve sınır koşulu girdisi sağlar;
- motor bağlantısını `reference_load_postprocess` seviyesinde modeller (RPM/akım/güç referans
  pervane dengesinden; katlanabilir `D_aero` yükü sonradan işlenir).

Kalibrasyonlu proje pervanesi deneyi, tam ileri-uçuş BEM kapsamı, CFD korelasyonu ve yapısal
analiz sonraki doğrulama adımları için referans alınır. Ayrıntı:
`reports/foldable_v2_engineering_design/model_assumptions_and_limits.md`

## Kapsam özeti

- **V1:** Kinematik, efektif çap, tasarım taraması, karar matrisi, görselleştirme
- **V2:** Menteşe dinamiği, itki bölünmesi, motor bağlantılı performans, mühendislik raporu

## Lisans

Telif hakkı © 2026 Poyraz Baydemir.

İlk-taraf proje malzemesi [PolyForm Noncommercial 1.0.0](LICENSE) altındadır. Kişisel,
akademik ve diğer lisans-tanımlı ticari olmayan kullanımlar serbesttir; ticari kullanım
için [@Poyqraz](https://github.com/Poyqraz) ile ayrı lisans gerekir. Bu, 0.3.0 ve sonrası
için ileriye dönük değişikliktir; daha önce Apache-2.0 altında edinilmiş kopyalar o
kopyaya eşlik eden lisansı korur.

Kapsam/üçüncü taraf sınırları: `docs/licensing.md` ve `THIRD_PARTY_NOTICES.md`. Katkı
koşulları: `CONTRIBUTING.md` ve `CLA.md`.

---

## Geliştirici notu

PyFoldable, [PyThrust](https://github.com/Poyqraz/PyThrust) ekosistemindeki foldable modülünün
bağımsız paket olarak dışa aktarılmış halidir. İşletim noktası eşlemesi için minimal
`pythrust.propellers` ve `pythrust.propulsion` dilimleri dahil edilmiştir; PyThrust çekirdek
çözücüsü değiştirilmemiştir.
