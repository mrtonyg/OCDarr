from flask import request, jsonify, Response, send_file
import re
import json
from datetime import datetime
import requests
from jellyfin_utils import JellyfinAPI
import tmdb_utils

import shared

bp = shared.bp


# Jellyfin Routes
@bp.route('/api/jellyfin/connect', methods=['POST'])
def connect_to_jellyfin():
    try:
        data = request.json
        jellyfin_url = data.get('jellyfin_url', '')
        jellyfin_token = data.get('jellyfin_token', '')
        jellyfin_user_id = data.get('jellyfin_user_id', '')

        if not jellyfin_url or not jellyfin_token or not jellyfin_user_id:
            return jsonify({"success": False, "message": "All Jellyfin connection parameters are required"}), 400

        # Create temp JellyfinAPI instance to test connection and resolve ID if needed
        temp_api = JellyfinAPI()
        temp_api.jellyfin_url = jellyfin_url
        temp_api.jellyfin_token = jellyfin_token

        # Check if the provided user_id looks like a username (shorter than GUID)
        if len(jellyfin_user_id) < 32:
            # Treat as username and resolve
            resolved_id = temp_api.get_user_id_by_name(jellyfin_user_id)
            if resolved_id:
                jellyfin_user_id = resolved_id
                shared.app.logger.info(f"Resolved username '{data.get('jellyfin_user_id')}' to ID: {jellyfin_user_id}")
            else:
                return jsonify({"success": False, "message": f"Could not find user with name: {jellyfin_user_id}"}), 400

        # Update the global API instance
        shared.jellyfin_api = JellyfinAPI()
        shared.jellyfin_api.jellyfin_url = jellyfin_url
        shared.jellyfin_api.jellyfin_token = jellyfin_token
        shared.jellyfin_api.jellyfin_user_id = jellyfin_user_id

        # Test connection
        stats = shared.jellyfin_api.get_library_stats()

        # Save to .env file
        with open('.env', 'r') as f:
            env_content = f.read()

        # Update or add the variables
        if 'JELLYFIN_URL=' in env_content:
            env_content = re.sub(r'JELLYFIN_URL=.*', f'JELLYFIN_URL={jellyfin_url}', env_content)
        else:
            env_content += f'\nJELLYFIN_URL={jellyfin_url}'

        if 'JELLYFIN_TOKEN=' in env_content:
            env_content = re.sub(r'JELLYFIN_TOKEN=.*', f'JELLYFIN_TOKEN={jellyfin_token}', env_content)
        else:
            env_content += f'\nJELLYFIN_TOKEN={jellyfin_token}'

        if 'JELLYFIN_USER_ID=' in env_content:
            env_content = re.sub(r'JELLYFIN_USER_ID=.*', f'JELLYFIN_USER_ID={jellyfin_user_id}', env_content)
        else:
            env_content += f'\nJELLYFIN_USER_ID={jellyfin_user_id}'

        with open('.env', 'w') as f:
            f.write(env_content)

        return jsonify({
            "success": True,
            "message": "Connected to Jellyfin successfully",
            "stats": stats
        })

    except Exception as e:
        shared.app.logger.error(f"Error connecting to Jellyfin: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500

@bp.route('/api/jellyfin/sync', methods=['POST'])
def sync_jellyfin_data():
    """Force a refresh of Jellyfin data."""
    try:
        if not shared.jellyfin_api.jellyfin_token:
            return jsonify({"success": False, "message": "Jellyfin not connected"}), 400

        # We don't need to save data persistently like with Plex
        # Just return success as we'll fetch fresh data on each page load
        return jsonify({"success": True, "message": "Jellyfin data refreshed"})

    except Exception as e:
        shared.app.logger.error(f"Error syncing Jellyfin data: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500

@bp.route('/api/jellyfin/stats')
def get_jellyfin_stats():
    try:
        # Debug logging
        shared.app.logger.info(f"JellyfinAPI config: URL={shared.jellyfin_api.jellyfin_url}, UserID={shared.jellyfin_api.jellyfin_user_id}")
        shared.app.logger.info(f"Token exists: {bool(shared.jellyfin_api.jellyfin_token)}")

        if not shared.jellyfin_api.jellyfin_token:
            shared.app.logger.error("No Jellyfin token configured")
            return jsonify({"success": False, "message": "Jellyfin not connected - no token"}), 400

        if not shared.jellyfin_api.jellyfin_user_id:
            shared.app.logger.error("No Jellyfin user ID configured")
            return jsonify({"success": False, "message": "Jellyfin not connected - no user ID"}), 400

        # Test connection
        try:
            test_url = f"{shared.jellyfin_api.jellyfin_url}/Users/{shared.jellyfin_api.jellyfin_user_id}"
            shared.app.logger.info(f"Testing Jellyfin connection with URL: {test_url}")

            response = requests.get(
                test_url,
                headers=shared.jellyfin_api.get_headers(),
                timeout=5
            )

            shared.app.logger.info(f"Jellyfin test response: Status={response.status_code}")

            if not response.ok:
                shared.app.logger.error(f"Failed to connect to Jellyfin: {response.status_code} - {response.text[:100]}")
                return jsonify({
                    "success": False,
                    "message": f"Cannot connect to Jellyfin: {response.status_code}",
                    "stats": {
                        "library_stats": {"movies": 0, "tv_shows": 0},
                        "favorites_stats": {"movies": 0, "tv_shows": 0}
                    },
                    "lastUpdated": datetime.now().isoformat()
                }), 200  # Return 200 but with error info so frontend can display it

        except requests.exceptions.RequestException as e:
            shared.app.logger.error(f"Connection error to Jellyfin: {str(e)}")
            return jsonify({
                "success": False,
                "message": f"Cannot connect to Jellyfin: {str(e)}",
                "stats": {
                    "library_stats": {"movies": 0, "tv_shows": 0},
                    "favorites_stats": {"movies": 0, "tv_shows": 0}
                },
                "lastUpdated": datetime.now().isoformat()
            }), 200  # Return 200 but with error info

        # If we got here, connection is good - get stats
        stats = shared.jellyfin_api.get_formatted_stats()

        # Log the stats for debugging
        shared.app.logger.info(f"Jellyfin stats retrieved: {json.dumps(stats)}")

        return jsonify(stats)

    except Exception as e:
        shared.app.logger.error(f"Error getting Jellyfin stats: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "message": str(e),
            "stats": {
                "library_stats": {"movies": 0, "tv_shows": 0},
                "favorites_stats": {"movies": 0, "tv_shows": 0}
            },
            "lastUpdated": datetime.now().isoformat()
        }), 200  # Return 200 but with error info

@bp.route('/api/jellyfin/favorites')
def get_jellyfin_favorites():
    try:
        shared.app.logger.info("Jellyfin favorites API called")

        if not shared.jellyfin_api.jellyfin_token:
            return jsonify({"success": False, "message": "Jellyfin not connected", "items": []}), 200

        # Use this URL with specific parameters
        url = f"{shared.jellyfin_api.jellyfin_url}/Users/{shared.jellyfin_api.jellyfin_user_id}/Items"

        params = {
            'Recursive': 'true',
            'IsFavorite': 'true',
            'IncludeItemTypes': 'Movie,Series',  # Only include Movies and TV Series
            'SortBy': 'DateCreated,SortName',
            'SortOrder': 'Descending'
        }

        shared.app.logger.info(f"Getting favorites from: {url} with params: {params}")

        response = requests.get(
            url,
            headers=shared.jellyfin_api.get_headers(),
            params=params
        )

        shared.app.logger.info(f"Favorites response: {response.status_code}")

        if response.ok:
            data = response.json()
            items = data.get('Items', [])
            shared.app.logger.info(f"Found {len(items)} favorites")

            # Process items
            processed_items = []
            for item in items:
                # Determine media type
                media_type = 'movie' if item.get('Type') == 'Movie' else 'tv'

                processed_item = {
                    'Id': item.get('Id'),
                    'Name': item.get('Name', ''),
                    'Type': item.get('Type', ''),
                    'type': media_type,
                    'ProductionYear': item.get('ProductionYear'),
                    'Overview': item.get('Overview', ''),
                    'ImageTags': item.get('ImageTags', {})
                }

                processed_items.append(processed_item)

            return jsonify({"success": True, "items": processed_items, "count": len(processed_items)})
        else:
            shared.app.logger.error(f"Failed to get favorites: {response.status_code} - {response.text[:100]}")
            return jsonify({"success": False, "message": f"Failed to get favorites: {response.status_code}", "items": []}), 200

    except Exception as e:
        shared.app.logger.error(f"Error getting Jellyfin favorites: {str(e)}")
        return jsonify({"success": False, "message": str(e), "items": []}), 200

@bp.route('/api/jellyfin/recommendations')
def get_jellyfin_recommendations():
    try:
        shared.app.logger.info("Jellyfin recommendations API called")

        # Use TMDB data for recommendations
        movies_data = tmdb_utils.get_quality_movies()
        tv_data = tmdb_utils.get_quality_tv_shows()

        # Format the results
        movies = []
        for movie in movies_data.get('results', [])[:12]:
            movies.append({
                'Id': movie.get('id'),
                'Name': movie.get('title'),
                'type': 'movie',
                'ProductionYear': movie.get('release_date', '').split('-')[0] if movie.get('release_date') else '',
                'Overview': movie.get('overview', ''),
                'posterUrl': f"https://image.tmdb.org/t/p/w300{movie.get('poster_path')}" if movie.get('poster_path') else None
            })

        shows = []
        for show in tv_data.get('results', [])[:12]:
            shows.append({
                'Id': show.get('id'),
                'Name': show.get('name'),
                'type': 'tv',
                'ProductionYear': show.get('first_air_date', '').split('-')[0] if show.get('first_air_date') else '',
                'Overview': show.get('overview', ''),
                'posterUrl': f"https://image.tmdb.org/t/p/w300{show.get('poster_path')}" if show.get('poster_path') else None
            })

        # Combine and limit
        recommendations = movies + shows
        recommendations = recommendations[:24]

        return jsonify({"success": True, "items": recommendations, "count": len(recommendations)})

    except Exception as e:
        shared.app.logger.error(f"Error getting recommendations: {str(e)}")
        return jsonify({"success": False, "message": str(e), "items": []}), 200

@bp.route('/api/jellyfin/recent-additions')
def get_jellyfin_recent_additions():
    try:
        shared.app.logger.info("Jellyfin recent additions API called")

        if not shared.jellyfin_api.jellyfin_token:
            return jsonify({"success": False, "message": "Jellyfin not connected", "items": []}), 200

        # Use the Items/Latest endpoint
        url = f"{shared.jellyfin_api.jellyfin_url}/Users/{shared.jellyfin_api.jellyfin_user_id}/Items/Latest"

        shared.app.logger.info(f"Getting recent items from: {url}")

        response = requests.get(
            url,
            headers=shared.jellyfin_api.get_headers(),
            params={
                'Limit': 24,
                'Fields': 'Overview,ProductionYear',
                'IncludeItemTypes': 'Movie,Series'  # Only get Movies and Series, exclude Episodes
            }
        )

        shared.app.logger.info(f"Recent items response: {response.status_code}")

        if response.ok:
            items = response.json()
            shared.app.logger.info(f"Found {len(items)} recent items")

            # Process items
            processed_items = []
            for item in items:
                # Determine media type
                media_type = 'movie' if item.get('Type') == 'Movie' else 'tv'

                processed_item = {
                    'Id': item.get('Id'),
                    'Name': item.get('Name', ''),
                    'Type': item.get('Type', ''),
                    'type': media_type,
                    'ProductionYear': item.get('ProductionYear'),
                    'Overview': item.get('Overview', ''),
                    'ImageTags': item.get('ImageTags', {})
                }

                processed_items.append(processed_item)

            return jsonify({"success": True, "items": processed_items, "count": len(processed_items)})
        else:
            shared.app.logger.error(f"Failed to get recent items: {response.status_code} - {response.text[:100]}")
            return jsonify({"success": False, "message": f"Failed to get recent items: {response.status_code}", "items": []}), 200

    except Exception as e:
        shared.app.logger.error(f"Error getting Jellyfin recent additions: {str(e)}")
        return jsonify({"success": False, "message": str(e), "items": []}), 200

@bp.route('/api/jellyfin/image/<item_id>/<image_type>')
def get_jellyfin_image(item_id, image_type):
    try:
        if not shared.jellyfin_api.jellyfin_token:
            return jsonify({"success": False, "message": "Jellyfin not connected"}), 400

        # Get parameters
        width = request.args.get('width', '300')
        tag = request.args.get('tag', '')

        # Build URL
        image_url = f"{shared.jellyfin_api.jellyfin_url}/Items/{item_id}/Images/{image_type}"

        if tag:
            image_url += f"?tag={tag}&width={width}"
        else:
            image_url += f"?width={width}"

        # Proxy the image to avoid CORS issues
        response = requests.get(image_url, headers=shared.jellyfin_api.get_headers(), stream=True)

        if response.ok:
            return Response(
                response.iter_content(chunk_size=1024),
                content_type=response.headers['Content-Type']
            )
        else:
            return send_file('static/placeholder-banner.png', mimetype='image/png')

    except Exception as e:
        shared.app.logger.error(f"Error getting Jellyfin image: {str(e)}")
        return send_file('static/placeholder-banner.png', mimetype='image/png')
