import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Mi Bitácora Pro", layout="wide")

# --- PROCESAMIENTO SEGURO DE LA LLAVE ---
if "connections" in st.secrets and "gsheets" in st.secrets.connections:
    # Creamos el diccionario pero eliminamos el 'type' de los secrets para que no choque
    secret_dict = dict(st.secrets.connections.gsheets)
    if "type" in secret_dict:
        del secret_dict["type"] 
    
    # Limpiamos la llave privada de saltos de línea mal formateados
    if "private_key" in secret_dict:
        secret_dict["private_key"] = secret_dict["private_key"].replace("\\n", "\n")
else:
    st.error("No se encontraron los Secrets configurados en Streamlit Cloud.")
    st.stop()

# --- FUNCIONES DE SOPORTE ---
def a_float(v):
    try:
        if pd.isna(v) or str(v).strip() == "": return 0.0
        return float(str(v).replace(',', '').replace('$', '').replace(' ', '').strip())
    except: return 0.0

# --- CONEXIÓN ---
try:
    # Ahora pasamos los parámetros sin duplicar 'type'
    conn = st.connection("gsheets", type=GSheetsConnection, **secret_dict)
    df_raw = conn.read(ttl=0)
    
    COLUMNAS = ["Fecha", "Concepto", "Monto", "Tipo", "Categoria", "Metodo_Pago"]
    
    if df_raw is not None and not df_raw.empty:
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        for c in COLUMNAS:
            if c not in df_raw.columns: df_raw[c] = ""
        df_man = df_raw[COLUMNAS].copy()
        
        # Limpieza para que coincida con los selectores
        for col in ["Tipo", "Categoria", "Metodo_Pago"]:
            df_man[col] = df_man[col].astype(str).str.strip().replace("nan", "")
        
        df_man['Fecha'] = pd.to_datetime(df_man['Fecha'], errors='coerce')
        df_man['Monto'] = pd.to_numeric(df_man['Monto'], errors='coerce').fillna(0.0)
    else:
        df_man = pd.DataFrame(columns=COLUMNAS)

    disponible_banco = 20000.0 

except Exception as e:
    st.error("Error de conexión. Revisa que el link de la hoja en Secrets sea correcto y que el bot tenga acceso.")
    st.exception(e)
    st.stop()

# --- INTERFAZ (Pestañas) ---
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
        key="editor_final_v8"
    )
    
    if st.button("💾 GUARDAR CAMBIOS"):
        # Solo guardamos si hay datos válidos
        df_save = df_editado.dropna(subset=['Fecha', 'Monto']).copy()
        if not df_save.empty:
            df_save['Fecha'] = df_save['Fecha'].dt.strftime('%Y-%m-%d')
            conn.update(data=df_save)
            st.success("¡Sincronizado con Google Sheets!")
            st.rerun()
        else:
            st.warning("Agregue al menos una fecha y un monto antes de guardar.")

with tab2:
    if not df_man.dropna(subset=['Monto', 'Fecha']).empty:
        # Lógica de gráficas
        df_p = df_man.dropna(subset=['Monto', 'Fecha']).copy()
        df_p['Fecha_DT'] = df_p['Fecha'].dt.normalize()
        
        total_g = df_p[df_p['Tipo'] == 'Gasto']['Monto'].sum()
        total_a = df_p[df_p['Tipo'] == 'Abono']['Monto'].sum()
        saldo_final = disponible_banco - total_g + total_a
        
        # Métricas
        c1, c2, c3 = st.columns(3)
        c1.metric("Límite Base", f"${disponible_banco:,.2f}")
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
