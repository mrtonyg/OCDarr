# radarr_utils.py
import os
import requests
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration settings from environment variables
RADARR_URL = os.getenv('RADARR_URL')
RADARR_API_KEY = os.getenv('RADARR_API_KEY')
# Separate browser-reachable base URL for image src attributes served to the
# client. RADARR_URL is often an internal-only address (e.g.
# host.docker.internal), which the API calls made from inside this container
# can reach but a user's own browser cannot. Falls back to RADARR_URL so
# deployments that don't set it behave exactly as before.
RADARR_PUBLIC_URL = os.getenv('RADARR_PUBLIC_URL', RADARR_URL)

MAX_MOVIES_ITEMS = int(os.getenv('MAX_MOVIES_ITEMS', 24))

# Setup logging
logger = logging.getLogger(__name__)

def load_preferences():
    """
    Load preferences for Radarr configuration.
    Returns a dictionary containing Radarr URL and API key.
    """
    return {'RADARR_URL': RADARR_URL, 'RADARR_API_KEY': RADARR_API_KEY}

def get_movie_list(preferences):
    """Get all movies from Radarr."""
    url = f"{preferences['RADARR_URL']}/api/v3/movie"
    headers = {'X-Api-Key': preferences['RADARR_API_KEY']}
    
    try:
        response = requests.get(url, headers=headers)
        if response.ok:
            movie_list = response.json()
            # Sort the movie list alphabetically by title
            sorted_movie_list = sorted(movie_list, key=lambda x: x['title'].lower())
            return sorted_movie_list
        else:
            logger.error(f"Failed to get movie list. Status: {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"Error fetching movie list: {str(e)}")
        return []

