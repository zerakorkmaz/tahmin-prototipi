"""
Washer tank montaj hattı – çevrim süresi tahmin DEMOSU.

Bu tek script baştan sona şunları yapar:
  1. Parametre tablosunu yazar         -> data/parametreler.xlsx
  2. Sentetik veri üretir              -> outputs/veri_seti.xlsx
  3. İleri (forward stepwise) regresyon -> outputs/rapor.md, outputs/model.json
  4. Arayüzü oluşturur                 -> outputs/index.html
  5. Python ve HTML tahminlerini karşılaştırır (Playwright varsa)

Çalıştırma (depo kök klasöründen):  python3 src/demo.py
Parametreleri değiştirmek için aşağıdaki AYARLAR bölümünü düzenleyip
script'i yeniden çalıştırmanız yeterli.

NOT: Ölçülmüş veri yoktur. Tüm sayılar literatür ve VARSAYIM'lardan gelir.
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

KOK = Path(__file__).resolve().parent.parent
DATA = KOK / "data"
OUT = KOK / "outputs"

# =====================================================================
# AYARLAR
# =====================================================================
SEED = 42
SATIR_PER_OPERATOR = 60          # 4 operatör seviyesi x 60 = 240 satır
GIRIS_P_ESIGI = 0.05             # ileri seçimde değişken alma eşiği
GURULTU_SD = 3.0                 # sn, normal gürültünün std. sapması (VARSAYIM)

# Kaynak kısaltmaları (tam künye KAYNAKLAR sözlüğünde)
# Her parametre: min, tipik, max, birim, kaynak/VARSAYIM açıklaması
PARAMETRELER = [
    # --- Literatürden okunan referans değerler (doğrudan modelde kullanılmayanlar dahil) ---
    dict(parametre="Sıcak plaka kaynağı – toplam çevrim", min=10, tipik=None, max=60, birim="sn",
         kaynak="[S1] 'cycle time ... ranges from 10 seconds to nearly a minute'; [S2] '10 seconds to minutes'"),
    dict(parametre="Sıcak plaka kaynağı – ısıtma süresi", min=1.5, tipik=None, max=20, birim="sn",
         kaynak="[S1] 'ranging from 1.5 seconds to 20 seconds'"),
    dict(parametre="Titreşim kaynağı – kaynak süresi (büyük birleşim)", min=5, tipik=None, max=15, birim="sn",
         kaynak="[S3] 'around 5-15 seconds'; [S4] ortalama 10–15 sn kaynak + ~15 sn bekleme"),
    dict(parametre="Ultrasonik kaynak – kaynak süresi", min=0.2, tipik=None, max=2, birim="sn",
         kaynak="[S5] '0.2 to 2 seconds (maximum of 3 seconds)'"),
    dict(parametre="Sızdırmazlık testi – benzer parçalar (radyatör, yağ soğutucu vb.)", min=20, tipik=None, max=30, birim="sn",
         kaynak="[S6] 'less than 20 to 30 seconds per part'; yakıt tankı için 45–65 sn"),
    dict(parametre="DFA ideal montaj süresi (parça başı)", min=None, tipik=3, max=None, birim="sn",
         kaynak="[S9] Boothroyd-Dewhurst: 1 sn tutma + 1 sn yerleştirme + 1 sn sabitleme"),
    dict(parametre="Vida – elle tutma süresi (kod 11)", min=None, tipik=1.8, max=None, birim="sn",
         kaynak="[S7], [S8] DFA çalışma tablosu"),
    dict(parametre="Vida – yerleştirme+sıkma (kod 38 / 39 / 59)", min=6.0, tipik=8.0, max=12.0, birim="sn",
         kaynak="[S7] kod 38=6 sn, kod 59 (engelli erişim)=12 sn; [S8] kod 39=8 sn"),
    dict(parametre="Denge kaybı değerlendirme bandı", min=10, tipik=None, max=20, birim="%",
         kaynak="[S11] Bd≤%10 mükemmel, %10–20 iyi, ≥%20 kötü; örnek hat %41,1 → %15"),
    dict(parametre="Denge kaybı – otomotiv yan sanayi örneği", min=25, tipik=None, max=58, birim="%",
         kaynak="[S12] dikiş hattı: %58 → yeniden dengeleme sonrası %25"),
    dict(parametre="Hat verimi hedefi (elle montaj)", min=85, tipik=None, max=90, birim="%",
         kaynak="[S13] '85–90%: standart hedef' (uygulayıcı makalesi, hakemsiz)"),
    dict(parametre="Hat dengeleme – iş bölünemezliği", min=None, tipik=None, max=None, birim="–",
         kaynak="[S17] model varsayımı: 'The task cannot be subdivided.' ve 'precedence relationship ... is "
                "known and invariable'; ayrıca zoning (aynı/ayrı istasyon) kısıtları"),
    dict(parametre="Hat dengeleme – aynı istasyon (pozitif zoning) kısıtı", min=None, tipik=None, max=None, birim="–",
         kaynak="[S18] bazı işler 'have to be assigned to the same workstation' (uyumlu işler) ya da aynı "
                "istasyonda yapılamaz (uyumsuz işler)"),
    dict(parametre="Hat dengeleme – öncelik kısıtı", min=None, tipik=None, max=None, birim="–",
         kaynak="[S19] 'no task is assigned to an earlier station than its predecessor'; çevrim süresi = en "
                "yüklü istasyon (örnek: c_min = 59 sn → 3600/59 = 61 adet/saat)"),
    dict(parametre="Çevrim süresinin alt sınırı = en uzun bölünemez iş", min=None, tipik=None, max=None, birim="–",
         kaynak="[S20] çözümlü örnek: günlük çevrim sayısı en uzun operasyonla (8 dk) sınırlanıyor"),
    dict(parametre="1 TMU", min=None, tipik=0.036, max=None, birim="sn",
         kaynak="[S14] 1 TMU = 0,036 sn (MTM tablo değerlerine erişilemedi, bkz. not)"),
    dict(parametre="Cam suyu deposu hacmi (binek araç)", min=2.8, tipik=None, max=6.2, birim="L",
         kaynak="[S16] 2,8 L; far yıkamalı 6,2 L. [S15] 3,2 L"),
]

# --- Modelde kullanılan element süreleri (sentetik veriyi üreten 'gerçek' değerler) ---
ELEMENTLER = {
    # anahtar: (min, tipik, max, birim, kaynak/VARSAYIM)
    "sabit_is":       (10, 15, 20, "sn/ürün",
                       "VARSAYIM: etiketleme, görsel kontrol, kutulama gibi üründen bağımsız işler."),
    "tasima_per_l":   (1.0, 2.0, 3.0, "sn/L",
                       "VARSAYIM: depo ~4 kez alınıp konur (kaynak, montaj, test, kutu). [S10] büyük/ağır parça "
                       "tutma 3,5–5 sn diyor; hacimle orantılı artış varsayıldı."),
    "kaynak_sabit":   (10, 20, 30, "sn/ürün",
                       "VARSAYIM: sıcak plaka çevriminin uzunluktan bağımsız kısmı (ısıtma+geçiş+tutma). "
                       "Toplam [S1],[S2]'deki 10–60 sn aralığında kalacak şekilde seçildi."),
    "kaynak_per_m":   (5, 10, 20, "sn/m",
                       "VARSAYIM: uzun kaynak hattı = büyük plaka, daha uzun ısıtma/soğuma. "
                       "Sıcak plakada tüm birleşim aynı anda kaynar; uzunluk etkisi zayıf tutuldu."),
    "pompa":          (6.0, 8.5, 12.0, "sn/adet",
                       "VARSAYIM ([S8]'den türetildi): tutma 1,95 sn + bastırarak yerleştirme 6,5 sn (kod 08)."),
    "sensor":         (4.0, 6.0, 9.0, "sn/adet",
                       "VARSAYIM: seviye sensörü contaya geçirilir + soket; pompadan biraz kısa kabul edildi."),
    "vida":           (7.8, 9.8, 13.8, "sn/adet",
                       "[S7],[S8]: tutma 1,8 sn + yerleştirme/sıkma 6 / 8 / 12 sn (kod 38 / 39 / 59)."),
    "klips":          (3.0, 3.5, 4.5, "sn/adet",
                       "[S10] tutma 1,5–2,0 + geçmeli (snap-fit) yerleştirme 1,5–2,5 sn. "
                       "Not: kaynak bunu 'genel çerçeve, doğrulanmış tablo değil' diye belirtiyor."),
    "hortum":         (6.0, 10.0, 15.0, "sn/adet",
                       "VARSAYIM: esnek parça tutma ([S10] 3–5 sn) + rakora geçirme + kelepçe. "
                       "Hortum için sayısal kaynak bulunamadı."),
    "sizdirmazlik":   (20, 25, 30, "sn/ürün",
                       "[S6] benzer otomotiv parçaları 20–30 sn; tipik değer orta nokta (VARSAYIM)."),
    "denge_kaybi":    (None, None, None, "oran",
                       "Varsayılmıyor, HESAPLANIYOR: öncelik sırası + bağlı (bölünemez) işler kısıtıyla hat her "
                       "ürün için optimum dengelenir; denge kaybı = n·C / iş içeriği − 1. Sonuç [S11] %10–20 "
                       "bandıyla karşılaştırılır."),
    "vida_per_braket": (None, 2, None, "vida/braket",
                       "VARSAYIM: vidalar braketleri tutar; bir braket ve onun 2 vidası aynı operatörce takılır "
                       "(bağlı iş). Tek kalan vida tek başına bir blok."),
    "gurultu_sd":     (None, GURULTU_SD, None, "sn",
                       "VARSAYIM: operatör performans farkı, küçük duruşlar vb. için normal gürültü."),
}

# --- Ürün girdileri: veri üretim aralıkları ve arayüz varsayılanı (tipik washer tank) ---
GIRDILER = {
    # ad: (etiket, birim, min, max, varsayılan, tamsayı mı, kaynak/VARSAYIM)
    "hacim_l":   ("Depo hacmi", "L", 2.5, 6.5, 3.5, False,
                  "[S15],[S16] 2,8–6,2 L; aralık biraz genişletildi (VARSAYIM)."),
    "kaynak_m":  ("Kaynak dikiş uzunluğu", "m", 0.6, 1.6, 1.0, False,
                  "VARSAYIM: 3–6 L'lik depoların birleşim çevresi tahmini."),
    "vida":      ("Vida sayısı", "adet", 0, 6, 2, True, "VARSAYIM"),
    "klips":     ("Klips sayısı", "adet", 2, 8, 4, True, "VARSAYIM"),
    "hortum":    ("Hortum bağlantısı", "adet", 1, 4, 2, True, "VARSAYIM"),
    "pompa":     ("Pompa sayısı", "adet", 1, 2, 1, True, "VARSAYIM (ön/arka cam için 2 pompa olabilir)"),
    "sensor":    ("Seviye sensörü", "adet", 0, 2, 1, True, "VARSAYIM"),
    "operator":  ("Operatör sayısı", "kişi", 1, 4, 2, True, "Kullanıcı isteği: 1–4"),
}
URUN_DEGISKENLERI = [k for k in GIRDILER if k != "operator"]

KAYNAKLAR = {
    "S1": "Sprovieri, J. (2022). What's New With Hot-Plate Welding. ASSEMBLY Magazine, 13.09.2022. "
          "https://www.assemblymag.com/articles/97311-whats-new-with-hot-plate-welding",
    "S2": "Wikipedia katkıcıları. Hot plate welding (9 Eylül 2025 sürümü). https://en.wikipedia.org/wiki/Hot_plate_welding",
    "S3": "TWI Ltd. (t.y.). What is vibration welding of thermoplastics? "
          "https://www.twi-global.com/technical-knowledge/faqs/faq-what-is-vibration-welding-of-thermoplastics",
    "S4": "Weber, A. (2021). Vibration Welding Adapts to Shifting Demands. ASSEMBLY Magazine, 08.02.2021. "
          "https://www.assemblymag.com/articles/96123-vibration-welding-adapts-to-shifting-demands",
    "S5": "Telsonic AG (t.y.). Ultrasonic joining technology systems. "
          "https://www.telsonic.com/en/ultrasound-technology/ultrasonic-joining-technology-systems",
    "S6": "Sprovieri, J. (2009). Leak Testing Auto Parts. ASSEMBLY Magazine, 27.03.2009. "
          "https://www.assemblymag.com/articles/86667-leak-testing-auto-parts",
    "S7": "Chang, G., Peterson, W. (2010). Design for Assembly in Manufacturing Engineering Technology Program: "
          "Experience and Success. ASEE Annual Conference, AC 2010-2309 (tablolar: BDI Product Design for "
          "Assembly Handbook, 1989). https://peer.asee.org/design-for-assembly-in-manufacturing-engineering-"
          "technology-program-experience-and-success.pdf",
    "S8": "HKUST IELM 317 ders notu (t.y.). Design For Manufacturing/Assembly (DFM, DFA, DFMA); "
          "Boothroyd & Dewhurst (1991)'e atıfla. https://ieda.ust.hk/dfaculty/ajay/courses/ielm317/lecs/dfm/dfm.pdf",
    "S9": "Teni, M.H.M., Naroh, A., Maliki, K.A.A., Tukiran, A. (2019). Design Development of a Coffee Maker "
          "using Design for Assembly Method. IJEAT 9(2). DOI: 10.35940/ijeat.B4942.129219",
    "S10": "Guns, B. (t.y.). Design for Manufacturing (DFM). Engineering LibreTexts, Northeast Wisconsin "
           "Technical College. https://eng.libretexts.org/Courses/Northeast_Wisconsin_Technical_College/"
           "Design_for_Various_Manufacturing_Methods/01:_Design_for_Manufacturing_(DFM)",
    "S11": "Yin, M., Jiang, W. (2016). The Theory of IE Assembly Line Balance and Optimization. "
           "MMEBC 2016, Atlantis Press. https://www.atlantis-press.com/article/25858924.pdf",
    "S12": "Govender, P., Dewa, M. (2022). Use of Kaizen Principle and Line Balancing Technique for Process "
           "Improvement in the Assembly of Automotive Components. South African Journal of Industrial "
           "Engineering 33(3), 69–82. DOI: 10.7166/33-3-2790",
    "S13": "Rajadurai, R. (2026). Line Balancing Calculation: Formula & Worked Example. MetricMech. "
           "https://metricmech.com/articles/line-balancing-calculation",
    "S14": "King Saud Univ. ders notu (t.y.). Predetermined Motion Time Systems – part 2 (MTM). "
           "https://faculty.ksu.edu.sa/sites/default/files/7_pmts_ams_may01_17_-_p2.pdf",
    "S15": "Tesla (t.y.). Model 3 – Topping Up Windshield Washer Fluid. https://service.tesla.com/docs/Public/"
           "diy/model3/en_us/GUID-3A80A08E-9DCB-45A4-9796-BCD9153A4A00.html",
    "S16": "VWmanual.ru (t.y.). Windscreen washer fluid level (Passat B5, bağımsız el kitabı sitesi). "
           "https://vwmanual.ru/en/passat/b5/main/checks/uroven-zhidkosti-stekloomyvatelya",
    "S17": "Triki, H., Hachicha, W., Mellouli, A., Masmoudi, F. (2015). An Assembly Line Balancing Problem "
           "Automotive Cables. Management and Production Engineering Review 6(1), 59–66. DOI: 10.1515/mper-2015-0008",
    "S18": "Hamzadayı, A. (2022). Benders Decomposition Algorithm for Solving the Type-II Simple Assembly Line "
           "Balancing Problem with Zoning Restrictions. Yüzüncü Yıl Üniv. Fen Bilimleri Enst. Dergisi 27(2), "
           "400–415. DOI: 10.53433/yyufbed.1080238",
    "S19": "Sgarbossa, F. (t.y.). Assembly Systems Design and Balancing (ders sunumu, NTNU TPK4191). "
           "https://jvatn.folk.ntnu.no/eLearning/TPK4191/slides/Fabio_AS_DesignAndBalancing.pdf",
    "S20": "King Saud Univ. IE 314 Operations Management II, Lecture 5: Assembly-Line Balancing (t.y.). "
           "https://faculty.ksu.edu.sa/sites/default/files/line_balancing.pdf",
}

# --- Öncelik sırası ve bağlı işler (VARSAYIM: washer tank montaj mantığı) ---
# Sıra: kaynak → pompa(+hortumu) → sensör → diğer hortumlar → braket+vidalar → klipsler → test → son işlemler.
# Basitlik için öncelik ilişkisi tek bir zincir (seri sıra) kabul edildi: her iş bir öncekinden sonra gelir,
# bu yüzden bir operatöre ancak art arda gelen işler verilebilir. Bir 'blok' bölünemez; tek operatöre gider.
IS_LISTESI_ACIKLAMA = [
    ("1", "Depoyu kaynak makinesine yükle + sıcak plaka kaynağı", "Bölünemez (makineyi besleyen operatör kaynağı da yapar)",
     "VARSAYIM; makine işi olduğu için ikiye bölünemez [S17]"),
    ("2", "Her pompa + o pompanın hortum bağlantısı", "Bağlı iş: aynı operatör (pozitif zoning)",
     "VARSAYIM; pompa çıkışına hortum, pompayı takan kişi tarafından bağlanır [S18]"),
    ("3", "Her seviye sensörü", "Tek iş", "VARSAYIM"),
    ("4", "Kalan her hortum bağlantısı", "Tek iş", "VARSAYIM"),
    ("5", "Her braket + vidaları (2 vida/braket)", "Bağlı iş: aynı operatör", "VARSAYIM [S18]"),
    ("6", "Her klips", "Tek iş", "VARSAYIM"),
    ("7", "Depoyu test cihazına yükle + sızdırmazlık testi", "Bölünemez (makine işi)", "VARSAYIM [S17]"),
    ("8", "Etiket, görsel kontrol, kutulama + son taşıma", "Tek iş", "VARSAYIM"),
]


def t(anahtar):
    """Elementin tipik süresi."""
    return ELEMENTLER[anahtar][1]


# =====================================================================
# 1) PARAMETRE TABLOSU
# =====================================================================
def excel_bicimle(ws, genislikler=None):
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="2F5D8A")
        c.alignment = Alignment(vertical="center", wrap_text=True)
    for i, col in enumerate(ws.columns, start=1):
        w = (genislikler or {}).get(i)
        if w is None:
            w = min(60, max(10, max(len(str(c.value or "")) for c in col) + 2))
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"


def parametre_tablosu_yaz():
    satirlar = []
    for p in PARAMETRELER:
        satirlar.append(dict(grup="Literatür referansı", **p))
    for k, (mn, tp, mx, birim, kay) in ELEMENTLER.items():
        satirlar.append(dict(grup="Modelde kullanılan element", parametre=k, min=mn, tipik=tp, max=mx,
                             birim=birim, kaynak=kay))
    for k, (et, birim, mn, mx, vs, _, kay) in GIRDILER.items():
        satirlar.append(dict(grup="Ürün girdisi (veri aralığı)", parametre=f"{k} ({et})", min=mn, tipik=vs,
                             max=mx, birim=birim, kaynak=kay))
    df = pd.DataFrame(satirlar).rename(columns={"kaynak": "kaynak/VARSAYIM"})
    kay = pd.DataFrame([dict(kod=k, kunye=v) for k, v in KAYNAKLAR.items()])
    notlar = pd.DataFrame({"not": [
        "Tüm kaynaklar bu çalışmada açılıp okunmuştur; tırnak içindeki ifadeler kaynaktan aynen alınmıştır.",
        "MTM-1 / MTM-UAS tablo değerleri: açık erişimli kaynaklarda tablolar resim olarak ya da telif "
        "kısıtlı olduğu için okunamadı. Bu yüzden element süreleri Boothroyd-Dewhurst DFA tablolarından alındı.",
        "Pompa, sensör ve hortum için doğrudan sayısal kaynak bulunamadı → VARSAYIM.",
        "Washer tank için doğrudan sızdırmazlık testi süresi bulunamadı; benzer otomotiv parçaları kullanıldı.",
        "Öncelik sırası ve bağlı iş grupları (is_listesi_oncelik sayfası) gerçek bir hattan değil, montaj "
        "mantığından türetilmiş VARSAYIM'lardır; kısıt türleri [S17]–[S20] literatüründen alınmıştır.",
    ]})
    DATA.mkdir(exist_ok=True)
    yol = DATA / "parametreler.xlsx"
    with pd.ExcelWriter(yol, engine="openpyxl") as xw:
        df.to_excel(xw, sheet_name="parametreler", index=False)
        kay.to_excel(xw, sheet_name="kaynaklar", index=False)
        notlar.to_excel(xw, sheet_name="notlar", index=False)
        isl = pd.DataFrame(IS_LISTESI_ACIKLAMA, columns=["sira", "is_blogu", "kisit", "kaynak/VARSAYIM"])
        isl.to_excel(xw, sheet_name="is_listesi_oncelik", index=False)
        excel_bicimle(xw.sheets["is_listesi_oncelik"], {2: 55, 3: 55, 4: 70})
        excel_bicimle(xw.sheets["parametreler"], {1: 26, 2: 46, 7: 90})
        excel_bicimle(xw.sheets["kaynaklar"], {2: 140})
        excel_bicimle(xw.sheets["notlar"], {1: 140})
        for ws in (xw.sheets["parametreler"],):
            for row in ws.iter_rows(min_row=2):
                for c in row:
                    c.alignment = Alignment(wrap_text=True, vertical="top")
    return yol


# =====================================================================
# 2) SENTETİK VERİ
# =====================================================================
def is_icerigi(d):
    """Toplam iş içeriği (sn) = Σ (element sayısı × element süresi)."""
    return (t("sabit_is")
            + t("tasima_per_l") * d["hacim_l"]
            + t("kaynak_sabit") + t("kaynak_per_m") * d["kaynak_m"]
            + t("pompa") * d["pompa"]
            + t("sensor") * d["sensor"]
            + t("vida") * d["vida"]
            + t("klips") * d["klips"]
            + t("hortum") * d["hortum"]
            + t("sizdirmazlik"))


def is_bloklari(d):
    """Ürünün iş bloklarını öncelik sırasıyla döndürür: [(ad, süre_sn), ...].
    Her blok bölünemez; tek bir operatöre atanır. Toplamı is_icerigi(d)'ye eşittir."""
    tl = t("tasima_per_l") * d["hacim_l"]
    b = [("Yükleme+kaynak", 0.5 * tl + t("kaynak_sabit") + t("kaynak_per_m") * d["kaynak_m"])]
    pompa_hortum = min(d["pompa"], d["hortum"])
    for i in range(d["pompa"]):
        b.append((f"Pompa{i + 1}" + ("+hortum" if i < pompa_hortum else ""),
                  t("pompa") + (t("hortum") if i < pompa_hortum else 0)))
    for i in range(d["sensor"]):
        b.append((f"Sensör{i + 1}", t("sensor")))
    for i in range(d["hortum"] - pompa_hortum):
        b.append((f"Hortum{i + 1}", t("hortum")))
    vpb = ELEMENTLER["vida_per_braket"][1]
    kalan = d["vida"]
    j = 0
    while kalan > 0:
        k = min(vpb, kalan)
        j += 1
        b.append((f"Braket{j}({k} vida)", t("vida") * k))
        kalan -= k
    for i in range(d["klips"]):
        b.append((f"Klips{i + 1}", t("klips")))
    b.append(("Yükleme+test", 0.25 * tl + t("sizdirmazlik")))
    b.append(("Etiket+kutulama", 0.25 * tl + t("sabit_is")))
    return b


def hat_dengele(sureler, n):
    """Seri öncelik zincirindeki blokları n operatöre (istasyona) art arda gruplar halinde böler ve
    en yüklü istasyonu en aza indirir (tam çözüm, dinamik programlama).
    Döndürür: (çevrim süresi = en yüklü istasyon, istasyon yükleri listesi)."""
    k = len(sureler)
    n = min(n, k)
    on = np.concatenate([[0.0], np.cumsum(sureler)])
    INF = float("inf")
    dp = [[INF] * (k + 1) for _ in range(n + 1)]
    kes = [[0] * (k + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0
    for s in range(1, n + 1):
        for i in range(1, k + 1):
            for j in range(s - 1, i):
                v = max(dp[s - 1][j], on[i] - on[j])
                if v < dp[s][i]:
                    dp[s][i], kes[s][i] = v, j
    yukler, i = [], k
    for s in range(n, 0, -1):
        j = kes[s][i]
        yukler.append(on[i] - on[j])
        i = j
    return dp[n][k], yukler[::-1]


def veri_uret():
    rng = np.random.default_rng(SEED)
    satirlar = []
    for n in range(1, 5):
        for _ in range(SATIR_PER_OPERATOR):
            d = {}
            for k in URUN_DEGISKENLERI:
                _, _, mn, mx, _, tam, _ = GIRDILER[k]
                d[k] = int(rng.integers(mn, mx + 1)) if tam else round(float(rng.uniform(mn, mx)), 2)
            d["operator"] = n
            bloklar = is_bloklari(d)
            sureler = [s for _, s in bloklar]
            C, yukler = hat_dengele(sureler, n)
            W = is_icerigi(d)
            assert abs(W - sum(sureler)) < 1e-9
            enb = max(bloklar, key=lambda x: x[1])
            d["is_icerigi_sn"] = round(W, 2)
            d["en_uzun_bagli_is"] = enb[0]
            d["en_uzun_bagli_is_sn"] = round(enb[1], 2)
            d["istasyon_yukleri_sn"] = " | ".join(f"{y:.1f}" for y in yukler)
            d["cevrim_gurultusuz_sn"] = round(C, 2)
            d["denge_kaybi"] = round(n * C / W - 1, 4)
            d["cevrim_suresi_sn"] = round(C + float(rng.normal(0, GURULTU_SD)), 2)
            d["kaynak"] = "sentetik"
            satirlar.append(d)
    df = pd.DataFrame(satirlar)
    df.insert(0, "urun_id", [f"V{i:03d}" for i in range(1, len(df) + 1)])
    return df


# =====================================================================
# 3) İLERİ (FORWARD STEPWISE) REGRESYON
# =====================================================================
def aday_terimler():
    """Aday terimler: ürün değişkenleri, n, 1/n ve (değişken / n) etkileşimleri."""
    adaylar = {}
    for k in URUN_DEGISKENLERI:
        adaylar[k] = dict(tur="x", degisken=k)
    adaylar["operator"] = dict(tur="x", degisken="operator")
    adaylar["1/operator"] = dict(tur="ters", degisken="operator")
    for k in URUN_DEGISKENLERI:
        adaylar[f"{k}/operator"] = dict(tur="bolu_n", degisken=k)
    return adaylar


def terim_hesapla(tanim, girdi):
    """Tek bir terimin değeri. girdi: dict ya da DataFrame."""
    n = girdi["operator"]
    if tanim["tur"] == "x":
        return girdi[tanim["degisken"]]
    if tanim["tur"] == "ters":
        return 1.0 / n
    if tanim["tur"] == "bolu_n":
        return girdi[tanim["degisken"]] / n
    raise ValueError(tanim)


def ileri_secim(df, y_adi="cevrim_suresi_sn"):
    adaylar = aday_terimler()
    X_tum = pd.DataFrame({ad: terim_hesapla(tn, df) for ad, tn in adaylar.items()})
    y = df[y_adi]
    secilen, adimlar = [], []
    onceki_adj = -np.inf
    while True:
        en_iyi = None
        for ad in X_tum.columns:
            if ad in secilen:
                continue
            m = sm.OLS(y, sm.add_constant(X_tum[secilen + [ad]])).fit()
            p = m.pvalues[ad]
            if en_iyi is None or p < en_iyi[1]:
                en_iyi = (ad, p, m)
        if en_iyi is None:
            break
        ad, p, m = en_iyi
        if p >= GIRIS_P_ESIGI or m.rsquared_adj <= onceki_adj:
            adimlar.append(dict(adim=len(adimlar) + 1, eklenen=f"(durdu: en iyi aday {ad}, p={p:.3g})",
                                p=p, r2=None, adj_r2=None))
            break
        secilen.append(ad)
        onceki_adj = m.rsquared_adj
        adimlar.append(dict(adim=len(adimlar) + 1, eklenen=ad, p=p, r2=m.rsquared, adj_r2=m.rsquared_adj))
    final = sm.OLS(y, sm.add_constant(X_tum[secilen])).fit()
    return final, secilen, adaylar, adimlar


def model_json_olustur(final, secilen, adaylar):
    kullanilan = []
    for ad in secilen:
        v = adaylar[ad]["degisken"]
        if v not in kullanilan:
            kullanilan.append(v)
    if "operator" not in kullanilan:   # arayüzde operatör her zaman seçilebilsin
        kullanilan.append("operator")
    girdiler = []
    for k in GIRDILER:
        if k not in kullanilan:
            continue
        et, birim, mn, mx, vs, tam, _ = GIRDILER[k]
        girdiler.append(dict(ad=k, etiket=et, birim=birim, min=mn, max=mx, varsayilan=vs, tamsayi=tam,
                             adim=1 if tam else 0.1))
    donusum_aciklama = {"x": "x", "ters": "1/operator", "bolu_n": "x/operator"}
    return dict(
        aciklama="Demo – sentetik veriyle eğitilmiş çevrim süresi modeli (sn). "
                 "tahmin = sabit + Σ katsayı × terim",
        hedef="cevrim_suresi_sn",
        sabit=float(final.params["const"]),
        terimler=[dict(ad=ad, degisken=adaylar[ad]["degisken"], donusum=adaylar[ad]["tur"],
                       donusum_formul=donusum_aciklama[adaylar[ad]["tur"]].replace("x", adaylar[ad]["degisken"])
                       if adaylar[ad]["tur"] != "ters" else "1/operator",
                       katsayi=float(final.params[ad])) for ad in secilen],
        girdiler=girdiler,
        r2=float(final.rsquared), duzeltilmis_r2=float(final.rsquared_adj), n_gozlem=int(final.nobs),
        hat=dict(
            aciklama="Operatör iş dağılımı: regresyon değil; literatür/VARSAYIM element süreleri, öncelik "
                     "sırası ve bağlı iş kısıtıyla optimum dengeleme.",
            element_sn={k: v[1] for k, v in ELEMENTLER.items() if isinstance(v[1], (int, float))},
            vida_per_braket=ELEMENTLER["vida_per_braket"][1],
            varsayilan={k: v[4] for k, v in GIRDILER.items()},
        ),
    )


def python_tahmin(model, girdi):
    y = model["sabit"]
    for tm in model["terimler"]:
        y += tm["katsayi"] * terim_hesapla(dict(tur=tm["donusum"], degisken=tm["degisken"]), girdi)
    return y


# =====================================================================
# RAPOR
# =====================================================================
def rapor_yaz(df, final, secilen, adimlar, model, aday_sayisi):
    s = []
    s.append("> **Bu sonuçlar sentetik veriye dayanan bir demodur.** Ölçülmüş veri kullanılmamıştır; "
             "element süreleri literatürden ve VARSAYIM'lardan alınmıştır (bkz. `data/parametreler.xlsx`).\n")
    s.append("# Çevrim Süresi Tahmin Modeli – Demo Raporu\n")
    s.append("## Veri\n")
    s.append(f"- {len(df)} satır sentetik ürün varyantı (her operatör sayısı 1–4 için {SATIR_PER_OPERATOR} satır), "
             f"random seed = {SEED}.")
    s.append(f"- Satır sayısı gerekçesi: {aday_sayisi} aday terim var. Yaygın kural olan 'aday değişken başına "
             f"en az 10–15 gözlem' ile 160–240 satır gerekir; üst sınır seçildi ve operatör seviyeleri dengeli tutuldu.")
    s.append("- Üretim formülü: `çevrim = iş_içeriği / n × (1 + denge_kaybı) + N(0, "
             f"{GURULTU_SD}²)`.")
    s.append("- **Öncelik ve bağlı iş kısıtı:** İşler sabit bir sırayla yapılır (kaynak → pompa+hortum → sensör → "
             "hortumlar → braket+vidalar → klipsler → test → kutulama). Bağlı işler (yükleme+kaynak, pompa+kendi "
             "hortumu, braket+vidaları, yükleme+test) tek blok sayılır ve **farklı operatörlere bölünemez** "
             "[S17], [S18]. Her ürün için bloklar n operatöre sırayı bozmadan, en yüklü istasyonu en aza "
             "indirecek şekilde (tam çözüm) dağıtılır. Çevrim süresi en yüklü istasyonun süresidir [S19], bu "
             "yüzden **en uzun bağlı işin altına inemez** [S20].")
    s.append("- Bu yüzden denge kaybı artık varsayılmıyor, kısıtlardan **hesaplanıyor**: "
             "`denge_kaybı = n × çevrim / iş_içeriği − 1`.\n")
    s.append("| Operatör | Ort. denge kaybı | Min | Maks | Çevrim / en uzun bağlı iş (ort. – min) |")
    s.append("|---|---|---|---|---|")
    for n_, g in df.groupby("operator"):
        oran = g["cevrim_gurultusuz_sn"] / g["en_uzun_bagli_is_sn"]
        s.append(f"| {n_} | %{100 * g.denge_kaybi.mean():.1f} | %{100 * g.denge_kaybi.min():.1f} | "
                 f"%{100 * g.denge_kaybi.max():.1f} | {oran.mean():.2f} – {oran.min():.2f} |")
    s.append("\nLiteratürde %10–20 denge kaybı 'iyi', %20 üstü 'kötü' sayılıyor [S11]. Operatör sayısı arttıkça "
             "kısıtlar yüzünden kaybın büyümesi beklenen bir sonuç. Son sütun 1'e ne kadar yakınsa hat o kadar en uzun "
             "bağlı işe (burada hep yükleme+kaynak) dayanmış demektir; 1'e ulaştığında operatör eklemek çevrimi artık "
             "kısaltmaz. Bu varsayımlarla 1–4 operatörde bu sınıra henüz değilmiyor, sınır daha fazla operatörde devreye "
             "girer.\n")
    s.append("## Aday değişkenler\n")
    s.append("Ürün değişkenleri (hacim, kaynak uzunluğu, vida, klips, hortum, pompa, sensör), operatör için "
             "**n** ve **1/n**, ayrıca her ürün değişkeninin **n'e bölünmüş** hali (çünkü üretim formülünde iş "
             "içeriği operatör sayısına bölünüyor).\n")
    s.append("## İleri seçim adımları\n")
    s.append(f"Her adımda p-değeri en küçük aday eklenir; p < {GIRIS_P_ESIGI} ve düzeltilmiş R² artmıyorsa durulur.\n")
    s.append("| Adım | Eklenen terim | p | R² | Düz. R² |")
    s.append("|---|---|---|---|---|")
    for a in adimlar:
        r2 = "–" if a["r2"] is None else f"{a['r2']:.4f}"
        ar2 = "–" if a["adj_r2"] is None else f"{a['adj_r2']:.4f}"
        s.append(f"| {a['adim']} | {a['eklenen']} | {a['p']:.2e} | {r2} | {ar2} |")
    s.append("\n## Son model\n")
    s.append(f"- R² = **{final.rsquared:.4f}**, düzeltilmiş R² = **{final.rsquared_adj:.4f}**, "
             f"artık std. sapma = {np.sqrt(final.scale):.2f} sn\n")
    s.append("| Terim | Katsayı | Std. hata | p |")
    s.append("|---|---|---|---|")
    for ad in ["const"] + secilen:
        s.append(f"| {'sabit' if ad == 'const' else ad} | {final.params[ad]:.3f} | {final.bse[ad]:.3f} | "
                 f"{final.pvalues[ad]:.2e} |")
    terimler = " ".join(f"{'+' if tm['katsayi'] >= 0 else '−'} {abs(tm['katsayi']):.2f}·{tm['ad']}"
                        for tm in model["terimler"])
    s.append(f"\n**Denklem:** `çevrim_sn = {model['sabit']:.2f} {terimler}`\n")
    s.append("## Kısa yorum\n")
    s.append("- Operatör etkisi n ile değil **1/n** ile (ve ürün değişkenleri / n ile) yakalanıyor: bu, süreyi "
             "operatör sayısına bölen üretim formülüyle uyumlu.")
    # beklenen katsayı karşılaştırması
    ort_carp = df["denge_kaybi"].mean() + 1
    karsi = {"vida": "vida", "klips": "klips", "hortum": "hortum", "pompa": "pompa", "sensor": "sensor",
             "hacim_l": "tasima_per_l", "kaynak_m": "kaynak_per_m"}
    satir = []
    for tm in model["terimler"]:
        if tm["donusum"] == "bolu_n" and tm["degisken"] in karsi:
            satir.append(f"{tm['degisken']}: {tm['katsayi']:.2f} (formülde {t(karsi[tm['degisken']])} × "
                         f"~{ort_carp:.2f} ≈ {t(karsi[tm['degisken']]) * ort_carp:.2f})")
    if satir:
        s.append("- '/operator' katsayıları ≈ element süresi × (1 + ortalama denge kaybı) olmalı: "
                 + "; ".join(satir) + ". n=1 satırlarında denge kaybı 0 olduğu için katsayılar bu değerin "
                 "biraz altında kalabilir.")
    s.append("- Doğrusal `operator` ya da bölünmemiş ürün terimleri seçildiyse, bunlar denge kaybının n=1'de 0, "
             "n≥2'de ~%15 olmasından doğan doğrusal olmayan farkı düzeltir; tek başına fiziksel anlamları yoktur.")
    s.append("- Sentetik veri, modelin bulması gereken formülden üretildiği için yüksek R² beklenen bir sonuçtur; "
             "gerçek ölçümlerle R² daha düşük çıkacaktır.")
    s.append("- Sınırlama: kaynak ve sızdırmazlık testi gerçekte makine süresidir ve operatör sayısıyla kısalmaz; "
             "demoda istenen formül gereği tüm iş içeriği n'e bölünmüştür.\n")
    s.append("## Dosyalar\n")
    s.append("- `outputs/veri_seti.xlsx` – sentetik veri\n- `outputs/model.json` – katsayılar, dönüşümler, girdi "
             "aralıkları\n- `outputs/index.html` – çevrimdışı tahmin arayüzü\n- `src/demo.py` – hepsini yeniden üretir\n")
    s.append("## Kaynakça\n")
    for k, v in KAYNAKLAR.items():
        s.append(f"- [{k}] {v}")
    (OUT / "rapor.md").write_text("\n".join(s) + "\n", encoding="utf-8")


# =====================================================================
# 4) HTML ARAYÜZ
# =====================================================================
HTML_SABLON = r"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Washer Tank Çevrim Tahmini</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>
:root{--iz:#e3e8ee;--vurgu-koyu:#1b3a5c;--bg:#f5f7fa;--kart:#fff;--yazi:#1d2733;--soluk:#5b6775;--vurgu:#2f5d8a;--cizgi:#d9e0e8;--uyari:#9a5b00;--uyari-bg:#fff4e0}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--iz:#26313c;--vurgu-koyu:#b9d6f2;--bg:#121820;--kart:#1b232d;--yazi:#e6ebf1;--soluk:#9aa6b4;--vurgu:#7fb0e0;--cizgi:#2c3742;--uyari:#ffc56b;--uyari-bg:#3a2a10;color-scheme:dark}}
:root[data-theme="dark"]{--iz:#26313c;--vurgu-koyu:#b9d6f2;--bg:#121820;--kart:#1b232d;--yazi:#e6ebf1;--soluk:#9aa6b4;--vurgu:#7fb0e0;--cizgi:#2c3742;--uyari:#ffc56b;--uyari-bg:#3a2a10;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--yazi);font:16px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:640px;margin:0 auto;padding-block:16px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
h1{font-size:1.25rem;margin:4px 0 2px}
.demo{display:inline-block;font-size:.78rem;color:var(--uyari);background:var(--uyari-bg);border-radius:6px;padding:2px 8px;margin-bottom:12px}
.kart{background:var(--kart);border:1px solid var(--cizgi);border-radius:12px;padding:16px;margin-bottom:14px}
.sonuc{display:grid;grid-template-columns:1fr 1fr;gap:12px;text-align:center}
.sonuc .deger{font-size:2rem;font-weight:700;color:var(--vurgu);font-variant-numeric:tabular-nums}
.sonuc .etiket{font-size:.85rem;color:var(--soluk)}
.alan{display:grid;grid-template-columns:1fr 110px;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid var(--cizgi)}
.alan:last-child{border-bottom:0}
.alan label{font-size:.95rem}
.alan small{color:var(--soluk)}
input[type=number]{width:100%;padding:8px;font-size:1rem;border:1px solid var(--cizgi);border-radius:8px;background:var(--bg);color:var(--yazi);text-align:right}
input.disarida{border-color:var(--uyari);outline:2px solid var(--uyari)}
.op{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;grid-column:1/-1}
.op button{padding:10px 0;font-size:1rem;border:1px solid var(--cizgi);border-radius:8px;background:var(--bg);color:var(--yazi);cursor:pointer}
.op button[aria-pressed=true]{background:var(--vurgu);border-color:var(--vurgu);color:var(--kart)}
.uyari{display:none;color:var(--uyari);background:var(--uyari-bg);border-radius:8px;padding:10px;font-size:.9rem;margin-bottom:14px}
details{font-size:.85rem;color:var(--soluk)}
h2{font-size:1rem;margin:0 0 4px}
.not{font-size:.8rem;color:var(--soluk);margin:0 0 12px}
.ist{margin:10px 0 14px}
.ist .ust{display:flex;flex-wrap:wrap;justify-content:space-between;column-gap:8px;font-size:.9rem;margin-bottom:4px}
.ist .ust>span{white-space:nowrap}
.ist .ust b{font-variant-numeric:tabular-nums}
.ist .iz{position:relative;height:14px;background:var(--iz);border-radius:4px;overflow:hidden}
.ist .dolu{position:absolute;left:0;top:0;bottom:0;background:var(--vurgu);border-radius:4px}
.ist.darbogaz .dolu{background:var(--vurgu-koyu)}
.ist .isler{font-size:.78rem;color:var(--soluk);margin-top:4px}
.rozet{font-size:.72rem;border:1px solid var(--cizgi);border-radius:5px;padding:0 5px;margin-left:6px;color:var(--yazi)}
.ozet{font-size:.85rem;border-top:1px solid var(--cizgi);padding-top:10px;margin-top:4px}
code{font-size:.8rem;word-break:break-word}
</style>
</head>
<body>
<main>
<h1>Washer tank montajı – çevrim süresi tahmini</h1>
<div class="demo">Demo – sentetik veriyle eğitilmiştir</div>

<div class="kart sonuc" aria-live="polite">
  <div><div class="deger" id="sure">–</div><div class="etiket">Tahmini çevrim süresi (sn)</div></div>
  <div><div class="deger" id="adet">–</div><div class="etiket">Saatlik üretim (adet)</div></div>
</div>
<div class="uyari" id="uyari"></div>

<div class="kart" id="girdiler"></div>

<div class="kart" id="operatorler">
  <h2>Operatörlerin çalışma süreleri</h2>
  <p class="not">Bir çevrimde her operatörün çalıştığı (çubuğun dolu kısmı) ve beklediği (boş kısım) süre. Literatür element
  süreleri, iş sırası ve bölünemeyen bağlı işlere göre hesaplanır; regresyon tahmininden birkaç saniye farklı olabilir.</p>
  <div id="istasyonlar"></div>
  <div class="ozet" id="hatozet"></div>
</div>

<details class="kart">
  <summary>Model denklemi</summary>
  <p><code id="denklem"></code></p>
  <p id="bilgi"></p>
</details>
</main>
<script>
const MODEL = __MODEL_JSON__;

function terim(t, v) {
  const n = v.operator;
  if (t.donusum === "x") return v[t.degisken];
  if (t.donusum === "ters") return 1 / n;
  if (t.donusum === "bolu_n") return v[t.degisken] / n;
  throw new Error(t.donusum);
}
function tahmin(v) {
  let y = MODEL.sabit;
  for (const t of MODEL.terimler) y += t.katsayi * terim(t, v);
  return y;
}
window.tahmin = tahmin;

// ---- Operatör iş dağılımı (Python'daki is_bloklari ve hat_dengele ile aynı) ----
const HAT = MODEL.hat, E = HAT.element_sn;
function isBloklari(v) {
  const tl = E.tasima_per_l * v.hacim_l, b = [];
  b.push(["Yükleme+kaynak", 0.5 * tl + E.kaynak_sabit + E.kaynak_per_m * v.kaynak_m]);
  const ph = Math.min(v.pompa, v.hortum);
  for (let i = 0; i < v.pompa; i++) b.push([`Pompa${i + 1}` + (i < ph ? "+hortum" : ""), E.pompa + (i < ph ? E.hortum : 0)]);
  for (let i = 0; i < v.sensor; i++) b.push([`Sensör${i + 1}`, E.sensor]);
  for (let i = 0; i < v.hortum - ph; i++) b.push([`Hortum${i + 1}`, E.hortum]);
  let kalan = v.vida, j = 0;
  while (kalan > 0) { const k = Math.min(HAT.vida_per_braket, kalan); j++; b.push([`Braket${j}(${k} vida)`, E.vida * k]); kalan -= k; }
  for (let i = 0; i < v.klips; i++) b.push([`Klips${i + 1}`, E.klips]);
  b.push(["Yükleme+test", 0.25 * tl + E.sizdirmazlik]);
  b.push(["Etiket+kutulama", 0.25 * tl + E.sabit_is]);
  return b;
}
function hatDengele(bloklar, nOp) {
  const k = bloklar.length, n = Math.min(nOp, k), on = [0];
  for (const [, t] of bloklar) on.push(on[on.length - 1] + t);
  const dp = [], kes = [];
  for (let s = 0; s <= n; s++) { dp.push(new Array(k + 1).fill(Infinity)); kes.push(new Array(k + 1).fill(0)); }
  dp[0][0] = 0;
  for (let s = 1; s <= n; s++) for (let i = 1; i <= k; i++) for (let j = s - 1; j < i; j++) {
    const v = Math.max(dp[s - 1][j], on[i] - on[j]);
    if (v < dp[s][i]) { dp[s][i] = v; kes[s][i] = j; }
  }
  const ist = []; let i = k;
  for (let s = n; s >= 1; s--) { const j = kes[s][i]; ist.unshift({ yuk: on[i] - on[j], isler: bloklar.slice(j, i).map(x => x[0]) }); i = j; }
  while (ist.length < nOp) ist.push({ yuk: 0, isler: [] });
  return { cevrim: dp[n][k], ist, toplam: on[k] };
}
window.hatHesapla = v => hatDengele(isBloklari(Object.assign({}, HAT.varsayilan, v)), v.operator);

function ciz(v) {
  const kutuI = document.getElementById("istasyonlar"), oz = document.getElementById("hatozet");
  const tamam = ["hacim_l", "kaynak_m", "vida", "klips", "hortum", "pompa", "sensor", "operator"]
    .every(k => Number.isFinite((k in v ? v : HAT.varsayilan)[k]) && (k in v ? v : HAT.varsayilan)[k] >= 0);
  if (!tamam) { kutuI.innerHTML = ""; oz.textContent = "Tüm girdileri doldurun."; return; }
  const vv = Object.assign({}, HAT.varsayilan, v);
  vv.vida = Math.round(vv.vida); vv.klips = Math.round(vv.klips); vv.hortum = Math.round(vv.hortum);
  vv.pompa = Math.round(vv.pompa); vv.sensor = Math.round(vv.sensor);
  const h = hatDengele(isBloklari(vv), vv.operator);
  kutuI.innerHTML = "";
  h.ist.forEach((s, i) => {
    const dar = Math.abs(s.yuk - h.cevrim) < 1e-9;
    const d = document.createElement("div");
    d.className = "ist" + (dar ? " darbogaz" : "");
    d.dataset.yuk = s.yuk;
    const bekle = h.cevrim - s.yuk;
    d.innerHTML = `<div class="ust"><span>Operatör ${i + 1}${dar ? '<span class="rozet">darboğaz</span>' : ""}</span>
      <span><b>${s.yuk.toFixed(1)} sn</b> çalışma · ${bekle.toFixed(1)} sn bekleme</span></div>
      <div class="iz" role="img" aria-label="Operatör ${i + 1}: ${s.yuk.toFixed(1)} sn çalışma, ${bekle.toFixed(1)} sn bekleme">
      <div class="dolu" style="width:${(100 * s.yuk / h.cevrim).toFixed(2)}%"></div></div>
      <div class="isler">${s.isler.length ? s.isler.join(" → ") : "iş atanmadı"}</div>`;
    d.title = `Operatör ${i + 1}: ${s.yuk.toFixed(1)} sn çalışma, %${(100 * s.yuk / h.cevrim).toFixed(0)} doluluk`;
    kutuI.appendChild(d);
  });
  const kayip = 100 * (vv.operator * h.cevrim / h.toplam - 1);
  oz.innerHTML = `Toplam iş içeriği <b>${h.toplam.toFixed(1)} sn</b> · en yüklü operatör (hesaplanan çevrim) ` +
    `<b>${h.cevrim.toFixed(1)} sn</b> · denge kaybı <b>%${kayip.toFixed(1)}</b>`;
}

const kutu = document.getElementById("girdiler");
const deger = {};
for (const g of MODEL.girdiler) {
  deger[g.ad] = g.varsayilan;
  const d = document.createElement("div");
  d.className = "alan";
  if (g.ad === "operator") {
    d.innerHTML = `<label>${g.etiket} <small>(${g.min}–${g.max})</small></label><div></div>`;
    const op = document.createElement("div");
    op.className = "op";
    for (let i = g.min; i <= g.max; i++) {
      const b = document.createElement("button");
      b.type = "button"; b.textContent = i; b.dataset.n = i;
      b.setAttribute("aria-pressed", i === g.varsayilan);
      b.onclick = () => {
        deger.operator = i;
        op.querySelectorAll("button").forEach(x => x.setAttribute("aria-pressed", x === b));
        hesapla();
      };
      op.appendChild(b);
    }
    d.appendChild(op);
  } else {
    d.innerHTML = `<label for="in_${g.ad}">${g.etiket} <small>(${g.birim}, ${g.min}–${g.max})</small></label>
      <input type="number" id="in_${g.ad}" inputmode="decimal" step="${g.adim}" value="${g.varsayilan}">`;
    d.querySelector("input").addEventListener("input", e => {
      deger[g.ad] = e.target.value === "" ? NaN : Number(e.target.value);
      hesapla();
    });
  }
  kutu.appendChild(d);
}

function hesapla() {
  const disarida = [];
  for (const g of MODEL.girdiler) {
    const v = deger[g.ad];
    const kotu = !Number.isFinite(v) || v < g.min || v > g.max;
    const inp = document.getElementById("in_" + g.ad);
    if (inp) inp.classList.toggle("disarida", kotu);
    if (kotu) disarida.push(`${g.etiket} (${g.min}–${g.max} ${g.birim})`);
  }
  const u = document.getElementById("uyari");
  u.style.display = disarida.length ? "block" : "none";
  u.textContent = disarida.length ? "Uyarı: model bu aralıkta eğitilmedi → " + disarida.join(", ") : "";
  const tumSayi = MODEL.girdiler.every(g => Number.isFinite(deger[g.ad]));
  const s = tumSayi ? tahmin(deger) : NaN;
  const sEl = document.getElementById("sure"), aEl = document.getElementById("adet");
  sEl.dataset.ham = s;
  sEl.textContent = Number.isFinite(s) ? s.toFixed(1) : "–";
  aEl.textContent = Number.isFinite(s) && s > 0 ? (3600 / s).toFixed(1) : "–";
  ciz(deger);
}

document.getElementById("denklem").textContent = "çevrim_sn = " + MODEL.sabit.toFixed(3) + " " +
  MODEL.terimler.map(t => (t.katsayi >= 0 ? "+ " : "− ") + Math.abs(t.katsayi).toFixed(3) + "·" + t.ad).join(" ");
document.getElementById("bilgi").textContent =
  `R² = ${MODEL.r2.toFixed(4)}, düzeltilmiş R² = ${MODEL.duzeltilmis_r2.toFixed(4)}, ${MODEL.n_gozlem} sentetik gözlem.`;
hesapla();
</script>
</body>
</html>
"""


def html_yaz(model, yayin_yolu=None):
    html = HTML_SABLON.replace("__MODEL_JSON__", json.dumps(model, ensure_ascii=False))
    (OUT / "index.html").write_text(html, encoding="utf-8")
    if yayin_yolu:  # web linki için: <html>/<head>/<body> sarmalayıcıları olmadan aynı içerik
        import re
        govde = re.sub(r"<!doctype html>\s*<html[^>]*>\s*<head>\s*<meta charset=\"utf-8\">\s*<meta name=\"viewport\"[^>]*>\s*",
                       "", html, flags=re.I)
        govde = govde.replace("</head>\n<body>\n", "").replace("</body>\n</html>\n", "")
        Path(yayin_yolu).write_text(govde, encoding="utf-8")


# =====================================================================
# 5) PYTHON ↔ HTML DOĞRULAMA
# =====================================================================
DOGRULAMA_JS = r"""
const { chromium } = require('playwright');
const [,, htmlYolu, ornekYolu] = process.argv;
const ornekler = JSON.parse(require('fs').readFileSync(ornekYolu, 'utf8'));
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 390, height: 844 } });
  await p.goto('file://' + htmlYolu);
  const sonuc = [];
  for (const o of ornekler) {
    // girişleri arayüz üzerinden doldur (gerçek kullanım gibi)
    for (const [k, v] of Object.entries(o)) {
      if (k === 'operator') await p.click(`.op button[data-n="${v}"]`);
      else await p.fill(`#in_${k}`, String(v));
    }
    const ham = await p.$eval('#sure', e => Number(e.dataset.ham));
    const fn = await p.evaluate(v => window.tahmin(v), o);
    const yukler = await p.$$eval('#istasyonlar .ist', l => l.map(e => Number(e.dataset.yuk)));
    sonuc.push({ arayuz: ham, fonksiyon: fn, yukler });
  }
  const tasma = await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  console.log(JSON.stringify({ sonuc, tasma }));
  await b.close();
})();
"""


def dogrula(model):
    ad = [g["ad"] for g in model["girdiler"]]
    rng = np.random.default_rng(SEED + 1)
    ornekler = [{g["ad"]: g["varsayilan"] for g in model["girdiler"]}]
    for n in range(1, 5):
        o = {}
        for g in model["girdiler"]:
            if g["ad"] == "operator":
                o[g["ad"]] = n
            elif g["tamsayi"]:
                o[g["ad"]] = int(rng.integers(g["min"], g["max"] + 1))
            else:
                o[g["ad"]] = round(float(rng.uniform(g["min"], g["max"])), 2)
        ornekler.append(o)
    py = [python_tahmin(model, o) for o in ornekler]
    py_yuk = []
    for o in ornekler:
        d = {k: v[4] for k, v in GIRDILER.items()}
        d.update(o)
        _, y = hat_dengele([s for _, s in is_bloklari(d)], d["operator"])
        py_yuk.append([float(x) for x in y] + [0.0] * (d["operator"] - len(y)))
    print("\n5) Python ↔ HTML karşılaştırması")
    if shutil.which("node") is None:
        print("   node bulunamadı; HTML doğrulaması atlandı.")
        return None
    with tempfile.TemporaryDirectory() as tmp:
        js, oy = Path(tmp) / "dogrula.js", Path(tmp) / "ornek.json"
        js.write_text(DOGRULAMA_JS)
        oy.write_text(json.dumps(ornekler))
        r = subprocess.run(["node", str(js), str(OUT / "index.html"), str(oy)], capture_output=True, text=True)
    if r.returncode != 0:
        print("   Playwright çalıştırılamadı; HTML doğrulaması atlandı.\n  ", r.stderr.strip()[:300])
        return None
    cikti = json.loads(r.stdout)
    hepsi = True
    for o, p_, h, yk in zip(ornekler, py, cikti["sonuc"], py_yuk):
        esit = abs(p_ - h["arayuz"]) < 1e-9 and abs(p_ - h["fonksiyon"]) < 1e-9
        yuk_esit = len(yk) == len(h["yukler"]) and all(abs(a - b) < 1e-9 for a, b in zip(yk, h["yukler"]))
        esit &= yuk_esit
        print(f"   operatör yükleri Python {[round(x, 1) for x in yk]} | HTML "
              f"{[round(x, 1) for x in h['yukler']]}  {'EŞLEŞTİ' if yuk_esit else 'FARKLI!'}")
        hepsi &= esit
        print(f"   {o} → Python {p_:.6f} | HTML {h['arayuz']:.6f}  {'EŞLEŞTİ' if esit else 'FARKLI!'}")
    print(f"   Telefon genişliğinde (390 px) yatay taşma: {'VAR' if cikti['tasma'] else 'yok'}")
    if not hepsi:
        raise SystemExit("HATA: Python ve HTML tahminleri eşleşmiyor.")
    print("   Tüm örneklerde Python ve HTML sonuçları birebir aynı.")
    return True


# =====================================================================
def main():
    OUT.mkdir(exist_ok=True)
    print("1) Parametre tablosu:", parametre_tablosu_yaz().relative_to(KOK))

    df = veri_uret()
    with pd.ExcelWriter(OUT / "veri_seti.xlsx", engine="openpyxl") as xw:
        df.to_excel(xw, sheet_name="veri", index=False)
        excel_bicimle(xw.sheets["veri"])
    print(f"2) Sentetik veri: outputs/veri_seti.xlsx ({len(df)} satır)")

    final, secilen, adaylar, adimlar = ileri_secim(df)
    model = model_json_olustur(final, secilen, adaylar)
    (OUT / "model.json").write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding="utf-8")
    rapor_yaz(df, final, secilen, adimlar, model, len(adaylar))
    print(f"3) Model: seçilen = {secilen}")
    print(f"   R² = {final.rsquared:.4f}, düzeltilmiş R² = {final.rsquared_adj:.4f}")

    import sys
    html_yaz(model, sys.argv[1] if len(sys.argv) > 1 else None)
    print("4) Arayüz: outputs/index.html")
    dogrula(model)


if __name__ == "__main__":
    main()
