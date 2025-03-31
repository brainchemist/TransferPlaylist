import logging
import os
from flask import Flask, redirect, request, session, render_template
import requests

app = Flask(__name__)
app.secret_key = "your_secret_key"

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")

SOUNDCLOUD_CLIENT_ID = os.getenv("SOUNDCLOUD_CLIENT_ID")
SOUNDCLOUD_CLIENT_SECRET = os.getenv("SOUNDCLOUD_CLIENT_SECRET")
SOUNDCLOUD_REDIRECT_URI = os.getenv("SOUNDCLOUD_REDIRECT_URI")

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE_URL = "https://api.spotify.com/v1"

SOUNDCLOUD_AUTH_URL = "https://soundcloud.com/connect"
SOUNDCLOUD_TOKEN_URL = "https://api.soundcloud.com/oauth2/token"
SOUNDCLOUD_API_BASE_URL = "https://api.soundcloud.com"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login_spotify")
def login_spotify():
    auth_url = (
        f"{SPOTIFY_AUTH_URL}?client_id={SPOTIFY_CLIENT_ID}"
        "&response_type=code"
        "&redirect_uri=https://transferplaylist-2nob.onrender.com/callback_spotify"
        "&scope=playlist-read-private playlist-modify-private"
    )
    return redirect(auth_url)


@app.route("/callback_spotify")
def callback_spotify():
    code = request.args.get("code")
    if not code:
        return "Authorization failed. No code received.", 400

    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "client_id": SPOTIFY_CLIENT_ID,
        "client_secret": SPOTIFY_CLIENT_SECRET,
    }
    response = requests.post(SPOTIFY_TOKEN_URL, data=token_data)
    if response.status_code != 200:
        return f"Failed to retrieve access token. Error: {response.text}", 500

    session["spotify_token"] = response.json().get("access_token")
    return redirect("/choose_playlist")


@app.route("/login_soundcloud")
def login_soundcloud():
    auth_url = (
        f"{SOUNDCLOUD_AUTH_URL}?client_id={SOUNDCLOUD_CLIENT_ID}"
        "&response_type=code"
        "&redirect_uri=https://transferplaylist-2nob.onrender.com/callback_soundcloud"
        "&scope=non-expiring"
    )
    return redirect(auth_url)


@app.route("/callback_soundcloud")
def callback_soundcloud():
    code = request.args.get("code")
    if not code:
        return "Authorization failed. No code received.", 400

    token_data = {
        "client_id": SOUNDCLOUD_CLIENT_ID,
        "client_secret": SOUNDCLOUD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "redirect_uri": SOUNDCLOUD_REDIRECT_URI,
        "code": code,
    }
    response = requests.post(SOUNDCLOUD_TOKEN_URL, data=token_data)
    if response.status_code != 200:
        return f"Failed to retrieve access token. Error: {response.text}", 500

    session["soundcloud_token"] = response.json().get("access_token")
    return redirect("/choose_playlist_soundcloud")


@app.route("/choose_playlist")
def choose_playlist():
    if not session.get("spotify_token"):
        return redirect("/login_spotify")

    headers = {"Authorization": f"Bearer {session['spotify_token']}"}
    response = requests.get(f"{SPOTIFY_API_BASE_URL}/me/playlists", headers=headers)
    playlists = response.json().get("items", [])

    return render_template("choose_playlist_spotify.html", playlists=playlists)


@app.route("/transfer_playlist_spotify/<playlist_id>")
def transfer_playlist_spotify(playlist_id):
    if not session.get("spotify_token"):
        return redirect("/login_spotify")

    headers = {"Authorization": f"Bearer {session['spotify_token']}"}
    response = requests.get(f"{SPOTIFY_API_BASE_URL}/playlists/{playlist_id}", headers=headers)
    playlist_data = response.json()
    playlist_name = playlist_data.get("name", "Transferred Playlist")
    playlist_description = playlist_data.get("description", "")
    tracks_data = playlist_data.get("tracks", {}).get("items", [])

    track_list = []
    soundcloud_track_ids = []
    for item in tracks_data:
        track = item["track"]
        track_name = track["name"]
        artist_name = track["artists"][0]["name"]
        album_image = track["album"]["images"][0]["url"] if track["album"]["images"] else "/static/default-cover.jpg"
        track_list.append({
            "name": track_name,
            "artist": artist_name,
            "album_image": album_image
        })

        query = f"{track_name} {artist_name}"
        soundcloud_response = requests.get(
            f"{SOUNDCLOUD_API_BASE_URL}/tracks",
            params={"q": query, "client_id": SOUNDCLOUD_CLIENT_ID}
        )
        soundcloud_tracks = soundcloud_response.json()

        logging.info(f"SoundCloud Search Query: {query}")
        logging.info(f"SoundCloud API Response: {soundcloud_tracks}")

        if soundcloud_tracks:
            try:
                soundcloud_track_ids.append(soundcloud_tracks[0]["id"])
            except (IndexError, KeyError):
                print(f"No match found for track: {track_name} by {artist_name}")
        else:
            print(f"No match found for track: {track_name} by {artist_name}")

    success = False
    if soundcloud_track_ids:
        soundcloud_playlist_data = {
            "playlist": {
                "title": playlist_name,
                "sharing": "public",
                "description": f"{playlist_description}\n\nThis playlist was created using TrackPlaylist by Zack - https://transferplaylist-2nob.onrender.com",
                "tracks": [{"id": track_id} for track_id in soundcloud_track_ids]
            }
        }
        headers = {"Authorization": f"OAuth {session.get('soundcloud_token')}"}
        response = requests.post(
            f"{SOUNDCLOUD_API_BASE_URL}/playlists",
            headers=headers,
            json=soundcloud_playlist_data
        )

        print(f"SoundCloud API Response: {response.status_code}")
        print(f"Response Body: {response.text}")

        if response.status_code == 201:
            success = True

    return render_template(
        "transfer_playlist_spotify.html",
        playlist_name=playlist_name,
        tracks=track_list,
        success=success
    )


@app.route("/choose_playlist_soundcloud")
def choose_playlist_soundcloud():
    if not session.get("soundcloud_token"):
        return redirect("/login_soundcloud")

    headers = {"Authorization": f"OAuth {session['soundcloud_token']}"}
    response = requests.get(f"{SOUNDCLOUD_API_BASE_URL}/me/playlists", headers=headers)
    playlists = response.json()

    return render_template("choose_playlist_soundcloud.html", playlists=playlists)


@app.route("/transfer_playlist_soundcloud/<playlist_id>")
def transfer_playlist_soundcloud(playlist_id):
    if not session.get("soundcloud_token"):
        return redirect("/login_soundcloud")

    headers = {"Authorization": f"OAuth {session['soundcloud_token']}"}
    response = requests.get(f"{SOUNDCLOUD_API_BASE_URL}/playlists/{playlist_id}", headers=headers)
    playlist_data = response.json()
    playlist_name = playlist_data.get("title", "Transferred Playlist")
    playlist_description = playlist_data.get("description", "")
    tracks_data = playlist_data.get("tracks", [])

    track_list = []
    spotify_track_uris = []
    for track in tracks_data:
        track_title = track.get("title", "Unknown Track")
        track_artist = track.get("user", {}).get("username", "Unknown Artist")
        track_list.append({
            "name": track_title,
            "artist": track_artist,
        })

        query = f"{track_title} {track_artist}"
        spotify_response = requests.get(
            f"{SPOTIFY_API_BASE_URL}/search",
            headers={"Authorization": f"Bearer {session.get('spotify_token')}"},
            params={"q": query, "type": "track", "limit": 1}
        )
        spotify_tracks = spotify_response.json().get("tracks", {}).get("items", [])
        if spotify_tracks:
            spotify_track_uris.append(spotify_tracks[0]["uri"])

    success = False
    if spotify_track_uris:
        user_response = requests.get(
            f"{SPOTIFY_API_BASE_URL}/me",
            headers={"Authorization": f"Bearer {session.get('spotify_token')}"}
        )
        user_id = user_response.json().get("id")
        playlist_data = {
            "name": playlist_name,
            "description": f"{playlist_description}\n\nThis playlist was created using TrackPlaylist by Zack - https://transferplaylist-2nob.onrender.com",
            "public": False
        }
        create_playlist_response = requests.post(
            f"{SPOTIFY_API_BASE_URL}/users/{user_id}/playlists",
            headers={"Authorization": f"Bearer {session.get('spotify_token')}", "Content-Type": "application/json"},
            json=playlist_data
        )
        playlist_id_spotify = create_playlist_response.json().get("id")
        if playlist_id_spotify:
            add_tracks_response = requests.post(
                f"{SPOTIFY_API_BASE_URL}/playlists/{playlist_id_spotify}/tracks",
                headers={"Authorization": f"Bearer {session.get('spotify_token')}", "Content-Type": "application/json"},
                json={"uris": spotify_track_uris}
            )
            if add_tracks_response.status_code == 201:
                success = True

    return render_template(
        "transfer_playlist_soundcloud.html",
        playlist_name=playlist_name,
        tracks=track_list,
        success=success
    )


if __name__ == "__main__":
    app.run(debug=True)