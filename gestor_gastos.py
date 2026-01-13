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

# --- 3. LECTURA DE DATOS CON CACHÉ (Para evitar el error 429) ---
try:
    # Usamos ttl=300 (5 minutos). La app solo leerá de Google cada 5 min 
    # a menos que nosotros forcemos la limpieza.
    df_config = conn.read(worksheet="Config", ttl=300)
    if not df_config.empty:
        saldo_base_valor = float(df_config.iloc[0, 0])
        limite_atracon = float(df_config.iloc[0, 1]) if len(df_config.columns) > 1 else 15000.0
    else:
        saldo_base_valor, limite_atracon = 20000.0, 15000.0

    df_raw = conn.read(ttl=300)
    
    if df_raw is not None and not df_raw.empty:
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        for col in COLUMNAS_MAESTRAS:
            if col not in df_raw.columns:
                df_raw[col] = ""
        df_man = df_raw[COLUMNAS_MAESTRAS].copy()
        df_man['Fecha'] = pd.to_datetime(df_man['Fecha'], errors='coerce')
        df_man['Monto'] = pd.to_numeric(df_man['Monto'], errors='coerce').fillna(0.0)
    else:
        df_man = pd.DataFrame(columns=COLUMNAS_MAESTRAS)

except Exception as e:
    if "429" in str(e):
        st.error("🚦 ¡Google está cansado! Espera 1 minuto y refresca la página.")
        st.stop()
    else:
        st.error(f"Error: {e}")
        st.stop()

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuración")
    nuevo_saldo = st.number_input("💰 Saldo Inicial", value=int(saldo_base_valor), step=100, format="%d")
    nuevo_limite = st.number_input("⚠️ Límite de Gasto", value=int(limite_atracón), step=500, format="%d")
    
    if st.button("🍳 Guardar Config"):
        df_conf_save = pd.DataFrame({"SaldoBase": [nuevo_saldo], "Limite": [nuevo_limite]})
        conn.update(worksheet="Config", data=df_conf_save)
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.subheader("🌡️ Termómetro")
    gastos_calc = df_man[df_man['Tipo'] == 'Gasto']['Monto'].sum()
    progreso = min(gastos_calc / nuevo_limite, 1.0) if nuevo_limite > 0 else 0
    st.progress(progreso)
    st.write(f"Llevan ${int(gastos_calc):,} de ${int(nuevo_limite):,}")

# --- 5. REGISTRO ---
tab_reg, tab_ana = st.tabs(["📝 Registro", "📊 Análisis"])

with tab_reg:
    df_editado = st.data_editor(
        df_man,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "Fecha": st.column_config.DateColumn("📅 Fecha", format="DD/MM/YYYY"),
            "Monto": st.column_config.NumberColumn("💵 Monto", format="$%d"),
            "Tipo": st.column_config.SelectboxColumn("✨ Tipo", options=["Gasto", "Abono"]),
            "Responsable": st.column_config.SelectboxColumn("👤 Responsable", options=["Gordify", "Mon"])
        },
        key="editor_2026_quota_fix"
    )

    if st.button("💾 GUARDAR TODO"):
        df_save = df_editado.dropna(subset=['Fecha', 'Concepto']).copy()
        
        if not df_save.empty:
            df_save['Fecha'] = pd.to_datetime(df_save['Fecha']).dt.strftime('%Y-%m-%d')
            df_final = df_save[COLUMNAS_MAESTRAS]
            
            try:
                conn.update(data=df_final)
                st.cache_data.clear() # Forzamos recarga tras guardar
                st.success("✅ Guardado. Google Sheets actualizado.")
                time.sleep(1) # Pausa pequeña para no saturar
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

with tab_ana:
    st.info("💡 Si los datos no aparecen, espera un momento; Google está procesando tu última subida.")
    # Lógica de análisis simplificada para evitar errores de 2026
    df_p = df_man.dropna(subset=['Monto', 'Fecha']).copy()
    if not df_p.empty:
        df_p['Fecha_DT'] = pd.to_datetime(df_p['Fecha']).dt.normalize()
        tot_g = df_p[df_p['Tipo'] == 'Gasto']['Monto'].sum()
        st.subheader(f"Gastado Total: ${int(tot_g):,}")
        
        # Gráfica rápida
        fig = px.line(df_p.sort_values('Fecha'), x='Fecha', y='Monto', color='Tipo', title="Movimientos")
        st.plotly_chart(fig, width='stretch')
