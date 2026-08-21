from flask import render_template, request, jsonify
import os
import json
from datetime import datetime
import requests
import sonarr_utils
import radarr_utils
import modified_episeerr

import shared
from shared import app
from blueprints.webhooks_routes import safe_datetime_sort, cleanup_config_rules, cleanup_invalid_requests

# Import each route module so its @bp.route(...) decorators register their
# views on the shared Blueprint (shared.bp) before it gets attached to the
# app below.
from blueprints import (
    jellyfin_routes,
    media_images,
    plex_routes,
    tmdb_routes,
    requests_routes,
    webhooks_routes,
    settings_routes,
)

# Registering with name='' keeps every endpoint exactly as it was before the
# split (see the comment on shared.bp for why this matters).
app.register_blueprint(shared.bp, name='')


def check_service_status(url):
    try:
        # Add a longer timeout and use a HEAD request which is lighter
        response = requests.head(url, timeout=3, allow_redirects=True)

        # Check for successful status codes
        if response.status_code in [200, 301, 302, 303, 307, 308]:
            return "Online"
    except requests.exceptions.RequestException:
        pass

    return "Offline"

def get_service_status():
    """Check reachability of every integration the dashboard depends on."""
    status = {
        'sonarr': check_service_status(shared.SONARR_URL) if shared.SONARR_URL else "Offline",
        'radarr': check_service_status(shared.RADARR_URL) if shared.RADARR_URL else "Offline",
        'jellyfin': check_service_status(shared.jellyfin_api.jellyfin_url) if shared.jellyfin_api.jellyfin_url else "Offline",
    }
    if shared.JELLYSEERR_URL:
        status['jellyseerr'] = check_service_status(shared.JELLYSEERR_URL)
    return status

@app.route('/health')
def health():
    status = get_service_status()
    overall_ok = all(value == "Online" for value in status.values())
    return jsonify({'status': 'ok' if overall_ok else 'degraded', 'services': status}), (200 if overall_ok else 503)

@app.route('/')
def home():
    config = shared.load_config()
    service_status = get_service_status()

    # Load Sonarr data
    sonarr_preferences = sonarr_utils.load_preferences()
    current_series = sonarr_utils.fetch_series_and_episodes(sonarr_preferences)
    upcoming_premieres = sonarr_utils.fetch_upcoming_premieres(sonarr_preferences)
    all_series = sonarr_utils.get_series_list(sonarr_preferences)

    # Load Radarr data
    radarr_preferences = radarr_utils.load_preferences()
    recent_movies = radarr_utils.fetch_recent_movies(radarr_preferences)
    upcoming_movies = radarr_utils.fetch_upcoming_movies(radarr_preferences)

    # Add type to TV shows for consistent handling
    for series in current_series:
        series['type'] = 'tv'

    # Combine and sort watching items by date added
    combined_watching = current_series + recent_movies
    combined_watching.sort(key=safe_datetime_sort, reverse=True) # Limit to reasonable number
    combined_watching = combined_watching[:shared.MAX_COMBINED_ITEMS]

    # Add type to TV premieres for consistent handling
    for premiere in upcoming_premieres:
        premiere['type'] = 'tv'

    # Combine upcoming premieres and sort by date
    # In the home route of webhook_listener.py:

    # Make sure this logic works properly:
    combined_upcoming = upcoming_premieres + upcoming_movies

    # Ensure consistent date field for sorting
    for item in combined_upcoming:
        if 'nextAiring' not in item and 'releaseDate' in item:
            item['nextAiring'] = item['releaseDate']

    # Sort by nextAiring - make sure we handle empty strings properly
    combined_upcoming.sort(key=lambda x: x.get('nextAiring', '') or '')

    # Limit to reasonable number
    combined_upcoming = combined_upcoming[:shared.MAX_COMBINED_ITEMS]

    # Get pending requests
    pending_requests = []
    has_pending_requests = False
    try:
        for filename in os.listdir(shared.REQUESTS_DIR):
            if filename.endswith('.json'):
                with open(os.path.join(shared.REQUESTS_DIR, filename), 'r') as f:
                    request_data = json.load(f)
                    pending_requests.append(request_data)
        pending_requests.sort(key=lambda x: x.get('created_at', 0), reverse=True)
        has_pending_requests = len(pending_requests) > 0
    except Exception as e:
        app.logger.error(f"Failed to load pending requests: {str(e)}")

    # Get the last processed show
    last_processed_show = None
    try:
        if os.path.exists(shared.LAST_PROCESSED_FILE):
            with open(shared.LAST_PROCESSED_FILE, 'r') as f:
                last_processed = json.load(f)

                # Calculate how long ago it was processed
                now = datetime.now()
                processed_time = datetime.fromisoformat(last_processed.get('timestamp', now.isoformat()))
                delta = now - processed_time

                # Don't show if it's been more than 15 minutes
                if delta.total_seconds() < 900:  # 15 minutes
                    if delta.seconds >= 60:
                        minutes = delta.seconds // 60
                        time_ago = f"{minutes} minute{'s' if minutes > 1 else ''} ago"
                    else:
                        time_ago = "just now"

                    last_processed['time_ago'] = time_ago
                    last_processed_show = last_processed
    except Exception as e:
        app.logger.error(f"Error loading last processed show: {str(e)}")

    # Map series to rules
    rules_mapping = {str(series_id): rule_name for rule_name, details in config['rules'].items() for series_id in details.get('series', [])}

    for series in all_series:
        series['assigned_rule'] = rules_mapping.get(str(series['id']), 'None')

    # Get Radarr quality profiles
    radarr_profiles = []
    try:
        headers = {'X-Api-Key': radarr_preferences['RADARR_API_KEY']}
        radarr_url = radarr_preferences['RADARR_URL']

        profile_response = requests.get(f"{radarr_url}/api/v3/qualityprofile", headers=headers)
        if profile_response.ok:
            radarr_profiles = profile_response.json()
    except Exception as e:
        app.logger.error(f"Error fetching Radarr profiles: {str(e)}")

    # Get Sonarr quality profiles
    sonarr_profiles = []
    try:
        headers = {'X-Api-Key': sonarr_preferences['SONARR_API_KEY']}
        sonarr_url = sonarr_preferences['SONARR_URL']

        profile_response = requests.get(f"{sonarr_url}/api/v3/qualityprofile", headers=headers)
        if profile_response.ok:
            sonarr_profiles = profile_response.json()
    except Exception as e:
        app.logger.error(f"Error fetching Sonarr profiles: {str(e)}")

    return render_template('index.html',
                        config=config,
                        current_series=combined_watching,
                        upcoming_premieres=combined_upcoming,
                        all_series=all_series,
                        sonarr_url=shared.SONARR_PUBLIC_URL,
                        radarr_url=shared.RADARR_URL,
                        jellyseerr_url=shared.JELLYSEERR_URL,
                        rule=request.args.get('rule', 'full_seasons'),
                        pending_requests=pending_requests,
                        has_pending_requests=has_pending_requests,
                        radarr_profiles=radarr_profiles,
                        sonarr_profiles=sonarr_profiles,
                        last_processed_show=last_processed_show,
                        service_status=service_status)

def initialize_episeerr():
    """Initialize episode tag and check for unmonitored downloads."""
    modified_episeerr.create_episode_tag()
    app.logger.info("Created episode tag")

    # Do an initial check for unmonitored downloads
    try:
        modified_episeerr.check_and_cancel_unmonitored_downloads()
    except Exception as e:
        app.logger.error(f"Error in initial download check: {str(e)}")

if __name__ == '__main__':
    # Clean up invalid requests
    cleanup_invalid_requests()
    # Call config rules cleanup at startup
    cleanup_config_rules()
    # Call initialization function before running the app
    initialize_episeerr()

    # Start the Flask application
    app.run(host='0.0.0.0', port=5002, debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true')
