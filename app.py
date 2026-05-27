import streamlit as st
import pandas as pd
import requests
import datetime
import math
import os
import pickle
import numpy as np
import io
import zipfile
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

# ============================================================
# NAČÍTANIE MODELOV A PIPELINE CONFIG Z GITHUBU
# ============================================================
GITHUB_RAW = "https://raw.githubusercontent.com/mecasysdata/protypB/main"

@st.cache_resource
def load_models_and_config():
    import urllib.request
    files = {
        "model_KR_M1.pkl":      f"{GITHUB_RAW}/model_KR_M1.pkl",
        "model_KR_M2.pkl":      f"{GITHUB_RAW}/model_KR_M2.pkl",
        "model_STV_M1.pkl":     f"{GITHUB_RAW}/model_STV_M1.pkl",
        "model_STV_M2.pkl":     f"{GITHUB_RAW}/model_STV_M2.pkl",
        "pipeline_config.pkl":  f"{GITHUB_RAW}/pipeline_config.pkl",
    }
    for fname, url in files.items():
        if not os.path.exists(fname):
            urllib.request.urlretrieve(url, fname)
    models = {
        "KR_M1":  pickle.load(open("model_KR_M1.pkl",  "rb")),
        "KR_M2":  pickle.load(open("model_KR_M2.pkl",  "rb")),
        "STV_M1": pickle.load(open("model_STV_M1.pkl", "rb")),
        "STV_M2": pickle.load(open("model_STV_M2.pkl", "rb")),
    }
    config = pickle.load(open("pipeline_config.pkl", "rb"))
    return models, config

models, pipeline_config = load_models_and_config()

# ============================================================
# CONFIG
# ============================================================
st.set_page_config(layout="wide", page_title="MEC Calculation")

SHEET_URL        = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSuHQWbpryWNerWr8aKKheHbzTPhXI6lS7YH1sL5zwFIIzLfpTZz47acY_ua2e_fVqEcfxMBe5wnjue/pub?gid=0&single=true&output=csv"
APP_SCRIPT_URL   = "https://script.google.com/macros/s/AKfycbwNR33wxSNXJFo9-o2otM-mdKQE22s3i3y5n08dY7eogGhhKDTasiPn3zaOoSihppTq/exec"
CP_APP_SCRIPT_URL= "https://script.google.com/macros/s/AKfycbwx7sAeUheQf1dm2r6k7jTslD9ufhq2yk1OWZXWjxVkeZOttVI949GIiPGx8l1B3cIP/exec"
POL_URL          = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQf4EiqZt1grkazJgfYWVhG0M8FGLNCjaGk6dcXhO3r04JQuZ9Qxv1jelDo3c8hBLy7Ny5C1pZqvbfS/pub?gid=0&single=true&output=csv"
KOOP_URL         = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRXlw1ybqaKDNFzTXEBQXtyZDSrLeauZ6l_1jZGuq5_KU8RPjrz4M_B5RGIAF9XTca8mSCSflH6pZE8/pub?gid=1711993868&single=true&output=csv"

# ============================================================
# SESSION STATE
# ============================================================
for key, default in [
    ("predicted_time", 0.0), ("time_confirmed", False),
    ("predicted_price", 0.0), ("price_confirmed", False),
    ("kosik", []), ("last_item_name", ""),
    ("note_text", ""), ("last_inputs_snapshot", {}),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ============================================================
# LOGO
# ============================================================
col_logo, col_title = st.columns([1, 5])
with col_logo:
    try:
        st.image("logo.png", width=150)
    except:
        st.write("🖼️ Logo")
with col_title:
    st.title("MEC Calculation")

st.divider()

# ============================================================
# NAČÍTANIE DÁT
# ============================================================
@st.cache_data
def load_customers():
    df = pd.read_csv(SHEET_URL)
    df.columns = df.columns.str.lower().str.strip()
    return df

@st.cache_data
def load_polotovary():
    df = pd.read_csv(POL_URL)
    df.columns = df.columns.str.lower().str.strip()
    return df

@st.cache_data
def load_kooperacie():
    df = pd.read_csv(KOOP_URL)
    df.columns = df.columns.str.lower().str.strip()
    return df

df_zak       = load_customers()
df_pol       = load_polotovary()
df_kooperacie= load_kooperacie()

# ============================================================
# ZÁKAZNÍK
# ============================================================
zakaznici = df_zak["zakaznik"].tolist()
if "force_customer" in st.session_state:
    fc = st.session_state["force_customer"]
    if fc not in zakaznici:
        zakaznici.append(fc)
zakaznici.append("+ Pridať nového zákazníka")

default_index = 0
if "force_customer" in st.session_state:
    fc = st.session_state["force_customer"]
    if fc in zakaznici:
        default_index = zakaznici.index(fc)

col1, col2, col3, col4, col5, col6, col7 = st.columns([1.2, 1.2, 1.6, 1.2, 1.6, 1.2, 0.8])
with col1:
    date = st.date_input("Dátum", datetime.date.today())
with col2:
    cp_nazov = st.text_input("Označenie CP")
with col3:
    vybrany = st.selectbox("Zákazník", zakaznici, index=default_index)
with col4:
    krajina_input = ""
    if vybrany != "+ Pridať nového zákazníka":
        k_df = df_zak.loc[df_zak["zakaznik"] == vybrany, "krajina"]
        krajina_input = k_df.values[0] if len(k_df) > 0 else "OTHER"
    st.text_input("Krajina zákazníka", krajina_input, disabled=True)

# Lojalita — na pozadí, používateľ nevidí
if vybrany == "+ Pridať nového zákazníka":
    lojalita_val = 0.5
    with col5:
        novy_zak = st.text_input("Nový zákazník")
    with col6:
        nova_krajina = st.text_input("Krajina nového zákazníka")
    with col7:
        if st.button("Uložiť"):
            if novy_zak and nova_krajina:
                r = requests.post(APP_SCRIPT_URL, json={"zakaznik": novy_zak, "krajina": nova_krajina})
                if r.status_code == 200:
                    st.session_state["force_customer"] = novy_zak
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("Chyba")
else:
    loj_df = df_zak.loc[df_zak["zakaznik"] == vybrany, "lojalita"]
    lojalita_val = float(loj_df.values[0]) if len(loj_df) > 0 and not pd.isna(loj_df.values[0]) else 0.5

st.divider()

# ============================================================
# ITEM + TVAR + ROZMERY
# ============================================================
col1, col2, col3, col4, col5, col6, col7, col8, col9 = st.columns([1.6, 1, 1, 1, 1, 1, 1, 1, 1])
with col1:
    item = st.text_input("ITEM")
with col2:
    pocet_kusov = st.number_input("Počet kusov", min_value=1, step=1)
with col3:
    narocnost = st.selectbox("Náročnosť", [1, 2, 3, 4, 5])
with col4:
    tvar = st.selectbox("Tvar položky", ["STV", "KR"])

dp = s = v = 0.0
d_mm = l_mm = 0.0
if tvar == "STV":
    with col5:
        dp = st.number_input("D/P (mm)", min_value=0.0, step=0.1)
    with col6:
        s = st.number_input("S (mm)", min_value=0.0, step=0.1)
    with col7:
        v = st.number_input("V (mm)", min_value=0.0, step=0.1)
else:
    with col5:
        d_mm = st.number_input("D (mm)", min_value=0.0, step=0.1)
    with col6:
        l_mm = st.number_input("L (mm)", min_value=0.0, step=0.1)

st.divider()

# ============================================================
# POLOTOVAR
# ============================================================
col1, col2, col3, col4, col5 = st.columns([1.2, 1.6, 2.4, 1.2, 1.2])

with col1:
    material = st.selectbox("Materiál", sorted(df_pol["material"].dropna().unique().tolist()), key="mat_select")
with col2:
    akosti = sorted(df_pol[df_pol["material"] == material]["akost"].dropna().unique().tolist())
    akost_vyber = st.multiselect("Akosť", akosti, key="akost_select")
with col3:
    df_filtered = df_pol[df_pol["akost"].isin(akost_vyber)]
    if tvar == "KR":
        df_filtered = df_filtered[df_filtered["tvar"].isin(["KR", "6HR", "TR"])]
    polozky_dict = {
        idx: f"[{r['akost']}] {r['názov']} | {r['rozmer1']}x{r['rozmer2']}x{r['rozmer3']} | Cena: {r['cena']} €/bm"
        for idx, r in df_filtered.iterrows()
    }
    polozky_dict["new"] = "+ Pridať nový polotovar"
    polotovar_key = st.selectbox(
        "Polotovar", list(polozky_dict.keys()),
        format_func=lambda x: polozky_dict[x], key="polotovar_select"
    )

cena_bm = float(df_filtered.loc[polotovar_key]["cena"]) if polotovar_key != "new" else 0.0
dlzka_mm = l_mm if tvar == "KR" else dp
cena_mat_ks = round(cena_bm * (dlzka_mm / 1000), 4)

with col4:
    st.write("Cena €/bm")
    st.write(round(cena_bm, 4))
with col5:
    st.write("Cena mat/ks")
    st.write(round(cena_mat_ks, 4))

# ============================================================
# NOVÝ POLOTOVAR
# ============================================================
material_list = sorted(df_pol["material"].dropna().unique().tolist())
if polotovar_key == "new":
    st.markdown("### ➕ Pridať nový polotovar")
    with st.container():
        box1, box2, box3, box4 = st.columns([1.2, 1.2, 1.2, 1.2])
        box5, box6, box7, box8 = st.columns([1.2, 1.2, 1.2, 1.2])
        with box1:
            novy_material = st.selectbox("Materiál (nový)", material_list,
                index=material_list.index(material), key="novy_material")
        with box2:
            nova_akost = st.text_input("Akosť (nová)",
                value=akost_vyber[0] if akost_vyber else "", key="nova_akost")
        with box3:
            novy_nazov = st.text_input("Názov (nový)", key="novy_nazov")
        with box4:
            novy_tvar = st.selectbox("Tvar (nový)", ["STV", "KR", "6HR", "TR"], key="novy_tvar")
        with box5: r1 = st.text_input("Rozmer 1", key="r1_new")
        with box6: r2 = st.text_input("Rozmer 2", key="r2_new")
        with box7: r3 = st.text_input("Rozmer 3", key="r3_new")
        with box8: cena_new = st.number_input("Cena €/bm", min_value=0.0, step=0.1, key="cena_new")
        if st.button("Uložiť nový polotovar", key="ulozit_polotovar"):
            if novy_material and nova_akost and novy_nazov and novy_tvar and r1 and r2 and r3 and cena_new:
                payload = {"Názov": novy_nazov, "Akost": nova_akost, "Material": novy_material,
                           "Cena": cena_new, "Tvar": novy_tvar, "Rozmer1": r1, "Rozmer2": r2, "Rozmer3": r3}
                r = requests.post(
                    "https://script.google.com/macros/s/AKfycbzyZxjTplhk010oq7ozvovAGx5lRx72PjqUvoJUrNazx_jRfq7lqfQgbeHYG9O-NCcX/exec",
                    json=payload)
                if r.status_code == 200:
                    st.session_state["force_akost"] = nova_akost
                    st.success("Polotovar bol uložený.")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("Nepodarilo sa uložiť polotovar.")
            else:
                st.error("Vyplň všetky polia.")

# ============================================================
# SUBCATEGORY — opravená logika s správnymi prioritami
# ============================================================
def urci_subcategory(akost, material):
    """
    Priorita:
    1. Špeciálne textové výnimky (TOOLOX a pod.)
    2. Špeciálne DIN čísla (výnimky pred všeobecnými rozsahmi)
    3. Všeobecné DIN rozsahy podľa materiálu
    4. Plasty — až na konci, PE až za PEEK/PET/PMMA/PC
    """
    ak = str(akost).strip().replace(" ", "").replace(",", ".")
    mat = str(material).strip().upper()

    # 1. Textové výnimky
    ak_up = ak.upper()
    if "TOOLOX" in ak_up:
        return "TOOL"

    # 2. Skús či je to DIN číslo
    try:
        wn = float(ak)
        is_din = True
    except ValueError:
        is_din = False

    if is_din:
        # --- OCEĽ ---
        if "OCEL" in mat or "OCEĽ" in mat:
            # Špeciálne výnimky pre oceľ — pred všeobecnými rozsahmi
            if wn == 1.3505 or (1.3500 <= wn <= 1.3599):
                return "TOOL"
            if (1.2900 <= wn <= 1.2999):
                return "TOOL"
            if (1.2000 <= wn <= 1.3299):
                return "TOOL"
            if (1.3300 <= wn <= 1.3899):
                return "HSS"
            if (1.3900 <= wn <= 1.3999):
                return "ALLOYED"
            if (1.6500 <= wn <= 1.8999):
                return "ALLOYED"
            if (1.1500 <= wn <= 1.6499):
                return "LOWAL"
            if (1.0000 <= wn <= 1.1499):
                return "UNALL"
            return "OCEĽ_OTHER"

        # --- NEREZ ---
        if "NEREZ" in mat:
            # Špeciálne výnimky pre nerez
            if (1.4700 <= wn <= 1.4799) or (1.4800 <= wn <= 1.4899):
                return "STAIN-SPEC"
            if wn == 1.4308 or wn == 1.4408:
                return "AUST"
            # Všeobecné rozsahy
            if (1.4000 <= wn <= 1.4099):
                return "FERR"
            if (1.4100 <= wn <= 1.4199):
                return "MART"
            if wn == 1.4462 or (1.4400 <= wn <= 1.4499):
                return "DUPX"
            if (1.4300 <= wn <= 1.4599):
                return "AUST"
            if (1.4600 <= wn <= 1.4999):
                return "STAIN-SPEC"
            return "AUST"

        # --- FAREBNÉ KOVY ---
        if "FAREB" in mat:
            if (2.0000 <= wn <= 2.0199): return "CU"
            if (2.0200 <= wn <= 2.0599): return "BRASS"
            if (2.0900 <= wn <= 2.1399): return "BRONZE"
            if (3.0000 <= wn <= 3.5999): return "ALU"
            if (3.7000 <= wn <= 3.7999): return "TI"
            if (2.4000 <= wn <= 2.4999): return "NI-SPEC"
            return "FK_OTHER"

        # --- LIATINA ---
        if "LIATINA" in mat:
            if (0.6000 <= wn <= 0.6999): return "CAST-GG"
            if (0.7000 <= wn <= 0.7999): return "CAST-GGG"
            if (0.8000 <= wn <= 0.9699): return "CAST-TEMP"
            return "LIATINA_OTHER"

    # 3. Plasty — textové mapovanie, PE až na konci za PEEK/PET/PMMA
    if "PLAST" in mat:
        ak_up = ak.upper()
        # Dlhšie/špecifickejšie reťazce PRED kratšími (PE musí byť až na konci)
        if ak_up.startswith("POM"):    return "POM"
        if ak_up.startswith("PEEK"):   return "PEEK"   # PRED PE !
        if ak_up.startswith("PET"):    return "PET"    # PRED PE !
        if ak_up.startswith("PETG"):   return "PET"
        if ak_up.startswith("PET-G"):  return "PET"
        if ak_up.startswith("PC"):     return "PC"     # PRED PP, PVC !
        if ak_up.startswith("PVC"):    return "PVC"
        if ak_up.startswith("PTFE"):   return "PTFE"
        if ak_up.startswith("PUR"):    return "PUR"
        if ak_up.startswith("PMMA"):   return "PMMA"
        if ak_up.startswith("PP"):     return "PP"     # PRED PE !
        if ak_up.startswith("PA"):     return "PA"
        if ak_up.startswith("EPDM"):   return "RUBBER"
        if ak_up.startswith("GUMA"):   return "RUBBER"
        if ak_up.startswith("RUBBER"): return "RUBBER"
        if ak_up.startswith("LEXAN"):  return "PC"
        if ak_up.startswith("PLEXISKLO"): return "PMMA"
        if ak_up.startswith("PLEXIGLASS"): return "PMMA"
        if ak_up.startswith("AKRYLÁT"): return "PMMA"
        if ak_up.startswith("EBABOARD"): return "PUR"
        if ak_up.startswith("EBABLOCK"): return "PUR"
        if ak_up.startswith("HDPE"):   return "PE"
        if ak_up.startswith("PE"):     return "PE"     # PE AŽ NA KONCI !
        return "PLAST_OTHER"

    return f"{mat}_OTHER"


# ============================================================
# HUSTOTY
# ============================================================
HUSTOTY = {
    "UNALL": 7900, "LOWAL": 7900, "ALLOYED": 7900, "TOOL": 7900, "HSS": 7900,
    "AUST": 8000, "MART": 8000, "DUPX": 8000, "FERR": 8000, "STAIN-SPEC": 8000,
    "CU": 9000, "BRASS": 9000, "BRONZE": 9000,
    "ALU": 2900, "TI": 4500, "NI-SPEC": 8500,
    "POM": 1500, "PE": 1000, "PA": 1200, "PP": 1000, "PEEK": 1400,
    "PET": 1700, "PC": 1500, "PVC": 1700, "PTFE": 3000, "PUR": 2000,
    "PMMA": 1600, "RUBBER": 7900,
    "CAST-GG": 7150, "CAST-GGG": 7250, "CAST-TEMP": 7400,
}

# ============================================================
# RIADOK 4 — KOOPERÁCIE + GEOMETRIA + HUSTOTA
# ============================================================
col1, col2, col3, col4, col5, col6, col7 = st.columns([1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.4])

with col1:
    kooperacia = st.checkbox("Koop.", key="koop_checkbox")

akost_pre_subcat = akost_vyber[0] if akost_vyber else ""
subcategory = urci_subcategory(akost_pre_subcat, material)

with col2:
    st.write("Subcategory")
    st.write(subcategory)

with col3:
    hustota_default = HUSTOTY.get(subcategory, 7900)
    hustota = st.number_input("Hustota", value=float(hustota_default), step=10.0)

# Geometria — zosúladená s tréningom
if tvar == "KR":
    D_m = d_mm / 1000
    L_m = l_mm / 1000
    objem        = math.pi * (D_m / 2) ** 2 * L_m          # m³
    plocha_plasta= math.pi * D_m * L_m                      # m² — len plášť (tréning!)
    plocha_dm2   = (plocha_plasta + 2 * math.pi * (D_m/2)**2) * 100  # dm² pre zobrazenie
    geom_koef    = L_m / D_m if D_m > 0 else 0             # štíhlosť
else:
    DP_m = dp / 1000
    S_m  = s  / 1000
    V_m  = v  / 1000
    objem        = DP_m * S_m * V_m                         # m³
    plocha_plasta= 2 * (DP_m + S_m) * V_m                  # m² — plášť
    plocha_dm2   = 2 * (S_m * V_m + S_m * DP_m + V_m * DP_m) * 100  # dm²
    geom_koef    = DP_m / S_m if S_m > 0 else 0            # pomer strán

hmotnost = objem * hustota  # kg

with col4:
    st.write("Objem (m³)")
    st.write(round(objem, 6))
with col5:
    st.write("Hmotnosť (kg)")
    st.write(round(hmotnost, 3))
with col6:
    st.write("Plocha (dm²)")
    st.write(round(plocha_dm2, 2))

# Kooperácia
if kooperacia:
    df_koop = df_kooperacie[df_kooperacie["material"] == material]
    druhy = df_koop["druh"].unique().tolist()
    with col1:
        vyber_koop = st.selectbox("Typ", druhy)
    riadok     = df_koop[df_koop["druh"] == vyber_koop].iloc[0]
    jednotka   = riadok["jednotka"]
    tarifa     = float(riadok["tarifa"])
    min_zakazka= float(riadok["minimalna zakazka"])
    if jednotka == "kg":
        cena_ks = hmotnost * tarifa
    elif jednotka == "dm2":
        cena_ks = plocha_dm2 * tarifa
    else:
        cena_ks = 0.0
    cena_spolu = cena_ks * pocet_kusov
    if cena_spolu < min_zakazka:
        cena_ks = min_zakazka / pocet_kusov
else:
    cena_ks = 0.0

vstupne_naklady_ks = cena_mat_ks + cena_ks

with col7:
    st.write("Vstupné €/ks")
    st.write(round(vstupne_naklady_ks, 3))

st.divider()

# ============================================================
# SNAPSHOT — reset predikcií pri zmene vstupov
# ============================================================
current_snapshot = {
    "item": item, "pocet_kusov": pocet_kusov, "narocnost": narocnost, "tvar": tvar,
    "dp": dp, "s": s, "v": v, "d_mm": d_mm, "l_mm": l_mm,
    "material": material, "akost": tuple(akost_vyber),
    "polotovar_key": polotovar_key, "kooperacia": kooperacia, "hustota": hustota,
}
if st.session_state.last_inputs_snapshot and current_snapshot != st.session_state.last_inputs_snapshot:
    st.session_state.predicted_time  = 0.0
    st.session_state.time_confirmed  = False
    st.session_state.predicted_price = 0.0
    st.session_state.price_confirmed = False
st.session_state.last_inputs_snapshot = current_snapshot

# ============================================================
# TARGET ENCODING — pomocné funkcie
# ============================================================
def te_transform(value, mapping, global_mean):
    """Aplikuje target encoding na jednu hodnotu."""
    return mapping.get(str(value), global_mean)

def get_kraj_encoded(krajina, model_key):
    """Vráti target-encoded hodnotu krajiny pre daný model."""
    enc = pipeline_config["encodings"]
    tvar_key = "kr" if tvar == "KR" else "stv"
    suffix = "m2"  # krajina je len v M2
    mapping   = enc[tvar_key][f"kraj_{suffix}"]
    global_mean = enc[tvar_key][f"kraj_{suffix}_gm"]
    kraj = str(krajina).strip() if krajina else "OTHER"
    if not kraj:
        kraj = "OTHER"
    return te_transform(kraj, mapping, global_mean)

def get_sub_encoded(subcat, model_suffix):
    """Vráti target-encoded hodnotu subcategory pre m1 alebo m2."""
    enc = pipeline_config["encodings"]
    tvar_key = "kr" if tvar == "KR" else "stv"
    mapping     = enc[tvar_key][f"sub_{model_suffix}"]
    global_mean = enc[tvar_key][f"sub_{model_suffix}_gm"]
    return te_transform(subcat, mapping, global_mean)

# ============================================================
# AI PREDIKCIE
# ============================================================
cols = st.columns([1, 1.2, 0.8, 1.2, 1, 1.2, 0.8, 1.2])

# ── PREDIKCIA ČASU ──────────────────────────────────────────
with cols[0]:
    if st.button("🚀 Predikuj čas"):
        try:
            model_key = f"{tvar}_M1"
            m = models[model_key]

            log_pocet = np.log1p(pocet_kusov)
            log_hmot  = np.log1p(hmotnost)
            sub_enc   = get_sub_encoded(subcategory, "m1")

            if tvar == "KR":
                log_pp = np.log1p(plocha_plasta)
                X = pd.DataFrame([{
                    "log_pocet_kusov":  log_pocet,
                    "v_narocnost_ord":  float(narocnost),
                    "sub_enc_m1":       sub_enc,
                    "log_hmotnost":     log_hmot,
                    "log_plocha_plasta":log_pp,
                }])
            else:  # STV
                log_s = np.log1p(s)
                X = pd.DataFrame([{
                    "log_pocet_kusov": log_pocet,
                    "log_hmotnost":    log_hmot,
                    "v_narocnost_ord": float(narocnost),
                    "log_S":           log_s,
                    "sub_enc_m1":      sub_enc,
                    "geom_koef":       geom_koef,
                }])

            pred_log = m.predict(X)[0]
            st.session_state.predicted_time = round(np.expm1(pred_log), 2)
            st.session_state.time_confirmed = False
            st.rerun()
        except Exception as e:
            st.error(f"Chyba predikcie času: {e}")

if st.session_state.get("predicted_time", 0) > 0:
    with cols[1]:
        st.info(f"Čas: {st.session_state.predicted_time} min")
        new_time = st.number_input("Uprav čas (min)", value=st.session_state.predicted_time, step=1.0)
        if st.button("✅ Potvrdiť čas"):
            st.session_state.predicted_time = new_time
            st.session_state.time_confirmed = True
            st.rerun()

# ── PREDIKCIA CENY ───────────────────────────────────────────
with cols[4]:
    if st.button("💰 Predikuj cenu", disabled=not st.session_state.get("time_confirmed", False)):
        try:
            model_key = f"{tvar}_M2"
            m = models[model_key]

            log_cas    = np.log1p(st.session_state.predicted_time)
            log_vstup  = np.log1p(vstupne_naklady_ks)
            kraj_enc   = get_kraj_encoded(krajina_input, model_key)

            X = pd.DataFrame([{
                "log_cas":                       log_cas,
                "log_cena_material_predpoklad":  log_vstup,
                "kraj_enc_m2":                   kraj_enc,
                "LOYALITY":                      lojalita_val,
            }])

            pred_log = m.predict(X)[0]
            st.session_state.predicted_price = round(np.expm1(pred_log), 2)
            st.session_state.price_confirmed = False
            st.rerun()
        except Exception as e:
            st.error(f"Chyba predikcie ceny: {e}")

if st.session_state.get("predicted_price", 0) > 0:
    with cols[5]:
        st.success(f"Cena: {st.session_state.predicted_price} €")
        new_price = st.number_input("Uprav cenu (€/ks)", value=st.session_state.predicted_price, step=0.1)
        if st.button("✅ Potvrdiť cenu"):
            st.session_state.predicted_price = new_price
            st.session_state.price_confirmed = True
            st.rerun()

# ============================================================
# KOŠÍK
# ============================================================
def vytvor_cp_riadok():
    cas_min = round(st.session_state.predicted_time, 2)
    jednotkova_cena   = st.session_state.predicted_price
    cena_polozky_spolu= round(jednotkova_cena * pocet_kusov, 2)
    return {
        "Dátum CP": date.strftime("%d.%m.%Y"),
        "Číslo CP": cp_nazov,
        "Zákazník": vybrany,
        "Krajina": krajina_input,
        "ITEM": item,
        "Tvar": tvar,
        "Materiál": material,
        "Akosť": ", ".join(akost_vyber) if akost_vyber else "",
        "Rozmer D / DP": dp if tvar == "STV" else d_mm,
        "Rozmer L / S":  s  if tvar == "STV" else l_mm,
        "Rozmer V": v if tvar == "STV" else 0.0,
        "Hustota": hustota,
        "Hmotnosť kusu (kg)": round(hmotnost, 3),
        "Náročnosť": narocnost,
        "J.cena materiálu (€/bm)": round(cena_bm, 4),
        "Náklad materiál (€/ks)":  round(cena_mat_ks, 4),
        "Náklad kooperácia (€/ks)":round(cena_ks, 4),
        "Vstupné náklady (€/ks)":  round(vstupne_naklady_ks, 4),
        "Čas (min)": cas_min,
        "Jednotková cena (€/ks)": jednotkova_cena,
        "Počet kusov": pocet_kusov,
        "Cena položky spolu (€)": cena_polozky_spolu,
    }

with cols[7]:
    can_add = (
        st.session_state.get("time_confirmed", False)
        and st.session_state.get("price_confirmed", False)
        and item.strip() != ""
    )
    if st.button("🧺 Pridať do košíka", disabled=not can_add):
        st.session_state.kosik.append(vytvor_cp_riadok())
        st.session_state.predicted_time  = 0.0
        st.session_state.time_confirmed  = False
        st.session_state.predicted_price = 0.0
        st.session_state.price_confirmed = False
        st.session_state.last_inputs_snapshot = {}
        st.success("Položka bola pridaná do košíka.")
        st.rerun()

st.divider()

if st.session_state.kosik:
    st.subheader("Košík – položky v cenovej ponuke")
    df_kosik = pd.DataFrame(st.session_state.kosik)
    st.dataframe(df_kosik, use_container_width=True)
    celkova_cena = df_kosik["Cena položky spolu (€)"].sum()
    st.markdown(f"### Celková cena ponuky: **{round(celkova_cena, 2)} €**")

st.session_state.note_text = st.text_area(
    "Poznámka pre zákazníka (NOTE v PDF)", value=st.session_state.note_text)

# ============================================================
# PDF FUNKCIE — nezmenené
# ============================================================
def generate_customer_pdf(kosik, cp_nazov, date, zakaznik, krajina, note_text, total_price):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 40
    c.setFont("Helvetica-Bold", 11); c.drawString(40, y, "MECASYS s.r.o."); y -= 14
    c.setFont("Helvetica", 10)
    for line in ["Oravská Polhora 455", "029 47 Oravská Polhora", "Slovenská republika"]:
        c.drawString(40, y, line); y -= 14
    y -= 6
    c.setFont("Helvetica-Bold", 11); c.drawString(40, y, f"Price offer: {cp_nazov}"); y -= 14
    c.setFont("Helvetica", 10)
    c.drawString(40, y, f"Date: {date.strftime('%d.%m.%Y')}"); y -= 14
    c.drawString(40, y, f"Customer: {zakaznik}"); y -= 14
    c.drawString(40, y, f"Country: {krajina}"); y -= 20
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, y, "ITEM"); c.drawString(220, y, "Qty")
    c.drawString(280, y, "Price/pcs"); c.drawString(370, y, "Total"); y -= 14
    c.setFont("Helvetica", 10)
    for row in kosik:
        if y < 120: c.showPage(); y = height - 40
        c.drawString(40, y, row["ITEM"]); c.drawString(220, y, str(row["Počet kusov"]))
        c.drawString(280, y, f"{round(row['Jednotková cena (€/ks)'],2)} €")
        c.drawString(370, y, f"{round(row['Cena položky spolu (€)'],2)} €"); y -= 14
    y -= 10
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, y, f"Total price without VAT: {round(total_price, 2)} €"); y -= 20
    if note_text:
        c.setFont("Helvetica-Bold", 10); c.drawString(40, y, "NOTE:"); y -= 14
        c.setFont("Helvetica", 10)
        for line in note_text.split("\n"):
            if y < 80: c.showPage(); y = height - 40
            c.drawString(40, y, line); y -= 14
    c.showPage(); c.save(); buffer.seek(0)
    return buffer

def generate_internal_pdf(kosik, cp_nazov, date, zakaznik, krajina, total_price):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)
    y = height - 40
    c.setFont("Helvetica-Bold", 14); c.drawString(40, y, "MECASYS – INTERNAL COSTING"); y -= 20
    c.setFont("Helvetica", 11)
    c.drawString(40, y, f"CP: {cp_nazov}   Date: {date.strftime('%d.%m.%Y')}"); y -= 14
    c.drawString(40, y, f"Customer: {zakaznik}   Country: {krajina}"); y -= 20
    headers = ["ITEM","Qty","Tvar","D/DP","L/S","V","Mat €/bm","Mat/ks","Koop/ks","Vstup/ks","Čas (min)","Cena/ks","Cena spolu"]
    x_pos   = [40,120,160,200,240,280,320,380,440,500,560,620,680]
    c.setFont("Helvetica-Bold", 8)
    for x, h in zip(x_pos, headers): c.drawString(x, y, h)
    y -= 12; c.setFont("Helvetica", 8)
    for row in kosik:
        if y < 60:
            c.showPage(); y = height - 40
            c.setFont("Helvetica-Bold", 8)
            for x, h in zip(x_pos, headers): c.drawString(x, y, h)
            y -= 12; c.setFont("Helvetica", 8)
        cells = [row["ITEM"], str(row["Počet kusov"]), row["Tvar"],
                 str(row["Rozmer D / DP"]), str(row["Rozmer L / S"]), str(row["Rozmer V"]),
                 str(row["J.cena materiálu (€/bm)"]), str(row["Náklad materiál (€/ks)"]),
                 str(row["Náklad kooperácia (€/ks)"]), str(row["Vstupné náklady (€/ks)"]),
                 str(row["Čas (min)"]), str(row["Jednotková cena (€/ks)"]), str(row["Cena položky spolu (€)"])]
        for x, cell in zip(x_pos, cells): c.drawString(x, y, cell)
        y -= 12
    y -= 16; c.setFont("Helvetica-Bold", 10)
    c.drawString(40, y, f"Total offer price: {round(total_price, 2)} €")
    c.showPage(); c.save(); buffer.seek(0)
    return buffer

# ============================================================
# ULOŽIŤ CP + STIAHNUŤ ZIP
# ============================================================
if st.session_state.kosik:
    df_kosik_export = pd.DataFrame(st.session_state.kosik)
    total_price_export = df_kosik_export["Cena položky spolu (€)"].sum()
    pdf_customer = generate_customer_pdf(
        st.session_state.kosik, cp_nazov, date, vybrany,
        krajina_input, st.session_state.note_text, total_price_export)
    pdf_internal = generate_internal_pdf(
        st.session_state.kosik, cp_nazov, date, vybrany,
        krajina_input, total_price_export)
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        zipf.writestr(f"{cp_nazov}_customer.pdf", pdf_customer.getvalue())
        zipf.writestr(f"{cp_nazov}_internal.pdf", pdf_internal.getvalue())
    zip_buffer.seek(0)
    if st.download_button(
        label="💾 Uložiť CP + stiahnuť ZIP",
        data=zip_buffer,
        file_name=f"{cp_nazov}_PDF_balík.zip",
        mime="application/zip"
    ):
        r = requests.post(CP_APP_SCRIPT_URL, json=st.session_state.kosik)
        if r.status_code == 200:
            st.success("CP bola uložená do Google Sheet.")
        else:
            st.error("Chyba pri ukladaní ponuky do Google Sheet.")
