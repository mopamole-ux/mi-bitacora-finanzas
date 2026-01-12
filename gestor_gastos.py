import streamlit as st
from streamlit_gsheets import GSheetsConnection  # Nueva librería
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime

st.set_page_config(page_title="Mi Bitácora de Gastos", layout="wide")
st.title("📝 Gestor de Gastos Personales (Nube)")

# --- FUNCIONES DE SOPORTE ---
def a_float(v):
    try:
        if pd.isna(v) or v == "": return 0.0
        clean_v = str(v).replace(',', '').replace('$', '').replace(' ', '').strip()
        return float(clean_v)
    except: return 0.0

# --- CONEXIÓN A GOOGLE SHEETS ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_man = conn.read()
    
    # Si la hoja está vacía o mal formada, forzamos las columnas correctas
    columnas_requeridas = ["Fecha", "Concepto", "Monto", "Tipo", "Categoria", "Metodo_Pago"]
    
    if df_man is None or df_man.empty:
        df_man = pd.DataFrame(columns=columnas_requeridas)
    else:
        # Si faltan columnas, las añadimos vacías para evitar el KeyError
        for col in columnas_requeridas:
            if col not in df_man.columns:
                df_man[col] = None

    # Limpieza de datos
    df_man['Fecha'] = pd.to_datetime(df_man['Fecha'], errors='coerce')
    df_man['Monto'] = df_man['Monto'].apply(a_float)
    
except Exception as e:
    st.error(f"Error de conexión o formato: {e}")
    st.stop()

# --- CONFIGURACIÓN ---
CATEGORIAS = ["Supermercado/Despensa", "Software/Suscripciones", "Alimentos/Restaurantes", "Servicios", "Préstamos", "Viajes", "Salud", "Transporte", "Seguros", "Compras/Otros", "Pagos Realizados"]
METODOS = ["Manual/Físico", "Automático"]

# Intentar cargar saldo base (si no tienes el archivo en la nube, usamos 0 o un valor base)
disponible_banco = 0.0
if os.path.exists("resumen_mensual.csv"):
    df_res = pd.read_csv("resumen_mensual.csv")
    disponible_banco = a_float(df_res.iloc[0]['CreditoDisponible']) if not df_res.empty else 0.0

# --- TABS ---
tab_bitacora, tab_analisis = st.tabs(["⌨️ Registro Manual", "📊 Análisis de Gastos"])

with tab_bitacora:
    st.subheader("Entrada de Movimientos")
    
    # El editor ahora usa los datos que bajamos de Google Sheets
    df_editado = st.data_editor(
        df_man[["Fecha", "Concepto", "Monto", "Tipo", "Categoria", "Metodo_Pago"]],
        num_rows="dynamic", width="stretch",
        column_config={
            "Fecha": st.column_config.DateColumn("Fecha", format="DD-MM-YYYY", required=True),
            "Tipo": st.column_config.SelectboxColumn("Tipo", options=["Gasto", "Abono"], required=True),
            "Metodo_Pago": st.column_config.SelectboxColumn("Método", options=METODOS, required=True),
            "Categoria": st.column_config.SelectboxColumn("Categoría", options=CATEGORIAS, required=True),
            "Monto": st.column_config.NumberColumn("Monto", format="$%.2f", min_value=0.0)
        },
        key="editor_nube"
    )
    
    # Totales rápidos
    tg = df_editado[df_editado['Tipo'] == 'Gasto']['Monto'].sum()
    ta = df_editado[df_editado['Tipo'] == 'Abono']['Monto'].sum()
    st.markdown(f"**Total Gastos:** ${tg:,.2f} | **Total Abonos:** ${ta:,.2f} | **Neto:** ${tg-ta:,.2f}")

    if st.button("💾 Guardar Cambios en la Nube"):
        # Limpiamos antes de subir
        df_save = df_editado.dropna(subset=['Fecha', 'Monto'], how='any')
        # Formateamos fecha para que Google Sheets la entienda bien
        df_save['Fecha'] = pd.to_datetime(df_save['Fecha']).dt.strftime('%Y-%m-%d')
        
        # MANDAR A GOOGLE SHEETS
        conn.update(data=df_save)
        st.success("¡Datos sincronizados con Google Drive!")
        st.rerun()

with tab_analisis:
    if not df_man.empty:
        # Tu lógica de análisis intacta
        df_p = df_man.dropna(subset=['Monto', 'Fecha']).copy()
        df_p['Fecha_DT'] = pd.to_datetime(df_p['Fecha']).dt.normalize()
        
        total_g = df_p[df_p['Tipo'] == 'Gasto']['Monto'].sum()
        total_a = df_p[df_p['Tipo'] == 'Abono']['Monto'].sum()
        saldo_final = disponible_banco - total_g + total_a
        uso_manual = (total_g / disponible_banco * 100) if disponible_banco > 0 else 0

        # --- FILA 1: MÉTRICAS ---
        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader("📉 Resumen de Flujo")
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("Saldo Banco (Base)", f"${disponible_banco:,.2f}")
            mc2.metric("Gastos Bitácora", f"${total_g:,.2f}", delta_color="inverse")
            mc3.metric("Disponible Estimado", f"${saldo_final:,.2f}")
        
        with c2:
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number", value = uso_manual,
                title = {'text': "% Uso de Disponible"},
                gauge = {
                    'axis': {'range': [0, 100]},
                    'bar': {'color': "#1f77b4"},
                    'steps': [
                        {'range': [0, 50], 'color': "lightgreen"},
                        {'range': [50, 80], 'color': "orange"},
                        {'range': [80, 100], 'color': "red"}]}))
            fig_gauge.update_layout(height=250, margin=dict(t=50, b=0, l=20, r=20))
            st.plotly_chart(fig_gauge, use_container_width=True)

        # --- FILA 2: GRÁFICA DE ESCALERA ---
        st.divider()
        diario = df_p.groupby('Fecha_DT').apply(lambda x: (x[x['Tipo']=='Abono']['Monto'].sum() - x[x['Tipo']=='Gasto']['Monto'].sum())).reset_index(name='Efecto')
        diario = diario.sort_values('Fecha_DT')
        diario['Saldo_Proyectado'] = disponible_banco + diario['Efecto'].cumsum()

        fecha_ini = diario['Fecha_DT'].min() - pd.Timedelta(days=1) if not diario.empty else datetime.now()
        df_plot = pd.concat([pd.DataFrame({'Fecha_DT':[fecha_ini], 'Saldo_Proyectado':[disponible_banco]}), diario]).sort_values('Fecha_DT')

        fig_line = px.area(df_plot, x='Fecha_DT', y='Saldo_Proyectado', 
                          line_shape="hv", markers=True, title="Trayectoria del Crédito Disponible")
        fig_line.update_xaxes(dtick="D1", tickformat="%d %b")
        fig_line.update_traces(line_color='#28A745', fillcolor='rgba(40, 167, 69, 0.2)')
        fig_line.add_hline(y=0, line_dash="dash", line_color="red")
        st.plotly_chart(fig_line, use_container_width=True)

        # --- FILA 3: DISTRIBUCIÓN ---
        st.divider()
        gc1, gc2 = st.columns(2)
        with gc1:
            fig_pie = px.pie(df_p[df_p['Tipo'] == 'Gasto'], values='Monto', names='Metodo_Pago', hole=0.4, title="Gastos: Auto vs Manual")
            st.plotly_chart(fig_pie, use_container_width=True)
        with gc2:
            fig_cat = px.bar(df_p[df_p['Tipo'] == 'Gasto'].groupby('Categoria')['Monto'].sum().reset_index(), x='Categoria', y='Monto', title="Gastos por Categoría", color='Monto')
            st.plotly_chart(fig_cat, use_container_width=True)
    else:
        st.info("Agrega datos para ver el análisis.")
