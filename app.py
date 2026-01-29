import streamlit as st
import folium
from folium import DivIcon
from streamlit_folium import st_folium
from supabase import create_client
from geopy.geocoders import Nominatim
from datetime import datetime, timedelta

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Donde Jugar", page_icon="⚽", layout="wide")

# --- CONEXIÓN ---
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except:
        return None

supabase = init_connection()

# --- FUNCIONES ---
def obtener_coordenadas(direccion):
    try:
        geolocator = Nominatim(user_agent="app_donde_jugar_final")
        location = geolocator.geocode(f"{direccion}, Chile")
        if location:
            return location.latitude, location.longitude
    except:
        return None
    return None

def obtener_emoji(deporte_texto):
    texto = deporte_texto.lower()
    if "fútbol" in texto or "futbol" in texto or "baby" in texto:
        return "⚽"
    elif "básquetbol" in texto or "basquetbol" in texto:
        return "🏀"
    elif "tenis" in texto:
        return "🎾"
    elif "voleibol" in texto:
        return "🏐"
    else:
        return "📍"

# ✨ NUEVA FUNCIÓN: VENTANA EMERGENTE PARA INSCRIBIRSE ✨
@st.dialog("¡Me sumo al partido!")
def confirmar_asistencia(partido_id, cupos_actuales, lista_actual, nombre_cancha):
    st.write(f"Vas a jugar en: **{nombre_cancha}**")
    
    # Pedimos los datos
    nombre = st.text_input("Tu Nombre:")
    contacto = st.text_input("Tu WhatsApp (para que te contacten):")
    
    if st.button("Confirmar Asistencia"):
        if nombre and contacto:
            # 1. Calculamos los nuevos valores
            nuevo_cupo = cupos_actuales - 1
            
            # Si la lista está vacía, ponemos el nombre. Si ya tiene gente, agregamos coma.
            nuevo_jugador = f"{nombre} ({contacto})"
            if lista_actual:
                nueva_lista = f"{lista_actual}, {nuevo_jugador}"
            else:
                nueva_lista = nuevo_jugador
            
            # 2. Guardamos en Base de Datos
            supabase.table('partidos').update({
                "faltan_jugadores": nuevo_cupo,
                "lista_jugadores": nueva_lista
            }).eq("id", partido_id).execute()
            
            st.success("¡Listo! Avisale al capitán.")
            st.rerun()
        else:
            st.error("Por favor llena nombre y contacto.")

# --- APP PRINCIPAL ---
st.title("📍 ¿Dónde jugamos hoy?")

# 1. BUSCADOR Y FILTROS
col_search, col_filter = st.columns([2, 1])

with col_search:
    direccion = st.text_input("🔍 Buscar Comuna:", placeholder="Ej: La Florida, Santiago Centro")

lat, lon = -33.4489, -70.6693
zoom = 12

if direccion:
    coords = obtener_coordenadas(direccion)
    if coords:
        lat, lon = coords
        zoom = 14

# Cargar datos
if supabase:
    response = supabase.table('canchas').select("*").execute()
    data_todas = response.data
else:
    data_todas = []

# Filtros
with col_filter:
    categorias = ["Fútbol", "Básquetbol", "Tenis", "Voleibol"]
    filtros_seleccionados = st.multiselect("Filtrar por deporte:", categorias, default=categorias)

data_filtrada = []
if data_todas:
    for cancha in data_todas:
        texto_deporte = cancha['deporte'].lower()
        mostrar = False
        for filtro in filtros_seleccionados:
            if filtro.lower() in texto_deporte or (filtro == "Fútbol" and "baby" in texto_deporte):
                mostrar = True
                break
        if mostrar:
            data_filtrada.append(cancha)

# Mapa
m = folium.Map(location=[lat, lon], zoom_start=zoom)
folium.Marker([lat, lon], popup="Tu Ubicación", icon=folium.Icon(color="red", icon="home")).add_to(m)

for c in data_filtrada:
    emoji = obtener_emoji(c['deporte'])
    folium.Marker(
        location=[c['latitud'], c['longitud']],
        popup=f"{c['nombre']}",
        icon=DivIcon(
            icon_size=(30, 30),
            icon_anchor=(15, 15),
            html=f"""<div style="font-size: 30px; text-shadow: 2px 2px 4px #ffffff;">{emoji}</div>"""
        )
    ).add_to(m)

st_folium(m, height=450, use_container_width=True)

# Sección Opciones
st.divider()
st.subheader("Opciones de Juego")
opciones = [c['nombre'] for c in data_filtrada]
seleccion = st.selectbox("Elige una cancha:", ["-- Selecciona --"] + opciones)

if seleccion != "-- Selecciona --":
    info = next(c for c in data_todas if c['nombre'] == seleccion)
    emoji_titulo = obtener_emoji(info['deporte'])
    st.info(f"🏟️ **{info['nombre']}** ({emoji_titulo} {info['deporte']})")
    
    with st.expander("📢 Publicar 'Falta Uno'"):
        with st.form("alerta"):
            faltan = st.number_input("Jugadores faltantes", 1, 10)
            contacto = st.text_input("Contacto")
            if st.form_submit_button("Publicar"):
                if contacto:
                    supabase.table('partidos').insert({
                        "cancha_nombre": info['nombre'],
                        "faltan_jugadores": faltan,
                        "contacto": contacto,
                        "lista_jugadores": "" # Inicializamos vacío
                    }).execute()
                    st.success("¡Publicado! Se verá por 24 horas.")

# --- AVISOS RECIENTES MEJORADOS ---
st.divider()
st.subheader("🔔 Avisos Recientes (Últimas 24 hrs)")

ayer = datetime.now() - timedelta(hours=24)

# Traemos los avisos
avisos = supabase.table('partidos').select("*")\
    .gt("creado_en", ayer.isoformat())\
    .order("creado_en", desc=True)\
    .execute().data

if avisos:
    for a in avisos:
        with st.container(border=True):
            col_texto, col_boton = st.columns([3, 1])
            
            with col_texto:
                st.markdown(f"### ⚽ {a['cancha_nombre']}")
                st.caption(f"Capitán: {a['contacto']}")
                
                if a['faltan_jugadores'] > 0:
                    st.warning(f"🔴 Buscan **{a['faltan_jugadores']}** jugadores")
                else:
                    st.success("✅ ¡Equipo Completo!")

                # MOSTRAR QUIÉNES SE HAN INSCRITO
                if a['lista_jugadores']:
                    st.info(f"📝 **Ya se anotaron:** {a['lista_jugadores']}")

            with col_boton:
                if a['faltan_jugadores'] > 0:
                    # Al hacer click, llamamos a la función dialog
                    if st.button("¡Yo voy!", key=f"btn_{a['id']}"):
                        confirmar_asistencia(
                            a['id'], 
                            a['faltan_jugadores'], 
                            a['lista_jugadores'],
                            a['cancha_nombre']
                        )
else:
    st.text("No hay partidos buscando gente en las últimas 24 horas.")