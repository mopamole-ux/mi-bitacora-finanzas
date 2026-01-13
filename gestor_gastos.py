import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Mi Bitácora Pro", layout="wide")

# --- 1. PREPARACIÓN DE CREDENCIALES ---
if "connections" in st.secrets and "gsheets" in st.secrets.connections:
    # Creamos una copia de los secretos
    creds = dict(st.secrets.connections.gsheets)
    
    # Extraemos la URL y la quitamos del diccionario de credenciales
    # para que no cause el error "unexpected keyword argument 'url'"
    target_url = creds.pop("url", None) or creds.pop("spreadsheet", None)
    
    # Quitamos 'type' si existe para que no choque con la clase GSheetsConnection
    if "type" in creds:
        del creds["type"]
    
    # Limpiamos la llave privada
    if "private_key" in creds:
        creds["private_key"] = creds["private_key"].replace("\\n", "\n")
else:
    st.error("No se encontraron los Secrets en Streamlit Cloud.")
    st.stop()

# --- 2. CONEXIÓN ---
try:
    # Conectamos usando solo las credenciales de la cuenta de servicio
    conn = st.connection("gsheets", type=GSheetsConnection, **creds)
    
    # Leemos pasando la URL aquí, que es donde la librería la espera
    df_raw = conn.read(spreadsheet=target_url, ttl=0)
    
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
    st.error("Error al acceder a Google Sheets.")
    st.exception(e)
    st.stop()

# --- 3. INTERFAZ ---
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
        },
        key="editor_final_v9"
    )
    
    if st.button("💾 GUARDAR CAMBIOS"):
        df_save = df_editado.dropna(subset=['Fecha', 'Monto']).copy()
        if not df_save.empty:
            df_save['Fecha'] = df_save['Fecha'].dt.strftime('%Y-%m-%d')
            # Al actualizar también pasamos la URL explícitamente
            conn.update(spreadsheet=target_url, data=df_save)
            st.success("¡Sincronizado!")
            st.rerun()

with tab2:
    if not df_man.dropna(subset=['Monto']).empty:
        df_p = df_man.dropna(subset=['Monto', 'Fecha']).copy()
        df_p['Fecha_DT'] = df_p['Fecha'].dt.normalize()
        total_g = df_p[df_p['Tipo'] == 'Gasto']['Monto'].sum()
        saldo_final = disponible_banco - total_g + df_p[df_p['Tipo'] == 'Abono']['Monto'].sum()

        st.metric("Disponible Real", f"${saldo_final:,.2f}", delta=f"-{total_g:,.2f}")
        
        diario = df_p.groupby('Fecha_DT').apply(lambda x: x[x['Tipo']=='Abono']['Monto'].sum() - x[x['Tipo']=='Gasto']['Monto'].sum()).reset_index(name='Efecto')
        diario['Saldo'] = disponible_banco + diario['Efecto'].cumsum()
        
        fig = px.area(diario, x='Fecha_DT', y='Saldo', line_shape="hv", title="Flujo de Caja")
        st.plotly_chart(fig, use_container_width=True)
