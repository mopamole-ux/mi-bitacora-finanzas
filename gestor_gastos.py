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

import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Mi Bitácora Pro", layout="wide")

# --- CONEXIÓN ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Intentamos leer la hoja
    df_raw = conn.read(ttl=0)
    
    # Definimos las columnas que DEBEN existir
    cols_necesarias = ["Fecha", "Concepto", "Monto", "Tipo", "Categoria", "Metodo_Pago"]
    
    if df_raw is not None and not df_raw.empty:
        # Limpiar títulos
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        
        # Si faltan columnas, las creamos vacías para que no truene
        for c in cols_necesarias:
            if c not in df_raw.columns:
                df_raw[c] = None
        
        df_man = df_raw[cols_necesarias].copy()
        
        # Limpieza agresiva de datos para los selectores
        for col in ["Tipo", "Categoria", "Metodo_Pago"]:
            df_man[col] = df_man[col].astype(str).str.strip().replace("nan", "")
            
        df_man['Fecha'] = pd.to_datetime(df_man['Fecha'], errors='coerce')
        df_man['Monto'] = pd.to_numeric(df_man['Monto'], errors='coerce').fillna(0.0)
    else:
        # Si la hoja está vacía, creamos un DataFrame con la estructura correcta
        df_man = pd.DataFrame(columns=cols_necesarias)

    disponible_banco = 20000.0

except Exception as e:
    st.error("🚨 Error de conexión. Revisa tus Secrets y que hayas compartido la hoja con el correo del bot.")
    st.exception(e) # Esto mostrará el error real en rojo
    st.stop()

# --- INTERFAZ ---
st.title("📝 Gestor de Gastos")
tab_bitacora, tab_analisis = st.tabs(["⌨️ Registro", "📊 Análisis"])

with tab_bitacora:
    df_editado = st.data_editor(
        df_man,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "Fecha": st.column_config.DateColumn("Fecha", format="DD-MM-YYYY"),
            "Tipo": st.column_config.SelectboxColumn("Tipo", options=["Gasto", "Abono"]),
            "Metodo_Pago": st.column_config.SelectboxColumn("Método", options=["Manual/Físico", "Automático"]),
            "Categoria": st.column_config.SelectboxColumn("Categoría", options=["Servicios", "Supermercado/Despensa", "Alimentos/Restaurantes", "Software/Suscripciones", "Préstamos", "Viajes", "Salud", "Transporte", "Seguros", "Compras/Otros", "Pagos Realizados"]),
            "Monto": st.column_config.NumberColumn("Monto", format="$%.2f")
        },
        key="editor_vFinal"
    )
    
    if st.button("💾 GUARDAR CAMBIOS"):
        try:
            # Quitamos filas vacías antes de guardar
            df_save = df_editado.dropna(subset=['Fecha', 'Monto'], how='any').copy()
            if not df_save.empty:
                df_save['Fecha'] = pd.to_datetime(df_save['Fecha']).dt.strftime('%Y-%m-%d')
                conn.update(data=df_save)
                st.success("¡Guardado!")
                st.rerun()
            else:
                st.warning("No hay datos válidos para guardar.")
        except Exception as e:
            st.error(f"Error al guardar: {e}")


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
