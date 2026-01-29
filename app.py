import streamlit as st
import folium
from folium import DivIcon
from streamlit_folium import st_folium
from supabase import create_client
from geopy.geocoders import Nominatim
from datetime import datetime, timedelta
import time

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
        geolocator = Nominatim(user_agent="app_donde_jugar_admin_final")
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

# ✨ FUNCIÓN: VENTANA EMERGENTE PARA INSCRIBIRSE
@st.dialog("¡Me sumo al partido!")
def confirmar_asistencia(partido_id, cupos_actuales, lista_actual, nombre_cancha):
    st.write(f"Vas a jugar en: **{nombre_cancha}**")
    
    nombre = st.text_input("Tu Nombre:")
    contacto = st.text_input("Tu WhatsApp:")
    
    if st.button("Confirmar Asistencia"):
        if nombre and contacto:
            nuevo_cupo = cupos_actuales - 1
            nuevo_jugador = f"{nombre} ({contacto})"
            
            if lista_actual:
                nueva_lista = f"{lista_actual}, {nuevo_jugador}"
            else:
                nueva_lista = nuevo_jugador
            
            supabase.table('partidos').update({
                "faltan_jugadores": nuevo_cupo,
                "lista_jugadores": nueva_lista
            }).eq("id", partido_id).execute()
            
            st.success("¡Listo! Avisale al capitán.")
            st.rerun()
        else:
            st.error("Por favor llena nombre y contacto.")

# --- BARRA LATERAL (ADMINISTRADOR) ---
with st.sidebar:
    st.header("🕵️ Zona Admin")
    mostrar_login = st.checkbox("Soy Administrador")
    
    if mostrar_login:
        password = st.text_input("Contraseña", type="password")
        
        if password == "admin123":
            st.success("🔓 Acceso Concedido")
            
            # --- PESTAÑAS PARA ORGANIZAR EL ADMIN ---
            tab1, tab2 = st.tabs(["Agregar", "Borrar"])
            
            # PESTAÑA 1: AGREGAR (Lo que ya tenías)
            with tab1:
                st.subheader("Nueva Cancha")
                with st.form("form_nueva_cancha"):
                    new_nombre = st.text_input("Nombre")
                    new_direccion = st.text_input("Dirección")
                    new_deporte = st.selectbox("Deporte", ["Fútbol", "Básquetbol", "Tenis", "Voleibol", "Multicancha"])
                    
                    if st.form_submit_button("Guardar"):
                        if new_nombre and new_direccion:
                            with st.spinner("Ubicando..."):
                                coords = obtener_coordenadas(new_direccion)
                                if coords:
                                    supabase.table('canchas').insert({
                                        "nombre": new_nombre,
                                        "direccion": new_direccion,
                                        "latitud": coords[0],
                                        "longitud": coords[1],
                                        "deporte": new_deporte
                                    }).execute()
                                    st.success("✅ Guardada")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("❌ Dirección no encontrada")
            
            # PESTAÑA 2: BORRAR (Nueva funcionalidad)
            with tab2:
                st.subheader("🗑️ Eliminar Cancha")
                st.warning("Cuidado: Esto no se puede deshacer.")
                
                # Traemos las canchas para ponerlas en la lista
                lista_canchas = supabase.table('canchas').select("id, nombre").execute().data
                if lista_canchas:
                    # Creamos un diccionario {Nombre: ID} para saber cuál borrar
                    opciones_dict = {c['nombre']: c['id'] for c in lista_canchas}
                    seleccion_borrar = st.selectbox("Selecciona cancha:", ["-- Selecciona --"] + list(opciones_dict.keys()))
                    
                    if seleccion_borrar != "-- Selecciona --":
                        if st.button("❌ Eliminar Definitivamente", type="primary"):
                            id_a_borrar = opciones_dict[seleccion_borrar]
                            # Borramos en Supabase
                            supabase.table('canchas').delete().eq('id', id_a_borrar).execute()
                            st.success(f"Chao, {seleccion_borrar} 👋")
                            time.sleep(1)
                            st.rerun()
                else:
                    st.info("No hay canchas para borrar.")

        elif password:
            st.error("Contraseña incorrecta")

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
    info = next((c for c in data_todas if c['nombre'] == seleccion), None)
    
    if info:
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
                            "lista_jugadores": "" 
                        }).execute()
                        st.success("¡Publicado! Se verá por 24 horas.")

# --- AVISOS RECIENTES ---
st.divider()
st.subheader("🔔 Avisos Recientes (Últimas 24 hrs)")

ayer = datetime.now() - timedelta(hours=24)

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

                if a['lista_jugadores']:
                    st.info(f"📝 **Ya se anotaron:** {a['lista_jugadores']}")

            with col_boton:
                if a['faltan_jugadores'] > 0:
                    if st.button("¡Yo voy!", key=f"btn_{a['id']}"):
                        confirmar_asistencia(
                            a['id'], 
                            a['faltan_jugadores'], 
                            a['lista_jugadores'],
                            a['cancha_nombre']
                        )
else:
    st.text("No hay partidos buscando gente en las últimas 24 horas.")