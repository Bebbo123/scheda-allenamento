import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
from supabase import create_client
import json

# -----------------------
# CONFIG APP
# -----------------------
st.set_page_config(page_title="Scheda Allenamento", page_icon="🏋️", layout="centered")

# 🔥 MOBILE + LOCAL STORAGE
st.markdown("""
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script>
function saveUser(user){
    localStorage.setItem("user", JSON.stringify(user));
}
function loadUser(){
    return localStorage.getItem("user");
}
function clearUser(){
    localStorage.removeItem("user");
}
</script>
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

def safe_float(val, default=0.0):
    try:
        if pd.isna(val) or val == "":
            return default
        return float(val)
    except:
        return default

# -----------------------
# LOGIN AUTO
# -----------------------
if "user" not in st.session_state:

    # prova recupero da localStorage
    user_js = st.components.v1.html("""
        <script>
        const user = localStorage.getItem("user");
        if(user){
            window.parent.postMessage({type: "USER", value: user}, "*");
        }
        </script>
    """, height=0)

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

            # 🔥 salva in localStorage
            st.components.v1.html(f"""
            <script>
            localStorage.setItem("user", JSON.stringify({json.dumps(user.session)}));
            </script>
            """, height=0)

            st.success("Login OK")
            st.rerun()

        except Exception as e:
            st.error(f"Errore login: {e}")

    st.stop()

# -----------------------
# UTENTE LOGGATO
# -----------------------
user = st.session_state.user
user_id = user.user.id

st.success("👤 Loggato")

# -----------------------
# LOGOUT
# -----------------------
if st.sidebar.button("🚪 Logout"):

    st.session_state.clear()

    st.components.v1.html("""
    <script>
    localStorage.removeItem("user");
    </script>
    """, height=0)

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
# UI
# -----------------------
for idx, row in filtered.iterrows():

    st.markdown(f"## 🏋️ {row['Esercizio']}")

    st.markdown(
        f"🎯 {safe_int(row['Reps Target'])} reps @ {safe_float(row['Carico Target'])} kg"
    )

    if row["Note Coach"]:
        st.info(row["Note Coach"])

    reps = st.number_input("Reps", key=f"r{idx}")
    carico = st.number_input("Kg", key=f"c{idx}")
    rpe = st.number_input("RPE", value=6, key=f"p{idx}")

    if st.button("✔ Salva", key=f"s{idx}"):

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