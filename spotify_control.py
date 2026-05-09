# ============================================================
# spotify_control.py — Control de Spotify para Eli
# Usa la API oficial de Spotify vía spotipy con OAuth.
#
# CONFIGURACIÓN INICIAL:
# 1. Crea una app en https://developer.spotify.com/dashboard
# 2. Copia tu Client ID y Client Secret
# 3. Pon http://localhost:8888/callback como Redirect URI
# 4. Reemplaza los valores abajo con los tuyos
# ============================================================

import spotipy
from spotipy.oauth2 import SpotifyOAuth

# --- Credenciales ---
# Reemplaza estos valores con los de tu app en el Dashboard.
# IMPORTANTE: nunca subas este archivo a GitHub con tus credenciales reales.
CLIENT_ID = "a228283c00e14af1acdf591749a45b6e"
CLIENT_SECRET = "dd120f155ee143ff8b416a5a7c68d6de"

# Esta URL debe coincidir EXACTAMENTE con la que pusiste en el Dashboard.
# IMPORTANTE: Spotify ya no acepta "localhost". Usa "127.0.0.1" en su lugar.
# Es donde Spotify te redirige después de autorizar.
REDIRECT_URI = "http://127.0.0.1:8888/callback"

# --- Permisos (scopes) ---
# Cada permiso le dice a Spotify qué puede hacer tu app.
# Sin estos scopes, la API rechaza las peticiones.
SCOPES = (
    "user-read-playback-state "      # Leer qué canción suena
    "user-modify-playback-state "     # Play, pause, skip, volumen
    "user-read-currently-playing "     # Leer la canción actual
    "playlist-read-private "         # Leer playlists privadas
    "playlist-read-collaborative"     # Leer playlists colaborativas
)

# --- Autenticación ---
# SpotifyOAuth maneja todo el flujo de tokens:
# 1. La primera vez, abre tu navegador para que autorices la app.
# 2. Guarda el token en un archivo ".cache" en la carpeta del proyecto.
# 3. Las siguientes veces, renueva el token automáticamente.
#
# cache_path define DÓNDE se guarda el token. ".spotify_cache" es un
# archivo oculto en la carpeta de Eli. Si lo borras, tendrás que
# autorizar de nuevo en el navegador.
_auth_manager = SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    scope=SCOPES,
    cache_path=".spotify_cache",
    open_browser=True  # Abre el navegador automáticamente la primera vez.
)

# Creamos el cliente de Spotify con el auth_manager.
# Este objeto es el que usamos para todas las peticiones a la API.
sp = spotipy.Spotify(auth_manager=_auth_manager)


# ============================================================
# FUNCIONES DE CONTROL
# Cada una retorna un str para que Eli lo diga en voz alta.
# ============================================================

def play():
    try:
        dispositivos = sp.devices()
        lista = dispositivos.get("devices", [])
        if not lista:
            return "Abre Spotify primero en tu computadora."
        device_id = next(
            (d["id"] for d in lista if d.get("type","").lower() == "computer"),
            lista[0]["id"]
        )
        sp.start_playback(device_id=device_id)
        return "Reproduciendo."
    except spotipy.exceptions.SpotifyException as error:
        return _manejar_error(error)


def pause():
    """Pausa la reproducción."""
    try:
        sp.pause_playback()
        return "Música pausada."
    except spotipy.exceptions.SpotifyException as error:
        return _manejar_error(error)


def siguiente():
    """Salta a la siguiente canción."""
    try:
        sp.next_track()
        return "Siguiente canción."
    except spotipy.exceptions.SpotifyException as error:
        return _manejar_error(error)


def anterior():
    """Vuelve a la canción anterior."""
    try:
        sp.previous_track()
        return "Canción anterior."
    except spotipy.exceptions.SpotifyException as error:
        if error.http_status == 403:
            return "No puedo ir a la canción anterior en este momento."
        return _manejar_error(error)


def volumen(porcentaje):
    """
    Cambia el volumen de Spotify (0-100).

    Nota: esto cambia el volumen DENTRO de Spotify, no el volumen
    del sistema operativo. Son independientes.

    Args:
        porcentaje (int): Volumen deseado, de 0 a 100.
    """
    try:
        porcentaje = max(0, min(100, int(porcentaje)))
        sp.volume(porcentaje)
        return f"Volumen de Spotify al {porcentaje}%."
    except spotipy.exceptions.SpotifyException as error:
        return _manejar_error(error)


def que_suena():
    """
    Retorna información sobre la canción que está sonando.

    La API retorna un JSON enorme con toda la info de la canción.
    Nosotros solo extraemos el nombre y los artistas.
    """
    try:
        actual = sp.current_playback()

        # Si no hay nada reproduciéndose, current_playback() retorna None.
        if not actual or not actual.get("item"):
            return "No hay nada reproduciéndose en Spotify."

        # Extraer nombre de la canción.
        cancion = actual["item"]["name"]

        # Los artistas son una lista de diccionarios.
        # Cada uno tiene un campo "name". Los unimos con coma.
        # Ej: [{"name": "Bad Bunny"}, {"name": "Chencho"}] → "Bad Bunny, Chencho"
        artistas = ", ".join(
            artista["name"] for artista in actual["item"]["artists"]
        )

        return f"Suena {cancion} de {artistas}."

    except spotipy.exceptions.SpotifyException as error:
        return _manejar_error(error)


def _activar_dispositivo():
    """Busca el dispositivo de la PC específicamente."""
    import time
    for _ in range(5):
        dispositivos = sp.devices()
        lista = dispositivos.get("devices", [])
        
        if lista:
            # Buscar primero un dispositivo tipo "Computer"
            for d in lista:
                if d.get("type", "").lower() == "computer":
                    return d["id"]
            # Si no hay computadora, usar el activo
            for d in lista:
                if d.get("is_active"):
                    return d["id"]
            # Si ninguno está activo, usar el primero
            return lista[0]["id"]
        
        time.sleep(2)
    return None


def buscar_y_reproducir(query):
    try:
        dispositivos = sp.devices()
        lista = dispositivos.get("devices", [])
        if not lista:
            import os, time
            os.system(r'start "" "C:\Users\Lenovo\OneDrive\Desktop\Spotify.lnk"')
            time.sleep(5)

        # Si busca algo "similar", usar recomendaciones de Spotify
        palabras_similar = ["similar", "parecida", "como", "estilo de"]
        if any(p in query.lower() for p in palabras_similar):
            return _recomendar_similar(query)

        resultados = sp.search(q=query, type="track", limit=5, market="ES")
        canciones = resultados["tracks"]["items"]
        if not canciones:
            return f"No encontré '{query}' en Spotify."

        cancion = None
        query_lower = query.lower()
        for c in canciones:
            if query_lower in c["name"].lower():
                cancion = c
                break
        if not cancion:
            cancion = canciones[0]

        nombre = cancion["name"]
        artista = cancion["artists"][0]["name"]
        track_uri = cancion["uri"]
        device_id = _activar_dispositivo()
        if not device_id:
            return "No pude conectar con Spotify."
        sp.start_playback(device_id=device_id, uris=[track_uri])
        return f"Reproduciendo {nombre} de {artista}."

    except spotipy.exceptions.SpotifyException as error:
        return _manejar_error(error)

def _recomendar_similar(query):
    """Busca recomendaciones basadas en la canción actual."""
    try:
        actual = sp.current_playback()
        if not actual or not actual.get("item"):
            return "No hay ninguna canción sonando para recomendar algo similar."
        
        track_id = actual["item"]["id"]
        recomendaciones = sp.recommendations(seed_tracks=[track_id], limit=5)
        canciones = recomendaciones.get("tracks", [])
        
        if not canciones:
            return "No encontré recomendaciones similares."
        
        cancion = canciones[0]
        nombre = cancion["name"]
        artista = cancion["artists"][0]["name"]
        device_id = _activar_dispositivo()
        sp.start_playback(device_id=device_id, uris=[cancion["uri"]])
        return f"Reproduciendo {nombre} de {artista}, similar a lo que escuchabas."
        
    except spotipy.exceptions.SpotifyException as error:
        return _manejar_error(error)


def buscar_y_reproducir_playlist(query):
    """Busca y reproduce una playlist en Spotify."""
    try:
        # Buscar en playlists del usuario primero
        playlists = sp.current_user_playlists(limit=50)
        lista = playlists.get("items", [])
        
        # Buscar coincidencia en playlists del usuario
        query_lower = query.lower()
        playlist_encontrada = None
        for p in lista:
            if p and query_lower in p["name"].lower():
                playlist_encontrada = p
                break
        
        # Si no encontró en las del usuario, buscar en Spotify general
        if not playlist_encontrada:
            resultados = sp.search(q=query, type="playlist", limit=5, market="ES")
            playlists_general = resultados["playlists"]["items"]
            if playlists_general:
                playlist_encontrada = playlists_general[0]
        
        if not playlist_encontrada:
            return f"No encontré la playlist '{query}'."
        
        nombre = playlist_encontrada["name"]
        uri = playlist_encontrada["uri"]
        
        device_id = _activar_dispositivo()
        sp.start_playback(device_id=device_id, context_uri=uri)
        return f"Reproduciendo playlist {nombre}."
        
    except spotipy.exceptions.SpotifyException as error:
        return _manejar_error(error)

def _manejar_error(error):
    """
    Traduce los errores de la API de Spotify a mensajes amigables.

    La API usa códigos HTTP estándar:
    - 401: Token expirado (spotipy debería renovarlo solo).
    - 403: Sin permisos o sin Premium.
    - 404: No hay dispositivo activo.
    """
    codigo = error.http_status

    if codigo == 404:
        # El error más común: Spotify no está abierto en ningún dispositivo.
        return (
            "No encontré un dispositivo de Spotify activo. "
            "Abre Spotify en tu computadora o celular."
        )

    if codigo == 403:
        return "Spotify requiere cuenta Premium para este control."

    if codigo == 401:
        return "El token de Spotify expiró. Reinicia Eli para autenticarte de nuevo."

    # Error genérico.
    return f"Error de Spotify: {error}"


# --- Prueba directa ---
if __name__ == "__main__":
    print("=== Prueba de Spotify ===")
    print("Nota: Spotify debe estar abierto y reproduciendo algo.\n")

    # Al ejecutar por primera vez, se abrirá tu navegador
    # para autorizar la app. Solo pasa una vez.

    print("1. ¿Qué suena?")
    print(f"   → {que_suena()}\n")

    print("2. Siguiente canción...")
    print(f"   → {siguiente()}\n")

    import time
    time.sleep(2)

    print("3. ¿Qué suena ahora?")
    print(f"   → {que_suena()}\n")

    print("4. Volumen al 40%...")
    print(f"   → {volumen(40)}\n")

    print("5. Buscando una canción...")
    print(f"   → {buscar_y_reproducir('Blinding Lights')}\n")
