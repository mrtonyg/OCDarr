from flask import request, jsonify
import subprocess
import os
import json
import time
from datetime import datetime, timezone
import requests
import sonarr_utils
import tmdb_utils
import modified_episeerr

import shared

bp = shared.bp

# Global variable to track pending requests from Jellyseerr
# Format: {tvdb_id: {request_id: "123", title: "Show Title"}}
jellyseerr_pending_requests = {}


def safe_datetime_sort(item):
    date_added = item.get('dateAdded')
    if isinstance(date_added, str):
        try:
            # Convert string to offset-aware datetime
            date_added = datetime.fromisoformat(date_added.replace('Z', '+00:00'))
        except:
            # If conversion fails, use current time
            date_added = datetime.now(timezone.utc)

    # If still naive, make it offset-aware
    elif isinstance(date_added, datetime) and date_added.tzinfo is None:
        date_added = date_added.replace(tzinfo=timezone.utc)

    # If date_added is None or another unexpected type
    if not isinstance(date_added, datetime):
        date_added = datetime.now(timezone.utc)

    return date_added

def cleanup_config_rules():
    """Remove series from rules that no longer exist in Sonarr."""
    try:
        config = shared.load_config()

        # Load Sonarr preferences
        sonarr_preferences = sonarr_utils.load_preferences()
        headers = {
            'X-Api-Key': sonarr_preferences['SONARR_API_KEY'],
            'Content-Type': 'application/json'
        }
        sonarr_url = sonarr_preferences['SONARR_URL']

        # Fetch all series from Sonarr
        series_response = requests.get(f"{sonarr_url}/api/v3/series", headers=headers)

        if not series_response.ok:
            shared.app.logger.error("Failed to fetch series from Sonarr during config cleanup")
            return

        # Get set of existing series IDs as strings
        existing_series_ids = set(str(series['id']) for series in series_response.json())

        # Iterate through all rules
        for rule_name, rule_details in config['rules'].items():
            # Filter out series IDs that no longer exist in Sonarr
            original_series_count = len(rule_details['series'])
            rule_details['series'] = [
                series_id for series_id in rule_details['series']
                if series_id in existing_series_ids
            ]

            # Log if any series were removed
            if len(rule_details['series']) != original_series_count:
                shared.app.logger.info(f"Cleaned up rule '{rule_name}': Removed {original_series_count - len(rule_details['series'])} non-existent series")

        # Save the updated configuration
        shared.save_config(config)
        shared.app.logger.info("Completed configuration rules cleanup")

    except Exception as e:
        shared.app.logger.error(f"Error during config rules cleanup: {str(e)}", exc_info=True)

def cleanup_invalid_requests():
    """Remove invalid or corrupted request files"""
    try:
        count = 0
        for filename in os.listdir(shared.REQUESTS_DIR):
            if filename.endswith('.json'):
                filepath = os.path.join(shared.REQUESTS_DIR, filename)
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)

                    # Check for invalid requests
                    if 'episodes' in data and not data['episodes']:
                        # Empty episodes array
                        os.remove(filepath)
                        shared.app.logger.info(f"Removed request with empty episodes: {filename}")
                        count += 1

                    if data.get('title') == 'Unknown Show':
                        # Unknown show with no useful information
                        os.remove(filepath)
                        shared.app.logger.info(f"Removed request for Unknown Show: {filename}")
                        count += 1

                except (json.JSONDecodeError, KeyError) as e:
                    # Invalid JSON or missing required fields
                    os.remove(filepath)
                    shared.app.logger.info(f"Removed invalid request file: {filename}")
                    count += 1

        return count
    except Exception as e:
        shared.app.logger.error(f"Error cleaning up invalid requests: {str(e)}")
        return 0

@bp.route('/sonarr-webhook', methods=['POST'])
def process_sonarr_webhook():
    """Handle incoming Sonarr webhooks for series additions."""
    shared.app.logger.info("Received webhook from Sonarr")

    try:
        json_data = request.json

        # Check if this is a "SeriesAdd" event
        event_type = json_data.get('eventType')
        if event_type != 'SeriesAdd':
            return jsonify({"message": "Not a series add event"}), 200

        # Get important data from the webhook
        series = json_data.get('series', {})
        series_id = series.get('id')
        tvdb_id = series.get('tvdbId')
        tmdb_id = series.get('tmdbId')
        series_title = series.get('title')

        shared.app.logger.info(f"Processing series addition: {series_title} (ID: {series_id}, TVDB: {tvdb_id})")

        # Setup Sonarr connection
        sonarr_preferences = sonarr_utils.load_preferences()
        headers = {
            'X-Api-Key': sonarr_preferences['SONARR_API_KEY'],
            'Content-Type': 'application/json'
        }
        sonarr_url = sonarr_preferences['SONARR_URL']

        # First, get all tags from Sonarr
        tags_response = requests.get(f"{sonarr_url}/api/v3/tag", headers=headers)
        tags = tags_response.json()

        # Create a mapping of tag IDs to tag labels
        tag_mapping = {tag['id']: tag['label'] for tag in tags}

        # Check series tags
        series_tags = series.get('tags', [])
        shared.app.logger.info(f"Series tags: {series_tags}")
        shared.app.logger.info(f"Tag mapping: {tag_mapping}")

        # Check if any of the tags match the 'episodes' label
        has_episodes_tag = any(
        str(tag).lower() == 'episodes'
        for tag in series_tags
        )

        # If no episodes tag, just add show to default rule and exit
        if not has_episodes_tag:
            shared.app.logger.info(f"Series {series_title} has no episodes tag, adding to default rule")

            # Add to default rule
            config = shared.load_config()
            default_rule_name = config.get('default_rule', 'Default')

            if default_rule_name in config['rules']:
                series_id_str = str(series_id)

                # Add to default rule if not already in a rule
                if 'series' not in config['rules'][default_rule_name]:
                    config['rules'][default_rule_name]['series'] = []

                if series_id_str not in config['rules'][default_rule_name]['series']:
                    config['rules'][default_rule_name]['series'].append(series_id_str)
                    shared.save_config(config)
                    shared.app.logger.info(f"Added series {series_title} (ID: {series_id}) to default rule")

            return jsonify({
                "status": "success",
                "message": "Series added to default rule"
            }), 200

        # If it has episodes tag, proceed with full episode selection flow
        shared.app.logger.info(f"Series {series_title} has episodes tag, proceeding with episode selection flow")
        global jellyseerr_pending_requests
        shared.app.logger.info(f"Looking for TVDB ID {tvdb_id} in pending requests")

        tvdb_id_str = str(tvdb_id)
        if tvdb_id_str in jellyseerr_pending_requests:
            jellyseerr_request = jellyseerr_pending_requests[tvdb_id_str]
            shared.app.logger.info(f"Found matching Jellyseerr request for {series_title}: {jellyseerr_request}")

            # Delete the Jellyseerr request if it exists
            if jellyseerr_request and 'request_id' in jellyseerr_request:
                request_id = jellyseerr_request['request_id']
                shared.app.logger.info(f"Canceling Jellyseerr request {request_id} for {series_title}")

                # Direct cancellation
                result = modified_episeerr.delete_overseerr_request(request_id)
                shared.app.logger.info(f"Jellyseerr cancellation result: {result}")

                # Remove from pending requests
                del jellyseerr_pending_requests[tvdb_id_str]
                shared.app.logger.info(f"Removed request {request_id} from pending requests dictionary")
        else:
            shared.app.logger.info(f"No matching Jellyseerr request found for TVDB ID: {tvdb_id_str}")
        # Check if a request already exists for this series
        existing_request = None
        for filename in os.listdir(shared.REQUESTS_DIR):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(shared.REQUESTS_DIR, filename), 'r') as f:
                        request_data = json.load(f)
                        # Check if this is a request for the same series
                        if (request_data.get('series_id') == series_id or
                            (tmdb_id and request_data.get('tmdb_id') == tmdb_id) or
                            (tvdb_id and request_data.get('tvdb_id') == tvdb_id)):
                            existing_request = request_data
                            shared.app.logger.info(f"Found existing request for {series_title}")

                            # Debug log to check if it's a pilot request
                            is_pilot = existing_request.get('pilot', False)
                            shared.app.logger.info(f"Is this a pilot request? {is_pilot}, type: {type(is_pilot)}")
                            shared.app.logger.info(f"Full request data: {json.dumps(existing_request)}")
                            break
                except Exception as e:
                    shared.app.logger.error(f"Error reading request file {filename}: {str(e)}")

        # If a request already exists, don't create a new one
        if existing_request:
            shared.app.logger.info(f"Using existing request for {series_title}")
            return jsonify({
                "status": "success",
                "message": "Request already exists for this series"
            }), 200

        # Ensure we have a TMDB ID for the UI
        if not tmdb_id:
            try:
                # Try to get TMDB ID from TVDB ID
                find_endpoint = f"find/tvdb_{tvdb_id}"
                params = {'external_source': 'tvdb_id'}

                details = tmdb_utils.get_tmdb_endpoint(find_endpoint, params)

                if details and 'tv_results' in details and details['tv_results']:
                    tmdb_id = details['tv_results'][0]['id']
                else:
                    search_results = tmdb_utils.search_tv_shows(series_title)
                    if search_results.get('results'):
                        tmdb_id = search_results['results'][0]['id']
            except Exception as e:
                shared.app.logger.error(f"Error finding TMDB ID: {str(e)}")

        # Setup Sonarr connection
        sonarr_preferences = sonarr_utils.load_preferences()
        headers = {
            'X-Api-Key': sonarr_preferences['SONARR_API_KEY'],
            'Content-Type': 'application/json'
        }
        sonarr_url = sonarr_preferences['SONARR_URL']

        # 1. Unmonitor ALL episodes
        try:
            # Get all episodes for the series
            episodes_response = requests.get(
                f"{sonarr_url}/api/v3/episode?seriesId={series_id}",
                headers=headers
            )

            if episodes_response.ok and episodes_response.json():
                all_episodes = episodes_response.json()
                all_episode_ids = [episode["id"] for episode in all_episodes]

                if all_episode_ids:
                    unmonitor_response = requests.put(
                        f"{sonarr_url}/api/v3/episode/monitor",
                        headers=headers,
                        json={"episodeIds": all_episode_ids, "monitored": False}
                    )

                    if unmonitor_response.ok:
                        shared.app.logger.info(f"Unmonitored all episodes for series {series_title}")
                    else:
                        shared.app.logger.error(f"Failed to unmonitor episodes: {unmonitor_response.text}")
        except Exception as e:
            shared.app.logger.error(f"Error unmonitoring episodes: {str(e)}")

        # 2. Cancel any active downloads
        try:
            modified_episeerr.check_and_cancel_unmonitored_downloads()
        except Exception as e:
            shared.app.logger.error(f"Error cancelling downloads: {str(e)}")

        # 3. Create a new season selection request
        request_id = f"sonarr-webhook-{series_id}-{int(time.time())}"

        pending_request = {
            "id": request_id,
            "series_id": series_id,
            "title": series_title,
            "needs_season_selection": True,
            "tmdb_id": tmdb_id,
            "tvdb_id": tvdb_id,
            "source": "sonarr",
            "source_name": "Sonarr Requires Selection",
            "needs_attention": True,
            "created_at": int(time.time())
        }

        os.makedirs(shared.REQUESTS_DIR, exist_ok=True)

        try:
            cleanup_config_rules()
        except Exception as e:
            shared.app.logger.error(f"Error during config rule cleanup: {str(e)}")

        with open(os.path.join(shared.REQUESTS_DIR, f"{request_id}.json"), 'w') as f:
            json.dump(pending_request, f)

        shared.app.logger.info(f"Created season selection request for {series_title}")

        return jsonify({
            "status": "success",
            "message": "Series requires season selection"
        }), 200

    except Exception as e:
        shared.app.logger.error(f"Error processing Sonarr webhook: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/seerr-webhook', methods=['POST'])
def process_seerr_webhook():
    """Handle incoming Jellyseerr webhooks - store request info for later."""
    try:
        shared.app.logger.info("Received webhook from Jellyseerr")
        json_data = request.json

        # Debug log the webhook data
        shared.app.logger.info(f"Jellyseerr webhook data: {json.dumps(json_data)}")

        # Get the request ID
        request_id = json_data.get('request', {}).get('request_id') or json_data.get('request', {}).get('id')

        # Check if it's a TV show request
        media_type = json_data.get('media', {}).get('media_type')
        if media_type != 'tv':
            shared.app.logger.info(f"Request is not a TV show request. Skipping.")
            return jsonify({"status": "success"}), 200

        # Store the TVDB ID, request ID, and title in the global dictionary
        tvdb_id = json_data.get('media', {}).get('tvdbId')
        title = json_data.get('subject', 'Unknown Show')

        if tvdb_id and request_id:
            # Store the request info for later use by the Sonarr webhook
            global jellyseerr_pending_requests
            jellyseerr_pending_requests[str(tvdb_id)] = {
                'request_id': request_id,
                'title': title,
                'timestamp': int(time.time())
            }

            shared.app.logger.info(f"Stored Jellyseerr request {request_id} for TVDB ID {tvdb_id} ({title})")

            # Clean up old requests (older than 10 minutes)
            current_time = int(time.time())
            expired_tvdb_ids = []

            for tid, info in jellyseerr_pending_requests.items():
                if current_time - info.get('timestamp', 0) > 600:  # 10 minutes
                    expired_tvdb_ids.append(tid)

            for tid in expired_tvdb_ids:
                del jellyseerr_pending_requests[tid]
                shared.app.logger.info(f"Cleaned up expired request for TVDB ID {tid}")

        return jsonify({"status": "success"}), 200

    except Exception as e:
        shared.app.logger.error(f"Error processing Jellyseerr webhook: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/webhook/<secret>', methods=['POST'])
def handle_server_webhook(secret):
    """Handle webhooks from Plex/Tautulli"""
    if secret != shared.get_webhook_secret():
        # 404 rather than 403 so a wrong secret isn't distinguishable from a
        # nonexistent path.
        return jsonify({'status': 'error', 'message': 'Not found'}), 404

    shared.app.logger.info("Received webhook from Tautulli")
    data = request.json
    if data:
        try:
            temp_dir = os.path.join(os.getcwd(), 'temp')
            os.makedirs(temp_dir, exist_ok=True)

            # Standardize field names for Plex/Tautulli data
            plex_data = {
                "server_title": data.get('plex_title'),
                "server_season_num": data.get('plex_season_num'),
                "server_ep_num": data.get('plex_ep_num')
            }

            # Save to the standardized filename
            with open(os.path.join(temp_dir, 'data_from_server.json'), 'w') as f:
                json.dump(plex_data, f)

            result = subprocess.run(["python3", os.path.join(os.getcwd(), "servertosonarr.py")], capture_output=True, text=True)
            if result.stderr:
                shared.app.logger.error(f"Servertosonarr.py error: {result.stderr}")
            return jsonify({'status': 'success'}), 200
        except Exception as e:
            shared.app.logger.error(f"Failed to process Tautulli webhook: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500
    return jsonify({'status': 'error', 'message': 'No data received'}), 400
