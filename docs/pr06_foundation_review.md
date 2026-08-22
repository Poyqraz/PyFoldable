# PR-06 foundation review

Bu inceleme PR-06A yerel annulus çekirdeğinin PR-06B radyal rotor integrasyonuna
temel olacak kadar açık, sayısal olarak güvenli ve fiziksel kapsamı dürüst olup
olmadığını değerlendirir.

## İnceleme kapsamı

- Kaynak denklemleri: QPROP hız üçgeni, `psi` parametrelemesi, dolaşım/swirl
  kalıntısı, değiştirilmiş Prandtl uç faktörü ve yerel itki/tork.
- Sayısal davranış: hover, pozitif ileri hız, kök bulma, kalıntı kabulü ve
  desteklenmeyen çözüm dalları.
- Yazılım sözleşmesi: polar kapsamı, geometri sınırları, airfoil kimliği,
  provenance ve kısmi sonuç davranışı.
- PR-06B: midpoint radyal integrasyon, geometri enterpolasyonu, kök sınırı ve
  boyutsuz performans katsayıları.

## Denklem doğrulaması

PR-06A aşağıdaki QPROP ilişkileriyle uyumludur:

| Uygulama | QPROP karşılığı | Sonuç |
| --- | --- | --- |
| `Wa`, `Wt`, `va`, `vt` için `psi` parametrelemesi | Eş. 17–23 | Doğrulandı |
| `alpha = beta - phi`, Reynolds ve Mach | Eş. 24–27 | Doğrulandı |
| Yerel wake ratio ve değiştirilmiş uç faktörü | Eş. 28–31 | Doğrulandı |
| `Gamma - 0.5 W c Cl` kökü | Eş. 32–34 | Doğrulandı |
| Diferansiyel itki ve tork | Eş. 50–51 | Doğrulandı |
| Midpoint rotor toplamları | Eş. 64–65 | PR-06B'de uygulandı |

Kaynak: Mark Drela, [QPROP Formulation](https://web.mit.edu/drela/Public/web/qprop/qprop_theory.pdf).

## Bulgular ve kapanışları

| Önem | Bulgu | Kapanış |
| --- | --- | --- |
| Yüksek | Rotor toplamının hangi radyal aralığı temsil edeceği tanımlı değildi. | Güvenli varsayılan `station_span`; endpoint geometriyi sabit uzatan `hub_to_tip` yalnız açık seçimle etkin. Aralık ve uzatma her sonuçta kayıtlı. |
| Yüksek | Farklı airfoil istasyonları arasında chord/twist enterpolasyonu airfoil fiziğini sessizce belirsiz bırakabilirdi. | PR-06B tek airfoil kimliğinde fail-closed çalışır. Airfoil blending daha sonraki açık bir model kararıdır. |
| Orta | QPROP temelinde kök kaybı yoktu; roadmap bunu PR-06B girdisi sayıyordu. | QPROP'a sadık varsayılan korunarak standart Prandtl kök faktörü ayrı `include_root_loss` uzantısı olarak eklendi; tip, kök ve birleşik faktör ayrı raporlanır. PR-06C benchmark'ı varsayılan seçimi belirleyecek. |
| Orta | Yalnız mutlak dolaşım toleransı ölçek değişimlerinde zayıftı. | Mutlak + bağıl tolerans sözleşmesi eklendi; desteklenmeyen negatif dolaşım/indüklenmiş-akış dalları ayrıca reddedilir. |
| Orta | Annulus ayarları rotor sonucu provenance'ında yoktu. | Tüm quadrature, radial-domain, polar-bound ve loss-model anahtarları JSON-serializable sonuçta korunur. |
| Düşük | Roadmap'taki Andrew Ning bağlantısı farklı bir yayına gidiyordu. | Doğru BYU Faculty Publication 1673 ve DOI kaydıyla değiştirildi. |

Andrew Ning'in [garantili yakınsama çalışması](https://scholarsarchive.byu.edu/facpub/1673/)
tek değişkenli, bracket edilmiş kök bulmanın neden tercih edildiğini destekler. PR-06A
QPROP'un `psi` değişkenini ve SciPy'nin bracket edilmiş Brent yöntemini kullanır; buna
rağmen yalnız açıkça desteklenen pozitif pervane dalında çözüm garantisi verir.

## PR-06B sözleşmesi

- Annuluslar eşit radyal genişlikli midpoint kuralıyla çözülür.
- Chord ve twist istasyonlar arasında doğrusal enterpole edilir.
- Varsayılan integrasyon yalnız tanımlı istasyon aralığındadır; geometri
  ekstrapolasyonu sessiz değildir.
- Bir annulus başarısızsa rotor toplamı üretilmez.
- `T`, `Q`, şaft gücü, `CT`, `CQ`, `CP` ve ileri uçuşta `eta` raporlanır.
- Hover'da faydalı-güç verimi fiziksel olarak tanımsız olduğundan `eta = null` tutulur.
- Her annulusun yerel çözümü ve polar kaynağı sonuç paketinde kalır.
- Promote edilmiş gerçek XFOIL polar fixture'ının rotor tüketicisine ulaştığı regresyonla
  doğrulanır; tek Reynolds/Mach hücresi dışındaki sorgular açık `clamp` provenance'ı
  taşır ve bu test fiziksel rotor doğrulaması olarak yorumlanmaz.

## Kalan model-form sınırları

PR-06B deneyle doğrulanmış bir performans modeli değildir. Aşağıdakiler özellikle
uygulanmamıştır:

- Farklı airfoil aileleri arasında geçiş veya 3B dönel-stall düzeltmesi.
- Yüksek Mach için polar dışında ek sıkıştırılabilirlik düzeltmesi.
- Eğik/yaw akış, dinamik inflow, wake contraction veya karşılıklı rotor etkileşimi.
- Katlanma açısı ve menteşe kinematiğinin yerel rotor geometrisine bağlantısı.
- APC/itki standı verisiyle hata eşiği ve model seçimi.

Bu sınırlar nedeniyle PR-06B'nin tamamlanması **kod ve sayısal integrasyon kapısını**
geçirir. Fiziksel tahmin doğruluğu kapısı PR-06C benchmark'ı ile açılacaktır.
