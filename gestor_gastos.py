import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px

# 1. CONFIGURACIÓN ÚNICA
st.set_page_config(page_title="Bitácora de Gorditos 🍔", layout="wide")

# --- BANNER ---
URL_BANNER = "https://lh3.googleusercontent.com/d/11Rdr2cVYIypLjmSp9jssuvoOxQ-kI1IZ"
st.image(URL_BANNER, use_container_width=True)

st.title("🍕 Bitácora de Gorditos 🍔")

# --- 2. CONEXIÓN Y ESTRUCTURA ---
conn = st.connection("gsheets", type=GSheetsConnection)

# Definimos el orden exacto que queremos en el Excel
COLUMNAS_MAESTRAS = [
    "Fecha", "Concepto", "Monto", "Tipo", 
    "Categoria", "Tipo_Pago", "Metodo_Pago", "Responsable"
]

# --- 3. LECTURA DE DATOS ---
try:
    # Leer Configuración (Pestaña Config)
    try:
        df_config = conn.read(worksheet="Config", ttl=0)
        saldo_base_valor = float(df_config.iloc[0, 0]) if not df_config.empty else 20000.0
        limite_atracón = float(df_config.iloc[0, 1]) if len(df_config.columns) > 1 else 15000.0
    except:
        saldo_base_valor, limite_atracón = 20000.0, 15000.0

    # Leer Movimientos
    df_man = conn.read(ttl=0)
    
    if df_man is not None and not df_man.empty:
        df_man.columns = [str(c).strip() for c in df_man.columns]
        # Si faltan columnas nuevas, las creamos con valores vacíos
        for c in COLUMNAS_MAESTRAS:
            if c not in df_man.columns:
                df_man[c] = ""
        # Reordenamos para que el Dashboard siempre vea lo mismo
        df_man = df_man[COLUMNAS_MAESTRAS]
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
        st.success("Configuración guardada")
        st.rerun()

# --- 5. REGISTRO ---
tab_reg, tab_ana = st.tabs(["⌨️ Registro", "📊 Análisis"])

with tab_reg:
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
        key="editor_vFinal_8col"
    )

    # Totales proyectados
    g_actual = df_editado[df_editado['Tipo'] == 'Gasto']['Monto'].sum()
    a_actual = df_editado[df_editado['Tipo'] == 'Abono']['Monto'].sum()
    neto_proyectado = nuevo_saldo + a_actual - g_actual

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("🔴 Gastos", f"${int(g_actual):,}")
    c2.metric("🟢 Abonos", f"${int(a_actual):,}")
    c3.metric("💰 NETO PROYECTADO", f"${int(neto_proyectado):,}")
    st.markdown("---")

    if st.button("💾 GUARDAR TODO EN GOOGLE SHEETS"):
        # PASO CLAVE: Solo guardamos si hay datos, y forzamos la estructura
        df_save = df_editado.dropna(subset=['Fecha', 'Concepto']).copy()
        
        if not df_save.empty:
            # Convertimos fecha a texto para que Google no se confunda
            df_save['Fecha'] = pd.to_datetime(df_save['Fecha']).dt.strftime('%Y-%m-%d')
            
            # Forzamos que el DataFrame tenga las 8 columnas antes de enviarlo
            df_final = df_save[COLUMNAS_MAESTRAS]
            
            try:
                # Usamos la conexión para sobreescribir la tabla
                conn.update(data=df_final)
                st.cache_data.clear()
                st.success("✅ ¡Sincronizado correctamente!")
                st.balloons()
                st.rerun()
            except Exception as e:
                st.error(f"Error al sincronizar: {e}")

with tab_ana:
    st.info("Revisa los totales en la pestaña de Registro.")

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
