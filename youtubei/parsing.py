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
import xml.sax.saxutils as saxutils
from datetime import datetime, timedelta
import time
import requests
from concurrent.futures import ThreadPoolExecutor
from .client import _get_base_headers, _build_context

def escape_xml(text):
    return saxutils.escape(text or "")


def _iter_grid_tiles(json_data):
    try:
        items = (json_data["contents"]["tvBrowseRenderer"]["content"]
                 ["tvSurfaceContentRenderer"]["content"]
                 ["gridRenderer"]["items"])
    except (KeyError, TypeError):
        return

    for item in items:
        tile = item.get("tileRenderer")
        if tile:
            yield tile


def _iter_tiles(json_data):
    try:
        contents = (json_data["contents"]["tvBrowseRenderer"]["content"]
                    ["tvSurfaceContentRenderer"]["content"]
                    ["sectionListRenderer"]["contents"])
    except (KeyError, TypeError):
        return

    for section in contents:
        shelf = section.get("shelfRenderer")
        if not shelf:
            continue
        items = (shelf.get("content", {})
                      .get("horizontalListRenderer", {})
                      .get("items", []))
        for item in items:
            tile = item.get("tileRenderer")
            if tile:
                yield tile


def _duration_to_seconds(text):
    if not text:
        return 0
    parts = text.strip().split(":")
    try:
        parts = [int(p) for p in parts]
    except ValueError:
        return 0
    seconds = 0
    for p in parts:
        seconds = seconds * 60 + p
    return seconds


def _parse_view_count(text):
    if not text:
        return 0
    t = text.strip()

    m = re.match(r"^([\d.]+)\s*(views|view)", t)
    if m:
        num = m.group(1).replace(".", "")
        try:
            return int(num)
        except ValueError:
            return 0

    m = re.match(r"^([\d,\.]+)\s*Mio\.?\s*views", t)
    if m:
        num = m.group(1).replace(".", "").replace(",", ".")
        try:
            return int(float(num) * 1_000_000)
        except ValueError:
            return 0

    m = re.match(r"^([\d,\.]+)\s*([KMB]?)\s*views?", t, re.IGNORECASE)
    if m:
        num_str = m.group(1).replace(",", "")
        suffix = m.group(2).upper()
        try:
            num = float(num_str)
        except ValueError:
            return 0
        multiplier = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}.get(suffix, 1)
        return int(num * multiplier)

    digits = re.sub(r"[^\d]", "", t)
    return int(digits) if digits else 0


def _tile_to_fields(tile):
    header = tile.get("header", {}).get("tileHeaderRenderer", {})
    meta = tile.get("metadata", {}).get("tileMetadataRenderer", {})

    video_id = tile.get("contentId", "")

    length_text = ""
    for overlay in header.get("thumbnailOverlays", []):
        ts = overlay.get("thumbnailOverlayTimeStatusRenderer")
        if ts:
            length_text = ts.get("text", {}).get("simpleText", "")
            break

    title = meta.get("title", {}).get("simpleText", "")

    author_name = ""
    view_count_text = ""
    published_text = ""
    lines = meta.get("lines", [])
    if lines:
        first_line_items = lines[0].get("lineRenderer", {}).get("items", [])
        if first_line_items:
            runs = first_line_items[0].get("lineItemRenderer", {}).get("text", {}).get("runs", [])
            if runs:
                author_name = runs[0].get("text", "")

    if len(lines) > 1:
        for li in lines[1].get("lineRenderer", {}).get("items", []):
            item = li.get("lineItemRenderer", {})
            txt = item.get("text", {})
            simple = txt.get("simpleText", "")
            if "Aufruf" in simple or "views" in simple.lower() or "Mio." in simple:
                view_count_text = simple
            elif simple.startswith("vor "):
                published_text = simple

    if not view_count_text:
        for simple in _collect_line_texts(meta):
            low = simple.lower()
            if simple != author_name and re.search(r"\d", simple) and (re.search(r"\bviews?\b", low) or "aufruf" in low):
                view_count_text = simple
                break
        else:
            if video_id in _view_cache:
                view_count_text = f"{_view_cache[video_id][0]} views"

    if view_count_text and _is_abbreviated_views(view_count_text) and video_id in _view_cache:
        view_count_text = f"{_view_cache[video_id][0]} views"

    author_id = ""
    try:
        menu_items = (tile["onLongPressCommand"]["showMenuCommand"]["menu"]
                      ["menuRenderer"]["items"])
        for mi in menu_items:
            nav = mi.get("menuNavigationItemRenderer", {}).get("navigationEndpoint", {})
            if "browseEndpoint" in nav:
                author_id = nav["browseEndpoint"].get("browseId", "")
                break
    except (KeyError, TypeError):
        pass

    return {
        "video_id": video_id,
        "duration_seconds": _duration_to_seconds(length_text),
        "author_name": author_name,
        "author_id": author_id,
        "title": title,
        "view_count": _parse_view_count(view_count_text),
        "published": (lambda t: (
            (lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"))(
                datetime.utcnow() - {
                    "seconds": timedelta(seconds=int(m.group(1))),
                    "minutes": timedelta(minutes=int(m.group(1))),
                    "hours": timedelta(hours=int(m.group(1))),
                    "days": timedelta(days=int(m.group(1))),
                    "weeks": timedelta(weeks=int(m.group(1))),
                    "months": timedelta(days=int(m.group(1)) * 30),
                    "years": timedelta(days=int(m.group(1)) * 365),
                }.get(m.group(2), timedelta(0))
            ) if (m := re.search(r"vor\s+(\d+)\s+(seconds|minutes|hours|days|weeks|months|years)", t)) else datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
        ))(published_text),
        "description": title,
    }


def _extract_length_text_and_seconds(vd):
    length_obj = vd.get("lengthText", {})
    simple_text = length_obj.get("simpleText")
    accessible_label = (
        length_obj.get("accessibility", {})
        .get("accessibilityData", {})
        .get("label")
    )

    result = None
    seconds = 0

    if simple_text:
        result = {
            "accessibility": {
                "accessibilityData": {
                    "label": accessible_label or ""
                }
            },
            "simpleText": simple_text
        }

        try:
            parts = list(map(int, simple_text.split(":")))
            if len(parts) == 3:
                seconds = parts[0] * 3600 + parts[1] * 60 + parts[2]
            elif len(parts) == 2:
                seconds = parts[0] * 60 + parts[1]
            elif len(parts) == 1:
                seconds = parts[0]
        except:
            seconds = 0

    return result, seconds


def _extract_videos_from_items(items):
    videos = []
    for item in items:
        if "videoRenderer" in item:
            videos.append(item["videoRenderer"])
        elif "carouselShelfRenderer" in item or "richShelfRenderer" in item:
            contents = item.get("carouselShelfRenderer", {}).get("contents", []) \
                or item.get("richShelfRenderer", {}).get("contents", [])
            videos.extend(_extract_videos_from_items(contents))
        elif "shelfRenderer" in item:
            contents = item.get("shelfRenderer", {}).get("content", {}).get("expandedShelfContentsRenderer", {}).get("items", [])
            videos.extend(_extract_videos_from_items(contents))
    return videos


_view_cache = {}


_VIEW_CACHE_TTL = 6 * 3600
EXACT_VIEWS_LIMIT = 20
_view_pool = ThreadPoolExecutor(max_workers=8)


def _text_of(txt):
    if isinstance(txt, str):
        return txt
    if not isinstance(txt, dict):
        return ""
    if txt.get("simpleText"):
        return txt["simpleText"]
    return "".join(r.get("text", "") for r in txt.get("runs", []) if isinstance(r, dict))


def _collect_line_texts(meta):
    out = []
    for line in meta.get("lines", []):
        for li in line.get("lineRenderer", {}).get("items", []):
            t = _text_of(li.get("lineItemRenderer", {}).get("text", {})).strip()
            if t:
                out.append(t)
    return out


def _is_abbreviated_views(text):
    return bool(re.search(r"\d\s*(?:[KMB]|Mio\.?|Mrd\.?|Tsd\.?)(?![A-Za-z])", text or ""))


def _tile_view_text(tile):
    meta = tile.get("metadata", {}).get("tileMetadataRenderer", {})
    for t in _collect_line_texts(meta):
        low = t.lower()
        if re.search(r"\bviews?\b", low) or "aufruf" in low:
            return t
    return ""


def _fetch_view_count(video_id):
    try:
        resp = requests.post(
            "https://www.youtube.com/youtubei/v1/next",
            json={"context": _build_context(video_id=video_id), "videoId": video_id},
            headers=_get_base_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        results = (data.get("contents", {}).get("twoColumnWatchNextResults", {})
                   .get("results", {}).get("results", {}).get("contents", []))
        for c in results:
            pi = c.get("videoPrimaryInfoRenderer")
            if pi:
                vc = pi.get("viewCount", {}).get("videoViewCountRenderer", {})
                text = _text_of(vc.get("viewCount", {})) or _text_of(vc.get("shortViewCount", {}))
                return _parse_view_count(text)
    except Exception:
        pass
    return None


def _prefetch_views(tiles, limit=None):
    limit = EXACT_VIEWS_LIMIT if limit is None else limit
    now = time.time()
    ids = []
    for tile in list(tiles)[:limit]:
        vid = tile.get("contentId", "")
        if not vid or len(vid) != 11:
            continue
        text = _tile_view_text(tile)
        if text and not _is_abbreviated_views(text):
            continue
        cached = _view_cache.get(vid)
        if cached and now - cached[1] < _VIEW_CACHE_TTL:
            continue
        ids.append(vid)
    ids = list(dict.fromkeys(ids))
    if not ids:
        return
    for vid, count in zip(ids, _view_pool.map(_fetch_view_count, ids)):
        if count is not None:
            _view_cache[vid] = (count, now)
