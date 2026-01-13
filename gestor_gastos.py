import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. CONFIGURACIÓN ÚNICA
st.set_page_config(page_title="Bitácora de Gorditos 🍔", layout="wide")

# --- BANNER ---
URL_BANNER = "https://lh3.googleusercontent.com/d/11Rdr2cVYIypLjmSp9jssuvoOxQ-kI1IZ"
st.image(URL_BANNER, use_container_width=True)
st.title("🍕 Bitácora de Gorditos 🍔")

# --- 2. CONEXIÓN ---
conn = st.connection("gsheets", type=GSheetsConnection)

COLUMNAS_MAESTRAS = [
    "Fecha", "Concepto", "Monto", "Tipo", 
    "Categoria", "Tipo_Pago", "Metodo_Pago", "Responsable"
]

# --- 3. LECTURA ---
try:
    # Saldo Base
    try:
        df_config = conn.read(worksheet="Config", ttl=0)
        saldo_base = float(df_config.iloc[0, 0]) if not df_config.empty else 20000.0
    except:
        saldo_base = 20000.0

    # Movimientos
    df_raw = conn.read(ttl=0)
    
    if df_raw is not None:
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        # Asegurar que existan todas
        for c in COLUMNAS_MAESTRAS:
            if c not in df_raw.columns: df_raw[c] = ""
        
        df_man = df_raw[COLUMNAS_MAESTRAS].copy()
        # Limpieza profunda de tipos
        df_man['Fecha'] = pd.to_datetime(df_man['Fecha'], errors='coerce')
        df_man['Monto'] = pd.to_numeric(df_man['Monto'], errors='coerce').fillna(0.0)
        # Forzar todo lo demás a texto para que el editor no se bloquee
        for c in ["Concepto", "Tipo", "Categoria", "Tipo_Pago", "Metodo_Pago", "Responsable"]:
            df_man[c] = df_man[c].astype(str).replace("nan", "")
    else:
        df_man = pd.DataFrame(columns=COLUMNAS_MAESTRAS)

except Exception as e:
    st.error(f"Error al cargar: {e}")
    st.stop()

# --- 4. SIDEBAR ---
with st.sidebar:
    nuevo_saldo = st.number_input("💰 Saldo Base", value=int(saldo_base), step=100)
    if st.button("🍳 Guardar Saldo"):
        conn.update(worksheet="Config", data=pd.DataFrame({"SaldoBase": [nuevo_saldo]}))
        st.cache_data.clear()
        st.rerun()

# --- 5. REGISTRO ---
tab_reg, tab_ana = st.tabs(["⌨️ Registro", "📊 Análisis"])

with tab_reg:
    df_editado = st.data_editor(
        df_man,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "Fecha": st.column_config.DateColumn("📅 Fecha", format="DD/MM/YYYY", required=True),
            "Monto": st.column_config.NumberColumn("💵 Monto", format="$%d"),
            "Tipo": st.column_config.SelectboxColumn("✨ Tipo", options=["Gasto", "Abono"]),
            "Categoria": st.column_config.SelectboxColumn("📂 Categoría", options=["Super", "Software", "Suscripciones", "Restaurantes", "Servicios", "Salud", "Préstamos", "Viajes", "Otros"]),
            "Tipo_Pago": st.column_config.SelectboxColumn("🪙 Tipo pago", options=["Manual", "Automático"]),
            "Metodo_Pago": st.column_config.SelectboxColumn("💳 Forma pago", options=["TDC", "Efectivo", "TDD"]),
            "Responsable": st.column_config.SelectboxColumn("👤 Responsable", options=["Gordify", "Mon"])
        },
        key="editor_fuerza_bruta_v5" # Nueva key para limpiar iPad
    )

    # Totales rápidos
    g_act = df_editado[df_editado['Tipo'] == 'Gasto']['Monto'].sum()
    a_act = df_editado[df_editado['Tipo'] == 'Abono']['Monto'].sum()
    
    st.metric("💰 NETO (Base + Movimientos)", f"${int(nuevo_saldo + a_act - g_act):,}")

    if st.button("💾 GUARDAR TODO EN LA NUBE"):
        # LIMPIEZA EXTREMA ANTES DE ENVIAR
        # 1. Quitar filas donde la Fecha sea nula (NaT)
        df_save = df_editado[df_editado['Fecha'].notna()].copy()
        
        if not df_save.empty:
            # 2. Convertir Fecha a Texto ISO
            df_save['Fecha'] = df_save['Fecha'].dt.strftime('%Y-%m-%d')
            
            # 3. Rellenar cualquier celda vacía con un espacio para que Google no la rechace
            df_save = df_save.fillna("")
            
            # 4. Asegurar las 8 columnas en orden
            df_final = df_save[COLUMNAS_MAESTRAS]
            
            try:
                # 5. Intentar el guardado
                conn.update(data=df_final)
                st.cache_data.clear()
                st.success("✅ ¡Sincronización Exitosa! Datos en la nube.")
                st.balloons()
                st.rerun()
            except Exception as e:
                st.error(f"Error crítico al guardar: {e}")
        else:
            st.warning("No hay filas con Fecha para guardar.")
