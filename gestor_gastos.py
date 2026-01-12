import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Mi Bitácora Pro", layout="wide")
st.title("📝 Gestor de Gastos en la Nube")

# 1. CONEXIÓN A GOOGLE SHEETS
# Configura el link en Settings -> Secrets de Streamlit Cloud
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Leemos la hoja (si está vacía, creamos un DataFrame base)
    df_original = conn.read()
except:
    st.error("⚠️ Error de conexión. Revisa el link en Secrets.")
    st.stop()

# Categorías y Métodos
CATEGORIAS = ["Supermercado/Despensa", "Software/Suscripciones", "Alimentos/Restaurantes", "Servicios/Seguros", "Compras/Otros", "Pagos Realizados"]
METODOS = ["Manual/Físico", "Automático"]

tab_bitacora, tab_analisis = st.tabs(["⌨️ Registro (iPad/Web)", "📊 Análisis Profundo"])

with tab_bitacora:
    st.subheader("Entrada de Movimientos")
    
    # Editor de datos vinculado a Google Sheets
    df_editado = st.data_editor(
        df_original,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "Fecha": st.column_config.DateColumn("Fecha", format="DD-MM-YYYY", required=True),
            "Tipo": st.column_config.SelectboxColumn("Tipo", options=["Gasto", "Abono"], required=True),
            "Metodo_Pago": st.column_config.SelectboxColumn("Método", options=METODOS, required=True),
            "Categoria": st.column_config.SelectboxColumn("Categoría", options=CATEGORIAS, required=True),
            "Monto": st.column_config.NumberColumn("Monto", format="$%.2f", min_value=0.0)
        },
        key="editor_gsheets"
    )
    
    # Totales rápidos
    if not df_editado.empty:
        tg = df_editado[df_editado['Tipo'] == 'Gasto']['Monto'].sum()
        ta = df_editado[df_editado['Tipo'] == 'Abono']['Monto'].sum()
        st.info(f"💰 Total Registrado: **Gastos ${tg:,.2f}** | **Abonos ${ta:,.2f}**")

    if st.button("💾 GUARDAR EN GOOGLE DRIVE"):
        # Limpiar filas vacías antes de subir
        df_save = df_editado.dropna(subset=['Fecha', 'Monto'], how='any')
        # Convertir fecha a string para que Google Sheets no se confunda
        df_save['Fecha'] = pd.to_datetime(df_save['Fecha']).dt.strftime('%Y-%m-%d')
        conn.update(data=df_save)
        st.success("¡Sincronizado con Google Sheets!")
        st.rerun()

with tab_analisis:
    if not df_original.empty:
        # Procesamiento para gráficas (Saldo base manual de ejemplo $20,000)
        disponible_banco = 20000.0 
        
        df_p = df_original.copy()
        df_p['Fecha'] = pd.to_datetime(df_p['Fecha'])
        df_p = df_p.sort_values('Fecha')
        
        total_g = df_p[df_p['Tipo'] == 'Gasto']['Monto'].sum()
        saldo_final = disponible_banco - total_g + df_p[df_p['Tipo'] == 'Abono']['Monto'].sum()

        c1, c2 = st.columns([2, 1])
        c1.metric("Disponible Estimado", f"${saldo_final:,.2f}", delta=f"-{total_g:,.2f}")
        
        # Gráfica de Escalera
        df_p['Efecto'] = df_p.apply(lambda r: -r['Monto'] if r['Tipo'] == 'Gasto' else r['Monto'], axis=1)
        df_p['Saldo_Proyectado'] = disponible_banco + df_p['Efecto'].cumsum()
        
        fig = px.area(df_p, x='Fecha', y='Saldo_Proyectado', line_shape="hv", title="Trayectoria de Crédito")
        fig.update_xaxes(dtick="D1", tickformat="%d %b")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No hay datos en Google Sheets para mostrar gráficas.")
