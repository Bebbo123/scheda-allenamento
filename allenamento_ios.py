import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
from supabase import create_client

# -----------------------
# CONFIG
# -----------------------
st.set_page_config(page_title="Scheda Allenamento", page_icon="🏋️", layout="centered")
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
        if val in ["", None]:
            return default
        return int(float(val))
    except:
        return default

def safe_float(val, default=0.0):
    try:
        if val in ["", None]:
            return default
        return float(val)
    except:
        return default

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
            "dati": clean_df.to_dict(orient="records"),  # 🔥 FIX IMPORTANTE
            "utente_id": user_id
        }).execute()

        st.success("Scheda salvata!")
        st.rerun()

# -----------------------
# SCHEDE LISTA
# -----------------------
schede = supabase.table("schede") \
    .select("*") \
    .eq("utente_id", user_id) \
    .execute().data

if not schede:
    st.warning("Carica una scheda")
    st.stop()

# -----------------------
# SIDEBAR
# -----------------------
st.sidebar.header("📋 Gestione Schede")

scheda_sel = st.sidebar.selectbox(
    "Seleziona scheda",
    schede,
    format_func=lambda x: x["nome"]
)

scheda_id = scheda_sel["id"]

# -----------------------
# ELIMINA SCHEDA
# -----------------------
if st.sidebar.button("🗑️ Elimina scheda"):

    supabase.table("workouts") \
        .delete() \
        .eq("scheda_id", scheda_id) \
        .execute()

    supabase.table("schede") \
        .delete() \
        .eq("id", scheda_id) \
        .execute()

    st.sidebar.success("Scheda eliminata")
    st.rerun()

# -----------------------
# CARICA SCHEDA (FIX)
# -----------------------
df = pd.DataFrame(scheda_sel["dati"])  # 🔥 FIX DEFINITIVO

# -----------------------
# VALIDAZIONE COLONNE
# -----------------------
required_columns = [
    "Giorno", "Settimana", "Esercizio",
    "Serie", "Reps Target", "Carico Target"
]

missing = [c for c in required_columns if c not in df.columns]

if missing:
    st.error(f"⚠️ Excel non valido. Mancano colonne: {missing}")
    st.stop()

# -----------------------
# NAVIGAZIONE
# -----------------------
st.sidebar.header("Navigazione")

settimana = st.sidebar.selectbox(
    "Settimana",
    sorted(df["Settimana"].dropna().unique())
)

giorno = st.sidebar.selectbox(
    "Giorno",
    sorted(df[df["Settimana"] == settimana]["Giorno"].dropna().unique())
)

filtered = df[
    (df["Settimana"] == settimana) &
    (df["Giorno"] == giorno)
]

# -----------------------
# WORKOUT CARICATI
# -----------------------
workouts = supabase.table("workouts") \
    .select("*") \
    .eq("utente_id", user_id) \
    .eq("scheda_id", scheda_id) \
    .execute().data

df_work = pd.DataFrame(workouts) if workouts else pd.DataFrame()

# -----------------------
# SESSION
# -----------------------
if "allenamento" not in st.session_state:
    st.session_state.allenamento = {}

allenamento = st.session_state.allenamento

# -----------------------
# UI ESERCIZI
# -----------------------
for idx, row in filtered.iterrows():

    key = f"{row['Esercizio']}_{row['Serie']}"

    st.subheader(f"{row['Esercizio']} - Serie {row['Serie']}")

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

    allenamento[key] = {
        "esercizio": row["Esercizio"],
        "serie": safe_int(row["Serie"]),
        "settimana": safe_int(row["Settimana"]),
        "giorno": row["Giorno"],
        "reps": reps,
        "carico": carico,
        "rpe": rpe,
        "done": done
    }

    st.markdown("---")

# -----------------------
# SALVA ALLENAMENTO
# -----------------------
if st.button("💾 Salva Allenamento"):

    for val in allenamento.values():

        if val["done"]:

            existing = supabase.table("workouts") \
                .select("*") \
                .eq("utente_id", user_id) \
                .eq("scheda_id", scheda_id) \
                .eq("esercizio", val["esercizio"]) \
                .eq("serie", val["serie"]) \
                .execute()

            if existing.data:
                supabase.table("workouts").update({
                    "reps": val["reps"],
                    "carico": val["carico"],
                    "rpe": val["rpe"]
                }).eq("id", existing.data[0]["id"]).execute()
            else:
                supabase.table("workouts").insert({
                    "utente_id": user_id,
                    "scheda_id": scheda_id,
                    "esercizio": val["esercizio"],
                    "serie": val["serie"],
                    "settimana": val["settimana"],
                    "giorno": val["giorno"],
                    "reps": val["reps"],
                    "carico": val["carico"],
                    "rpe": val["rpe"]
                }).execute()

    st.success("Allenamento salvato 🔥")

# -----------------------
# EXPORT EXCEL
# -----------------------
st.subheader("📥 Esporta Scheda")

buffer = BytesIO()
df.to_excel(buffer, index=False)
buffer.seek(0)

st.download_button(
    "⬇️ Scarica Excel",
    buffer,
    f"Scheda_{datetime.now().strftime('%d-%m-%Y')}.xlsx"
)