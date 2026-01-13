import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px

# 1. CONFIGURACIÓN ÚNICA
st.set_page_config(page_title="Bitácora de Gorditos 🍔", layout="wide")

# --- BANNER ---
URL_BANNER = "https://lh3.googleusercontent.com/d/11Rdr2cVYIypLjmSp9jssuvoOxQ-kI1IZ"
st.image(URL_BANNER, use_container_width=True)

st.title("🍕 Bitácora de Gorditos 🍔")

# --- 2. CONEXIÓN Y ESTRUCTURA ---
conn = st.connection("gsheets", type=GSheetsConnection)

# Definimos el orden y nombres exactos
COLUMNAS_MAESTRAS = [
    "Fecha", "Concepto", "Monto", "Tipo", 
    "Categoria", "Tipo_Pago", "Metodo_Pago", "Responsable"
]

# --- 3. LECTURA DE DATOS ---
try:
    # Leer Configuración (Pestaña Config)
    try:
        df_config = conn.read(worksheet="Config", ttl=0)
        saldo_base_valor = float(df_config.iloc[0, 0]) if not df_config.empty else 20000.0
        limite_atracón = float(df_config.iloc[0, 1]) if len(df_config.columns) > 1 else 15000.0
    except:
        saldo_base_valor, limite_atracón = 20000.0, 15000.0

    # Leer Movimientos
    df_man = conn.read(ttl=0)
    
    if df_man is not None:
        # Limpiar nombres de columnas
        df_man.columns = [str(c).strip() for c in df_man.columns]
        
        # FORZAR ESTRUCTURA: Asegurar que existan las 8 columnas y que sean texto
        for col in COLUMNAS_MAESTRAS:
            if col not in df_man.columns:
                df_man[col] = ""
        
        # Reordenar y limpiar vacíos para evitar errores en el editor
        df_man = df_man[COLUMNAS_MAESTRAS].fillna("")
        
        # Convertir tipos específicos para que el editor no se bloquee
        df_man['Fecha'] = pd.to_datetime(df_man['Fecha'], errors='coerce')
        df_man['Monto'] = pd.to_numeric(df_man['Monto'], errors='coerce').fillna(0.0)
        df_man['Concepto'] = df_man['Concepto'].astype(str)
        df_man['Responsable'] = df_man['Responsable'].astype(str)
    else:
        df_man = pd.DataFrame(columns=COLUMNAS_MAESTRAS)

except Exception as e:
    st.error(f"Error al leer datos: {e}")
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
        st.success("Configuración guardada")
        st.rerun()

# --- 5. REGISTRO ---
tab_reg, tab_ana = st.tabs(["📝 Registro", "📊 Análisis"])

with tab_reg:
    st.subheader("🛒 Registro de Movimientos")
    
    # IMPORTANTE: El data_editor debe recibir el DataFrame limpio
    df_editado = st.data_editor(
        df_man,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "Fecha": st.column_config.DateColumn("📅 Fecha", format="DD/MM/YYYY"),
            "Concepto": st.column_config.TextColumn("📝 Concepto", required=True),
            "Tipo": st.column_config.SelectboxColumn("✨ Tipo", options=["Gasto", "Abono"]),
            "Monto": st.column_config.NumberColumn("💵 Monto", format="$%d"),
            "Categoria": st.column_config.SelectboxColumn("📂 Categoría", options=["Super", "Software", "Suscripciones", "Restaurantes", "Servicios", "Salud", "Préstamos", "Pago TDC", "Salarios", "Viajes", "Otros"]),
            "Tipo_Pago": st.column_config.SelectboxColumn("🪙 Tipo pago", options=["Manual", "Automático"]),
            "Metodo_Pago": st.column_config.SelectboxColumn("💳 Forma pago", options=["TDC", "Efectivo", "TDD"]),
            "Responsable": st.column_config.SelectboxColumn("👤 Responsable", options=["Gordify", "Mon"])
        },
        key="editor_definitivo_v3" 
    )

    # Totales proyectados
    g_actual = df_editado[df_editado['Tipo'] == 'Gasto']['Monto'].sum()
    a_actual = df_editado[df_editado['Tipo'] == 'Abono']['Monto'].sum()
    neto_proyectado = nuevo_saldo + a_actual - g_actual

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("🔴 Gastos", f"${int(g_actual):,}")
    c2.metric("🟢 Abonos", f"${int(a_actual):,}")
    c3.metric("💰 NETO PROYECTADO", f"${int(neto_proyectado):,}")
    st.markdown("---")

    if st.button("💾 GUARDAR TODO EN GOOGLE SHEETS"):
        # Filtrar filas que al menos tengan Fecha
        df_save = df_editado.dropna(subset=['Fecha']).copy()
        
        if not df_save.empty:
            # Formateo final antes de enviar
            df_save['Fecha'] = pd.to_datetime(df_save['Fecha']).dt.strftime('%Y-%m-%d')
            df_save['Monto'] = df_save['Monto'].astype(float)
            
            # Asegurar que enviamos las 8 columnas exactas y convertirlas a string
            for col in ["Concepto", "Tipo", "Categoria", "Tipo_Pago", "Metodo_Pago", "Responsable"]:
                df_save[col] = df_save[col].astype(str)

            df_final_to_send = df_save[COLUMNAS_MAESTRAS]
            
            try:
                conn.update(data=df_final_to_send)
                st.cache_data.clear()
                st.success("✅ ¡Sincronizado! Responsable y Concepto guardados.")
                st.balloons()
                st.rerun()
            except Exception as e:
                st.error(f"Error al sincronizar: {e}")
