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
# SUPABASE (SECRETS)
# -----------------------
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# -----------------------
# LOAD EXCEL
# -----------------------
@st.cache_data
def load_excel(file):
    return pd.read_excel(file)

uploaded_file = st.file_uploader("📂 Carica la tua scheda Excel", type=["xlsx"])

if not uploaded_file:
    st.info("Carica un file Excel per iniziare")
    st.stop()

df = load_excel(uploaded_file)

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
    st.error("⚠️ Il file Excel non è corretto")
    st.stop()

# -----------------------
# STATE
# -----------------------
if "data" not in st.session_state:
    st.session_state.data = df.copy()

if "timer" not in st.session_state:
    st.session_state.timer = {
        "active": False,
        "start": 0,
        "duration": 0,
        "exercise": ""
    }

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
# UI ESERCIZI (MOBILE)
# -----------------------
for esercizio in filtered["Esercizio"].unique():

    blocco = filtered[filtered["Esercizio"] == esercizio]
    recupero = int(blocco["Recupero (sec)"].iloc[0])

    with st.expander(f"🏋️ {esercizio}"):

        note_coach = blocco["Note Coach"].dropna()
        if not note_coach.empty:
            st.info(note_coach.iloc[0])

        st.write(f"⏱ Recupero: {recupero}s")

        if st.button("▶️ Avvia Timer", key=f"timer_{esercizio}"):
            st.session_state.timer = {
                "active": True,
                "start": time.time(),
                "duration": recupero,
                "exercise": esercizio
            }
            st.rerun()

        for idx, row in blocco.iterrows():

            st.markdown(f"### 🔹 Serie {int(row['Serie'])}")
            st.caption(f"🎯 {row['Reps Target']} reps @ {row['Carico Target']} kg")

            reps = st.number_input("Reps", value=int(row["Reps Effettive"] or 0), key=f"r{idx}")
            carico = st.number_input("Kg", value=float(row["Carico"] or 0), key=f"c{idx}")
            rpe = st.number_input("RPE", min_value=1, max_value=10, value=int(row["RPE"] or 6), key=f"p{idx}")

            done = st.checkbox("✔ Serie completata", key=f"d{idx}")

            # SALVATAGGIO LOCALE
            data.loc[idx, "Reps Effettive"] = reps
            data.loc[idx, "Carico"] = carico
            data.loc[idx, "RPE"] = rpe
            data.loc[idx, "Stato"] = "Completata" if done else ""

            # SALVATAGGIO CLOUD
            if done:
                supabase.table("workouts").insert({
                    "esercizio": esercizio,
                    "settimana": int(row["Settimana"]),
                    "giorno": row["Giorno"],
                    "serie": int(row["Serie"]),
                    "carico": float(carico),
                    "reps": int(reps),
                    "rpe": int(rpe),
                    "carico_target": float(row["Carico Target"])
                }).execute()

                st.success("☁️ Salvato nel cloud")

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

st.download_button("⬇️ Esporta Scheda", buffer, nome_file)

# -----------------------
# DASHBOARD PRO
# -----------------------
st.subheader("📊 Dashboard Progressi")

data_db = supabase.table("workouts").select("*").execute().data

if data_db:

    df_db = pd.DataFrame(data_db)

    esercizio_sel = st.selectbox("Seleziona esercizio", df_db["esercizio"].unique())

    if st.button("📈 Mostra Dashboard"):

        df_es = df_db[df_db["esercizio"] == esercizio_sel].sort_values("settimana")

        st.markdown("## 📊 Analisi")

        # CARICO
        st.markdown("### 🏋️ Carico medio")
        st.line_chart(df_es.groupby("settimana")["carico"].mean())

        # REPS
        st.markdown("### 🔢 Reps medie")
        st.line_chart(df_es.groupby("settimana")["reps"].mean())

        # RPE
        st.markdown("### 🔥 RPE medio")
        st.line_chart(df_es.groupby("settimana")["rpe"].mean())

        # SERIE
        st.markdown("### 📊 Carico per serie")
        st.line_chart(df_es.groupby(["settimana", "serie"])["carico"].mean().unstack())

        # TARGET VS REALE
        if "carico_target" in df_es.columns:

            st.markdown("### 🎯 Target vs Reale")

            confronto = df_es.groupby("settimana")[["carico", "carico_target"]].mean()

            st.line_chart(confronto)

            last = confronto.iloc[-1]

            if last["carico"] >= last["carico_target"]:
                st.success("🔥 Sopra target!")
            else:
                st.warning("📈 Sotto target")

        # BEST SET
        st.markdown("### 🏆 Best Set")
        best = df_es.sort_values("carico", ascending=False).iloc[0]

        st.success(
            f"{best['carico']} kg x {best['reps']} reps (RPE {best['rpe']})"
        )

else:
    st.info("Nessun dato salvato")