# Playlist Transfer App

[![Render Deployment](https://img.shields.io/badge/Deployed%20on-Render-blue)](https://transferplaylist-2nob.onrender.com)

This is a Flask-based web application that allows users to transfer playlists between **Spotify** and **SoundCloud**. Specifically:

- Transfer playlists from **Spotify to SoundCloud**.
- Transfer playlists from **SoundCloud to Spotify**.

The app uses the **Spotify Web API** and **SoundCloud API** to fetch playlists, search for tracks, and create new playlists on the target platform.

**Live Demo**: [https://transferplaylist-2nob.onrender.com](https://transferplaylist-2nob.onrender.com)

---

## Features

1. **Transfer Playlists from Spotify to SoundCloud**:
   - Fetch playlists from Spotify.
   - Search for matching tracks on SoundCloud.
   - Create a new playlist on SoundCloud with the matched tracks.

2. **Transfer Playlists from SoundCloud to Spotify**:
   - Fetch playlists from SoundCloud.
   - Search for matching tracks on Spotify.
   - Create a new playlist on Spotify with the matched tracks.

3. **User-Friendly Interface**:
   - Clean and responsive design using HTML and CSS.
   - Dynamic feedback during the transfer process.

---

## Technologies Used

- **Backend**: Python (Flask)
- **Frontend**: HTML, CSS
- **APIs**:
  - [Spotify Web API](https://developer.spotify.com/documentation/web-api/)
  - [SoundCloud API](https://developers.soundcloud.com/docs/api/guide)
- **Deployment**: [Render](https://render.com/)
- **Dependencies**:
  - `Flask`: Web framework.
  - `requests`: For making API calls.
  - `gunicorn`: WSGI server for production deployment.

---

## How It Works

1. **Authentication**:
   - Users log in to Spotify or SoundCloud via OAuth to grant access to their playlists.
   - The app securely stores API credentials as environment variables.

2. **Playlist Selection**:
   - After authentication, users can select a playlist from their account.

3. **Track Matching**:
   - The app searches for matching tracks on the target platform using track names and artist names.

4. **Playlist Creation**:
   - A new playlist is created on the target platform, and the matched tracks are added.

5. **Feedback**:
   - The app displays a list of transferred tracks and indicates whether the transfer was successful.

---

## Deployment on Render

This app is deployed on **Render**, a cloud platform for hosting web applications. Follow these steps to deploy your own instance:

### **Step 1: Prepare Your Project**
1. Clone this repository:
   ```bash
   git clone https://github.com/your-username/playlist-transfer-app.git
   cd playlist-transfer-app
   ```

2. Ensure you have the following files:
   - `app.py`: Main Flask application.
   - `Procfile`: Defines how to run the app (`web: gunicorn app:app`).
   - `requirements.txt`: Lists dependencies (`Flask`, `requests`, `gunicorn`).
   - `runtime.txt`: Specifies the Python version (e.g., `python-3.9.18`).

3. Replace placeholder values in the code with your actual API credentials:
   - Spotify Client ID, Client Secret, Redirect URI.
   - SoundCloud Client ID, Client Secret, Redirect URI.

### **Step 2: Push Code to GitHub**
1. Initialize a Git repository:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   ```

2. Push your code to GitHub:
   ```bash
   git remote add origin https://github.com/your-username/playlist-transfer-app.git
   git branch -M main
   git push -u origin main
   ```

### **Step 3: Deploy on Render**
1. Sign up for a free account on [Render](https://render.com/).
2. Connect your GitHub repository to Render.
3. Create a new **Web Service**:
   - Set the build command: `pip install -r requirements.txt`.
   - Set the start command: `gunicorn app:app`.
   - Add environment variables for your API credentials:
     ```
     SPOTIFY_CLIENT_ID=your_spotify_client_id
     SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
     SPOTIFY_REDIRECT_URI=https://your-render-url/callback_spotify
     SOUNDCLOUD_CLIENT_ID=your_soundcloud_client_id
     SOUNDCLOUD_CLIENT_SECRET=your_soundcloud_client_secret
     SOUNDCLOUD_REDIRECT_URI=https://your-render-url/callback_soundcloud
     ```
4. Deploy the app and wait for Render to build and host it.

---

## Usage

1. Visit the live demo: [https://transferplaylist-2nob.onrender.com](https://transferplaylist-2nob.onrender.com).
2. Choose one of the following options:
   - **Transfer from Spotify to SoundCloud**.
   - **Transfer from SoundCloud to Spotify**.
3. Authenticate with the respective platform.
4. Select a playlist and wait for the app to transfer it.

---

## Limitations

1. **Track Matching**:
   - Not all tracks may be found on the target platform due to differences in catalog availability.

2. **API Rate Limits**:
   - Both Spotify and SoundCloud APIs have rate limits. Avoid excessive requests to prevent errors.

3. **Free Tier on Render**:
   - The app may "sleep" after 15 minutes of inactivity on Render's free tier.

---

## Future Improvements

1. **Enhanced Matching**:
   - Use fuzzy matching algorithms to improve track search accuracy.

2. **Error Handling**:
   - Provide more detailed error messages for failed transfers.

3. **Custom Domain**:
   - Upgrade to a paid plan on Render to use a custom domain.

4. **Database Integration**:
   - Store user preferences and transfer history for a better user experience.

---

## Credits

- **Spotify Developer Documentation**: [https://developer.spotify.com/documentation/web-api/](https://developer.spotify.com/documentation/web-api/)
- **SoundCloud Developer Documentation**: [https://developers.soundcloud.com/docs/api/guide](https://developers.soundcloud.com/docs/api/guide)
- **Render Documentation**: [https://render.com/docs](https://render.com/docs)

---

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

---

Feel free to contribute, report issues, or suggest improvements! 🚀
