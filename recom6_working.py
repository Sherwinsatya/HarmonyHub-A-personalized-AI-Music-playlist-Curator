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

# Initialize logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_spotify_object(client_id, client_secret, redirect_uri):
    try:
        return spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=client_id, 
                                                         client_secret=client_secret, 
                                                         redirect_uri=redirect_uri,
                                                         scope="playlist-modify-public user-top-read"))
    except Exception as e:
        logger.error(f"Error in creating Spotify object: {e}")
        return None

def fetch_user_data(access_token, endpoint, params=None):
    try:
        url = f'https://api.spotify.com/v1/me/{endpoint}'
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching user data: {e}")
        return None

def get_audio_features(access_token, track_ids):
    try:
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
    except Exception as e:
        logger.error(f"Error fetching audio features: {e}")
        return {}

def preprocess_data(top_tracks, audio_features):
    try:
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
    except Exception as e:
        logger.error(f"Error in preprocessing data: {e}")
        return pd.DataFrame()
def apply_kmeans(df, n_clusters=3, n_init=15):
    try:
        kmeans = KMeans(n_clusters=n_clusters, n_init=n_init, random_state=42)
        df['kmeans_cluster'] = kmeans.fit_predict(df.select_dtypes(include=[np.number]))
        return df, kmeans
    except Exception as e:
        logger.error(f"Error applying KMeans: {e}")
        return df, None

def apply_svd(df, n_components=14):
    try:
        svd = TruncatedSVD(n_components=n_components, random_state=42)
        svd_features = svd.fit_transform(df.select_dtypes(include=[np.number]))
        return svd_features
    except Exception as e:
        logger.error(f"Error applying SVD: {e}")
        return np.array([])

def apply_dbscan(df, eps=0.5, min_samples=5):
    try:
        dbscan = DBSCAN(eps=eps, min_samples=min_samples)
        df['dbscan_cluster'] = dbscan.fit_predict(df.select_dtypes(include=[np.number]))
        return df, dbscan
    except Exception as e:
        logger.error(f"Error applying DBSCAN: {e}")
        return df, None

def create_playlist_on_spotify(sp, user_id, track_uris, playlist_name):
    try:
        playlist = sp.user_playlist_create(user_id, playlist_name, public=True)
        sp.playlist_add_items(playlist['id'], track_uris[:100])  # Limit to 100 tracks
        return playlist['external_urls']['spotify']
    except Exception as e:
        logger.error(f"Error creating playlist on Spotify: {e}")
        return None

def analyze_clusters(df):
    try:
        cluster_features = {}
        for cluster in df['kmeans_cluster'].unique():
            cluster_data = df[df['kmeans_cluster'] == cluster]
            cluster_features[cluster] = cluster_data[['danceability', 'energy', 'acousticness', 'tempo']].mean().to_dict()
        return cluster_features
    except Exception as e:
        logger.error(f"Error analyzing clusters: {e}")
        return {}

def filter_songs_by_cluster_characteristics(df, cluster_features, cluster_label):
    try:
        criteria = cluster_features[cluster_label]
        filtered_songs = df
        for feature, value in criteria.items():
            filtered_songs = filtered_songs[(filtered_songs[feature] >= value * 0.8) & (filtered_songs[feature] <= value * 1.2)]
        return filtered_songs['id'].tolist()
    except Exception as e:
        logger.error(f"Error filtering songs by cluster characteristics: {e}")
        return []
def fallback_song_selection(df, target_features, cluster_label, min_tracks):
    # Sort the dataframe by closeness to the target features
    df['similarity_score'] = df.apply(lambda row: sum([abs(row[feature] - target_features[feature]) 
                                                       for feature in target_features]), axis=1)
    sorted_df = df.sort_values('similarity_score')
    return sorted_df['id'].tolist()[:min_tracks]

def create_characteristic_playlists(df, sp, user_id, cluster_features, min_tracks=10):
    playlist_links = {}
    for cluster_label, features in cluster_features.items():
        track_ids = filter_songs_by_cluster_characteristics(df, features, cluster_label)
        
        # Check if enough tracks are available, if not, use fallback strategy
        if len(track_ids) < min_tracks:
            track_ids = fallback_song_selection(df, features, cluster_label, min_tracks)

        playlist_name = f"Characteristic Playlist {cluster_label}"
        playlist_link = create_playlist_on_spotify(sp, user_id, track_ids, playlist_name)
        if playlist_link:
            playlist_links[f'characteristic_based {cluster_label}'] = playlist_link

    return playlist_links

def get_recommendations(access_token, user_id):
    try:
        sp = create_spotify_object(client_id, client_secret, redirect_uri)
        top_tracks = fetch_user_data(access_token, 'top/tracks')
        track_ids = [track['id'] for track in top_tracks['items']]
        audio_features = get_audio_features(access_token, track_ids)
        df = preprocess_data(top_tracks, audio_features)

        df_kmeans, kmeans = apply_kmeans(df)
        svd_features = apply_svd(df)
        df_dbscan, dbscan = apply_dbscan(df)

        # ... [existing playlist creation code] ...
        # Get tracks for KMeans and DBSCAN playlists
        kmeans_tracks = df_kmeans[df_kmeans['kmeans_cluster'] == 0]['id'].tolist()[:30]
        dbscan_outliers = df_dbscan[df_dbscan['dbscan_cluster'] == -1]['id'].tolist()[:30]

    # Load JSON data for SVD, Combined SVD, and New KMeans playlists
        with open('templates\global.json') as file:
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
        playlist_links = {
        'kmeans': create_playlist_on_spotify(sp, user_id, kmeans_tracks, "KMeans Playlist"),
        'dbscan': create_playlist_on_spotify(sp, user_id, dbscan_outliers, "DBSCAN Outliers Playlist"),
        'svd': create_playlist_on_spotify(sp, user_id, svd_playlist_tracks, "SVD Playlist"),
        'combined_svd': create_playlist_on_spotify(sp, user_id, combined_svd_tracks, "Combined SVD Playlist"),
        'new_kmeans': create_playlist_on_spotify(sp, user_id, new_kmeans_tracks, "New KMeans Playlist")
    }

        # Analyze clusters to determine common characteristics
        cluster_features = analyze_clusters(df)

        # Create playlists based on cluster characteristics
        characteristic_playlist_links = create_characteristic_playlists(df, sp, user_id, cluster_features)

    # Combine all playlist links
        playlist_links.update(characteristic_playlist_links)
        return playlist_links
    except Exception as e:
        logger.error(f"Error in get_recommendations: {e}")
        return {}

def main(access_token, user_id):
    try:
        logger.info("Starting playlist generation for user: %s", user_id)
        playlist_links = get_recommendations(access_token, user_id)
        if playlist_links:
            logger.info('Playlists created successfully for user: %s', user_id)
            return playlist_links
        else:
            logger.warning('No playlists were created for user: %s', user_id)
            return {}
    except Exception as e:
        logger.exception("Exception occurred during playlist generation for user: %s", user_id)
        return {}

# Global variables
client_id = '9896c76ec59140e9b8272264405314c8'
client_secret = '634c9e958451472a9244b1824c071557'
redirect_uri = 'http://localhost:6969/callback'
user_id = '95ff07qy4bb3bxlmfc3mxmfqo'
access_token = 'BQDqxblXW0KG-E6VYwcqSvhPULheBtVGM2gvX1bD2zfxf8_KNS0BdG3Qf8ZSf2itO-wG4LY8FwzdoMj0shVBaN8Mqe4I8Xy8xjWLXFWAo8Tjy94tJoAQ-f_vYL8xrdJzMLXT6qCkmqHBTOFzJTkPHUwVnl4RHXuIT-4JVeTRVjJFyYqZ0hVy6Hijr_Rnq_R6l581Cc-28j8-dZV6UCl5-6-aTqiP2KbApFUnHxBcSj9z3UOnaoW-SZSiM5MlgpgDzP8lYhn2O2W19y0E6I1W7Bsw'


if __name__ == '__main__':
    try:
        playlist_links = main(access_token, user_id)
        for playlist_type, link in playlist_links.items():
            print(f"{playlist_type.capitalize()} Playlist Link: {link}")
    except Exception as e:
        logger.error(f"Error in main execution: {e}")