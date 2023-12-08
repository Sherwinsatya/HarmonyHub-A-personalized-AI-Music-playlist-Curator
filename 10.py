import logging
import numpy as np
import pandas as pd
import requests
import spotipy
from sklearn.cluster import KMeans, DBSCAN
from sklearn.decomposition import TruncatedSVD
from spotipy.oauth2 import SpotifyOAuth
import time
import os
import json
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
def apply_kmeans(df, n_clusters=1, n_init=15):
    kmeans = KMeans(n_clusters=n_clusters, n_init=n_init, random_state=42)
    df['kmeans_cluster'] = kmeans.fit_predict(df.select_dtypes(include=[np.number]))
    return df, kmeans

# Apply SVD to the preprocessed data
def apply_svd(df, n_components=14):
    if df.empty or not any(df.select_dtypes(include=[np.number])):
        logger.error("DataFrame is empty or does not contain numeric types for SVD.")
        return np.array([]), None  # Return None for the svd object if the DataFrame is not suitable

    svd = TruncatedSVD(n_components=n_components, random_state=42)
    svd_features = svd.fit_transform(df.select_dtypes(include=[np.number]))
    return svd_features, svd  # Return both svd_features and the svd object


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

# Function to filter songs by cluster (KMeans or DBSCAN)
def filter_songs_by_cluster(song_data, cluster_labels, desired_cluster):
    return [song for song, cluster in zip(song_data, cluster_labels) if cluster == desired_cluster]

# Function to filter songs based on SVD similarity
def filter_songs_by_svd(song_data, svd_features, user_svd_features, threshold_similarity):
    return [song for song, features in zip(song_data, svd_features) if compute_similarity(user_svd_features, features) >= threshold_similarity]

# Function to combine SVD and KMeans results for filtering
def combined_svd_kmeans_filter(song_data, svd_features, kmeans_clusters, user_svd_features, desired_kmeans_cluster, threshold_similarity):
    return [song for song, svd_feature, kmeans_cluster in zip(song_data, svd_features, kmeans_clusters) if kmeans_cluster == desired_kmeans_cluster and compute_similarity(user_svd_features, svd_feature) >= threshold_similarity]

# Function to compute cosine similarity (for SVD based filtering)
# def compute_similarity(user_svd_features, song_svd_features):
#     return cosine_similarity([user_svd_features], [song_svd_features])[0][0]
def compute_similarity(user_svd_features, song_svd_features):
    # Debug: print the shapes of the arrays
    print(f"User SVD Features shape: {user_svd_features.shape}")
    print(f"Song SVD Features shape: {song_svd_features.shape}")

    # Ensure both arrays are 2D
    if user_svd_features.ndim == 1:
        user_svd_features = user_svd_features.reshape(1, -1)
    if song_svd_features.ndim == 1:
        song_svd_features = song_svd_features.reshape(1, -1)

    return cosine_similarity(user_svd_features, song_svd_features)[0][0]

def get_recommendations(access_token, user_id):
    sp = create_spotify_object(client_id, client_secret, redirect_uri)
    top_tracks = fetch_user_data(access_token, 'top/tracks')
    track_ids = [track['id'] for track in top_tracks['items']]
    audio_features = get_audio_features(access_token, track_ids)
    df = preprocess_data(top_tracks, audio_features)
    df_kmeans, kmeans = apply_kmeans(df)
    svd_features,svd = apply_svd(df)
    df_dbscan, dbscan = apply_dbscan(df)
    df_transform = df[df['id'].isin(track_ids)].select_dtypes(include=[np.number])
    if 'dbscan_cluster' in df_transform.columns:
            df_transform = df_transform.drop(columns=['dbscan_cluster'])
    # Calculate SVD features for user's top tracks
    # user_svd_features = svd.transform(df[df['id'].isin(track_ids)])
# Calculate SVD features for user's top tracks
    # user_svd_features = svd.transform(df[df['id'].isin(track_ids)].select_dtypes(include=[np.number]))
    user_svd_features = svd.transform(df_transform)
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

    # Filter songs based on K-Means cluster (Example)
    desired_kmeans_cluster = 0  # Adjust the desired K-Means cluster
    filtered_songs_kmeans = filter_songs_by_cluster(df['name'], df_kmeans['kmeans_cluster'], desired_kmeans_cluster)[:30]

    # Filter songs based on Combined SVD and K-Means (Example)
    desired_combined_cluster = 0  # Adjust the desired Combined cluster (K-Means + SVD)
    threshold_combined_similarity = 0.8  # Adjust the combined similarity threshold
    filtered_songs_combined = combined_svd_kmeans_filter(df['name'], svd_features, df_kmeans['kmeans_cluster'], user_svd_features, desired_combined_cluster, threshold_combined_similarity)[:30]

    # Create playlists and add tracks
    playlist_links = {
        'kmeans': create_playlist_on_spotify(sp, user_id, kmeans_tracks, "KMeans Playlist"),
        'dbscan': create_playlist_on_spotify(sp, user_id, dbscan_outliers, "DBSCAN Outliers Playlist"),
        'svd': create_playlist_on_spotify(sp, user_id, svd_playlist_tracks, "SVD Playlist"),
        'combined_svd': create_playlist_on_spotify(sp, user_id, combined_svd_tracks, "Combined SVD Playlist"),
        'new_kmeans': create_playlist_on_spotify(sp, user_id, new_kmeans_tracks, "New KMeans Playlist"),
        # New playlists...
        'kmeans_new': create_playlist_on_spotify(sp, user_id, filtered_songs_kmeans, "KMeans New Playlist"),
        'combined_new': create_playlist_on_spotify(sp, user_id, filtered_songs_combined, "Combined New Playlist"),
    }

    return playlist_links

# Generate recommendations based on user's top tracks and create playlists
# def get_recommendations(access_token, user_id):
#     sp = create_spotify_object(client_id, client_secret, redirect_uri)
#     top_tracks = fetch_user_data(access_token, 'top/tracks')
#     track_ids = [track['id'] for track in top_tracks['items']]
#     audio_features = get_audio_features(access_token, track_ids)
#     df = preprocess_data(top_tracks, audio_features)
#     df_kmeans, kmeans = apply_kmeans(df)
#     svd_features = apply_svd(df)
#     df_dbscan, dbscan = apply_dbscan(df)

#     # Get tracks for KMeans and DBSCAN playlists
#     kmeans_tracks = df_kmeans[df_kmeans['kmeans_cluster'] == 0]['id'].tolist()[:30]
#     dbscan_outliers = df_dbscan[df_dbscan['dbscan_cluster'] == -1]['id'].tolist()[:30]

#     # Load JSON data for SVD, Combined SVD, and New KMeans playlists
#     with open('global.json') as file:
#         json_data = json.load(file)

#     # Extract tracks from JSON
#     json_tracks = [track['track']['id'] for playlist in json_data['playlists'].values()
#                    for track in playlist['tracks']][:30]

#     # Create SVD playlist using JSON data
#     svd_playlist_tracks = json_tracks  # SVD applied to JSON data

#     # Combined SVD playlist (KMeans user data + SVD JSON data)
#     combined_svd_tracks = list(set(kmeans_tracks + svd_playlist_tracks))[:30]

#     # New KMeans playlist (songs from JSON data with features similar to user's KMeans clusters)
#     new_kmeans_tracks = json_tracks  # Use a method to filter based on similarity to KMeans clusters

#     # Filter songs based on K-Means cluster (Example)
#     desired_kmeans_cluster = 0  # Adjust the desired K-Means cluster
#     filtered_songs_kmeans = filter_songs_by_cluster(df['name'], df_kmeans['kmeans_cluster'], desired_kmeans_cluster)[:30]

#     # Filter songs based on Combined SVD and K-Means (Example)
#     desired_combined_cluster = 0  # Adjust the desired Combined cluster (K-Means + SVD)
#     threshold_combined_similarity = 0.8  # Adjust the combined similarity threshold
#     filtered_songs_combined = combined_svd_kmeans_filter(df['name'], svd_features, df_kmeans['kmeans_cluster'], user_svd_features, desired_combined_cluster, threshold_combined_similarity)[:30]

#     # Create playlists and add tracks
#     playlist_links = {
#         'kmeans': create_playlist_on_spotify(sp, user_id, kmeans_tracks, "KMeans Playlist"),
#         'dbscan': create_playlist_on_spotify(sp, user_id, dbscan_outliers, "DBSCAN Outliers Playlist"),
#         'svd': create_playlist_on_spotify(sp, user_id, svd_playlist_tracks, "SVD Playlist"),
#         'combined_svd': create_playlist_on_spotify(sp, user_id, combined_svd_tracks, "Combined SVD Playlist"),
#         'new_kmeans': create_playlist_on_spotify(sp, user_id, new_kmeans_tracks, "New KMeans Playlist"),
#         # New playlists...
#         'kmeans_new': create_playlist_on_spotify(sp, user_id, filtered_songs_kmeans, "KMeans New Playlist"),
#         'combined_new': create_playlist_on_spotify(sp, user_id, filtered_songs_combined, "Combined New Playlist"),
#     }

#     return playlist_links

# Main function
def main(access_token, user_id):
    try:
        logger.info("Starting playlist generation for user: %s", user_id)
        playlist_links = get_recommendations(access_token, user_id)
        if playlist_links:
            logger.info('Playlists created successfully for user: %s', user_id)
        else:
            logger.warning('No playlists were created for user: %s', user_id)
        return playlist_links
    except Exception as e:
        logger.exception("Exception occurred during playlist generation for user: %s", user_id)
        return {}

# Global variables
# client_id = os.getenv('SPOTIFY_CLIENT_ID', 'your_default_client_id')
# client_secret = os.getenv('SPOTIFY_CLIENT_SECRET', 'your_default_client_secret')
# redirect_uri = os.getenv('SPOTIFY_REDIRECT_URI', 'http://localhost:8080/callback')


client_id = '9896c76ec59140e9b8272264405314c8'
client_secret = '634c9e958451472a9244b1824c071557'
redirect_uri = 'http://localhost:5000/callback'

user_id = '95ff07qy4bb3bxlmfc3mxmfqo'
access_token =  'BQB7l_DjOHeF1s59Ht94L-ByEfH7zfk1olELksoQ-XIkXD2CvE8tcRqhbvooZ4Cdz8Xzmz9Mqwzxrqv4KtK4E9bEUleynPM-jMbzkHzcXVRi-BGAR6QXqtmCOg59cpZFREiuLNcaej5xlWybVQtWVUCcu7bQBSRHTxSiPE0iF13lNwy23j5ylW4RWWamfY9GsKqainAYHY10394exPOKOjw6T0adV8YB0rcuS3tzyn9RzGc6IdhgfF57Rwas_7GmsJYYt1K3WBucNZSuOoeqH8Jr'
if __name__ == '__main__':
    playlist_links = main(access_token, user_id)
    for playlist_type, link in playlist_links.items():
        print(f"{playlist_type.capitalize()} Playlist Link: {link}")
