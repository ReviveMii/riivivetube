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
import time
import requests
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import datetime

from .client import _get_base_headers, _build_context
from .parsing import (
    escape_xml, _text_of, _collect_line_texts, _tile_to_fields, _prefetch_views, _parse_view_count,
)


def _tv_browse(browse_id, oauth_token=None, params=None, lang="en", gl="US"):
    headers = {
        "content-type": "application/json",
        "origin": "https://www.youtube.com",
        "referer": "https://www.youtube.com/tv",
        "x-youtube-client-name": "TVHTML5",
        "user-agent": "Mozilla/5.0 (SMART-TV; Linux; Tizen 6.5) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/5.0 Chrome/108.0.5359.1 TV Safari/537.36",
    }
    if oauth_token:
        headers["authorization"] = f"Bearer {oauth_token}"
    payload = {
        "context": {
            "client": {
                "hl": lang, "gl": gl, "clientName": "TVHTML5",
                "clientVersion": "7.20260715.15.00", "platform": "TV",
                "originalUrl": "https://www.youtube.com/tv",
            }
        },
        "browseId": browse_id,
    }
    if params:
        payload["params"] = params
    try:
        resp = requests.post("https://www.youtube.com/youtubei/v1/browse", json=payload, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None, resp.status_code
        return resp.json(), 200
    except Exception:
        return None, 500


def _iter_all_tiles(obj):
    if isinstance(obj, dict):
        t = obj.get("tileRenderer")
        if isinstance(t, dict):
            yield t
        for v in obj.values():
            yield from _iter_all_tiles(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _iter_all_tiles(v)


def _tile_kind(tile):
    ct = str(tile.get("contentType", "")).upper()
    if "CHANNEL" in ct:
        return "channel"
    if "PLAYLIST" in ct:
        return "playlist"
    if "VIDEO" in ct:
        return "video"
    return ""


def _tile_title(tile):
    meta = tile.get("metadata", {}).get("tileMetadataRenderer", {})
    return _text_of(meta.get("title", {}))


def _now_iso():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _feed_head(title, total):
    xml = '<?xml version="1.0" encoding="UTF-8"?>'
    xml += '<feed xmlns:openSearch="http://a9.com/-/spec/opensearch/1.1/" xmlns:media="http://search.yahoo.com/mrss/" xmlns:yt="http://www.youtube.com/xml/schemas/2015">'
    xml += f'<title type="text">{escape_xml(title)}</title>'
    xml += f'<openSearch:totalResults>{total}</openSearch:totalResults>'
    xml += '<openSearch:startIndex>1</openSearch:startIndex>'
    xml += f'<openSearch:itemsPerPage>{max(total, 20)}</openSearch:itemsPerPage>'
    return xml


def _video_feed_xml(title, tiles, base, exact_limit=None):
    _prefetch_views(tiles, exact_limit)
    entries = ""
    count = 0
    for tile in tiles:
        f = _tile_to_fields(tile)
        if not f["video_id"]:
            continue
        count += 1
        entries += '<entry>'
        entries += f'<id>{base}/api/videos/{f["video_id"]}</id>'
        entries += f'<published>{f["published"]}</published>'
        entries += f'<title type="text">{escape_xml(f["title"])}</title>'
        entries += f'<author><name>{escape_xml(f["author_name"])}</name><uri>https://www.youtube.com/channel/{f["author_id"]}</uri></author>'
        entries += '<media:group>'
        entries += f'<media:thumbnail yt:name="mqdefault" url="http://i.ytimg.com/vi/{f["video_id"]}/mqdefault.jpg" height="240" width="320" time="00:00:00"/>'
        entries += f'<media:description>{escape_xml(f["description"])}</media:description>'
        entries += f'<yt:duration seconds="{f["duration_seconds"]}"/>'
        entries += f'<yt:uploaded>{f["published"]}</yt:uploaded>'
        entries += f'<yt:uploaderId>{f["author_id"]}</yt:uploaderId>'
        entries += f'<yt:videoid>{f["video_id"]}</yt:videoid>'
        entries += f'<media:credit role="uploader" yt:display="{escape_xml(f["author_name"])}">{escape_xml(f["author_name"])}</media:credit>'
        entries += '</media:group>'
        entries += f'<yt:statistics favoriteCount="0" viewCount="{f["view_count"]}"/>'
        entries += '</entry>'
    return _feed_head(title, count) + entries + '</feed>'


def _extract_channels(data):
    channels = {}
    for tile in _iter_all_tiles(data):
        if _tile_kind(tile) == "channel":
            cid = tile.get("contentId", "")
            if cid and cid not in channels:
                channels[cid] = _tile_title(tile)
    if channels:
        return channels

    def walk(o):
        if isinstance(o, dict):
            be = None
            for k in ("endpoint", "navigationEndpoint", "onSelectCommand"):
                e = o.get(k)
                if isinstance(e, dict) and isinstance(e.get("browseEndpoint"), dict):
                    be = e["browseEndpoint"]
            if be and str(be.get("browseId", "")).startswith("UC") and o.get("title"):
                cid = be["browseId"]
                name = _text_of(o["title"])
                if cid not in channels:
                    channels[cid] = name
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(data)
    return channels


def build_subscriptions_xml(channels):
    xml = _feed_head("Subscriptions", len(channels))
    for cid, name in channels.items():
        xml += '<entry>'
        xml += f'<yt:username display="{escape_xml(name)}">{escape_xml(cid)}</yt:username>'
        xml += f'<yt:channelId>{escape_xml(cid)}</yt:channelId>'
        xml += '<yt:unreadCount>0</yt:unreadCount>'
        xml += '</entry>'
    xml += '</feed>'
    return xml


def _recent_upload_order(recent_data, channels):
    by_name = {name: cid for cid, name in channels.items() if name}
    order, seen = [], set()
    for tile in _iter_all_tiles(recent_data or {}):
        if _tile_kind(tile) not in ("video", ""):
            continue
        f = _tile_to_fields(tile)
        cid = f["author_id"] if f["author_id"] in channels else by_name.get(f["author_name"], "")
        if cid and cid not in seen:
            seen.add(cid)
            order.append(cid)
    return order


RECENT_WAIT = 4.0
_io_pool = ThreadPoolExecutor(max_workers=8)
_job_pool = ThreadPoolExecutor(max_workers=2)
_recent_cache = {}
_prefetched = {}


def _remember_recent(key, future, channels):
    try:
        data, _status = future.result()
        if data:
            _recent_cache[key] = (_recent_upload_order(data, channels), time.time())
    except Exception:
        pass


def _load_subscriptions(oauth_token):
    f_channels = _io_pool.submit(_tv_browse, "FEchannels", oauth_token)
    f_recent = _io_pool.submit(_tv_browse, "FEsubscriptions", oauth_token)
    channels_data, status = f_channels.result()

    channels = _extract_channels(channels_data) if channels_data else {}
    key = hash(tuple(sorted(channels)))

    recent_data, recent_status = None, 0
    try:
        recent_data, recent_status = f_recent.result(timeout=0.3 if key in _recent_cache else RECENT_WAIT)
    except FutureTimeout:
        f_recent.add_done_callback(lambda f: _remember_recent(key, f, channels))

    if channels_data is None and recent_data is None and status in (401, 403):
        return None, status
    if not channels and recent_data:
        channels = _extract_channels(recent_data)
    if not channels:
        return build_subscriptions_xml({}), 200

    if recent_data:
        recent = _recent_upload_order(recent_data, channels)
        _recent_cache[key] = (recent, time.time())
    else:
        recent = _recent_cache.get(key, ([], 0))[0]
    return build_subscriptions_xml(_order_subscriptions(channels, recent)), 200


def prefetch_subscriptions(oauth_token):
    if oauth_token in _prefetched:
        return
    if len(_prefetched) > 20:
        _prefetched.pop(next(iter(_prefetched)), None)
    _prefetched[oauth_token] = _job_pool.submit(_load_subscriptions, oauth_token)


def fetch_subscriptions(oauth_token, base="http://ytv2.nossl.revivemii.xyz"):
    future = _prefetched.pop(oauth_token, None)
    if future is not None:
        try:
            return future.result()
        except Exception:
            pass
    return _load_subscriptions(oauth_token)


def build_playlists_xml(tiles, base):
    entries = ""
    count = 0
    seen = set()
    for tile in tiles:
        pid = tile.get("contentId", "")
        if pid.startswith("VL"):
            pid = pid[2:]
        if not pid or pid in seen or pid in ("WL", "LL"):
            continue
        seen.add(pid)
        count += 1
        header = tile.get("header", {}).get("tileHeaderRenderer", {})
        thumbs = header.get("thumbnail", {}).get("thumbnails", [])
        thumb = thumbs[-1].get("url", "") if thumbs else ""
        if thumb.startswith("//"):
            thumb = "http:" + thumb
        elif thumb.startswith("https://"):
            thumb = "http://" + thumb[len("https://"):]
        count_hint = 0
        texts = []
        for overlay in header.get("thumbnailOverlays", []):
            for v in overlay.values():
                if isinstance(v, dict):
                    texts.append(_text_of(v.get("text", {})))
        texts += _collect_line_texts(tile.get("metadata", {}).get("tileMetadataRenderer", {}))
        for t in texts:
            m = re.search(r"(\d[\d,.]*)", t or "")
            if m and ("video" in t.lower() or t.strip().isdigit()):
                try:
                    count_hint = int(m.group(1).replace(",", "").replace(".", ""))
                except ValueError:
                    pass
                break
        entries += '<entry>'
        entries += f'<yt:playlistId>{escape_xml(pid)}</yt:playlistId>'
        entries += f'<title type="text">{escape_xml(_tile_title(tile))}</title>'
        entries += f'<link rel="http://gdata.youtube.com/schemas/2007#playlist" type="application/atom+xml" href="{base}/feeds/api/playlists/{escape_xml(pid)}?v=2"/>'
        entries += f'<updated>{_now_iso()}</updated>'
        entries += f'<yt:countHint>{count_hint}</yt:countHint>'
        entries += '<media:group>'
        entries += f'<media:thumbnail yt:name="mqdefault" url="{escape_xml(thumb)}" height="180" width="320"/>'
        entries += '</media:group>'
        entries += '</entry>'
    return _feed_head("Playlists", count) + entries + '</feed>'


def fetch_playlists(oauth_token, base="http://ytv2.nossl.revivemii.xyz"):
    for browse_id in ("FEplaylist_aggregation", "FElibrary", "FEmy_youtube"):
        data, status = _tv_browse(browse_id, oauth_token)
        if data is None:
            if status in (401, 403):
                return None, status
            continue
        tiles = [t for t in _iter_all_tiles(data) if _tile_kind(t) == "playlist"]
        if tiles:
            return build_playlists_xml(tiles, base), 200
    return build_playlists_xml([], base), 200


def fetch_playlist_videos(playlist_id, oauth_token, base="http://ytv2.nossl.revivemii.xyz"):
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "", playlist_id)
    data, status = _tv_browse("VL" + safe_id, oauth_token or None)
    if data is None:
        return None, status
    tiles = [t for t in _iter_all_tiles(data) if _tile_kind(t) in ("video", "")]
    return _video_feed_xml("Playlist", tiles, base), 200


def fetch_channel_uploads(channel_id, oauth_token, base="http://ytv2.nossl.revivemii.xyz"):
    if channel_id == "default":
        return fetch_own_uploads(oauth_token, base)
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "", channel_id)
    data, status = _tv_browse(safe_id, oauth_token or None)
    if data is None:
        return None, status
    tiles = [t for t in _iter_all_tiles(data) if _tile_kind(t) in ("video", "")]
    return _video_feed_xml("Uploads", tiles, base, 5), 200


def _get_account_item(oauth_token):
    try:
        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {oauth_token}",
            "origin": "https://www.youtube.com",
            "referer": "https://www.youtube.com/tv",
            "x-youtube-client-name": "TVHTML5",
            "user-agent": "Mozilla/5.0 (SMART-TV; Linux; Tizen 6.5) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/5.0 Chrome/108.0.5359.1 TV Safari/537.36",
        }
        payload = {
            "context": {"client": {"hl": "en", "gl": "US", "clientName": "TVHTML5",
                                   "clientVersion": "7.20260715.15.00", "platform": "TV",
                                   "originalUrl": "https://www.youtube.com/tv"}},
            "accountReadMask": {"returnOwner": True, "returnBrandAccounts": True,
                                "returnPersonaAccounts": True, "returnFamilyChildAccounts": True,
                                "returnFamilyMembersAccounts": False},
        }
        resp = requests.post("https://www.youtube.com/youtubei/v1/account/accounts_list",
                             json=payload, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None
        item = None
        for section in resp.json().get("contents", []):
            for sec in section.get("accountSectionListRenderer", {}).get("contents", []):
                for it in sec.get("accountItemSectionRenderer", {}).get("contents", []):
                    ai = it.get("accountItem")
                    if ai and (ai.get("isSelected") or item is None):
                        item = ai
        return item
    except Exception:
        return None


def _get_own_channel_id(oauth_token):
    item = _get_account_item(oauth_token)
    if not item:
        return None
    try:
        ids = re.findall(r'"(UC[\w-]{22})"', json.dumps(item))
        if ids:
            return ids[0]
        handle = ""
        for cand in (item.get("channelHandle"), item.get("accountByline")):
            t = _text_of(cand).strip() if cand else ""
            if t.startswith("@"):
                handle = t
                break
        if not handle:
            return None
        r = requests.post("https://www.youtube.com/youtubei/v1/navigation/resolve_url",
                          json={"context": _build_context(), "url": f"https://www.youtube.com/{handle}"},
                          headers=_get_base_headers(), timeout=15)
        r.raise_for_status()
        return r.json().get("endpoint", {}).get("browseEndpoint", {}).get("browseId", "") or None
    except Exception:
        return None


def fetch_own_uploads(oauth_token, base="http://ytv2.nossl.revivemii.xyz"):
    if not oauth_token:
        return _feed_head("Uploads", 0) + '</feed>', 200

    attempts = ["FEmy_videos"]
    cid = _get_own_channel_id(oauth_token)
    if cid:
        attempts.append(cid)

    for browse_id in attempts:
        data, status = _tv_browse(browse_id, oauth_token)
        if data is None:
            if status in (401, 403):
                return None, status
            continue
        tiles = [t for t in _iter_all_tiles(data) if _tile_kind(t) in ("video", "")]
        if tiles:
            return _video_feed_xml("Uploads", tiles, base), 200
    return _feed_head("Uploads", 0) + '</feed>', 200


SUBSCRIPTION_LIMIT = 50


def _order_subscriptions(channels, recent_ids):
    ordered = []
    used = set()
    for cid in list(recent_ids) + list(channels):
        if cid in channels and cid not in used:
            used.add(cid)
            ordered.append(cid)
    return {cid: channels[cid] for cid in ordered[:SUBSCRIPTION_LIMIT]}


def empty_feed_xml(title):
    return _feed_head(title, 0) + '</feed>'
