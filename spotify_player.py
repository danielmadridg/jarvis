"""
Spotify integration via Web API — search, play, control playback.
Requires Premium for playback control.
"""
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI

_sp = None

SCOPE = (
    "user-read-playback-state "
    "user-modify-playback-state "
    "user-read-currently-playing "
    "playlist-read-private "
    "playlist-read-collaborative"
)


def _get_sp():
    """Get authenticated Spotify client (caches token after first login)."""
    global _sp
    if _sp is None:
        cache_path = os.path.join(os.path.dirname(__file__), ".spotify_cache")
        _sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
            redirect_uri=SPOTIFY_REDIRECT_URI,
            scope=SCOPE,
            cache_path=cache_path,
            open_browser=True,
        ))
    return _sp


def get_active_device():
    """Get the active Spotify device, or the first available one."""
    sp = _get_sp()
    devices = sp.devices()
    if not devices or not devices["devices"]:
        return None
    # Prefer active device
    for d in devices["devices"]:
        if d["is_active"]:
            return d["id"]
    # Fallback to first device
    return devices["devices"][0]["id"]


def play_track(query):
    """Search for a track and play it."""
    sp = _get_sp()
    results = sp.search(q=query, type="track", limit=1)
    tracks = results["tracks"]["items"]
    if not tracks:
        print(f"  [spotify] No tracks found for: {query}")
        return False

    track = tracks[0]
    device = get_active_device()
    sp.start_playback(device_id=device, uris=[track["uri"]])
    print(f"  [spotify] Playing: {track['name']} — {track['artists'][0]['name']}")
    return True


def play_artist(query):
    """Search for an artist and play their top tracks."""
    sp = _get_sp()
    results = sp.search(q=query, type="artist", limit=1)
    artists = results["artists"]["items"]
    if not artists:
        return False

    artist = artists[0]
    device = get_active_device()
    sp.start_playback(device_id=device, context_uri=artist["uri"])
    print(f"  [spotify] Playing artist: {artist['name']}")
    return True


def play_playlist_by_name(query):
    """Search user's playlists first, then public playlists."""
    sp = _get_sp()

    # Search user's own playlists first
    playlists = sp.current_user_playlists(limit=50)
    for pl in playlists["items"]:
        if query.lower() in pl["name"].lower():
            device = get_active_device()
            sp.start_playback(device_id=device, context_uri=pl["uri"])
            print(f"  [spotify] Playing your playlist: {pl['name']}")
            return pl["name"]

    # Fallback: search public playlists
    results = sp.search(q=query, type="playlist", limit=1)
    items = results["playlists"]["items"]
    if items:
        device = get_active_device()
        sp.start_playback(device_id=device, context_uri=items[0]["uri"])
        print(f"  [spotify] Playing playlist: {items[0]['name']}")
        return items[0]["name"]

    return None


def play_album(query):
    """Search for an album and play it."""
    sp = _get_sp()
    results = sp.search(q=query, type="album", limit=1)
    albums = results["albums"]["items"]
    if not albums:
        return False

    album = albums[0]
    device = get_active_device()
    sp.start_playback(device_id=device, context_uri=album["uri"])
    print(f"  [spotify] Playing album: {album['name']}")
    return True


def play_search(query):
    """Smart play — tries track, then playlist, then artist."""
    sp = _get_sp()

    # Check user playlists first
    name = play_playlist_by_name(query)
    if name:
        return f"playlist:{name}"

    # Try track
    results = sp.search(q=query, type="track", limit=1)
    if results["tracks"]["items"]:
        track = results["tracks"]["items"][0]
        device = get_active_device()
        sp.start_playback(device_id=device, uris=[track["uri"]])
        return f"track:{track['name']} by {track['artists'][0]['name']}"

    # Try artist
    results = sp.search(q=query, type="artist", limit=1)
    if results["artists"]["items"]:
        artist = results["artists"]["items"][0]
        device = get_active_device()
        sp.start_playback(device_id=device, context_uri=artist["uri"])
        return f"artist:{artist['name']}"

    return None


# ── Playback controls ───────────────────────────────────────────────

def pause():
    sp = _get_sp()
    sp.pause_playback()


def resume():
    sp = _get_sp()
    device = get_active_device()
    sp.start_playback(device_id=device)


def next_track():
    sp = _get_sp()
    sp.next_track()


def previous_track():
    sp = _get_sp()
    sp.previous_track()


def now_playing():
    """Return what's currently playing."""
    sp = _get_sp()
    current = sp.current_playback()
    if not current or not current.get("item"):
        return None
    item = current["item"]
    artist = item["artists"][0]["name"] if item.get("artists") else "Unknown"
    return f"{item['name']} by {artist}"


def get_user_playlists():
    """Return list of user's playlist names."""
    sp = _get_sp()
    playlists = sp.current_user_playlists(limit=50)
    return [pl["name"] for pl in playlists["items"]]
