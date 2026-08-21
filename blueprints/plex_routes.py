from flask import request, jsonify
import os
from datetime import datetime
import requests
import sonarr_utils
import radarr_utils
import tmdb_utils
import plex_utils

import shared

bp = shared.bp


@bp.route('/api/plex/sync', methods=['POST'])
def sync_plex_watchlist():
    """Force a sync of the Plex watchlist."""
    try:
        # Read Plex token directly from .env
        plex_token = os.getenv('PLEX_TOKEN', '')

        if not plex_token:
            return jsonify({"success": False, "message": "Plex not connected"}), 400

        plex_api = plex_utils.PlexWatchlistAPI(plex_token)
        success = plex_api.save_watchlist_data()

        if success:
            return jsonify({"success": True, "message": "Watchlist synced successfully"})
        else:
            return jsonify({"success": False, "message": "Failed to sync watchlist"}), 500

    except Exception as e:
        shared.app.logger.error(f"Error syncing Plex watchlist: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500
@bp.route('/api/plex/connect', methods=['POST'])
def connect_to_plex():
    try:
        plex_token = request.form.get('plex_token', '')

        if not plex_token:
            return jsonify({"success": False, "message": "Plex token is required"}), 400

        # Test the token
        plex_api = plex_utils.PlexWatchlistAPI(plex_token)
        watchlist = plex_api.get_watchlist()

        if 'MediaContainer' not in watchlist:
            return jsonify({"success": False, "message": "Invalid Plex token"}), 400

        # Save token to .env file instead of config
        with open('.env', 'a') as f:
            f.write(f"\nPLEX_TOKEN={plex_token}\n")

        # Update config to mark Plex as connected
        config = shared.load_config()
        if 'plex' not in config:
            config['plex'] = {}

        config['plex']['connected'] = True
        config['plex']['auto_download'] = False  # Default to off
        config['plex']['last_sync'] = datetime.now().isoformat()

        shared.save_config(config)

        # Sync watchlist
        plex_api.save_watchlist_data()

        return jsonify({"success": True, "message": "Connected to Plex successfully"})
    except Exception as e:
        shared.app.logger.error(f"Error connecting to Plex: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500

@bp.route('/api/plex/watchlist')
def get_plex_watchlist():
    try:
        plex_token = os.getenv('PLEX_TOKEN', '')

        if not plex_token:
            return jsonify({"success": False, "message": "Plex not connected"}), 400

        plex_api = plex_utils.PlexWatchlistAPI(plex_token)
        watchlist_data = plex_api.get_watchlist()

        # Prepare categories and stats
        categories = {
            'tv_in_watchlist': [],
            'tv_not_in_arr': [],
            'movie_in_watchlist': [],
            'movie_not_in_arr': []
        }

        # Get existing Sonarr/Radarr series
        sonarr_preferences = sonarr_utils.load_preferences()
        sonarr_series = sonarr_utils.get_series_list(sonarr_preferences)
        sonarr_tmdb_ids = set(str(series.get('tmdbId')) for series in sonarr_series if series.get('tmdbId'))

        radarr_preferences = radarr_utils.load_preferences()
        radarr_movies = radarr_utils.get_movie_list(radarr_preferences)
        radarr_tmdb_ids = set(str(movie.get('tmdbId')) for movie in radarr_movies if movie.get('tmdbId'))

        # Check the correct structure from the API
        if 'MediaContainer' in watchlist_data and 'Metadata' in watchlist_data['MediaContainer']:
            items = watchlist_data['MediaContainer']['Metadata']

            for item in items:
                media_type = 'movie' if item.get('type') == 'movie' else 'tv'
                processed_item = {
                    'title': item.get('title', ''),
                    'type': media_type,
                    'year': item.get('year'),
                    'plex_guid': item.get('guid', ''),
                    'thumb': item.get('thumb', '')
                }

                # Attempt to get TMDB ID
                try:
                    if media_type == 'movie':
                        search_results = tmdb_utils.search_movies(processed_item['title'])
                        if search_results.get('results'):
                            processed_item['tmdb_id'] = search_results['results'][0]['id']
                    else:
                        search_results = tmdb_utils.search_tv_shows(processed_item['title'])
                        if search_results.get('results'):
                            processed_item['tmdb_id'] = search_results['results'][0]['id']
                except Exception as e:
                    shared.app.logger.error(f"Error getting TMDB ID for {processed_item['title']}: {str(e)}")

                # Categorize items
                tmdb_id = str(processed_item.get('tmdb_id', ''))
                if media_type == 'tv':
                    categories['tv_in_watchlist'].append(processed_item)
                    if not tmdb_id or tmdb_id not in sonarr_tmdb_ids:
                        categories['tv_not_in_arr'].append(processed_item)
                else:
                    categories['movie_in_watchlist'].append(processed_item)
                    if not tmdb_id or tmdb_id not in radarr_tmdb_ids:
                        categories['movie_not_in_arr'].append(processed_item)

        # Get library counts
        library_sections = plex_api.get_library_sections()
        library_stats = {
            "movies": 0,
            "tv_shows": 0
        }

        if library_sections.get("movie"):
            try:
                movie_url = f"{plex_api.plex_url}/library/sections/{library_sections['movie']}/all"
                movie_response = requests.get(movie_url, headers=plex_api.get_headers())
                if movie_response.ok:
                    movie_data = movie_response.json()
                    library_stats["movies"] = movie_data.get("MediaContainer", {}).get("size", 0)
            except Exception as e:
                shared.app.logger.error(f"Error getting movie count: {str(e)}")

        if library_sections.get("tv"):
            try:
                tv_url = f"{plex_api.plex_url}/library/sections/{library_sections['tv']}/all"
                tv_response = requests.get(tv_url, headers=plex_api.get_headers())
                if tv_response.ok:
                    tv_data = tv_response.json()
                    library_stats["tv_shows"] = tv_data.get("MediaContainer", {}).get("size", 0)
            except Exception as e:
                shared.app.logger.error(f"Error getting TV show count: {str(e)}")

        # Prepare watchlist stats
        watchlist_stats = {
            "movies": len(categories['movie_in_watchlist']),
            "tv_shows": len(categories['tv_in_watchlist'])
        }

        response_data = {
            'success': True,
            'watchlist': {
                'categories': categories,
                'last_updated': datetime.now().isoformat(),
                'count': len(categories['tv_in_watchlist']) + len(categories['movie_in_watchlist']),
                'stats': {
                    'library_stats': library_stats,
                    'watchlist_stats': watchlist_stats
                }
            }
        }

        return jsonify(response_data)

    except Exception as e:
        shared.app.logger.error(f"Error fetching Plex watchlist: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500

@bp.route('/api/recent-additions')
def get_recent_additions():
    """Get recently added content from Plex."""
    try:
        # Check for Plex token
        plex_token = os.getenv('PLEX_TOKEN', '')

        if not plex_token:
            return jsonify({
                'success': False,
                'message': 'Plex token not configured',
                'items': []
            }), 400

        # Create Plex API instance
        plex_api = plex_utils.PlexWatchlistAPI(plex_token)

        # Get recent items
        recent_items = plex_api.get_recent_items()

        # Format response
        response_data = {
            'success': True,
            'items': recent_items,
            'count': len(recent_items)
        }

        return jsonify(response_data)

    except Exception as e:
        shared.app.logger.error(f"Error fetching recent Plex additions: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e),
            'items': []
        }), 500
