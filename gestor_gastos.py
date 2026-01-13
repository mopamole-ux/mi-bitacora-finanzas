import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import time

# 1. CONFIGURACIÓN INICIAL
st.set_page_config(page_title="Bitácora de Gorditos 🍔", layout="wide")

URL_BANNER = "https://lh3.googleusercontent.com/d/11Rdr2cVYIypLjmSp9jssuvoOxQ-kI1IZ"
st.image(URL_BANNER, width='stretch')
st.title("🍕 Bitácora de Gorditos 🍔")

# --- 2. CONEXIÓN ---
conn = st.connection("gsheets", type=GSheetsConnection)

COLUMNAS_MAESTRAS = [
    "Fecha", "Concepto", "Monto", "Tipo", 
    "Categoria", "Tipo_Pago", "Metodo_Pago", "Responsable"
]

# --- 3. LECTURA DE DATOS ---
try:
    # Leer Configuración (TTL 5 min para evitar error 429)
    df_config = conn.read(worksheet="Config", ttl=300)
    saldo_base_valor = float(df_config.iloc[0, 0]) if not df_config.empty else 20000.0
    limite_atracón = float(df_config.iloc[0, 1]) if len(df_config.columns) > 1 else 15000.0

    df_raw = conn.read(ttl=300)
    
    if df_raw is not None and not df_raw.empty:
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        for col in COLUMNAS_MAESTRAS:
            if col not in df_raw.columns: df_raw[col] = ""
        
        # ELIMINAMOS EL ÍNDICE para que Streamlit no pida un número al crear filas
        df_man = df_raw[COLUMNAS_MAESTRAS].copy().reset_index(drop=True)
        df_man['Fecha'] = pd.to_datetime(df_man['Fecha'], errors='coerce')
        df_man['Monto'] = pd.to_numeric(df_man['Monto'], errors='coerce').fillna(0.0)
    else:
        df_man = pd.DataFrame(columns=COLUMNAS_MAESTRAS)

except Exception as e:
    if "429" in str(e):
        st.error("🚦 ¡Google saturado! Espera 60 segundos.")
        st.stop()
    else:
        st.error(f"Error: {e}")
        st.stop()

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuración")
    n_saldo = st.number_input("💰 Saldo Base", value=int(saldo_base_valor), step=100)
    n_limite = st.number_input("⚠️ Límite Gasto", value=int(limite_atracón), step=500)
    
    if st.button("🍳 Guardar Config"):
        conn.update(worksheet="Config", data=pd.DataFrame({"SaldoBase": [n_saldo], "Limite": [n_limite]}))
        st.cache_data.clear()
        st.rerun()

# --- 5. REGISTRO ---
tab_reg, tab_ana = st.tabs(["📝 Registro", "📊 Análisis"])

with tab_reg:
    st.markdown("### 🛒 Añade tus gastos")
    
    # Aquí está el cambio: reset_index(drop=True) y una nueva KEY
    # Al no tener un índice con nombre, Streamlit asigna uno interno invisible
    df_editado = st.data_editor(
        df_man,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "Fecha": st.column_config.DateColumn("📅 Fecha", format="DD/MM/YYYY"),
            "Monto": st.column_config.NumberColumn("💵 Monto", format="$%d"),
            "Tipo": st.column_config.SelectboxColumn("✨ Tipo", options=["Gasto", "Abono"]),
            "Responsable": st.column_config.SelectboxColumn("👤 Responsable", options=["Gordify", "Mon"]),
            "Categoria": st.column_config.SelectboxColumn("📂 Categoría", options=["Super", "Software", "Suscripciones", "Restaurantes", "Servicios", "Salud", "Préstamos", "Viajes", "Otros"]),
        },
        key="editor_sin_id_manual_v1"
    )

    # Totales rápidos (calculados sobre lo que ves en pantalla)
    g_act = df_editado[df_editado['Tipo'] == 'Gasto']['Monto'].sum()
    a_act = df_editado[df_editado['Tipo'] == 'Abono']['Monto'].sum()
    st.metric("💰 NETO PROYECTADO", f"${int(n_saldo + a_act - g_act):,}")

    if st.button("💾 GUARDAR TODO"):
        # Limpiamos filas vacías (solo guardamos si tienen fecha o concepto)
        df_save = df_editado.dropna(subset=['Fecha', 'Concepto'], how='all').copy()
        
        if not df_save.empty:
            # Formateamos para Google Sheets
            df_save['Fecha'] = pd.to_datetime(df_save['Fecha']).dt.strftime('%Y-%m-%d')
            df_final = df_save[COLUMNAS_MAESTRAS]
            
            try:
                conn.update(data=df_final)
                st.cache_data.clear()
                st.success("✅ ¡Guardado con éxito!")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

with tab_ana:
    # Gráfica de quién gasta más
    if not df_man.empty:
        gastos = df_man[df_man['Tipo'] == 'Gasto'].groupby('Responsable')['Monto'].sum().reset_index()
        fig = px.pie(gastos, values='Monto', names='Responsable', title="Reparto de Gastos")
        st.plotly_chart(fig, width='stretch')
