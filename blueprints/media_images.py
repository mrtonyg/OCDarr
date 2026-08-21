from flask import Response, send_file
import requests

import shared

bp = shared.bp


@bp.route('/api/sonarr/image/<path:image_path>')
def get_sonarr_image(image_path):
    """Proxy Sonarr media covers so the API key stays server-side (header, not URL)."""
    try:
        image_url = f"{shared.SONARR_URL}/api/v3/mediacover/{image_path}"
        response = requests.get(image_url, headers={'X-Api-Key': shared.SONARR_API_KEY}, stream=True)
        if response.ok:
            return Response(
                response.iter_content(chunk_size=1024),
                content_type=response.headers.get('Content-Type', 'image/jpeg')
            )
        return send_file('static/placeholder-banner.png', mimetype='image/png')
    except Exception as e:
        shared.app.logger.error(f"Error proxying Sonarr image: {str(e)}")
        return send_file('static/placeholder-banner.png', mimetype='image/png')

@bp.route('/api/radarr/image/<path:image_path>')
def get_radarr_image(image_path):
    """Proxy Radarr media covers so the API key stays server-side (header, not URL)."""
    try:
        image_url = f"{shared.RADARR_URL}/api/v3/mediacover/{image_path}"
        response = requests.get(image_url, headers={'X-Api-Key': shared.RADARR_API_KEY}, stream=True)
        if response.ok:
            return Response(
                response.iter_content(chunk_size=1024),
                content_type=response.headers.get('Content-Type', 'image/jpeg')
            )
        return send_file('static/placeholder-banner.png', mimetype='image/png')
    except Exception as e:
        shared.app.logger.error(f"Error proxying Radarr image: {str(e)}")
        return send_file('static/placeholder-banner.png', mimetype='image/png')
