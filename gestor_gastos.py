import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime

st.set_page_config(page_title="Mi Bitácora Pro", layout="wide")

# --- LIMPIEZA DE LLAVE PRIVADA (Evita el error UnsupportedSubstrateError) ---
if "connections" in st.secrets and "gsheets" in st.secrets.connections:
    obj = st.secrets.connections.gsheets
    if hasattr(obj, "private_key") and "\\n" in obj.private_key:
        obj.private_key = obj.private_key.replace("\\n", "\n")

# --- FUNCIONES DE SOPORTE ---
def a_float(v):
    try:
        if pd.isna(v) or str(v).strip() == "": return 0.0
        return float(str(v).replace(',', '').replace('$', '').replace(' ', '').strip())
    except: return 0.0

# --- CONFIGURACIÓN ---
CATEGORIAS = ["Supermercado/Despensa", "Software/Suscripciones", "Alimentos/Restaurantes", "Servicios", "Préstamos", "Viajes", "Salud", "Transporte", "Seguros", "Compras/Otros", "Pagos Realizados"]
METODOS = ["Manual/Físico", "Automático"]
TIPOS = ["Gasto", "Abono"]

# --- CONEXIÓN SEGURA ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_raw = conn.read(ttl=0)
    COLUMNAS = ["Fecha", "Concepto", "Monto", "Tipo", "Categoria", "Metodo_Pago"]
    
    if df_raw is not None and not df_raw.empty:
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        for c in COLUMNAS:
            if c not in df_raw.columns: df_raw[c] = ""
        df_man = df_raw[COLUMNAS].copy()
        
        # Limpieza para que coincida con los selectores del iPad/Web
        for col in ["Tipo", "Categoria", "Metodo_Pago"]:
            df_man[col] = df_man[col].astype(str).str.strip().replace("nan", "")
        
        df_man['Fecha'] = pd.to_datetime(df_man['Fecha'], errors='coerce')
        df_man['Monto'] = pd.to_numeric(df_man['Monto'], errors='coerce').fillna(0.0)
    else:
        df_man = pd.DataFrame(columns=COLUMNAS)

    disponible_banco = 20000.0 # Saldo base inicial

except Exception as e:
    st.error("Error de conexión. Revisa los Secrets y comparte la hoja con el correo del bot.")
    st.exception(e)
    st.stop()

# --- INTERFAZ ---
st.title("📝 Gestor de Gastos en la Nube")
tab1, tab2 = st.tabs(["⌨️ Registro", "📊 Análisis Profundo"])

with tab1:
    st.subheader("Entrada de Movimientos")
    df_editado = st.data_editor(
        df_man, num_rows="dynamic", width="stretch",
        column_config={
            "Fecha": st.column_config.DateColumn("Fecha", format="DD-MM-YYYY"),
            "Tipo": st.column_config.SelectboxColumn("Tipo", options=TIPOS),
            "Metodo_Pago": st.column_config.SelectboxColumn("Método", options=METODOS),
            "Categoria": st.column_config.SelectboxColumn("Categoría", options=CATEGORIAS),
            "Monto": st.column_config.NumberColumn("Monto", format="$%.2f")
        },
        key="editor_v6"
    )
    
    if st.button("💾 GUARDAR CAMBIOS"):
        df_save = df_editado.dropna(subset=['Fecha', 'Monto']).copy()
        # Convertir fecha a texto para Google Sheets
        df_save['Fecha'] = df_save['Fecha'].dt.strftime('%Y-%m-%d')
        conn.update(data=df_save)
        st.success("¡Sincronizado con Google Sheets!")
        st.rerun()

with tab2:
    if not df_man.dropna(subset=['Monto', 'Fecha']).empty:
        # Preparación de datos para análisis
        df_p = df_man.dropna(subset=['Monto', 'Fecha']).copy()
        df_p['Fecha_DT'] = pd.to_datetime(df_p['Fecha']).dt.normalize()
        
        total_g = df_p[df_p['Tipo'] == 'Gasto']['Monto'].sum()
        total_a = df_p[df_p['Tipo'] == 'Abono']['Monto'].sum()
        saldo_final = disponible_banco - total_g + total_a
        uso_manual = (total_g / disponible_banco * 100) if disponible_banco > 0 else 0

        # --- FILA 1: MÉTRICAS Y TERMÓMETRO ---
        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader("📉 Resumen de Disponibilidad")
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("Saldo Banco", f"${disponible_banco:,.2f}")
            mc2.metric("Gastos Totales", f"${total_g:,.2f}", delta_color="inverse")
            mc3.metric("Disponible Real", f"${saldo_final:,.2f}")
        
        with c2:
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number", value = min(uso_manual, 100),
                title = {'text': "% Uso Crédito"},
                gauge = {
                    'axis': {'range': [0, 100]},
                    'bar': {'color': "#1f77b4"},
                    'steps': [
                        {'range': [0, 50], 'color': "lightgreen"},
                        {'range': [50, 80], 'color': "orange"},
                        {'range': [80, 100], 'color': "red"}]}))
            fig_gauge.update_layout(height=250, margin=dict(t=50, b=0, l=20, r=20))
            st.plotly_chart(fig_gauge, use_container_width=True)

        # --- FILA 2: TRAYECTORIA (Gráfica de Escalera) ---
        st.divider()
        diario = df_p.groupby('Fecha_DT').apply(
            lambda x: x[x['Tipo']=='Abono']['Monto'].sum() - x[x['Tipo']=='Gasto']['Monto'].sum()
        ).reset_index(name='Efecto')
        diario = diario.sort_values('Fecha_DT')
        diario['Saldo_Proyectado'] = disponible_banco + diario['Efecto'].cumsum()

        # Añadir punto inicial para que la gráfica empiece bien
        fecha_ini = diario['Fecha_DT'].min() - pd.Timedelta(days=1)
        df_plot = pd.concat([pd.DataFrame({'Fecha_DT':[fecha_ini], 'Saldo_Proyectado':[disponible_banco]}), diario]).sort_values('Fecha_DT')

        fig_line = px.area(df_plot, x='Fecha_DT', y='Saldo_Proyectado', 
                          line_shape="hv", markers=True, title="Evolución del Crédito Disponible")
        fig_line.update_xaxes(dtick="D1", tickformat="%d %b")
        fig_line.update_traces(line_color='#28A745', fillcolor='rgba(40, 167, 69, 0.2)')
        st.plotly_chart(fig_line, use_container_width=True)

        # --- FILA 3: COMPARATIVAS ---
        st.divider()
        gc1, gc2 = st.columns(2)
        with gc1:
            fig_pie = px.pie(df_p[df_p['Tipo'] == 'Gasto'], values='Monto', names='Metodo_Pago', 
                             hole=0.4, title="Métodos de Pago")
            st.plotly_chart(fig_pie, use_container_width=True)
        with gc2:
            fig_cat = px.bar(df_p[df_p['Tipo'] == 'Gasto'].groupby('Categoria')['Monto'].sum().reset_index(),
                             x='Categoria', y='Monto', title="Gastos por Categoría", color='Categoria')
            st.plotly_chart(fig_cat, use_container_width=True)
    else:
        st.warning("No hay datos suficientes para el análisis. Registra movimientos en la otra pestaña.")
