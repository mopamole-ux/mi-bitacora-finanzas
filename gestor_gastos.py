import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Bitácora de Gorditos 🍔", layout="wide")

# --- BANNER ---
URL_BANNER = "https://lh3.googleusercontent.com/d/11Rdr2cVYIypLjmSp9jssuvoOxQ-kI1IZ"
st.image(URL_BANNER, use_container_width=True)

st.title("🍕 Bitácora de Gorditos 🍔")

# --- ESTILOS CSS ---
st.markdown("""
    <style>
    .main { background-color: #fffaf0; }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 1. CONFIGURACIÓN DE SEGURIDAD ---
if "connections" in st.secrets and "gsheets" in st.secrets.connections:
    secret_dict = dict(st.secrets.connections.gsheets)
    if "private_key" in secret_dict:
        secret_dict["private_key"] = secret_dict["private_key"].replace("\\n", "\n")
else:
    st.error("¡Faltan las credenciales!")
    st.stop()

# --- 2. CONEXIÓN Y LECTURA ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Leer Config (Saldo y Límite)
    try:
        df_config = conn.read(worksheet="Config", ttl=0)
        saldo_base_valor = float(df_config.iloc[0, 0]) if not df_config.empty else 20000.0
        limite_atracón = float(df_config.iloc[0, 1]) if len(df_config.columns) > 1 else 15000.0
    except:
        saldo_base_valor, limite_atracón = 20000.0, 15000.0

    # Leer Movimientos
    df_man = conn.read(ttl=0)
    # Lista maestra de columnas (asegúrate que coincidan con el Excel)
    COLUMNAS = ["Fecha", "Concepto", "Monto", "Tipo", "Categoria", "Tipo_Pago", "Metodo_Pago", "Responsable"]
    
    if df_man is not None and not df_man.empty:
        df_man.columns = [str(c).strip() for c in df_man.columns]
        for c in COLUMNAS:
            if c not in df_man.columns: df_man[c] = None
        
        df_man['Fecha'] = pd.to_datetime(df_man['Fecha'], errors='coerce')
        df_man['Monto'] = pd.to_numeric(df_man['Monto'], errors='coerce').fillna(0.0)
    else:
        df_man = pd.DataFrame(columns=COLUMNAS)

except Exception as e:
    st.error(f"Error de conexión: {e}")
    st.stop()

# --- SIDEBAR: TERMÓMETRO Y CONFIG ---
with st.sidebar:
    st.header("⚙️ Configuración")
    nuevo_saldo = st.number_input("💰 Saldo Base", value=int(saldo_base_valor), step=100)
    nuevo_limite = st.number_input("⚠️ Límite de Atracón", value=int(limite_atracón), step=500)
    
    if st.button("Guardar Configuración"):
        df_conf_save = pd.DataFrame({"SaldoBase": [nuevo_saldo], "Limite": [nuevo_limite]})
        conn.update(worksheet="Config", data=df_conf_save)
        st.cache_data.clear()
        st.success("¡Configuración guardada!")
        st.rerun()

    st.divider()
    st.subheader("🌡️ Termómetro de Atracón")
    gastos_totales = df_man[df_man['Tipo'] == 'Gasto']['Monto'].sum()
    progreso = min(gastos_totales / nuevo_limite, 1.0) if nuevo_limite > 0 else 0
    
    if gastos_totales > nuevo_limite:
        st.error(f"🚨 ¡LIMITE SUPERADO! Llevan ${int(gastos_totales):,}")
    else:
        st.progress(progreso)
        st.info(f"Llevan ${int(gastos_totales):,} de ${int(nuevo_limite):,}")

# --- INTERFAZ ---
tab_registro, tab_analisis = st.tabs(["⌨️ Registro", "📊 Análisis"])

with tab_registro:
    df_editado = st.data_editor(
        df_man[COLUMNAS],
        num_rows="dynamic",
        width="stretch",
        column_config={
            "Fecha": st.column_config.DateColumn("📅 Fecha", format="DD/MM/YYYY", required=True),
            "Tipo": st.column_config.SelectboxColumn("✨ Tipo", options=["Gasto", "Abono"]),
            "Monto": st.column_config.NumberColumn("💵 Monto", format="$%d"),
            "Categoria": st.column_config.SelectboxColumn("📂 Categoría", options=["Super", "Software", "Suscripciones", "Restaurantes", "Servicios", "Salud", "Préstamos", "Pago TDC", "Salarios", "Viajes", "Otros"]),
            "Tipo_Pago": st.column_config.SelectboxColumn("🪙 Tipo pago", options=["Manual", "Automático"]),
            "Metodo_Pago": st.column_config.SelectboxColumn("💳 Forma pago", options=["TDC", "Efectivo", "TDD"]),
            "Responsable": st.column_config.SelectboxColumn("👤 Responsable", options=["Gordify", "Mon"])
        },
        key="editor_final_v1"
    )
    
    # Totales rápidos
    g_actual = df_editado[df_editado['Tipo'] == 'Gasto']['Monto'].sum()
    a_actual = df_editado[df_editado['Tipo'] == 'Abono']['Monto'].sum()
    disponible_final = nuevo_saldo + a_actual - g_actual
    
    c1, c2, c3 = st.columns(3)
    c1.metric("🔴 Gastos", f"${int(g_actual):,}")
    c2.metric("🟢 Abonos", f"${int(a_actual):,}")
    c3.metric("💰 NETO", f"${int(disponible_final):,}", delta=f"{int(a_actual - g_actual):,}")

    if st.button("💾 GUARDAR TODO"):
        df_save = df_editado.dropna(subset=['Fecha', 'Monto']).copy()
        if not df_save.empty:
            df_save['Fecha'] = pd.to_datetime(df_save['Fecha']).dt.strftime('%Y-%m-%d')
            try:
                # IMPORTANTE: Forzamos el guardado de TODAS las columnas
                conn.update(data=df_save[COLUMNAS])
                st.cache_data.clear()
                st.success("✅ ¡Datos guardados en la nube!")
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

with tab_analisis:
    # (Tu código de gráficas actual funciona bien, se mantiene igual)
    df_p = df_man.dropna(subset=['Monto', 'Fecha']).copy()
    if not df_p.empty:
        df_p['Fecha_DT'] = pd.to_datetime(df_p['Fecha']).dt.normalize()
        # ... resto del código de gráficas ...
        st.write("Datos listos para análisis.")
