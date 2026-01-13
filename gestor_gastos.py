import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px

# 1. CONFIGURACIÓN INICIAL
st.set_page_config(page_title="Bitácora de Gorditos 🍔", layout="wide")

# Banner con el nuevo estándar de ancho
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
    # Leer Configuración (Saldo y Límite)
    df_config = conn.read(worksheet="Config", ttl=0)
    if not df_config.empty:
        saldo_base_valor = float(df_config.iloc[0, 0])
        limite_atracon = float(df_config.iloc[0, 1]) if len(df_config.columns) > 1 else 15000.0
    else:
        saldo_base_valor, limite_atracon = 20000.0, 15000.0

    # Leer Movimientos
    df_raw = conn.read(ttl=0)
    
    if df_raw is not None and not df_raw.empty:
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        # Asegurar que existan las 8 columnas
        for col in COLUMNAS_MAESTRAS:
            if col not in df_raw.columns:
                df_raw[col] = ""
        df_man = df_raw[COLUMNAS_MAESTRAS].copy()
        df_man['Fecha'] = pd.to_datetime(df_man['Fecha'], errors='coerce')
        df_man['Monto'] = pd.to_numeric(df_man['Monto'], errors='coerce').fillna(0.0)
    else:
        df_man = pd.DataFrame(columns=COLUMNAS_MAESTRAS)

except Exception as e:
    st.error(f"Error de conexión: {e}")
    st.stop()

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuración")
    n_saldo = st.number_input("💰 Saldo Base", value=int(saldo_base_valor), step=100)
    n_limite = st.number_input("⚠️ Límite Gasto", value=int(limite_atracon), step=500)
    
    if st.button("🍳 Guardar Config"):
        df_conf_save = pd.DataFrame({"SaldoBase": [n_saldo], "Limite": [n_limite]})
        conn.update(worksheet="Config", data=df_conf_save)
        st.cache_data.clear()
        st.rerun()

# --- 5. REGISTRO ---
tab_reg, tab_ana = st.tabs(["📝 Registro", "📊 Análisis"])

with tab_reg:
    # Editor con clave nueva para forzar limpieza
    df_editado = st.data_editor(
        df_man,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "Fecha": st.column_config.DateColumn("📅 Fecha", format="DD/MM/YYYY"),
            "Tipo": st.column_config.SelectboxColumn("✨ Tipo", options=["Gasto", "Abono"]),
            "Monto": st.column_config.NumberColumn("💵 Monto", format="$%d"),
            "Categoria": st.column_config.SelectboxColumn("📂 Categoría", options=["Super", "Software", "Suscripciones", "Restaurantes", "Servicios", "Salud", "Viajes", "Otros"]),
            "Tipo_Pago": st.column_config.SelectboxColumn("🪙 Tipo pago", options=["Manual", "Automático"]),
            "Metodo_Pago": st.column_config.SelectboxColumn("💳 Forma pago", options=["TDC", "Efectivo", "TDD"]),
            "Responsable": st.column_config.SelectboxColumn("👤 Responsable", options=["Gordify", "Mon"])
        },
        key="editor_2026_final_safe"
    )

    # Métricas Proyectadas
    g_act = df_editado[df_editado['Tipo'] == 'Gasto']['Monto'].sum()
    a_act = df_editado[df_editado['Tipo'] == 'Abono']['Monto'].sum()
    st.metric("💰 NETO PROYECTADO", f"${int(n_saldo + a_act - g_act):,}")

    if st.button("💾 GUARDAR TODO"):
        # PASO CRÍTICO: Eliminar filas donde el Concepto o la Fecha estén vacíos
        # Esto evita enviar basura a Google Sheets
        df_save = df_editado.dropna(subset=['Fecha', 'Concepto']).copy()
        
        if not df_save.empty:
            # Convertir Fecha a Texto ISO para estabilidad
            df_save['Fecha'] = pd.to_datetime(df_save['Fecha']).dt.strftime('%Y-%m-%d')
            
            # Forzar todas las columnas maestras
            df_final = df_save[COLUMNAS_MAESTRAS]
            
            try:
                # Borramos caché antes de intentar subir
                st.cache_data.clear()
                conn.update(data=df_final)
                st.success("✅ ¡Guardado con éxito!")
                st.balloons()
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")
        else:
            st.warning("⚠️ Escribe al menos la Fecha y el Concepto.")

with tab_ana:
    # Lógica de análisis simplificada para evitar errores de 2026
    df_p = df_man.dropna(subset=['Monto', 'Fecha']).copy()
    if not df_p.empty:
        df_p['Fecha_DT'] = pd.to_datetime(df_p['Fecha']).dt.normalize()
        tot_g = df_p[df_p['Tipo'] == 'Gasto']['Monto'].sum()
        st.subheader(f"Gastado Total: ${int(tot_g):,}")
        
        # Gráfica rápida
        fig = px.line(df_p.sort_values('Fecha'), x='Fecha', y='Monto', color='Tipo', title="Movimientos")
        st.plotly_chart(fig, width='stretch')
