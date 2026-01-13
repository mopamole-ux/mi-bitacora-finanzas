import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime
import time

# 1. CONFIGURACIÓN
st.set_page_config(page_title="Bitácora de Gorditos 🍔", layout="wide")
URL_BANNER = "https://lh3.googleusercontent.com/d/11Rdr2cVYIypLjmSp9jssuvoOxQ-kI1IZ"
st.image(URL_BANNER, width='stretch')
st.title("🍕 Bitácora de Gorditos 🍔")

# --- 2. CONEXIÓN ---
conn = st.connection("gsheets", type=GSheetsConnection)

# Columnas actualizadas para incluir Ámbito
COLUMNAS_MAESTRAS = [
    "Fecha", "Concepto", "Monto", "Tipo", 
    "Categoria", "Tipo_Pago", "Metodo_Pago", "Responsable", "Ambito"
]

# --- 3. LECTURA DE DATOS ---
try:
    # Leer Configuración (TTL 5 min)
    df_config = conn.read(worksheet="Config", ttl=300)
    saldo_base = float(df_config.iloc[0, 0]) if not df_config.empty else 20000.0
    limite_gasto = float(df_config.iloc[0, 1]) if len(df_config.columns) > 1 else 15000.0

    # Leer Movimientos Principales
    df_raw = conn.read(ttl=0) # TTL 0 para ver cambios inmediatos al registrar fijos
    if df_raw is not None and not df_raw.empty:
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        for col in COLUMNAS_MAESTRAS:
            if col not in df_raw.columns: df_raw[col] = ""
        df_man = df_raw[COLUMNAS_MAESTRAS].copy().reset_index(drop=True)
        df_man['Fecha'] = pd.to_datetime(df_man['Fecha'], errors='coerce')
        df_man['Monto'] = pd.to_numeric(df_man['Monto'], errors='coerce').fillna(0.0)
    else:
        df_man = pd.DataFrame(columns=COLUMNAS_MAESTRAS)

    # Leer Gastos Fijos (Plantillas)
    df_fijos = conn.read(worksheet="Fijos", ttl=300)
    if df_fijos is not None and not df_fijos.empty:
        df_fijos.columns = [str(c).strip() for c in df_fijos.columns]
    else:
        df_fijos = pd.DataFrame(columns=["Dia", "Concepto", "Monto", "Categoria", "Responsable", "Ambito"])

except Exception as e:
    st.error(f"Error de conexión o cuota: {e}")
    st.stop()

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuración")
    n_saldo = st.number_input("💰 Saldo Base", value=int(saldo_base), step=100)
    n_limite = st.number_input("⚠️ Límite Gasto", value=int(limite_gasto), step=500)
    if st.button("🍳 Guardar Config"):
        conn.update(worksheet="Config", data=pd.DataFrame({"SaldoBase": [n_saldo], "Limite": [n_limite]}))
        st.cache_data.clear()
        st.rerun()

# --- 5. TABS ---
tab_reg, tab_fijos, tab_ana = st.tabs(["📝 Registro Diario", "📅 Gastos Fijos (Checklist)", "📊 Análisis"])

# --- TAB: REGISTRO DIARIO ---
with tab_reg:
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
            "Ambito": st.column_config.SelectboxColumn("🏠🏢 Ámbito", options=["Casa", "Oficina", "Personal"]),
        },
        key="editor_2026_ambito"
    )

    if st.button("💾 GUARDAR REGISTROS"):
        df_save = df_editado.dropna(subset=['Fecha', 'Concepto'], how='all').copy()
        if not df_save.empty:
            df_save['Fecha'] = pd.to_datetime(df_save['Fecha']).dt.strftime('%Y-%m-%d')
            try:
                conn.update(data=df_save[COLUMNAS_MAESTRAS])
                st.cache_data.clear()
                st.success("✅ ¡Guardado!")
                st.rerun()
            except Exception as e: st.error(f"Error: {e}")

# --- TAB: GASTOS FIJOS (CHECKLIST & AUTOMATIZACIÓN) ---
with tab_fijos:
    st.subheader("📌 Pendientes del Mes")
    mes_actual = datetime.now().month
    anio_actual = datetime.now().year
    
    # Identificar qué fijos ya se pagaron este mes
    df_mes = df_man[(df_man['Fecha'].dt.month == mes_actual) & (df_man['Fecha'].dt.year == anio_actual)]
    conceptos_pagados = df_mes['Concepto'].tolist()

    for ambito in ["Casa", "Oficina"]:
        st.markdown(f"### {'🏠' if ambito == 'Casa' else '🏢'} Gastos de {ambito}")
        items_ambito = df_fijos[df_fijos['Ambito'] == ambito]
        
        if items_ambito.empty:
            st.info(f"No hay gastos fijos definidos para {ambito} en la pestaña 'Fijos'.")
            continue

        for _, row in items_ambito.iterrows():
            col1, col2, col3, col4 = st.columns([1, 3, 2, 2])
            
            pago_realizado = row['Concepto'] in conceptos_pagados
            
            col1.write(f"Día {row['Dia']}")
            col2.write(f"**{row['Concepto']}** (${int(row['Monto']):,})")
            
            if pago_realizado:
                col3.success("✅ Pagado")
                col4.write("")
            else:
                col3.warning("⏳ Pendiente")
                if col4.button(f"Pagar {row['Concepto']}", key=f"btn_{row['Concepto']}"):
                    # Crear nuevo registro basado en el fijo
                    nuevo_pago = pd.DataFrame([{
                        "Fecha": datetime.now().strftime('%Y-%m-%d'),
                        "Concepto": row['Concepto'],
                        "Monto": row['Monto'],
                        "Tipo": "Gasto",
                        "Categoria": row['Categoria'],
                        "Tipo_Pago": "Automático",
                        "Metodo_Pago": "Transferencia",
                        "Responsable": row['Responsable'],
                        "Ambito": row['Ambito']
                    }])
                    # Concatenar con los datos actuales
                    # Importante: Convertir df_man['Fecha'] a string para que coincida con el nuevo registro
                    df_temp = df_man.copy()
                    df_temp['Fecha'] = df_temp['Fecha'].dt.strftime('%Y-%m-%d')
                    df_final_upd = pd.concat([df_temp, nuevo_pago], ignore_index=True)
                    
                    conn.update(data=df_final_to_send := df_final_upd[COLUMNAS_MAESTRAS])
                    st.cache_data.clear()
                    st.toast(f"Registrado: {row['Concepto']}")
                    st.rerun()

# --- TAB: ANÁLISIS ---
with tab_ana:
    if not df_man.empty:
        # Gráfica de Ámbito
        st.subheader("🏠 vs 🏢 ¿Quién consume más?")
        gastos_ambito = df_man[df_man['Tipo'] == 'Gasto'].groupby('Ambito')['Monto'].sum().reset_index()
        fig_ambito = px.bar(gastos_ambito, x='Ambito', y='Monto', color='Ambito', text_auto='.2s',
                           color_discrete_map={'Casa': '#FF5733', 'Oficina': '#33C1FF', 'Personal': '#FFC300'})
        st.plotly_chart(fig_ambito, width='stretch')
        
        # Resumen de Fijos
        total_fijos = df_fijos['Monto'].sum()
        pagado_fijos = df_fijos[df_fijos['Concepto'].isin(conceptos_pagados)]['Monto'].sum()
        
        c1, c2 = st.columns(2)
        c1.metric("📋 Total Fijos Comprometidos", f"${int(total_fijos):,}")
        c2.metric("✅ Total Fijos Pagados", f"${int(pagado_fijos):,}", delta=f"-${int(total_fijos - pagado_fijos)} faltantes")
