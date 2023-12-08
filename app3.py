# from recom3 import main as generate_playlists
# import recom3
from flask import Flask, render_template, request, session, redirect, url_for
import requests
import logging
import os
# from recommendations import get_recommendations, create_playlist_on_spotify
# import new_recom1
# import recom2
import recom6
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24))
logging.basicConfig(level=logging.INFO)

SPOTIFY_CLIENT_ID = '9896c76ec59140e9b8272264405314c8'
SPOTIFY_CLIENT_SECRET = '634c9e958451472a9244b1824c071557'
SPOTIFY_REDIRECT_URI = 'http://localhost:8000/callback'
SPOTIFY_REFRESH_TOKEN = 'AQBoEl92bv-v62DSPu5wYKfNKdmysVBcYVVHtWB15Bn6W7GglCr_xz3jNPVy1rH8Xch3bPOWzMhTop4XgqP3-jO2-ggsmNY-csNnb8SJ3ypFsQ6MY1yUQ1xxeUXLCvjdJFQ'

def exchange_code_for_tokens(code):
    token_url = 'https://accounts.spotify.com/api/token'
    token_data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': SPOTIFY_REDIRECT_URI,
        'client_id': SPOTIFY_CLIENT_ID,
        'client_secret': SPOTIFY_CLIENT_SECRET
    }
    try:
        response = requests.post(token_url, data=token_data)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.error(f'Error during token exchange: {e}')
        return None

def refresh_access_token(refresh_token):
    token_url = 'https://accounts.spotify.com/api/token'
    token_data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': SPOTIFY_CLIENT_ID,
        'client_secret': SPOTIFY_CLIENT_SECRET
    }
    try:
        response = requests.post(token_url, data=token_data)
        response.raise_for_status()
        return response.json().get('access_token')
    except requests.RequestException as e:
        logging.error(f'Error refreshing token: {e}')
        return None

@app.route('/')
def index():
    return render_template('index3.html')

@app.route('/login')
def login():
    scope = 'user-top-read playlist-modify-public'
    auth_url = f"https://accounts.spotify.com/authorize?client_id={SPOTIFY_CLIENT_ID}&response_type=code&redirect_uri={SPOTIFY_REDIRECT_URI}&scope={scope}"
    return redirect(auth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        logger.error("No code received in callback.")
        return redirect(url_for('error'))

    tokens = exchange_code_for_tokens(code)
    if not tokens:
        logger.error("Failed to exchange code for tokens.")
        return redirect(url_for('error'))

    session['access_token'] = tokens.get('access_token')
    session['refresh_token'] = tokens.get('refresh_token')

    if not session.get('access_token'):
        logger.error("Access token missing after exchange.")
        return redirect(url_for('error'))

    # Fetch user profile data to get user_id
    user_profile = fetch_user_profile(session['access_token'])
    if user_profile:
        session['user_id'] = user_profile.get('id')
    else:
        logger.error("Failed to fetch user profile.")
        return redirect(url_for('error'))

    return redirect(url_for('recommendations'))

def fetch_user_profile(access_token):
    """Fetch user profile data from Spotify."""
    url = 'https://api.spotify.com/v1/me'
    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f'Error fetching user profile: {e}')
        return None

# def callback():
#     code = request.args.get('code')
#     if not code:
#         logging.error("No code received in callback.")
#         return redirect(url_for('error'))

#     tokens = exchange_code_for_tokens(code)
#     if not tokens:
#         logging.error("Failed to exchange code for tokens.")
#         return redirect(url_for('error'))

#     session['access_token'] = tokens.get('access_token')
#     session['refresh_token'] = tokens.get('refresh_token') or SPOTIFY_REFRESH_TOKEN

#     if not session.get('access_token'):
#         logging.error("Access token missing after exchange.")
#         return redirect(url_for('error'))

#     return redirect(url_for('recommendations'))

@app.route('/recommendations')
def recommendations():
    access_token = refresh_access_token(session.get('refresh_token'))
    if not access_token:
        return redirect(url_for('login'))

    # Call the main function from recom2.py
    playlist_links = recom6.main(access_token, session['user_id'])
    return render_template('recommendations3.html', playlist_links=playlist_links)

@app.route('/create_playlist', methods=['POST'])
def create_playlist():
    access_token = refresh_access_token(session.get('refresh_token'))
    if not access_token:
        logger.error('Access token is missing.')
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    if not user_id:
        logger.error('User ID is missing.')
        return redirect(url_for('error'))

    try:
        playlist_links = recom6.main(access_token, user_id)
        return render_template('success_og1.html', playlist_links=playlist_links)
    except Exception as e:
        logger.error(f'Error during playlist creation: {e}')
        return redirect(url_for('error'))

@app.route('/generate_playlists', methods=['GET', 'POST'])
def generate_playlists():
    access_token = session.get('access_token')
    user_id = session.get('user_id')

    if not access_token or not user_id:
        return redirect(url_for('login'))

    try:
        # Call the main function from recom2.py
        playlist_links = recom6.main(access_token,  user_id)
        return render_template('success_og3.html', playlist_links=playlist_links)
    except Exception as e:
        logger.error(f"Error during playlist generation: {e}")
        return redirect(url_for('error'))







# @app.route('/recommendations')
# def recommendations():
#     access_token = refresh_access_token(session.get('refresh_token'))
#     if not access_token:
#         return redirect(url_for('login'))

#     recommendations_data = new_recom1.get_recommendations(access_token)
#     return render_template('recommendations1.html', recommendations=recommendations_data)



# # def recommendations():
# #     access_token = refresh_access_token(session.get('refresh_token'))
# #     if not access_token:
# #         return redirect(url_for('login'))

# #     # Get recommendations
# #     # Assuming get_recommendations function returns data suitable for rendering in recommendations.html
# #     recommendations_data = new_recom.get_recommendations(access_token)
# #     return render_template('recommendations.html', recommendations=recommendations_data)


# # @app.route('/recommendations')
# # def recommendations():
# #     access_token = refresh_access_token(session.get('refresh_token'))
# #     if not access_token:
# #         return redirect(url_for('login'))
# #     # Fetch recommendations using the refreshed access token
# #     # ...
# #     return render_template('recommendations.html')



# # @app.route('/create_playlist', methods=['POST'])
# # def create_playlist():
# #     try:
# #         access_token = session.get('access_token')
# #         if not access_token:
# #             app.logger.error('Access token is missing.')
# #             return redirect(url_for('login'))

# #         user_id = request.form.get('user_id')
# #         track_uris = request.form.get('track_uris')  # Ensure this is correct

# #         if not user_id or not track_uris:
# #             app.logger.error('User ID or Track URIs are missing.')
# #             return redirect(url_for('error'))

# #         playlist_url = new_recom.main(access_token, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI, user_id)

# #         return render_template('success.html', playlist_url=playlist_url)
# #     except Exception as e:
# #         app.logger.error(f'Error during playlist creation: {e}')
# #         return redirect(url_for('error'))

# @app.route('/create_playlist', methods=['POST'])
# def create_playlist():
#     try:
#         access_token = session.get('access_token')
#         if not access_token:
#             logger.error('Access token is missing.')
#             return redirect(url_for('login'))

#         user_id = session.get('user_id')
#         if not user_id:
#             logger.error('User ID is missing.')
#             return redirect(url_for('error'))
        
#         playlist_links = new_recom1.main(access_token, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI, user_id)

#         for playlist_name, playlist_url in playlist_links.items():
#             logger.info(f"{playlist_name} Playlist URL: {playlist_url}")

#         return render_template('success_og1.html', playlist_links=playlist_links)
#     except Exception as e:
#         logger.error(f'Error during playlist creation: {e}')
#         return redirect(url_for('error'))

# @app.route('/generate_playlists', methods=['GET', 'POST'])
# def generate_playlists():
#     access_token = session.get('access_token')
#     user_id = session.get('user_id')

#     if not access_token or not user_id:
#         return redirect(url_for('login'))

#     try:
#         playlist_links = new_recom1.main(access_token, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI, user_id)

#         return render_template('success_og1.html', playlist_links=playlist_links)
#     except Exception as e:
#         logging.error(f"Error during playlist generation: {e}")
#         return redirect(url_for('error'))





# @app.route('/create_playlist', methods=['POST'])
# def create_playlist():
#     try:
#         access_token = session.get('access_token')
#         if not access_token:
#             logger.error('Access token is missing.')
#             return redirect(url_for('login'))

#         user_id = session.get('user_id')
#         if not user_id:
#             logger.error('User ID is missing.')
#             return redirect(url_for('error'))
        
#         playlist_links = new_recom.main(access_token, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI, user_id)

#         # Logging for debugging
#         for playlist_name, playlist_url in playlist_links.items():
#             logger.info(f"{playlist_name} Playlist URL: {playlist_url}")

#         return render_template('success_og.html', playlist_links=playlist_links)
#     except Exception as e:
#         logger.error(f'Error during playlist creation: {e}')
#         return redirect(url_for('error'))
# # @app.route('/create_playlist', methods=['POST'])
# # # def create_playlist():##working this use later
# #     try:
# #         access_token = session.get('access_token')
# #         if not access_token:
# #             app.logger.error('Access token is missing.')
# #             return redirect(url_for('login'))

# #         user_id = session.get('user_id')  # Make sure user_id is set in the session
# #         if not user_id:
# #             app.logger.error('User ID is missing.')
# #             return redirect(url_for('error'))

# #         # new_recom.main() should return a dictionary of playlist URLs
# #         playlist_links = new_recom.main(access_token, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI, user_id)

# #         # Pass the dictionary to the success.html template
# #         return render_template('success.html', playlist_links=playlist_links)
# #     except Exception as e:
# #         app.logger.error(f'Error during playlist creation: {e}')
# #         return redirect(url_for('error'))





# # @app.route('/create_playlist', methods=['POST'])
# # def create_playlist():
# #     access_token = session.get('access_token')
# #     if not access_token:
# #         return redirect(url_for('login'))
# #     user_id = request.form.get('user_id')
# #     track_uris = request.form.get('track_uris')  # Ensure this is correct
# #     if not user_id:
# #         logging.error("User ID is missing")
# #         return redirect(url_for('error'))
# #     try:
# #         playlist_url = create_playlist_on_spotify(user_id, access_token, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI, track_uris, 'My Playlist')
# #         return render_template('success.html', playlist_url=playlist_url)
# #     except Exception as e:
# #         logging.error(f'Error during playlist creation: {e}')
# #         return redirect(url_for('error'))
# # @app.route('/generate_playlists', methods=['POST'])
# # def generate_playlists():
# #     return render_template('success.html')

# @app.route('/generate_playlists', methods=['GET', 'POST'])  # Changed to support GET for simplicity
# @app.route('/generate_playlists', methods=['GET', 'POST'])
# def generate_playlists():
#     access_token = session.get('access_token')
#     user_id = session.get('user_id')  # Make sure this is set during the login/authentication process

#     if not access_token or not user_id:
#         return redirect(url_for('login'))

#     try:
#         playlist_links = new_recom.main(access_token, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI, user_id)

#         return render_template('success_og.html', playlist_links=playlist_links)
#     except Exception as e:
#         logging.error(f"Error during playlist generation: {e}")
#         return redirect(url_for('error'))

# @app.route('/generate_playlists', methods=['GET', 'POST'])
# def generate_playlists():
#     user_id = session.get('user_id')  # Ensure user_id is set in the session
#     if not user_id:
#         return redirect(url_for('login'))

#     try:
#         playlist_links = new_recom.main(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI, user_id)
#         return render_template('success.html', playlist_links=playlist_links)
#     except Exception as e:
#         logger.error(f"Error generating playlists: {e}")
#         return redirect(url_for('error'))

# @app.route('/generate_playlists')
# def generate_playlists():
#     access_token = session.get('access_token')
#     user_id = session.get('user_id')
#     if not access_token or not user_id:
#         return redirect(url_for('login'))

#     # Call the recommendation logic from new_recom.py
#     playlist_links = new_recom.main(access_token, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI, user_id)

#     # Render the success page with playlist links
#     return render_template('success.html', playlist_links=playlist_links)


# @app.route('/generate_playlists')
# def generate_playlists():
#     access_token = session.get('access_token')
#     user_id = session.get('user_id')
#     if not access_token or not user_id:
#         return redirect(url_for('login'))

#     playlist_links = new_recom.main(access_token, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI, user_id)
#     return render_template('success.html', playlist_links=playlist_links)
# # @app.route('/generate_playlists')
# def generate_playlists():
#     access_token = session.get('access_token')
#     user_id = session.get('user_id')
#     if not access_token or not user_id:
#         return redirect(url_for('login'))

#     # Call the recommendation logic from new_recom.py
#     playlist_links = get_recommendations(access_token, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI, user_id)

#     # Render the success page with playlist links
#     return render_template('success.html', playlist_links=playlist_links)


@app.route('/generate_playlists')
def generate_playlists_route():
    access_token = session.get('access_token')
    user_id = session.get('user_id')
    if not access_token or not user_id:
        return redirect(url_for('login'))

    # Ensure that the correct function from recom3.py is called here
    playlist_links = generate_playlists(access_token,  user_id)
    return render_template('success_og1.html', playlist_links=playlist_links)

# @app.route('/generate_playlists')
# def generate_playlists_route():
#     try:
#         # Assuming necessary variables for Spotify are defined (access_token, client_id, etc.)
#         playlist_links = generate_playlists()
#         return render_template('success_og1.html', playlist_links=playlist_links)
#     except Exception as e:
#         return f"An error occurred: {e}"
@app.route('/error')
def error():
    return render_template('error.html')


# @app.route('/generate_playlists')
# def generate_playlists_route():
#     try:
#         # Assuming necessary variables for Spotify are defined (access_token, client_id, etc.)
#         playlist_links = generate_playlists()
#         return render_template('success_og1.html', playlist_links=playlist_links)
#     except Exception as e:
#         return f"An error occurred: {e}"


if __name__ == '__main__':
    app.run(debug=True, port=8000)