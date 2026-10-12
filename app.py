import streamlit as st
from PIL import Image
import json
from google import genai

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Control de Ventas - Farmacia",
    page_icon="💊",
    layout="wide"
)

st.title("💊 Indicadores de Ventas por Cajero")
st.markdown("Control operativo diario: Configuración matutina y análisis nocturno de rendimiento.")

# --- GESTIÓN DE CREDENCIALES (SECRETS + MEMORIA DE SESIÓN) ---
if "api_key_sesion" not in st.session_state:
    st.session_state.api_key_sesion = ""

api_key_final = ""
try:
    if "GEMINI_API_KEY" in st.secrets and st.secrets["GEMINI_API_KEY"].strip():
        api_key_final = st.secrets["GEMINI_API_KEY"].strip()
except Exception:
    pass

if not api_key_final:
    if st.session_state.api_key_sesion:
        api_key_final = st.session_state.api_key_sesion
    else:
        ingresada = st.sidebar.text_input("🔑 Ingresa tu Gemini API Key:", type="password")
        if ingresada.strip():
            st.session_state.api_key_sesion = ingresada.strip()
            api_key_final = ingresada.strip()

# --- 1, 2 y 3. BARRA LATERAL: CONFIGURACIÓN MATUTINA ---
st.sidebar.header("🌅 Configuración Matutina")
st.sidebar.markdown("Parámetros al iniciar el día:")

meta_mensual_usd = st.sidebar.number_input("Meta Mensual ($ USD)", value=15000.0, step=500.0)
ventas_acumuladas_usd = st.sidebar.number_input("Ventas Acumuladas del Mes ($ USD)", value=4500.0, step=100.0)
dias_restantes = st.sidebar.number_input("Días restantes del mes", value=20, min_value=1, step=1)

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Metas Fijas por Transacción")
target_upt = st.sidebar.number_input("Unidad Promedio Objetivo (UPT)", value=3.0, step=0.1)
target_ticket = st.sidebar.number_input("Ticket Promedio Objetivo ($ USD)", value=9.0, step=0.5)

st.sidebar.markdown("---")
st.sidebar.subheader("👥 Personal de Hoy")
num_cajeros_turno = st.sidebar.number_input(
    "Cantidad de usuarios que laboran hoy:", 
    min_value=1, 
    max_value=10, 
    value=4, 
    step=1,
    help="Indica cuántos cajeros trabajaron en la jornada para repartir la meta diaria equitativamente."
)

# --- 4 y 5. CÁLCULO DE META DIARIA GLOBAL E INDIVIDUAL ---
monto_pendiente_usd = meta_mensual_usd - ventas_acumuladas_usd
if monto_pendiente_usd < 0:
    monto_pendiente_usd = 0.0

meta_hoy_usd = monto_pendiente_usd / dias_restantes
meta_hoy_unidades = (meta_hoy_usd / target_ticket) * target_upt

meta_cajero_usd = meta_hoy_usd / num_cajeros_turno
meta_cajero_unidades = meta_hoy_unidades / num_cajeros_turno

st.info(f"""
### 📊 Resumen de Metas para la Jornada:
* **4. Meta Global Requerida Hoy (Farmacia):** ${meta_hoy_usd:,.2f} USD ({int(meta_hoy_unidades)} unidades)
* **5. Meta Individual por Cajero ({num_cajeros_turno} en turno):** **${meta_cajero_usd:,.2f} USD** | **{int(meta_cajero_unidades)} unidades**
""")

# --- 6. SECCIÓN NOCTURNA: FORMULARIO DE CIERRE ---
st.markdown("---")
st.subheader("🌙 Cierre de Jornada: Análisis de Rendimiento por IA")
st.markdown("Sube la foto del reporte de cierre y presiona el botón para procesar.")

with st.form("form_cierre"):
    uploaded_file = st.file_uploader("Sube la imagen del reporte general (tabla de usuarios)", type=["jpg", "jpeg", "png", "webp", "heic"])
    submitted = st.form_submit_button("🔍 Analizar Rendimiento de Usuarios con IA")

# Procesamiento automático al enviar el formulario
if submitted:
    if not api_key_final:
        st.warning("⚠️ No se detectó ninguna API Key válida. Configúrala en los Secrets de Streamlit o en la barra lateral.")
    elif not uploaded_file:
        st.warning("⚠️ Por favor sube la foto del reporte antes de analizar.")
    else:
        image = Image.open(uploaded_file)
        st.image(image, caption="Reporte de Cierre Nocturno", use_column_width=True)
        
        try:
            with st.spinner("Procesando la tabla de cierre con Gemini..."):
                client = genai.Client(api_key=api_key_final)
                
                prompt = """
                Analiza esta imagen de reporte de cierre de ventas de farmacia. 
                En la tabla verás una columna llamada 'USUARIO' (que contiene los nombres de cada cajero/usuario), 'VENTAS $' (o ventas en dólares), 'UNID V' (unidades vendidas) y 'FACTURAS' (tráfico o transacciones).
                
                Extrae la información de cada fila de la tabla en formato JSON estricto. 
                Responde ÚNICAMENTE con un arreglo JSON válido con esta estructura exacta, sin texto adicional ni bloques markdown:
                [
                  {
                    "cajero": "Nombre exacto que aparece en la columna USUARIO",
                    "ventas_usd": 0.00,
                    "unidades": 0,
                    "trafico": 0
                  }
                ]
                """
                
                # MODELO OBLIGATORIO Y CORRECTO EXIGIDO POR LA PLATAFORMA
                response = client.models.generate_content(
                    model='gemini-3.8-flash',
                    contents=[image, prompt]
                )
            
            if response and response.text:
                raw_text = response.text.strip()
                if "```json" in raw_text:
                    raw_text = raw_text.split("```json")[1].split("```")[0].strip()
                elif "```" in raw_text:
                    raw_text = raw_text.split("```")[1].split("```")[0].strip()
                
                lista_cajeros = json.loads(raw_text)
                
                if isinstance(lista_cajeros, list) and len(lista_cajeros) > 0:
                    st.success(f"✅ ¡Cierre procesado con éxito! Se evaluaron **{len(lista_cajeros)} usuarios** detectados en el reporte.")
                    
                    # --- 7. ANÁLISIS DETALLADO, DIAGNÓSTICO Y RECOMENDACIONES POR USUARIO ---
                    for item in lista_cajeros:
                        nombre = item.get("cajero", "Usuario Desconocido")
                        ventas_real = float(item.get("ventas_usd", 0))
                        unidades_real = float(item.get("unidades", 0))
                        trafico_real = float(item.get("trafico", 1))
                        
                        upt_real = unidades_real / trafico_real if trafico_real > 0 else 0
                        ticket_real = ventas_real / trafico_real if trafico_real > 0 else 0
                        
                        with st.container():
                            st.markdown(f"### 👤 Usuario: {nombre}")
                            
                            col1, col2, col3, col4 = st.columns(4)
                            col1.metric("Ventas USD", f"${ventas_real:,.2f}", f"{((ventas_real/meta_cajero_usd)-1)*100:.1f}% vs Meta")
                            col2.metric("Unidades", f"{int(unidades_real)}", f"{((unidades_real/meta_cajero_unidades)-1)*100:.1f}% vs Meta")
                            col3.metric("UPT (Unid/Factura)", f"{upt_real:.2f}", f"{upt_real - target_upt:.2f} vs Obj")
                            col4.metric("Ticket Promedio", f"${ticket_real:.2f}", f"${ticket_real - target_ticket:.2f} vs Obj")
                            
                            st.markdown("**💡 7. Diagnóstico y Recomendaciones de Mejora:**")
                            if upt_real < target_upt:
                                st.warning(f"⚠️ **UPT Bajo ({upt_real:.2f} vs objetivo de {target_upt}):** El usuario debe mejorar la venta cruzada, ofreciendo productos complementarios (como vitaminas, analgésicos o cuidado personal) en cada transacción.")
                            else:
                                st.success(f"✅ **UPT Destacado ({upt_real:.2f}):** Excelente colocación de múltiples artículos por cliente.")
                                
                            if ticket_real < target_ticket:
                                st.warning(f"⚠️ **Ticket Promedio Bajo (${ticket_real:.2f} vs objetivo de ${target_ticket:.2f}):** Se recomienda incentivar marcas de mayor valor, combos o presentaciones más grandes para elevar el monto por factura.")
                            else:
                                st.success(f"✅ **Ticket Promedio Alto (${ticket_real:.2f}):** Muy buen valor monetario por cada cliente atendido.")
                                
                            st.markdown("---")
                else:
                    st.warning("No se pudieron extraer filas de usuarios en la imagen. Verifica que la foto esté nítida y muestre la tabla completa.")
            else:
                st.error("La IA no devolvió ninguna respuesta. Intenta de nuevo.")
                
        except Exception as e:
            st.error(f"Ocurrió un error al procesar la solicitud: {e}")
