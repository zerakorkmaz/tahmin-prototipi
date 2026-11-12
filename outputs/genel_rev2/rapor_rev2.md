> **Bu sonuçlar sentetik veriye dayanan bir demodur.** Ölçülmüş veri kullanılmamıştır; süreler literatürden ve VARSAYIM'lardan alınmıştır (bkz. `data/genel_parametreler_rev2.xlsx`).

# Genel Sürüm Rev2 – Zorluk Eki (Engelli Erişim) Eklenmiş Model

Rev1 (`outputs/genel/`) ile aynı yapı; fark: zor parça ve vida için engelli erişim eki. Ayrıntı ve karşılaştırma aşağıda.

## Soru: 'X takma' mı, 'takma' mı, hareket sayısı mı?

Ürünü tarif etmenin üç seviyesi var. MTM sistemleri de aynı hiyerarşiyi kullanır: MTM-1 temel hareketler seviyesinde, MTM-2 hareket dizileri seviyesinde, MTM-UAS temel işlemler seviyesindedir ve üst seviyelerin hepsi MTM-1'e dayanır [S21].

| Seviye | Örnek değişkenler | Artısı | Eksisi | Bu projede |
|---|---|---|---|---|
| 1. Ürüne özel kalem | pompa takma, hortum takma, sensör takma | Firma için en anlaşılır; tek ürün ailesinde iyi çalışır. | Başka ürüne taşınamaz: aynada 'pompa' yok. Her yeni ürün için yeni değişken ve yeni veri gerekir. | Washer tank sürümü (src/demo.py) |
| 2. Genel işlem tipi (önerilen) | kolay/zor parça yerleştir, vidala, geçme, esnek bağlantı, kontrol, makine süresi | Ürün ailesinden bağımsız; MTM-UAS'ın 'temel işlem' seviyesi [S21],[S22] ve DFA sınıflandırması [S7],[S8] ile aynı mantık. Değişken sayısı az, regresyon için az veri yeter. | Bir işlem tipinin içi ortalama süre kabul edilir; zor bir vida ile kolay vida farkı kaybolur (MTM-UAS'ın kendisi de temel hareket seviyesine göre daha az hassas [S22]). | Genel sürüm (rev1 ve rev2) |
| 3. Hareket bazlı (MTM-1) | uzan, kavra, taşı, konumla, bırak (TMU) | En taşınabilir ve en ayrıntılı; tüm üst MTM sistemleri buna dayanır [S21]. | Her ürün için eğitimli analist ve lisanslı tablolar gerekir; değişken sayısı çok fazla. Hareketler bilindiğinde süre zaten toplamla hesaplanır, regresyona gerek kalmaz. | Element sürelerinin kaynağı olarak kullanılmalı (firma MTM analizi yaparsa tablodaki süreler güncellenir) |

**Öneri:** Tahmin modeli **2. seviyede** (genel işlem tipi) kurulmalı. 'Pompa takma' yerine 'zor parça yerleştirme', 'hortum takma' yerine 'esnek bağlantı' denir; makine işlemleri saniye olarak girilir. Böylece aynı model washer tank ve ayna için çalışır, ürün ailesi yalnızca sayıları değiştirir. Hareket bazlı (MTM-1) seviye tahmin girdisi olarak değil, her işlem tipinin **süresini belirlemek** için kullanılmalı: firma bir işlem tipini MTM ile analiz ederse `ELEMENTLER` tablosundaki süre güncellenir ve script yeniden çalıştırılır.
- Benzer bir yaklaşımda ürün yapısından (parça bağlantı grafiği) montaj süresi tahmin edilmiş ve sonuçlar ±%25 içinde kalmıştır; aynı çalışma **eğitim verisindeki ürün çeşitliliğinin** kritik olduğunu vurgular [S23]. Bu yüzden gerçek veri toplanırken birden fazla ürün ailesinden ölçüm alınmalıdır.

## Rev2: zorluk eki (engelli erişim)

Aynı kategori içindeki işlerin süresi iki ayrı tepe etrafında toplanabilir (ör. zor parçaların bir kısmı ~8–9 sn, bir kısmı ~11–12 sn). Hepsini tek kategoriye koymak, katsayıyı ikisinin ortalamasına çeker ve yavaş alt grubu çok içeren ürünler sistematik olarak düşük tahmin edilir.
Rev2'de kategori bölünmez; yanına **'bunlardan kaçı engelli erişimli'** sayısı eklenir. Bu sayının katsayısı, iş başına **ek süreyi** verir. Bu, DFA'daki ceza mantığıdır: aynı vida engelli erişim ve kısıtlı görüşte 12 sn, kolay erişimde 6 sn sürer [S7].

| Ek | Değer | Kaynak/VARSAYIM |
|---|---|---|
| Vida – engelli erişim eki | +6.0 sn/adet | [S7] aynı vida engelli erişim+kısıtlı görüşte 12 sn (kod 59), kolay erişimli yeniden tasarımda 6 sn (kod 38) → ek 6 sn. |
| Zor parça – engelli erişim eki | +2.25 sn/adet | [S10]'dan türetildi: engelli erişimde yerleştirme 4,0–6,0 sn, orta hizalamada 2,0–3,5 sn → fark 0,5–4,0 sn, orta noktaların farkı 2,25 sn (genel çerçeve). |

**Ölçümde nasıl kullanılır:** Her vida ve zor parça için 'engelli erişim / kısıtlı görüş var mı?' sorusu kaydedilir. Katsayısı anlamlı çıkmazsa (p ≥ 0,05) ileri seçim bu değişkeni zaten almaz; yani ek, gerçekten fark yaratıyorsa modele girer.

### Eksiz ve ekli model karşılaştırması (eğitim 294 satır, ayrı test 106 satır)

| Model | Terim sayısı | Düz. R² (eğitim) | Test RMSE (sn) | Test ort. mutlak hata (sn) |
|---|---|---|---|---|
| Eksiz model (rev1 tipi) | 13 | 0.9872 | 9.04 | 6.88 |
| Ekli model (rev2) | 17 | 0.9950 | 5.51 | 4.28 |

**Sistematik sapma** (test kümesinde ortalama gerçek − tahmin; + ise model süreyi düşük tahmin ediyor):

| Grup | Eksiz model (rev1 tipi) | Ekli model (rev2) |
|---|---|---|
| engelli işlem yok (n=14) | -5.33 sn | -0.56 sn |
| 1–2 engelli işlem (n=36) | -2.48 sn | +1.21 sn |
| 3+ engelli işlem (n=56) | +4.71 sn | +1.05 sn |

Eksiz model, engelli işi çok olan ürünlerde süreyi düşük, hiç olmayanlarda yüksek tahmin eder; ekli model bu sapmayı büyük ölçüde kaldırır.

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
| vida_engelli_ek | 6.0 sn/adet (ek) | [S7] aynı vida engelli erişim+kısıtlı görüşte 12 sn (kod 59), kolay erişimli yeniden tasarımda 6 sn (kod 38) → ek 6 sn. |
| parca_zor_engelli_ek | 2.25 sn/adet (ek) | [S10]'dan türetildi: engelli erişimde yerleştirme 4,0–6,0 sn, orta hizalamada 2,0–3,5 sn → fark 0,5–4,0 sn, orta noktaların farkı 2,25 sn (genel çerçeve). |
| kontrol | 2.0 sn/nokta | VARSAYIM: MTM-UAS'ta görsel kontrol ayrı bir sınıf [S22]; sayısal değeri okunamadı. |
| zor_parca_vida | 2 vida/parça | VARSAYIM: her zor parça en fazla 2 vidasıyla birlikte aynı operatörce takılır (bağlı iş). |

## Ürün şablonları (arayüzde hazır)

| Şablon | govde_kg | parca_kolay | parca_zor | parca_zor_engelli | vida | vida_engelli | gecme | baglanti | kontrol | makine1_sn | makine2_sn | Eşleştirme |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Washer tank | 0.6 | 2 | 1 | 0 | 2 | 0 | 4 | 2 | 2 | 30 | 25 | zor parça = pompa; kolay = sensör, kapak; esnek bağlantı = hortum; geçme = klips; makine 1 = sıcak plaka kaynağı ([S1],[S2] 10–60 sn içinde 30 sn); makine 2 = sızdırmazlık testi ([S6] 20–30 sn içinde 25 sn). Rev2: engelli erişim yok (VARSAYIM). |
| Dış dikiz aynası | 0.9 | 3 | 2 | 1 | 4 | 2 | 6 | 2 | 3 | 0 | 15 | zor parça = ayar motoru, cam+tutucu; kolay = kapak, sinyal camı, conta; esnek bağlantı = kablo soketi; makine 1 yok; makine 2 = elektriksel fonksiyon testi 15 sn. Tüm sayılar VARSAYIM (aynaya özel süre kaynağı bulunamadı). Rev2: ayar motoru gövde içinde dar yerde takılır (1 engelli zor parça), 2 vida gövde içinden sıkılır (VARSAYIM). |

## Veri

- 400 satır (her operatör sayısı için 100), seed = 2024. Girdi aralıkları geniş tutuldu ki hem washer tank hem ayna gibi ürünler kapsansın; makine işlemleri %20 olasılıkla 0 (o üründe yok).
- 25 aday terim × 15–20 gözlem ≈ 315–420 satır → 400 seçildi.
- Çevrim süresi: işler sabit sırada, bağlı işler bölünemez blok (yükleme+makine, zor parça+vidaları); bloklar operatörlere en yüklü istasyonu en aza indirecek şekilde dağıtılır [S17]–[S20]; çevrim = en yüklü istasyon + N(0, 3.0²). **Makine süreleri operatöre bölünmez.**

| Operatör | Ort. denge kaybı | Maks | Çevrimin makine bloğuna dayandığı satır |
|---|---|---|---|
| 1 | %0.0 | %0.0 | %0 |
| 2 | %3.0 | %18.3 | %0 |
| 3 | %8.8 | %33.5 | %3 |
| 4 | %19.4 | %60.8 | %13 |

Operatör arttıkça çevrim uzun makine işleminin altına inemez; bu satırlarda operatör eklemek süreyi kısaltmaz. Bu yüzden aday listesine `maks_makine` (iki makine süresinden büyüğü) de eklendi.

## İleri seçim adımları

| Adım | Eklenen terim | p | R² | Düz. R² |
|---|---|---|---|---|
| 1 | 1/operator | 5.11e-115 | 0.7294 | 0.7287 |
| 2 | vida/operator | 6.45e-66 | 0.8711 | 0.8704 |
| 3 | maks_makine | 1.18e-38 | 0.9159 | 0.9153 |
| 4 | baglanti/operator | 3.33e-23 | 0.9345 | 0.9338 |
| 5 | parca_zor/operator | 6.15e-23 | 0.9488 | 0.9482 |
| 6 | gecme/operator | 2.43e-21 | 0.9593 | 0.9587 |
| 7 | makine2_sn/operator | 3.62e-19 | 0.9668 | 0.9663 |
| 8 | makine1_sn/operator | 1.71e-43 | 0.9797 | 0.9793 |
| 9 | vida_engelli/operator | 6.51e-49 | 0.9883 | 0.9881 |
| 10 | parca_kolay/operator | 1.49e-24 | 0.9911 | 0.9909 |
| 11 | kontrol/operator | 2.60e-18 | 0.9927 | 0.9925 |
| 12 | govde_kg/operator | 1.52e-06 | 0.9931 | 0.9929 |
| 13 | parca_zor_engelli/operator | 2.37e-06 | 0.9935 | 0.9933 |
| 14 | operator | 1.21e-06 | 0.9939 | 0.9937 |
| 15 | vida_engelli | 1.64e-03 | 0.9940 | 0.9938 |
| 16 | makine2_sn | 1.42e-03 | 0.9942 | 0.9939 |
| 17 | parca_zor | 6.82e-03 | 0.9943 | 0.9940 |
| 18 | govde_kg | 4.38e-02 | 0.9944 | 0.9941 |
| 19 | baglanti | 2.42e-02 | 0.9944 | 0.9942 |
| 20 | (durdu: en iyi aday kontrol, p=0.207) | 2.07e-01 | – | – |

## Son model

- R² = **0.9944**, düzeltilmiş R² = **0.9942**, artık std. sapma = 4.71 sn

| Terim | Katsayı | Std. hata | p |
|---|---|---|---|
| sabit | -6.782 | 3.169 | 3.30e-02 |
| 1/operator | 23.627 | 3.779 | 1.09e-09 |
| vida/operator | 10.027 | 0.193 | 8.82e-175 |
| maks_makine | 0.039 | 0.027 | 1.42e-01 |
| baglanti/operator | 8.932 | 0.484 | 1.08e-54 |
| parca_zor/operator | 6.908 | 0.633 | 2.68e-24 |
| gecme/operator | 3.422 | 0.135 | 2.58e-83 |
| makine2_sn/operator | 0.834 | 0.043 | 1.15e-58 |
| makine1_sn/operator | 0.977 | 0.031 | 2.98e-109 |
| vida_engelli/operator | 5.301 | 0.466 | 5.91e-26 |
| parca_kolay/operator | 2.900 | 0.193 | 1.88e-40 |
| kontrol/operator | 2.287 | 0.245 | 9.46e-19 |
| govde_kg/operator | 7.594 | 1.652 | 5.85e-06 |
| parca_zor_engelli/operator | 2.468 | 0.456 | 1.13e-07 |
| operator | 3.101 | 0.581 | 1.65e-07 |
| vida_engelli | 0.778 | 0.249 | 1.95e-03 |
| makine2_sn | 0.103 | 0.029 | 5.19e-04 |
| parca_zor | 0.941 | 0.347 | 7.05e-03 |
| govde_kg | -2.191 | 0.962 | 2.33e-02 |
| baglanti | -0.659 | 0.291 | 2.42e-02 |

**Denklem:** `çevrim_sn = -6.78 + 23.63·1/operator + 10.03·vida/operator + 0.04·maks_makine + 8.93·baglanti/operator + 6.91·parca_zor/operator + 3.42·gecme/operator + 0.83·makine2_sn/operator + 0.98·makine1_sn/operator + 5.30·vida_engelli/operator + 2.90·parca_kolay/operator + 2.29·kontrol/operator + 7.59·govde_kg/operator + 2.47·parca_zor_engelli/operator + 3.10·operator + 0.78·vida_engelli + 0.10·makine2_sn + 0.94·parca_zor − 2.19·govde_kg − 0.66·baglanti`

## Kısa yorum

- '/operator' terimleri elle yapılan ve operatörler arasında paylaşılabilen işleri, bölünmemiş terimler (özellikle makine süreleri ve `maks_makine`) operatör sayısıyla kısalmayan kısmı temsil eder.
- Makine darboğazı gerçekte bir 'en büyüğü' (max) ilişkisidir; doğrusal regresyon bunu `maks_makine` ve bölünmemiş makine terimleriyle ancak yaklaşık yakalar. 3–4 operatörlü ve uzun makine süreli ürünlerde hata büyüyebilir; gerekirse parçalı (ör. 'çevrim = max(elle iş/n, makine)') bir model denenebilir.
- Model sentetik veriyi, onu üreten formülden öğrendiği için R² yüksek; gerçek veriyle düşecektir.
- Bu sürümün katsayıları ürün ailesine bağlı değil. Yeni bir ürün ailesi için yalnızca işlem sayılarını girmek yeterli; ancak gerçek veride her ailenin kendine özgü farkları için bir 'aile' değişkeni eklemek gerekebilir.

## Dosyalar

- `src/genel_demo_rev2.py` – hepsini yeniden üretir
- `data/genel_parametreler_rev2.xlsx`
- `outputs/genel_rev2/veri_seti_rev2.xlsx`, `model_rev2.json`, `index_rev2.html`
- Önceki sürüm (rev1) değişmeden duruyor: `src/genel_demo.py`, `outputs/genel/`

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
