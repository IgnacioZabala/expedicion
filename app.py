import streamlit as st
import pandas as pd
import glob
import os

st.set_page_config(
    page_title="Optimizador de Pallets - Expedición", 
    layout="wide",
    page_icon="📦"
)

st.title("📦 Optimizador Inteligente de Pallets para Expedición")
st.markdown("Agrupación optimizada de cajas por lote con restricciones múltiples (Peso, Cajas por Pallet y Cantidad de Pallets).")

# 1. Subida de archivos
uploaded_files = st.file_uploader(
    "Subir archivos de producción CajasxOrden (.xls)", 
    type=["xls", "xlsx"], 
    accept_multiple_files=True
)

if uploaded_files:
    all_data = []
    for file in uploaded_files:
        try:
            df = pd.read_excel(file, sheet_name='Cajas', header=2)
            df['Archivo_Origen'] = file.name
            all_data.append(df)
        except Exception as e:
            st.error(f"Error al leer {file.name}: {e}")
            
    if all_data:
        df_total = pd.concat(all_data, ignore_index=True)
        
        # Limpieza de tipos de datos clave
        df_total['Peso'] = pd.to_numeric(df_total['Peso'], errors='coerce')
        df_total['Numerador'] = pd.to_numeric(df_total['Numerador'], errors='coerce')
        df_total['Fecha'] = pd.to_numeric(df_total['Fecha'], errors='coerce')
        
        lotes_disponibles = sorted(df_total['Lote'].dropna().unique().tolist())
        
        # --- BARRA LATERAL ---
        st.sidebar.header("🎛️ Panel de Control")
        
        st.sidebar.subheader("1. Selección de Lotes")
        lotes_seleccionados = st.sidebar.multiselect(
            "Lotes a incluir en la expedición:", 
            lotes_disponibles,
            default=lotes_disponibles
        )
        
        if not lotes_seleccionados:
            lotes_seleccionados = lotes_disponibles
            
        st.sidebar.divider()
        st.sidebar.subheader("2. Restricciones Operativas")
        
        # Variables de limitación
        peso_max_pallet = st.sidebar.number_input(
            "Peso Máximo por Pallet (kg):", 
            min_value=100.0, max_value=2000.0, value=1020.0, step=10.0,
            help="Límite superior de peso permitido por pallet."
        )
        
        max_cajas_pallet = st.sidebar.number_input(
            "Cantidad Máxima de Cajas por Pallet:", 
            min_value=1, max_value=200, value=84, step=1,
            help="Límite físico de cajas que entran en un pallet."
        )
        
        usar_limite_pallets = st.sidebar.checkbox("Limitar Cantidad Total de Pallets", value=False)
        cant_pallets_objetivo = None
        if usar_limite_pallets:
            cant_pallets_objetivo = st.sidebar.number_input(
                "Cantidad Objetiva de Pallets:", 
                min_value=1, max_value=50, value=5, step=1
            )
            
        # Filtrar dataframe según lotes elegidos y ordenar
        df_expedicion = df_total[df_total['Lote'].isin(lotes_seleccionados)].copy()
        df_expedicion = df_expedicion.sort_values(by=['Lote', 'Fecha', 'Numerador'], na_position='last').reset_index(drop=True)
        
        peso_total_expedicion = df_expedicion['Peso'].sum()
        cajas_total_expedicion = len(df_expedicion)
        
        # Mostrar resumen en barra lateral
        st.sidebar.divider()
        st.sidebar.markdown(f"**Cajas en expedición:** {cajas_total_expedicion}")
        st.sidebar.markdown(f"**Peso total:** {peso_total_expedicion:,.2f} kg")
        
        # --- CUERPO PRINCIPAL ---
        st.info(f"Configuración lista para procesar **{cajas_total_expedicion} cajas** de los lotes seleccionados.")
        
        if st.button("🚀 Calcular Optimización de Pallets", type="primary"):
            pallets_generados = []
            pallet_actual_num = 1
            peso_acum_pallet = 0.0
            cajas_actual_pallet = []
            
            for idx, row in df_expedicion.iterrows():
                # Comprobar si al agregar la caja superamos alguna restricción (Peso o Cantidad de Cajas)
                supera_peso = (peso_acum_pallet + row['Peso'] > peso_max_pallet)
                supera_cajas = (len(cajas_actual_pallet) >= max_cajas_pallet)
                
                if (supera_peso or supera_cajas) and len(cajas_actual_pallet) > 0:
                    df_subset = df_expedicion.loc[cajas_actual_pallet]
                    pallets_generados.append({
                        'Pallet': f"P-{pallet_actual_num:02d}",
                        'Cantidad de Cajas': len(cajas_actual_pallet),
                        'Peso Total (kg)': round(peso_acum_pallet, 3),
                        'Lotes Incluidos': ", ".join(df_subset['Lote'].astype(str).unique()),
                        'Codigos': df_subset['Codigo'].tolist()
                    })
                    pallet_actual_num += 1
                    peso_acum_pallet = 0.0
                    cajas_actual_pallet = []
                
                peso_acum_pallet += row['Peso']
                cajas_actual_pallet.append(idx)
            
            # Cerrar el último pallet remanente
            if cajas_actual_pallet:
                df_subset = df_expedicion.loc[cajas_actual_pallet]
                pallets_generados.append({
                    'Pallet': f"P-{pallet_actual_num:02d}",
                    'Cantidad de Cajas': len(cajas_actual_pallet),
                    'Peso Total (kg)': round(peso_acum_pallet, 3),
                    'Lotes Incluidos': ", ".join(df_subset['Lote'].astype(str).unique()),
                    'Codigos': df_subset['Codigo'].tolist()
                })
                
            # Si se especificó un límite estricto de cantidad de pallets y hay desfasaje, se advierte
            df_resumen_salida = pd.DataFrame([{
                'Pallet': p['Pallet'],
                'Lotes': p['Lotes Incluidos'],
                'Cantidad de Cajas': p['Cantidad de Cajas'],
                'Peso Total (kg)': p['Peso Total (kg)']
            } for p in pallets_generados])
            
            st.subheader("📋 Plan de Paletizado Óptimo")
            st.dataframe(df_resumen_salida, use_container_width=True)
            
            # Métricas principales
            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric("Total Pallets Resultantes", len(pallets_generados))
            col_m2.metric("Peso Promedio por Pallet", f"{df_resumen_salida['Peso Total (kg)'].mean():.2f} kg")
            col_m3.metric("Cajas Totales Asignadas", df_resumen_salida['Cantidad de Cajas'].sum())
            
            # Detalle expandible por pallet
            with st.expander("🔍 Ver detalle de cajas por cada Pallet"):
                for p in pallets_generados:
                    st.markdown(f"### Pallet: {p['Pallet']} (Lotes: {p['Lotes Incluidos']} | Peso: {p['Peso Total (kg)']:.2f} kg | Cajas: {p['Cantidad de Cajas']})")
                    df_det = df_expedicion[df_expedicion['Codigo'].isin(p['Codigos'])][['Numerador', 'Codigo', 'Lote', 'Peso', 'Elaboracion']]
                    st.dataframe(df_det, hide_index=True)
            
            # Botón de descarga
            csv_data = df_resumen_salida.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar Plan de Expedición (CSV)",
                data=csv_data,
                file_name="Plan_Pallets_Expedicion.csv",
                mime="text/csv"
            )
else:
    st.info("👈 Por favor, subí los archivos de producción en la barra lateral o área principal para comenzar.")
