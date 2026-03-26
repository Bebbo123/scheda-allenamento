import streamlit as st
import pandas as pd
from io import BytesIO
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

scheda_sel = st.sidebar.selectbox("Scheda", schede, format_func=lambda x: x["nome"])
scheda_id = scheda_sel["id"]

# -----------------------
# CARICA DATAFRAME
# -----------------------
df = pd.DataFrame(scheda_sel["dati"])

# -----------------------
# NAVIGAZIONE
# -----------------------
settimana = st.sidebar.selectbox("Settimana", sorted(df["Settimana"].unique()))
giorno = st.sidebar.selectbox("Giorno", sorted(df["Giorno"].unique()))

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
# SESSION
# -----------------------
if "allenamento" not in st.session_state:
    st.session_state.allenamento = {}

allenamento = st.session_state.allenamento

# -----------------------
# UI
# -----------------------
for idx, row in filtered.iterrows():

    st.subheader(f"{row['Esercizio']} - Serie {row['Serie']}")

    # ----------- PT INFO -----------
    st.info(
        f"🎯 Target: {safe_int(row.get('Reps Target'))} reps @ {safe_float(row.get('Carico Target'))} kg"
    )

    if row.get("Note Coach"):
        st.warning(f"🧠 Coach: {row['Note Coach']}")

    # ----------- VALORI SALVATI -----------
    saved = df_work[
        (df_work["esercizio"] == row["Esercizio"]) &
        (df_work["serie"] == row["Serie"])
    ] if not df_work.empty else pd.DataFrame()

    reps_default = safe_int(saved["reps"].iloc[0]) if not saved.empty else 0
    carico_default = safe_float(saved["carico"].iloc[0]) if not saved.empty else 0
    rpe_default = safe_int(saved["rpe"].iloc[0], 6) if not saved.empty else 6
    note_default = saved["note"].iloc[0] if not saved.empty and "note" in saved else ""

    # ----------- INPUT UTENTE -----------
    reps = st.number_input("Reps Effettive", value=reps_default, key=f"r{idx}")
    carico = st.number_input("Carico (kg)", value=carico_default, key=f"c{idx}")
    rpe = st.number_input("RPE", value=rpe_default, key=f"p{idx}")

    note = st.text_input("Note Personali", value=note_default, key=f"n{idx}")

    done = st.checkbox("✔ Completata", key=f"d{idx}")

    allenamento[idx] = {
        "esercizio": row["Esercizio"],
        "serie": safe_int(row["Serie"]),
        "settimana": safe_int(row["Settimana"]),
        "giorno": row["Giorno"],
        "reps": reps,
        "carico": carico,
        "rpe": rpe,
        "note": note,
        "done": done
    }

    st.markdown("---")

# -----------------------
# SALVA
# -----------------------
if st.button("💾 Salva Allenamento"):

    for val in allenamento.values():

        if val["done"]:

            supabase.table("workouts").insert({
                "utente_id": user_id,
                "scheda_id": scheda_id,
                "esercizio": val["esercizio"],
                "serie": val["serie"],
                "settimana": val["settimana"],
                "giorno": val["giorno"],
                "reps": val["reps"],
                "carico": val["carico"],
                "rpe": val["rpe"],
                "note": val["note"]
            }).execute()

    st.success("Allenamento salvato 🔥")

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