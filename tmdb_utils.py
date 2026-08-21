import os
import requests
from dotenv import load_dotenv
import sonarr_utils  # Import your existing sonarr_utils module

load_dotenv()
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
MAX_TMDB_MOVIES = int(os.getenv('MAX_TMDB_MOVIES', 24))
MAX_TMDB_SHOWS = int(os.getenv('MAX_TMDB_SHOWS', 24))

def get_tmdb_endpoint(endpoint, params=None):
    """Make a request to any TMDB endpoint with the given parameters."""
    base_url = f"https://api.themoviedb.org/3/{endpoint}"
    if params is None:
        params = {}
    
    # Check if we have a v3 or v4 token
    auth_token = TMDB_API_KEY.strip('"\'')
    
    try:
        headers = {}
        # If it's a long token (v4), use it as a bearer token
        if len(auth_token) > 40:
            headers["Authorization"] = f"Bearer {auth_token}"
        else:
            # Otherwise use as API key in params (v3)
            params['api_key'] = auth_token
        
        response = requests.get(base_url, params=params, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching {endpoint}: {response.status_code}")
            return {'results': []}
    except Exception as e:
        print(f"Exception during API request: {str(e)}")
        return {'results': []}
def get_movie_details(tmdb_id):
    """
    Get detailed movie information from TMDB by its ID
    :param tmdb_id: TMDB movie ID
    :return: Dictionary of movie details
    """
    return get_tmdb_endpoint(f"movie/{tmdb_id}")

def get_tv_show_details(tmdb_id):
    """
    Get detailed TV show information from TMDB by its ID
    :param tmdb_id: TMDB TV show ID
    :return: Dictionary of TV show details
    """
    return get_tmdb_endpoint(f"tv/{tmdb_id}")
def get_recommendations_by_genre(genre_ids, media_type='movie'):
    """Get recommendations based on genres."""
    try:
        params = {
            'api_key': TMDB_API_KEY,
            'language': 'en-US',
            'sort_by': 'popularity.desc',
            'with_genres': ','.join(str(g) for g in genre_ids),
            'page': 1
        }
        
        endpoint = 'discover/movie' if media_type == 'movie' else 'discover/tv'
        
        response = requests.get(f"{TMDB_BASE_URL}/{endpoint}", params=params)
        if response.ok:
            return response.json()
        else:
            logger.error(f"Failed to get {media_type} recommendations: {response.status_code}")
            return {'results': []}
    except Exception as e:
        logger.error(f"Error getting {media_type} recommendations: {str(e)}")
        return {'results': []}
def search_tv_shows(query):
    """Search for TV shows using TMDB API."""
    return get_tmdb_endpoint("search/tv", {
        'query': query,
        'language': 'en-US',
        'page': 1
    })

def search_movies(query):
    """Search for movies using TMDB API."""
    return get_tmdb_endpoint("search/movie", {
        'query': query,
        'language': 'en-US',
        'page': 1
    })

def get_external_ids(tmdb_id, media_type='tv'):
    """Get external IDs for a TV show or movie."""
    endpoint = f"{media_type}/{tmdb_id}/external_ids"
    return get_tmdb_endpoint(endpoint)

def get_or_add_series_to_sonarr(show_data):
    """Add a series to Sonarr if it doesn't exist, or return the ID if it does."""
    try:
        tmdb_id = show_data.get('id')
        
        # Get TVDB ID from TMDB
        details = tmdb_utils.get_external_ids(tmdb_id, 'tv')
        tvdb_id = details.get('tvdb_id')
        
        if not tvdb_id:
            app.logger.error(f"Could not find TVDB ID for {show_data.get('name')}")
            return None
        
        # Check if show exists in Sonarr
        sonarr_preferences = sonarr_utils.load_preferences()
        headers = {
            'X-Api-Key': sonarr_preferences['SONARR_API_KEY'],
            'Content-Type': 'application/json'
        }
        sonarr_url = sonarr_preferences['SONARR_URL']
        
        # Check if show already exists in Sonarr
        existing_series = sonarr_utils.get_series_list(sonarr_preferences)
        
        for series in existing_series:
            if series.get('tvdbId') == tvdb_id:
                return series.get('id')
        
        # If not, look up the show
        response = requests.get(
            f"{sonarr_url}/api/v3/series/lookup", 
            headers=headers,
            params={"term": f"tvdb:{tvdb_id}"}
        )
        
        if not response.ok or not response.json():
            app.logger.error(f"Failed to look up show {show_data.get('name')}")
            return None
        
        lookup_results = response.json()
        
        # Get the first root folder path
        root_folder_response = requests.get(f"{sonarr_url}/api/v3/rootfolder", headers=headers)
        
        if not root_folder_response.ok or not root_folder_response.json():
            app.logger.error("Failed to get root folders from Sonarr")
            return None
        
        root_folder = root_folder_response.json()[0].get('path')
        
        # Get quality profile
        profile_response = requests.get(f"{sonarr_url}/api/v3/qualityprofile", headers=headers)
        
        if not profile_response.ok or not profile_response.json():
            app.logger.error("Failed to get quality profiles from Sonarr")
            return None
        
        # Use the first quality profile
        quality_profile_id = profile_response.json()[0].get('id')
        
        # Prepare series for adding
        series_to_add = lookup_results[0]
        series_to_add['rootFolderPath'] = root_folder
        series_to_add['qualityProfileId'] = quality_profile_id
        series_to_add['monitored'] = True
        series_to_add['addOptions'] = {
            'searchForMissingEpisodes': False,
            'monitor': 'none'  # Start with nothing monitored
        }
        
        # Add to Sonarr
        add_response = requests.post(
            f"{sonarr_url}/api/v3/series", 
            headers=headers,
            json=series_to_add
        )
        
        if not add_response.ok:
            app.logger.error(f"Failed to add show to Sonarr: {add_response.text}")
            return None
        
        return add_response.json().get('id')
    
    except Exception as e:
        app.logger.error(f"Error in get_or_add_series_to_sonarr: {str(e)}")
        return None

def monitor_and_search_season(series_id, season_number):
    """Monitor and search for a full season."""
    try:
        sonarr_preferences = sonarr_utils.load_preferences()
        headers = {
            'X-Api-Key': sonarr_preferences['SONARR_API_KEY'],
            'Content-Type': 'application/json'
        }
        sonarr_url = sonarr_preferences['SONARR_URL']
        
        # Get episodes for the season
        episodes_response = requests.get(
            f"{sonarr_url}/api/v3/episode?seriesId={series_id}&seasonNumber={season_number}",
            headers=headers
        )
        
        if not episodes_response.ok or not episodes_response.json():
            app.logger.error(f"Failed to get episodes for season {season_number}")
            return False
        
        episodes = episodes_response.json()
        episode_ids = [ep.get('id') for ep in episodes]
        
        # Monitor all episodes
        if episode_ids:
            monitor_response = requests.put(
                f"{sonarr_url}/api/v3/episode/monitor",
                headers=headers,
                json={"episodeIds": episode_ids, "monitored": True}
            )
            
            if not monitor_response.ok:
                app.logger.error(f"Failed to monitor episodes for season {season_number}")
                return False
        
        # Search for the season
        search_response = requests.post(
            f"{sonarr_url}/api/v3/command",
            headers=headers,
            json={"name": "SeasonSearch", "seriesId": series_id, "seasonNumber": season_number}
        )
        
        if not search_response.ok:
            app.logger.error(f"Failed to search for season {season_number}")
            return False
        
        return True
    
    except Exception as e:
        app.logger.error(f"Error in monitor_and_search_season: {str(e)}")
        return False

def monitor_and_search_episode(series_id, season_number, episode_number):
    """Monitor and search for a specific episode."""
    try:
        sonarr_preferences = sonarr_utils.load_preferences()
        headers = {
            'X-Api-Key': sonarr_preferences['SONARR_API_KEY'],
            'Content-Type': 'application/json'
        }
        sonarr_url = sonarr_preferences['SONARR_URL']
        
        # Get episodes for the season
        episodes_response = requests.get(
            f"{sonarr_url}/api/v3/episode?seriesId={series_id}&seasonNumber={season_number}",
            headers=headers
        )
        
        if not episodes_response.ok:
            app.logger.error(f"Failed to get episodes for season {season_number}")
            return False
        
        episodes = episodes_response.json()
        
        # Find the specific episode
        target_episode = None
        for ep in episodes:
            if ep.get('episodeNumber') == episode_number:
                target_episode = ep
                break
        
        if not target_episode:
            app.logger.error(f"Episode {episode_number} not found in season {season_number}")
            return False
        
        # Monitor just this episode
        monitor_response = requests.put(
            f"{sonarr_url}/api/v3/episode/monitor",
            headers=headers,
            json={"episodeIds": [target_episode.get('id')], "monitored": True}
        )
        
        if not monitor_response.ok:
            app.logger.error(f"Failed to monitor episode {episode_number}")
            return False
        
        # Search for the episode
        search_response = requests.post(
            f"{sonarr_url}/api/v3/command",
            headers=headers,
            json={"name": "EpisodeSearch", "episodeIds": [target_episode.get('id')]}
        )
        
        if not search_response.ok:
            app.logger.error(f"Failed to search for episode {episode_number}")
            return False
        
        return True
    
    except Exception as e:
        app.logger.error(f"Error in monitor_and_search_episode: {str(e)}")
        return False