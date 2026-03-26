import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
from supabase import create_client

# -----------------------
# CONFIG MOBILE APP STYLE
# -----------------------
st.set_page_config(page_title="Scheda Allenamento", page_icon="🏋️", layout="centered")

# 🔥 MIGLIORIA MOBILE
st.markdown(
    """
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
    /* bottoni più grandi */
    div.stButton > button {
        width: 100%;
        height: 50px;
        font-size: 18px;
        border-radius: 10px;
    }

    /* input più grandi */
    input {
        font-size: 18px !important;
    }

    /* checkbox più grandi */
    div[data-baseweb="checkbox"] {
        transform: scale(1.3);
    }

    /* padding mobile */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("🏋️ Scheda Allenamento")

# -----------------------
# SUPABASE
# -----------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# -----------------------
# SAFE FUNCTIONS
# -----------------------
def safe_int(val, default=0):
    try:
        if pd.isna(val) or val == "":
            return default
        return int(float(val))
    except:
        return default

def safe_float(val, default=0.0):
    try:
        if pd.isna(val) or val == "":
            return default
        return float(val)
    except:
        return default

def safe_str(val):
    if pd.isna(val):
        return ""
    return str(val)

# -----------------------
# LOGIN
# -----------------------
if "user" not in st.session_state:
    st.subheader("🔐 Login")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        user = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        st.session_state.user = user
        st.rerun()

    st.stop()

user_id = st.session_state.user.user.id

# -----------------------
# UPLOAD SCHEDA
# -----------------------
st.subheader("📂 Carica Scheda")

uploaded_file = st.file_uploader("Carica Excel", type=["xlsx"])

if uploaded_file:
    df_new = pd.read_excel(uploaded_file)

    if st.button("💾 Salva Scheda"):
        clean_df = df_new.fillna("")

        supabase.table("schede").insert({
            "nome": uploaded_file.name,
            "dati": clean_df.to_dict(orient="records"),
            "utente_id": user_id
        }).execute()

        st.success("Scheda salvata!")
        st.rerun()

# -----------------------
# SCHEDE
# -----------------------
schede = supabase.table("schede") \
    .select("*") \
    .eq("utente_id", user_id) \
    .execute().data

if not schede:
    st.warning("Carica una scheda")
    st.stop()

scheda_sel = st.selectbox("📋 Scheda", schede, format_func=lambda x: x["nome"])
scheda_id = scheda_sel["id"]

df = pd.DataFrame(scheda_sel["dati"])

# -----------------------
# NAVIGAZIONE MOBILE
# -----------------------
col1, col2 = st.columns(2)

with col1:
    settimana = st.selectbox("Settimana", sorted(df["Settimana"].unique()))

with col2:
    giorno = st.selectbox("Giorno", sorted(df["Giorno"].unique()))

filtered = df[
    (df["Settimana"] == settimana) &
    (df["Giorno"] == giorno)
]

# -----------------------
# WORKOUT SALVATI
# -----------------------
workouts = supabase.table("workouts") \
    .select("*") \
    .eq("utente_id", user_id) \
    .eq("scheda_id", scheda_id) \
    .execute().data

df_work = pd.DataFrame(workouts) if workouts else pd.DataFrame()

# -----------------------
# UI ESERCIZI MOBILE
# -----------------------
for idx, row in filtered.iterrows():

    st.markdown(f"## 🏋️ {row['Esercizio']}")

    st.markdown(
        f"🎯 {safe_int(row['Reps Target'])} reps @ {safe_float(row['Carico Target'])} kg"
    )

    if safe_str(row["Note Coach"]):
        st.info(f"🧠 {row['Note Coach']}")

    st.caption(f"⏱ Recupero: {safe_int(row['Recupero (sec)'])} sec")

    saved = df_work[
        (df_work["esercizio"] == row["Esercizio"]) &
        (df_work["serie"] == row["Serie"])
    ] if not df_work.empty else pd.DataFrame()

    reps_default = safe_int(saved["reps"].iloc[0]) if not saved.empty else 0
    carico_default = safe_float(saved["carico"].iloc[0]) if not saved.empty else 0
    rpe_default = safe_int(saved["rpe"].iloc[0], 6) if not saved.empty else 6

    reps = st.number_input("Reps", value=reps_default, key=f"r{idx}")
    carico = st.number_input("Kg", value=carico_default, key=f"c{idx}")
    rpe = st.number_input("RPE", value=rpe_default, key=f"p{idx}")

    done = st.checkbox("✔ Completata", key=f"d{idx}")

    if done:
        supabase.table("workouts").insert({
            "utente_id": user_id,
            "scheda_id": scheda_id,
            "esercizio": row["Esercizio"],
            "serie": safe_int(row["Serie"]),
            "settimana": safe_int(row["Settimana"]),
            "giorno": row["Giorno"],
            "reps": reps,
            "carico": carico,
            "rpe": rpe
        }).execute()

        st.success("Salvato 💪")

    st.divider()

# -----------------------
# EXPORT
# -----------------------
buffer = BytesIO()
df.to_excel(buffer, index=False)
buffer.seek(0)

st.download_button(
    "⬇️ Scarica Excel",
    buffer,
    f"Scheda_{datetime.now().strftime('%d-%m-%Y')}.xlsx"
)