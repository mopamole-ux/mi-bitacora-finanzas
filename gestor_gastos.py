import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Bitácora Comelones 🍔", layout="wide")

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
    
    # Leer Saldo Base
    try:
        df_config = conn.read(worksheet="Config", ttl=0)
        saldo_base_valor = float(df_config.iloc[0, 0]) if not df_config.empty else 20000.0
    except:
        saldo_base_valor = 20000.0

    # Leer Movimientos
    df_man = conn.read(ttl=0)
    COLUMNAS = ["Fecha", "Concepto", "Monto", "Tipo", "Categoria", "Metodo_Pago"]
    
    if df_man is not None and not df_man.empty:
        df_man.columns = [str(c).strip() for c in df_man.columns]
        
        # --- SOLUCIÓN AL PROBLEMA DE LA FECHA ---
        # Forzamos la conversión a datetime al leer, si falla pone NaT (Not a Time)
        df_man['Fecha'] = pd.to_datetime(df_man['Fecha'], errors='coerce')
        
        # Aseguramos el resto de columnas
        for c in COLUMNAS:
            if c not in df_man.columns: df_man[c] = None
        df_man['Monto'] = pd.to_numeric(df_man['Monto'], errors='coerce').fillna(0.0)
    else:
        df_man = pd.DataFrame(columns=COLUMNAS)

except Exception as e:
    st.error(f"Error de conexión: {e}")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.header("👨‍🍳 Menú del Chef")
    nuevo_saldo = st.number_input("💰 Saldo Base", value=int(saldo_base_valor), step=100, format="%d")
    if st.button("🍳 Guardar Saldo"):
        conn.update(worksheet="Config", data=pd.DataFrame({"SaldoBase": [nuevo_saldo]}))
        st.cache_data.clear()
        st.rerun()

# --- INTERFAZ ---
st.title("🍕 El Festín de los Comelones 🌮")
tab_registro, tab_analisis = st.tabs(["⌨️ Registro", "📊 Análisis"])

with tab_registro:
    # Editor de datos
    df_editado = st.data_editor(
        df_man[COLUMNAS],
        num_rows="dynamic",
        width="stretch",
        column_config={
            # Forzamos el formato de visualización aquí también
            "Fecha": st.column_config.DateColumn("📅 Fecha", format="DD/MM/YYYY", required=True),
            "Tipo": st.column_config.SelectboxColumn("✨ Tipo", options=["Gasto", "Abono"]),
            "Monto": st.column_config.NumberColumn("💵 Monto", format="$%d"),
            "Categoria": st.column_config.SelectboxColumn("📂 Categoría", options=["Supermercado/Despensa", "Software/Suscripciones", "Alimentos/Restaurantes", "Servicios", "Viajes", "Otros"])
        },
        key="editor_fechas_fix"
    )
    
    # Totales en tiempo real
    g_actual = df_editado[df_editado['Tipo'] == 'Gasto']['Monto'].sum()
    a_actual = df_editado[df_editado['Tipo'] == 'Abono']['Monto'].sum()
    disponible_final = nuevo_saldo + a_actual - g_actual
    
    c1, c2, c3 = st.columns(3)
    c1.metric("🔴 Gastos", f"${int(g_actual):,}")
    c2.metric("🟢 Abonos", f"${int(a_actual):,}")
    c3.metric("💰 NETO (Saldo Real)", f"${int(disponible_final):,}", delta=f"{int(a_actual - g_actual):,}")

    if st.button("💾 GUARDAR TODO"):
        # Limpiar filas sin fecha o monto
        df_save = df_editado.dropna(subset=['Fecha', 'Monto']).copy()
        
        if not df_save.empty:
            # --- SEGUNDA PARTE DE LA SOLUCIÓN ---
            # Antes de enviar a Google, convertimos la fecha a string simple YYYY-MM-DD
            # Esto evita que Google reciba formatos extraños de Python
            df_save['Fecha'] = df_save['Fecha'].dt.strftime('%Y-%m-%d')
            
            try:
                conn.update(data=df_save)
                st.cache_data.clear()
                st.success("✅ ¡Guardado! Ahora la fecha debería aparecer al recargar.")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

with tab_analisis:
    # Filtramos las fechas que no son válidas para que la gráfica no explote
    df_p = df_man.dropna(subset=['Fecha', 'Monto']).copy()
    if not df_p.empty:
        df_p = df_p.sort_values('Fecha')
        tot_g = df_p[df_p['Tipo'] == 'Gasto']['Monto'].sum()
        tot_a = df_p[df_p['Tipo'] == 'Abono']['Monto'].sum()
        
        st.metric("🥗 Disponible Real", f"${int(nuevo_saldo - tot_g + tot_a):,}")
        
        # Gráfica simple
        df_p['Efecto'] = df_p.apply(lambda x: x['Monto'] if x['Tipo']=='Abono' else -x['Monto'], axis=1)
        df_p['Acumulado'] = nuevo_saldo + df_p['Efecto'].cumsum()
        
        fig = px.line(df_p, x='Fecha', y='Acumulado', title="Trayectoria del Dinero")
        st.plotly_chart(fig, use_container_width=True)
