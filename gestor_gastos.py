import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="Bitácora Comelones 🍔", layout="wide")

# --- 1. CONFIGURACIÓN DE SEGURIDAD (Limpieza de llave) ---
if "connections" in st.secrets and "gsheets" in st.secrets.connections:
    secret_dict = dict(st.secrets.connections.gsheets)
    if "private_key" in secret_dict:
        secret_dict["private_key"] = secret_dict["private_key"].replace("\\n", "\n")
else:
    st.error("¡Faltan las credenciales en los Secrets!")
    st.stop()

# --- 2. CONEXIÓN Y LECTURA ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Leer Saldo Base de 'Config'
    try:
        df_config = conn.read(worksheet="Config", ttl=0)
        saldo_base_valor = float(df_config.iloc[0, 0]) if not df_config.empty else 20000.0
    except:
        saldo_base_valor = 20000.0

    # Leer Movimientos
    df_man = conn.read(ttl=0)
    COLUMNAS = ["Fecha", "Concepto", "Monto", "Tipo", "Categoria", "Metodo_Pago"]
    
    if df_man is not None and not df_man.empty:
        df_man.columns = [str(c).strip() for c in df_man.columns]
        # Renombrar si viene con acento desde Excel
        if "Categoría" in df_man.columns:
            df_man = df_man.rename(columns={"Categoría": "Categoria"})
        for c in COLUMNAS:
            if c not in df_man.columns: df_man[c] = None
        df_man['Fecha'] = pd.to_datetime(df_man['Fecha'], errors='coerce')
        df_man['Monto'] = pd.to_numeric(df_man['Monto'], errors='coerce').fillna(0.0)
    else:
        df_man = pd.DataFrame(columns=COLUMNAS)

except Exception as e:
    st.error(f"Error de conexión: {e}")
    st.stop()

# --- SIDEBAR: CONFIGURACIÓN ---
with st.sidebar:
    st.header("👨‍🍳 Menú del Chef")
    nuevo_saldo = st.number_input("💰 Saldo Base Inicial", value=int(saldo_base_valor), step=100, format="%d")
    
    if st.button("🍳 Guardar Saldo Base"):
        try:
            df_conf_save = pd.DataFrame({"SaldoBase": [nuevo_saldo]})
            conn.update(worksheet="Config", data=df_conf_save)
            st.cache_data.clear()
            st.success("✅ Saldo base actualizado!")
            st.rerun()
        except Exception as e:
            st.error(f"Error: ¿Creaste la pestaña 'Config'? {e}")

# --- INTERFAZ PRINCIPAL ---
st.title("🍕 El Festín de los Comelones 🌮")
tab_registro, tab_analisis = st.tabs(["⌨️ Registro de Pedidos", "📊 ¿Qué nos comimos?"])

with tab_registro:
    st.subheader("🛒 Lista de Movimientos")
    
    OPCIONES_CAT = ["Supermercado/Despensa", "Software/Suscripciones", "Alimentos/Restaurantes", "Servicios", "Viajes", "Salud", "Transporte", "Otros"]

    # Editor de datos
    df_editado = st.data_editor(
        df_man[COLUMNAS],
        num_rows="dynamic",
        width="stretch",
        column_config={
            "Fecha": st.column_config.DateColumn("📅 Fecha", format="DD-MM-YYYY"),
            "Tipo": st.column_config.SelectboxColumn("✨ Tipo", options=["Gasto", "Abono"]),
            "Monto": st.column_config.NumberColumn("💵 Monto", format="$%d"),
            "Categoria": st.column_config.SelectboxColumn("📂 Categoría", options=OPCIONES_CAT)
        },
        key="editor_vFinal_Comelones"
    )
    
    # --- TOTALES EN TIEMPO REAL (Lo que pediste) ---
    st.markdown("### 📊 Resumen de la sesión")
    g_actual = df_editado[df_editado['Tipo'] == 'Gasto']['Monto'].sum()
    a_actual = df_editado[df_editado['Tipo'] == 'Abono']['Monto'].sum()
    disponible_final = nuevo_saldo + a_actual - g_actual
    
    c1, c2, c3 = st.columns(3)
    c1.metric("🔴 Gastos en Tabla", f"${int(g_actual):,}")
    c2.metric("🟢 Abonos en Tabla", f"${int(a_actual):,}")
    c3.metric("💰 NETO (Disponible)", f"${int(disponible_final):,}", delta=f"{int(a_actual - g_actual):,}")

    st.markdown("---")

    if st.button("💾 GUARDAR TODO EN LA NUBE"):
        # 1. Limpieza crítica: solo filas con Fecha Y Monto
        df_save = df_editado.dropna(subset=['Fecha', 'Monto']).copy()
        
        if not df_save.empty:
            # 2. Forzar formatos para Google Sheets
            df_save['Fecha'] = pd.to_datetime(df_save['Fecha']).dt.strftime('%Y-%m-%d')
            df_save['Categoria'] = df_save['Categoria'].astype(str)
            df_save['Monto'] = df_save['Monto'].astype(float)
            
            try:
                # 3. Actualizar
                conn.update(data=df_save)
                # 4. Limpiar caché para que lea lo nuevo
                st.cache_data.clear()
                st.success("✅ ¡Sincronizado con Google Sheets!")
                st.balloons()
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar movimientos: {e}")
        else:
            st.warning("⚠️ No hay datos válidos para guardar.")

with tab_analisis:
    df_p = df_man.dropna(subset=['Monto', 'Fecha']).copy()
    if not df_p.empty:
        df_p['Fecha_DT'] = pd.to_datetime(df_p['Fecha']).dt.normalize()
        tot_g = df_p[df_p['Tipo'] == 'Gasto']['Monto'].sum()
        tot_a = df_p[df_p['Tipo'] == 'Abono']['Monto'].sum()
        saldo_global = nuevo_saldo - tot_g + tot_a

        st.subheader("🍴 Estado Global de la Cartera")
        m1, m2, m3 = st.columns(3)
        m1.metric("Saldo Inicial", f"${int(nuevo_saldo):,}")
        m2.metric("🍗 Gastado Total", f"${int(tot_g):,}", delta_color="inverse")
        m3.metric("🥗 Disponible Real", f"${int(saldo_global):,}")

        # Gráfica
        diario = df_p.groupby('Fecha_DT').apply(lambda x: (x[x['Tipo']=='Abono']['Monto'].sum() - x[x['Tipo']=='Gasto']['Monto'].sum())).reset_index(name='Efecto')
        diario = diario.sort_values('Fecha_DT')
        diario['Saldo_Proyectado'] = nuevo_saldo + diario['Efecto'].cumsum()

        fig = px.area(diario, x='Fecha_DT', y='Saldo_Proyectado', line_shape="hv", markers=True)
        fig.update_traces(line_color='#FF5733', fillcolor='rgba(255, 87, 51, 0.2)')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Anota movimientos para ver el historial.")
