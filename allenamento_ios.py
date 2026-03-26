import streamlit as st
import pandas as pd
import time
from io import BytesIO
from datetime import datetime
from supabase import create_client

# CONFIG
st.set_page_config(page_title="Scheda Allenamento", page_icon="🏋️", layout="centered")
st.title("🏋️ Scheda Allenamento")

# SUPABASE
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# SAFE FUNCTIONS
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
st.subheader("🔐 Login")

if "user" not in st.session_state:
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

# CARICA SCHEDA
res = supabase.table("schede") \
    .select("*") \
    .eq("utente_id", user_id) \
    .eq("attiva", True) \
    .execute()

if not res.data:
    st.warning("⚠️ Nessuna scheda trovata")
    st.stop()

df = pd.DataFrame(res.data[0]["dati"])
st.session_state.data = df.copy()

data = st.session_state.data

# NAVIGAZIONE
settimana = st.sidebar.selectbox("Settimana", sorted(data["Settimana"].dropna().unique()))
giorno = st.sidebar.selectbox(
    "Giorno",
    sorted(data[data["Settimana"] == settimana]["Giorno"].dropna().unique())
)

filtered = data[
    (data["Settimana"] == settimana) &
    (data["Giorno"] == giorno)
]

# UI
for esercizio in filtered["Esercizio"].unique():

    blocco = filtered[filtered["Esercizio"] == esercizio]

    with st.expander(f"🏋️ {esercizio}"):

        for idx, row in blocco.iterrows():

            st.markdown(f"### Serie {safe_int(row['Serie'])}")

            reps = st.number_input("Reps", value=safe_int(row["Reps Effettive"]), key=f"r{idx}")
            carico = st.number_input("Kg", value=safe_float(row["Carico"]), key=f"c{idx}")
            rpe = st.number_input("RPE", min_value=1, max_value=10, value=safe_int(row["RPE"], 6), key=f"p{idx}")

            done = st.checkbox("✔ Completata", key=f"d{idx}")

            if done:

                try:
                    supabase.table("workouts").insert({
                        "utente_id": user_id,
                        "esercizio": esercizio,
                        "settimana": safe_int(row["Settimana"]),
                        "giorno": row["Giorno"],
                        "serie": safe_int(row["Serie"]),
                        "carico": float(carico),
                        "reps": int(reps),
                        "rpe": int(rpe),
                        "carico_target": safe_float(row["Carico Target"])
                    }).execute()

                    st.success("☁️ Salvato!")

                except Exception as e:
                    st.error(f"Errore salvataggio: {e}")

            st.markdown("---")

# EXPORT
buffer = BytesIO()
data.to_excel(buffer, index=False)
buffer.seek(0)

st.download_button("⬇️ Esporta", buffer, f"Scheda_{datetime.now().strftime('%d-%m-%Y')}.xlsx")