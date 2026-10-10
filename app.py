import streamlit as st
from PIL import Image
import os
import json
from google import genai

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Control de Ventas - Farmacia",
    page_icon="💊",
    layout="wide"
)

st.title("💊 Indicadores de Ventas por Cajero")
st.markdown("Análisis diario de metas e indicadores mediante la foto general del reporte.")

# --- SIDEBAR: CONFIGURACIÓN DE METAS MENSUALES Y DÍAS ---
st.sidebar.header("🎯 Metas y Configuración Mensual")

meta_mensual_usd = st.sidebar.number_input("Meta Mensual ($ USD)", value=15000.0, step=500.0)
ventas_acumuladas_usd = st.sidebar.number_input("Ventas Acumuladas del Mes ($ USD)", value=4500.0, step=100.0)
dias_restantes = st.sidebar.number_input("Días restantes del mes", value=20, min_value=1, step=1)

st.sidebar.markdown("---")
st.sidebar.subheader("📌 Metas Fijas por Transacción")
target_upt = st.sidebar.number_input("Unidad Promedio Objetivo (UPT)", value=3.0, step=0.1)
target_ticket = st.sidebar.number_input("Ticket Promedio Objetivo ($ USD)", value=9.0, step=0.5)

# --- CÁLCULO DE META DIARIA REQUERIDA (FARMACIA) ---
monto_pendiente_usd = meta_mensual_usd - ventas_acumuladas_usd
if monto_pendiente_usd < 0:
    monto_pendiente_usd = 0.0

meta_hoy_usd = monto_pendiente_usd / dias_restantes
meta_hoy_unidades = (meta_hoy_usd / target_ticket) * target_upt

st.info(f"""
### 📊 Meta Global Requerida para la Farmacia Hoy:
* **Ventas Requeridas:** ${meta_hoy_usd:,.2f} USD
* **Unidades Requeridas:** {int(meta_hoy_unidades)} unidades
""")

# --- CLAVE API DE GEMINI ---
api_key = st.text_input("Ingresa tu Gemini API Key:", type="password")

# --- CARGA Y PROCESAMIENTO DE FOTO ---
st.markdown("---")
st.subheader("📸 Cargar Foto General del Reporte de Cierre")
uploaded_file = st.file_uploader("Sube la imagen de WhatsApp con la lista de cajeros", type=["jpg", "jpeg", "png"])

if uploaded_file and api_key:
    image = Image.open(uploaded_file)
    st.image(image, caption="Reporte General Cargado", use_column_width=True)
    
    if st.button("🔍 Analizar Todos los Cajeros con IA"):
        with st.spinner("Leyendo la tabla de cajeros y calculando indicadores individuales..."):
            try:
                client = genai.Client(api_key=api_key)
                prompt = """
                Analiza esta imagen de reporte de cierre de ventas de farmacia que contiene una lista o tabla de varios cajeros.
                Extrae la información de CADA CAJERO que aparezca en el reporte en una lista de objetos JSON. 
                Cada objeto debe tener exactamente estas llaves:
                - cajero: (nombre completo del cajero)
                - ventas_usd: (monto total en dólares o divisas de ese cajero como número)
                - unidades: (total de unidades vendidas por ese cajero como número)
                - trafico: (cantidad total de transacciones, tickets o facturas de ese cajero como número)
                
                Responde ÚNICAMENTE con una lista JSON válida (ejemplo: [{"cajero": "NOMBRE", "ventas_usd": 0.0, "unidades": 0, "trafico": 0}]) sin texto adicional ni formato markdown extra.
                """
                # Usando el modelo actualizado gemini-3.8-flash
                response = client.models.generate_content(
                    model='gemini-3.8-flash',
                    contents=[image, prompt]
                )
                
                raw_text = response.text.strip()
                if raw_text.startswith("```json"):
                    raw_text = raw_text.replace("```json", "").replace("```", "").strip()
                elif raw_text.startswith("```"):
                    raw_text = raw_text.replace("```", "").strip()
                
                lista_cajeros = json.loads(raw_text)
                
                num_cajeros_detectados = len(lista_cajeros)
                meta_cajero_usd = meta_hoy_usd / num_cajeros_detectados if num_cajeros_detectados > 0 else meta_hoy_usd
                meta_cajero_unidades = meta_hoy_unidades / num_cajeros_detectados if num_cajeros_detectados > 0 else meta_hoy_unidades

                st.success(f"✅ Se detectaron **{num_cajeros_detectados} cajeros** en el reporte. Meta individual estimada por cajero: **${meta_cajero_usd:,.2f} USD**.")

                # Recorrer cada cajero detectado y mostrar su tarjeta individual
                for item in lista_cajeros:
                    nombre = item.get("cajero", "Desconocido")
                    ventas_real = float(item.get("ventas_usd", 0))
                    unidades_real = float(item.get("unidades", 0))
                    trafico_real = float(item.get("trafico", 1))
                    
                    upt_real = unidades_real / trafico_real if trafico_real > 0 else 0
                    ticket_real = ventas_real / trafico_real if trafico_real > 0 else 0
                    
                    with st.container():
                        st.markdown(f"### 👤 Cajero(a): {nombre}")
                        
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("Ventas USD", f"${ventas_real:,.2f}", f"{((ventas_real/meta_cajero_usd)-1)*100:.1f}% vs Meta")
                        col2.metric("Unidades", f"{int(unidades_real)}", f"{((unidades_real/meta_cajero_unidades)-1)*100:.1f}% vs Meta")
                        col3.metric("UPT", f"{upt_real:.2f}", f"{upt_real - target_upt:.2f} vs Obj")
                        col4.metric("Ticket Prom.", f"${ticket_real:.2f}", f"${ticket_real - target_ticket:.2f} vs Obj")
                        
                        # Diagnóstico y recomendaciones específicas por cajero
                        recomendaciones = []
                        if upt_real < target_upt:
                            recomendaciones.append(f"⚠️ **UPT Bajo ({upt_real:.2f}):** Debe mejorar la venta cruzada en caja ofreciendo productos complementarios (ej. sueros, analgésicos con protectores).")
                        else:
                            recomendaciones.append(f"✅ **Buen UPT ({upt_real:.2f}):** Excelente manejo de artículos por cliente.")
                            
                        if ticket_real < target_ticket:
                            recomendaciones.append(f"⚠️ **Ticket Promedio Bajo (${ticket_real:.2f}):** Necesita incentivar marcas de mayor valor o combos en mostrador para elevar el monto por cliente.")
                        else:
                            recomendaciones.append(f"✅ **Buen Ticket Promedio (${ticket_real:.2f}):** Excelente valor por transacción.")
                            
                        for rec in recomendaciones:
                            st.markdown(f"- {rec}")
                            
                        st.markdown("---")
                    
            except Exception as e:
                st.error(f"Error al procesar la imagen o la respuesta de la IA: {e}")
elif uploaded_file and not api_key:
    st.warning("Por favor ingresa tu API Key de Gemini para procesar la imagen.")
