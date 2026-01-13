import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Mi Bitácora Pro", layout="wide")

# --- CONEXIÓN ---
try:
    # Dejamos que Streamlit maneje la conexión automáticamente desde los secrets
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_raw = conn.read(ttl=0)
    
    COLUMNAS = ["Fecha", "Concepto", "Monto", "Tipo", "Categoria", "Metodo_Pago"]
    
    if df_raw is not None and not df_raw.empty:
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        for c in COLUMNAS:
            if c not in df_raw.columns: df_raw[c] = ""
        df_man = df_raw[COLUMNAS].copy()
        
        # Limpiar datos para que coincidan con selectores
        for col in ["Tipo", "Categoria", "Metodo_Pago"]:
            df_man[col] = df_man[col].astype(str).str.strip().replace("nan", "")
        
        df_man['Fecha'] = pd.to_datetime(df_man['Fecha'], errors='coerce')
        df_man['Monto'] = pd.to_numeric(df_man['Monto'], errors='coerce').fillna(0.0)
    else:
        df_man = pd.DataFrame(columns=COLUMNAS)

    disponible_banco = 20000.0 

except Exception as e:
    st.error("🚨 Error de conexión. Revisa que hayas compartido la hoja con el correo del bot.")
    st.exception(e) # Esto mostrará el error real si persiste
    st.stop()

# --- INTERFAZ ---
st.title("📝 Mi Bitácora Financiera")
tab1, tab2 = st.tabs(["⌨️ Registro", "📊 Análisis Profundo"])

with tab1:
    st.subheader("Entrada de Movimientos")
    df_editado = st.data_editor(
        df_man, num_rows="dynamic", width="stretch",
        column_config={
            "Fecha": st.column_config.DateColumn("Fecha", format="DD-MM-YYYY"),
            "Tipo": st.column_config.SelectboxColumn("Tipo", options=["Gasto", "Abono"]),
            "Metodo_Pago": st.column_config.SelectboxColumn("Método", options=["Manual/Físico", "Automático"]),
            "Categoria": st.column_config.SelectboxColumn("Categoría", options=["Servicios", "Supermercado/Despensa", "Alimentos/Restaurantes", "Software/Suscripciones", "Otros"]),
            "Monto": st.column_config.NumberColumn("Monto", format="$%.2f")
        },
        key="editor_vFinal_OK"
    )
    
    if st.button("💾 GUARDAR CAMBIOS"):
        df_save = df_editado.dropna(subset=['Fecha', 'Monto']).copy()
        if not df_save.empty:
            df_save['Fecha'] = df_save['Fecha'].dt.strftime('%Y-%m-%d')
            conn.update(data=df_save)
            st.success("¡Sincronizado con Google Sheets!")
            st.rerun()

with tab2:
    if not df_man.dropna(subset=['Monto']).empty:
        df_p = df_man.dropna(subset=['Monto', 'Fecha']).copy()
        df_p['Fecha_DT'] = df_p['Fecha'].dt.normalize()
        
        total_g = df_p[df_p['Tipo'] == 'Gasto']['Monto'].sum()
        total_a = df_p[df_p['Tipo'] == 'Abono']['Monto'].sum()
        saldo_final = disponible_banco - total_g + total_a

        c1, c2, c3 = st.columns(3)
        c1.metric("Límite", f"${disponible_banco:,.2f}")
        c2.metric("Gastos", f"${total_g:,.2f}", delta_color="inverse")
        c3.metric("Disponible", f"${saldo_final:,.2f}")

        # Gráfica de Escalera
        st.divider()
        diario = df_p.groupby('Fecha_DT').apply(lambda x: x[x['Tipo']=='Abono']['Monto'].sum() - x[x['Tipo']=='Gasto']['Monto'].sum()).reset_index(name='Efecto')
        diario = diario.sort_values('Fecha_DT')
        diario['Saldo'] = disponible_banco + diario['Efecto'].cumsum()

        fig = px.area(diario, x='Fecha_DT', y='Saldo', line_shape="hv", title="Trayectoria del Disponible")
        fig.update_traces(line_color='#28A745', fillcolor='rgba(40, 167, 69, 0.2)')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sin datos para analizar.")
