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

from .client import _get_base_headers, _build_context
from .parsing import _parse_view_count
from .search import innertube_search

def get_video_info(video_id):
    url = "https://www.youtube.com/youtubei/v1/next" # lower risk of being blocked because the next entpoint has a lower ratelimit than the player endpoint. player endpoint ratelimits: ~1000 (player) requests per hour for logged-out sessions, ~4000 (player) requests per hour for logged-in accounts (cookies) (https://github.com/yt-dlp/yt-dlp/wiki/Extractors#common-youtube-errors)
    headers = _get_base_headers()
    payload = {
        "context": _build_context(video_id=video_id),
        "videoId": video_id
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()

        contents = data.get('contents', {})
        two_col = contents.get('twoColumnWatchNextResults', {})
        results_wrapper = two_col.get('results', {})
        results = results_wrapper.get('results', {}).get('contents', [])

        primary_info = None
        secondary_info = None
        for c in results:
            if 'videoPrimaryInfoRenderer' in c:
                primary_info = c['videoPrimaryInfoRenderer']
            if 'videoSecondaryInfoRenderer' in c:
                secondary_info = c['videoSecondaryInfoRenderer']

        title = ""
        if primary_info:
            title_runs = primary_info.get('title', {}).get('runs', [])
            if title_runs:
                title = title_runs[0].get('text', '')
            else:
                title = primary_info.get('title', {}).get('simpleText', '')

        author = ""
        author_id = ""
        if secondary_info:
            owner = secondary_info.get('owner', {}).get('videoOwnerRenderer', {})
            owner_title = owner.get('title', {})
            owner_runs = owner_title.get('runs', [])
            if owner_runs:
                author = owner_runs[0].get('text', '')
                author_id = owner_runs[0].get('navigationEndpoint', {}).get('browseEndpoint', {}).get('browseId', '')
            else:
                author = owner_title.get('simpleText', '')

        length_seconds = 0
        if title and author:
            try:
                search_results = innertube_search(f"{title} {author}", region="US", max_results=50)
                for result in search_results:
                    if result.get("videoId") == video_id:
                        length_seconds = result.get("lengthSeconds", 0)
                        break
            except Exception as e:
                print(f"[youtubei] Error searching for video length: {e}")
                length_seconds = 0

        view_count = 0
        if primary_info:
            try:
                vc_renderer = primary_info.get('viewCount', {}).get('videoViewCountRenderer', {})
                vc_text = vc_renderer.get('shortViewCount', {}).get('simpleText', '')
                if not vc_text:
                    vc_text = vc_renderer.get('viewCount', {}).get('simpleText', '')
                view_count = _parse_view_count(vc_text)
            except Exception:
                pass

        published_text = ""
        if primary_info:
            try:
                published_text = primary_info.get('dateText', {}).get('simpleText', '')
            except Exception:
                pass

        return {
            'videoId': video_id,
            'title': title,
            'author': author,
            'authorId': author_id,
            'lengthSeconds': length_seconds,
            'viewCount': view_count,
            'publishedText': published_text,
            'likeCount': 0,
            'dislikeCount': 0,
            'averageRating': 0,
            'description': '',
            'keywords': [],
            'isLive': False,
            'thumbnail': {
                'thumbnails': [{'url': f'http://i.ytimg.com/vi/{video_id}/mqdefault.jpg', 'width': 320, 'height': 180}]
            }
        }

    except Exception as e:
        print(f"[youtubei] Error fetching video info: {e}")
        return None
