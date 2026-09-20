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
