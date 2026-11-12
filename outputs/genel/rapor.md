> **Bu sonuçlar sentetik veriye dayanan bir demodur.** Ölçülmüş veri kullanılmamıştır; süreler literatürden ve VARSAYIM'lardan alınmıştır (bkz. `data/genel_parametreler.xlsx`).

# Genel Sürüm – Ürün Ailesinden Bağımsız Çevrim Süresi Modeli

## Soru: 'X takma' mı, 'takma' mı, hareket sayısı mı?

Ürünü tarif etmenin üç seviyesi var. MTM sistemleri de aynı hiyerarşiyi kullanır: MTM-1 temel hareketler seviyesinde, MTM-2 hareket dizileri seviyesinde, MTM-UAS temel işlemler seviyesindedir ve üst seviyelerin hepsi MTM-1'e dayanır [S21].

| Seviye | Örnek değişkenler | Artısı | Eksisi | Bu projede |
|---|---|---|---|---|
| 1. Ürüne özel kalem | pompa takma, hortum takma, sensör takma | Firma için en anlaşılır; tek ürün ailesinde iyi çalışır. | Başka ürüne taşınamaz: aynada 'pompa' yok. Her yeni ürün için yeni değişken ve yeni veri gerekir. | Washer tank sürümü (src/demo.py) |
| 2. Genel işlem tipi (önerilen) | kolay/zor parça yerleştir, vidala, geçme, esnek bağlantı, kontrol, makine süresi | Ürün ailesinden bağımsız; MTM-UAS'ın 'temel işlem' seviyesi [S21],[S22] ve DFA sınıflandırması [S7],[S8] ile aynı mantık. Değişken sayısı az, regresyon için az veri yeter. | Bir işlem tipinin içi ortalama süre kabul edilir; zor bir vida ile kolay vida farkı kaybolur (MTM-UAS'ın kendisi de temel hareket seviyesine göre daha az hassas [S22]). | Bu genel sürüm |
| 3. Hareket bazlı (MTM-1) | uzan, kavra, taşı, konumla, bırak (TMU) | En taşınabilir ve en ayrıntılı; tüm üst MTM sistemleri buna dayanır [S21]. | Her ürün için eğitimli analist ve lisanslı tablolar gerekir; değişken sayısı çok fazla. Hareketler bilindiğinde süre zaten toplamla hesaplanır, regresyona gerek kalmaz. | Element sürelerinin kaynağı olarak kullanılmalı (firma MTM analizi yaparsa tablodaki süreler güncellenir) |

**Öneri:** Tahmin modeli **2. seviyede** (genel işlem tipi) kurulmalı. 'Pompa takma' yerine 'zor parça yerleştirme', 'hortum takma' yerine 'esnek bağlantı' denir; makine işlemleri saniye olarak girilir. Böylece aynı model washer tank ve ayna için çalışır, ürün ailesi yalnızca sayıları değiştirir. Hareket bazlı (MTM-1) seviye tahmin girdisi olarak değil, her işlem tipinin **süresini belirlemek** için kullanılmalı: firma bir işlem tipini MTM ile analiz ederse `ELEMENTLER` tablosundaki süre güncellenir ve script yeniden çalıştırılır.
- Benzer bir yaklaşımda ürün yapısından (parça bağlantı grafiği) montaj süresi tahmin edilmiş ve sonuçlar ±%25 içinde kalmıştır; aynı çalışma **eğitim verisindeki ürün çeşitliliğinin** kritik olduğunu vurgular [S23]. Bu yüzden gerçek veri toplanırken birden fazla ürün ailesinden ölçüm alınmalıdır.

## Genel işlem tipleri ve süreleri

| İşlem tipi | Tipik süre | Kaynak/VARSAYIM |
|---|---|---|
| sabit_is | 15 sn/ürün | VARSAYIM: etiketleme, kutulama gibi üründen bağımsız işler. |
| tasima_sabit | 2.0 sn/taşıma | [S10] orta boy parça tutma 2,0–3,0 sn; gövde 3 kez alınıp konur (VARSAYIM). |
| tasima_per_kg | 1.5 sn/kg/taşıma | VARSAYIM: [S10] ağır parça (>2 kg) 3,5–5,0 sn'ye çıkacak şekilde kütleyle artış. |
| parca_kolay | 3.0 sn/adet | [S7],[S8] tutma 1,5–1,95 sn + engelsiz yerleştirme 1,5 sn (kod 10/00, 30/00). |
| parca_zor | 8.5 sn/adet | [S8] tutma 1,95–2,36 sn + bastırarak/tutarak yerleştirme 6,5 sn (kod 08). |
| vida | 9.8 sn/adet | [S7],[S8] tutma 1,8 sn + yerleştirme/sıkma 6 / 8 / 12 sn (kod 38 / 39 / 59). |
| gecme | 3.5 sn/adet | [S10] tutma 1,5–2,0 + geçmeli yerleştirme 1,5–2,5 sn (genel çerçeve, doğrulanmış tablo değil). |
| baglanti | 8.0 sn/adet | VARSAYIM: esnek parça tutma [S10] 3–5 sn + rakora/sokete geçirme; elektrik soketi kısa, kelepçeli hortum uzun uçta. |
| kontrol | 2.0 sn/nokta | VARSAYIM: MTM-UAS'ta görsel kontrol ayrı bir sınıf [S22]; sayısal değeri okunamadı. |
| zor_parca_vida | 2 vida/parça | VARSAYIM: her zor parça en fazla 2 vidasıyla birlikte aynı operatörce takılır (bağlı iş). |

## Ürün şablonları (arayüzde hazır)

| Şablon | govde_kg | parca_kolay | parca_zor | vida | gecme | baglanti | kontrol | makine1_sn | makine2_sn | Eşleştirme |
|---|---|---|---|---|---|---|---|---|---|---|
| Washer tank | 0.6 | 2 | 1 | 2 | 4 | 2 | 2 | 30 | 25 | zor parça = pompa; kolay = sensör, kapak; esnek bağlantı = hortum; geçme = klips; makine 1 = sıcak plaka kaynağı ([S1],[S2] 10–60 sn içinde 30 sn); makine 2 = sızdırmazlık testi ([S6] 20–30 sn içinde 25 sn). |
| Dış dikiz aynası | 0.9 | 3 | 2 | 4 | 6 | 2 | 3 | 0 | 15 | zor parça = ayar motoru, cam+tutucu; kolay = kapak, sinyal camı, conta; esnek bağlantı = kablo soketi; makine 1 yok; makine 2 = elektriksel fonksiyon testi 15 sn. Tüm sayılar VARSAYIM (aynaya özel süre kaynağı bulunamadı). |

## Veri

- 400 satır (her operatör sayısı için 100), seed = 2024. Girdi aralıkları geniş tutuldu ki hem washer tank hem ayna gibi ürünler kapsansın; makine işlemleri %20 olasılıkla 0 (o üründe yok).
- 21 aday terim × 15–20 gözlem ≈ 315–420 satır → 400 seçildi.
- Çevrim süresi: işler sabit sırada, bağlı işler bölünemez blok (yükleme+makine, zor parça+vidaları); bloklar operatörlere en yüklü istasyonu en aza indirecek şekilde dağıtılır [S17]–[S20]; çevrim = en yüklü istasyon + N(0, 3.0²). **Makine süreleri operatöre bölünmez.**

| Operatör | Ort. denge kaybı | Maks | Çevrimin makine bloğuna dayandığı satır |
|---|---|---|---|
| 1 | %0.0 | %0.0 | %0 |
| 2 | %2.5 | %19.1 | %0 |
| 3 | %9.9 | %74.0 | %5 |
| 4 | %19.5 | %81.9 | %17 |

Operatör arttıkça çevrim uzun makine işleminin altına inemez; bu satırlarda operatör eklemek süreyi kısaltmaz. Bu yüzden aday listesine `maks_makine` (iki makine süresinden büyüğü) de eklendi.

## İleri seçim adımları

| Adım | Eklenen terim | p | R² | Düz. R² |
|---|---|---|---|---|
| 1 | 1/operator | 4.69e-134 | 0.7828 | 0.7823 |
| 2 | maks_makine | 1.29e-33 | 0.8497 | 0.8490 |
| 3 | vida/operator | 5.43e-44 | 0.9079 | 0.9072 |
| 4 | baglanti/operator | 8.95e-22 | 0.9270 | 0.9263 |
| 5 | gecme/operator | 3.07e-22 | 0.9425 | 0.9418 |
| 6 | parca_zor/operator | 1.27e-28 | 0.9580 | 0.9574 |
| 7 | makine1_sn/operator | 6.99e-22 | 0.9668 | 0.9663 |
| 8 | makine2_sn/operator | 9.50e-90 | 0.9882 | 0.9880 |
| 9 | parca_kolay/operator | 1.41e-38 | 0.9923 | 0.9922 |
| 10 | kontrol/operator | 8.50e-16 | 0.9935 | 0.9934 |
| 11 | govde_kg/operator | 7.88e-11 | 0.9942 | 0.9940 |
| 12 | operator | 1.01e-10 | 0.9948 | 0.9946 |
| 13 | gecme | 1.11e-03 | 0.9949 | 0.9948 |
| 14 | baglanti | 3.89e-03 | 0.9950 | 0.9949 |
| 15 | makine2_sn | 9.93e-03 | 0.9951 | 0.9949 |
| 16 | govde_kg | 4.42e-02 | 0.9952 | 0.9950 |
| 17 | (durdu: en iyi aday makine1_sn, p=0.169) | 1.69e-01 | – | – |

## Son model

- R² = **0.9952**, düzeltilmiş R² = **0.9950**, artık std. sapma = 4.23 sn

| Terim | Katsayı | Std. hata | p |
|---|---|---|---|
| sabit | -5.657 | 2.844 | 4.74e-02 |
| 1/operator | 22.439 | 3.230 | 1.61e-11 |
| maks_makine | 0.121 | 0.022 | 4.69e-08 |
| vida/operator | 9.864 | 0.145 | 1.84e-216 |
| baglanti/operator | 8.573 | 0.430 | 3.97e-61 |
| gecme/operator | 3.891 | 0.227 | 2.37e-49 |
| parca_zor/operator | 8.687 | 0.254 | 1.45e-118 |
| makine1_sn/operator | 0.921 | 0.025 | 1.20e-129 |
| makine2_sn/operator | 0.827 | 0.038 | 4.73e-69 |
| parca_kolay/operator | 3.097 | 0.177 | 9.83e-51 |
| kontrol/operator | 1.903 | 0.216 | 3.96e-17 |
| govde_kg/operator | 7.262 | 1.396 | 3.22e-07 |
| operator | 3.427 | 0.517 | 1.12e-10 |
| gecme | -0.464 | 0.137 | 7.47e-04 |
| baglanti | -0.718 | 0.262 | 6.38e-03 |
| makine2_sn | 0.066 | 0.025 | 9.09e-03 |
| govde_kg | -1.706 | 0.845 | 4.42e-02 |

**Denklem:** `çevrim_sn = -5.66 + 22.44·1/operator + 0.12·maks_makine + 9.86·vida/operator + 8.57·baglanti/operator + 3.89·gecme/operator + 8.69·parca_zor/operator + 0.92·makine1_sn/operator + 0.83·makine2_sn/operator + 3.10·parca_kolay/operator + 1.90·kontrol/operator + 7.26·govde_kg/operator + 3.43·operator − 0.46·gecme − 0.72·baglanti + 0.07·makine2_sn − 1.71·govde_kg`

## Kısa yorum

- '/operator' terimleri elle yapılan ve operatörler arasında paylaşılabilen işleri, bölünmemiş terimler (özellikle makine süreleri ve `maks_makine`) operatör sayısıyla kısalmayan kısmı temsil eder.
- Makine darboğazı gerçekte bir 'en büyüğü' (max) ilişkisidir; doğrusal regresyon bunu `maks_makine` ve bölünmemiş makine terimleriyle ancak yaklaşık yakalar. 3–4 operatörlü ve uzun makine süreli ürünlerde hata büyüyebilir; gerekirse parçalı (ör. 'çevrim = max(elle iş/n, makine)') bir model denenebilir.
- Model sentetik veriyi, onu üreten formülden öğrendiği için R² yüksek; gerçek veriyle düşecektir.
- Bu sürümün katsayıları ürün ailesine bağlı değil. Yeni bir ürün ailesi için yalnızca işlem sayılarını girmek yeterli; ancak gerçek veride her ailenin kendine özgü farkları için bir 'aile' değişkeni eklemek gerekebilir.

## Dosyalar

- `src/genel_demo.py` – hepsini yeniden üretir
- `data/genel_parametreler.xlsx`
- `outputs/genel/veri_seti.xlsx`, `model.json`, `index.html`

## Kaynakça

- [S1] Sprovieri, J. (2022). What's New With Hot-Plate Welding. ASSEMBLY Magazine, 13.09.2022. https://www.assemblymag.com/articles/97311-whats-new-with-hot-plate-welding
- [S2] Wikipedia katkıcıları. Hot plate welding (9 Eylül 2025 sürümü). https://en.wikipedia.org/wiki/Hot_plate_welding
- [S5] Telsonic AG (t.y.). Ultrasonic joining technology systems. https://www.telsonic.com/en/ultrasound-technology/ultrasonic-joining-technology-systems
- [S6] Sprovieri, J. (2009). Leak Testing Auto Parts. ASSEMBLY Magazine, 27.03.2009. https://www.assemblymag.com/articles/86667-leak-testing-auto-parts
- [S7] Chang, G., Peterson, W. (2010). Design for Assembly in Manufacturing Engineering Technology Program: Experience and Success. ASEE Annual Conference, AC 2010-2309 (tablolar: BDI Product Design for Assembly Handbook, 1989). https://peer.asee.org/design-for-assembly-in-manufacturing-engineering-technology-program-experience-and-success.pdf
- [S8] HKUST IELM 317 ders notu (t.y.). Design For Manufacturing/Assembly (DFM, DFA, DFMA); Boothroyd & Dewhurst (1991)'e atıfla. https://ieda.ust.hk/dfaculty/ajay/courses/ielm317/lecs/dfm/dfm.pdf
- [S9] Teni, M.H.M., Naroh, A., Maliki, K.A.A., Tukiran, A. (2019). Design Development of a Coffee Maker using Design for Assembly Method. IJEAT 9(2). DOI: 10.35940/ijeat.B4942.129219
- [S10] Guns, B. (t.y.). Design for Manufacturing (DFM). Engineering LibreTexts, Northeast Wisconsin Technical College. https://eng.libretexts.org/Courses/Northeast_Wisconsin_Technical_College/Design_for_Various_Manufacturing_Methods/01:_Design_for_Manufacturing_(DFM)
- [S11] Yin, M., Jiang, W. (2016). The Theory of IE Assembly Line Balance and Optimization. MMEBC 2016, Atlantis Press. https://www.atlantis-press.com/article/25858924.pdf
- [S14] King Saud Univ. ders notu (t.y.). Predetermined Motion Time Systems – part 2 (MTM). https://faculty.ksu.edu.sa/sites/default/files/7_pmts_ams_may01_17_-_p2.pdf
- [S17] Triki, H., Hachicha, W., Mellouli, A., Masmoudi, F. (2015). An Assembly Line Balancing Problem Automotive Cables. Management and Production Engineering Review 6(1), 59–66. DOI: 10.1515/mper-2015-0008
- [S18] Hamzadayı, A. (2022). Benders Decomposition Algorithm for Solving the Type-II Simple Assembly Line Balancing Problem with Zoning Restrictions. Yüzüncü Yıl Üniv. Fen Bilimleri Enst. Dergisi 27(2), 400–415. DOI: 10.53433/yyufbed.1080238
- [S19] Sgarbossa, F. (t.y.). Assembly Systems Design and Balancing (ders sunumu, NTNU TPK4191). https://jvatn.folk.ntnu.no/eLearning/TPK4191/slides/Fabio_AS_DesignAndBalancing.pdf
- [S20] King Saud Univ. IE 314 Operations Management II, Lecture 5: Assembly-Line Balancing (t.y.). https://faculty.ksu.edu.sa/sites/default/files/line_balancing.pdf
- [S21] MTM ASSOCIATION e. V. (t.y.). The brands of the MTM ASSOCIATION e. V. https://mtm.org/en/brands/our-brands
- [S22] Terkaj, W., Urgo, M. (t.y.). Virtual Learning Factory Toolkit – MTM / Formalise the process. https://virtualfactory.gitbook.io/vlft/tools/mtm/formalise
- [S23] Owensby, J. E., Summers, J. D. (2014). Assembly Time Estimation: Assembly Mate Based Structural Complexity Metric Predictive Modeling. Journal of Computing and Information Science in Engineering 14(1). https://open.clemson.edu/cedar_pubs/8
