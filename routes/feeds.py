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
import json
import requests
import xml.etree.ElementTree as ET
from flask import Blueprint, request, Response, jsonify, abort

from config import CATEGORY_MAP, thumbnail_url_cache
from scraper import scrape
from thumbnails import get_first_video_id_from_route
from thumbnails import queue_standby

bp = Blueprint('feeds', __name__)


@bp.route('/complete/search')
def completesearch():
    query = request.args.get('q')
    if not query:
        return jsonify({"error": "Missing query"}), 400

    suggest_url = (
        "https://suggestqueries-clients6.youtube.com/complete/search?ds=yt&hl=en&gl=us&client=youtube&gs_ri=youtube&q=" + query
    )

    try:
        response = requests.get(suggest_url)
        if response.status_code != 200:
            return jsonify({"error": f"Failed to fetch suggestions: HTTP {response.status_code}"}), 500
        jsonp = response.text
        json_str = re.search(r'\[.*\]', jsonp).group(0)
        data = json.loads(json_str)
        suggestions = [item[0] for item in data[1]]
        root = ET.Element("toplevel")
        for suggestion in suggestions:
            complete_suggestion = ET.SubElement(root, "CompleteSuggestion")
            suggestion_elem = ET.SubElement(complete_suggestion, "suggestion")
            suggestion_elem.set("data", suggestion)
        xml_string = ET.tostring(root, encoding="utf-8", method="xml").decode("utf-8")
        xml_string = '<?xml version="1.0" encoding="UTF-8"?>' + xml_string

        return Response(xml_string, mimetype='text/xml')

    except Exception as e:
        return jsonify({"error": f"Error processing suggestions: {str(e)}"}), 500


@bp.route('/feeds/api/videos')
def api_videos():
    query = request.args.get('q')
    if not query:
        return jsonify({"error": "Missing 'q' parameter"}), 400
    try:
        return scrape.search(query)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/feeds/api/users/trends/favorites')
def trending():
    try:
        return scrape.trends()
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/feeds/api/standardfeeds/US/most_popular_Music')
def trending_music():
    try:
        return scrape.music()
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/feeds/api/standardfeeds/US/most_popular_Games')
def trending_gaming():
    try:
        return scrape.gaming()
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/feeds/api/standardfeeds/US/most_popular_Sports')
def trending_sports():
    try:
        return scrape.sports()
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/feeds/api/standardfeeds/US/most_popular_FilmAnimation')
def trending_film_animation():
    try:
        return scrape.film_animation()
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/feeds/api/standardfeeds/US/most_popular_Entertainment')
def trending_entertainment():
    try:
        return scrape.entertainment()
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/feeds/api/standardfeeds/US/most_popular_Comedy')
def trending_comedy():
    try:
        return scrape.comedy()
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/feeds/api/standardfeeds/US/most_popular_NewsPolitics')
def trending_news_politics():
    try:
        return scrape.news_politics()
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/feeds/api/standardfeeds/US/most_popular_PeopleBlogs')
def trending_people_blogs():
    try:
        return scrape.people_blogs()
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/feeds/api/standardfeeds/US/most_popular_ScienceTech')
def trending_science_technology():
    try:
        return scrape.science_technology()
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/feeds/api/standardfeeds/US/most_popular_HowtoStyle')
def trending_howto_style():
    try:
        return scrape.howto_style()
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/feeds/api/standardfeeds/US/most_popular_Education')
def trending_education():
    try:
        return scrape.education()
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/feeds/api/standardfeeds/US/most_popular_PetsAnimals')
def trending_pets_animals():
    try:
        return scrape.pets_animals()
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/dl/<category>.jpg')
def serve_thumbnail(category):
    allowed = set(CATEGORY_MAP.values())
    if category not in allowed:
        abort(404)
    queue_standby(category)

    url = thumbnail_url_cache.get(category)
    if not url:
        for cat, name in CATEGORY_MAP.items():
            if name == category:
                video_id = get_first_video_id_from_route(cat)
                if video_id:
                    url = f"http://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                    thumbnail_url_cache[category] = url
                    break

    if not url:
        abort(404)

    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return Response(
                r.content,
                mimetype=r.headers.get('Content-Type', 'image/jpeg'),
                headers={
                    'Cache-Control': 'public, max-age=86400, immutable',
                    'Expires': 'Thu, 31 Dec 2037 23:55:55 GMT',
                    'Pragma': 'cache'
                }
            )
    except Exception as e:
        print(f"[thumbnail] failed to fetch {url}: {e}")

    abort(404)
