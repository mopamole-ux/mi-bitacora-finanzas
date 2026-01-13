import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px

# 1. CONFIGURACIÓN ÚNICA
st.set_page_config(page_title="Bitácora de Gorditos 🍔", layout="wide")

# --- BANNER (Actualizado a width='stretch') ---
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
    df_config = conn.read(worksheet="Config", ttl=0)
    if not df_config.empty:
        saldo_base_valor = float(df_config.iloc[0, 0])
        limite_atracón = float(df_config.iloc[0, 1]) if len(df_config.columns) > 1 else 15000.0
    else:
        saldo_base_valor, limite_atracón = 20000.0, 15000.0

    # Leer Movimientos
    df_man = conn.read(ttl=0)
    
    if df_man is not None and not df_man.empty:
        df_man.columns = [str(c).strip() for c in df_man.columns]
        for c in COLUMNAS_MAESTRAS:
            if c not in df_man.columns:
                df_man[c] = ""
        
        df_man = df_man[COLUMNAS_MAESTRAS].copy()
        df_man['Fecha'] = pd.to_datetime(df_man['Fecha'], errors='coerce')
        df_man['Monto'] = pd.to_numeric(df_man['Monto'], errors='coerce').fillna(0.0)
    else:
        df_man = pd.DataFrame(columns=COLUMNAS_MAESTRAS)

except Exception as e:
    st.error(f"Error al leer datos: {e}")
    st.stop()

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuración")
    nuevo_saldo = st.number_input("💰 Saldo Inicial", value=int(saldo_base_valor), step=100, format="%d")
    nuevo_limite = st.number_input("⚠️ Límite de Gasto", value=int(limite_atracón), step=500, format="%d")
    
    if st.button("🍳 Guardar Config"):
        df_conf_save = pd.DataFrame({"SaldoBase": [nuevo_saldo], "Limite": [nuevo_limite]})
        conn.update(worksheet="Config", data=df_conf_save)
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.subheader("🌡️ Termómetro")
    gastos_calc = df_man[df_man['Tipo'] == 'Gasto']['Monto'].sum()
    progreso = min(gastos_calc / nuevo_limite, 1.0) if nuevo_limite > 0 else 0
    st.progress(progreso)
    st.write(f"Llevan ${int(gastos_calc):,} de ${int(nuevo_limite):,}")

# --- 5. REGISTRO ---
tab_reg, tab_ana = st.tabs(["📝 Registro", "📊 Análisis"])

with tab_reg:
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
        key="editor_2026_v1"
    )

    # Totales
    g_act = df_editado[df_editado['Tipo'] == 'Gasto']['Monto'].sum()
    a_act = df_editado[df_editado['Tipo'] == 'Abono']['Monto'].sum()
    st.metric("💰 NETO PROYECTADO", f"${int(nuevo_saldo + a_act - g_act):,}")

    if st.button("💾 GUARDAR TODO"):
        # Limpieza estricta: Solo filas con Fecha y Monto
        df_save = df_editado.dropna(subset=['Fecha', 'Monto']).copy()
        
        if not df_save.empty:
            # Convertir Fecha a Texto ISO para Google
            df_save['Fecha'] = pd.to_datetime(df_save['Fecha']).dt.strftime('%Y-%m-%d')
            df_final = df_save[COLUMNAS_MAESTRAS]
            
            try:
                conn.update(data=df_final)
                st.cache_data.clear()
                st.success("✅ Guardado correctamente")
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

with tab_ana:
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
