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
st.markdown("Análisis diario de metas e indicadores mediante la foto del reporte.")

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

# --- CONFIGURACIÓN DE NOMBRES DE CAJEROS CON MEMORIA ---
st.subheader("👥 Asignación de Turno")

if "nombres_cajeros" not in st.session_state:
    st.session_state.nombres_cajeros = "Mary Millán, Yosfrank Gamero, Doralys Cumaná, Yorlin Henríquez"

cajeros_input = st.text_area(
    "Nombres de cajeros disponibles (separa cada nombre con una coma):",
    value=st.session_state.nombres_cajeros,
    help="Puedes escribir o agregar nuevos nombres aquí."
)

st.session_state.nombres_cajeros = cajeros_input

cajeros_lista = [c.strip() for c in cajeros_input.split(",") if c.strip()]

cajeros_activos = st.multiselect(
    "Selecciona los cajeros que están de turno hoy:",
    options=cajeros_lista,
    default=cajeros_lista[:2] if len(cajeros_lista) >= 2 else cajeros_lista
)

if cajeros_activos:
    num_cajeros = len(cajeros_activos)
    meta_cajero_usd = meta_hoy_usd / num_cajeros
    meta_cajero_unidades = meta_hoy_unidades / num_cajeros
    
    st.success(f"""
    **Meta Individual para los {num_cajeros} cajeros en turno hoy:**
    * **Meta USD por Cajero:** ${meta_cajero_usd:,.2f} USD
    * **Meta Unidades por Cajero:** {int(meta_cajero_unidades)} unidades
    * **Meta UPT:** {target_upt}
    * **Meta Ticket Promedio:** ${target_ticket:.2f} USD
    """)
else:
    meta_cajero_usd = meta_hoy_usd
    meta_cajero_unidades = meta_hoy_unidades

# --- CLAVE API DE GEMINI ---
api_key = st.text_input("Ingresa tu Gemini API Key:", type="password")

# --- CARGA Y PROCESAMIENTO DE FOTO ---
st.markdown("---")
st.subheader("📸 Cargar Foto del Reporte de Cierre")
uploaded_file = st.file_uploader("Sube la imagen enviada por WhatsApp", type=["jpg", "jpeg", "png"])

if uploaded_file and api_key:
    image = Image.open(uploaded_file)
    st.image(image, caption="Reporte Cargado", use_column_width=True)
    
    if st.button("🔍 Analizar Reporte de Cajeros con IA"):
        with st.spinner("Procesando la tabla de cajeros..."):
            try:
                client = genai.Client(api_key=api_key)
                prompt = """
                Esta imagen contiene un reporte de ventas de farmacia por cajero.
                Lee detenidamente la tabla o lista e identifica CADA CAJERO individualmente.
                
                Responde EXCLUSIVAMENTE con un arreglo JSON de objetos con la siguiente estructura:
                [
                  {
                    "cajero": "Nombre del Cajero",
                    "ventas_usd": 0.00,
                    "unidades": 0,
                    "trafico": 0
                  }
                ]
                
                Instrucciones estrictas:
                1. Extrae el monto de venta en dólares/divisas (ventas_usd).
                2. Extrae las unidades vendidas (unidades).
                3. Extrae la cantidad de tickets/facturas/clientes (trafico). Si no es visible, asigna 1.
                4. Devuelve SOLO el JSON sin texto ni bloques de formato antes o después.
                """
                
                response = client.models.generate_content(
                    model='gemini-3.8-flash',
                    contents=[image, prompt]
                )
                
                raw_text = response.text.strip()
                if "```json" in raw_text:
                    raw_text = raw_text.split("```json")[1].split("```")[0].strip()
                elif "```" in raw_text:
                    raw_text = raw_text.split("```")[1].split("```")[0].strip()
                
                lista_cajeros = json.loads(raw_text)
                
                if isinstance(lista_cajeros, list) and len(lista_cajeros) > 0:
                    st.success(f"✅ Se analizó con éxito el reporte para **{len(lista_cajeros)} cajero(s)**.")
                    
                    for item in lista_cajeros:
                        nombre = item.get("cajero", "Cajero Desconocido")
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
                            
                            st.markdown("**💡 Recomendaciones e Indicadores:**")
                            if upt_real < target_upt:
                                st.warning(f"⚠️ **UPT Bajo ({upt_real:.2f}):** Debe reforzarse la venta de impulso y productos complementarios en mostrador.")
                            else:
                                st.success(f"✅ **UPT Destacado ({upt_real:.2f}):** Buen volumen de unidades por cliente.")
                                
                            if ticket_real < target_ticket:
                                st.warning(f"⚠️ **Ticket Promedio Bajo (${ticket_real:.2f}):** Se recomienda incentivar combos o marcas de mayor valor.")
                            else:
                                st.success(f"✅ **Ticket Promedio Alto (${ticket_real:.2f}):** Excelente rendimiento por factura.")
                                
                            st.markdown("---")
                else:
                    st.warning("No se pudieron extraer filas de cajeros en la imagen. Asegúrate de que la foto esté bien enfocada.")
                    
            except Exception as e:
                st.error(f"Error procesando los datos de la imagen: {e}")
elif uploaded_file and not api_key:
    st.warning("Por favor ingresa tu API Key de Gemini para procesar la imagen.")
