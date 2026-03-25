import streamlit as st
import pandas as pd
import time
from io import BytesIO
from datetime import datetime

# -----------------------
# CONFIG
# -----------------------
st.set_page_config(
    page_title="Scheda Allenamento",
    page_icon="🏋️",
    layout="centered"
)

st.title("🏋️ Scheda Allenamento")

# -----------------------
# LOAD FILE
# -----------------------
@st.cache_data
def load_excel(file):
    return pd.read_excel(file)

uploaded_file = st.file_uploader("📂 Carica la tua scheda Excel", type=["xlsx"])

if not uploaded_file:
    st.info("Carica un file Excel per iniziare")
    st.stop()

try:
    df = load_excel(uploaded_file)
except Exception as e:
    st.error(f"Errore lettura file: {e}")
    st.stop()

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
    st.error("⚠️ Il file Excel non ha le colonne corrette")
    st.write(required_columns)
    st.stop()

# -----------------------
# SESSION STATE
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

settimana = st.sidebar.selectbox(
    "Settimana",
    sorted(data["Settimana"].dropna().unique())
)

giorno = st.sidebar.selectbox(
    "Giorno",
    sorted(data[data["Settimana"] == settimana]["Giorno"].dropna().unique())
)

filtered = data[
    (data["Settimana"] == settimana) &
    (data["Giorno"] == giorno)
]

if filtered.empty:
    st.warning("Nessun dato trovato")
    st.stop()

# -----------------------
# TIMER GLOBALE
# -----------------------
if timer["active"]:
    elapsed = time.time() - timer["start"]
    remaining = int(timer["duration"] - elapsed)

    if remaining > 0:
        st.warning(f"⏳ Recupero {timer['exercise']}: {remaining} sec")
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
    recupero = int(blocco["Recupero (sec)"].iloc[0])

    with st.expander(f"🏋️ {esercizio}", expanded=True):

        # NOTE COACH
        note_coach = blocco["Note Coach"].dropna()
        if not note_coach.empty:
            st.info(note_coach.iloc[0])

        st.write(f"⏱ Recupero: {recupero} sec")

        # TIMER
        if st.button("▶️ Avvia Timer", key=f"timer_{esercizio}"):
            st.session_state.timer = {
                "active": True,
                "start": time.time(),
                "duration": recupero,
                "exercise": esercizio
            }
            st.rerun()

        st.divider()

        # SERIE
        for idx, row in blocco.iterrows():

            st.markdown(f"### Serie {int(row['Serie'])}")

            st.write(
                f"🎯 Target: {int(row['Reps Target'])} reps @ {row['Carico Target']} kg"
            )

            col1, col2, col3 = st.columns(3)

            with col1:
                reps = st.number_input(
                    "Reps",
                    value=int(row["Reps Effettive"]) if pd.notna(row["Reps Effettive"]) else 0,
                    key=f"reps_{idx}"
                )

            with col2:
                carico = st.number_input(
                    "Carico Effettivo",
                    value=float(row["Carico"]) if pd.notna(row["Carico"]) else 0.0,
                    step=2.5,
                    key=f"carico_{idx}"
                )

            with col3:
                rpe = st.number_input(
                    "RPE",
                    min_value=1,
                    max_value=10,
                    value=int(row["RPE"]) if pd.notna(row["RPE"]) else 6,
                    key=f"rpe_{idx}"
                )

            note = st.text_input(
                "Note",
                value=str(row["Note Personali"]) if pd.notna(row["Note Personali"]) else "",
                key=f"note_{idx}"
            )

            done = st.checkbox(
                "Completata",
                value=row["Stato"] == "Completata",
                key=f"done_{idx}"
            )

            # SALVATAGGIO
            data.loc[idx, "Reps Effettive"] = reps
            data.loc[idx, "Carico"] = carico
            data.loc[idx, "RPE"] = rpe
            data.loc[idx, "Note Personali"] = note
            data.loc[idx, "Stato"] = "Completata" if done else ""

            if done:
                st.success("✔ Serie completata")

            st.divider()

# -----------------------
# EXPORT
# -----------------------
st.subheader("📥 Esporta")

oggi = datetime.now().strftime("%d-%m-%Y")
nome_file = f"Scheda al {oggi}.xlsx"

buffer = BytesIO()
data.to_excel(buffer, index=False)
buffer.seek(0)

st.download_button(
    label="⬇️ Esporta Scheda",
    data=buffer,
    file_name=nome_file,
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
 