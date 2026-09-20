"""
Copyright (C) 2026 ReviveMii Project & TheErrorExe, All rights reserved.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""


import re
import requests
from flask import Blueprint, request, Response, abort

import youtubei

bp = Blueprint('users', __name__)


def channelPfp(channel_id):
    try:
        url = f"https://www.youtube.com/channel/{channel_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        cookies = {
            "SOCS": "CAISNQgDEitib3FfaWRlbnRpdHlmcm9udGVuZHVpc2VydmVyXzIwMjYwNzE0LjA3X3AwGgJkZSACGgYIgL7g0gY",
            "PREF": "f6=40000000&tz=Europe.Berlin"
        }
        resp = requests.get(url, headers=headers, cookies=cookies, timeout=5)
        resp.raise_for_status()
        pattern = r'<meta property="og:image" content="([^"]+)"'
        match = re.search(pattern, resp.text)
        return match.group(1) if match else None

    except Exception:
        return None


@bp.route('/feeds/api/users/<user_id>/icon')
def user_icon(user_id):
    avatar_url = channelPfp(user_id)
    if avatar_url:
        try:
            r = requests.get(avatar_url, timeout=5)
            if r.status_code == 200:
                return Response(r.content, mimetype=r.headers.get('Content-Type', 'image/jpeg'))
        except Exception:
            pass

    abort(404)


@bp.route("/feeds/api/users/default/watch_later", methods=["GET"])
def feeds_watch_later_default():
    oauth_token = request.args.get("oauth_token", "")
    if not oauth_token:
        return Response(status=401)
    xml_data, status = youtubei.fetch_watch_later(oauth_token)
    if xml_data is None:
        return Response(status=status)
    return Response(xml_data, mimetype="text/atom+xml")


@bp.route("/feeds/api/users/default/favorites", methods=["GET"])
def feeds_favorites_default():
    oauth_token = request.args.get("oauth_token", "")
    if not oauth_token:
        return Response(status=401)
    xml_data, status = youtubei.fetch_favorites(oauth_token)
    if xml_data is None:
        return Response(status=status)
    return Response(xml_data, mimetype="text/atom+xml")


@bp.route("/feeds/api/users/default", methods=["GET"])
def feeds_users_default():
    oauth_token = request.args.get("oauth_token", "")
    if not oauth_token:
        return Response(status=401)

    xml_data, status = youtubei.fetch_user_info(oauth_token)
    if xml_data is None:
        return Response(status=status)

    return Response(xml_data, mimetype="text/atom+xml")


@bp.route('/pfpproxy/<path:url>', methods=['GET', 'HEAD'])
def pfp_proxy(url):
    if 'yt3.ggpht.com' not in url:
        return "Invalid URL", 400

    if not url.startswith('http://') and not url.startswith('https://'):
        url = 'https://' + url

    try:
        response = requests.request(
            method=request.method,
            url=url,
            headers={key: value for key, value in request.headers if key != 'Host'},
            allow_redirects=True,
            timeout=10
        )

        return Response(
            response.content,
            status=response.status_code,
            headers=dict(response.headers)
        )
    except Exception as e:
        return f"Error: {str(e)}", 500


@bp.route("/feeds/api/users/default/watch_history", methods=["GET"])
def feeds_watch_history_default():
    oauth_token = request.args.get("oauth_token", "")
    if not oauth_token:
        return Response(status=401)

    xml_data, status = youtubei.fetch_watch_history(oauth_token)
    if xml_data is None:
        return Response(status=status)

    return Response(xml_data, mimetype="text/atom+xml")


@bp.route("/feeds/api/users/default/river", methods=["GET"])
def feeds_river_default():
    oauth_token = request.args.get("oauth_token", "")
    if not oauth_token:
        return Response(status=401)
    xml_data, status = youtubei.fetch_river_tv(oauth_token)
    if xml_data is None:
        return Response(status=status)

    return Response(xml_data, mimetype="text/atom+xml")
