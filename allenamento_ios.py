import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
from supabase import create_client

# -----------------------
# CONFIG MOBILE
# -----------------------
st.set_page_config(page_title="Scheda Allenamento", page_icon="🏋️", layout="centered")

st.markdown("""
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
div.stButton > button {
    width: 100%;
    height: 50px;
    font-size: 18px;
    border-radius: 10px;
}
input {
    font-size: 18px !important;
}
.block-container {
    padding: 1rem;
}
</style>
""", unsafe_allow_html=True)

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

def clean_float(val):
    try:
        return float(str(val).replace(",", "."))
    except:
        return 0.0

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
        try:
            user = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            st.session_state.user = user
            st.rerun()
        except Exception as e:
            st.error(f"Errore login: {e}")

    st.stop()

user = st.session_state.user
user_id = user.user.id

# LOGOUT
if st.sidebar.button("🚪 Logout"):
    st.session_state.clear()
    st.rerun()

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
# NAVIGAZIONE
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
# UI ESERCIZI
# -----------------------
for idx, row in filtered.iterrows():

    st.markdown(f"## 🏋️ {row['Esercizio']} - Serie {row['Serie']}")

    # PT INFO
    st.markdown(
        f"🎯 {safe_int(row['Reps Target'])} reps @ {clean_float(row['Carico Target'])} kg"
    )

    if safe_str(row.get("Note Coach")):
        st.info(f"🧠 {row['Note Coach']}")

    st.caption(f"⏱ Recupero: {safe_int(row['Recupero (sec)'])} sec")

    # VALORI SALVATI
    saved = df_work[
        (df_work["esercizio"] == row["Esercizio"]) &
        (df_work["serie"] == row["Serie"])
    ] if not df_work.empty else pd.DataFrame()

    reps_default = int(safe_int(saved["reps"].iloc[0])) if not saved.empty else 0
    carico_default = float(clean_float(saved["carico"].iloc[0])) if not saved.empty else 0.0
    rpe_default = int(safe_int(saved["rpe"].iloc[0], 6)) if not saved.empty else 6
    note_default = saved["note"].iloc[0] if not saved.empty and "note" in saved else ""

    # INPUT (TIPI COERENTI)
    reps = st.number_input("Reps", value=int(reps_default), step=1, key=f"r{idx}")

    carico = st.number_input(
        "Kg",
        value=float(carico_default),
        step=float(0.5),
        format="%.2f",
        key=f"c{idx}"
    )

    rpe = st.number_input(
        "RPE",
        value=int(rpe_default),
        min_value=1,
        max_value=10,
        step=1,
        key=f"p{idx}"
    )

    note = st.text_input("Note Personali", value=note_default, key=f"n{idx}")

    # SALVA
    if st.button("✔ Salva Serie", key=f"s{idx}"):

        try:
            supabase.table("workouts").insert({
                "utente_id": user_id,
                "scheda_id": scheda_id,
                "esercizio": row["Esercizio"],
                "serie": int(safe_int(row["Serie"])),
                "settimana": int(safe_int(row["Settimana"])),
                "giorno": row["Giorno"],
                "reps": int(reps),
                "carico": float(clean_float(carico)),
                "rpe": int(rpe),
                "note": note
            }).execute()

            st.success("Salvato 💪")

        except Exception as e:
            st.error(f"Errore DB: {e}")

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