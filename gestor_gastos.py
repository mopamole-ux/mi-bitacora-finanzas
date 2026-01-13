import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import time

# 1. CONFIGURACIÓN INICIAL
st.set_page_config(page_title="Bitácora de Gorditos 🍔", layout="wide")

URL_BANNER = "https://lh3.googleusercontent.com/d/11Rdr2cVYIypLjmSp9jssuvoOxQ-kI1IZ"
st.image(URL_BANNER, width='stretch')
st.title("🍕 Bitácora de Gorditos 🍔")

# --- 2. CONEXIÓN ---
conn = st.connection("gsheets", type=GSheetsConnection)

COLUMNAS_MAESTRAS = [
    "Fecha", "Concepto", "Monto", "Tipo", 
    "Categoria", "Tipo_Pago", "Metodo_Pago", "Responsable"
]

# --- 3. LECTURA DE DATOS ---
try:
    # Leer Configuración
    df_config = conn.read(worksheet="Config", ttl=300)
    saldo_base_valor = float(df_config.iloc[0, 0]) if not df_config.empty else 20000.0
    limite_atracon = float(df_config.iloc[0, 1]) if len(df_config.columns) > 1 else 15000.0

    df_raw = conn.read(ttl=300)
    
    if df_raw is not None and not df_raw.empty:
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        for col in COLUMNAS_MAESTRAS:
            if col not in df_raw.columns: df_raw[col] = ""
        
        df_man = df_raw[COLUMNAS_MAESTRAS].copy().reset_index(drop=True)
        df_man['Fecha'] = pd.to_datetime(df_man['Fecha'], errors='coerce')
        df_man['Monto'] = pd.to_numeric(df_man['Monto'], errors='coerce').fillna(0.0)
    else:
        df_man = pd.DataFrame(columns=COLUMNAS_MAESTRAS)

except Exception as e:
    if "429" in str(e):
        st.error("🚦 ¡Google saturado! Espera 60 segundos.")
        st.stop()
    else:
        st.error(f"Error: {e}")
        st.stop()

# --- 4. SIDEBAR CON TERMÓMETRO ---
with st.sidebar:
    st.header("⚙️ Configuración")
    n_saldo = st.number_input("💰 Saldo Base", value=int(saldo_base_valor), step=100)
    n_limite = st.number_input("⚠️ Límite Gasto", value=int(limite_atracon), step=500)
    
    if st.button("🍳 Guardar Config"):
        conn.update(worksheet="Config", data=pd.DataFrame({"SaldoBase": [n_saldo], "Limite": [n_limite]}))
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.subheader("🌡️ Límite de Gasto")
    # Cálculo de gastos totales para el termómetro
    gastos_totales = df_man[df_man['Tipo'] == 'Gasto']['Monto'].sum()
    porcentaje = min(gastos_totales / n_limite, 1.0) if n_limite > 0 else 0
    
    if gastos_totales > n_limite:
        st.error(f"🚨 ¡LIMITE SUPERADO! Llevan ${int(gastos_totales):,}")
    else:
        st.progress(porcentaje)
        st.info(f"Gastado: ${int(gastos_totales):,} / ${int(n_limite):,}")

# --- 5. REGISTRO ---
tab_reg, tab_ana = st.tabs(["📝 Registro", "📊 Análisis"])

with tab_reg:
    st.markdown("### 🛒 Añade tus gastos")
    
    df_editado = st.data_editor(
        df_man,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "Fecha": st.column_config.DateColumn("📅 Fecha", format="DD/MM/YYYY"),
            "Monto": st.column_config.NumberColumn("💵 Monto", format="$%d"),
            "Tipo": st.column_config.SelectboxColumn("✨ Tipo", options=["Gasto", "Abono"]),
            "Categoria": st.column_config.SelectboxColumn("📂 Categoría", options=["Super", "Software", "Suscripciones", "Restaurantes", "Servicios", "Salud", "Préstamos", "Viajes", "Otros"]),
            "Tipo_Pago": st.column_config.SelectboxColumn("📂 Modo Pago", options=["Manual", "Automático"]),
            "Metodo_Pago": st.column_config.SelectboxColumn("📂 Método Pago", options=["TDC", "TDD", "Efectivo", "Transferencia"]),
            "Responsable": st.column_config.SelectboxColumn("👤 Responsable", options=["Gordify", "Mon"])
        },
        key="editor_sin_id_manual_v1"
    )

    # Totales rápidos
    g_act = df_editado[df_editado['Tipo'] == 'Gasto']['Monto'].sum()
    a_act = df_editado[df_editado['Tipo'] == 'Abono']['Monto'].sum()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("🔴 Gastos", f"${int(g_act):,}")
    c2.metric("🟢 Abonos", f"${int(a_act):,}")
    c3.metric("💰 NETO PROYECTADO", f"${int(n_saldo + a_act - g_act):,}")

    if st.button("💾 GUARDAR TODO"):
        df_save = df_editado.dropna(subset=['Fecha', 'Concepto'], how='all').copy()
        if not df_save.empty:
            df_save['Fecha'] = pd.to_datetime(df_save['Fecha']).dt.strftime('%Y-%m-%d')
            df_final = df_save[COLUMNAS_MAESTRAS]
            try:
                conn.update(data=df_final)
                st.cache_data.clear()
                st.success("✅ ¡Guardado con éxito!")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

with tab_ana:
    # Filtramos datos válidos para las gráficas
    df_p = df_man.dropna(subset=['Monto', 'Fecha']).copy()
    
    if not df_p.empty:
        df_p['Fecha_DT'] = pd.to_datetime(df_p['Fecha']).dt.normalize()
        tot_g = df_p[df_p['Tipo'] == 'Gasto']['Monto'].sum()
        tot_a = df_p[df_p['Tipo'] == 'Abono']['Monto'].sum()
        disponible = n_saldo + tot_a - tot_g

        st.subheader("🍴 Resumen Financiero")
        m1, m2, m3 = st.columns(3)
        m1.metric("💰 Saldo Inicial", f"${int(n_saldo):,}")
        m2.metric("🍗 Total Gastado", f"${int(tot_g):,}")
        m3.metric("🥗 Disponible Real", f"${int(disponible):,}")

        # --- Gráfica de Línea (Saldo en el tiempo) ---
        st.markdown("### 📈 Trayectoria del Saldo")
        # Calculamos el flujo diario: Abonos (+) Gastos (-)
        df_p['Valor_Neto'] = df_p.apply(lambda x: x['Monto'] if x['Tipo'] == 'Abono' else -x['Monto'], axis=1)
        diario = df_p.groupby('Fecha_DT')['Valor_Neto'].sum().reset_index().sort_values('Fecha_DT')
        diario['Saldo_Acumulado'] = n_saldo + diario['Valor_Neto'].cumsum()

        fig_area = px.area(diario, x='Fecha_DT', y='Saldo_Acumulado', line_shape="hv", markers=True)
        fig_area.update_traces(line_color='#FF5733', fillcolor='rgba(255, 87, 51, 0.2)')
        fig_area.update_xaxes(tickformat="%d/%m/%y", title="Fecha")
        st.plotly_chart(fig_area, width='stretch')

        # --- Gráficas de Reparto ---
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.markdown("### 👤 Gastos por Persona")
            gastos_persona = df_p[df_p['Tipo'] == 'Gasto'].groupby('Responsable')['Monto'].sum().reset_index()
            fig_pie = px.pie(gastos_persona, values='Monto', names='Responsable', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_pie, width='stretch')

        with col_right:
            st.markdown("### 📂 Gastos por Categoría")
            gastos_cat = df_p[df_p['Tipo'] == 'Gasto'].groupby('Categoria')['Monto'].sum().reset_index().sort_values('Monto')
            fig_bar = px.bar(gastos_cat, x='Monto', y='Categoria', orientation='h', color='Monto', color_continuous_scale='OrRd')
            st.plotly_chart(fig_bar, width='stretch')
    else:
        st.info("No hay datos suficientes para generar el análisis.")
