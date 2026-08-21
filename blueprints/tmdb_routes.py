from flask import jsonify
import tmdb_utils

import shared

bp = shared.bp


@bp.route('/api/tmdb/season/<tmdb_id>/<season_number>')
def get_tmdb_season(tmdb_id, season_number):
    """Get season details from TMDB API."""
    try:
        season_data = tmdb_utils.get_tmdb_endpoint(f"tv/{tmdb_id}/season/{season_number}")
        return jsonify(season_data)
    except Exception as e:
        shared.app.logger.error(f"Error fetching season data: {str(e)}")
        return jsonify({"error": str(e)}), 500
