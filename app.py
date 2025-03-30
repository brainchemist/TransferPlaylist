import json

from flask import Flask, redirect, request, session
import requests

app = Flask(__name__)
app.secret_key = "your_secret_key"

with open("spotify_credentials.json", "r") as spotify_file:
    spotify_credentials = json.load(spotify_file)

with open("soundcloud_credentials.json", "r") as soundcloud_file:
    soundcloud_credentials = json.load(soundcloud_file)

# Access credentials
SPOTIFY_CLIENT_ID = spotify_credentials["client_id"]
SPOTIFY_CLIENT_SECRET = spotify_credentials["client_secret"]
SPOTIFY_REDIRECT_URI = spotify_credentials["redirect_uri"]

SOUNDCLOUD_CLIENT_ID = soundcloud_credentials["client_id"]
SOUNDCLOUD_CLIENT_SECRET = soundcloud_credentials["client_secret"]
SOUNDCLOUD_REDIRECT_URI = soundcloud_credentials["redirect_uri"]

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE_URL = "https://api.spotify.com/v1"

SOUNDCLOUD_AUTH_URL = "https://soundcloud.com/connect"
SOUNDCLOUD_TOKEN_URL = "https://api.soundcloud.com/oauth2/token"

@app.route("/")
def index():
    return """
    <a href="/login_spotify">Login with Spotify</a><br>
    <a href="/login_soundcloud">Login with SoundCloud</a>
    """

@app.route("/login_spotify")
def login_spotify():
    auth_url = f"{SPOTIFY_AUTH_URL}?client_id={SPOTIFY_CLIENT_ID}&response_type=code&redirect_uri={SPOTIFY_REDIRECT_URI}&scope=playlist-read-private"
    return redirect(auth_url)

@app.route("/callback_spotify")
def callback_spotify():
    code = request.args.get("code")
    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "client_id": SPOTIFY_CLIENT_ID,
        "client_secret": SPOTIFY_CLIENT_SECRET,
    }
    response = requests.post(SPOTIFY_TOKEN_URL, data=token_data)
    session["spotify_token"] = response.json().get("access_token")
    return "Spotify login successful!"

@app.route("/login_soundcloud")
def login_soundcloud():
    auth_url = f"{SOUNDCLOUD_AUTH_URL}?client_id={SOUNDCLOUD_CLIENT_ID}&response_type=code&redirect_uri={SOUNDCLOUD_REDIRECT_URI}&scope=non-expiring"
    return redirect(auth_url)

@app.route("/callback_soundcloud")
def callback_soundcloud():
    code = request.args.get("code")
    token_data = {
        "client_id": SOUNDCLOUD_CLIENT_ID,
        "client_secret": SOUNDCLOUD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "redirect_uri": SOUNDCLOUD_REDIRECT_URI,
        "code": code,
    }
    response = requests.post(SOUNDCLOUD_TOKEN_URL, data=token_data)
    session["soundcloud_token"] = response.json().get("access_token")
    return "SoundCloud login successful!"

@app.route("/choose_playlist")
def choose_playlist():
    if "spotify_token" not in session:
        return redirect("/login_spotify")

    headers = {"Authorization": f"Bearer {session['spotify_token']}"}
    response = requests.get(f"{SPOTIFY_API_BASE_URL}/me/playlists", headers=headers)
    playlists = response.json().get("items", [])

    # Render a list of playlists for the user to choose from
    playlist_html = "<h2>Select a Playlist to Transfer:</h2>"
    playlist_html += "<ul>"
    for playlist in playlists:
        playlist_id = playlist["id"]
        playlist_name = playlist["name"]
        playlist_html += f'<li><a href="/transfer_playlist/{playlist_id}">{playlist_name}</a></li>'
    playlist_html += "</ul>"
    return playlist_html

@app.route("/transfer_playlist/<playlist_id>")
def transfer_playlist(playlist_id):
    if "spotify_token" not in session:
        return redirect("/login_spotify")

    headers = {"Authorization": f"Bearer {session['spotify_token']}"}
    response = requests.get(f"{SPOTIFY_API_BASE_URL}/playlists/{playlist_id}/tracks", headers=headers)
    tracks = response.json().get("items", [])

    track_list = []
    for item in tracks:
        track = item["track"]
        track_name = track["name"]
        artist_name = track["artists"][0]["name"]
        track_list.append(f"{track_name} by {artist_name}")


    transfer_html = "<h2>Transferring Tracks:</h2>"
    transfer_html += "<ul>"
    for track in track_list:
        transfer_html += f"<li>{track}</li>"
    transfer_html += "</ul>"
    transfer_html += "<p>Tracks transferred successfully!</p>"
    return transfer_html

if __name__ == "__main__":
    app.run(debug=True)