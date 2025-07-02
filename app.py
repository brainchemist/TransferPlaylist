import json
import re
import logging
import os
import io
import time
from flask import Flask, redirect, request, session, render_template
import requests
import base64

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


def find_best_match(track_name, artist_name, soundcloud_tracks):
    for track in soundcloud_tracks:
        if isinstance(track, dict):
            logging.info(f"Picked first match for '{track_name}' by '{artist_name}': {track.get('title')}")
            return track
    logging.warning(f"No valid track dict found for: {track_name}")
    return None


def clean_track_query(title, artist):
    title = re.sub(r"\(.*?\)|\[.*?\]|- .*", "", title)
    title = title.replace("feat.", "").replace("ft.", "").lower()
    return f"{title.strip()} {artist.lower().strip()}"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login_spotify")
def login_spotify():
    redirect_after = request.args.get("redirect", "/choose_playlist")
    session["post_spotify_redirect"] = redirect_after
    auth_url = (
        f"{SPOTIFY_AUTH_URL}?client_id={SPOTIFY_CLIENT_ID}"
        "&response_type=code"
        f"&redirect_uri={SPOTIFY_REDIRECT_URI}"
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
    return redirect(session.pop("post_spotify_redirect", "/choose_playlist"))


@app.route("/login_soundcloud")
def login_soundcloud():
    redirect_after = request.args.get("redirect", request.referrer or "/")
    session["post_soundcloud_redirect"] = redirect_after
    auth_url = (
        f"{SOUNDCLOUD_AUTH_URL}?client_id={SOUNDCLOUD_CLIENT_ID}"
        "&response_type=code"
        f"&redirect_uri={SOUNDCLOUD_REDIRECT_URI}"
        "&scope=non-expiring"
    )
    return redirect(auth_url)


@app.route("/callback")
def callback_soundcloud():
    code = request.args.get("code")
    if not code:
        logging.error("Authorization failed. No code received.")
        return "Authorization failed. No code received.", 400

    token_data = {
        "client_id": SOUNDCLOUD_CLIENT_ID,
        "client_secret": SOUNDCLOUD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "redirect_uri": SOUNDCLOUD_REDIRECT_URI,
        "code": code,
    }

    response = requests.post(SOUNDCLOUD_TOKEN_URL, data=token_data)
    logging.debug(f"[DEBUG] SoundCloud token response: {response.text}")

    if response.status_code != 200:
        logging.error(f"Failed to retrieve access token. Error: {response.text}")
        return f"Failed to retrieve access token. Error: {response.text}", 500

    token_json = response.json()
    access_token = token_json.get("access_token")
    logging.debug(f"[DEBUG] Received access token: {access_token}")
    session["soundcloud_token"] = access_token

    if "transfer_url" not in session or "transfer_direction" not in session:
        logging.warning("[WARNING] Missing transfer session. Attempting recovery fallback.")
        playlist_url = request.args.get("playlist_url")
        if playlist_url:
            session["transfer_url"] = playlist_url
            session["transfer_direction"] = "soundcloud_to_spotify"
            logging.debug(f"[DEBUG] Recovered transfer_url from query: {playlist_url}")
        else:
            logging.debug("[DEBUG] No playlist_url in query. Recovery not possible.")

    redirect_to = session.pop("post_soundcloud_redirect", "/")
    logging.debug(f"[DEBUG] Redirecting to: {redirect_to}")
    return redirect(redirect_to)


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
    if not session.get("soundcloud_token"):
        logging.warning("User is not logged into SoundCloud. Redirecting to login.")
        return redirect("/login_soundcloud")

    headers = {"Authorization": f"Bearer {session['spotify_token']}"}
    response = requests.get(f"{SPOTIFY_API_BASE_URL}/playlists/{playlist_id}", headers=headers)
    if response.status_code != 200:
        logging.error(
            f"Failed to fetch Spotify playlist. Status Code: {response.status_code}, Response: {response.text}")
        return render_template("transfer_playlist_spotify.html", playlist_name="Unknown Playlist", tracks=[],
                               success=False, message="Failed to fetch playlist from Spotify. Please try again.")

    playlist_data = response.json()
    playlist_name = playlist_data.get("name", "Transferred Playlist")
    playlist_description = playlist_data.get("description", "")
    tracks_data = playlist_data.get("tracks", {}).get("items", [])
    track_list = []
    soundcloud_track_ids = []

    for item in tracks_data:
        track = item.get("track")
        if not track:
            logging.warning("Skipped a None track (possibly deleted or unavailable).")
            continue

        track_name = track.get("name", "Unknown Track")
        artist_name = track.get("artists", [{}])[0].get("name", "Unknown Artist")
        album_image = track.get("album", {}).get("images", [{}])[0].get("url", "/static/default-cover.jpg")

        track_list.append({
            "name": track_name,
            "artist": artist_name,
            "album_image": album_image
        })

        fallback_queries = [
            clean_track_query(track_name, artist_name),
            track_name.lower(),
            f"{track_name} {artist_name.split(' ')[0]}".lower()
        ]

        token = session.get("soundcloud_token")
        soundcloud_tracks = []

        for query in fallback_queries:
            logging.info(f"Searching SoundCloud for: {query}")
            soundcloud_response = requests.get(
                f"{SOUNDCLOUD_API_BASE_URL}/tracks",
                headers={"Authorization": f"OAuth {token}"},
                params={"q": query, "limit": 5}
            )
            time.sleep(0.15)

            if soundcloud_response.status_code == 401:
                logging.error("SoundCloud token expired or invalid. Forcing re-login.")
                session.pop("soundcloud_token", None)
                return redirect("/login_soundcloud")

            logging.info(f"SoundCloud Search Query: {query}")
            logging.info(f"SoundCloud API Raw Response: {soundcloud_response.text}")

            if soundcloud_response.status_code == 200:
                try:
                    soundcloud_tracks = soundcloud_response.json()
                    if isinstance(soundcloud_tracks, list) and soundcloud_tracks:
                        break
                    else:
                        logging.warning("No valid tracks returned in this query.")
                except ValueError:
                    logging.error("Invalid JSON response from SoundCloud API.")
            else:
                logging.error(f"SoundCloud API Error: {soundcloud_response.status_code}, {soundcloud_response.text}")

        if soundcloud_tracks:
            logging.info(f"Got {len(soundcloud_tracks)} tracks from SoundCloud for {track_name}")
            best_match = find_best_match(track_name, artist_name, soundcloud_tracks)
            if best_match:
                soundcloud_track_ids.append(best_match["id"])
            else:
                logging.warning(f"No match found for track: {track_name} by {artist_name}")
        else:
            logging.warning(f"No results found for query: {query}")

    if not soundcloud_track_ids:
        return render_template("transfer_playlist_spotify.html", playlist_name=playlist_name, tracks=track_list,
                               success=False,
                               message="No matching tracks found on SoundCloud. Some tracks may not be available.")

    image_url = playlist_data.get("images", [{}])[0].get("url")
    image_data = None
    valid_image = False

    if image_url:
        image_response = requests.get(image_url)
        if image_response.status_code == 200:
            content_type = image_response.headers.get("Content-Type", "")
            if "jpeg" in content_type or image_url.lower().endswith(".jpg"):
                raw_image = image_response.content
                if len(raw_image) < 2 * 1024 * 1024:
                    image_data = io.BytesIO(raw_image)
                    image_data.name = "cover.jpg"
                    valid_image = True

    files_list = [
        ("playlist[title]", (None, playlist_name)),
        ("playlist[sharing]", (None, "public")),
        ("playlist[description]", (None,
                                   f"{playlist_description}\n\nThis playlist was created using TrackPlaylist by Zack - https://transferplaylist-2nob.onrender.com")),
    ]

    # Append all track IDs correctly
    for track_id in soundcloud_track_ids:
        files_list.append(("playlist[tracks][][id]", (None, str(track_id))))

    # Append image if available
    if valid_image and image_data:
        files_list.append(("playlist[artwork_data]", ("cover.jpg", image_data, "image/jpeg")))
        logging.info("Playlist image attached successfully.")
    else:
        logging.warning("Skipping image upload due to invalid image format or size.")

    response = requests.post(
        f"{SOUNDCLOUD_API_BASE_URL}/playlists",
        headers={"Authorization": f"OAuth {session['soundcloud_token']}"},
        files=files_list
    )

    if response.status_code != 201:
        logging.error(
            f"Failed to create SoundCloud playlist. Status Code: {response.status_code}, Response: {response.text}")
        return render_template("transfer_playlist_spotify.html", playlist_name=playlist_name, tracks=track_list,
                               success=False, message="Failed to create playlist on SoundCloud. Please try again.")

    return render_template("transfer_playlist_spotify.html", playlist_name=playlist_name, tracks=track_list,
                           success=True, message="Playlist created successfully!")


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
    access_token = session.get("soundcloud_token")
    if not access_token:
        return redirect("/login_soundcloud")

    # Fetch SoundCloud playlist
    headers = {"Authorization": f"OAuth {access_token}"}
    playlist_response = requests.get(f"https://api.soundcloud.com/playlists/{playlist_id}", headers=headers)
    if playlist_response.status_code != 200:
        return "Failed to fetch SoundCloud playlist", 400
    playlist_data = playlist_response.json()

    playlist_title = playlist_data.get("title", "Untitled Playlist")
    tracks_data = playlist_data.get("tracks", [])
    print(f"[DEBUG] Transferring SoundCloud playlist: '{playlist_title}', with {len(tracks_data)} tracks")

    # Check Spotify token and refresh if needed
    token_check = requests.get(
        f"{SPOTIFY_API_BASE_URL}/me",
        headers={"Authorization": f"Bearer {session.get('spotify_token')}"}
    )
    if token_check.status_code == 401:
        session.pop("spotify_token", None)
        return redirect("/login_spotify")

    # Get Spotify user ID
    user_response = requests.get(
        f"{SPOTIFY_API_BASE_URL}/me",
        headers={"Authorization": f"Bearer {session['spotify_token']}"}
    )
    if user_response.status_code != 200:
        return "Failed to fetch Spotify user info", 400
    user_id = user_response.json().get("id")
    print(f"[DEBUG] Spotify user ID: {user_id}")

    # Create the Spotify playlist (without description)
    playlist_json = {
        "name": playlist_title,
        "public": False
    }
    print(f"[DEBUG] Final Playlist JSON: {json.dumps(playlist_json)}")
    create_response = requests.post(
        f"{SPOTIFY_API_BASE_URL}/users/{user_id}/playlists",
        headers={
            "Authorization": f"Bearer {session['spotify_token']}",
            "Content-Type": "application/json"
        },
        data=json.dumps(playlist_json)
    )
    print(f"[DEBUG] Create playlist → Status: {create_response.status_code}")
    print(f"[DEBUG] Response: {create_response.text}")
    if create_response.status_code != 201:
        print("[DEBUG] Failed to create Spotify playlist")
        return "Failed to create Spotify playlist", 400

    spotify_playlist_id = create_response.json().get("id")

    # Search for each track on Spotify
    track_uris = []
    for track in tracks_data:
        track_title = track.get("title", "Unknown Track")
        track_artist = track.get("user", {}).get("username", "Unknown Artist")
        query = f'track:"{track_title}" artist:"{track_artist}"'
        print(f"[DEBUG] Searching: {query}", end="")

        search_response = requests.get(
            f"{SPOTIFY_API_BASE_URL}/search",
            headers={"Authorization": f"Bearer {session['spotify_token']}"},
            params={"q": query, "type": "track", "limit": 1}
        )
        print(
            f" → Found: {search_response.status_code == 200 and search_response.json().get('tracks', {}).get('items')}")
        if search_response.status_code == 200:
            search_json = search_response.json()
            items = search_json.get("tracks", {}).get("items")
            if items:
                track_uri = items[0].get("uri")
                if track_uri:
                    track_uris.append(track_uri)

    # Add tracks to the new Spotify playlist
    if track_uris:
        add_response = requests.post(
            f"{SPOTIFY_API_BASE_URL}/playlists/{spotify_playlist_id}/tracks",
            headers={"Authorization": f"Bearer {session['spotify_token']}", "Content-Type": "application/json"},
            data=json.dumps({"uris": track_uris})
        )
        print(f"[DEBUG] Added tracks → Status: {add_response.status_code}")
        if add_response.status_code != 201:
            return "Failed to add tracks to Spotify playlist", 400

    return render_template("transfer_playlist_soundcloud.html", playlist_name=playlist_title, )


@app.route("/transfer_from_url")
def transfer_from_url():
    playlist_url = request.args.get("playlist_url")
    if not playlist_url:
        playlist_url = session.get("playlist_url")
    else:
        session["playlist_url"] = playlist_url

    if not playlist_url:
        return "Missing playlist URL", 400

    if "open.spotify.com/playlist" in playlist_url:
        session["direction"] = "spotify_to_soundcloud"
        return redirect("/login_spotify?redirect=/complete_transfer")

    elif "soundcloud.com" in playlist_url:
        return handle_soundcloud_link(playlist_url)

    return "Unsupported playlist link format", 400


def handle_spotify_link(url):
    try:
        playlist_id = url.split("playlist/")[1].split("?")[0]
    except IndexError:
        return "Invalid Spotify playlist URL", 400

    token = session.get("spotify_token")
    if not token:
        # Save current state and redirect back here after login
        session["post_spotify_redirect"] = f"/transfer_from_url?playlist_url={url}"
        return redirect("/login_spotify")

    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{SPOTIFY_API_BASE_URL}/playlists/{playlist_id}", headers=headers)
    if r.status_code != 200:
        return f"Failed to fetch Spotify playlist: {r.text}", 400

    playlist_data = r.json()
    tracks = []
    for item in playlist_data.get("tracks", {}).get("items", []):
        track = item.get("track")
        if not track:
            continue
        title = track.get("name")
        artist = track.get("artists", [{}])[0].get("name")
        if title and artist:
            tracks.append({"name": title, "artist": artist})

    # Store playlist image and name if available
    image_url = playlist_data.get("images", [{}])[0].get("url")
    playlist_name = playlist_data.get("name", "Transferred Playlist")

    session["tracks_to_transfer"] = tracks
    session["transfer_direction"] = "spotify_to_soundcloud"
    session["playlist_image_url"] = image_url
    session["playlist_name"] = playlist_name

    return redirect("/login_soundcloud?redirect=/complete_transfer")


def handle_soundcloud_link(url):
    access_token = session.get("soundcloud_token")
    print(f"[DEBUG] Access Token: {access_token}")
    if not access_token:
        # Save the URL and redirect for login
        session["playlist_url"] = url
        session["transfer_direction"] = "soundcloud_to_spotify"
        return redirect("/login_soundcloud?redirect=/transfer_from_url")

    resolve_url = "https://api.soundcloud.com/resolve"
    headers = {
        "Authorization": f"OAuth {access_token}"
    }
    params = {
        "url": url
    }

    res = requests.get(resolve_url, headers=headers, params=params)
    if res.status_code != 200:
        return f"Failed to resolve SoundCloud URL: {res.text}", 400

    playlist = res.json()
    session["playlist_title"] = playlist.get("title", "Transferred from SoundCloud")
    session["playlist_artwork_url"] = playlist.get("artwork_url")
    tracks = []

    for track in playlist.get("tracks", []):
        title = track.get("title")
        artist = track.get("user", {}).get("username")
        if title and artist:
            tracks.append(f"{title} {artist}")

    session["tracks_to_transfer"] = tracks
    session["transfer_direction"] = "soundcloud_to_spotify"
    return redirect("/login_spotify?redirect=/complete_transfer")


@app.route("/complete_transfer")
def complete_transfer():
    tracks = session.get("tracks_to_transfer", [])
    direction = session.get("transfer_direction")

    if not tracks or not direction:
        return "No transfer session found", 400

    added_tracks = []
    failed_tracks = []

    if direction == "spotify_to_soundcloud":
        sc_token = session.get("soundcloud_token")
        if not sc_token:
            return redirect("/login_soundcloud?redirect=/complete_transfer")

        headers = {
            "Authorization": f"OAuth {sc_token}"
        }

        for track in tracks:
            query = f"{track['name']} {track['artist']}"
            print(f"[DEBUG] Searching SoundCloud for: {query}")
            try:
                response = requests.get(
                    f"{SOUNDCLOUD_API_BASE_URL}/tracks",
                    headers=headers,
                    params={"q": query, "limit": 1}
                )
                response.raise_for_status()
                results = response.json()
                if results:
                    t = results[0]
                    added_tracks.append({
                        "name": t["title"],
                        "artist": t["user"]["username"],
                        "id": t["id"]
                    })
                else:
                    failed_tracks.append(query)
            except Exception as e:
                print(f"[ERROR] SoundCloud search failed for {query}: {e}")
                failed_tracks.append(query)

        if not added_tracks:
            return "No tracks were matched on SoundCloud", 400

        try:
            playlist_data = {
                "playlist": {
                    "title": "Transferred from Spotify",
                    "sharing": "public",
                    "tracks": [{"id": t["id"]} for t in added_tracks]
                }
            }

            playlist_response = requests.post(
                f"{SOUNDCLOUD_API_BASE_URL}/playlists",
                headers=headers,
                json=playlist_data
            )
            playlist_response.raise_for_status()
            playlist = playlist_response.json()
        except Exception as e:
            return f"Failed to create SoundCloud playlist: {e}", 500

        return render_template(
            "transfer_success.html",
            playlist_name=playlist["title"],
            tracks=added_tracks,
            success=True
        )

    elif direction == "soundcloud_to_spotify":
        sp_token = session.get("spotify_token")
        if not sp_token:
            return redirect("/login_spotify?redirect=/complete_transfer")

        headers = {"Authorization": f"Bearer {sp_token}"}

        try:
            user_info = requests.get(f"{SPOTIFY_API_BASE_URL}/me", headers=headers).json()
            user_id = user_info["id"]

            playlist_data = {"name": "Transferred from SoundCloud", "public": False}
            playlist_response = requests.post(
                f"{SPOTIFY_API_BASE_URL}/users/{user_id}/playlists",
                headers=headers,
                json=playlist_data
            ).json()
            playlist_id = playlist_response["id"]

            image_url = session.pop("playlist_artwork_url", None)
            if image_url:
                image_url = image_url.replace("-large", "-t500x500")  # Higher resolution
                try:
                    img_response = requests.get(image_url)
                    if img_response.status_code == 200:
                        image_data = img_response.content
                        encoded_image = base64.b64encode(image_data).decode('utf-8')
                        upload_headers = {
                            "Authorization": f"Bearer {sp_token}",
                            "Content-Type": "image/jpeg"
                        }
                        upload_cover = requests.put(
                            f"{SPOTIFY_API_BASE_URL}/playlists/{playlist_id}/images",
                            headers=upload_headers,
                            data=encoded_image
                        )
                        if upload_cover.status_code == 202:
                            print("[DEBUG] Playlist cover uploaded successfully")
                        else:
                            print(
                                f"[WARNING] Failed to upload cover image: {upload_cover.status_code}, {upload_cover.text}")
                except Exception as e:
                    print(f"[ERROR] Error downloading/uploading cover image: {e}")

        except Exception as e:
            return f"Failed to create Spotify playlist: {e}", 500

        track_uris = []
        for query in tracks:
            try:
                r = requests.get(
                    f"{SPOTIFY_API_BASE_URL}/search",
                    headers=headers,
                    params={"q": query, "type": "track", "limit": 1}
                )
                r.raise_for_status()
                items = r.json().get("tracks", {}).get("items", [])
                if items:
                    track = items[0]
                    track_uris.append(track["uri"])
                    added_tracks.append({
                        "name": track["name"],
                        "artist": track["artists"][0]["name"]
                    })
                else:
                    failed_tracks.append(query)
            except Exception as e:
                print(f"[ERROR] Spotify search failed for {query}: {e}")
                failed_tracks.append(query)

        if track_uris:
            try:
                requests.post(
                    f"{SPOTIFY_API_BASE_URL}/playlists/{playlist_id}/tracks",
                    headers=headers,
                    json={"uris": track_uris}
                )
            except Exception as e:
                return f"Failed to add tracks to Spotify playlist: {e}", 500

        return render_template(
            "transfer_success.html",
            playlist_name="Transferred from SoundCloud",
            tracks=added_tracks,
            success=len(added_tracks) > 0
        )

    return "Unknown transfer direction", 400
