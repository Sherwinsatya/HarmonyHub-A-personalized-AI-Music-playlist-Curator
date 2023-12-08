from sklearn.metrics.pairwise import cosine_similarity


# Optimized Function to filter songs by cluster (KMeans or DBSCAN)
def optimized_filter_songs_by_cluster(song_data, cluster_labels, desired_cluster):
    return [song for song, cluster in zip(song_data, cluster_labels) if cluster == desired_cluster]

# Optimized Function to filter songs based on SVD similarity
def optimized_filter_songs_by_svd(song_data, svd_features, user_svd_features, threshold_similarity):
    return [song for song, features in zip(song_data, svd_features) if compute_similarity(user_svd_features, features) >= threshold_similarity]

# Function to combine SVD and KMeans results for filtering
def optimized_combined_svd_kmeans_filter(song_data, svd_features, kmeans_clusters, user_svd_features, desired_kmeans_cluster, threshold_similarity):
    return [song for song, svd_feature, kmeans_cluster in zip(song_data, svd_features, kmeans_clusters) if kmeans_cluster == desired_kmeans_cluster and compute_similarity(user_svd_features, svd_feature) >= threshold_similarity]

def filter_songs_by_cluster(song_data, cluster_labels, desired_cluster, num_recommendations=10):
    filtered_songs = []
    for song, cluster in zip(song_data, cluster_labels):
        if cluster == desired_cluster:
            filtered_songs.append(song)
            if len(filtered_songs) >= num_recommendations:
                break
    return filtered_songs

# Function to compute cosine similarity (for SVD based filtering)
def compute_similarity(user_svd_features, song_svd_features):
    return cosine_similarity([user_svd_features], [song_svd_features])[0][0]

# Function to filter songs based on SVD similarity
def filter_songs_by_svd(song_data, svd_features, user_svd_features, threshold_similarity, num_recommendations=10):
    filtered_songs = []
    for song, song_features in zip(song_data, svd_features):
        similarity = compute_similarity(user_svd_features, song_features)
        if similarity >= threshold_similarity:
            filtered_songs.append(song)
            if len(filtered_songs) >= num_recommendations:
                break
    return filtered_songs

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