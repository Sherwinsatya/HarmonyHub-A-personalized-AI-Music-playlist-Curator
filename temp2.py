# ... (previous code)
import json
import logging
import numpy as np
import pandas as pd
import requests
import spotipy
from sklearn.cluster import KMeans, DBSCAN
from sklearn.decomposition import TruncatedSVD
from spotipy.oauth2 import SpotifyOAuth
import time
from sklearn.metrics.pairwise import cosine_similarity

# Initialize logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a Spotify client object
def create_spotify_object(client_id, client_secret, redirect_uri):
    return spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=client_id, 
                                                     client_secret=client_secret, 
                                                     redirect_uri=redirect_uri,
                                                     scope="playlist-modify-public user-top-read"))

# Fetch user data from Spotify
def fetch_user_data(access_token, endpoint, params=None):
    url = f'https://api.spotify.com/v1/me/{endpoint}'
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(url, headers=headers, params=params)
    return response.json()

# Fetch audio features for given track IDs from Spotify
def get_audio_features(access_token, track_ids):
    url = 'https://api.spotify.com/v1/audio-features'
    headers = {'Authorization': f'Bearer {access_token}'}
    audio_features = {}
    
    for i in range(0, len(track_ids), 10):
        batch_ids = track_ids[i:i + 10]
        params = {'ids': ','.join(batch_ids)}
        response = requests.get(url, headers=headers, params=params).json()
        audio_features.update({feat['id']: feat for feat in response['audio_features'] if feat})
        time.sleep(5)
    
    return audio_features

# Preprocess the top tracks data and combine with audio features
def preprocess_data(top_tracks, audio_features):
    data = []
    for track in top_tracks['items']:
        track_id = track['id']
        features = audio_features.get(track_id, {})
        
        data.append({
            'id': track_id,
            'name': track.get('name', 'Unknown'),
            'popularity': track.get('popularity', 0),
            'duration_ms': track.get('duration_ms', 0),
            'explicit': track.get('explicit', False),
            'album_name': track['album'].get('name', 'Unknown') if 'album' in track else 'Unknown',
            'release_date': track.get('release_date', 'Unknown'),
            'artist_names': ', '.join([artist.get('name', 'Unknown') for artist in track.get('artists', [])]),
            # Audio features
            'danceability': features.get('danceability', 0),
            'energy': features.get('energy', 0),
            'key': features.get('key', 0),
            'loudness': features.get('loudness', 0),
            'mode': features.get('mode', 0),
            'speechiness': features.get('speechiness', 0),
            'acousticness': features.get('acousticness', 0),
            'instrumentalness': features.get('instrumentalness', 0),
            'liveness': features.get('liveness', 0),
            'valence': features.get('valence', 0),
            'tempo': features.get('tempo', 0),
        })
    
    return pd.DataFrame(data)

# Apply K-Means clustering to the preprocessed data
def apply_kmeans(df, n_clusters=3, n_init=15):
    kmeans = KMeans(n_clusters=n_clusters, n_init=n_init, random_state=42)
    df['kmeans_cluster'] = kmeans.fit_predict(df.select_dtypes(include=[np.number]))
    return df, kmeans

# Apply SVD to the preprocessed data
def apply_svd(df, n_components=14):
    if df.empty or not any(df.select_dtypes(include=[np.number])):
        logger.error("DataFrame is empty or does not contain numeric types for SVD.")
        return np.array([])

    svd = TruncatedSVD(n_components=n_components, random_state=42)
    svd_features = svd.fit_transform(df.select_dtypes(include=[np.number]))
    return svd_features

# Apply DBSCAN clustering to the preprocessed data
def apply_dbscan(df, eps=0.5, min_samples=5):
    dbscan = DBSCAN(eps=eps, min_samples=min_samples)
    df['dbscan_cluster'] = dbscan.fit_predict(df.select_dtypes(include=[np.number]))
    return df, dbscan

# Create a Spotify playlist and add tracks
def create_playlist_on_spotify(sp, user_id, track_uris, playlist_name):
    playlist = sp.user_playlist_create(user_id, playlist_name, public=True)
    sp.playlist_add_items(playlist['id'], track_uris[:100])  # Limit to 100 tracks
    return playlist['external_urls']['spotify']

# Generate recommendations based on user's top tracks and create playlists
def get_recommendations(access_token, user_id):
    sp = create_spotify_object(client_id, client_secret, redirect_uri)
    top_tracks = fetch_user_data(access_token, 'top/tracks')
    track_ids = [track['id'] for track in top_tracks['items']]
    audio_features = get_audio_features(access_token, track_ids)
    df = preprocess_data(top_tracks, audio_features)
    df_kmeans, kmeans = apply_kmeans(df)
    svd_features = apply_svd(df)
    df_dbscan, dbscan = apply_dbscan(df)

    # Get tracks for KMeans and DBSCAN playlists
    kmeans_tracks = df_kmeans[df_kmeans['kmeans_cluster'] == 0]['id'].tolist()[:30]
    dbscan_outliers = df_dbscan[df_dbscan['dbscan_cluster'] == -1]['id'].tolist()[:30]

    # Load JSON data for SVD, Combined SVD, and New KMeans playlists
    with open('global.json') as file:
        json_data = json.load(file)

    # Extract tracks from JSON
    json_tracks = [track['track']['id'] for playlist in json_data['playlists'].values()
                   for track in playlist['tracks']][:30]

    # Create SVD playlist using JSON data
    svd_playlist_tracks = json_tracks  # SVD applied to JSON data

    # Combined SVD playlist (KMeans user data + SVD JSON data)
    combined_svd_tracks = list(set(kmeans_tracks + svd_playlist_tracks))[:30]

    # New KMeans playlist (songs from JSON data with features similar to user's KMeans clusters)
    new_kmeans_tracks = json_tracks  # Use a method to filter based on similarity to KMeans clusters


# Function to filter songs by K-Means cluster
def filter_songs_by_kmeans(song_data, kmeans_clusters, desired_cluster, num_recommendations=10):
    filtered_songs = []
    for song, cluster in zip(song_data, kmeans_clusters):
        if cluster == desired_cluster:
            filtered_songs.append(song)
            if len(filtered_songs) >= num_recommendations:
                break
    return filtered_songs

# Generate recommendations based on user's top tracks and create playlists
def get_recommendations_updated(access_token, user_id):
    sp = create_spotify_object(client_id, client_secret, redirect_uri)
    top_tracks = fetch_user_data(access_token, 'top/tracks')
    track_ids = [track['id'] for track in top_tracks['items']]
    audio_features = get_audio_features(access_token, track_ids)
    df = preprocess_data(top_tracks, audio_features)
    df_kmeans, kmeans = apply_kmeans(df)
    svd_features = apply_svd(df)

    # Example: Filter songs based on SVD similarity
    user_svd_features = svd_features[0]  # Replace with user's SVD features
    threshold_similarity = 0.8  # Adjust the similarity threshold
    filtered_songs_svd = filter_songs_by_svd(df['name'], svd_features, user_svd_features, threshold_similarity, num_recommendations=10)

    # Example: Filter songs based on K-Means cluster
    desired_kmeans_cluster = 0  # Adjust the desired K-Means cluster
    filtered_songs_kmeans = filter_songs_by_kmeans(df['name'], df_kmeans['kmeans_cluster'], desired_kmeans_cluster, num_recommendations=10)

    # Example: Filter songs based on Combined SVD and K-Means
    desired_combined_cluster = 0  # Adjust the desired Combined cluster (K-Means + SVD)
    threshold_combined_similarity = 0.8  # Adjust the combined similarity threshold
    filtered_songs_combined = combined_svd_kmeans_filter(df['name'], svd_features, df_kmeans['kmeans_cluster'], user_svd_features, desired_combined_cluster, threshold_combined_similarity, num_recommendations=10)

    # You can create more filtering logic as needed based on your use case

    return filtered_songs_svd, filtered_songs_kmeans, filtered_songs_combined

# Main function
def main_updated(access_token, user_id):
    try:
        logger.info("Starting playlist generation for user: %s", user_id)
        filtered_songs_svd, filtered_songs_kmeans, filtered_songs_combined = get_recommendations_updated(access_token, user_id)

        # Create playlists or perform other actions with recommended songs
        if filtered_songs_svd:
            logger.info('SVD Recommendations generated successfully for user: %s', user_id)
            # Create SVD playlist and add filtered_songs_svd to it
        else:
            logger.warning('No SVD recommendations generated for user: %s', user_id)

        if filtered_songs_kmeans:
            logger.info('K-Means Recommendations generated successfully for user: %s', user_id)
            # Create K-Means playlist and add filtered_songs_kmeans to it
        else:
            logger.warning('No K-Means recommendations generated for user: %s', user_id)

        if filtered_songs_combined:
            logger.info('Combined Recommendations generated successfully for user: %s', user_id)
            # Create Combined playlist and add filtered_songs_combined to it
        else:
            logger.warning('No Combined recommendations generated for user: %s', user_id)

        # ... (create other playlists as needed)

    except Exception as e:
        logger.exception("Exception occurred during playlist generation for user: %s", user_id)

def filter_songs_by_svd(song_data, svd_features, user_svd_features, threshold_similarity, num_recommendations=10):
    filtered_songs = []
    for song, song_features in zip(song_data, svd_features):
        similarity = compute_similarity(user_svd_features, song_features)
        if similarity >= threshold_similarity:
            filtered_songs.append(song)
            if len(filtered_songs) >= num_recommendations:
                break
    return filtered_songs

def compute_similarity(user_svd_features, song_svd_features):
    return cosine_similarity([user_svd_features], [song_svd_features])[0][0]
# Function to combine SVD and KMeans results for filtering
def combined_svd_kmeans_filter(song_data, svd_features, kmeans_clusters, user_svd_features, desired_kmeans_cluster, threshold_similarity, num_recommendations=10):
    filtered_songs = []
    for song, svd_feature, kmeans_cluster in zip(song_data, svd_features, kmeans_clusters):
        similarity = compute_similarity(user_svd_features, svd_feature)
        if kmeans_cluster == desired_kmeans_cluster and similarity >= threshold_similarity:
            filtered_songs.append(song)
            if len(filtered_songs) >= num_recommendations:
                break
    return filtered_songs

client_id = '9896c76ec59140e9b8272264405314c8'
client_secret = '634c9e958451472a9244b1824c071557'
redirect_uri = 'http://localhost:5000/callback'
user_id = '95ff07qy4bb3bxlmfc3mxmfqo'
access_token = 'BQBg5dMvgnbR7V1rwB36KWhAdiINI0fPDXL_uyx-ky6Sk0HTtQDyP-MIzfOucLNrwj5h4rmk8h06ZHJcvcTYxcp-1BOg6FqEDYaUhyiVWUDM1XXSUKn6mW4jYQ5bQ9NseCw9mO9K3u-2F97O9ty2gTQprxWsErBSXu4LzFciMR-oLoDnqdkewaNwDvL4XfQ5U69n_EL1VT3Dw-OIwVJKovQhTbfVdt7IS6vVi-yAe03BgF3jrt_srIA4Gc57Fe3cSaBGxg0-ozcP7MtIu4EdDP2K'

# ... (previous code)

if __name__ == '__main__':
    main_updated(access_token, user_id)