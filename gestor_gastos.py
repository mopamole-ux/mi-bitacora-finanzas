import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Configuración divertida
st.set_page_config(page_title="La Bitácora de los Comelones 🍔", layout="wide")
st.title("🍕 El Festín de las Finanzas 🌮")
st.markdown("### *Porque comer es un placer, pero pagarlo es un deber...*")

# --- 1. CONFIGURACIÓN DE SEGURIDAD ---
if "connections" in st.secrets and "gsheets" in st.secrets.connections:
    secret_dict = dict(st.secrets.connections.gsheets)
    if "private_key" in secret_dict:
        secret_dict["private_key"] = secret_dict["private_key"].replace("\\n", "\n")
else:
    st.error("¡Faltan los ingredientes (Secrets)!")
    st.stop()

# --- 2. CONEXIÓN Y LECTURA ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Leer Movimientos (Hoja 1)
    df_man = conn.read(ttl=0) 
    
    # Leer Saldo Base (Pestaña 'Config')
    try:
        df_config = conn.read(worksheet="Config", ttl=0)
        saldo_base_valor = float(df_config.iloc[0, 0])
    except:
        saldo_base_valor = 20000.0 # Respaldo por si no existe la pestaña

    COLUMNAS = ["Fecha", "Concepto", "Monto", "Tipo", "Categoria", "Metodo_Pago"]
    
    if df_man is not None and not df_man.empty:
        df_man.columns = [str(c).strip() for c in df_man.columns]
        for c in COLUMNAS:
            if c not in df_man.columns: df_man[c] = None
        for col in ["Tipo", "Categoria", "Metodo_Pago"]:
            df_man[col] = df_man[col].astype(str).str.strip().replace("nan", "")
        df_man['Fecha'] = pd.to_datetime(df_man['Fecha'], errors='coerce')
        df_man['Monto'] = pd.to_numeric(df_man['Monto'], errors='coerce').fillna(0.0)
    else:
        df_man = pd.DataFrame(columns=COLUMNAS)

except Exception as e:
    st.error(f"Se quemó el arroz (Error de conexión): {e}")
    st.stop()

# --- SIDEBAR: EL CHEF CONFIGURADOR ---
with st.sidebar:
    st.header("👨‍🍳 Menú de Control")
    nuevo_saldo = st.number_input("💰 Fondos Totales ($)", value=saldo_base_valor, step=500.0)
    
    if st.button("🍳 Actualizar Caja Registradora"):
        df_conf_save = pd.DataFrame({"SaldoBase": [nuevo_saldo]})
        conn.update(worksheet="Config", data=df_conf_save)
        st.success("¡Saldo base guardado!")
        st.cache_data.clear()
        st.rerun()
    
    st.divider()
    st.markdown("❤️ **Comelón 1 & Comelón 2**")
    st.image("https://cdn-icons-png.flaticon.com/512/857/857681.png", width=100)

# --- TABS CON ONDA ---
tab_registro, tab_atracos = st.tabs(["📝 Anotar el Pedido", "📊 ¿Cuánto nos comimos?"])

with tab_registro:
    st.subheader("🛒 Lista de Compras y Antojos")
    
    # Categorías con emojis
    OPCIONES_CAT = [
        "🍱 Super", "💻 Software/Suscripciones", 
        "🍕 Alimentos/Restaurantes", "💡 Servicios", 
        "💸 Préstamos", "✈️ Viajes", "💊 Salud", 
        "🚌 Transporte", "🛡️ Seguros", "🎁 Compras/Otros", "💳 Pagos Realizados"
    ]

    df_editado = st.data_editor(
        df_man[COLUMNAS],
        num_rows="dynamic",
        width="stretch",
        column_config={
            "Fecha": st.column_config.DateColumn("📅 Fecha"),
            "Tipo": st.column_config.SelectboxColumn("✨ Tipo", options=["Gasto", "Abono"]),
            "Metodo_Pago": st.column_config.SelectboxColumn("💳 Pago", options=["Manual", "Automático"]),
            "Categoria": st.column_config.SelectboxColumn("📂 Categoría", options=OPCIONES_CAT),
            "Monto": st.column_config.NumberColumn("💵 Monto", format="$%.2f")
        },
        key="editor_comelones_v1"
    )
    
    # Totales rápidos estilo "Ticket de restaurante"
    g_total = df_editado[df_editado['Tipo'] == 'Gasto']['Monto'].sum()
    a_total = df_editado[df_editado['Tipo'] == 'Abono']['Monto'].sum()
    
    st.markdown(f"""
    ---
    **RESUMEN DEL TICKET:**
    * 🔴 Total Gastado: `${g_total:,.2f}`
    * 🟢 Total Abonos: `${a_total:,.2f}`
    * ⚖️ Diferencia: `${a_total - g_total:,.2f}`
    """)

    if st.button("👨‍🍳 ENVIAR A COCINA (Guardar)"):
        df_save = df_editado.dropna(subset=['Fecha', 'Monto'], how='any').copy()
        if not df_save.empty:
            df_save['Fecha'] = pd.to_datetime(df_save['Fecha']).dt.strftime('%Y-%m-%d')
            # Limpiar emojis de la categoría antes de guardar para no romper el Excel
            df_save['Categoria'] = df_save['Categoria'].str.split(" ").str[-1]
            
            conn.update(data=df_save)
            st.cache_data.clear()
            st.success("¡Buen provecho! Datos guardados.")
            st.balloons()
            st.rerun()

with tab_atracos:
    df_p = df_man.dropna(subset=['Monto', 'Fecha']).copy()
    
    if not df_p.empty:
        df_p['Fecha_DT'] = pd.to_datetime(df_p['Fecha']).dt.normalize()
        tot_g = df_p[df_p['Tipo'] == 'Gasto']['Monto'].sum()
        tot_a = df_p[df_p['Tipo'] == 'Abono']['Monto'].sum()
        disponible_final = nuevo_saldo - tot_g + tot_a

        # Métricas gigantes
        c1, c2, c3 = st.columns(3)
        c1.metric("💰 Saldo Inicial", f"${nuevo_saldo:,.2f}")
        c2.metric("🍗 Gastos", f"${tot_g:,.2f}", delta_color="inverse")
        c3.metric("🥗 Disponible", f"${disponible_final:,.2f}")

        # Gráfica de trayectoria con colores de comida
        st.divider()
        diario = df_p.groupby('Fecha_DT').apply(lambda x: (x[x['Tipo']=='Abono']['Monto'].sum() - x[x['Tipo']=='Gasto']['Monto'].sum())).reset_index(name='Efecto')
        diario = diario.sort_values('Fecha_DT')
        diario['Saldo_Proyectado'] = nuevo_saldo + diario['Efecto'].cumsum()

        fig_line = px.area(diario, x='Fecha_DT', y='Saldo_Proyectado', 
                          line_shape="hv", markers=True, title="🍔 Nuestra Curva de Felicidad (Saldo)")
        fig_line.update_traces(line_color='#FF5733', fillcolor='rgba(255, 87, 51, 0.2)')
        st.plotly_chart(fig_line, use_container_width=True)

        # Categorías más pedidas
        st.subheader("🏆 Lo que más nos gusta")
        df_cat = df_p[df_p['Tipo'] == 'Gasto'].groupby('Categoria')['Monto'].sum().reset_index()
        fig_cat = px.bar(df_cat.sort_values('Monto'), x='Monto', y='Categoria', orientation='h', color='Monto', color_continuous_scale='OrRd')
        st.plotly_chart(fig_cat, use_container_width=True)
    else:
        st.warning("¡La nevera está vacía! (No hay datos)")
