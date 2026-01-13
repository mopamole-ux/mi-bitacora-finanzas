import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime

st.set_page_config(page_title="Mi Bitácora Pro", layout="wide")
st.title("📝 Gestor de Gastos Personales (Nube)")

# --- 1. CONFIGURACIÓN DE SEGURIDAD (Limpieza de llave) ---
# Usamos una copia para no modificar st.secrets directamente
if "connections" in st.secrets and "gsheets" in st.secrets.connections:
    secret_dict = dict(st.secrets.connections.gsheets)
    if "private_key" in secret_dict:
        # Esto soluciona el error de "Incorrect padding" o "bit stream"
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
    # Conectamos usando la clase oficial
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Leemos con ttl=0 para tener datos en tiempo real
    df_man = conn.read(ttl=0)
    
    COLUMNAS = ["Fecha", "Concepto", "Monto", "Tipo", "Categoria", "Metodo_Pago"]
    
    if df_man is not None and not df_man.empty:
        # Limpiar nombres de columnas
        df_man.columns = [str(c).strip() for c in df_man.columns]
        # Asegurar columnas
        for c in COLUMNAS:
            if c not in df_man.columns: df_man[c] = None
        
        # Limpiar datos para evitar errores de visualización
        for col in ["Tipo", "Categoria", "Metodo_Pago"]:
            df_man[col] = df_man[col].astype(str).str.strip().replace("nan", "")
            
        df_man['Fecha'] = pd.to_datetime(df_man['Fecha'], errors='coerce')
        df_man['Monto'] = df_man['Monto'].apply(a_float)
    else:
        df_man = pd.DataFrame(columns=COLUMNAS)

except Exception as e:
    st.error(f"Error de conexión: {e}")
    st.stop()

# --- CONFIGURACIÓN DE UI ---
CATEGORIAS = ["Supermercado/Despensa", "Software/Suscripciones", "Alimentos/Restaurantes", "Servicios", "Préstamos", "Viajes", "Salud", "Transporte", "Seguros", "Compras/Otros", "Pagos Realizados"]
METODOS = ["Manual/Físico", "Automático"]
disponible_banco = 20000.0 

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
            "Metodo_Pago": st.column_config.SelectboxColumn("Método", options=METODOS, required=True),
            "Categoria": st.column_config.SelectboxColumn("Categoría", options=CATEGORIAS, required=True),
            "Monto": st.column_config.NumberColumn("Monto", format="$%.2f", min_value=0.0)
        },
        key="editor_nube_vFINAL"
    )
    
    # Totales rápidos
    tg = df_editado[df_editado['Tipo'] == 'Gasto']['Monto'].sum()
    ta = df_editado[df_editado['Tipo'] == 'Abono']['Monto'].sum()
    st.markdown(f"**Total Gastos:** ${tg:,.2f} | **Total Abonos:** ${ta:,.2f} | **Neto:** ${tg-ta:,.2f}")

    # --- BOTÓN DE GUARDADO (Corregida la indentación y formato de fecha) ---
    if st.button("💾 Guardar Cambios en la Nube"):
        # 1. Filtramos solo filas válidas
        df_save = df_editado.dropna(subset=['Fecha', 'Monto'], how='any').copy()
        
        if not df_save.empty:
            # 2. CONVERSIÓN DE FECHA: Crítico para que Google Sheets la registre
            # Usamos formato ISO que Sheets siempre acepta
            df_save['Fecha'] = pd.to_datetime(df_save['Fecha']).dt.strftime('%Y-%m-%d')
            
            try:
                # 3. Subir a la nube
                conn.update(data=df_save)
                
                # 4. Limpiar caché para que la siguiente lectura sea fresca
                st.cache_data.clear()
                
                st.success("✅ ¡Datos guardados y fecha registrada!")
                st.balloons()
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")
        else:
            st.warning("Asegúrate de poner Fecha y Monto antes de guardar.")

with tab_analisis:
    if not df_man.dropna(subset=['Monto', 'Fecha']).empty:
        df_p = df_man.dropna(subset=['Monto', 'Fecha']).copy()
        # Normalizamos fecha para la gráfica (agrupar por día)
        df_p['Fecha_DT'] = df_p['Fecha'].dt.normalize()
        
        total_g = df_p[df_p['Tipo'] == 'Gasto']['Monto'].sum()
        total_a = df_p[df_p['Tipo'] == 'Abono']['Monto'].sum()
        saldo_final = disponible_banco - total_g + total_a
        uso_manual = (total_g / disponible_banco * 100) if disponible_banco > 0 else 0

        # --- FILA 1: MÉTRICAS ---
        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader("📉 Resumen de Flujo")
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("Saldo Banco (Base)", f"${disponible_banco:,.2f}")
            mc2.metric("Gastos Bitácora", f"${total_g:,.2f}", delta_color="inverse")
            mc3.metric("Disponible Estimado", f"${saldo_final:,.2f}")
        
        with c2:
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number", value = min(uso_manual, 100),
                title = {'text': "% Uso de Disponible"},
                gauge = {'bar': {'color': "#1f77b4"}}))
            fig_gauge.update_layout(height=250, margin=dict(t=50, b=0, l=20, r=20))
            st.plotly_chart(fig_gauge, use_container_width=True)

        # --- FILA 2: GRÁFICA DE ESCALERA ---
        st.divider()
        diario = df_p.groupby('Fecha_DT').apply(lambda x: (x[x['Tipo']=='Abono']['Monto'].sum() - x[x['Tipo']=='Gasto']['Monto'].sum())).reset_index(name='Efecto')
        diario = diario.sort_values('Fecha_DT')
        diario['Saldo_Proyectado'] = disponible_banco + diario['Efecto'].cumsum()

        fig_line = px.area(diario, x='Fecha_DT', y='Saldo_Proyectado', 
                          line_shape="hv", markers=True, title="Trayectoria del Crédito Disponible")
        
        # Ajustamos el eje X para que no se vea "raro" con demasiados días
        fig_line.update_xaxes(nticks=10, tickformat="%d %b")
        fig_line.update_traces(line_color='#28A745', fillcolor='rgba(40, 167, 69, 0.2)')
        st.plotly_chart(fig_line, use_container_width=True)

        # --- FILA 3: DISTRIBUCIÓN ---
        st.divider()
        gc1, gc2 = st.columns(2)
        with gc1:
            fig_pie = px.pie(df_p[df_p['Tipo'] == 'Gasto'], values='Monto', names='Metodo_Pago', hole=0.4, title="Gastos: Auto vs Manual")
            st.plotly_chart(fig_pie, use_container_width=True)
        with gc2:
            fig_cat = px.bar(df_p[df_p['Tipo'] == 'Gasto'].groupby('Categoria')['Monto'].sum().reset_index(), x='Categoria', y='Monto', title="Gastos por Categoría")
            st.plotly_chart(fig_cat, use_container_width=True)
    else:
        st.info("Agrega datos para ver el análisis.")
