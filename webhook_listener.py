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
from blueprints.webhooks_routes import cleanup_config_rules, cleanup_invalid_requests

# Import each route module so its @bp.route(...) decorators register their
# views on the shared Blueprint (shared.bp) before it gets attached to the
# app below.
from blueprints import (
    media_images,
    tmdb_routes,
    requests_routes,
    webhooks_routes,
    settings_routes,
)

# Registering with name='' keeps every endpoint exactly as it was before the
# split (see the comment on shared.bp for why this matters).
app.register_blueprint(shared.bp, name='')


def check_service_status(url, headers=None):
    try:
        response = requests.get(url, headers=headers or {}, timeout=5)
        return "Online" if response.ok else "Offline"
    except requests.exceptions.RequestException:
        return "Offline"

def get_service_status():
    """Check reachability of every integration the dashboard depends on.

    Sonarr/Radarr are hit via their authenticated system/status API
    endpoint (the same X-Api-Key pattern already used everywhere else in
    this codebase to talk to them), not a bare HEAD request to the root
    URL — a plain unauthenticated HEAD against their web UI root was
    unreliable (redirects/auth behavior on the SPA root differs from the
    REST API) and reported "Offline" even when both services were
    confirmed reachable and actively serving real data to the dashboard.
    """
    status = {
        'sonarr': check_service_status(
            f"{shared.SONARR_URL}/api/v3/system/status", {'X-Api-Key': shared.SONARR_API_KEY}
        ) if shared.SONARR_URL else "Offline",
        'radarr': check_service_status(
            f"{shared.RADARR_URL}/api/v3/system/status", {'X-Api-Key': shared.RADARR_API_KEY}
        ) if shared.RADARR_URL else "Offline",
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

    # Needed for Settings > Assign Rules (the checkbox list of every
    # series). Not used for any "recently added" browsing anymore - OCDarr
    # doesn't duplicate library views Plex/Sonarr/Radarr already show.
    sonarr_preferences = sonarr_utils.load_preferences()
    all_series = sonarr_utils.get_series_list(sonarr_preferences)

    radarr_preferences = radarr_utils.load_preferences()

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

    # Get the last time a webhook actually arrived from Tautulli/Plex
    last_webhook_display = "Never received"
    try:
        if os.path.exists(shared.LAST_WEBHOOK_FILE):
            with open(shared.LAST_WEBHOOK_FILE, 'r') as f:
                last_webhook = json.load(f)
            webhook_time = datetime.fromisoformat(last_webhook['timestamp'])
            local_str = webhook_time.strftime('%Y-%m-%d %H:%M:%S %Z')
            title = last_webhook.get('title')
            if title:
                last_webhook_display = f"{local_str} ({title} S{last_webhook.get('season')}E{last_webhook.get('episode')})"
            else:
                last_webhook_display = local_str
    except Exception as e:
        app.logger.error(f"Error loading last webhook info: {str(e)}")

    # "Recently Filled" - plain-text log of what OCDarr itself has done
    # (fill-ahead actions), most recent first. Not a library browser -
    # Plex/Sonarr/Radarr already show what's in the library.
    recent_actions = []
    try:
        if os.path.exists(shared.ACTION_LOG_FILE):
            with open(shared.ACTION_LOG_FILE, 'r') as f:
                entries = json.load(f)
            for entry in reversed(entries):
                entry_time = datetime.fromisoformat(entry['timestamp'])
                count = entry.get('fetched_count', 0)
                recent_actions.append(
                    f"{entry_time.strftime('%Y-%m-%d %H:%M UTC')} — {entry.get('series', 'Unknown')}: "
                    f"watched {entry.get('watched', '?')}, fetched {count} episode{'s' if count != 1 else ''} "
                    f"({entry.get('action', 'monitor')})"
                )
    except Exception as e:
        app.logger.error(f"Error loading action log: {str(e)}")

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

    connection_urls = {
        'Sonarr': shared.SONARR_URL,
        'Radarr': shared.RADARR_URL,
        'Plex': os.getenv('PLEX_URL', ''),
        'Jellyseerr': shared.JELLYSEERR_URL,
    }

    return render_template('index.html',
                        config=config,
                        all_series=all_series,
                        sonarr_url=shared.SONARR_PUBLIC_URL,
                        radarr_url=shared.RADARR_URL,
                        jellyseerr_url=shared.JELLYSEERR_URL,
                        connection_urls=connection_urls,
                        recent_actions=recent_actions,
                        rule=request.args.get('rule', 'full_seasons'),
                        pending_requests=pending_requests,
                        has_pending_requests=has_pending_requests,
                        radarr_profiles=radarr_profiles,
                        sonarr_profiles=sonarr_profiles,
                        last_processed_show=last_processed_show,
                        last_webhook_display=last_webhook_display)

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
