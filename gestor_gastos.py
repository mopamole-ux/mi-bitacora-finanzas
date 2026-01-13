import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime

st.set_page_config(page_title="Mi Bitácora de Gastos", layout="wide")
st.title("📝 Gestor de Gastos Personales (Nube)")

# --- 1. CONFIGURACIÓN DE SEGURIDAD (IMPORTANTE) ---
# Esto limpia la llave de tus Secrets para que Google permita la ESCRITURA
if "connections" in st.secrets and "gsheets" in st.secrets.connections:
    secret_dict = dict(st.secrets.connections.gsheets)
    # Extraemos la URL para usarla después
    target_url = secret_dict.get("spreadsheet") or secret_dict.get("url")
    # Limpiamos saltos de línea en la llave
    if "private_key" in secret_dict:
        secret_dict["private_key"] = secret_dict["private_key"].replace("\\n", "\n")

# --- FUNCIONES DE SOPORTE ---
def a_float(v):
    try:
        if pd.isna(v) or str(v).strip() == "": return 0.0
        return float(str(v).replace(',', '').replace('$', '').replace(' ', '').strip())
    except: return 0.0

# --- 2. CONEXIÓN Y LECTURA ---
try:
    # Pasamos las credenciales limpias
    conn = st.connection("gsheets", type=GSheetsConnection)
    df_man = conn.read(ttl=0) # ttl=0 obliga a traer lo último de la nube
    
    COLUMNAS = ["Fecha", "Concepto", "Monto", "Tipo", "Categoria", "Metodo_Pago"]
    
    if df_man is not None and not df_man.empty:
        # Limpiar nombres de columnas por si acaso
        df_man.columns = [str(c).strip() for c in df_man.columns]
        # Asegurar que existan todas las columnas
        for c in COLUMNAS:
            if c not in df_man.columns: df_man[c] = None
        
        # Limpiar datos para que coincidan con los selectores (quita espacios invisibles)
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
disponible_banco = 20000.0 # Valor base si no hay resumen_mensual.csv

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
    
    if st.button("💾 Guardar Cambios en la Nube"):
        # 1. Copia de seguridad del editor
        df_save = df_editado.copy()
        
        # 2. Filtrar: Solo filas que tengan Fecha y Monto (evita basura)
        df_save = df_save.dropna(subset=['Fecha', 'Monto'], how='any')
        
        if not df_save.empty:
            # --- TRUCO DE FECHA PARA GOOGLE ---
            # Convertimos a datetime y luego a string ISO (YYYY-MM-DD)
            # Esto es lo que Google Sheets entiende como Fecha universal
            df_save['Fecha'] = pd.to_datetime(df_save['Fecha']).dt.strftime('%Y-%m-%d')
            
            # Aseguramos que el resto sean formatos simples
            df_save['Monto'] = df_save['Monto'].astype(float)
            df_save['Concepto'] = df_save['Concepto'].astype(str).fillna("")
            
            try:
                # 3. ACTUALIZACIÓN REAL
                conn.update(data=df_save)
                
                # 4. LIMPIEZA DE MEMORIA (CRUCIAL)
                # Esto borra la copia vieja que Streamlit tiene guardada
                st.cache_data.clear() 
                
                st.success(f"✅ ¡{len(df_save)} movimientos guardados!")
                st.balloons()
                
                # 5. Reinicio para ver los cambios
                st.rerun()
                
            except Exception as e:
                st.error(f"Error al enviar a Google Sheets: {e}")
        else:
            st.warning("No hay datos válidos (Fecha y Monto) para guardar.")

with tab_analisis:
    # Mantenemos tu lógica de gráficas intacta aquí abajo...
    if not df_man.dropna(subset=['Monto', 'Fecha']).empty:
        # (Aquí va el resto de tu código de gráficas que ya tenías)
        st.info("Análisis cargado correctamente.")

    if not df_man.empty:
        # Tu lógica de análisis intacta
        df_p = df_man.dropna(subset=['Monto', 'Fecha']).copy()
        df_p['Fecha_DT'] = pd.to_datetime(df_p['Fecha']).dt.normalize()
        
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
                mode = "gauge+number", value = uso_manual,
                title = {'text': "% Uso de Disponible"},
                gauge = {
                    'axis': {'range': [0, 100]},
                    'bar': {'color': "#1f77b4"},
                    'steps': [
                        {'range': [0, 50], 'color': "lightgreen"},
                        {'range': [50, 80], 'color': "orange"},
                        {'range': [80, 100], 'color': "red"}]}))
            fig_gauge.update_layout(height=250, margin=dict(t=50, b=0, l=20, r=20))
            st.plotly_chart(fig_gauge, use_container_width=True)

        # --- FILA 2: GRÁFICA DE ESCALERA ---

        df_p = df_man.dropna(subset=['Fecha', 'Monto']).copy()
        
        # Forzar a que la fecha sea solo el DÍA (elimina horas/minutos)
        df_p['Fecha_Dia'] = df_p['Fecha'].dt.normalize()
        
        # Agrupar por día para que no salgan mil puntos en el eje X
        diario = df_p.groupby('Fecha_Dia').apply(
            lambda x: x[x['Tipo']=='Abono']['Monto'].sum() - x[x['Tipo']=='Gasto']['Monto'].sum()
        ).reset_index(name='Cambio_Neto')
        
        diario = diario.sort_values('Fecha_Dia')
        diario['Saldo_Acumulado'] = disponible_banco + diario['Cambio_Neto'].cumsum()

        # --- GRÁFICO ---
        fig = px.area(
            diario, 
            x='Fecha_Dia', 
            y='Saldo_Acumulado', 
            line_shape="hv", # Forma de escalera (escalones)
            title="Evolución del Saldo Disponible (Día a Día)",
            markers=True
        )
        
        # Configurar eje X para que se vea limpio
        fig.update_xaxes(
            title="Día",
            dtick="D1", # Forzar una marca por cada día
            tickformat="%d %b" # Ejemplo: 12 Jan
        )
        
        fig.update_traces(line_color='#28A745', fillcolor='rgba(40, 167, 69, 0.2)')
        st.plotly_chart(fig, use_container_width=True)
        
        # Mostrar resumen de hoy
        hoy = datetime.now().date()
        saldo_hoy = diario['Saldo_Acumulado'].iloc[-1] if not diario.empty else disponible_banco
        st.metric("Saldo al día de hoy", f"${saldo_hoy:,.2f}")
    else:
        st.info("Agrega registros con fecha en la pestaña anterior para ver el gráfico.")


        
        st.divider()
        diario = df_p.groupby('Fecha_DT').apply(lambda x: (x[x['Tipo']=='Abono']['Monto'].sum() - x[x['Tipo']=='Gasto']['Monto'].sum())).reset_index(name='Efecto')
        diario = diario.sort_values('Fecha_DT')
        diario['Saldo_Proyectado'] = disponible_banco + diario['Efecto'].cumsum()

        fecha_ini = diario['Fecha_DT'].min() - pd.Timedelta(days=1) if not diario.empty else datetime.now()
        df_plot = pd.concat([pd.DataFrame({'Fecha_DT':[fecha_ini], 'Saldo_Proyectado':[disponible_banco]}), diario]).sort_values('Fecha_DT')

        fig_line = px.area(df_plot, x='Fecha_DT', y='Saldo_Proyectado', 
                          line_shape="hv", markers=True, title="Trayectoria del Crédito Disponible")
        fig_line.update_xaxes(dtick="D1", tickformat="%d %b")
        fig_line.update_traces(line_color='#28A745', fillcolor='rgba(40, 167, 69, 0.2)')
        fig_line.add_hline(y=0, line_dash="dash", line_color="red")
        st.plotly_chart(fig_line, use_container_width=True)

        # --- FILA 3: DISTRIBUCIÓN ---
        st.divider()
        gc1, gc2 = st.columns(2)
        with gc1:
            fig_pie = px.pie(df_p[df_p['Tipo'] == 'Gasto'], values='Monto', names='Metodo_Pago', hole=0.4, title="Gastos: Auto vs Manual")
            st.plotly_chart(fig_pie, use_container_width=True)
        with gc2:
            fig_cat = px.bar(df_p[df_p['Tipo'] == 'Gasto'].groupby('Categoria')['Monto'].sum().reset_index(), x='Categoria', y='Monto', title="Gastos por Categoría", color='Monto')
            st.plotly_chart(fig_cat, use_container_width=True)
    else:
        st.info("Agrega datos para ver el análisis.")
