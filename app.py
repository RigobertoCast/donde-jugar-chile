import streamlit as st
import folium
from folium import DivIcon
from streamlit_folium import st_folium
from supabase import create_client
from geopy.geocoders import Nominatim
from datetime import datetime, timedelta

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Donde Jugar V2", page_icon="🚀", layout="wide")

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

# --- APP ---
st.title("📍 ¿Dónde jugamos hoy?")

# 1. BUSCADOR Y FILTROS
col_search, col_filter = st.columns([2, 1])

with col_search:
    direccion = st.text_input("🔍 Buscar Comuna:", placeholder="Ej: La Florida, Santiago Centro")

# Coordenadas por defecto
lat, lon = -33.4489, -70.6693
zoom = 12

if direccion:
    coords = obtener_coordenadas(direccion)
    if coords:
        lat, lon = coords
        zoom = 14

# Cargar datos de canchas
if supabase:
    response = supabase.table('canchas').select("*").execute()
    data_todas = response.data
else:
    data_todas = []

# --- LÓGICA DEL FILTRO (CORREGIDA) ---
with col_filter:
    # Definimos las categorías manuales
    categorias = ["Fútbol", "Básquetbol", "Tenis", "Voleibol"]
    # AQUÍ ESTABA EL ERROR: Ahora usamos 'categorias' (en español)
    filtros_seleccionados = st.multiselect("Filtrar por deporte:", categorias, default=categorias)

# Aplicamos el filtro a los datos
data_filtrada = []
if data_todas:
    for cancha in data_todas:
        texto_deporte = cancha['deporte'].lower()
        mostrar = False
        
        # Lógica de coincidencia
        for filtro in filtros_seleccionados:
            # Truco: Si seleccionan Fútbol, mostramos también 'Baby'
            if filtro.lower() in texto_deporte or (filtro == "Fútbol" and "baby" in texto_deporte):
                mostrar = True
                break
        
        if mostrar:
            data_filtrada.append(cancha)

# --- MAPA ---
m = folium.Map(location=[lat, lon], zoom_start=zoom)

# Marcador Usuario
folium.Marker([lat, lon], popup="Tu Ubicación", icon=folium.Icon(color="red", icon="home")).add_to(m)

# Marcadores Canchas (Usando data_filtrada)
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

# --- SECCIÓN INFERIOR ---
st.divider()
st.subheader("Opciones de Juego")

# Solo mostramos en el selector las canchas que pasaron el filtro
opciones = [c['nombre'] for c in data_filtrada]
seleccion = st.selectbox("Elige una cancha:", ["-- Selecciona --"] + opciones)

if seleccion != "-- Selecciona --":
    # Buscamos la info dentro de data_todas por seguridad
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
                        "contacto": contacto
                    }).execute()
                    st.success("¡Publicado! Se verá por 24 horas.")

# --- AVISOS RECIENTES (LIMPIEZA AUTOMÁTICA) ---
st.divider()
st.subheader("🔔 Avisos Recientes (Últimas 24 hrs)")

ayer = datetime.now() - timedelta(hours=24)

avisos = supabase.table('partidos').select("*")\
    .gt("creado_en", ayer.isoformat())\
    .order("creado_en", desc=True)\
    .execute().data

if avisos:
    for a in avisos:
        st.warning(f"🏃 {a['cancha_nombre']}: Faltan {a['faltan_jugadores']} (Contacto: {a['contacto']})")
else:
    st.text("No hay partidos buscando gente en las últimas 24 horas.")