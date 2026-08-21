from flask import Flask, Blueprint
import os
import json
import uuid
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from api.jellyseerr_api import JellyseerrAPI
from jellyfin_utils import JellyfinAPI

app = Flask(__name__)

# A single Blueprint instance shared by every module under blueprints/.
#
# Flask always qualifies a Blueprint's endpoints with "<blueprint.name>."
# when it's registered (this is baked into BlueprintSetupState.add_url_rule
# and can't be turned off per-blueprint). With more than one Blueprint
# object registered on the same app there is no way to avoid that prefix,
# which would silently break every bare url_for('some_view') call already
# in the templates/static JS. Using ONE shared Blueprint across all the
# route modules, registered once with name='' (see webhook_listener.py),
# keeps every endpoint name byte-identical to the original monolith while
# still moving the route bodies into separate files by feature area.
bp = Blueprint('routes', __name__)

# Load environment variables
load_dotenv()
BASE_DIR = os.getcwd()
# Sonarr variables
SONARR_URL = os.getenv('SONARR_URL')
SONARR_API_KEY = os.getenv('SONARR_API_KEY')
# Browser-reachable base URL for the template's client-facing image src.
# Falls back to SONARR_URL so deployments that don't set it are unaffected.
SONARR_PUBLIC_URL = os.getenv('SONARR_PUBLIC_URL', SONARR_URL)

# Radarr variables
RADARR_URL = os.getenv('RADARR_URL')
RADARR_API_KEY = os.getenv('RADARR_API_KEY')
# Jellyseerr variables
JELLYSEERR_URL = os.getenv('JELLYSEERR_URL', '')

# Import the environment variable limits
MAX_SHOWS_ITEMS = int(os.getenv('MAX_SHOWS_ITEMS', 24))
MAX_MOVIES_ITEMS = int(os.getenv('MAX_MOVIES_ITEMS', 24))
MAX_COMBINED_ITEMS = int(os.getenv('MAX_COMBINED_ITEMS', 24))

# Other settings
REQUESTS_DIR = os.path.join(os.getcwd(), 'data', 'requests')
os.makedirs(REQUESTS_DIR, exist_ok=True)

LAST_PROCESSED_FILE = os.path.join(os.getcwd(), 'data', 'last_processed.json')
os.makedirs(os.path.dirname(LAST_PROCESSED_FILE), exist_ok=True)

# Initialize the Jellyseerr API client
jellyseerr_api = JellyseerrAPI()

jellyfin_api = JellyfinAPI(
    jellyfin_token=os.getenv('JELLYFIN_TOKEN', ''),
    jellyfin_user_id=os.getenv('JELLYFIN_USER_ID', '')
)

# Setup logging to capture all logs
log_file = os.getenv('LOG_PATH', os.path.join(os.getcwd(), 'logs', 'app.log'))

log_level = logging.INFO  # Capture INFO and ERROR levels

# Create log directory if it doesn't exist
os.makedirs(os.path.dirname(log_file), exist_ok=True)

# Create a RotatingFileHandler
file_handler = RotatingFileHandler(
    log_file,
    maxBytes=1*1024*1024,  # 1 MB max size
    backupCount=2,  # Keep 2 backup files
    encoding='utf-8'
)
file_handler.setLevel(log_level)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

# Configure the root logger
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[file_handler]
)

# Adding stream handler to also log to console for Docker logs to capture
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.DEBUG if os.getenv('FLASK_DEBUG', 'false').lower() == 'true' else logging.INFO)
formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(message)s')
stream_handler.setFormatter(formatter)
app.logger.addHandler(stream_handler)


# Configuration management
config_path = os.path.join(app.root_path, 'config', 'config.json')

def load_config():
    try:
        with open(config_path, 'r') as file:
            config = json.load(file)
        if 'rules' not in config:
            config['rules'] = {}
        if 'preferences' not in config:
            config['preferences'] = {
                'radarr_quality_profile': 'Any',
                'sonarr_quality_profile': 'Any'
            }

        return config
    except FileNotFoundError:
        default_config = {
            'rules': {
                'full_seasons': {
                    'get_option': 'season',
                    'action_option': 'monitor',
                    'keep_watched': 'season',
                    'monitor_watched': False,
                    'series': []
                }
            },
            'preferences': {
                'radarr_quality_profile': 'Any',
                'sonarr_quality_profile': 'Any'
            }
        }
        return default_config

def save_config(config):
    with open(config_path, 'w') as file:
        json.dump(config, file, indent=4)

def get_webhook_secret():
    """Return this instance's webhook secret, generating and persisting one on first use."""
    config = load_config()
    secret = config.get('webhook_secret')
    if not secret:
        secret = str(uuid.uuid4())
        config['webhook_secret'] = secret
        save_config(config)
    return secret
