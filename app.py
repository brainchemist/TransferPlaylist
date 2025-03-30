import json

from flask import Flask, redirect, request, session, render_template
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
    return render_template("index.html")


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
    return choose_playlist()


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
    return choose_playlist()


@app.route("/choose_playlist")
def choose_playlist():
    if "spotify_token" not in session:
        return redirect("/login_spotify")

    headers = {"Authorization": f"Bearer {session['spotify_token']}"}
    response = requests.get(f"{SPOTIFY_API_BASE_URL}/me/playlists", headers=headers)
    playlists = response.json().get("items", [])

    return render_template("choose_playlist.html", playlists=playlists)


@app.route("/transfer_playlist/<playlist_id>")
def transfer_playlist(playlist_id):
    if "spotify_token" not in session:
        return redirect("/login_spotify")

    headers = {"Authorization": f"Bearer {session['spotify_token']}"}
    response = requests.get(f"{SPOTIFY_API_BASE_URL}/playlists/{playlist_id}/tracks", headers=headers)
    tracks_data = response.json().get("items", [])

    track_list = []
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

    return render_template("transfer_playlist.html", tracks=track_list)


if __name__ == "__main__":
    app.run(debug=True)
