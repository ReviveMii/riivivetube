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


from .video import get_video_info
from .search import innertube_search, innertube_trending
from .tv import (
    fetch_river_tv,
    fetch_user_info,
    fetch_watch_history,
    fetch_watch_later,
    fetch_favorites,
)
from .parsing import escape_xml
from .library import (
    fetch_subscriptions,
    fetch_playlists,
    fetch_playlist_videos,
    fetch_channel_uploads,
    empty_feed_xml,
)
from .library import prefetch_subscriptions
import threading as _threading
import time as _time

SEARCH_CACHE_TTL = 5 * 60
_search_cache = {}
_search_lock = _threading.Lock()
_innertube_search_uncached = innertube_search


def innertube_search(query, region="US", max_results=50):
    key = (query, region, max_results)
    now = _time.time()
    with _search_lock:
        hit = _search_cache.get(key)
    if hit and now - hit[0] < SEARCH_CACHE_TTL:
        return hit[1]
    results = _innertube_search_uncached(query, region, max_results)
    if results:
        with _search_lock:
            if len(_search_cache) > 200:
                _search_cache.clear()
            _search_cache[key] = (now, results)
    return results
