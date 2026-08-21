from flask import request, jsonify, redirect, url_for
import requests
import sonarr_utils
import modified_episeerr

import shared
from blueprints.webhooks_routes import cleanup_invalid_requests

bp = shared.bp


@bp.route('/update-settings', methods=['POST'])
def update_settings():
    config = shared.load_config()

    rule_name = request.form.get('rule_name')
    if rule_name == 'add_new':
        rule_name = request.form.get('new_rule_name')
        if not rule_name:
            return redirect(url_for('home', section='settings', message="New rule name is required."))

    get_option = request.form.get('get_option')
    keep_watched = request.form.get('keep_watched', '').strip()
    monitor_watched_raw = request.form.get('monitor_watched', '').strip()

    # keep_watched (deletion) and monitor_watched (auto-unmonitor) are
    # optional, opt-in per rule - left blank/unset means "don't touch
    # already-downloaded episodes", which is the default. Only store them
    # when the user actually chose a value; library cleanup is Maintainerr's
    # job unless a rule explicitly asks OCDarr to also manage it.
    new_rule = {
        'get_option': get_option,
        'action_option': request.form.get('action_option'),
        'series': config['rules'].get(rule_name, {}).get('series', [])
    }
    if keep_watched:
        new_rule['keep_watched'] = keep_watched
    if monitor_watched_raw:
        new_rule['monitor_watched'] = monitor_watched_raw.lower() == 'true'

    config['rules'][rule_name] = new_rule

    shared.save_config(config)
    return redirect(url_for('home', section='settings', message="Settings updated successfully"))

@bp.route('/delete_rule', methods=['POST'])
def delete_rule():
    config = shared.load_config()
    rule_name = request.form.get('rule_name')
    if rule_name and rule_name in config['rules']:
        del config['rules'][rule_name]
        shared.save_config(config)
        return redirect(url_for('home', section='settings', message=f"Rule '{rule_name}' deleted successfully."))
    else:
        return redirect(url_for('home', section='settings', message=f"Rule '{rule_name}' not found."))

@bp.route('/assign_rules', methods=['POST'])
def assign_rules():
    config = shared.load_config()
    rule_name = request.form.get('assign_rule_name')
    submitted_series_ids = set(request.form.getlist('series_ids'))

    # For series being assigned to a rule, remove the episodes tag
    sonarr_preferences = sonarr_utils.load_preferences()
    headers = {
        'X-Api-Key': sonarr_preferences['SONARR_API_KEY'],
        'Content-Type': 'application/json'
    }
    sonarr_url = sonarr_preferences['SONARR_URL']

    # Get all series first
    series_response = requests.get(f"{sonarr_url}/api/v3/series", headers=headers)
    if series_response.ok:
        series_list = series_response.json()
        for series in series_list:
            # If this series is being assigned to ANY rule and has the episodes tag
            if str(series['id']) in submitted_series_ids and modified_episeerr.EPISODES_TAG_ID in series.get('tags', []):
                # Remove the episodes tag
                updated_tags = [tag for tag in series.get('tags', []) if tag != modified_episeerr.EPISODES_TAG_ID]
                series['tags'] = updated_tags

                # Update the series
                update_response = requests.put(f"{sonarr_url}/api/v3/series", headers=headers, json=series)
                if update_response.ok:
                    shared.app.logger.info(f"Removed episodes tag from series {series['title']} (ID: {series['id']})")
                else:
                    shared.app.logger.error(f"Failed to remove episodes tag from series {series['id']}")

    if rule_name == 'None':
        # Remove series from any rule
        for key, details in config['rules'].items():
            details['series'] = [sid for sid in details.get('series', []) if sid not in submitted_series_ids]
    else:
        # Update the rule's series list to include only those submitted
        if rule_name in config['rules']:
            current_series = set(config['rules'][rule_name]['series'])
            updated_series = current_series.union(submitted_series_ids)
            config['rules'][rule_name]['series'] = list(updated_series)

        # Update other rules to remove the series if it's no longer assigned there
        for key, details in config['rules'].items():
            if key != rule_name:
                # Preserve series not submitted in other rules
                details['series'] = [sid for sid in details.get('series', []) if sid not in submitted_series_ids]

    shared.save_config(config)
    return redirect(url_for('home', section='settings', message="Rules updated successfully."))

@bp.route('/unassign_rules', methods=['POST'])
def unassign_rules():
    config = shared.load_config()
    rule_name = request.form.get('assign_rule_name')
    submitted_series_ids = set(request.form.getlist('series_ids'))

    # Update the rule's series list to exclude those submitted
    if rule_name in config['rules']:
        current_series = set(config['rules'][rule_name]['series'])
        updated_series = current_series.difference(submitted_series_ids)
        config['rules'][rule_name]['series'] = list(updated_series)

    shared.save_config(config)
    return redirect(url_for('home', section='settings', message="Rules updated successfully."))

@bp.route('/update_profile_settings', methods=['POST'])
def update_profile_settings():
    """Update profile settings."""
    try:
        config = shared.load_config()

        # Ensure preferences section exists
        if 'preferences' not in config:
            config['preferences'] = {}

        # Update preferences
        config['preferences']['radarr_quality_profile'] = request.form.get('radarr_quality_profile', 'Any')
        config['preferences']['sonarr_quality_profile'] = request.form.get('sonarr_quality_profile', 'Any')

        shared.save_config(config)

        return redirect(url_for('home', section='settings', subsection='profile_settings',
                      message="Profile settings updated successfully"))
    except Exception as e:
        shared.app.logger.error(f"Error updating profile settings: {str(e)}")
        return redirect(url_for('home', section='settings', subsection='profile_settings',
                      message=f"Error: {str(e)}"))

@bp.route('/cleanup-requests', methods=['GET'])
def cleanup_requests_route():
    """Route to manually clean up invalid requests"""
    count = cleanup_invalid_requests()
    return jsonify({"message": f"Cleaned up {count} invalid requests"}), 200
