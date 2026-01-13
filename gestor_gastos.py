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

# Añadimos ID al inicio de la lista
COLUMNAS_MAESTRAS = [
    "ID", "Fecha", "Concepto", "Monto", "Tipo", 
    "Categoria", "Tipo_Pago", "Metodo_Pago", "Responsable"
]

# --- 3. LECTURA DE DATOS CON CONTROL DE CUOTA ---
try:
    # Leer Configuración (TTL de 5 min para evitar Error 429)
    df_config = conn.read(worksheet="Config", ttl=300)
    saldo_base_valor = float(df_config.iloc[0, 0]) if not df_config.empty else 20000.0
    limite_atracon = float(df_config.iloc[0, 1]) if len(df_config.columns) > 1 else 15000.0

    df_raw = conn.read(ttl=300)
    
    if df_raw is not None and not df_raw.empty:
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        for col in COLUMNAS_MAESTRAS:
            if col not in df_raw.columns: df_raw[col] = ""
        
        df_man = df_raw[COLUMNAS_MAESTRAS].copy()
        df_man['ID'] = pd.to_numeric(df_man['ID'], errors='coerce')
        df_man['Fecha'] = pd.to_datetime(df_man['Fecha'], errors='coerce')
        df_man['Monto'] = pd.to_numeric(df_man['Monto'], errors='coerce').fillna(0.0)
    else:
        df_man = pd.DataFrame(columns=COLUMNAS_MAESTRAS)

except Exception as e:
    if "429" in str(e):
        st.error("🚦 ¡Google pide un respiro! Espera 60 segundos.")
        st.stop()
    else:
        st.error(f"Error: {e}")
        st.stop()

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuración")
    n_saldo = st.number_input("💰 Saldo Base", value=int(saldo_base_valor), step=100)
    n_limite = st.number_input("⚠️ Límite Gasto", value=int(limite_atracon), step=500)
    
    if st.button("🍳 Guardar Config"):
        conn.update(worksheet="Config", data=pd.DataFrame({"SaldoBase": [n_saldo], "Limite": [n_limite]}))
        st.cache_data.clear()
        st.rerun()

# --- 5. REGISTRO ---
tab_reg, tab_analisis = st.tabs(["📝 Registro", "📊 Análisis"])

with tab_reg:
    st.info("💡 El ID se asignará automáticamente al presionar 'Guardar'.")
    
    df_editado = st.data_editor(
        df_man,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "ID": st.column_config.NumberColumn("🆔 ID", disabled=True, format="%d"),
            "Fecha": st.column_config.DateColumn("📅 Fecha", format="DD/MM/YYYY"),
            "Monto": st.column_config.NumberColumn("💵 Monto", format="$%d"),
            "Responsable": st.column_config.SelectboxColumn("👤 Responsable", options=["Gordify", "Mon"])
        },
        key="editor_2026_id_fix"
    )

    if st.button("💾 GUARDAR TODO"):
        # 1. Filtramos filas válidas
        df_save = df_editado.dropna(subset=['Fecha', 'Concepto']).copy()
        
        if not df_save.empty:
            # --- LÓGICA DE ID AUTOMÁTICO ---
            # Identificamos el último ID usado
            ultimo_id = df_man['ID'].max()
            if pd.isna(ultimo_id): ultimo_id = 0
            
            # Asignamos IDs a las filas que no lo tienen
            for i, row in df_save.iterrows():
                if pd.isna(row['ID']) or row['ID'] == "":
                    ultimo_id += 1
                    df_save.at[i, 'ID'] = ultimo_id

            # Formateo final
            df_save['Fecha'] = pd.to_datetime(df_save['Fecha']).dt.strftime('%Y-%m-%d')
            df_final = df_save[COLUMNAS_MAESTRAS]
            
            try:
                conn.update(data=df_final)
                st.cache_data.clear()
                st.success(f"✅ ¡Guardado! Se procesaron {len(df_final)} registros.")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

with tab_analisis:
    # Usamos df_man que ya tiene las fechas limpias de la lectura
    df_p = df_man.dropna(subset=['Monto', 'Fecha']).copy()
    if not df_p.empty:
        # Para la gráfica, normalizamos la fecha a "solo día"
        df_p['Fecha_Grafica'] = pd.to_datetime(df_p['Fecha']).dt.normalize()
        
        tot_g = df_p[df_p['Tipo'] == 'Gasto']['Monto'].sum()
        tot_a = df_p[df_p['Tipo'] == 'Abono']['Monto'].sum()
        saldo_global = nuevo_saldo - tot_g + tot_a

        st.subheader("🍴 Estado de Nuestra Fortuna")
        m1, m2, m3 = st.columns(3)
        m1.metric("💰 Fondo Inicial", f"${int(nuevo_saldo):,}")
        m2.metric("🍗 Gastado Total", f"${int(tot_g):,}")
        m3.metric("🥗 Disponible Real", f"${int(saldo_global):,}")

        # Gráfica de Escalera corregida
        diario = df_p.groupby('Fecha_Grafica').apply(lambda x: (x[x['Tipo']=='Abono']['Monto'].sum() - x[x['Tipo']=='Gasto']['Monto'].sum())).reset_index(name='Efecto')
        diario = diario.sort_values('Fecha_Grafica')
        diario['Saldo_Proyectado'] = nuevo_saldo + diario['Efecto'].cumsum()

        fig_line = px.area(diario, x='Fecha_Grafica', y='Saldo_Proyectado', line_shape="hv", markers=True)
        fig_line.update_traces(line_color='#FF5733', fillcolor='rgba(255, 87, 51, 0.2)')
        fig_line.update_xaxes(tickformat="%d/%m/%Y", title="Día")
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("No hay datos suficientes para las gráficas.")
