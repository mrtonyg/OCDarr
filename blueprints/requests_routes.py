from flask import request, jsonify, redirect, url_for, render_template
import os
import json
import time
from datetime import datetime
import requests
import sonarr_utils
import tmdb_utils
import modified_episeerr

import shared
from blueprints.webhooks_routes import cleanup_config_rules

bp = shared.bp


@bp.route('/api/process-selected-episodes', methods=['POST'])
def process_selected_episodes_api():
    """Process selected episodes without creating a new request."""
    try:
        data = request.json
        tmdb_id = data.get('tmdbId')
        season_number = data.get('seasonNumber')
        episode_numbers = data.get('episodes', [])

        # Detect if this is a solo episode 1
        is_first_episode_only = (
            len(episode_numbers) == 1 and
            episode_numbers[0] == 1
        )

        if not tmdb_id or not season_number or not episode_numbers:
            return jsonify({"success": False, "error": "Missing required parameters"}), 400
        try:
            cleanup_config_rules()
        except Exception as e:
            shared.app.logger.error(f"Error during config rule cleanup: {str(e)}")
        # Find the series in Sonarr
        sonarr_preferences = sonarr_utils.load_preferences()
        headers = {
            'X-Api-Key': sonarr_preferences['SONARR_API_KEY'],
            'Content-Type': 'application/json'
        }
        sonarr_url = sonarr_preferences['SONARR_URL']

        # First find the TVDB ID from the TMDB ID
        details = tmdb_utils.get_external_ids(tmdb_id, 'tv')
        tvdb_id = details.get('tvdb_id')

        if not tvdb_id:
            return jsonify({"success": False, "error": "Could not find TVDB ID for this show"}), 400

        # Check if series already exists in Sonarr
        series_id = None
        series_response = requests.get(f"{sonarr_url}/api/v3/series", headers=headers)
        if series_response.ok:
            existing_series = series_response.json()
            for series in existing_series:
                if series.get('tvdbId') == tvdb_id:
                    series_id = series.get('id')
                    title = series.get('title', 'Unknown Series')
                    current_series = series  # Store the full series details
                    break

        if not series_id:
            return jsonify({"success": False, "error": "Show not found in Sonarr"}), 404

        # Determine if we should add to default rule
        add_to_default_rule = (
            is_first_episode_only or  # First episode (S01E01)
            (current_series and modified_episeerr.EPISODES_TAG_ID not in current_series.get('tags', []))  # No episodes tag
        )

        if add_to_default_rule:
            shared.app.logger.info(f"Processing for {title} - Adding to default rule")

            config = shared.load_config()
            default_rule_name = config.get('default_rule', 'Default')

            # Remove episodes tag if it exists
            if current_series and modified_episeerr.EPISODES_TAG_ID in current_series.get('tags', []):
                updated_tags = [tag for tag in current_series.get('tags', []) if tag != modified_episeerr.EPISODES_TAG_ID]

                update_payload = current_series.copy()
                update_payload['tags'] = updated_tags

                update_response = requests.put(f"{sonarr_url}/api/v3/series", headers=headers, json=update_payload)
                if update_response.ok:
                    shared.app.logger.info(f"Removed episodes tag from series {title} (ID: {series_id})")

            # Add to default rule
            if default_rule_name in config['rules']:
                series_id_str = str(series_id)
                if series_id_str not in config['rules'][default_rule_name]['series']:
                    config['rules'][default_rule_name]['series'].append(series_id_str)
                    shared.save_config(config)
                    shared.app.logger.info(f"Added series {title} to default rule")
        else:
            shared.app.logger.info(f"Series {title} does not meet default rule criteria")



        # Process the episodes using modified_episeerr
        # Store selected episodes in modified_episeerr's pending_selections
        if str(series_id) not in modified_episeerr.pending_selections:
            modified_episeerr.pending_selections[str(series_id)] = {
                'title': title,
                'season': season_number,
                'episodes': [],
                'selected_episodes': set(episode_numbers)
            }
        else:
            modified_episeerr.pending_selections[str(series_id)]['selected_episodes'] = set(episode_numbers)

        # Process the episodes using episeerr
        success = modified_episeerr.process_episode_selection(series_id, episode_numbers)

        if not success:
            return jsonify({"success": False, "error": "Failed to process episodes"}), 500

        # Find and delete all requests for this series
        for filename in os.listdir(shared.REQUESTS_DIR):
            if filename.endswith('.json'):
                try:
                    filepath = os.path.join(shared.REQUESTS_DIR, filename)
                    with open(filepath, 'r') as f:
                        request_data = json.load(f)
                        if (request_data.get('series_id') == series_id or
                            request_data.get('tmdb_id') == tmdb_id or
                            request_data.get('tvdb_id') == tvdb_id):
                            os.remove(filepath)
                            shared.app.logger.info(f"Removed request file: {filename}")
                except Exception as e:
                    shared.app.logger.error(f"Error processing request file {filename}: {str(e)}")

        # Save the last processed show
        last_processed = {
            'series_id': series_id,
            'title': title,
            'season': season_number,
            'timestamp': datetime.now().isoformat(),
            'episode_count': len(episode_numbers)
        }

        try:
            with open(shared.LAST_PROCESSED_FILE, 'w') as f:
                json.dump(last_processed, f, indent=2)
        except Exception as e:
            shared.app.logger.error(f"Error saving last processed show: {str(e)}")

        # Run download check to cancel any unmonitored downloads
        modified_episeerr.check_and_cancel_unmonitored_downloads()

        return jsonify({"success": True, "message": f"Processing {len(episode_numbers)} episodes"}), 200

    except Exception as e:
        shared.app.logger.error(f"Error processing selected episodes: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@bp.route('/select-episodes/<tmdb_id>')
def select_episodes(tmdb_id):
    """Show episode selection UI for a TV show."""
    # Get TV show details
    show_data = shared.jellyseerr_api.get_media_details(tmdb_id, media_type='tv')

    if not show_data:
        return render_template('error.html', message="Failed to get show details")

    return render_template('episode_selection.html', show=show_data, tmdb_id=tmdb_id)

@bp.route('/select-seasons/<tmdb_id>')
def select_seasons(tmdb_id):
    """Show season selection UI for a TV show."""
    # Get TV show details
    show_data = shared.jellyseerr_api.get_media_details(tmdb_id, media_type='tv')

    if not show_data:
        return render_template('error.html', message="Failed to get show details")

    # Get tag selection parameter (default to 'episodes')
    tag_selection = request.args.get('tag_selection', 'episodes')

    return render_template('season_selection.html',
                         show=show_data,
                         tmdb_id=tmdb_id,
                         tag_selection=tag_selection)

@bp.route('/process-episode-selection', methods=['POST'])
def process_episode_selection():
    """Process selected episodes by monitoring and searching for them"""
    try:
        shared.app.logger.info(f"Form data received: {request.form}")
        request_id = request.form.get('request_id')
        episode_numbers = request.form.getlist('episodes')
        action = request.form.get('action', 'process')  # 'process' or 'cancel'

        shared.app.logger.info(f"Processing episodes for request {request_id}, action={action}")
        shared.app.logger.info(f"Selected episodes: {episode_numbers}")
        # Load the request
        request_file = os.path.join(shared.REQUESTS_DIR, f"{request_id}.json")
        if not os.path.exists(request_file):
            shared.app.logger.error(f"Request file not found: {request_file}")
            return jsonify({"error": "Request not found"}), 404

        with open(request_file, 'r') as f:
            request_data = json.load(f)

        series_id = request_data['series_id']
        series_title = request_data['title']
        tmdb_id = request_data.get('tmdb_id')
        tvdb_id = request_data.get('tvdb_id')
        jellyseerr_request_id = request_data.get('request_id')

        # NEW CODE: Find and get paths to ALL related requests
        related_request_files = []
        for filename in os.listdir(shared.REQUESTS_DIR):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(shared.REQUESTS_DIR, filename), 'r') as f:
                        other_request = json.load(f)
                        if (other_request.get('series_id') == series_id or
                            (tmdb_id and other_request.get('tmdb_id') == tmdb_id) or
                            (tvdb_id and other_request.get('tvdb_id') == tvdb_id)):
                            related_request_files.append(os.path.join(shared.REQUESTS_DIR, filename))
                except Exception as e:
                    shared.app.logger.error(f"Error reading request file {filename}: {str(e)}")

        if action == 'cancel':
            shared.app.logger.info(f"Cancelling request {request_id} for {series_title}")

            # Delete the Jellyseerr request if available
            if jellyseerr_request_id:
                shared.app.logger.info(f"Deleting Jellyseerr request ID: {jellyseerr_request_id}")
                delete_success = modified_episeerr.delete_overseerr_request(jellyseerr_request_id)
                shared.app.logger.info(f"Jellyseerr delete result: {delete_success}")

            # Delete ALL related request files
            for file_path in related_request_files:
                try:
                    os.remove(file_path)
                    shared.app.logger.info(f"Removed related request file: {os.path.basename(file_path)}")
                except Exception as e:
                    shared.app.logger.error(f"Error removing request file: {str(e)}")

            # Redirect to the home page with appropriate message
            return redirect(url_for('home', section='requests',
                          message=f"Request for {series_title} cancelled"))

        # Convert episode numbers to integers
        episode_numbers = [int(num) for num in episode_numbers if num.isdigit()]

        if not episode_numbers:
            return jsonify({"error": "No valid episodes selected"}), 400

        # Store selected episodes in modified_episeerr's pending_selections
        season_number = request_data['season']
        if str(series_id) not in modified_episeerr.pending_selections:
            modified_episeerr.pending_selections[str(series_id)] = {
                'title': series_title,
                'season': season_number,
                'episodes': request_data.get('episodes', []),
                'selected_episodes': set(episode_numbers)
            }
        else:
            modified_episeerr.pending_selections[str(series_id)]['selected_episodes'] = set(episode_numbers)

        # Process the episodes using episeerr
        shared.app.logger.info(f"Calling process_episode_selection for series_id={series_id}, episodes={episode_numbers}")
        success = modified_episeerr.process_episode_selection(series_id, episode_numbers)
        shared.app.logger.info(f"Result of process_episode_selection: {success}")

        if success:
            # Delete ALL related request files
            for file_path in related_request_files:
                try:
                    os.remove(file_path)
                    shared.app.logger.info(f"Removed related request file: {os.path.basename(file_path)}")
                except Exception as e:
                    shared.app.logger.error(f"Error removing request file: {str(e)}")

            # Also check for any related Sonarr request files
            if tmdb_id:
                sonarr_request_file = os.path.join(os.getcwd(), 'data', 'sonarr_requests', f"{tmdb_id}.json")
                if os.path.exists(sonarr_request_file):
                    os.remove(sonarr_request_file)
                    shared.app.logger.info(f"Removed related Sonarr request file for TMDB ID {tmdb_id}")

            # Delete the Jellyseerr request if available
            if jellyseerr_request_id:
                modified_episeerr.delete_overseerr_request(jellyseerr_request_id)

            # Save the last processed show
            last_processed = {
                'series_id': series_id,
                'title': series_title,
                'season': request_data['season'],
                'timestamp': datetime.now().isoformat(),
                'episode_count': len(episode_numbers)
            }

            try:
                with open(shared.LAST_PROCESSED_FILE, 'w') as f:
                    json.dump(last_processed, f, indent=2)
            except Exception as e:
                shared.app.logger.error(f"Error saving last processed show: {str(e)}")

            # Run download check twice to catch any downloads that might be delayed
            shared.app.logger.info("Checking for downloads to cancel after processing request")
            modified_episeerr.check_and_cancel_unmonitored_downloads()

            shared.app.logger.info("Running download check again")
            modified_episeerr.check_and_cancel_unmonitored_downloads()

            # Redirect to the home page instead of returning JSON
            return redirect(url_for('home', section='requests',
                           message=f"Processing {len(episode_numbers)} episodes for {series_title}"))
        else:
            return redirect(url_for('home', section='requests',
                          message=f"Failed to process episodes for {series_title}"))

    except Exception as e:
        shared.app.logger.error(f"Error processing episode selection: {str(e)}", exc_info=True)
        return redirect(url_for('home', section='requests',
                      message="An error occurred while processing episodes"))

@bp.route('/api/pending-requests/count')
def pending_requests_count():
    """Get the count of pending requests."""
    try:
        count = 0
        for filename in os.listdir(shared.REQUESTS_DIR):
            if filename.endswith('.json'):
                count += 1

        return jsonify({"count": count})
    except Exception as e:
        shared.app.logger.error(f"Error counting pending requests: {str(e)}")
        return jsonify({"count": 0})
@bp.route('/api/new-requests-since', methods=['GET'])
def check_new_requests_since():
    # Get the timestamp from the query parameter
    since_timestamp = request.args.get('since', 0, type=int)

    new_requests = []
    for filename in os.listdir(shared.REQUESTS_DIR):
        if filename.endswith('.json'):
            try:
                with open(os.path.join(shared.REQUESTS_DIR, filename), 'r') as f:
                    request_data = json.load(f)
                    created_at = request_data.get('created_at', 0)

                    if created_at > since_timestamp:
                        new_requests.append({
                            'id': request_data.get('id'),
                            'title': request_data.get('title'),
                            'created_at': created_at
                        })
            except Exception as e:
                shared.app.logger.error(f"Error reading request file {filename}: {str(e)}")

    return jsonify({
        "hasNewRequests": len(new_requests) > 0,
        "newRequests": new_requests,
        "latestTimestamp": int(time.time()) if new_requests else since_timestamp
    })
