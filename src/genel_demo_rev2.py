"""
GENEL SÜRÜM – REV2: "zorluk eki" (engelli erişim) eklenmiş sürüm.

Rev2'nin rev1'den (src/genel_demo.py) farkı:
  * "Zor parça" ve "vida" için ikinci bir sayı girilir: bunlardan kaçının ENGELLİ ERİŞİMLİ /
    KISITLI GÖRÜŞLÜ olduğu. Her biri, normal süreye ek bir süre ekler (DFA ceza mantığı).
  * Böylece aynı kategori içindeki hızlı ve yavaş alt gruplar tek bir ortalamaya
    karıştırılmaz; model ek süreyi ayrı bir katsayı olarak öğrenir.
  * Rapor, eksiz (rev1 tipi) ve ekli modeli aynı veride, ayrı bir test kümesinde karşılaştırır.

Rev1 açıklaması:

Washer tank sürümünden (src/demo.py) farkı:
  * Ürün, ürüne özel kalemlerle ("pompa takma", "hortum takma") değil, GENEL İŞLEM TİPLERİYLE
    tarif edilir (MTM-UAS / Boothroyd-Dewhurst DFA seviyesi):
      kolay parça yerleştirme, zor parça yerleştirme, vidalama, geçmeli bağlantı,
      esnek bağlantı (hortum/kablo/konnektör), görsel kontrol, makine işlemleri (sn).
  * Böylece aynı model washer tank, dış dikiz aynası vb. ürünlere uygulanabilir;
    ürün ailesi yalnızca bu sayıları değiştirir.
  * Makine işlemleri (kaynak, test) saniye olarak girilir, bölünemez bloktur ve operatör
    sayısıyla kısalmaz.

Çalıştırma (depo kökünden):  python3 src/genel_demo_rev2.py [yayın_kopyası.html]
Çıktılar: data/genel_parametreler_rev2.xlsx, outputs/genel_rev2/ (veri_seti_rev2.xlsx, rapor_rev2.md,
          model_rev2.json, index_rev2.html)

NOT: Ölçülmüş veri yoktur. Tüm sayılar literatür ve VARSAYIM'lardan gelir.
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parent))
import demo  # noqa: E402  (ortak yardımcılar: excel_bicimle, hat_dengele, kaynaklar, CSS)

KOK = demo.KOK
DATA = KOK / "data"
OUT = KOK / "outputs" / "genel_rev2"

# =====================================================================
# AYARLAR
# =====================================================================
SEED = 2024
SATIR_PER_OPERATOR = 100          # 4 x 100 = 400 satır
GIRIS_P_ESIGI = 0.05
GURULTU_SD = 3.0
MAKINE_SIFIR_OLASILIGI = 0.2      # bazı ürünlerde o makine işlemi yok (VARSAYIM)

# Genel işlem tiplerinin süreleri: (min, tipik, max, birim, kaynak/VARSAYIM)
ELEMENTLER = {
    "sabit_is":     (10, 15, 20, "sn/ürün",
                     "VARSAYIM: etiketleme, kutulama gibi üründen bağımsız işler."),
    "tasima_sabit": (1.5, 2.0, 2.5, "sn/taşıma",
                     "[S10] orta boy parça tutma 2,0–3,0 sn; gövde 3 kez alınıp konur (VARSAYIM)."),
    "tasima_per_kg": (1.0, 1.5, 2.0, "sn/kg/taşıma",
                      "VARSAYIM: [S10] ağır parça (>2 kg) 3,5–5,0 sn'ye çıkacak şekilde kütleyle artış."),
    "parca_kolay":  (3.0, 3.0, 3.45, "sn/adet",
                     "[S7],[S8] tutma 1,5–1,95 sn + engelsiz yerleştirme 1,5 sn (kod 10/00, 30/00)."),
    "parca_zor":    (8.45, 8.5, 8.86, "sn/adet",
                     "[S8] tutma 1,95–2,36 sn + bastırarak/tutarak yerleştirme 6,5 sn (kod 08)."),
    "vida":         (7.8, 9.8, 13.8, "sn/adet",
                     "[S7],[S8] tutma 1,8 sn + yerleştirme/sıkma 6 / 8 / 12 sn (kod 38 / 39 / 59)."),
    "gecme":        (3.0, 3.5, 4.5, "sn/adet",
                     "[S10] tutma 1,5–2,0 + geçmeli yerleştirme 1,5–2,5 sn (genel çerçeve, doğrulanmış tablo değil)."),
    "baglanti":     (5.0, 8.0, 15.0, "sn/adet",
                     "VARSAYIM: esnek parça tutma [S10] 3–5 sn + rakora/sokete geçirme; elektrik soketi "
                     "kısa, kelepçeli hortum uzun uçta."),
    "vida_engelli_ek": (None, 6.0, None, "sn/adet (ek)",
                        "[S7] aynı vida engelli erişim+kısıtlı görüşte 12 sn (kod 59), kolay erişimli yeniden "
                        "tasarımda 6 sn (kod 38) → ek 6 sn."),
    "parca_zor_engelli_ek": (0.5, 2.25, 4.0, "sn/adet (ek)",
                             "[S10]'dan türetildi: engelli erişimde yerleştirme 4,0–6,0 sn, orta hizalamada "
                             "2,0–3,5 sn → fark 0,5–4,0 sn, orta noktaların farkı 2,25 sn (genel çerçeve)."),
    "kontrol":      (1.0, 2.0, 3.0, "sn/nokta",
                     "VARSAYIM: MTM-UAS'ta görsel kontrol ayrı bir sınıf [S22]; sayısal değeri okunamadı."),
    "zor_parca_vida": (None, 2, None, "vida/parça",
                       "VARSAYIM: her zor parça en fazla 2 vidasıyla birlikte aynı operatörce takılır (bağlı iş)."),
}

# Ürün girdileri: (etiket, birim, min, max, tamsayı mı, açıklama)
GIRDILER = {
    "govde_kg":    ("Ana gövde kütlesi", "kg", 0.2, 2.0, False, "Taşıma/yükleme süresini belirler"),
    "parca_kolay": ("Kolay parça yerleştirme", "adet", 0, 6, True, "Küçük, simetrik, kendiliğinden hizalanan"),
    "parca_zor":   ("Zor parça yerleştirme", "adet", 0, 4, True, "Hizalama isteyen, bastırılarak/tutularak takılan"),
    "parca_zor_engelli": ("– bunlardan engelli erişimli", "adet", 0, 4, True,
                          "Dar yer veya kısıtlı görüş; zor parça sayısını aşamaz"),
    "vida":        ("Vidalama", "adet", 0, 8, True, "Her vida ayrı sayılır"),
    "vida_engelli": ("– bunlardan engelli erişimli", "adet", 0, 8, True,
                     "Dar yer veya kısıtlı görüş; vida sayısını aşamaz"),
    "gecme":       ("Geçmeli bağlantı", "adet", 0, 10, True, "Klips, snap-fit"),
    "baglanti":    ("Esnek bağlantı", "adet", 0, 5, True, "Hortum, kablo, konnektör"),
    "kontrol":     ("Görsel kontrol noktası", "adet", 0, 5, True, "Ayrı bir bakış/kontrol işlemi"),
    "makine1_sn":  ("Makine işlemi 1", "sn", 0, 60, False, "Kaynak, pres vb. (yoksa 0) – operatöre bölünmez"),
    "makine2_sn":  ("Makine işlemi 2", "sn", 0, 60, False, "Sızdırmazlık / fonksiyon testi (yoksa 0) – bölünmez"),
    "operator":    ("Operatör sayısı", "kişi", 1, 4, True, ""),
}
URUN = [k for k in GIRDILER if k != "operator"]
UST = {"parca_zor_engelli": "parca_zor", "vida_engelli": "vida"}   # alt sayı ≤ üst sayı

# Arayüzde hazır ürün şablonları (hepsi VARSAYIM; gerçek parça/firma bilgisi yok)
SABLONLAR = {
    "Washer tank": dict(govde_kg=0.6, parca_kolay=2, parca_zor=1, parca_zor_engelli=0, vida=2, vida_engelli=0, gecme=4, baglanti=2, kontrol=2,
                        makine1_sn=30, makine2_sn=25),
    "Dış dikiz aynası": dict(govde_kg=0.9, parca_kolay=3, parca_zor=2, parca_zor_engelli=1, vida=4, vida_engelli=2, gecme=6, baglanti=2, kontrol=3,
                             makine1_sn=0, makine2_sn=15),
}
SABLON_ACIKLAMA = {
    "Washer tank": "zor parça = pompa; kolay = sensör, kapak; esnek bağlantı = hortum; geçme = klips; "
                   "makine 1 = sıcak plaka kaynağı ([S1],[S2] 10–60 sn içinde 30 sn); makine 2 = sızdırmazlık "
                   "testi ([S6] 20–30 sn içinde 25 sn). Rev2: engelli erişim yok (VARSAYIM).",
    "Dış dikiz aynası": "zor parça = ayar motoru, cam+tutucu; kolay = kapak, sinyal camı, conta; esnek bağlantı = "
                        "kablo soketi; makine 1 yok; makine 2 = elektriksel fonksiyon testi 15 sn. Tüm sayılar "
                        "VARSAYIM (aynaya özel süre kaynağı bulunamadı). Rev2: ayar motoru gövde içinde dar yerde "
                        "takılır (1 engelli zor parça), 2 vida gövde içinden sıkılır (VARSAYIM).",
}

EK_KAYNAKLAR = {
    "S21": "MTM ASSOCIATION e. V. (t.y.). The brands of the MTM ASSOCIATION e. V. https://mtm.org/en/brands/our-brands",
    "S22": "Terkaj, W., Urgo, M. (t.y.). Virtual Learning Factory Toolkit – MTM / Formalise the process. "
           "https://virtualfactory.gitbook.io/vlft/tools/mtm/formalise",
    "S23": "Owensby, J. E., Summers, J. D. (2014). Assembly Time Estimation: Assembly Mate Based Structural "
           "Complexity Metric Predictive Modeling. Journal of Computing and Information Science in Engineering "
           "14(1). https://open.clemson.edu/cedar_pubs/8",
}
KAYNAKLAR = {**demo.KAYNAKLAR, **EK_KAYNAKLAR}
KULLANILAN = ["S1", "S2", "S5", "S6", "S7", "S8", "S9", "S10", "S11", "S14", "S17", "S18", "S19", "S20",
              "S21", "S22", "S23"]

SEVIYELER = [
    ("1. Ürüne özel kalem", "pompa takma, hortum takma, sensör takma",
     "Firma için en anlaşılır; tek ürün ailesinde iyi çalışır.",
     "Başka ürüne taşınamaz: aynada 'pompa' yok. Her yeni ürün için yeni değişken ve yeni veri gerekir.",
     "Washer tank sürümü (src/demo.py)"),
    ("2. Genel işlem tipi (önerilen)", "kolay/zor parça yerleştir, vidala, geçme, esnek bağlantı, kontrol, "
     "makine süresi", "Ürün ailesinden bağımsız; MTM-UAS'ın 'temel işlem' seviyesi [S21],[S22] ve DFA "
     "sınıflandırması [S7],[S8] ile aynı mantık. Değişken sayısı az, regresyon için az veri yeter.",
     "Bir işlem tipinin içi ortalama süre kabul edilir; zor bir vida ile kolay vida farkı kaybolur "
     "(MTM-UAS'ın kendisi de temel hareket seviyesine göre daha az hassas [S22]).", "Genel sürüm (rev1 ve rev2)"),
    ("3. Hareket bazlı (MTM-1)", "uzan, kavra, taşı, konumla, bırak (TMU)",
     "En taşınabilir ve en ayrıntılı; tüm üst MTM sistemleri buna dayanır [S21].",
     "Her ürün için eğitimli analist ve lisanslı tablolar gerekir; değişken sayısı çok fazla. Hareketler "
     "bilindiğinde süre zaten toplamla hesaplanır, regresyona gerek kalmaz.",
     "Element sürelerinin kaynağı olarak kullanılmalı (firma MTM analizi yaparsa tablodaki süreler güncellenir)"),
]


def t(k):
    return ELEMENTLER[k][1]


# =====================================================================
# İŞ BLOKLARI, İŞ İÇERİĞİ
# =====================================================================
def tasima(d):
    return t("tasima_sabit") + t("tasima_per_kg") * d["govde_kg"]


def is_bloklari(d):
    """Öncelik sırasına göre bölünemez iş blokları [(ad, sn), ...].
    Sıra: yükleme(+makine1) → zor parçalar(+vidaları) → kolay parçalar → geçmeler → kalan vidalar →
          esnek bağlantılar → kontroller → yükleme(+makine2) → etiket/kutulama."""
    b = []
    h = tasima(d)
    b.append(("Yükleme+Makine1" if d["makine1_sn"] > 0 else "Gövde yükleme", h + d["makine1_sn"]))
    # vidalar: önce engelli olanlar (ek süreli), sonra normal olanlar sırayla kullanılır
    ve = min(d["vida_engelli"], d["vida"])   # engelli sayısı toplamı aşamaz
    vidalar = [t("vida") + t("vida_engelli_ek")] * ve + [t("vida")] * (d["vida"] - ve)
    for i in range(d["parca_zor"]):
        v = min(ELEMENTLER["zor_parca_vida"][1], len(vidalar))
        vs, vidalar = vidalar[:v], vidalar[v:]
        eng = i < min(d["parca_zor_engelli"], d["parca_zor"])
        b.append((f"ZorParça{i + 1}" + ("(engelli)" if eng else "") + (f"+{v}vida" if v else ""),
                  t("parca_zor") + (t("parca_zor_engelli_ek") if eng else 0) + sum(vs)))
    for i in range(d["parca_kolay"]):
        b.append((f"KolayParça{i + 1}", t("parca_kolay")))
    for i in range(d["gecme"]):
        b.append((f"Geçme{i + 1}", t("gecme")))
    for i, vs in enumerate(vidalar):
        b.append((f"Vida{i + 1}" + ("(engelli)" if vs > t("vida") else ""), vs))
    for i in range(d["baglanti"]):
        b.append((f"Bağlantı{i + 1}", t("baglanti")))
    for i in range(d["kontrol"]):
        b.append((f"Kontrol{i + 1}", t("kontrol")))
    b.append(("Yükleme+Makine2" if d["makine2_sn"] > 0 else "Ara taşıma", h + d["makine2_sn"]))
    b.append(("Etiket+kutulama", h + t("sabit_is")))
    return b


def is_icerigi(d):
    return (3 * tasima(d) + d["makine1_sn"] + d["makine2_sn"] + t("sabit_is")
            + t("parca_kolay") * d["parca_kolay"] + t("parca_zor") * d["parca_zor"] + t("vida") * d["vida"]
            + t("parca_zor_engelli_ek") * d["parca_zor_engelli"] + t("vida_engelli_ek") * d["vida_engelli"]
            + t("gecme") * d["gecme"] + t("baglanti") * d["baglanti"] + t("kontrol") * d["kontrol"])


# =====================================================================
# 1) PARAMETRE TABLOSU
# =====================================================================
def parametre_tablosu_yaz():
    s = []
    for k, (mn, tp, mx, birim, kay) in ELEMENTLER.items():
        s.append(dict(grup="Genel işlem tipi süresi", parametre=k, min=mn, tipik=tp, max=mx, birim=birim,
                      **{"kaynak/VARSAYIM": kay}))
    for k, (et, birim, mn, mx, _, acik) in GIRDILER.items():
        s.append(dict(grup="Ürün girdisi (veri aralığı)", parametre=f"{k} ({et})", min=mn, tipik=None, max=mx,
                      birim=birim, **{"kaynak/VARSAYIM": "VARSAYIM: geniş tutuldu ki farklı ürün aileleri "
                                                         "kapsansın. " + acik}))
    sab = [dict(sablon=ad, **deg, aciklama=SABLON_ACIKLAMA[ad]) for ad, deg in SABLONLAR.items()]
    sev = pd.DataFrame(SEVIYELER, columns=["seviye", "örnek değişkenler", "artısı", "eksisi", "bu projede"])
    kay = pd.DataFrame([dict(kod=k, kunye=KAYNAKLAR[k]) for k in KULLANILAN])
    yol = DATA / "genel_parametreler_rev2.xlsx"
    with pd.ExcelWriter(yol, engine="openpyxl") as xw:
        pd.DataFrame(s).to_excel(xw, sheet_name="parametreler", index=False)
        pd.DataFrame(sab).to_excel(xw, sheet_name="urun_sablonlari", index=False)
        sev.to_excel(xw, sheet_name="tanim_seviyeleri", index=False)
        kay.to_excel(xw, sheet_name="kaynaklar", index=False)
        demo.excel_bicimle(xw.sheets["parametreler"], {1: 28, 2: 40, 7: 90})
        demo.excel_bicimle(xw.sheets["urun_sablonlari"], {1: 18, 12: 90})
        demo.excel_bicimle(xw.sheets["tanim_seviyeleri"], {1: 28, 2: 40, 3: 60, 4: 60, 5: 40})
        demo.excel_bicimle(xw.sheets["kaynaklar"], {2: 140})
    return yol


# =====================================================================
# 2) VERİ
# =====================================================================
def veri_uret():
    rng = np.random.default_rng(SEED)
    rows = []
    for n in range(1, 5):
        for _ in range(SATIR_PER_OPERATOR):
            d = {}
            for k in URUN:
                _, _, mn, mx, tam, _ = GIRDILER[k]
                if k.startswith("makine") and rng.random() < MAKINE_SIFIR_OLASILIGI:
                    d[k] = 0.0
                elif k in UST:
                    d[k] = int(rng.integers(0, d[UST[k]] + 1))
                elif tam:
                    d[k] = int(rng.integers(mn, mx + 1))
                else:
                    d[k] = round(float(rng.uniform(mn, mx)), 2 if k == "govde_kg" else 1)
            d["operator"] = n
            bl = is_bloklari(d)
            sure = [x for _, x in bl]
            C, yuk = demo.hat_dengele(sure, n)
            W = is_icerigi(d)
            assert abs(W - sum(sure)) < 1e-9
            enb = max(bl, key=lambda x: x[1])
            d.update(is_icerigi_sn=round(W, 2), en_uzun_bagli_is=enb[0], en_uzun_bagli_is_sn=round(enb[1], 2),
                     istasyon_yukleri_sn=" | ".join(f"{y:.1f}" for y in yuk), cevrim_gurultusuz_sn=round(C, 2),
                     denge_kaybi=round(n * C / W - 1, 4),
                     cevrim_suresi_sn=round(C + float(rng.normal(0, GURULTU_SD)), 2), kaynak="sentetik")
            rows.append(d)
    df = pd.DataFrame(rows)
    df.insert(0, "urun_id", [f"R2-{i:03d}" for i in range(1, len(df) + 1)])
    return df


# =====================================================================
# 3) İLERİ REGRESYON
# =====================================================================
def adaylar():
    a = {k: dict(tur="x", degisken=k) for k in URUN}
    a["operator"] = dict(tur="x", degisken="operator")
    a["1/operator"] = dict(tur="ters", degisken="operator")
    for k in URUN:
        a[f"{k}/operator"] = dict(tur="bolu_n", degisken=k)
    a["maks_makine"] = dict(tur="maks", degisken="makine1_sn,makine2_sn")
    return a


def terim(tn, g):
    n = g["operator"]
    if tn["tur"] == "x":
        return g[tn["degisken"]]
    if tn["tur"] == "ters":
        return 1.0 / n
    if tn["tur"] == "bolu_n":
        return g[tn["degisken"]] / n
    if tn["tur"] == "maks":
        a, b = tn["degisken"].split(",")
        return np.maximum(g[a], g[b])
    raise ValueError(tn)


def ileri_secim(df, haric=()):
    A = {k: v for k, v in adaylar().items() if not any(h in k for h in haric)}
    X = pd.DataFrame({k: terim(v, df) for k, v in A.items()})
    y = df["cevrim_suresi_sn"]
    sec, adim, onceki = [], [], -np.inf
    while True:
        best = None
        for k in X.columns:
            if k in sec:
                continue
            m = sm.OLS(y, sm.add_constant(X[sec + [k]])).fit()
            if best is None or m.pvalues[k] < best[1]:
                best = (k, m.pvalues[k], m)
        if best is None:
            break
        k, p, m = best
        if p >= GIRIS_P_ESIGI or m.rsquared_adj <= onceki:
            adim.append(dict(adim=len(adim) + 1, eklenen=f"(durdu: en iyi aday {k}, p={p:.3g})", p=p,
                             r2=None, adj=None))
            break
        sec.append(k)
        onceki = m.rsquared_adj
        adim.append(dict(adim=len(adim) + 1, eklenen=k, p=p, r2=m.rsquared, adj=m.rsquared_adj))
    return sm.OLS(y, sm.add_constant(X[sec])).fit(), sec, A, adim


def model_olustur(final, sec, A):
    girdiler = []
    for k, (et, birim, mn, mx, tam, acik) in GIRDILER.items():
        girdiler.append(dict(ad=k, etiket=et, birim=birim, min=mn, max=mx, tamsayi=tam, aciklama=acik,
                             varsayilan=SABLONLAR["Washer tank"].get(k, 2), adim=1 if tam else (0.1 if k == "govde_kg" else 1)))
    return dict(
        aciklama="Genel sürüm – sentetik veriyle eğitilmiş çevrim süresi modeli (sn). tahmin = sabit + Σ katsayı × terim",
        sabit=float(final.params["const"]),
        terimler=[dict(ad=k, degisken=A[k]["degisken"], donusum=A[k]["tur"], katsayi=float(final.params[k]))
                  for k in sec],
        girdiler=girdiler, sablonlar=SABLONLAR, ust=UST,
        r2=float(final.rsquared), duzeltilmis_r2=float(final.rsquared_adj), n_gozlem=int(final.nobs),
        hat=dict(element_sn={k: v[1] for k, v in ELEMENTLER.items()}),
    )


def py_tahmin(model, g):
    y = model["sabit"]
    for tm in model["terimler"]:
        y += tm["katsayi"] * float(terim(dict(tur=tm["donusum"], degisken=tm["degisken"]), g))
    return y


# =====================================================================
# EKSİZ (rev1 tipi) ↔ EKLİ (rev2) MODEL KARŞILAŞTIRMASI
# =====================================================================
def karsilastir(df):
    """Aynı veride iki model: eksiz (engelli değişkenleri yok sayılır, rev1 gibi) ve ekli.
    %75 eğitim / %25 test; test kümesinde hata ve engelli erişim grubuna göre sistematik sapma."""
    rng = np.random.default_rng(SEED + 7)
    test = rng.random(len(df)) < 0.25
    egit, tst = df[~test].reset_index(drop=True), df[test].reset_index(drop=True)
    eng_sayi = tst["parca_zor_engelli"] + tst["vida_engelli"]
    gruplar = {"engelli işlem yok": eng_sayi == 0, "1–2 engelli işlem": eng_sayi.between(1, 2),
               "3+ engelli işlem": eng_sayi >= 3}
    sonuc = {}
    for ad, haric in (("Eksiz model (rev1 tipi)", ("engelli",)), ("Ekli model (rev2)", ())):
        f, sec, A, _ = ileri_secim(egit, haric)
        m = model_olustur(f, sec, A)
        tah = np.array([py_tahmin(m, r) for r in tst.to_dict("records")])
        art = tst["cevrim_suresi_sn"].to_numpy() - tah
        sonuc[ad] = dict(rmse=float(np.sqrt(np.mean(art ** 2))), mae=float(np.mean(np.abs(art))),
                         adj=float(f.rsquared_adj), terim=len(sec),
                         sapma={g: (float(art[msk.to_numpy()].mean()), int(msk.sum())) for g, msk in gruplar.items()})
    return sonuc, int(len(egit)), int(len(tst))


# =====================================================================
# RAPOR
# =====================================================================
def rapor_yaz(df, final, sec, adim, model, n_aday, kars=None):
    s = ["> **Bu sonuçlar sentetik veriye dayanan bir demodur.** Ölçülmüş veri kullanılmamıştır; süreler "
         "literatürden ve VARSAYIM'lardan alınmıştır (bkz. `data/genel_parametreler_rev2.xlsx`).\n",
         "# Genel Sürüm Rev2 – Zorluk Eki (Engelli Erişim) Eklenmiş Model\n",
         "Rev1 (`outputs/genel/`) ile aynı yapı; fark: zor parça ve vida için engelli erişim eki. "
         "Ayrıntı ve karşılaştırma aşağıda.\n",
         "## Soru: 'X takma' mı, 'takma' mı, hareket sayısı mı?\n",
         "Ürünü tarif etmenin üç seviyesi var. MTM sistemleri de aynı hiyerarşiyi kullanır: MTM-1 temel "
         "hareketler seviyesinde, MTM-2 hareket dizileri seviyesinde, MTM-UAS temel işlemler seviyesindedir ve "
         "üst seviyelerin hepsi MTM-1'e dayanır [S21].\n",
         "| Seviye | Örnek değişkenler | Artısı | Eksisi | Bu projede |", "|---|---|---|---|---|"]
    for r in SEVIYELER:
        s.append("| " + " | ".join(r) + " |")
    s += ["\n**Öneri:** Tahmin modeli **2. seviyede** (genel işlem tipi) kurulmalı. 'Pompa takma' yerine "
          "'zor parça yerleştirme', 'hortum takma' yerine 'esnek bağlantı' denir; makine işlemleri saniye olarak "
          "girilir. Böylece aynı model washer tank ve ayna için çalışır, ürün ailesi yalnızca sayıları "
          "değiştirir. Hareket bazlı (MTM-1) seviye tahmin girdisi olarak değil, her işlem tipinin **süresini "
          "belirlemek** için kullanılmalı: firma bir işlem tipini MTM ile analiz ederse "
          "`ELEMENTLER` tablosundaki süre güncellenir ve script yeniden çalıştırılır.",
          "- Benzer bir yaklaşımda ürün yapısından (parça bağlantı grafiği) montaj süresi tahmin edilmiş ve "
          "sonuçlar ±%25 içinde kalmıştır; aynı çalışma **eğitim verisindeki ürün çeşitliliğinin** kritik "
          "olduğunu vurgular [S23]. Bu yüzden gerçek veri toplanırken birden fazla ürün ailesinden ölçüm "
          "alınmalıdır.\n",
          "## Rev2: zorluk eki (engelli erişim)\n",
          "Aynı kategori içindeki işlerin süresi iki ayrı tepe etrafında toplanabilir (ör. zor parçaların bir kısmı "
          "~8–9 sn, bir kısmı ~11–12 sn). Hepsini tek kategoriye koymak, katsayıyı ikisinin ortalamasına çeker ve "
          "yavaş alt grubu çok içeren ürünler sistematik olarak düşük tahmin edilir.",
          "Rev2'de kategori bölünmez; yanına **'bunlardan kaçı engelli erişimli'** sayısı eklenir. Bu sayının "
          "katsayısı, iş başına **ek süreyi** verir. Bu, DFA'daki ceza mantığıdır: aynı vida engelli erişim ve "
          "kısıtlı görüşte 12 sn, kolay erişimde 6 sn sürer [S7].\n",
          "| Ek | Değer | Kaynak/VARSAYIM |", "|---|---|---|",
          f"| Vida – engelli erişim eki | +{t('vida_engelli_ek')} sn/adet | {ELEMENTLER['vida_engelli_ek'][4]} |",
          f"| Zor parça – engelli erişim eki | +{t('parca_zor_engelli_ek')} sn/adet | "
          f"{ELEMENTLER['parca_zor_engelli_ek'][4]} |\n",
          "**Ölçümde nasıl kullanılır:** Her vida ve zor parça için 'engelli erişim / kısıtlı görüş var mı?' "
          "sorusu kaydedilir. Katsayısı anlamlı çıkmazsa (p ≥ 0,05) ileri seçim bu değişkeni zaten almaz; "
          "yani ek, gerçekten fark yaratıyorsa modele girer.\n"]
    if kars:
        sonuc, n_e, n_t = kars
        s += [f"### Eksiz ve ekli model karşılaştırması (eğitim {n_e} satır, ayrı test {n_t} satır)\n",
              "| Model | Terim sayısı | Düz. R² (eğitim) | Test RMSE (sn) | Test ort. mutlak hata (sn) |",
              "|---|---|---|---|---|"]
        for ad, r in sonuc.items():
            s.append(f"| {ad} | {r['terim']} | {r['adj']:.4f} | {r['rmse']:.2f} | {r['mae']:.2f} |")
        gr = list(next(iter(sonuc.values()))["sapma"].keys())
        s += ["\n**Sistematik sapma** (test kümesinde ortalama gerçek − tahmin; + ise model süreyi düşük tahmin "
              "ediyor):\n", "| Grup | " + " | ".join(sonuc.keys()) + " |", "|---|" + "---|" * len(sonuc)]
        for g in gr:
            s.append(f"| {g} (n={next(iter(sonuc.values()))['sapma'][g][1]}) | "
                     + " | ".join(f"{r['sapma'][g][0]:+.2f} sn" for r in sonuc.values()) + " |")
        s.append("\nEksiz model, engelli işi çok olan ürünlerde süreyi düşük, hiç olmayanlarda yüksek tahmin "
                 "eder; ekli model bu sapmayı büyük ölçüde kaldırır.\n")
    s += ["## Genel işlem tipleri ve süreleri\n",
          "| İşlem tipi | Tipik süre | Kaynak/VARSAYIM |", "|---|---|---|"]
    for k, (mn, tp, mx, birim, kay) in ELEMENTLER.items():
        s.append(f"| {k} | {tp} {birim} | {kay} |")
    s += ["\n## Ürün şablonları (arayüzde hazır)\n", "| Şablon | " + " | ".join(URUN) + " | Eşleştirme |",
          "|---|" + "---|" * len(URUN) + "---|"]
    for ad, deg in SABLONLAR.items():
        s.append(f"| {ad} | " + " | ".join(str(deg[k]) for k in URUN) + f" | {SABLON_ACIKLAMA[ad]} |")
    s += ["\n## Veri\n",
          f"- {len(df)} satır (her operatör sayısı için {SATIR_PER_OPERATOR}), seed = {SEED}. Girdi aralıkları "
          "geniş tutuldu ki hem washer tank hem ayna gibi ürünler kapsansın; makine işlemleri %20 olasılıkla 0 "
          "(o üründe yok).",
          f"- {n_aday} aday terim × 15–20 gözlem ≈ 315–420 satır → 400 seçildi.",
          "- Çevrim süresi: işler sabit sırada, bağlı işler bölünemez blok (yükleme+makine, zor parça+vidaları); "
          "bloklar operatörlere en yüklü istasyonu en aza indirecek şekilde dağıtılır [S17]–[S20]; çevrim = en "
          f"yüklü istasyon + N(0, {GURULTU_SD}²). **Makine süreleri operatöre bölünmez.**\n",
          "| Operatör | Ort. denge kaybı | Maks | Çevrimin makine bloğuna dayandığı satır |", "|---|---|---|---|"]
    for n_, g in df.groupby("operator"):
        tavan = ((g["en_uzun_bagli_is"].str.contains("Makine"))
                 & (abs(g["cevrim_gurultusuz_sn"] - g["en_uzun_bagli_is_sn"]) < 0.02)).mean()
        s.append(f"| {n_} | %{abs(100 * g.denge_kaybi.mean()):.1f} | %{abs(100 * g.denge_kaybi.max()):.1f} | "
                 f"%{100 * tavan:.0f} |")
    s += ["\nOperatör arttıkça çevrim uzun makine işleminin altına inemez; bu satırlarda operatör eklemek "
          "süreyi kısaltmaz. Bu yüzden aday listesine `maks_makine` (iki makine süresinden büyüğü) de eklendi.\n",
          "## İleri seçim adımları\n", "| Adım | Eklenen terim | p | R² | Düz. R² |", "|---|---|---|---|---|"]
    for a in adim:
        s.append(f"| {a['adim']} | {a['eklenen']} | {a['p']:.2e} | "
                 f"{'–' if a['r2'] is None else f'{a[chr(114) + chr(50)]:.4f}'} | "
                 f"{'–' if a['adj'] is None else f'{a[chr(97) + chr(100) + chr(106)]:.4f}'} |")
    s += [f"\n## Son model\n", f"- R² = **{final.rsquared:.4f}**, düzeltilmiş R² = **{final.rsquared_adj:.4f}**, "
          f"artık std. sapma = {np.sqrt(final.scale):.2f} sn\n", "| Terim | Katsayı | Std. hata | p |",
          "|---|---|---|---|"]
    for k in ["const"] + sec:
        s.append(f"| {'sabit' if k == 'const' else k} | {final.params[k]:.3f} | {final.bse[k]:.3f} | "
                 f"{final.pvalues[k]:.2e} |")
    den = " ".join(f"{'+' if tm['katsayi'] >= 0 else '−'} {abs(tm['katsayi']):.2f}·{tm['ad']}"
                   for tm in model["terimler"])
    s += [f"\n**Denklem:** `çevrim_sn = {model['sabit']:.2f} {den}`\n", "## Kısa yorum\n",
          "- '/operator' terimleri elle yapılan ve operatörler arasında paylaşılabilen işleri, bölünmemiş "
          "terimler (özellikle makine süreleri ve `maks_makine`) operatör sayısıyla kısalmayan kısmı temsil eder.",
          "- Makine darboğazı gerçekte bir 'en büyüğü' (max) ilişkisidir; doğrusal regresyon bunu `maks_makine` "
          "ve bölünmemiş makine terimleriyle ancak yaklaşık yakalar. 3–4 operatörlü ve uzun makine süreli "
          "ürünlerde hata büyüyebilir; gerekirse parçalı (ör. 'çevrim = max(elle iş/n, makine)') bir model "
          "denenebilir.",
          "- Model sentetik veriyi, onu üreten formülden öğrendiği için R² yüksek; gerçek veriyle düşecektir.",
          "- Bu sürümün katsayıları ürün ailesine bağlı değil. Yeni bir ürün ailesi için yalnızca işlem sayılarını "
          "girmek yeterli; ancak gerçek veride her ailenin kendine özgü farkları için bir 'aile' değişkeni "
          "eklemek gerekebilir.\n",
          "## Dosyalar\n", "- `src/genel_demo_rev2.py` – hepsini yeniden üretir",
          "- `data/genel_parametreler_rev2.xlsx`",
          "- `outputs/genel_rev2/veri_seti_rev2.xlsx`, `model_rev2.json`, `index_rev2.html`",
          "- Önceki sürüm (rev1) değişmeden duruyor: `src/genel_demo.py`, `outputs/genel/`\n", "## Kaynakça\n"]
    for k in KULLANILAN:
        s.append(f"- [{k}] {KAYNAKLAR[k]}")
    (OUT / "rapor_rev2.md").write_text("\n".join(s) + "\n", encoding="utf-8")


# =====================================================================
# 4) HTML
# =====================================================================
CSS = demo.HTML_SABLON.split("<style>")[1].split("</style>")[0]
HTML = r"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Montaj Çevrim Tahmini Rev2</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>__CSS__
.sablon{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:6px}
.sablon button{padding:8px 12px;font-size:.92rem;border:1px solid var(--cizgi);border-radius:8px;background:var(--bg);color:var(--yazi);cursor:pointer}
.sablon button[aria-pressed=true]{background:var(--vurgu);border-color:var(--vurgu);color:var(--kart)}
.alan small.acik{display:block;font-size:.75rem}
.grup{font-size:.75rem;letter-spacing:.06em;text-transform:uppercase;color:var(--soluk);margin:14px 0 2px}
.grup:first-child{margin-top:0}
.alan.alt label{padding-left:14px;color:var(--soluk)}
button:focus-visible,input:focus-visible{outline:2px solid var(--vurgu);outline-offset:2px}
</style>
</head>
<body>
<main>
<h1>Montaj hattı – çevrim süresi tahmini (genel sürüm, rev2)</h1>
<p class="not">Rev2: zor parça ve vida için "engelli erişim" eki. Dar yerde ya da kısıtlı görüşle yapılan işler ek süre alır.</p>
<div class="demo">Demo – sentetik veriyle eğitilmiştir</div>

<div class="kart sonuc" aria-live="polite">
  <div><div class="deger" id="sure">–</div><div class="etiket">Tahmini çevrim süresi (sn)</div></div>
  <div><div class="deger" id="adet">–</div><div class="etiket">Saatlik üretim (adet)</div></div>
</div>
<div class="uyari" id="uyari"></div>

<div class="kart">
  <h2>Ürün şablonu</h2>
  <p class="not">Şablon seçince işlem sayıları dolar (operatör sayısı değişmez); sonra istediğiniz kadar değiştirebilirsiniz.</p>
  <div class="sablon" id="sablonlar"></div>
</div>

<div class="kart" id="girdiler"></div>

<div class="kart" id="operatorler">
  <h2>Operatörlerin çalışma süreleri</h2>
  <p class="not">Bir çevrimde her operatörün çalıştığı (çubuğun dolu kısmı) ve beklediği (boş kısım) süre.
  İşlem tipi süreleri, iş sırası ve bölünemeyen bağlı işlere göre hesaplanır; makine süreleri operatöre bölünmez.
  Regresyon tahmininden birkaç saniye farklı olabilir.</p>
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
const E = MODEL.hat.element_sn;

function terim(t, v) {
  const n = v.operator;
  if (t.donusum === "x") return v[t.degisken];
  if (t.donusum === "ters") return 1 / n;
  if (t.donusum === "bolu_n") return v[t.degisken] / n;
  if (t.donusum === "maks") { const [a, b] = t.degisken.split(","); return Math.max(v[a], v[b]); }
  throw new Error(t.donusum);
}
function tahmin(v) { let y = MODEL.sabit; for (const t of MODEL.terimler) y += t.katsayi * terim(t, v); return y; }
window.tahmin = tahmin;

function isBloklari(d) {
  const h = E.tasima_sabit + E.tasima_per_kg * d.govde_kg, b = [];
  b.push([d.makine1_sn > 0 ? "Yükleme+Makine1" : "Gövde yükleme", h + d.makine1_sn]);
  const ve = Math.min(d.vida_engelli, d.vida);
  let vidalar = Array(ve).fill(E.vida + E.vida_engelli_ek).concat(Array(d.vida - ve).fill(E.vida));
  for (let i = 0; i < d.parca_zor; i++) {
    const v = Math.min(E.zor_parca_vida, vidalar.length), vs = vidalar.slice(0, v); vidalar = vidalar.slice(v);
    const eng = i < Math.min(d.parca_zor_engelli, d.parca_zor);
    b.push([`ZorParça${i + 1}` + (eng ? "(engelli)" : "") + (v ? `+${v}vida` : ""),
            E.parca_zor + (eng ? E.parca_zor_engelli_ek : 0) + vs.reduce((a, x) => a + x, 0)]);
  }
  for (let i = 0; i < d.parca_kolay; i++) b.push([`KolayParça${i + 1}`, E.parca_kolay]);
  for (let i = 0; i < d.gecme; i++) b.push([`Geçme${i + 1}`, E.gecme]);
  vidalar.forEach((x, i) => b.push([`Vida${i + 1}` + (x > E.vida ? "(engelli)" : ""), x]));
  for (let i = 0; i < d.baglanti; i++) b.push([`Bağlantı${i + 1}`, E.baglanti]);
  for (let i = 0; i < d.kontrol; i++) b.push([`Kontrol${i + 1}`, E.kontrol]);
  b.push([d.makine2_sn > 0 ? "Yükleme+Makine2" : "Ara taşıma", h + d.makine2_sn]);
  b.push(["Etiket+kutulama", h + E.sabit_is]);
  return b;
}
function hatDengele(bl, nOp) {
  const k = bl.length, n = Math.min(nOp, k), on = [0];
  for (const [, t] of bl) on.push(on[on.length - 1] + t);
  const dp = [], kes = [];
  for (let s = 0; s <= n; s++) { dp.push(new Array(k + 1).fill(Infinity)); kes.push(new Array(k + 1).fill(0)); }
  dp[0][0] = 0;
  for (let s = 1; s <= n; s++) for (let i = 1; i <= k; i++) for (let j = s - 1; j < i; j++) {
    const v = Math.max(dp[s - 1][j], on[i] - on[j]);
    if (v < dp[s][i]) { dp[s][i] = v; kes[s][i] = j; }
  }
  const ist = []; let i = k;
  for (let s = n; s >= 1; s--) { const j = kes[s][i]; ist.unshift({ yuk: on[i] - on[j], isler: bl.slice(j, i).map(x => x[0]) }); i = j; }
  while (ist.length < nOp) ist.push({ yuk: 0, isler: [] });
  return { cevrim: dp[n][k], ist, toplam: on[k] };
}

const deger = {}, GRUP = { govde_kg: "Ürün", parca_kolay: "Elle işlemler (operatörler paylaşabilir)",
  makine1_sn: "Makine işlemleri (bölünmez)", operator: "Hat" };
const kutu = document.getElementById("girdiler");
for (const g of MODEL.girdiler) {
  deger[g.ad] = g.varsayilan;
  if (GRUP[g.ad]) { const h = document.createElement("div"); h.className = "grup"; h.textContent = GRUP[g.ad]; kutu.appendChild(h); }
  const d = document.createElement("div");
  d.className = "alan" + ((MODEL.ust || {})[g.ad] ? " alt" : "");
  if (g.ad === "operator") {
    d.innerHTML = `<label>${g.etiket} <small>(${g.min}–${g.max})</small></label><div></div>`;
    const op = document.createElement("div"); op.className = "op";
    for (let i = g.min; i <= g.max; i++) {
      const b = document.createElement("button"); b.type = "button"; b.textContent = i; b.dataset.n = i;
      b.onclick = () => { deger.operator = i; hesapla(); };
      op.appendChild(b);
    }
    d.appendChild(op);
  } else {
    d.innerHTML = `<label for="in_${g.ad}">${g.etiket} <small>(${g.birim}, ${g.min}–${g.max})</small>
      <small class="acik">${g.aciklama}</small></label>
      <input type="number" id="in_${g.ad}" inputmode="decimal" step="${g.adim}" value="${g.varsayilan}">`;
    d.querySelector("input").addEventListener("input", e => {
      deger[g.ad] = e.target.value === "" ? NaN : Number(e.target.value); sablonSec(null); hesapla();
    });
  }
  kutu.appendChild(d);
}
const sabKutu = document.getElementById("sablonlar");
for (const ad of [...Object.keys(MODEL.sablonlar), "Özel"]) {
  const b = document.createElement("button"); b.type = "button"; b.textContent = ad; b.dataset.ad = ad;
  b.onclick = () => {
    if (ad !== "Özel") {
      Object.assign(deger, MODEL.sablonlar[ad]);
      for (const g of MODEL.girdiler) { const el = document.getElementById("in_" + g.ad); if (el) el.value = deger[g.ad]; }
    }
    sablonSec(ad); hesapla();
  };
  sabKutu.appendChild(b);
}
function sablonSec(ad) {
  if (ad === null) ad = Object.keys(MODEL.sablonlar).find(s => Object.keys(MODEL.sablonlar[s]).every(k => MODEL.sablonlar[s][k] === deger[k])) || "Özel";
  sabKutu.querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", b.dataset.ad === ad));
}

function ciz(v) {
  const kI = document.getElementById("istasyonlar"), oz = document.getElementById("hatozet");
  if (!MODEL.girdiler.every(g => Number.isFinite(v[g.ad]) && v[g.ad] >= 0) || v.operator < 1) {
    kI.innerHTML = ""; oz.textContent = "Tüm girdileri doldurun."; return;
  }
  const d = Object.assign({}, v);
  for (const g of MODEL.girdiler) if (g.tamsayi) d[g.ad] = Math.round(d[g.ad]);
  const h = hatDengele(isBloklari(d), d.operator);
  kI.innerHTML = "";
  h.ist.forEach((s, i) => {
    const dar = Math.abs(s.yuk - h.cevrim) < 1e-9, bekle = h.cevrim - s.yuk;
    const el = document.createElement("div");
    el.className = "ist" + (dar ? " darbogaz" : ""); el.dataset.yuk = s.yuk;
    el.innerHTML = `<div class="ust"><span>Operatör ${i + 1}${dar ? '<span class="rozet">darboğaz</span>' : ""}</span>
      <span><b>${s.yuk.toFixed(1)} sn</b> çalışma · ${bekle.toFixed(1)} sn bekleme</span></div>
      <div class="iz" role="img" aria-label="Operatör ${i + 1}: ${s.yuk.toFixed(1)} sn çalışma, ${bekle.toFixed(1)} sn bekleme">
      <div class="dolu" style="width:${(100 * s.yuk / h.cevrim).toFixed(2)}%"></div></div>
      <div class="isler">${s.isler.length ? s.isler.join(" → ") : "iş atanmadı"}</div>`;
    el.title = `Operatör ${i + 1}: %${(100 * s.yuk / h.cevrim).toFixed(0)} doluluk`;
    kI.appendChild(el);
  });
  oz.innerHTML = `Toplam iş içeriği <b>${h.toplam.toFixed(1)} sn</b> · en yüklü operatör (hesaplanan çevrim) ` +
    `<b>${h.cevrim.toFixed(1)} sn</b> · denge kaybı <b>%${(100 * (d.operator * h.cevrim / h.toplam - 1)).toFixed(1)}</b>`;
}

function hesapla() {
  document.querySelectorAll(".op button").forEach(b => b.setAttribute("aria-pressed", Number(b.dataset.n) === deger.operator));
  const dis = [];
  for (const g of MODEL.girdiler) {
    const v = deger[g.ad], kotu = !Number.isFinite(v) || v < g.min || v > g.max;
    const inp = document.getElementById("in_" + g.ad); if (inp) inp.classList.toggle("disarida", kotu);
    if (kotu) dis.push(`${g.etiket} (${g.min}–${g.max} ${g.birim})`);
  }
  for (const [alt, ust] of Object.entries(MODEL.ust || {})) {
    const kotu = deger[alt] > deger[ust];
    const inp = document.getElementById("in_" + alt); if (inp && kotu) inp.classList.add("disarida");
    const ustEt = MODEL.girdiler.find(g => g.ad === ust).etiket;
    if (kotu) dis.push(`${ustEt}: engelli sayısı toplamdan büyük olamaz (hesapta toplam kadar alındı)`);
  }
  const u = document.getElementById("uyari");
  u.style.display = dis.length ? "block" : "none";
  u.textContent = dis.length ? "Uyarı: model bu aralıkta eğitilmedi → " + dis.join("; ") : "";
  const s = MODEL.girdiler.every(g => Number.isFinite(deger[g.ad])) ? tahmin(deger) : NaN;
  const sEl = document.getElementById("sure");
  sEl.dataset.ham = s;
  sEl.textContent = Number.isFinite(s) ? s.toFixed(1) : "–";
  document.getElementById("adet").textContent = Number.isFinite(s) && s > 0 ? (3600 / s).toFixed(1) : "–";
  ciz(deger);
}
document.getElementById("denklem").textContent = "çevrim_sn = " + MODEL.sabit.toFixed(3) + " " +
  MODEL.terimler.map(t => (t.katsayi >= 0 ? "+ " : "− ") + Math.abs(t.katsayi).toFixed(3) + "·" + t.ad).join(" ");
document.getElementById("bilgi").textContent =
  `R² = ${MODEL.r2.toFixed(4)}, düzeltilmiş R² = ${MODEL.duzeltilmis_r2.toFixed(4)}, ${MODEL.n_gozlem} sentetik gözlem.`;
sablonSec(null);
hesapla();
</script>
</body>
</html>
"""


def html_yaz(model, yayin=None):
    html = HTML.replace("__CSS__", CSS).replace("__MODEL_JSON__", json.dumps(model, ensure_ascii=False))
    (OUT / "index_rev2.html").write_text(html, encoding="utf-8")
    if yayin:
        g = re.sub(r"<!doctype html>\s*<html[^>]*>\s*<head>\s*<meta charset=\"utf-8\">\s*<meta name=\"viewport\"[^>]*>\s*",
                   "", html, flags=re.I)
        g = g.replace("</head>\n<body>\n", "").replace("</body>\n</html>\n", "")
        Path(yayin).write_text(g, encoding="utf-8")


# =====================================================================
# 5) DOĞRULAMA
# =====================================================================
JS = r"""
const { chromium } = require('playwright');
const [,, htmlYolu, ornekYolu] = process.argv;
const ornekler = JSON.parse(require('fs').readFileSync(ornekYolu, 'utf8'));
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 390, height: 844 } });
  await p.goto('file://' + htmlYolu);
  const sonuc = [];
  for (const o of ornekler) {
    if (o.__sablon) await p.click(`.sablon button[data-ad="${o.__sablon}"]`);
    for (const [k, v] of Object.entries(o)) {
      if (k === '__sablon') continue;
      if (k === 'operator') await p.click(`.op button[data-n="${v}"]`);
      else await p.fill(`#in_${k}`, String(v));
    }
    sonuc.push({ arayuz: await p.$eval('#sure', e => Number(e.dataset.ham)),
                 yukler: await p.$$eval('#istasyonlar .ist', l => l.map(e => Number(e.dataset.yuk))) });
  }
  const tasma = await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  console.log(JSON.stringify({ sonuc, tasma }));
  await b.close();
})();
"""


def dogrula(model):
    rng = np.random.default_rng(SEED + 1)
    ornekler = [dict(SABLONLAR["Washer tank"], operator=2), dict(SABLONLAR["Dış dikiz aynası"], operator=3)]
    for n in range(1, 5):
        o = {}
        for g in model["girdiler"]:
            if g["ad"] == "operator":
                o["operator"] = n
            elif g["ad"] in UST:
                o[g["ad"]] = int(rng.integers(0, o[UST[g["ad"]]] + 1))
            elif g["tamsayi"]:
                o[g["ad"]] = int(rng.integers(g["min"], g["max"] + 1))
            else:
                o[g["ad"]] = round(float(rng.uniform(g["min"], g["max"])), 1)
        ornekler.append(o)
    py = [py_tahmin(model, o) for o in ornekler]
    pyy = []
    for o in ornekler:
        _, y = demo.hat_dengele([x for _, x in is_bloklari(o)], o["operator"])
        pyy.append([float(x) for x in y] + [0.0] * (o["operator"] - len(y)))
    print("\n5) Python ↔ HTML karşılaştırması")
    if shutil.which("node") is None:
        print("   node yok; atlandı.")
        return
    with tempfile.TemporaryDirectory() as tmp:
        js, oy = Path(tmp) / "d.js", Path(tmp) / "o.json"
        js.write_text(JS)
        oy.write_text(json.dumps(ornekler))
        r = subprocess.run(["node", str(js), str(OUT / "index_rev2.html"), str(oy)], capture_output=True, text=True)
    if r.returncode != 0:
        print("   Playwright çalışmadı; atlandı.", r.stderr[:300])
        return
    c = json.loads(r.stdout)
    hepsi = True
    for o, p_, h, yk in zip(ornekler, py, c["sonuc"], pyy):
        e1 = abs(p_ - h["arayuz"]) < 1e-9
        e2 = len(yk) == len(h["yukler"]) and all(abs(a - b) < 1e-9 for a, b in zip(yk, h["yukler"]))
        hepsi &= e1 and e2
        print(f"   {o} → Python {p_:.4f} | HTML {h['arayuz']:.4f} | yükler {'EŞLEŞTİ' if e2 else 'FARKLI'}"
              f"  {'EŞLEŞTİ' if e1 else 'FARKLI!'}")
    print(f"   Telefon genişliğinde (390 px) yatay taşma: {'VAR' if c['tasma'] else 'yok'}")
    if not hepsi:
        raise SystemExit("HATA: Python ve HTML eşleşmiyor.")
    print("   Tüm örneklerde Python ve HTML sonuçları birebir aynı.")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("1) Parametreler:", parametre_tablosu_yaz().relative_to(KOK))
    df = veri_uret()
    with pd.ExcelWriter(OUT / "veri_seti_rev2.xlsx", engine="openpyxl") as xw:
        df.to_excel(xw, sheet_name="veri", index=False)
        demo.excel_bicimle(xw.sheets["veri"])
    print(f"2) Veri: outputs/genel_rev2/veri_seti_rev2.xlsx ({len(df)} satır)")
    final, sec, A, adim = ileri_secim(df)
    model = model_olustur(final, sec, A)
    (OUT / "model_rev2.json").write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding="utf-8")
    kars = karsilastir(df)
    rapor_yaz(df, final, sec, adim, model, len(A), kars)
    for ad, r in kars[0].items():
        print(f"   {ad}: test RMSE {r['rmse']:.2f} sn, sapma " +
              ", ".join(f"{g} {v[0]:+.2f}" for g, v in r["sapma"].items()))
    print(f"3) Model: {sec}\n   R² = {final.rsquared:.4f}, düz. R² = {final.rsquared_adj:.4f}")
    html_yaz(model, sys.argv[1] if len(sys.argv) > 1 else None)
    print("4) Arayüz: outputs/genel_rev2/index_rev2.html")
    dogrula(model)


if __name__ == "__main__":
    main()
