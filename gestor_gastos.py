import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime

# 1. CONFIGURACIÓN DE PÁGINA (Solo una vez al principio)
st.set_page_config(page_title="Bitácora de Gorditos 🍔", layout="wide")

# --- BANNER Y ESTILOS ---
URL_BANNER = "https://lh3.googleusercontent.com/d/11Rdr2cVYIypLjmSp9jssuvoOxQ-kI1IZ"
st.image(URL_BANNER, use_container_width=True)

st.title("🍕 Bitácora de Gorditos 🍔")
st.markdown("""
    <style>
    .main { background-color: #fffaf0; }
    
    img {
        max-height: 300px;
        width: 100%;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. SEGURIDAD Y CONEXIÓN ---
if "connections" in st.secrets and "gsheets" in st.secrets.connections:
    secret_dict = dict(st.secrets.connections.gsheets)
    if "private_key" in secret_dict:
        secret_dict["private_key"] = secret_dict["private_key"].replace("\\n", "\n")
    conn = st.connection("gsheets", type=GSheetsConnection)
else:
    st.error("¡Faltan las credenciales!")
    st.stop()

# --- 3. LECTURA DE DATOS ---
try:
    # Leer Config (Saldo y Límite)
    try:
        df_config = conn.read(worksheet="Config", ttl=0)
        saldo_base_valor = float(df_config.iloc[0, 0]) if not df_config.empty else 20000.0
        limite_atracón = float(df_config.iloc[0, 1]) if len(df_config.columns) > 1 else 15000.0
    except:
        saldo_base_valor, limite_atracón = 20000.0, 15000.0

    # Leer Movimientos
    df_man = conn.read(ttl=0)
    COLUMNAS_MAESTRAS = ["Fecha", "Concepto", "Monto", "Tipo", "Categoria", "Tipo_Pago", "Metodo_Pago", "Responsable"]
    
    if df_man is not None and not df_man.empty:
        df_man.columns = [str(c).strip() for c in df_man.columns]
        for c in COLUMNAS_MAESTRAS:
            if c not in df_man.columns: df_man[c] = ""
        df_man = df_man[COLUMNAS_MAESTRAS]
        df_man['Fecha'] = pd.to_datetime(df_man['Fecha'], errors='coerce')
        df_man['Monto'] = pd.to_numeric(df_man['Monto'], errors='coerce').fillna(0.0)
    else:
        df_man = pd.DataFrame(columns=COLUMNAS_MAESTRAS)

except Exception as e:
    st.error(f"Error de conexión: {e}")
    st.stop()

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuración")
    nuevo_saldo = st.number_input("💰 Saldo Base", value=int(saldo_base_valor), step=100, format="%d")
    nuevo_limite = st.number_input("⚠️ Límite de Atracón", value=int(limite_atracón), step=500, format="%d")
    
    if st.button("Guardar Configuración"):
        df_conf_save = pd.DataFrame({"SaldoBase": [nuevo_saldo], "Limite": [nuevo_limite]})
        conn.update(worksheet="Config", data=df_conf_save)
        st.cache_data.clear()
        st.success("¡Configuración guardada!")
        st.rerun()

    st.divider()
    st.subheader("🌡️ Termómetro")
    gastos_totales_db = df_man[df_man['Tipo'] == 'Gasto']['Monto'].sum()
    progreso = min(gastos_totales_db / nuevo_limite, 1.0) if nuevo_limite > 0 else 0
    st.progress(progreso)
    st.write(f"Llevan ${int(gastos_totales_db):,} de ${int(nuevo_limite):,}")

# --- 5. INTERFAZ DE TABS ---
tab_registro, tab_analisis = st.tabs(["⌨️ Registro", "📊 Análisis"])

with tab_registro:
    st.subheader("🛒 Registro de Movimientos")
    df_editado = st.data_editor(
        df_man,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "Fecha": st.column_config.DateColumn("📅 Fecha", format="DD/MM/YYYY"),
            "Tipo": st.column_config.SelectboxColumn("✨ Tipo", options=["Gasto", "Abono"]),
            "Monto": st.column_config.NumberColumn("💵 Monto", format="$%d"),
            "Categoria": st.column_config.SelectboxColumn("📂 Categoría", options=["Super", "Software", "Suscripciones", "Restaurantes", "Servicios", "Salud", "Préstamos", "Pago TDC", "Salarios", "Viajes", "Otros"]),
            "Tipo_Pago": st.column_config.SelectboxColumn("🪙 Tipo pago", options=["Manual", "Automático"]),
            "Metodo_Pago": st.column_config.SelectboxColumn("💳 Forma pago", options=["TDC", "Efectivo", "TDD"]),
            "Responsable": st.column_config.SelectboxColumn("👤 Responsable", options=["Gordify", "Mon"])
        },
        key="editor_final_v1"
    )
    
    # Totales en tiempo real sobre lo que está en el editor
    g_actual = df_editado[df_editado['Tipo'] == 'Gasto']['Monto'].sum()
    a_actual = df_editado[df_editado['Tipo'] == 'Abono']['Monto'].sum()
    disponible_final = nuevo_saldo + a_actual - g_actual
    
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("🔴 Gastos", f"${int(g_actual):,}")
    c2.metric("🟢 Abonos", f"${int(a_actual):,}")
    c3.metric("💰 NETO PROYECTADO", f"${int(disponible_final):,}", delta=f"{int(a_actual - g_actual):,}")
    st.markdown("---")

    if st.button("💾 GUARDAR TODO"):
        df_save = df_editado.dropna(subset=['Fecha', 'Concepto']).copy()
        if not df_save.empty:
            df_save['Fecha'] = pd.to_datetime(df_save['Fecha']).dt.strftime('%Y-%m-%d')
            try:
                conn.update(data=df_save[COLUMNAS_MAESTRAS])
                st.cache_data.clear()
                st.success("✅ ¡Guardado en la nube!")
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

with tab_analisis:
    df_p = df_man.dropna(subset=['Monto', 'Fecha']).copy()
    if not df_p.empty:
        df_p['Fecha_DT'] = pd.to_datetime(df_p['Fecha']).dt.normalize()
        tot_g = df_p[df_p['Tipo'] == 'Gasto']['Monto'].sum()
        tot_a = df_p[df_p['Tipo'] == 'Abono']['Monto'].sum()
        saldo_global = nuevo_saldo - tot_g + tot_a

        st.subheader("🍴 Estado de Nuestra Fortuna")
        m1, m2, m3 = st.columns(3)
        m1.metric("💰 Fondo Inicial", f"${int(nuevo_saldo):,}")
        m2.metric("🍗 Gastado Total", f"${int(tot_g):,}", delta_color="inverse")
        m3.metric("🥗 Disponible Real", f"${int(saldo_global):,}")

        # Gráfica de Escalera
        diario = df_p.groupby('Fecha_DT').apply(lambda x: (x[x['Tipo']=='Abono']['Monto'].sum() - x[x['Tipo']=='Gasto']['Monto'].sum())).reset_index(name='Efecto')
        diario = diario.sort_values('Fecha_DT')
        diario['Saldo_Proyectado'] = nuevo_saldo + diario['Efecto'].cumsum()

        fig_line = px.area(diario, x='Fecha_DT', y='Saldo_Proyectado', line_shape="hv", markers=True)
        fig_line.update_traces(line_color='#FF5733', fillcolor='rgba(255, 87, 51, 0.2)')
        st.plotly_chart(fig_line, use_container_width=True)

        st.subheader("🍕 Gastos por Categoría")
        df_cat = df_p[df_p['Tipo'] == 'Gasto'].groupby('Categoria')['Monto'].sum().reset_index()
        fig_cat = px.bar(df_cat.sort_values('Monto'), x='Monto', y='Categoria', orientation='h', color='Monto', color_continuous_scale='OrRd')
        st.plotly_chart(fig_cat, use_container_width=True)
    else:
        st.info("No hay datos para analizar.")
