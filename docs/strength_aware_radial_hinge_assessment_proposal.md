# Strength-aware radial hinge-position assessment

Status: **PROPOSED / NOT IMPLEMENTED**. This documentation-only proposal is not
a frozen contract, implementation authorization or qualified design.
Inspection base: `a5286cc6d80ea0130bd3bdc87d2b42277c499900`.
Parent-blade design-intent clarification base:
`c2b267f1e1536e205c5d7ac3c05c2a8ab227533d` (merged proposal PR #86).

The question is where to divide an actual blade into fixed and movable parts,
given its section geometry and one declared joint design. A shorter tip can
reduce moving mass yet place the attachment in a thinner section; neither fact
alone establishes fracture resistance. The first useful result is a traceable
candidate comparison with explicit missing evidence, not an overall safe winner.
No CAD, solver, source, trajectory, executable fixture, numerical gate or CMM-2
contract changes belong to this proposal. PR #81/#84 remain separate.

## 1. Existing capabilities and their boundaries

| Existing path | Reuse in a later authorized assessment | Boundary retained |
| --- | --- | --- |
| [Legacy root/tip variants](../pyfoldable/variants.py) and [sweep](../pyfoldable/design_sweep.py) | Split labels and historical comparisons | Ratios partition the shaft-to-tip radius. The helper assumes midpoint tip CG and scales tip mass linearly with tip fraction; the sweep uses reference-scaled thrust. These are not CAD-derived mass, stress or source-bound aerodynamic evidence. Default percentage pairs do not encode exact 8:5 or 10:3 splits. |
| [Canonical design](../configs/designs/TIP_HINGED_250_CANONICAL.toml), [GEOM-02](geom02_station_contract.md), [draft service](../pyfoldable/application/design_draft.py) | SI units, explicit station/profile identities, candidate drafts | Canonical station/chord/twist values are schema examples, not recovered blade geometry. Stations span 0.20R–0.98R; missing span is not silently completed. Manufacturing thickness fields and analytic profiles are not strength evidence. |
| [GEOM-01](geom01_feasibility_plan.md), [geometry search](../pyfoldable/application/geometry_search.py) | Bounded hinge-radius/endpoint screening on the same declared source geometry | One planar rigid tip, +z hinge, zero offsets; centerline bounds and endpoint preview are not swept CAD clearance. Unsupported joint geometry is reported unsupported, not projected into this topology. |
| [GEOM-04](geom04_surface_hardware.md), [hardware contract](../pyfoldable/application/hardware_contract.py) | Candidate-specific retained-surface/declared hardware evidence within supported representations | Preview surfaces, convex solids and cylinder envelopes are not arbitrary CAD contact. Shared-hinge contact, exclusions, incomplete coverage and budget exhaustion remain visible. Evidence cannot be reused across changed candidates. |
| [Active BEM search](py04_deterministic_design_search.md), [adapter](../pyfoldable/application/active_design_search.py), [analysis](../pyfoldable/application/design_analysis.py) | Source-bound fully-open aerodynamic screening with matched coordinate/polar identity and unchanged budgets | Search axes are chord/twist multipliers, with hinge fixed. This is not a strength-aware hinge optimizer. Physical/structural constraints remain unknown. Supported first operating condition, profile and source-domain restrictions apply; no fallback polar or reference substitution. |
| [Mechanism binding](../pyfoldable/application/mechanism_binding.py) | Explicit one-tip radial mass samples and intrinsic inertia when their model is applicable | Caller-labelled samples remain unqualified. The radial reduction does not supply an arbitrary 3D joint tensor, measured CG or impact load. |
| [PR-09 plan](pr09_fea_contract_execution_plan.md), [FEA contract](../pyfoldable/core/fea_contract.py), [evidence](../reports/pr09_fea_contract_evidence.md) | Revision/material/load-case/result identities and existing convergence/unit/limit checks | Synthetic results prove validator behavior only. Software pass always leaves physical qualification false. Actual PA-CF, CAD, loads, limits and ANSYS evidence are missing. Schema acceptance alone does not prove a material card or load model physically adequate. |

These are separate capabilities. No existing adapter turns their outputs into a
structurally qualified radial-hinge winner. This proposal adds none and changes
none of their constraints.

## 2. Diameter, radius and split conventions

Use the **250 mm project baseline**: open swept diameter D=250 mm, shaft-to-tip
radius R=D/2=125 mm, canonical hub radius b=18 mm, canonical hinge radius
h=100 mm, nominal movable length L=R-h=25 mm. Hinge radius is measured from the
shaft axis. Available fixed radial span outside the hub is h-b, not h. The
canonical 140 mm stowed-diameter and 0.85 matched-reference thrust-retention
targets at 7100 RPM are targets, not achieved results or new acceptance gates.

For this comparison only, **diameter-equivalent A+B** means A=2h and B=2L,
so D=A+B. It does not mean two physical blade lengths added along one radius.
Raw user/CAD labels must declare units and reference origin before conversion;
unresolved conventions block the candidate. Radius-based or hub-edge splits
are different declarations, not silently interpreted as this convention.

| Scenario / split | h/R | h (mm) | L (mm) | Interpretation |
| --- | --- | --- | --- | --- |
| 250 mm, proportions 8:5 | 8/13 | 1000/13 ≈ 76.923 | 625/13 ≈ 48.077 | Same ratio, not an 8-inch fixed diameter |
| 250 mm, proportions 10:3 | 10/13 | 1250/13 ≈ 96.154 | 375/13 ≈ 28.846 | Same ratio; not the canonical 100 mm hinge |
| Separate 13-inch diameter, 8+5 inches equivalent | 8/13 | 101.6 | 63.5 | D=330.2 mm, R=165.1 mm |
| Separate 13-inch diameter, 10+3 inches equivalent | 10/13 | 127.0 | 38.1 | D=330.2 mm, R=165.1 mm |

These are unit/ratio arithmetic, not manufactured candidates or screening results.
The 13-inch scenario needs its own real blade, hub, motor/operating envelope,
joint, material and acceptance declarations. Do not scale 250 mm CAD, tip mass,
polars, targets or evidence into it. A 254 mm benchmark is also distinct from
the 250 mm project rotor.

Keep the existing topology conflict visible: full 180-degree folding with hub
nonpenetration requires h≥(R+b)/2 and centerline envelope diameter ≥R+b=143 mm
for the canonical R,b. Equality is touching, not positive clearance. Changing
hinge radius cannot meet the 140 mm target under that full-fold topology;
surface/hardware thickness can add restrictions. Partial travel must be explicitly
declared and reviewed as a different endpoint, not substituted for full stow.

## 3. Smallest useful first deliverable

### Parent blade and deployed correspondence

One original blade is the accepted reference **for this study**. Its presumed
optimality is a scoped study assumption at a declared operating condition, not
independently validated global optimality. Record the parent CAD/section/profile
source identities, revision/hashes and the assumed objective, RPM, inflow and
environment with their source; these actual inputs remain unsupplied. The 7100 RPM
project target alone does not identify that condition or prove the assumption.

The fixed and moving portions are complementary cuts of that same parent blade.
Use global shaft-based radius r and tip-local span s=r-r_h: outside explicitly
declared joint modifications, the tip inherits c_tip(s)=c0(r_h+s) and
beta_tip(s)=beta0(r_h+s), over s in [0,R-r_h]. Do not replay the parent ro…13730 tokens truncated…ri-uçuş kapsamı %46/%20,6'dan %100/%100'e çıktı. Tam zarf artık proxy
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

**Ayrı tasarım önerisi — PROPOSED / NOT IMPLEMENTED:**
[Dayanımı gözeten radyal menteşe konumu değerlendirmesi](strength_aware_radial_hinge_assessment_proposal.md)
250 mm proje tabanında tek gerçek pal ve tek beyan edilmiş bağlantı için sınırlı,
adaya bağlı geometri/kütle/aerodinamik/yük-vakası/FEA kanıt dosyası önerir.
İlk CAD karşılaştırması aynı ana palın iki menteşe konumunda kesilip yeniden
birleştirilmiş açık geometrisini özgün pal ile eşler; radyal kesit/twist eşleşmesi,
dönüşümler ve bağlantı bölgesi farkları açıkça kaydedilir. Ana palın varsayılan
optimumluğu yalnız beyan edilmiş çalışma koşuluna bağlı çalışma varsayımıdır.
Dar [istasyon karşılaştırma raporu](parent_blade_station_comparison.md) ayrı Draft
uygulama dilimidir: kaynak bağlı açık eşleme ve sayısal farklar raporlanır;
tam 3B yüzey, bağlantı boşluğu/dayanımı veya güvenli aday kanıtı değildir.
Geniş tasarım önerisi PROPOSED / NOT IMPLEMENTED olarak kalır.
13 inç ayrı senaryodur. CAD, yönsel PA-CF kuponları ve deney hazırlığı CMM-2
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
