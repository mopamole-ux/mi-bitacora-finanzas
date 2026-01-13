import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Mi Bitácora Pro", layout="wide")

# --- LIMPIEZA AUTOMÁTICA DE LLAVE (Anti-Incorrect Padding) ---
if "connections" in st.secrets and "gsheets" in st.secrets.connections:
    s = st.secrets.connections.gsheets
    # Reemplazamos posibles errores de pegado de saltos de línea
    if hasattr(s, "private_key"):
        s.private_key = s.private_key.replace("\\n", "\n")

# --- FUNCIONES ---
def a_float(v):
    try:
        if pd.isna(v) or str(v).strip() == "": return 0.0
        return float(str(v).replace(',', '').replace('$', '').replace(' ', '').strip())
    except: return 0.0

# --- CONEXIÓN ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_raw = conn.read(ttl=0)
    COLUMNAS = ["Fecha", "Concepto", "Monto", "Tipo", "Categoria", "Metodo_Pago"]
    
    if df_raw is not None and not df_raw.empty:
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        for c in COLUMNAS:
            if c not in df_raw.columns: df_raw[c] = ""
        df_man = df_raw[COLUMNAS].copy()
        
        for col in ["Tipo", "Categoria", "Metodo_Pago"]:
            df_man[col] = df_man[col].astype(str).str.strip().replace("nan", "")
        
        df_man['Fecha'] = pd.to_datetime(df_man['Fecha'], errors='coerce')
        df_man['Monto'] = pd.to_numeric(df_man['Monto'], errors='coerce').fillna(0.0)
    else:
        df_man = pd.DataFrame(columns=COLUMNAS)

    disponible_banco = 20000.0 

except Exception as e:
    st.error("Error de conexión. Revisa los Secrets.")
    st.exception(e)
    st.stop()

# --- INTERFAZ ---
st.title("📝 Mi Bitácora Financiera")
tab1, tab2 = st.tabs(["⌨️ Registro", "📊 Análisis"])

with tab1:
    df_editado = st.data_editor(
        df_man, num_rows="dynamic", width="stretch",
        column_config={
            "Fecha": st.column_config.DateColumn("Fecha", format="DD-MM-YYYY"),
            "Tipo": st.column_config.SelectboxColumn("Tipo", options=["Gasto", "Abono"]),
            "Metodo_Pago": st.column_config.SelectboxColumn("Método", options=["Manual/Físico", "Automático"]),
            "Categoria": st.column_config.SelectboxColumn("Categoría", options=["Servicios", "Supermercado/Despensa", "Alimentos/Restaurantes", "Software/Suscripciones", "Otros"]),
            "Monto": st.column_config.NumberColumn("Monto", format="$%.2f")
        }
    )
    
    if st.button("💾 GUARDAR"):
        df_save = df_editado.dropna(subset=['Fecha', 'Monto']).copy()
        df_save['Fecha'] = df_save['Fecha'].dt.strftime('%Y-%m-%d')
        conn.update(data=df_save)
        st.success("¡Guardado!")
        st.rerun()

with tab2:
    if not df_man.dropna(subset=['Monto', 'Fecha']).empty:
        df_p = df_man.dropna(subset=['Monto', 'Fecha']).copy()
        df_p['Fecha_DT'] = df_p['Fecha'].dt.normalize()
        
        total_g = df_p[df_p['Tipo'] == 'Gasto']['Monto'].sum()
        total_a = df_p[df_p['Tipo'] == 'Abono']['Monto'].sum()
        saldo_final = disponible_banco - total_g + total_a
        uso_manual = (total_g / disponible_banco * 100) if disponible_banco > 0 else 0

        # Métricas
        c1, c2 = st.columns([2, 1])
        with c1:
            m1, m2, m3 = st.columns(3)
            m1.metric("Límite", f"${disponible_banco:,.2f}")
            m2.metric("Gastos", f"${total_g:,.2f}", delta_color="inverse")
            m3.metric("Disponible", f"${saldo_final:,.2f}")
        
        # Gráfica de Escalera
        diario = df_p.groupby('Fecha_DT').apply(lambda x: x[x['Tipo']=='Abono']['Monto'].sum() - x[x['Tipo']=='Gasto']['Monto'].sum()).reset_index(name='Efecto')
        diario = diario.sort_values('Fecha_DT')
        diario['Saldo'] = disponible_banco + diario['Efecto'].cumsum()

        fig = px.area(diario, x='Fecha_DT', y='Saldo', line_shape="hv", title="Trayectoria del Disponible")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sin datos para analizar.")
