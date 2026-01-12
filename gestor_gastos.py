import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime

# --- FUNCIONES DE SOPORTE ---
def a_float(v):
    try:
        if pd.isna(v) or v == "": return 0.0
        clean_v = str(v).replace(',', '').replace('$', '').replace(' ', '').strip()
        return float(clean_v)
    except: return 0.0

# --- CONFIGURACIÓN DE OPCIONES ---
CATEGORIAS = ["Supermercado/Despensa", "Software/Suscripciones", "Alimentos/Restaurantes", "Servicios", "Préstamos", "Viajes", "Salud", "Transporte", "Seguros", "Compras/Otros", "Pagos Realizados"]
METODOS = ["Manual/Físico", "Automático"]
TIPOS = ["Gasto", "Abono"]

import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime

st.set_page_config(page_title="Mi Bitácora Pro", layout="wide")
st.title("📝 Gestor de Gastos en la Nube")

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

# --- CONEXIÓN A GOOGLE SHEETS ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    # TTL=0 para que siempre refresque los datos de la nube
    df_raw = conn.read(ttl=0)
    
    if df_raw is not None:
        # LIMPIEZA DE COLUMNAS: Forzar nombres exactos sin espacios
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        
        # Filtrar solo las columnas que nos interesan
        cols_ok = ["Fecha", "Concepto", "Monto", "Tipo", "Categoria", "Metodo_Pago"]
        df_man = df_raw[cols_ok].copy() if all(c in df_raw.columns for c in cols_ok) else df_raw.copy()
        
        # LIMPIEZA DE CONTENIDO: Quitar espacios que rompen los selectores
        for col in ["Tipo", "Categoria", "Metodo_Pago"]:
            if col in df_man.columns:
                df_man[col] = df_man[col].astype(str).str.strip()
        
        df_man['Fecha'] = pd.to_datetime(df_man['Fecha'], errors='coerce')
        df_man['Monto'] = df_man['Monto'].apply(a_float)
    else:
        df_man = pd.DataFrame(columns=cols_ok)

except Exception as e:
    st.error(f"Error al leer de Google Sheets. Verifica que los títulos en el Excel sean exactamente: Fecha, Concepto, Monto, Tipo, Categoria, Metodo_Pago")
    st.stop()

# --- INTERFAZ ---
tab_bitacora, tab_analisis = st.tabs(["⌨️ Registro Manual", "📊 Análisis Profundo"])

with tab_bitacora:
    st.subheader("Entrada de Movimientos")
    
    df_editado = st.data_editor(
        df_man,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "Fecha": st.column_config.DateColumn("Fecha", format="DD-MM-YYYY"),
            "Tipo": st.column_config.SelectboxColumn("Tipo", options=TIPOS),
            "Metodo_Pago": st.column_config.SelectboxColumn("Método", options=METODOS),
            "Categoria": st.column_config.SelectboxColumn("Categoría", options=CATEGORIAS),
            "Monto": st.column_config.NumberColumn("Monto", format="$%.2f")
        },
        key="editor_v5"
    )
    
    if st.button("💾 GUARDAR EN LA NUBE"):
        try:
            df_save = df_editado.dropna(subset=['Fecha', 'Monto'], how='any').copy()
            df_save['Fecha'] = df_save['Fecha'].dt.strftime('%Y-%m-%d')
            # Intentar actualizar
            conn.update(data=df_save)
            st.success("¡Datos guardados con éxito!")
            st.rerun()
        except Exception as e:
            st.error("❌ ERROR DE PERMISOS DE GOOGLE")
            st.warning("Google Sheets no permite 'Escribir' datos mediante un link público. Para solucionar esto DEBES usar el archivo JSON de Service Account o conectar vía Privada.")
            st.info("Mientras tanto, tus datos se muestran pero no se pueden guardar permanentemente en el Excel desde aquí.")



with tab_analisis:
    if not df_man.dropna(subset=['Monto']).empty:
        # 1. Cálculos de Estado
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
            mc2.metric("Gastos Registrados", f"${total_g:,.2f}", delta_color="inverse")
            mc3.metric("Disponible Final", f"${saldo_final:,.2f}")
        
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

        # --- FILA 2: TRAYECTORIA ---
        st.divider()
        diario = df_p.groupby('Fecha_DT').apply(lambda x: (x[x['Tipo']=='Abono']['Monto'].sum() - x[x['Tipo']=='Gasto']['Monto'].sum())).reset_index(name='Efecto')
        diario = diario.sort_values('Fecha_DT')
        diario['Saldo_Proyectado'] = disponible_banco + diario['Efecto'].cumsum()

        fecha_ini = diario['Fecha_DT'].min() - pd.Timedelta(days=1)
        df_plot = pd.concat([pd.DataFrame({'Fecha_DT':[fecha_ini], 'Saldo_Proyectado':[disponible_banco]}), diario]).sort_values('Fecha_DT')

        fig_line = px.area(df_plot, x='Fecha_DT', y='Saldo_Proyectado', 
                          line_shape="hv", markers=True, title="Evolución del Crédito Disponible")
        fig_line.update_xaxes(dtick="D1", tickformat="%d %b")
        fig_line.update_traces(line_color='#28A745', fillcolor='rgba(40, 167, 69, 0.2)')
        fig_line.add_hline(y=0, line_dash="dash", line_color="red")
        st.plotly_chart(fig_line, use_container_width=True)

        # --- FILA 3: COMPARATIVAS ---
        st.divider()
        gc1, gc2 = st.columns(2)
        with gc1:
            fig_pie = px.pie(df_p[df_p['Tipo'] == 'Gasto'], values='Monto', names='Metodo_Pago', 
                             hole=0.4, title="Manual vs Automático",
                             color_discrete_map={"Manual/Físico":"#1f77b4", "Automático":"#ff7f0e"})
            st.plotly_chart(fig_pie, use_container_width=True)
        with gc2:
            fig_cat = px.bar(df_p[df_p['Tipo'] == 'Gasto'].groupby('Categoria')['Monto'].sum().reset_index(),
                             x='Categoria', y='Monto', title="Gastos por Categoría", color='Categoria')
            st.plotly_chart(fig_cat, use_container_width=True)
    else:
        st.warning("No hay datos suficientes para el análisis. Registra movimientos primero.")
