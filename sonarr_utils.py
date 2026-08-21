import os
import requests
import random
from dotenv import load_dotenv
from PIL import Image, ImageFilter
import io
import logging

# Load environment variables from .env file
load_dotenv()

# Configuration settings from environment variables
SONARR_URL = os.getenv('SONARR_URL')
SONARR_API_KEY = os.getenv('SONARR_API_KEY')
# Separate browser-reachable base URL for image src / deep-link attributes
# served to the client. SONARR_URL is often an internal-only address (e.g.
# host.docker.internal), which the API calls made from inside this container
# can reach but a user's own browser cannot. Falls back to SONARR_URL so
# deployments that don't set it behave exactly as before.
SONARR_PUBLIC_URL = os.getenv('SONARR_PUBLIC_URL', SONARR_URL)
HA_WWW_PATH = '/app/backgrounds' 

MAX_SHOWS_ITEMS = int(os.getenv('MAX_SHOWS_ITEMS', 24))

# Setup logging
logger = logging.getLogger()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_preferences():
    """
    Load preferences for Sonarr configuration.
    Returns a dictionary containing Sonarr URL and API key.
    """
    return {'SONARR_URL': SONARR_URL, 'SONARR_API_KEY': SONARR_API_KEY}

def fetch_random_fanart():
    """Fetch, blur, and save a random fanart from the Sonarr series list."""
    url = f"{SONARR_URL}/api/v3/series"
    headers = {'X-Api-Key': SONARR_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        logger.info(f"Fetching series list from: {url}")
        
        if response.ok:
            series_list = response.json()
            random_series = random.choice(series_list)
            series_id = random_series['id']
            fanart_url = f"{SONARR_URL}/api/v3/mediacover/{series_id}/fanart.jpg"
            logger.info(f"Fetching fanart from: {fanart_url}")

            fanart_response = requests.get(fanart_url, headers={'X-Api-Key': SONARR_API_KEY})
            if fanart_response.ok:
                # Open the image using PIL
                image = Image.open(io.BytesIO(fanart_response.content))
                
                # Resize the image to 3840x2160
                desired_width, desired_height = 3840, 2160
                resized_image = image.resize((desired_width, desired_height), Image.LANCZOS)

                # Apply the blur
                blurred_image = resized_image.filter(ImageFilter.GaussianBlur(radius=2))  # Adjust radius for more/less blur

                # Save the blurred image
                fanart_path = os.path.join(HA_WWW_PATH, "fanart.jpg")
                blurred_image.save(fanart_path, format='JPEG')
                logger.info(f"Saved blurred fanart as {fanart_path}")
            else:
                logger.error(f"Failed to fetch fanart. Status code: {fanart_response.status_code}, Content: {fanart_response.content[:100]}")
        else:
            logger.error(f"Failed to fetch series list. Status code: {response.status_code}, Content: {response.content[:100]}")
    except Exception as e:
        logger.error(f"Exception occurred while fetching or processing fanart: {str(e)}")

def get_series_list(preferences):
    url = f"{preferences['SONARR_URL']}/api/v3/series"
    headers = {'X-Api-Key': preferences['SONARR_API_KEY']}
    response = requests.get(url, headers=headers)
    if response.ok:
        series_list = response.json()
        # Sort the series list alphabetically by title
        sorted_series_list = sorted(series_list, key=lambda x: x['title'].lower())
        return sorted_series_list
    else:
        return []

