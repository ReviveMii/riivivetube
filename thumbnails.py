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


import requests
import xml.etree.ElementTree as ET
import time
import threading
import queue

from config import CATEGORIES, CATEGORY_MAP, thumbnail_url_cache

def get_first_video_id_from_route(category):
    try:
        url = f"http://127.0.0.1:5005/{category}"
        response = requests.get(url)
        if response.status_code != 200:
            print(f"[{category}] Error fetching: HTTP {response.status_code}")
            return None
        ns = {
            'yt': 'http://www.youtube.com/xml/schemas/2015'
        }

        root = ET.fromstring(response.content)
        entry = root.find('entry')
        if entry is None:
            print(f"[{category}] <entry> not found")
            return None
        videoid_el = entry.find('.//yt:videoid', ns)
        if videoid_el is None:
            print(f"[{category}] <yt:videoid> not found")
            return None
        return videoid_el.text.strip()
    except Exception as e:
        print(f"[{category}] XML parsing error: {e}")
        return None


def cache_thumbnail_url(video_id, category_name):
    url = f"http://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    thumbnail_url_cache[category_name] = url
    print(f"[{category_name}] Cached thumbnail URL: {url}")


def thumbnail_scheduler():
    time.sleep(5)
    while True:
        for category in CATEGORIES:
            video_id = get_first_video_id_from_route(category)
            if video_id:
                name = CATEGORY_MAP.get(category, category)
                cache_thumbnail_url(video_id, name)
            else:
                print(f"[{category}] video id missing")
        time.sleep(60)


THUMB_ORDER = ["music", "sports", "gaming", "trending", "film_animation", "entertainment", "comedy",
               "news_politics", "people_blogs", "science_technology", "howto_style", "education", "pets_animals"]
THUMB_TTL = 30 * 60
THUMB_STANDBY_DELAY = 1.0       # just to make it easy on the server.. make it 0 if theres no need
THUMB_WARM_COUNT = 5

_url_time = {}
_standby_queue = queue.Queue()
_standby_pending = set()
_standby_guard = threading.Lock()
_NAME_TO_ROUTE = {name: route for route, name in CATEGORY_MAP.items()}


def _expire_old(name):
    if name in thumbnail_url_cache:
        first_seen = _url_time.setdefault(name, time.time())
        if time.time() - first_seen > THUMB_TTL:
            thumbnail_url_cache.pop(name, None)
            _url_time.pop(name, None)
    else:
        _url_time.pop(name, None)


def queue_standby(name):
    _expire_old(name)
    if name not in THUMB_ORDER:
        return
    idx = THUMB_ORDER.index(name)
    if idx + 1 >= len(THUMB_ORDER):
        return
    nxt = THUMB_ORDER[idx + 1]
    _expire_old(nxt)
    if nxt in thumbnail_url_cache:
        return
    with _standby_guard:
        if nxt in _standby_pending:
            return
        _standby_pending.add(nxt)
    _standby_queue.put(nxt)


def _resolve_thumbnail(name):
    video_id = get_first_video_id_from_route(_NAME_TO_ROUTE[name])
    if video_id and name not in thumbnail_url_cache:
        cache_thumbnail_url(video_id, name)
        _url_time[name] = time.time()


def standby_worker():
    time.sleep(5)
    for name in THUMB_ORDER[:THUMB_WARM_COUNT]:
        if name not in thumbnail_url_cache:
            _resolve_thumbnail(name)
    while True:
        name = _standby_queue.get()
        try:
            _resolve_thumbnail(name)
        finally:
            with _standby_guard:
                _standby_pending.discard(name)
        time.sleep(THUMB_STANDBY_DELAY)
