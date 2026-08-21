import os
import requests
import logging
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Define log paths
LOG_PATH = os.getenv('LOG_PATH', '/app/logs/app.log')
MISSING_LOG_PATH = os.getenv('MISSING_LOG_PATH', '/app/logs/missing.log')

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()  # Optional: adds console logging
    ]
)

# Create loggers
logger = logging.getLogger(__name__)
missing_logger = logging.getLogger('missing')

# Add file handler for missing logger
missing_handler = logging.FileHandler(MISSING_LOG_PATH)
missing_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
missing_logger.addHandler(missing_handler)

# Load settings from a JSON configuration file
def load_config():
    config_path = os.getenv('CONFIG_PATH', '/app/config/config.json')
    with open(config_path, 'r') as file:
        config = json.load(file)
    # Ensure required keys are present with default values
    if 'rules' not in config:
        config['rules'] = {}
    return config

config = load_config()

# Define global variables based on environment settings
SONARR_URL = os.getenv('SONARR_URL')
SONARR_API_KEY = os.getenv('SONARR_API_KEY')

def get_server_activity():
    """Read current viewing details from server webhook stored data."""
    try:
        # First try the standardized filename
        filepath = '/app/temp/data_from_server.json'
        if not os.path.exists(filepath):
            # Fallback to the Tautulli-specific filename for backward compatibility
            filepath = '/app/temp/data_from_tautulli.json'
            
        with open(filepath, 'r') as file:
            data = json.load(file)
        
        # Try server-prefix fields first (standardized format)
        series_title = data.get('server_title')
        season_number = data.get('server_season_num')
        episode_number = data.get('server_ep_num')
        
        # If not found, try plex-prefix fields (backward compatibility)
        if not all([series_title, season_number, episode_number]):
            series_title = data.get('plex_title')
            season_number = data.get('plex_season_num')
            episode_number = data.get('plex_ep_num')
        
        if all([series_title, season_number, episode_number]):
            return series_title, int(season_number), int(episode_number)
            
        logger.error(f"Required data fields not found in {filepath}")
        logger.debug(f"Data contents: {data}")
        
    except Exception as e:
        logger.error(f"Failed to read or parse data from server webhook: {str(e)}")
    
    return None, None, None

def get_series_id(series_name):
    """Fetch series ID by name from Sonarr."""
    url = f"{SONARR_URL}/api/v3/series"
    headers = {'X-Api-Key': SONARR_API_KEY}
    response = requests.get(url, headers=headers)
    if response.ok:
        series_list = response.json()
        for series in series_list:
            if series['title'].lower() == series_name.lower():
                return series['id']
        missing_logger.info(f"Series not found in Sonarr: {series_name}")
    else:
        logger.error("Failed to fetch series from Sonarr.")
    return None

def get_episode_details(series_id, season_number):
    """Fetch details of episodes for a specific series and season from Sonarr."""
    url = f"{SONARR_URL}/api/v3/episode?seriesId={series_id}&seasonNumber={season_number}"
    headers = {'X-Api-Key': SONARR_API_KEY}
    response = requests.get(url, headers=headers)
    if response.ok:
        return response.json()
    logger.error("Failed to fetch episode details.")
    return []

def monitor_or_search_episodes(episode_ids, action_option):
    """Either monitor or trigger a search for episodes in Sonarr based on the action_option."""
    monitor_episodes(episode_ids, True)
    if action_option == "search":
        trigger_episode_search_in_sonarr(episode_ids)

def monitor_episodes(episode_ids, monitor=True):
    """Set episodes to monitored or unmonitored in Sonarr."""
    url = f"{SONARR_URL}/api/v3/episode/monitor"
    headers = {'X-Api-Key': SONARR_API_KEY, 'Content-Type': 'application/json'}
    data = {"episodeIds": episode_ids, "monitored": monitor}
    response = requests.put(url, json=data, headers=headers)
    if response.ok:
        action = "monitored" if monitor else "unmonitored"
        logger.info(f"Episodes {episode_ids} successfully {action}.")
    else:
        logger.error(f"Failed to set episodes {action}. Response: {response.text}")

def trigger_episode_search_in_sonarr(episode_ids):
    """Trigger a search for specified episodes in Sonarr."""
    url = f"{SONARR_URL}/api/v3/command"
    headers = {'X-Api-Key': SONARR_API_KEY, 'Content-Type': 'application/json'}
    data = {"name": "EpisodeSearch", "episodeIds": episode_ids}
    response = requests.post(url, json=data, headers=headers)
    if response.ok:
        logger.info("Episode search command sent to Sonarr successfully.")
    else:
        logger.error(f"Failed to send episode search command. Response: {response.text}")

def unmonitor_episodes(episode_ids):
    """Unmonitor specified episodes in Sonarr."""
    monitor_episodes(episode_ids, False)

def get_protected_episode_ids(all_episodes, keep_watched, last_watched_id):
    """
    Determine which episode IDs 'keep_watched' says must survive deletion.

    Returns None to mean "keep everything, don't delete anything" (this is
    the case for keep_watched == 'all', and the safe fallback for an
    unrecognized value - better to keep too much than silently wipe a
    library). Otherwise returns the set of episode IDs to protect.

    For a numeric keep_watched (stored as a string, e.g. "2", since it
    comes straight out of the rule-editing form), this keeps the last N
    episodes chronologically up to and including whichever episode was
    just watched, across season boundaries - i.e. "keep the last N
    watched episodes" the way the setting name reads. It does NOT mean
    "delete everything except whatever's about to be fetched next", which
    is what a prior bug here actually did (see incident 2026-08-21: wiped
    ~31 episodes across 2 shows because keep_watched was never actually
    read as a count anywhere in this code path).
    """
    if keep_watched == "all":
        return None

    if keep_watched == "season":
        last_watched_season = next(
            (ep['seasonNumber'] for ep in all_episodes if ep['id'] == last_watched_id), None
        )
        if last_watched_season is None:
            return None
        return {ep['id'] for ep in all_episodes if ep['seasonNumber'] >= last_watched_season}

    try:
        keep_count = int(keep_watched)
    except (TypeError, ValueError):
        logger.error(f"Invalid keep_watched value '{keep_watched}'; keeping all episodes to avoid unintended deletion.")
        return None

    sorted_episodes = sorted(all_episodes, key=lambda ep: (ep['seasonNumber'], ep['episodeNumber']))
    last_watched_index = next(
        (i for i, ep in enumerate(sorted_episodes) if ep['id'] == last_watched_id), None
    )
    if last_watched_index is None:
        return None

    start = max(0, last_watched_index - keep_count + 1)
    keep_range = sorted_episodes[start:last_watched_index + 1]
    return {ep['id'] for ep in keep_range}

def delete_episodes_in_sonarr(episode_file_ids):
    """Delete specified episodes in Sonarr."""
    if not episode_file_ids:
        logger.info("No episodes to delete.")
        return

    failed_deletes = []
    for episode_file_id in episode_file_ids:
        try:
            url = f"{SONARR_URL}/api/v3/episodeFile/{episode_file_id}"
            headers = {'X-Api-Key': SONARR_API_KEY}
            response = requests.delete(url, headers=headers)
            response.raise_for_status()  # Raise an HTTPError for bad responses
            logger.info(f"Successfully deleted episode file with ID: {episode_file_id}")
        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP error occurred: {http_err} - Response: {response.text}")
            failed_deletes.append(episode_file_id)
        except Exception as err:
            logger.error(f"Other error occurred: {err}")
            failed_deletes.append(episode_file_id)

    if failed_deletes:
        logger.error(f"Failed to delete the following episode files: {failed_deletes}")

def fetch_next_episodes(series_id, season_number, episode_number, get_option):
    """Fetch the next num_episodes episodes starting from the given season and episode."""
    next_episode_ids = []

    try:
        if get_option == "all":
            # Fetch all episodes from Sonarr
            all_episodes = fetch_all_episodes(series_id)
            next_episode_ids.extend([ep['id'] for ep in all_episodes if ep['seasonNumber'] >= season_number])
            return next_episode_ids
        num_episodes = int(get_option)
        # Get remaining episodes in the current season
        current_season_episodes = get_episode_details(series_id, season_number)
        next_episode_ids.extend([ep['id'] for ep in current_season_episodes if ep['episodeNumber'] > episode_number])

        # Fetch episodes from the next season if needed
        next_season_number = season_number + 1
        while len(next_episode_ids) < num_episodes:
            next_season_episodes = get_episode_details(series_id, next_season_number)
            next_episode_ids.extend([ep['id'] for ep in next_season_episodes])
            next_season_number += 1

        return next_episode_ids[:num_episodes]
    except ValueError:
        if get_option == 'season':
            # Fetch all remaining episodes in the current season
            current_season_episodes = get_episode_details(series_id, season_number)
            next_episode_ids.extend([ep['id'] for ep in current_season_episodes if ep['episodeNumber'] > episode_number])
            return next_episode_ids
        else:
            raise ValueError(f"Invalid get_option value: {get_option}")

def fetch_all_episodes(series_id):
    """Fetch all episodes for a series from Sonarr."""
    url = f"{SONARR_URL}/api/v3/episode?seriesId={series_id}"
    headers = {'X-Api-Key': SONARR_API_KEY}
    response = requests.get(url, headers=headers)
    if response.ok:
        return response.json()
    logger.error("Failed to fetch all episodes.")
    return []

def process_episodes_based_on_rules(series_id, season_number, episode_number, rule):
    """
    Fill ahead: fetch/monitor the next episodes per the rule's get_option,
    across season boundaries if needed. This always runs.

    keep_watched (deletion) and monitor_watched (auto-unmonitor after
    watching) are optional, opt-in per rule - omitted means "don't touch
    already-downloaded episodes at all". Library cleanup/retention is
    Maintainerr's job; a rule only reaches into that territory if it
    explicitly asks to.
    """
    next_episode_ids = fetch_next_episodes(series_id, season_number, episode_number, rule['get_option'])
    monitor_or_search_episodes(next_episode_ids, rule['action_option'])

    keep_watched = rule.get('keep_watched')
    monitor_watched = rule.get('monitor_watched')
    if not keep_watched and monitor_watched is None:
        return

    all_episodes = fetch_all_episodes(series_id)
    last_watched_id = next(
        (ep['id'] for ep in all_episodes if ep['seasonNumber'] == season_number and ep['episodeNumber'] == episode_number),
        None
    )
    if last_watched_id is None:
        return

    if monitor_watched is False:
        unmonitor_episodes([last_watched_id])

    if keep_watched:
        protected_ids = get_protected_episode_ids(all_episodes, keep_watched, last_watched_id)
        if protected_ids is not None:
            # Always protect whatever was just fetched for "next up", even
            # though it usually won't have a file yet - guards against the
            # rare case where it's already downloaded (e.g. a fast/cached
            # grab) and would otherwise fall outside the keep window.
            protected_ids |= set(next_episode_ids) | {last_watched_id}
            episodes_to_delete = [
                ep['episodeFileId'] for ep in all_episodes
                if ep['hasFile'] and ep['id'] not in protected_ids and 'episodeFileId' in ep
            ]
            delete_episodes_in_sonarr(episodes_to_delete)
def process_new_series_from_watchlist(series_id, rule):
    """
    Process a newly added series from watchlist based on rule parameters.
    """
    # Fetch all episodes for the series
    all_episodes = fetch_all_episodes(series_id)
    
    # Sort first season episodes by episode number
    first_season_episodes = sorted(
        [ep for ep in all_episodes if ep['seasonNumber'] == 1], 
        key=lambda x: x['episodeNumber']
    )
    
    # Select episodes based on get_option
    if rule['get_option'] == 'all':
        # All episodes in the first season
        episode_ids = [ep['id'] for ep in first_season_episodes]
    
    elif rule['get_option'] == 'season':
        # All episodes in the first season
        episode_ids = [ep['id'] for ep in first_season_episodes]
    
    else:
        try:
            # Treat as number of episodes to get
            num_episodes = int(rule['get_option'])
            episode_ids = [ep['id'] for ep in first_season_episodes[:num_episodes]]
        except ValueError:
            # Fallback to first episode if invalid input
            episode_ids = [first_season_episodes[0]['id']] if first_season_episodes else []
    
    # Monitor or search selected episodes
    if episode_ids:
        monitor_or_search_episodes(episode_ids, rule['action_option'])
    
    return episode_ids


def main():
    series_name, season_number, episode_number = get_server_activity()
    if series_name:
        series_id = get_series_id(series_name)
        if series_id:
            
            rule = next((details for key, details in config['rules'].items() if str(series_id) in details.get('series', [])), None)
            if rule:
                logger.info(f"Applying rule: {rule}")
                process_episodes_based_on_rules(series_id, season_number, episode_number, rule)
            else:
                logger.info(f"No rule found for series ID {series_id}. Skipping operations.")
        else:
            logger.error(f"Series ID not found for series: {series_name}")
    else:
        logger.error("No server activity found.")

if __name__ == "__main__":
    main()

