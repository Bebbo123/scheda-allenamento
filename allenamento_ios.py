import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client

# CONFIG
st.set_page_config(page_title="Scheda Allenamento", layout="centered")
st.title("🏋️ Scheda Allenamento")

# SUPABASE
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# SAFE
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

# LOGIN
if "user" not in st.session_state:
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
# CARICA SCHEDA
# -----------------------
res = supabase.table("schede") \
    .select("*") \
    .eq("utente_id", user_id) \
    .eq("attiva", True) \
    .execute()

if not res.data:
    st.warning("Carica una scheda")
    st.stop()

df = pd.DataFrame(res.data[0]["dati"])

# -----------------------
# CARICA WORKOUT SALVATI
# -----------------------
workouts = supabase.table("workouts") \
    .select("*") \
    .eq("utente_id", user_id) \
    .execute().data

df_work = pd.DataFrame(workouts) if workouts else pd.DataFrame()

# -----------------------
# NAVIGAZIONE
# -----------------------
settimana = st.selectbox("Settimana", df["Settimana"].unique())
giorno = st.selectbox("Giorno", df["Giorno"].unique())

filtered = df[
    (df["Settimana"] == settimana) &
    (df["Giorno"] == giorno)
]

# -----------------------
# SESSION STATE
# -----------------------
if "allenamento" not in st.session_state:
    st.session_state.allenamento = {}

allenamento = st.session_state.allenamento

# -----------------------
# UI
# -----------------------
for idx, row in filtered.iterrows():

    key = f"{row['Esercizio']}_{row['Serie']}"

    st.subheader(f"{row['Esercizio']} - Serie {row['Serie']}")

    # valori già salvati
    saved = df_work[
        (df_work["esercizio"] == row["Esercizio"]) &
        (df_work["serie"] == row["Serie"])
    ]

    reps_default = int(saved["reps"].iloc[0]) if not saved.empty else 0
    carico_default = float(saved["carico"].iloc[0]) if not saved.empty else 0
    rpe_default = int(saved["rpe"].iloc[0]) if not saved.empty else 6

    reps = st.number_input("Reps", value=reps_default, key=f"r{idx}")
    carico = st.number_input("Kg", value=carico_default, key=f"c{idx}")
    rpe = st.number_input("RPE", value=rpe_default, key=f"p{idx}")

    done = st.checkbox("✔ Completata", key=f"d{idx}")

    # salva in memoria
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

# -----------------------
# SALVATAGGIO
# -----------------------
if st.button("💾 Salva Allenamento"):

    for k, val in allenamento.items():

        if val["done"]:

            # controlla se esiste già
            existing = supabase.table("workouts") \
                .select("*") \
                .eq("utente_id", user_id) \
                .eq("esercizio", val["esercizio"]) \
                .eq("serie", val["serie"]) \
                .execute()

            if existing.data:
                # UPDATE
                supabase.table("workouts").update({
                    "reps": val["reps"],
                    "carico": val["carico"],
                    "rpe": val["rpe"]
                }).eq("id", existing.data[0]["id"]).execute()

            else:
                # INSERT
                supabase.table("workouts").insert({
                    "utente_id": user_id,
                    "esercizio": val["esercizio"],
                    "serie": val["serie"],
                    "settimana": val["settimana"],
                    "giorno": val["giorno"],
                    "reps": val["reps"],
                    "carico": val["carico"],
                    "rpe": val["rpe"]
                }).execute()

    st.success("Allenamento salvato 🔥")