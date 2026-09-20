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

from .parsing import escape_xml, _iter_grid_tiles, _iter_tiles, _tile_to_fields

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
        inner += f'<id>http://ytv2.nossl.revivemii.xyz/feeds/api/videos/{f["video_id"]}</id>'
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
        xml_string += f'<id>http://ytv2.nossl.revivemii.xyz/feeds/api/videos/{f["video_id"]}</id>'
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
                "clientVersion": "7.20260916.14.00",
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
    avatar_url = "http://ytv2.nossl.revivemii.xyz/pfpproxy/" + old_avatar_url
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
                "clientVersion": "7.20260916.14.00",
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
        xml_string += f'<id>http://ytv2.nossl.revivemii.xyz/feeds/api/videos/{f["video_id"]}</id>'
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
                "clientVersion": "7.20260916.14.00",
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
        xml_string += f'<id>http://ytv2.nossl.revivemii.xyz/feeds/api/videos/{f["video_id"]}</id>'
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
                "clientVersion": "7.20260916.14.00", "platform": "TV",
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
        xml_string += f'<id>http://ytv2.nossl.revivemii.xyz/feeds/api/videos/{f["video_id"]}</id>'
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
                "clientVersion": "7.20260916.14.00", "platform": "TV",
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
