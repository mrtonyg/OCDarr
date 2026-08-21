from flask import jsonify
import tmdb_utils

import shared

bp = shared.bp


@bp.route('/api/tmdb/filtered/tv')
def tmdb_filtered_tv():
    """Get filtered TV shows using TMDB API directly."""
    try:
        # Get quality TV shows
        shows_data = tmdb_utils.get_quality_tv_shows()

        # Format the data to match what your frontend expects
        results = []
        for show in shows_data.get('results', []):
            results.append({
                'id': show['id'],
                'name': show['name'],
                'posterUrl': f"https://image.tmdb.org/t/p/w300{show['poster_path']}" if show.get('poster_path') else '/static/placeholder-banner.png',
                'overview': show.get('overview', ''),
                'releaseYear': show.get('first_air_date', '').split('-')[0] if show.get('first_air_date') else '',
                'genre_ids': show.get('genre_ids', [])
            })

        shared.app.logger.info(f"Returning {len(results)} filtered TV shows")
        return jsonify({'results': results})

    except Exception as e:
        shared.app.logger.error(f"Error in tmdb_filtered_tv: {str(e)}", exc_info=True)
        return jsonify({"results": [], "error": str(e)})

@bp.route('/api/tmdb/filtered/movies')
def tmdb_filtered_movies():
    """Get filtered movies using TMDB API directly."""
    try:
        # Get quality movies
        movies_data = tmdb_utils.get_quality_movies()

        # Format the data to match what your frontend expects
        results = []
        for movie in movies_data.get('results', []):
            results.append({
                'id': movie['id'],
                'title': movie['title'],
                'posterUrl': f"https://image.tmdb.org/t/p/w300{movie['poster_path']}" if movie.get('poster_path') else '/static/placeholder-banner.png',
                'overview': movie.get('overview', ''),
                'releaseYear': movie.get('release_date', '').split('-')[0] if movie.get('release_date') else '',
                'genre_ids': movie.get('genre_ids', [])
            })

        shared.app.logger.info(f"Returning {len(results)} filtered movies")
        return jsonify({'results': results})

    except Exception as e:
        shared.app.logger.error(f"Error in tmdb_filtered_movies: {str(e)}", exc_info=True)
        return jsonify({"results": [], "error": str(e)})

@bp.route('/api/tmdb/season/<tmdb_id>/<season_number>')
def get_tmdb_season(tmdb_id, season_number):
    """Get season details from TMDB API."""
    try:
        season_data = tmdb_utils.get_tmdb_endpoint(f"tv/{tmdb_id}/season/{season_number}")
        return jsonify(season_data)
    except Exception as e:
        shared.app.logger.error(f"Error fetching season data: {str(e)}")
        return jsonify({"error": str(e)}), 500
