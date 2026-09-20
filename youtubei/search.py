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
from .parsing import _parse_view_count, _extract_length_text_and_seconds, _extract_videos_from_items

def innertube_search(query, region="US", max_results=50):
    url = "https://www.youtube.com/youtubei/v1/search"
    headers = _get_base_headers()
    payload = {
        "context": _build_context(),
        "query": query,
        "params": ""
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()

        videos = []
        sections = (
            data.get("contents", {})
                .get("twoColumnSearchResultsRenderer", {})
                .get("primaryContents", {})
                .get("sectionListRenderer", {})
                .get("contents", [])
        )

        for section in sections:
            items = section.get("itemSectionRenderer", {}).get("contents", [])
            for item in items:
                vd = item.get("videoRenderer")
                if not vd:
                    continue

                title = vd["title"]["runs"][0]["text"]
                vid = vd.get("videoId", "")
                owner_runs = vd.get("ownerText", {}).get("runs", [{}])
                author = owner_runs[0].get("text", "")
                nav = owner_runs[0].get("navigationEndpoint", {}).get("browseEndpoint", {})
                authorId = nav.get("browseId", "")
                authorUrl = nav.get("canonicalBaseUrl", "")

                authorVerified = any(
                    b.get("metadataBadgeRenderer", {}).get("style") == "BADGE_STYLE_TYPE_VERIFIED"
                    for b in vd.get("ownerBadges", [])
                )

                authorThumbnails = (
                    vd.get("channelThumbnailSupportedRenderers", {})
                      .get("channelThumbnailWithLinkRenderer", {})
                      .get("thumbnail", {}).get("thumbnails", [])
                )

                videoThumbnails = vd.get("thumbnail", {}).get("thumbnails", [])
                desc_runs = vd.get("descriptionSnippet", {}).get("runs", [{}])
                desc = desc_runs[0].get("text", "") if desc_runs else ""
                viewCountText = vd.get("viewCountText", {}).get("simpleText", "")
                viewCount = _parse_view_count(viewCountText)
                publishedText = vd.get("publishedTimeText", {}).get("simpleText", "")
                liveNow = any(
                    "LIVE" in b.get("metadataBadgeRenderer", {}).get("label", "").upper()
                    for b in vd.get("badges", [])
                )
                lengthText, lengthSeconds = _extract_length_text_and_seconds(vd)

                videos.append({
                    "type": "video",
                    "title": title,
                    "videoId": vid,
                    "author": author,
                    "authorId": authorId,
                    "authorUrl": authorUrl,
                    "authorVerified": authorVerified,
                    "authorThumbnails": authorThumbnails,
                    "videoThumbnails": videoThumbnails,
                    "description": desc,
                    "viewCount": viewCount,
                    "viewCountText": viewCountText,
                    "publishedText": publishedText,
                    "lengthSeconds": lengthSeconds,
                    "lengthText": lengthText,
                    "liveNow": liveNow
                })

                if len(videos) >= max_results:
                    break
            if len(videos) >= max_results:
                break

        return videos

    except Exception as e:
        print(f"[youtubei] Error searching: {e}")
        return []


def innertube_trending(trending_type=None, region="US", max_results=50):
    TRENDING_PARAMS = {
        "music": "4gINGgt5dG1hX2NoYXJ0cw%3D%3D",
        "gaming": "4gIcGhpnYW1pbmdfY29ycHVzX21vc3RfcG9wdWxhcg%3D%3D",
        "movies": "4gIKGgh0cmFpbGVycw%3D%3D"
    }

    url = "https://www.youtube.com/youtubei/v1/browse"
    headers = _get_base_headers()

    trending_type_key = trending_type.lower() if trending_type else ""
    params = TRENDING_PARAMS.get(trending_type_key, "")

    payload = {
        "context": _build_context(),
        "browseId": "FEtrending",
    }

    if params:
        payload["params"] = params

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        section_list = data.get("contents", {}) \
            .get("twoColumnBrowseResultsRenderer", {}) \
            .get("tabs", [])[0] \
            .get("tabRenderer", {}) \
            .get("content", {}) \
            .get("sectionListRenderer", {}) \
            .get("contents", [])

        all_items = []
        for section in section_list:
            items = section.get("itemSectionRenderer", {}).get("contents", [])
            all_items.extend(items)

        videos = _extract_videos_from_items(all_items)
        seen = set()
        unique = []
        for v in videos:
            vid = v.get("videoId")
            if vid and vid not in seen:
                seen.add(vid)
                unique.append(v)
        videos = unique
        videos = videos[:max_results]

        def parse_video(vd):
            title = vd.get("title", {}).get("runs", [{}])[0].get("text", "")
            vid = vd.get("videoId", "")
            author = vd.get("ownerText", {}).get("runs", [{}])[0].get("text", "")
            thumbnails = vd.get("thumbnail", {}).get("thumbnails", [])
            view_count_text = vd.get("viewCountText", {}).get("simpleText", "")
            view_count = _parse_view_count(view_count_text)
            published_text = vd.get("publishedTimeText", {}).get("simpleText", "")
            length_text_obj, length_seconds = _extract_length_text_and_seconds(vd)
            return {
                "title": title,
                "videoId": vid,
                "author": author,
                "videoThumbnails": thumbnails,
                "viewCount": view_count,
                "publishedText": published_text,
                "lengthText": length_text_obj,
                "lengthSeconds": length_seconds
            }

        return [parse_video(v) for v in videos]

    except Exception as e:
        print(f"[youtubei] Error fetching trending: {e}")
        return []
