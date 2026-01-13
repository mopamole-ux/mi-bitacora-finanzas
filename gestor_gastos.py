import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="Mi Bitácora Pro", layout="wide")

# --- 1. CONFIGURACIÓN DE SEGURIDAD ---
if "connections" in st.secrets and "gsheets" in st.secrets.connections:
    secret_dict = dict(st.secrets.connections.gsheets)
    if "private_key" in secret_dict:
        secret_dict["private_key"] = secret_dict["private_key"].replace("\\n", "\n")
else:
    st.error("No se encontraron los Secrets configurados.")
    st.stop()

# --- FUNCIONES DE SOPORTE ---
def a_float(v):
    try:
        if pd.isna(v) or str(v).strip() == "": return 0.0
        clean_v = str(v).replace(',', '').replace('$', '').replace(' ', '').strip()
        return float(clean_v)
    except: return 0.0

# --- 2. CONEXIÓN Y LECTURA ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    # ttl=0 es vital para que al guardar y recargar lea los datos NUEVOS
    df_man = conn.read(ttl=0)
    
    COLUMNAS = ["Fecha", "Concepto", "Monto", "Tipo", "Categoria", "Metodo_Pago"]
    
    if df_man is not None and not df_man.empty:
        df_man.columns = [str(c).strip() for c in df_man.columns]
        for c in COLUMNAS:
            if c not in df_man.columns: df_man[c] = None
        for col in ["Tipo", "Categoria", "Metodo_Pago"]:
            df_man[col] = df_man[col].astype(str).str.strip().replace("nan", "")
        df_man['Fecha'] = pd.to_datetime(df_man['Fecha'], errors='coerce')
        df_man['Monto'] = df_man['Monto'].apply(a_float)
    else:
        df_man = pd.DataFrame(columns=COLUMNAS)

except Exception as e:
    st.error(f"Error de conexión: {e}")
    st.stop()

# --- SIDEBAR: SALDO BASE ---
with st.sidebar:
    st.header("⚙️ Configuración")
    disponible_banco = st.number_input("💰 Saldo Base Inicial", value=20000.0, step=100.0)
    st.caption("Este valor es el punto de partida de tu dinero.")

# --- TABS ---
tab_bitacora, tab_analisis = st.tabs(["⌨️ Registro Manual", "📊 Análisis de Gastos"])

with tab_bitacora:
    st.subheader("Entrada de Movimientos")
    
    df_editado = st.data_editor(
        df_man[COLUMNAS],
        num_rows="dynamic",
        width="stretch",
        column_config={
            "Fecha": st.column_config.DateColumn("Fecha", format="DD-MM-YYYY", required=True),
            "Tipo": st.column_config.SelectboxColumn("Tipo", options=["Gasto", "Abono"], required=True),
            "Metodo_Pago": st.column_config.SelectboxColumn("Método", options=["Manual/Físico", "Automático"], required=True),
            "Categoria": st.column_config.SelectboxColumn("Categoría", options=["Servicios", "Super", "Alimentos", "Restaurantes", "Software, "Suscripciones", "Viajes, "Salud", "Préstamos", "Pago TDC", "Pagos Sardina", "Otros"], required=True),
            "Monto": st.column_config.NumberColumn("Monto", format="$%.2f", min_value=0.0)
        },
        key="editor_nube_v_final"
    )
    
    # --- CÁLCULO DE TOTALES EN PANTALLA ---
    gastos_temp = df_editado[df_editado['Tipo'] == 'Gasto']['Monto'].sum()
    abonos_temp = df_editado[df_editado['Tipo'] == 'Abono']['Monto'].sum()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Gastos (en tabla)", f"${gastos_temp:,.2f}")
    c2.metric("Total Abonos (en tabla)", f"${abonos_temp:,.2f}")
    c3.metric("Neto Actual", f"${abonos_temp - gastos_temp:,.2f}")

    if st.button("💾 GUARDAR CAMBIOS PERMANENTES"):
        df_save = df_editado.dropna(subset=['Fecha', 'Monto'], how='any').copy()
        
        if not df_save.empty:
            # FORMATO DE FECHA PARA GOOGLE SHEETS
            df_save['Fecha'] = pd.to_datetime(df_save['Fecha']).dt.strftime('%Y-%m-%d')
            
            try:
                conn.update(data=df_save)
                # LIMPIEZA DE CACHÉ: Esto es lo que faltaba para que se "vea" el cambio
                st.cache_data.clear()
                st.success("✅ ¡Datos sincronizados con Google Sheets!")
                st.balloons()
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")
        else:
            st.warning("Agrega datos válidos antes de guardar.")

with tab_analisis:
    if not df_man.dropna(subset=['Monto', 'Fecha']).empty:
        df_p = df_man.dropna(subset=['Monto', 'Fecha']).copy()
        df_p['Fecha_DT'] = df_p['Fecha'].dt.normalize()
        
        total_g = df_p[df_p['Tipo'] == 'Gasto']['Monto'].sum()
        total_a = df_p[df_p['Tipo'] == 'Abono']['Monto'].sum()
        saldo_final = disponible_banco - total_g + total_a

        # Resumen visual
        st.subheader("📉 Estado de Cuenta Real")
        m1, m2, m3 = st.columns(3)
        m1.metric("Saldo Inicial", f"${disponible_banco:,.2f}")
        m2.metric("Total Gastos", f"${total_g:,.2f}", delta_color="inverse")
        m3.metric("Disponible Hoy", f"${saldo_final:,.2f}")

        # Gráfica de Escalera
        st.divider()
        diario = df_p.groupby('Fecha_DT').apply(lambda x: (x[x['Tipo']=='Abono']['Monto'].sum() - x[x['Tipo']=='Gasto']['Monto'].sum())).reset_index(name='Efecto')
        diario = diario.sort_values('Fecha_DT')
        diario['Saldo_Proyectado'] = disponible_banco + diario['Efecto'].cumsum()

        fig_line = px.area(diario, x='Fecha_DT', y='Saldo_Proyectado', 
                          line_shape="hv", markers=True, title="Evolución del Dinero")
        fig_line.update_xaxes(nticks=10, tickformat="%d %b")
        fig_line.update_traces(line_color='#28A745', fillcolor='rgba(40, 167, 69, 0.2)')
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("No hay datos en la nube para analizar.")
