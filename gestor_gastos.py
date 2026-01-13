import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="Bitácora Comelones 🍔", layout="wide")
st.title("🍕 Finanzas de gorditos 🌮")

# --- 1. CONFIGURACIÓN DE SEGURIDAD ---
if "connections" in st.secrets and "gsheets" in st.secrets.connections:
    secret_dict = dict(st.secrets.connections.gsheets)
    if "private_key" in secret_dict:
        secret_dict["private_key"] = secret_dict["private_key"].replace("\\n", "\n")
else:
    st.error("¡Faltan las credenciales!")
    st.stop()

# --- 2. CONEXIÓN ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Leer Saldo Base de 'Config'
    try:
        df_config = conn.read(worksheet="Config", ttl=0)
        saldo_base_valor = float(df_config.iloc[0, 0]) if not df_config.empty else 20000.0
    except:
        saldo_base_valor = 20000.0

    # Leer Movimientos con TTL=0 (Sin memoria vieja)
    df_man = conn.read(ttl=0)
    COLUMNAS = ["Fecha", "Concepto", "Monto", "Tipo", "Categoria", "Metodo_Pago"]
    
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

# --- SIDEBAR: CONFIGURACIÓN ---
with st.sidebar:
    st.header("👨‍🍳 El Chef del Dinero")
    nuevo_saldo = st.number_input("💰 Saldo Inicial", value=int(saldo_base_valor), step=100, format="%d")
    
    if st.button("🍳 Guardar Saldo Base"):
        try:
            df_conf_save = pd.DataFrame({"SaldoBase": [nuevo_saldo]})
            conn.update(worksheet="Config", data=df_conf_save)
            st.cache_data.clear()
            st.success("¡Saldo base guardado!")
            st.rerun()
        except:
            st.error("¿Creaste la pestaña 'Config'?")

# --- TABS ---
tab_registro, tab_analisis = st.tabs(["📝 Anotar Pedido", "📊 ¿Cuánto nos comimos?"])

with tab_registro:
    st.subheader("🛒 Registro de Movimientos")
    
    # Editor de datos con nueva Key para forzar refresco
    df_editado = st.data_editor(
        df_man[COLUMNAS],
        num_rows="dynamic",
        width="stretch",
        column_config={
            "Fecha": st.column_config.DateColumn("Fecha", format="DD-MM-YYYY"),
            "Tipo": st.column_config.SelectboxColumn("Tipo", options=["Gasto", "Abono"]),
            "Monto": st.column_config.NumberColumn("Monto", format="$%d"),
            "Categoria": st.column_config.SelectboxColumn("Categoría", options=["Supermercado/Despensa", "Software/Suscripciones", "Alimentos/Restaurantes", "Servicios", "Viajes", "Otros"])
        },
        key="editor_comelones_vFINAL_FIX"
    )
    
    # --- CÁLCULO DE TOTALES ---
    st.markdown("### 📊 Resumen de esta sesión")
    g_actual = df_editado[df_editado['Tipo'] == 'Gasto']['Monto'].sum()
    a_actual = df_editado[df_editado['Tipo'] == 'Abono']['Monto'].sum()
    neto_total = nuevo_saldo + a_actual - g_actual
    
    c1, c2, c3 = st.columns(3)
    c1.metric("🔴 Gastos", f"${int(g_actual):,}")
    c2.metric("🟢 Abonos", f"${int(a_actual):,}")
    c3.metric("💰 DISPONIBLE FINAL", f"${int(neto_total):,}", delta=f"{int(a_actual - g_actual):,}")

    st.markdown("---")

    if st.button("💾 GUARDAR TODO EN LA NUBE"):
        # Limpiar datos para el guardado
        df_save = df_editado.dropna(subset=['Fecha', 'Monto']).copy()
        
        if not df_save.empty:
            # Forzar formato de fecha texto
            df_save['Fecha'] = pd.to_datetime(df_save['Fecha']).dt.strftime('%Y-%m-%d')
            
            try:
                # El comando clave: Actualizar
                conn.update(data=df_save)
                
                # ¡IMPORTANTE! Limpiar la caché para que la App lea los cambios de Sheets
                st.cache_data.clear()
                
                st.success("✅ ¡Datos guardados exitosamente!")
                st.balloons()
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")
        else:
            st.warning("Escribe algo antes de guardar.")

with tab_analisis:
    # Lógica de gráficas aquí... (se mantiene igual que antes)
    st.info("Revisa la pestaña de registro para actualizar datos.")
