import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Bitácora de Gorditos 🍔", layout="wide")

# --- BANNER ---
URL_BANNER = "https://lh3.googleusercontent.com/d/11Rdr2cVYIypLjmSp9jssuvoOxQ-kI1IZ"
st.image(URL_BANNER, use_container_width=True)

st.title("🍕 Bitácora de Gorditos 🍔")

# --- ESTILOS CSS ---
st.markdown("""
    <style>
    .main { background-color: #fffaf0; }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 1. CONFIGURACIÓN DE SEGURIDAD ---
if "connections" in st.secrets and "gsheets" in st.secrets.connections:
    secret_dict = dict(st.secrets.connections.gsheets)
    if "private_key" in secret_dict:
        secret_dict["private_key"] = secret_dict["private_key"].replace("\\n", "\n")
else:
    st.error("¡Faltan las credenciales!")
    st.stop()

# --- 2. CONEXIÓN Y LECTURA ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Leer Config (Saldo y Límite)
    try:
        df_config = conn.read(worksheet="Config", ttl=0)
        saldo_base_valor = float(df_config.iloc[0, 0]) if not df_config.empty else 20000.0
        limite_atracón = float(df_config.iloc[0, 1]) if len(df_config.columns) > 1 else 15000.0
    except:
        saldo_base_valor, limite_atracón = 20000.0, 15000.0

    # Leer Movimientos
    df_man = conn.read(ttl=0)
    # Lista maestra de columnas (asegúrate que coincidan con el Excel)
    COLUMNAS_MAESTRAS = [
    "Fecha", "Concepto", "Monto", "Tipo", 
    "Categoria", "Tipo_Pago", "Metodo_Pago", "Responsable"]
    
    if df_man is not None and not df_man.empty:
        
        df# 2. Lectura con Limpieza Inmediata
df_man = conn.read(ttl=0)

if df_man is not None and not df_man.empty:
    # Limpiar nombres de columnas por si acaso hay espacios ocultos
    df_man.columns = [str(c).strip() for c in df_man.columns]
    
    # FORZAR: Si una columna no existe en el Excel, la creamos vacía en el DataFrame
    for col in COLUMNAS_MAESTRAS:
        if col not in df_man.columns:
            df_man[col] = ""
    
    # Ordenar las columnas para que coincidan siempre con nuestra lista maestra
    df_man = df_man[COLUMNAS_MAESTRAS]
    
    # Formatear tipos de datos
    df_man['Fecha'] = pd.to_datetime(df_man['Fecha'], errors='coerce')
    df_man['Monto'] = pd.to_numeric(df_man['Monto'], errors='coerce').fillna(0.0)
else:
    df_man = pd.DataFrame(columns=COLUMNAS_MAESTRAS)
    

# --- SIDEBAR: TERMÓMETRO Y CONFIG ---
with st.sidebar:
    st.header("⚙️ Configuración")
    nuevo_saldo = st.number_input("💰 Saldo Base", value=int(saldo_base_valor), step=100)
    nuevo_limite = st.number_input("⚠️ Límite de Atracón", value=int(limite_atracón), step=500)
    
    if st.button("Guardar Configuración"):
        df_conf_save = pd.DataFrame({"SaldoBase": [nuevo_saldo], "Limite": [nuevo_limite]})
        conn.update(worksheet="Config", data=df_conf_save)
        st.cache_data.clear()
        st.success("¡Configuración guardada!")
        st.rerun()

    st.divider()
    st.subheader("🌡️ Termómetro de Atracón")
    gastos_totales = df_man[df_man['Tipo'] == 'Gasto']['Monto'].sum()
    progreso = min(gastos_totales / nuevo_limite, 1.0) if nuevo_limite > 0 else 0
    
    if gastos_totales > nuevo_limite:
        st.error(f"🚨 ¡LIMITE SUPERADO! Llevan ${int(gastos_totales):,}")
    else:
        st.progress(progreso)
        st.info(f"Llevan ${int(gastos_totales):,} de ${int(nuevo_limite):,}")

# --- INTERFAZ ---
tab_registro, tab_analisis = st.tabs(["⌨️ Registro", "📊 Análisis"])

with tab_registro:
    df_editado = st.data_editor(
        df_man[COLUMNAS],
        num_rows="dynamic",
        width="stretch",
        column_config={
            "Fecha": st.column_config.DateColumn("📅 Fecha", format="DD/MM/YYYY"),
        "Tipo": st.column_config.SelectboxColumn("✨ Tipo", options=["Gasto", "Abono"]),
        "Categoria": st.column_config.SelectboxColumn("📂 Categoría", options=["Super", "Software", "Suscripciones", "Restaurantes", "Servicios", "Salud", "Préstamos", "Pago TDC", "Salarios", "Viajes", "Otros"]),
        "Tipo_Pago": st.column_config.SelectboxColumn("🪙 Tipo pago", options=["Manual", "Automático"]),
        "Metodo_Pago": st.column_config.SelectboxColumn("💳 Forma pago", options=["TDC", "Efectivo", "TDD"]),
        "Responsable": st.column_config.SelectboxColumn("👤 Responsable", options=["Gordify", "Mon"])
    },
        key="editor_ultra_fix_v2" # Nueva clave para resetear caché en iPad
    )
    
    # Totales rápidos
    g_actual = df_editado[df_editado['Tipo'] == 'Gasto']['Monto'].sum()
    a_actual = df_editado[df_editado['Tipo'] == 'Abono']['Monto'].sum()
    disponible_final = nuevo_saldo + a_actual - g_actual
    
    c1, c2, c3 = st.columns(3)
    c1.metric("🔴 Gastos", f"${int(g_actual):,}")
    c2.metric("🟢 Abonos", f"${int(a_actual):,}")
    c3.metric("💰 NETO", f"${int(disponible_final):,}", delta=f"{int(a_actual - g_actual):,}")

    if st.button("💾 GUARDAR TODO EN GOOGLE SHEETS"):
    # 1. Filtramos solo las filas que tienen datos esenciales
    df_save = df_editado.dropna(subset=['Fecha', 'Concepto']).copy()
    
    if not df_save.empty:
        # 2. Formateo de fecha estricto para Sheets
        df_save['Fecha'] = pd.to_datetime(df_save['Fecha']).dt.strftime('%Y-%m-%d')
        
        # 3. ASEGURAR TODAS LAS COLUMNAS: Re-ordenamos justo antes de subir
        # Esto garantiza que 'Tipo_Pago' y 'Responsable' se envíen
        df_final_to_send = df_save[COLUMNAS_MAESTRAS]
        
        try:
            # 4. Actualización
            conn.update(data=df_final_to_send)
            
            # 5. Limpieza de caché y reinicio
            st.cache_data.clear()
            st.success("✅ ¡Sincronización completa! Las 8 columnas fueron enviadas.")
            st.balloons()
            st.rerun()
        except Exception as e:
            st.error(f"Error al guardar: {e}")
    else:
        st.warning("Escribe algo antes de intentar guardar.")

with tab_analisis:
    # 1. Filtramos datos válidos (que tengan Fecha y Monto)
    df_p = df_man.dropna(subset=['Monto', 'Fecha']).copy()
    
    if not df_p.empty:
        # 2. Normalizamos la fecha a solo DÍA para que la gráfica sea legible
        df_p['Fecha_DT'] = pd.to_datetime(df_p['Fecha']).dt.normalize()
        
        # 3. Cálculos de Totales Históricos
        tot_g = df_p[df_p['Tipo'] == 'Gasto']['Monto'].sum()
        tot_a = df_p[df_p['Tipo'] == 'Abono']['Monto'].sum()
        # El Neto toma el Saldo Base + lo guardado en la nube
        saldo_global = nuevo_saldo - tot_g + tot_a

        # --- MÉTRICAS DE RESUMEN ---
        st.subheader("🍴 Estado de Nuestra Fortuna")
        m1, m2, m3 = st.columns(3)
        m1.metric("💰 Fondo Inicial", f"${int(nuevo_saldo):,}")
        m2.metric("🍗 Gastado Total", f"${int(tot_g):,}", delta_color="inverse")
        m3.metric("🥗 Disponible Real", f"${int(saldo_global):,}")

        # --- GRÁFICA DE ESCALERA (Trayectoria del dinero) ---
        st.divider()
        # Agrupamos cambios por día para que no salgan líneas verticales raras
        diario = df_p.groupby('Fecha_DT').apply(
            lambda x: (x[x['Tipo']=='Abono']['Monto'].sum() - x[x['Tipo']=='Gasto']['Monto'].sum())
        ).reset_index(name='Efecto')
        
        diario = diario.sort_values('Fecha_DT')
        # Calculamos el saldo acumulado empezando desde el Saldo Base
        diario['Saldo_Proyectado'] = nuevo_saldo + diario['Efecto'].cumsum()

        fig_line = px.area(
            diario, 
            x='Fecha_DT', 
            y='Saldo_Proyectado', 
            line_shape="hv", # Forma de escalera
            markers=True, 
            title="🎢 Nuestra Montaña Rusa del Dinero"
        )
        
        # Diseño visual (Colores Comelones)
        fig_line.update_traces(line_color='#FF5733', fillcolor='rgba(255, 87, 51, 0.2)')
        
        # AJUSTE DE EJE X: Para que NO se amontonen los días
        fig_line.update_xaxes(
            title="Día",
            tickformat="%d %b", # Ejemplo: 12 Ene
            nticks=10           # Muestra máximo 10 fechas para que no se vea saturado
        )
        
        st.plotly_chart(fig_line, use_container_width=True)

        # --- GRÁFICA DE CATEGORÍAS ---
        st.divider()
        st.subheader("🍕 ¿En qué se nos va el hambre?")
        df_cat = df_p[df_p['Tipo'] == 'Gasto'].groupby('Categoria')['Monto'].sum().reset_index()
        
        if not df_cat.empty:
            fig_cat = px.bar(
                df_cat.sort_values('Monto', ascending=True), 
                x='Monto', 
                y='Categoria', 
                orientation='h',
                color='Monto',
                color_continuous_scale='OrRd',
                title="Gastos por Categoría"
            )
            st.plotly_chart(fig_cat, use_container_width=True)
    else:
        st.info("¡La despensa está vacía! Anota movimientos en la otra pestaña para ver las gráficas. 👨‍🍳")
