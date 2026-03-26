import streamlit as st
import pandas as pd
import time
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
    return int(val) if pd.notna(val) else default

def safe_float(val, default=0.0):
    return float(val) if pd.notna(val) else default

# -----------------------
# GESTIONE SCHEDE
# -----------------------
st.subheader("📂 Gestione Schede")

uploaded_file = st.file_uploader("Carica nuova scheda Excel", type=["xlsx"])

if uploaded_file:
    df_new = pd.read_excel(uploaded_file)

    if st.button("Salva nuova scheda"):
        # disattiva tutte
        supabase.table("schede").update({"attiva": False}).neq("id", "").execute()

        # salva nuova
        supabase.table("schede").insert({
            "nome": uploaded_file.name,
            "dati": df_new.to_dict(),
            "attiva": True
        }).execute()

        st.success("✅ Scheda salvata e attiva")
        st.rerun()

# -----------------------
# SWITCH SCHEDE
# -----------------------
schede = supabase.table("schede").select("id,nome").execute().data

if schede:
    scheda_sel = st.sidebar.selectbox(
        "Scheda attiva",
        schede,
        format_func=lambda x: x["nome"]
    )

    if st.sidebar.button("Attiva scheda"):
        supabase.table("schede").update({"attiva": False}).neq("id", "").execute()
        supabase.table("schede").update({"attiva": True}).eq("id", scheda_sel["id"]).execute()
        st.rerun()

# -----------------------
# CARICA SCHEDA ATTIVA
# -----------------------
res = supabase.table("schede").select("*").eq("attiva", True).limit(1).execute()

if not res.data:
    st.warning("Carica una scheda per iniziare")
    st.stop()

df = pd.DataFrame(res.data[0]["dati"])

# -----------------------
# VALIDAZIONE
# -----------------------
required_columns = [
    "Giorno", "Settimana", "Esercizio", "Note Coach",
    "Recupero (sec)",
    "Serie", "Reps Target", "Carico Target",
    "Reps Effettive", "Carico",
    "RPE", "Note Personali", "Stato"
]

if not all(col in df.columns for col in required_columns):
    st.error("⚠️ Excel non valido")
    st.stop()

# -----------------------
# STATE
# -----------------------
if "data" not in st.session_state:
    st.session_state.data = df.copy()

if "timer" not in st.session_state:
    st.session_state.timer = {"active": False, "start": 0, "duration": 0, "exercise": ""}

data = st.session_state.data
timer = st.session_state.timer

# -----------------------
# NAVIGAZIONE
# -----------------------
st.sidebar.header("Navigazione")

settimana = st.sidebar.selectbox("Settimana", sorted(data["Settimana"].dropna().unique()))
giorno = st.sidebar.selectbox(
    "Giorno",
    sorted(data[data["Settimana"] == settimana]["Giorno"].dropna().unique())
)

filtered = data[
    (data["Settimana"] == settimana) &
    (data["Giorno"] == giorno)
]

# -----------------------
# TIMER
# -----------------------
if timer["active"]:
    elapsed = time.time() - timer["start"]
    remaining = int(timer["duration"] - elapsed)

    if remaining > 0:
        st.warning(f"⏳ {timer['exercise']} - {remaining}s")
        st.progress(elapsed / timer["duration"])
        time.sleep(1)
        st.rerun()
    else:
        st.success("✅ Recupero finito!")
        timer["active"] = False

# -----------------------
# UI ESERCIZI
# -----------------------
for esercizio in filtered["Esercizio"].unique():

    blocco = filtered[filtered["Esercizio"] == esercizio]
    recupero = safe_int(blocco["Recupero (sec)"].iloc[0])

    with st.expander(f"🏋️ {esercizio}"):

        note_coach = blocco["Note Coach"].dropna()
        if not note_coach.empty:
            st.info(note_coach.iloc[0])

        st.write(f"⏱ Recupero: {recupero}s")

        if st.button("▶️ Timer", key=f"timer_{esercizio}"):
            st.session_state.timer = {
                "active": True,
                "start": time.time(),
                "duration": recupero,
                "exercise": esercizio
            }
            st.rerun()

        for idx, row in blocco.iterrows():

            st.markdown(f"### 🔹 Serie {safe_int(row['Serie'])}")
            st.caption(f"🎯 {safe_int(row['Reps Target'])} reps @ {safe_float(row['Carico Target'])} kg")

            reps = st.number_input("Reps", value=safe_int(row["Reps Effettive"]), key=f"r{idx}")
            carico = st.number_input("Kg", value=safe_float(row["Carico"]), key=f"c{idx}")
            rpe = st.number_input("RPE", min_value=1, max_value=10, value=safe_int(row["RPE"], 6), key=f"p{idx}")

            done = st.checkbox("✔ Completata", key=f"d{idx}")

            # salva locale
            data.loc[idx, "Reps Effettive"] = reps
            data.loc[idx, "Carico"] = carico
            data.loc[idx, "RPE"] = rpe
            data.loc[idx, "Stato"] = "Completata" if done else ""

            # salva cloud
            if done:
                supabase.table("workouts").insert({
                    "esercizio": esercizio,
                    "settimana": safe_int(row["Settimana"]),
                    "giorno": row["Giorno"],
                    "serie": safe_int(row["Serie"]),
                    "carico": float(carico),
                    "reps": int(reps),
                    "rpe": int(rpe),
                    "carico_target": safe_float(row["Carico Target"])
                }).execute()

                st.success("☁️ Salvato")

            st.markdown("---")

# -----------------------
# EXPORT
# -----------------------
st.subheader("📥 Esporta")

oggi = datetime.now().strftime("%d-%m-%Y")
nome_file = f"Scheda al {oggi}.xlsx"

buffer = BytesIO()
data.to_excel(buffer, index=False)
buffer.seek(0)

st.download_button("⬇️ Esporta", buffer, nome_file)

# -----------------------
# DASHBOARD
# -----------------------
st.subheader("📊 Dashboard")

data_db = supabase.table("workouts").select("*").execute().data

if data_db:

    df_db = pd.DataFrame(data_db)

    esercizio_sel = st.selectbox("Esercizio", df_db["esercizio"].unique())

    if st.button("📈 Mostra"):

        df_es = df_db[df_db["esercizio"] == esercizio_sel]

        st.line_chart(df_es.groupby("settimana")["carico"].mean())
        st.line_chart(df_es.groupby("settimana")["reps"].mean())
        st.line_chart(df_es.groupby("settimana")["rpe"].mean())

        if "carico_target" in df_es.columns:
            confronto = df_es.groupby("settimana")[["carico", "carico_target"]].mean()
            st.line_chart(confronto)

else:
    st.info("Nessun dato")