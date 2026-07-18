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
import re
import json
import time
import threading
import xml.sax.saxutils as saxutils
from datetime import datetime, timedelta
import base64

_client_version = None
_client_version_lock = threading.Lock()
_client_version_last_fetch = 0
_CLIENT_VERSION_TTL = 3600

def _fetch_client_version():
    global _client_version, _client_version_last_fetch
    with _client_version_lock:
        now = time.time()
        if _client_version and (now - _client_version_last_fetch) < _CLIENT_VERSION_TTL:
            return _client_version

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "de-DE,de;q=0.5",
            }
            resp = requests.get("https://www.youtube.com", headers=headers, timeout=10)
            resp.raise_for_status()

            match = re.search(r'"INNERTUBE_CLIENT_VERSION":"([^"]+)"', resp.text)
            if match:
                _client_version = match.group(1)
                _client_version_last_fetch = now
                return _client_version
        except Exception as e:
            print(f"[youtubei] Error fetching client version: {e}")
        _client_version = "2.20260714.05.00"
        _client_version_last_fetch = now
        return _client_version

# ported from https://github.com/erievs/FourthTube/blob/9f871f95f9fce14f3c109f0a403bb8b5224bc6c7/source/youtube_parser/video.cpp#L486-L517
def _fetch_visitor_data():
    try:
        headers = {
            "Origin": "https://www.youtube.com",
            "Referer": "https://www.youtube.com/",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
        }
        resp = requests.get("https://www.youtube.com/sw.js_data", headers=headers, timeout=10)
        resp.raise_for_status()

        text = resp.text
        prefix = ")]}'\n"
        if text.startswith(prefix):
            text = text[len(prefix):]

        data = json.loads(text)
        visitor_data = data[0][2][0][0][13]
        return visitor_data
    except Exception as e:
        print(f"[youtubei] Error fetching visitor data: {e}")
        return "0"

def _get_base_headers():
    client_version = _fetch_client_version()
    visitor_data = _fetch_visitor_data()

    return {
        "Host": "www.youtube.com",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.5",
        "Content-Type": "application/json",
        "Origin": "https://www.youtube.com",
        "Priority": "u=1, i",
        "Referer": "https://www.youtube.com/",
        "Sec-Ch-Ua": '"Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
        "Sec-Ch-Ua-Arch": '"x86"',
        "Sec-Ch-Ua-Bitness": '"64"',
        "Sec-Ch-Ua-Full-Version-List": '"Not;A=Brand";v="8.0.0.0", "Chromium";v="150.0.0.0", "Google Chrome";v="150.0.0.0"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Model": '""',
        "Sec-Ch-Ua-Platform": '"Linux"',
        "Sec-Ch-Ua-Platform-Version": '""',
        "Sec-Ch-Ua-Wow64": "?0",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "same-origin",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Gpc": "1",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
        "X-Goog-Authuser": "1",
        "X-Goog-Visitor-Id": visitor_data,
        "X-Origin": "https://www.youtube.com",
        "X-Youtube-Bootstrap-Logged-In": "true",
        "X-Youtube-Client-Name": "1",
        "X-Youtube-Client-Version": client_version,
    }

def _build_context(video_id=None, graft_url=None):
    client_version = _fetch_client_version()
    visitor_data = _fetch_visitor_data()

    original_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else "https://www.youtube.com/"
    _graft_url = graft_url if graft_url else (f"/watch?v={video_id}" if video_id else "/")

    return {
        "client": {
            "acceptHeader": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "browserName": "Chrome",
            "browserVersion": "150.0.0.0",
            "clientFormFactor": "UNKNOWN_FORM_FACTOR",
            "clientName": "WEB",
            "clientVersion": client_version,
            "configInfo": {
                "appInstallData": ""
            },
            "deviceMake": "",
            "deviceModel": "",
            "gl": "US",
            "hl": "en",
            "mainAppWebInfo": {
                "graftUrl": _graft_url,
                "isWebNativeShareAvailable": True,
                "pwaInstallabilityStatus": "PWA_INSTALLABILITY_STATUS_CAN_BE_INSTALLED",
                "webDisplayMode": "WEB_DISPLAY_MODE_BROWSER"
            },
            "memoryTotalKbytes": "8000000",
            "originalUrl": original_url,
            "osName": "X11",
            "osVersion": "",
            "platform": "DESKTOP",
            "remoteHost": "2003:d2:cf2b:a85e:517a:451f:a30d:fbf5",
            "screenDensityFloat": 1,
            "screenHeightPoints": 953,
            "screenPixelDensity": 1,
            "screenWidthPoints": 974,
            "timeZone": "Europe/Berlin",
            "userAgent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36,gzip(gfe)",
            "userInterfaceTheme": "USER_INTERFACE_THEME_DARK",
            "utcOffsetMinutes": 120,
            "visitorData": visitor_data
        },
        "request": {
            "internalExperimentFlags": [],
            "useSsl": True
        },
        "user": {
            "enableSafetyMode": False,
            "lockedSafetyMode": False
        }
    }

def get_video_info(video_id):
    url = "https://www.youtube.com/youtubei/v1/next" # lower risk of being blocked because the next entpoint has a lower ratelimit than the player endpoint
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


def build_river_xml_tv(json_data):
    xml_string = '<?xml version="1.0" encoding="UTF-8"?>'
    xml_string += '<feed xmlns:openSearch="http://a9.com/-/spec/opensearch/1.1/" xmlns:media="http://search.yahoo.com/mrss/" xmlns:yt="http://www.youtube.com/xml/schemas/2015">'
    xml_string += '<title type="text">What to Watch</title>'
    xml_string += '<openSearch:totalResults>0</openSearch:totalResults>'
    xml_string += '<openSearch:startIndex>1</openSearch:startIndex>'
    xml_string += '<openSearch:itemsPerPage>20</openSearch:itemsPerPage>'

    for tile in _iter_tiles(json_data):
        f = _tile_to_fields(tile)
        if not f["video_id"]:
            continue
        inner = '<entry>'
        inner += f'<id>http://ytv2.nossl.revivemii.xyz/api/videos/{f["video_id"]}</id>'
        inner += f'<published>{f["published"]}</published>'
        inner += f'<updated>{f["published"]}</updated>'
        inner += f'<title type="text">{escape_xml(f["title"])}</title>'
        inner += f'<author><name>{escape_xml(f["author_name"])}</name><uri>https://www.youtube.com/channel/{f["author_id"]}</uri></author>'
        inner += '<media:group>'
        inner += f'<media:thumbnail yt:name="mqdefault" url="http://i.ytimg.com/vi/{f["video_id"]}/mqdefault.jpg" height="240" width="320" time="00:00:00"/>'
        inner += f'<media:description>{escape_xml(f["description"])}</media:description>'
        inner += f'<yt:duration seconds="{f["duration_seconds"]}"/>'
        inner += f'<yt:uploaderId>{f["author_id"]}</yt:uploaderId>'
        inner += f'<yt:videoid>{f["video_id"]}</yt:videoid>'
        inner += f'<media:credit role="uploader" yt:display="{escape_xml(f["author_name"])}">{escape_xml(f["author_name"])}</media:credit>'
        inner += '</media:group>'
        inner += f'<yt:statistics favoriteCount="0" viewCount="{f["view_count"]}"/>'
        inner += '</entry>'
        xml_string += '<entry>'
        xml_string += f'<id>http://ytv2.nossl.revivemii.xyz/api/videos/{f["video_id"]}</id>'
        xml_string += f'<published>{f["published"]}</published>'
        xml_string += f'<title type="text">{escape_xml(f["title"])}</title>'
        xml_string += '<link>'
        xml_string += inner
        xml_string += '</link>'
        xml_string += '</entry>'

    xml_string += '</feed>'
    return xml_string


def fetch_river_tv(oauth_token, lang="en", gl="US"):
    url = "https://www.youtube.com/youtubei/v1/browse"
    headers = {
        "content-type": "application/json",
        "authorization": f"Bearer {oauth_token}",
        "origin": "https://www.youtube.com",
        "referer": "https://www.youtube.com/tv",
        "x-youtube-client-name": "TVHTML5",
        "user-agent": "Mozilla/5.0 (SMART-TV; Linux; Tizen 6.5) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/5.0 Chrome/108.0.5359.1 TV Safari/537.36",
    }
    payload = {
        "context": {
            "client": {
                "hl": lang,
                "gl": gl,
                "clientName": "TVHTML5",
                "clientVersion": "7.20260715.15.00",
                "platform": "TV",
                "originalUrl": "https://www.youtube.com/tv",
            }
        },
        "browseId": "default",
    }

    response = requests.post(url, json=payload, headers=headers)
    if response.status_code != 200:
        return None, response.status_code

    data = response.json()
    return build_river_xml_tv(data), 200


def build_user_info_xml(account_item):
    account_name = account_item.get("accountName", {}).get("simpleText", "")
    account_byline = account_item.get("accountByline", {}).get("simpleText", "")

    thumbnails = account_item.get("accountPhoto", {}).get("thumbnails", [])
    old_avatar_url = thumbnails[-1].get("url", "") if thumbnails else ""
    avatar_url = "http://ytv2.nossl.revivemii.xyz//pfpproxy/" + old_avatar_url
    user_id = ""
    try:
        tokens = account_item["serviceEndpoint"]["selectActiveIdentityEndpoint"]["supportedTokens"]
        for tok in tokens:
            state_token = tok.get("accountStateToken")
            if state_token and state_token.get("obfuscatedGaiaId"):
                user_id = state_token["obfuscatedGaiaId"]
                break
    except (KeyError, TypeError):
        pass
    username = escape_xml(account_byline or account_name)
    display_username = escape_xml(account_name)

    xml_string = '<?xml version="1.0" encoding="UTF-8"?>'
    xml_string += '<entry xmlns:media="http://search.yahoo.com/mrss/" xmlns:yt="http://www.youtube.com/xml/schemas/2015">'
    xml_string += f'<yt:username display="{display_username}">{username}</yt:username>'
    xml_string += f'<yt:userId>{escape_xml(user_id)}</yt:userId>'
    xml_string += f'<media:thumbnail url="{escape_xml(avatar_url)}"/>'
    xml_string += f'<author><name>{display_username}</name></author>'
    xml_string += '</entry>'
    return xml_string


def fetch_user_info(oauth_token, lang="en", gl="US"):
    url = "https://www.youtube.com/youtubei/v1/account/accounts_list"
    headers = {
        "content-type": "application/json",
        "authorization": f"Bearer {oauth_token}",
        "origin": "https://www.youtube.com",
        "referer": "https://www.youtube.com/tv",
        "x-youtube-client-name": "TVHTML5",
        "user-agent": "Mozilla/5.0 (SMART-TV; Linux; Tizen 6.5) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/5.0 Chrome/108.0.5359.1 TV Safari/537.36",
    }
    payload = {
        "context": {
            "client": {
                "hl": lang,
                "gl": gl,
                "clientName": "TVHTML5",
                "clientVersion": "7.20260715.15.00",
                "platform": "TV",
                "originalUrl": "https://www.youtube.com/tv",
            }
        },
        "accountReadMask": {
            "returnOwner": True,
            "returnBrandAccounts": True,
            "returnPersonaAccounts": True,
            "returnFamilyChildAccounts": True,
            "returnFamilyMembersAccounts": False,
        },
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        if response.status_code != 200:
            return None, response.status_code

        data = response.json()

        account_item = None
        for section in data.get("contents", []):
            for item_section in section.get("accountSectionListRenderer", {}).get("contents", []):
                for item in item_section.get("accountItemSectionRenderer", {}).get("contents", []):
                    ai = item.get("accountItem")
                    if not ai:
                        continue
                    if ai.get("isSelected") or account_item is None:
                        account_item = ai
                    if ai.get("isSelected"):
                        break

        if account_item is None:
            return None, 404

        return build_user_info_xml(account_item), 200

    except Exception as e:
        print(f"[youtubei] Error fetching user info: {e}")
        return None, 500


def build_watch_history_xml(json_data):
    xml_string = '<?xml version="1.0" encoding="UTF-8"?>'
    xml_string += '<feed xmlns:openSearch="http://a9.com/-/spec/opensearch/1.1/" xmlns:media="http://search.yahoo.com/mrss/" xmlns:yt="http://www.youtube.com/xml/schemas/2015">'
    xml_string += '<title type="text">Watch History</title>'
    xml_string += '<openSearch:totalResults>0</openSearch:totalResults>'
    xml_string += '<openSearch:startIndex>1</openSearch:startIndex>'
    xml_string += '<openSearch:itemsPerPage>20</openSearch:itemsPerPage>'

    for tile in _iter_grid_tiles(json_data):
        f = _tile_to_fields(tile)
        if not f["video_id"]:
            continue

        is_hd = False
        for line in tile.get("metadata", {}).get("tileMetadataRenderer", {}).get("lines", []):
            for li in line.get("lineRenderer", {}).get("items", []):
                badge = li.get("lineItemRenderer", {}).get("badge", {}).get("metadataBadgeRenderer", {})
                if badge.get("label") in ("4K", "HD"):
                    is_hd = True

        xml_string += '<entry>'
        xml_string += f'<id>http://ytv2.nossl.revivemii.xyz/api/videos/{f["video_id"]}</id>'
        xml_string += f'<published>{f["published"]}</published>'
        xml_string += f'<title type="text">{escape_xml(f["title"])}</title>'
        xml_string += f'<author><name>{escape_xml(f["author_name"])}</name><uri>https://www.youtube.com/channel/{f["author_id"]}</uri></author>'
        xml_string += f'<yt:hd>{"true" if is_hd else "false"}</yt:hd>'
        xml_string += f'<yt:rating numDislikes="0" numLikes="0"/>'
        xml_string += '<media:group>'
        xml_string += f'<media:thumbnail yt:name="mqdefault" url="http://i.ytimg.com/vi/{f["video_id"]}/mqdefault.jpg" height="240" width="320" time="00:00:00"/>'
        xml_string += f'<media:description>{escape_xml(f["description"])}</media:description>'
        xml_string += f'<yt:duration seconds="{f["duration_seconds"]}"/>'
        xml_string += f'<yt:uploaded>{f["published"]}</yt:uploaded>'
        xml_string += f'<yt:uploaderId>{f["author_id"]}</yt:uploaderId>'
        xml_string += f'<yt:videoid>{f["video_id"]}</yt:videoid>'
        xml_string += f'<media:credit role="uploader" yt:display="{escape_xml(f["author_name"])}">{escape_xml(f["author_name"])}</media:credit>'
        xml_string += '</media:group>'
        xml_string += f'<yt:statistics favoriteCount="0" viewCount="{f["view_count"]}"/>'
        xml_string += '</entry>'

    xml_string += '</feed>'
    return xml_string


def fetch_watch_history(oauth_token, lang="en", gl="US"):
    url = "https://www.youtube.com/youtubei/v1/browse"
    headers = {
        "content-type": "application/json",
        "authorization": f"Bearer {oauth_token}",
        "origin": "https://www.youtube.com",
        "referer": "https://www.youtube.com/tv",
        "x-youtube-client-name": "TVHTML5",
        "user-agent": "Mozilla/5.0 (SMART-TV; Linux; Tizen 6.5) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/5.0 Chrome/108.0.5359.1 TV Safari/537.36",
    }
    payload = {
        "context": {
            "client": {
                "hl": lang,
                "gl": gl,
                "clientName": "TVHTML5",
                "clientVersion": "7.20260715.15.00",
                "platform": "TV",
                "originalUrl": "https://www.youtube.com/tv",
            }
        },
        "browseId": "FEhistory",
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        if response.status_code != 200:
            return None, response.status_code

        data = response.json()
        return build_watch_history_xml(data), 200

    except Exception as e:
        print(f"[youtubei] Error fetching watch history: {e}")
        return None, 500


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



def build_watch_later_xml(json_data):
    xml_string = '<?xml version="1.0" encoding="UTF-8"?>'
    xml_string += '<feed xmlns:openSearch="http://a9.com/-/spec/opensearch/1.1/" xmlns:media="http://search.yahoo.com/mrss/" xmlns:yt="http://www.youtube.com/xml/schemas/2015">'
    xml_string += '<title type="text">Watch Later</title>'

    tiles = list(_iter_grid_tiles(json_data))
    xml_string += f'<openSearch:totalResults>{len(tiles)}</openSearch:totalResults>'
    xml_string += '<openSearch:startIndex>1</openSearch:startIndex>'
    xml_string += '<openSearch:itemsPerPage>20</openSearch:itemsPerPage>'

    for tile in tiles:
        f = _tile_to_fields(tile)
        if not f["video_id"]:
            continue
        xml_string += '<entry>'
        xml_string += f'<id>http://ytv2.nossl.revivemii.xyz/api/videos/{f["video_id"]}</id>'
        xml_string += f'<published>{f["published"]}</published>'
        xml_string += f'<title type="text">{escape_xml(f["title"])}</title>'
        xml_string += f'<author><name>{escape_xml(f["author_name"])}</name><uri>https://www.youtube.com/channel/{f["author_id"]}</uri></author>'
        xml_string += '<media:group>'
        xml_string += f'<media:thumbnail yt:name="mqdefault" url="http://i.ytimg.com/vi/{f["video_id"]}/mqdefault.jpg" height="240" width="320" time="00:00:00"/>'
        xml_string += f'<media:description>{escape_xml(f["description"])}</media:description>'
        xml_string += f'<yt:duration seconds="{f["duration_seconds"]}"/>'
        xml_string += f'<yt:uploaderId>{f["author_id"]}</yt:uploaderId>'
        xml_string += f'<yt:videoid>{f["video_id"]}</yt:videoid>'
        xml_string += f'<media:credit role="uploader" yt:display="{escape_xml(f["author_name"])}">{escape_xml(f["author_name"])}</media:credit>'
        xml_string += '</media:group>'
        xml_string += f'<yt:statistics favoriteCount="0" viewCount="{f["view_count"]}"/>'
        xml_string += '</entry>'

    xml_string += '</feed>'
    return xml_string


def fetch_watch_later(oauth_token, lang="en", gl="US"):
    url = "https://www.youtube.com/youtubei/v1/browse"
    headers = {
        "content-type": "application/json",
        "authorization": f"Bearer {oauth_token}",
        "origin": "https://www.youtube.com",
        "referer": "https://www.youtube.com/tv",
        "x-youtube-client-name": "TVHTML5",
        "user-agent": "Mozilla/5.0 (SMART-TV; Linux; Tizen 6.5) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/5.0 Chrome/108.0.5359.1 TV Safari/537.36",
    }
    payload = {
        "context": {
            "client": {
                "hl": lang, "gl": gl, "clientName": "TVHTML5",
                "clientVersion": "7.20260715.15.00", "platform": "TV",
                "originalUrl": "https://www.youtube.com/tv",
            }
        },
        "browseId": "FEmy_youtube",
        "params": "cAc%3D",
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None, resp.status_code
        return build_watch_later_xml(resp.json()), 200
    except Exception as e:
        print(f"[youtubei] Error fetching watch_later: {e}")
        return None, 500

def build_favorites_xml(json_data):
    xml_string = '<?xml version="1.0" encoding="UTF-8"?>'
    xml_string += '<feed xmlns:openSearch="http://a9.com/-/spec/opensearch/1.1/" xmlns:media="http://search.yahoo.com/mrss/" xmlns:yt="http://www.youtube.com/xml/schemas/2015">'
    xml_string += '<title type="text">Liked Videos</title>'

    tiles = []
    try:
        contents = (json_data["contents"]["tvBrowseRenderer"]["content"]
                    ["tvSurfaceContentRenderer"]["content"]
                    ["twoColumnRenderer"]["rightColumn"]
                    ["playlistVideoListRenderer"]["contents"])
        for item in contents:
            tile = item.get("tileRenderer")
            if tile:
                tiles.append(tile)
    except (KeyError, TypeError):
        pass
    xml_string += f'<openSearch:totalResults>{len(tiles)}</openSearch:totalResults>'
    xml_string += '<openSearch:startIndex>1</openSearch:startIndex>'
    xml_string += '<openSearch:itemsPerPage>20</openSearch:itemsPerPage>'

    for tile in tiles:
        f = _tile_to_fields(tile)
        if not f["video_id"]:
            continue
        xml_string += '<entry>'
        xml_string += f'<id>http://ytv2.nossl.revivemii.xyz/api/videos/{f["video_id"]}</id>'
        xml_string += f'<published>{f["published"]}</published>'
        xml_string += f'<title type="text">{escape_xml(f["title"])}</title>'
        xml_string += f'<author><name>{escape_xml(f["author_name"])}</name><uri>https://www.youtube.com/channel/{f["author_id"]}</uri></author>'
        xml_string += '<media:group>'
        xml_string += f'<media:thumbnail yt:name="mqdefault" url="http://i.ytimg.com/vi/{f["video_id"]}/mqdefault.jpg" height="240" width="320" time="00:00:00"/>'
        xml_string += f'<media:description>{escape_xml(f["description"])}</media:description>'
        xml_string += f'<yt:duration seconds="{f["duration_seconds"]}"/>'
        xml_string += f'<yt:uploaderId>{f["author_id"]}</yt:uploaderId>'
        xml_string += f'<yt:videoid>{f["video_id"]}</yt:videoid>'
        xml_string += f'<media:credit role="uploader" yt:display="{escape_xml(f["author_name"])}">{escape_xml(f["author_name"])}</media:credit>'
        xml_string += '</media:group>'
        xml_string += f'<yt:statistics favoriteCount="0" viewCount="{f["view_count"]}"/>'
        xml_string += '</entry>'

    xml_string += '</feed>'
    return xml_string


def fetch_favorites(oauth_token, lang="en", gl="US"):
    url = "https://www.youtube.com/youtubei/v1/browse"
    headers = {
        "content-type": "application/json",
        "authorization": f"Bearer {oauth_token}",
        "origin": "https://www.youtube.com",
        "referer": "https://www.youtube.com/tv",
        "x-youtube-client-name": "TVHTML5",
        "user-agent": "Mozilla/5.0 (SMART-TV; Linux; Tizen 6.5) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/5.0 Chrome/108.0.5359.1 TV Safari/537.36",
    }
    payload = {
        "context": {
            "client": {
                "hl": lang, "gl": gl, "clientName": "TVHTML5",
                "clientVersion": "7.20260715.15.00", "platform": "TV",
                "originalUrl": "https://www.youtube.com/tv",
            }
        },
        "browseId": "VLLL",
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None, resp.status_code
        return build_favorites_xml(resp.json()), 200
    except Exception as e:
        print(f"[youtubei] Error fetching favorites: {e}")
        return None, 500

