import base64
import time
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-me")

SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI", "http://localhost:5000/callback")
GENIUS_ACCESS_TOKEN = os.environ.get("GENIUS_ACCESS_TOKEN")

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"
SPOTIFY_SCOPES = (
    "user-read-currently-playing user-read-playback-state user-modify-playback-state "
    "streaming user-read-email user-read-private"
)

GENIUS_SEARCH_URL = "https://api.genius.com/search"

# O endpoint oficial /v1/audio-features do Spotify foi bloqueado para apps novos
# desde nov/2024. A ReccoBeats (reccobeats.com) é um serviço comunitário gratuito
# que replica os mesmos dados (key, mode, tempo) a partir do ID da faixa no Spotify.
RECCOBEATS_API_BASE = "https://api.reccobeats.com/v1"

PITCH_CLASS_MAP = {
    0: "C", 1: "C♯/D♭", 2: "D", 3: "D♯/E♭", 4: "E", 5: "F",
    6: "F♯/G♭", 7: "G", 8: "G♯/A♭", 9: "A", 10: "A♯/B♭", 11: "B",
    -1: "Desconhecida",
}
MODE_MAP = {0: "menor", 1: "maior"}

WEATHER_CODE_MAP = {
    0: "Céu limpo", 1: "Predominantemente limpo", 2: "Parcialmente nublado", 3: "Nublado",
    45: "Neblina", 48: "Neblina com geada",
    51: "Chuvisco leve", 53: "Chuvisco moderado", 55: "Chuvisco intenso",
    61: "Chuva leve", 63: "Chuva moderada", 65: "Chuva forte",
    71: "Neve leve", 73: "Neve moderada", 75: "Neve forte",
    80: "Aguaceiros leves", 81: "Aguaceiros moderados", 82: "Aguaceiros violentos",
    95: "Trovoadas", 96: "Trovoadas com granizo leve", 99: "Trovoadas com granizo forte",
}

WEATHER_ICON_MAP = {
    0: "☀️", 1: "🌤️", 2: "⛅", 3: "☁️",
    45: "🌫️", 48: "🌫️",
    51: "🌦️", 53: "🌦️", 55: "🌧️",
    61: "🌧️", 63: "🌧️", 65: "⛈️",
    71: "🌨️", 73: "🌨️", 75: "❄️",
    80: "🌦️", 81: "🌧️", 82: "⛈️",
    95: "⛈️", 96: "⛈️", 99: "⛈️",
}

WIND_DIRECTIONS = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSO", "SO", "OSO", "O", "ONO", "NO", "NNO",
]

_lyrics_cache = {}
_audio_features_cache = {}


@app.route("/")
def pokedex():
    return render_template("pokedex.html")


@app.route("/weather")
def weather():
    return render_template("weather.html")


@app.route("/spotify")
def spotify():
    return render_template("spotify.html")


@app.route("/player")
def player():
    return render_template("player.html")


@app.route("/liquido")
def liquido():
    return render_template("liquido.html")


@app.route("/deserto")
def deserto():
    return render_template("deserto.html")


@app.route("/chuva-letras")
def chuva_letras():
    return render_template("chuva_letras.html")


def _direcao_vento(graus):
    if graus is None:
        return None
    return WIND_DIRECTIONS[round(graus / 22.5) % 16]


def _buscar_localizacao(lat, lon):
    try:
        resp = requests.get(
            "https://api.bigdatacloud.net/data/reverse-geocode-client",
            params={"latitude": lat, "longitude": lon, "localityLanguage": "pt"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException:
        return None

    cidade = data.get("city") or data.get("locality")
    estado = data.get("principalSubdivision")
    pais = data.get("countryName")
    partes = [p for p in (cidade, estado, pais) if p]
    return ", ".join(partes) if partes else None


@app.route("/api/clima")
def api_clima():
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    if not lat or not lon:
        return jsonify({"error": "Parâmetros lat/lon são obrigatórios."}), 400

    try:
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": ",".join([
                    "temperature_2m", "relative_humidity_2m", "apparent_temperature",
                    "precipitation", "weather_code", "cloud_cover", "pressure_msl",
                    "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m", "is_day",
                ]),
                "daily": ",".join([
                    "temperature_2m_max", "temperature_2m_min", "uv_index_max",
                    "precipitation_probability_max", "sunrise", "sunset",
                ]),
                "timezone": "auto",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        return jsonify({"error": f"Falha ao consultar serviço de clima: {exc}"}), 502

    current = data.get("current", {})
    daily = data.get("daily", {})
    codigo = current.get("weather_code")

    return jsonify({
        "local": _buscar_localizacao(lat, lon),
        "timezone": data.get("timezone"),
        "atual": {
            "temperatura": current.get("temperature_2m"),
            "sensacao_termica": current.get("apparent_temperature"),
            "umidade": current.get("relative_humidity_2m"),
            "precipitacao": current.get("precipitation"),
            "nebulosidade": current.get("cloud_cover"),
            "pressao": current.get("pressure_msl"),
            "vento_velocidade": current.get("wind_speed_10m"),
            "vento_direcao": _direcao_vento(current.get("wind_direction_10m")),
            "vento_rajada": current.get("wind_gusts_10m"),
            "condicao": WEATHER_CODE_MAP.get(codigo, "Desconhecido"),
            "icone": WEATHER_ICON_MAP.get(codigo, "🌡️"),
            "e_dia": bool(current.get("is_day")),
        },
        "hoje": {
            "temp_max": (daily.get("temperature_2m_max") or [None])[0],
            "temp_min": (daily.get("temperature_2m_min") or [None])[0],
            "uv_max": (daily.get("uv_index_max") or [None])[0],
            "chance_chuva": (daily.get("precipitation_probability_max") or [None])[0],
            "nascer_sol": (daily.get("sunrise") or [None])[0],
            "por_sol": (daily.get("sunset") or [None])[0],
        },
    })


@app.route("/login")
def spotify_login():
    params = {
        "client_id": SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "scope": SPOTIFY_SCOPES,
    }
    return redirect(f"{SPOTIFY_AUTH_URL}?{urlencode(params)}")


@app.route("/callback")
def spotify_callback():
    code = request.args.get("code")
    error = request.args.get("error")
    if error or not code:
        return redirect(url_for("spotify"))

    auth_header = base64.b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()).decode()

    resp = requests.post(
        SPOTIFY_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": SPOTIFY_REDIRECT_URI,
        },
        headers={"Authorization": f"Basic {auth_header}"},
        timeout=10,
    )
    if resp.status_code != 200:
        return redirect(url_for("spotify"))

    token_data = resp.json()
    session["spotify_access_token"] = token_data["access_token"]
    session["spotify_refresh_token"] = token_data.get("refresh_token")
    session["spotify_token_expires_at"] = time.time() + token_data["expires_in"]

    return redirect(url_for("spotify"))


@app.route("/logout")
def spotify_logout():
    session.pop("spotify_access_token", None)
    session.pop("spotify_refresh_token", None)
    session.pop("spotify_token_expires_at", None)
    return redirect(url_for("spotify"))


def _refresh_spotify_token():
    refresh_token = session.get("spotify_refresh_token")
    if not refresh_token:
        return None

    auth_header = base64.b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()).decode()

    resp = requests.post(
        SPOTIFY_TOKEN_URL,
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        headers={"Authorization": f"Basic {auth_header}"},
        timeout=10,
    )
    if resp.status_code != 200:
        return None

    token_data = resp.json()
    session["spotify_access_token"] = token_data["access_token"]
    session["spotify_token_expires_at"] = time.time() + token_data["expires_in"]
    return token_data["access_token"]


def _get_valid_spotify_token():
    access_token = session.get("spotify_access_token")
    expires_at = session.get("spotify_token_expires_at", 0)

    if not access_token:
        return None
    if time.time() >= expires_at - 30:
        access_token = _refresh_spotify_token()
    return access_token


def _buscar_letra(track_name, artists):
    """Busca a música no Genius e devolve dados para o widget de embed oficial.

    Não fazemos scraping da página de letra: o Genius bloqueia (403) requisições
    vindas de IPs de datacenter/nuvem via proteção anti-bot. Em vez disso, usamos
    o embed oficial deles (carregado no navegador do usuário, não no backend).
    """
    if not GENIUS_ACCESS_TOKEN or not track_name:
        return None

    cache_key = f"{track_name}::{artists}"
    if _lyrics_cache.get(cache_key):
        return _lyrics_cache[cache_key]

    resultado = None
    try:
        primeiro_artista = artists.split(",")[0].strip() if artists else ""
        busca = requests.get(
            GENIUS_SEARCH_URL,
            params={"q": f"{track_name} {primeiro_artista}"},
            headers={"Authorization": f"Bearer {GENIUS_ACCESS_TOKEN}"},
            timeout=10,
        )
        busca.raise_for_status()
        hits = busca.json().get("response", {}).get("hits", [])

        if hits:
            song = hits[0]["result"]
            resultado = {
                "id": song["id"],
                "url": song.get("url"),
                "titulo": song.get("title"),
            }
    except (requests.RequestException, KeyError, IndexError):
        resultado = None

    _lyrics_cache[cache_key] = resultado
    return resultado


def _buscar_audio_features(spotify_track_id):
    if not spotify_track_id:
        return None

    if spotify_track_id in _audio_features_cache:
        return _audio_features_cache[spotify_track_id]

    resultado = None
    try:
        mapeamento = requests.get(
            f"{RECCOBEATS_API_BASE}/track",
            params={"ids": spotify_track_id},
            timeout=10,
        )
        mapeamento.raise_for_status()
        itens = mapeamento.json().get("content", [])

        if itens:
            reccobeats_id = itens[0]["id"]
            features_resp = requests.get(
                f"{RECCOBEATS_API_BASE}/track/{reccobeats_id}/audio-features",
                timeout=10,
            )
            features_resp.raise_for_status()
            features = features_resp.json()
            resultado = {
                "bpm": round(features.get("tempo", 0)),
                "tonalidade": PITCH_CLASS_MAP.get(features.get("key"), "Desconhecida"),
                "modo": MODE_MAP.get(features.get("mode"), ""),
            }
    except (requests.RequestException, KeyError, IndexError):
        resultado = None

    if resultado:
        _audio_features_cache[spotify_track_id] = resultado
    return resultado


REPEAT_LABELS = {"off": "Desligada", "track": "Faixa atual", "context": "Lista/Álbum"}
CONTEXT_LABELS = {"album": "Álbum", "playlist": "Playlist", "artist": "Artista", "show": "Podcast"}

_artist_genres_cache = {}
_context_name_cache = {}


def _buscar_generos_artista(artist_id, headers):
    if not artist_id:
        return []
    if artist_id in _artist_genres_cache:
        return _artist_genres_cache[artist_id]

    generos = []
    try:
        resp = requests.get(f"{SPOTIFY_API_BASE}/artists/{artist_id}", headers=headers, timeout=10)
        resp.raise_for_status()
        generos = resp.json().get("genres", [])
    except requests.RequestException:
        generos = []

    _artist_genres_cache[artist_id] = generos
    return generos


def _buscar_nome_contexto(contexto, headers):
    href = contexto.get("href")
    if not href:
        return None
    if href in _context_name_cache:
        return _context_name_cache[href]

    nome = None
    try:
        resp = requests.get(href, headers=headers, timeout=10)
        resp.raise_for_status()
        nome = resp.json().get("name")
    except requests.RequestException:
        nome = None

    _context_name_cache[href] = nome
    return nome


@app.route("/api/spotify/now-playing")
def api_spotify_now_playing():
    access_token = _get_valid_spotify_token()
    if not access_token:
        return jsonify({"authenticated": False})

    headers = {"Authorization": f"Bearer {access_token}"}
    resp = requests.get(f"{SPOTIFY_API_BASE}/me/player", headers=headers, timeout=10)

    if resp.status_code == 204 or not resp.content:
        return jsonify({"authenticated": True, "playing": False})

    if resp.status_code != 200:
        return jsonify({"authenticated": True, "playing": False, "error": "Falha ao consultar Spotify."})

    data = resp.json()
    item = data.get("item")
    if not item:
        return jsonify({"authenticated": True, "playing": False})

    artistas_lista = item.get("artists", [])
    artists = ", ".join(a["name"] for a in artistas_lista)
    track_name = item.get("name")
    album = item.get("album", {})
    device = data.get("device") or {}
    contexto = data.get("context") or {}
    contexto_tipo = contexto.get("type")

    primeiro_artista_id = artistas_lista[0]["id"] if artistas_lista else None

    return jsonify({
        "authenticated": True,
        "playing": data.get("is_playing", False),
        "track": {
            "id": item.get("id"),
            "nome": track_name,
            "artistas": artists,
            "artistas_detalhe": [
                {"nome": a["name"], "link": a.get("external_urls", {}).get("spotify")}
                for a in artistas_lista
            ],
            "generos": _buscar_generos_artista(primeiro_artista_id, headers),
            "album": album.get("name"),
            "tipo_album": album.get("album_type"),
            "capa": (album.get("images") or [{}])[0].get("url"),
            "progresso_ms": data.get("progress_ms"),
            "duracao_ms": item.get("duration_ms"),
            "explicito": item.get("explicit", False),
            "popularidade": item.get("popularity"),
            "numero_faixa": item.get("track_number"),
            "total_faixas_album": album.get("total_tracks"),
            "data_lancamento": album.get("release_date"),
            "preview_url": item.get("preview_url"),
            "link_spotify": item.get("external_urls", {}).get("spotify"),
            "isrc": item.get("external_ids", {}).get("isrc"),
        },
        "reproducao": {
            "dispositivo": device.get("name"),
            "tipo_dispositivo": device.get("type"),
            "aleatorio": data.get("shuffle_state", False),
            "repeticao": data.get("repeat_state", "off"),
            "repeticao_label": REPEAT_LABELS.get(data.get("repeat_state"), "—"),
            "contexto_tipo": CONTEXT_LABELS.get(contexto_tipo, contexto_tipo),
            "contexto_nome": _buscar_nome_contexto(contexto, headers) if contexto else None,
            "contexto_link": contexto.get("external_urls", {}).get("spotify"),
        },
        "genius": _buscar_letra(track_name, artists),
        "metricas": _buscar_audio_features(item.get("id")),
    })


@app.route("/api/spotify/token")
def api_spotify_token():
    """Token de acesso para o Web Playback SDK (roda no navegador do usuário logado).

    Só devolve o token para quem já tem uma sessão Flask autenticada — nunca é
    exposto publicamente nem logado.
    """
    access_token = _get_valid_spotify_token()
    if not access_token:
        return jsonify({"error": "Não autenticado."}), 401
    return jsonify({"access_token": access_token})


@app.route("/api/spotify/transferir-playback", methods=["POST"])
def api_spotify_transferir_playback():
    access_token = _get_valid_spotify_token()
    if not access_token:
        return jsonify({"error": "Não autenticado."}), 401

    device_id = (request.get_json(silent=True) or {}).get("device_id")
    if not device_id:
        return jsonify({"error": "device_id é obrigatório."}), 400

    resp = requests.put(
        f"{SPOTIFY_API_BASE}/me/player",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"device_ids": [device_id], "play": True},
        timeout=10,
    )
    if resp.status_code not in (200, 204):
        return jsonify({"error": "Falha ao transferir playback.", "detalhe": resp.text}), 502
    return jsonify({"ok": True})


@app.route("/api/spotify/shuffle", methods=["POST"])
def api_spotify_shuffle():
    access_token = _get_valid_spotify_token()
    if not access_token:
        return jsonify({"error": "Não autenticado."}), 401

    corpo = request.get_json(silent=True) or {}
    resp = requests.put(
        f"{SPOTIFY_API_BASE}/me/player/shuffle",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"state": str(bool(corpo.get("state"))).lower(), "device_id": corpo.get("device_id")},
        timeout=10,
    )
    if resp.status_code not in (200, 204):
        return jsonify({"error": "Falha ao alternar modo aleatório."}), 502
    return jsonify({"ok": True})


@app.route("/api/spotify/repeat", methods=["POST"])
def api_spotify_repeat():
    access_token = _get_valid_spotify_token()
    if not access_token:
        return jsonify({"error": "Não autenticado."}), 401

    corpo = request.get_json(silent=True) or {}
    estado = corpo.get("state", "off")
    if estado not in ("off", "context", "track"):
        return jsonify({"error": "state inválido."}), 400

    resp = requests.put(
        f"{SPOTIFY_API_BASE}/me/player/repeat",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"state": estado, "device_id": corpo.get("device_id")},
        timeout=10,
    )
    if resp.status_code not in (200, 204):
        return jsonify({"error": "Falha ao alternar repetição."}), 502
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
