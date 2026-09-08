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
st.markdown("Planificación avanzada con control simultáneo de **Peso Máximo**, **Cajas por Pallet** y **Cantidad de Pallets**.")

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
        st.sidebar.subheader("2. Estrategia de Priorización")
        estrategia = st.sidebar.radio(
            "Criterio de ordenamiento:",
            ["FIFO (Lotes más antiguos primero)", "Homogéneo (Optimizar pureza de lote por pallet)"],
            help="FIFO prioriza la rotación cronológica. Homogéneo agrupa por lote para evitar mezclas."
        )
        
        st.sidebar.divider()
        st.sidebar.subheader("3. Las 3 Restricciones Operativas")
        
        peso_max_pallet = st.sidebar.number_input(
            "Peso Máximo por Pallet (kg):", 
            min_value=100.0, max_value=2000.0, value=1020.0, step=10.0
        )
        
        max_cajas_pallet = st.sidebar.number_input(
            "Cantidad Máxima de Cajas por Pallet:", 
            min_value=1, max_value=200, value=84, step=1
        )
        
        cant_pallets_objetivo = st.sidebar.number_input(
            "Cantidad Máxima de Pallets a armar:", 
            min_value=1, max_value=50, value=5, step=1,
            help="El sistema armará como máximo esta cantidad de pallets. Las cajas que no entren quedarán para revisión aparte."
        )
            
        # Filtrar dataframe según lotes elegidos
        df_expedicion = df_total[df_total['Lote'].isin(lotes_seleccionados)].copy()
        
        # Aplicar orden según estrategia elegida
        if "FIFO" in estrategia:
            df_expedicion = df_expedicion.sort_values(by=['Elaboracion', 'Fecha', 'Numerador'], na_position='last').reset_index(drop=True)
        else:
            df_expedicion = df_expedicion.sort_values(by=['Lote', 'Fecha', 'Numerador'], na_position='last').reset_index(drop=True)
        
        peso_total_expedicion = df_expedicion['Peso'].sum()
        cajas_total_expedicion = len(df_expedicion)
        
        st.sidebar.divider()
        st.sidebar.markdown(f"**Cajas disponibles:** {cajas_total_expedicion}")
        st.sidebar.markdown(f"**Peso disponible:** {peso_total_expedicion:,.2f} kg")
        
        # --- CUERPO PRINCIPAL ---
        st.info(f"Configuración activa: Topes de **{peso_max_pallet} kg** y **{max_cajas_pallet} cajas**, con un límite de hasta **{cant_pallets_objetivo} pallets**.")
        
        if st.button("🚀 Calcular Optimización de Pallets", type="primary"):
            pallets_generados = []
            pallet_actual_num = 1
            peso_acum_pallet = 0.0
            cajas_actual_pallet = []
            
            cajas_procesadas_indices = []
            
            for idx, row in df_expedicion.iterrows():
                peso_caja = row['Peso']
                
                # Comprobar si al agregar la caja superamos los topes físicos de peso o cantidad de cajas
                supera_peso = (peso_acum_pallet + peso_caja > peso_max_pallet)
                supera_cajas = (len(cajas_actual_pallet) >= max_cajas_pallet)
                
                # Si superamos los límites, debemos cerrar el pallet actual
                if (supera_peso or supera_cajas) and len(cajas_actual_pallet) > 0:
                    # Antes de cerrar, verificamos si ya alcanzamos el límite máximo de pallets permitidos
                    if pallet_actual_num >= cant_pallets_objetivo:
                        # Ya alcanzamos el cupo máximo de pallets, dejamos de procesar aquí
                        break
                    
                    df_subset = df_expedicion.loc[cajas_actual_pallet]
                    pallets_generados.append({
                        'Pallet': f"P-{pallet_actual_num:02d}",
                        'Cantidad de Cajas': len(cajas_actual_pallet),
                        'Peso Total (kg)': round(peso_acum_pallet, 3),
                        'Lotes Incluidos': ", ".join(df_subset['Lote'].astype(str).unique()),
                        'Codigos': df_subset['Codigo'].tolist()
                    })
                    cajas_procesadas_indices.extend(cajas_actual_pallet)
                    
                    pallet_actual_num += 1
                    peso_acum_pallet = 0.0
                    cajas_actual_pallet = []
                
                # Si ya alcanzamos el límite de pallets y el pallet actual está lleno/cerrándose, paramos
                if pallet_actual_num > cant_pallets_objetivo:
                    break
                
                peso_acum_pallet += peso_caja
                cajas_actual_pallet.append(idx)
            
            # Cerrar el último pallet si quedó con cajas y todavía no excedimos la cantidad de pallets
            if len(cajas_actual_pallet) > 0 and pallet_actual_num <= cant_pallets_objetivo:
                df_subset = df_expedicion.loc[cajas_actual_pallet]
                pallets_generados.append({
                    'Pallet': f"P-{pallet_actual_num:02d}",
                    'Cantidad de Cajas': len(cajas_actual_pallet),
                    'Peso Total (kg)': round(peso_acum_pallet, 3),
                    'Lotes Incluidos': ", ".join(df_subset['Lote'].astype(str).unique()),
                    'Codigos': df_subset['Codigo'].tolist()
                })
                cajas_procesadas_indices.extend(cajas_actual_pallet)
            
            # Identificar cajas que quedaron afuera
            indices_afuera = [i for i in df_expedicion.index if i not in cajas_procesadas_indices]
            df_remanente = df_expedicion.loc[indices_afuera]
            
            # Mostrar Resultados
            st.subheader("📋 Plan de Paletizado Óptimo")
            if pallets_generados:
                df_resumen_salida = pd.DataFrame([{
                    'Pallet': p['Pallet'],
                    'Lotes': p['Lotes Incluidos'],
                    'Cantidad de Cajas': p['Cantidad de Cajas'],
                    'Peso Total (kg)': p['Peso Total (kg)']
                } for p in pallets_generados])
                st.dataframe(df_resumen_salida, use_container_width=True)
                
                col_m1, col_m2, col_m3 = st.columns(3)
                col_m1.metric("Total Pallets Armados", len(pallets_generados))
                col_m2.metric("Peso Promedio por Pallet", f"{df_resumen_salida['Peso Total (kg)'].mean():.2f} kg")
                col_m3.metric("Cajas Asignadas a Pallets", df_resumen_salida['Cantidad de Cajas'].sum())
            else:
                st.warning("No se pudo armar ningún pallet con los parámetros actuales.")
            
            # Mostrar remanentes si los hay
            if len(df_remanente) > 0:
                st.subheader("⚠️ Cajas Remanentes (Fuera de los Pallets armados)")
                st.info(f"Quedaron **{len(df_remanente)} cajas** sin asignar (Peso total: **{df_remanente['Peso'].sum():,.2f} kg**).")
                with st.expander("🔍 Ver detalle de cajas remanentes"):
                    st.dataframe(df_remanente[['Numerador', 'Codigo', 'Lote', 'Peso', 'Elaboracion']], hide_index=True)
            
            # Detalle expandible por pallet armado
            with st.expander("🔍 Ver detalle de cajas por cada Pallet"):
                for p in pallets_generados:
                    st.markdown(f"### Pallet: {p['Pallet']} (Lotes: {p['Lotes Incluidos']} | Peso: {p['Peso Total (kg)']:.2f} kg | Cajas: {p['Cantidad de Cajas']})")
                    df_det = df_expedicion[df_expedicion['Codigo'].isin(p['Codigos'])][['Numerador', 'Codigo', 'Lote', 'Peso', 'Elaboracion']]
                    st.dataframe(df_det, hide_index=True)
            
            # Botones de descarga
            if pallets_generados:
                csv_data = df_resumen_salida.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Descargar Plan de Pallets (CSV)",
                    data=csv_data,
                    file_name="Plan_Pallets_Expedicion.csv",
                    mime="text/csv"
                )
else:
    st.info("👈 Por favor, subí los archivos de producción en la barra lateral o área principal para comenzar.")
