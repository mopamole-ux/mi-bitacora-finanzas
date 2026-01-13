  import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="Bitácora Comelones 🍔", layout="wide")
st.title("🍕 El Festín de los Comelones 🌮")

# --- 1. CONFIGURACIÓN DE SEGURIDAD ---
if "connections" in st.secrets and "gsheets" in st.secrets.connections:
    secret_dict = dict(st.secrets.connections.gsheets)
    if "private_key" in secret_dict:
        secret_dict["private_key"] = secret_dict["private_key"].replace("\\n", "\n")
else:
    st.error("¡Faltan las credenciales en Secrets!")
    st.stop()

# --- 2. CONEXIÓN ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Intentar leer Saldo Base de la pestaña 'Config'
    try:
        df_config = conn.read(worksheet="Config", ttl=0)
        if not df_config.empty:
            saldo_base_valor = float(df_config.iloc[0, 0])
        else:
            saldo_base_valor = 20000.0
    except:
        st.warning("⚠️ No encontré la pestaña 'Config'. Usando saldo temporal.")
        saldo_base_valor = 20000.0

    # Leer Movimientos Principales
    df_man = conn.read(ttl=0)
    COLUMNAS = ["Fecha", "Concepto", "Monto", "Tipo", "Categoria", "Metodo_Pago"]
    
    if df_man is not None and not df_man.empty:
        df_man.columns = [str(c).strip() for c in df_man.columns]
        for c in COLUMNAS:
            if c not in df_man.columns: df_man[c] = None
        df_man['Fecha'] = pd.to_datetime(df_man['Fecha'], errors='coerce')
        df_man['Monto'] = pd.to_numeric(df_man['Monto'], errors='coerce').fillna(0.0)
    else:
        df_man = pd.DataFrame(columns=COLUMNAS)

except Exception as e:
    st.error(f"Error de conexión: {e}")
    st.stop()

# --- SIDEBAR: CONFIGURACIÓN DIVERTIDA ---
with st.sidebar:
    st.header("👨‍🍳 El Chef del Dinero")
    
    # --- AJUSTE SOLICITADO: Salto de 100 en 100 y sin decimales (%d) ---
    nuevo_saldo = st.number_input(
        "💰 Saldo Inicial", 
        value=int(saldo_base_valor), 
        step=100, 
        format="%d"
    )
    
    if st.button("🍳 Guardar Saldo Base"):
        df_conf_save = pd.DataFrame({"SaldoBase": [nuevo_saldo]})
        try:
            conn.update(worksheet="Config", data=df_conf_save)
            st.success("¡Caja Registradora actualizada!")
            st.cache_data.clear()
            st.rerun()
        except:
            st.error("¿Creaste la pestaña 'Config' en tu Google Sheets?")

# --- TABS ---
tab_registro, tab_analisis = st.tabs(["📝 Anotar Pedido", "📊 ¿Cuánto nos comimos?"])

with tab_registro:
    st.subheader("🛒 Registro de Atracos Culinarios")
    
    df_editado = st.data_editor(
        df_man[COLUMNAS],
        num_rows="dynamic",
        width="stretch",
        column_config={
            "Fecha": st.column_config.DateColumn("Fecha"),
            "Tipo": st.column_config.SelectboxColumn("Tipo", options=["Gasto", "Abono"]),
            "Categoria": st.column_config.SelectboxColumn("Categoría", options=["Super", "Software/Suscripciones", "Alimentos/Restaurantes", "Servicios", "Viajes", "Salud", "Transporte", "Otros"]),
            "Monto": st.column_config.NumberColumn("Monto", format="$%.2f")
        },
        key="editor_comelones"
    )
    
    if st.button("💾 GUARDAR TODO"):
        df_save = df_editado.dropna(subset=['Fecha', 'Monto']).copy()
        if not df_save.empty:
            df_save['Fecha'] = pd.to_datetime(df_save['Fecha']).dt.strftime('%Y-%m-%d')
            conn.update(data=df_save)
            st.cache_data.clear()
            st.success("¡Sincronizado!")
            st.rerun()

with tab_atracos if 'tab_atracos' in locals() else tab_analisis:
    df_p = df_man.dropna(subset=['Monto', 'Fecha']).copy()
    
    if not df_p.empty:
        df_p['Fecha_DT'] = pd.to_datetime(df_p['Fecha']).dt.normalize()
        tot_g = df_p[df_p['Tipo'] == 'Gasto']['Monto'].sum()
        tot_a = df_p[df_p['Tipo'] == 'Abono']['Monto'].sum()
        disponible_final = nuevo_saldo - tot_g + tot_a

        # RESUMEN PARA LOS DOS COMELONES
        st.subheader("🍴 Estado de la Panza (y la Cartera)")
        m1, m2, m3 = st.columns(3)
        m1.metric("Fondo de Comida", f"${nuevo_saldo:,.2f}")
        m2.metric("🍗 Gastado", f"${tot_g:,.2f}", delta_color="inverse")
        m3.metric("🥗 Nos queda", f"${disponible_final:,.2f}")

        # GRÁFICA DE ESCALERA
        diario = df_p.groupby('Fecha_DT').apply(lambda x: (x[x['Tipo']=='Abono']['Monto'].sum() - x[x['Tipo']=='Gasto']['Monto'].sum())).reset_index(name='Efecto')
        diario = diario.sort_values('Fecha_DT')
        diario['Saldo_Proyectado'] = nuevo_saldo + diario['Efecto'].cumsum()

        fig = px.area(diario, x='Fecha_DT', y='Saldo_Proyectado', line_shape="hv", markers=True, 
                      title="🎢 Montaña Rusa del Dinero")
        fig.update_traces(line_color='#FF5733', fillcolor='rgba(255, 87, 51, 0.2)')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("¡Anota algo arriba para que yo pueda trabajar! 👨‍🍳")
