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


import json
from functools import lru_cache

import requests
from flask import Blueprint, Response, request

bp = Blueprint('transliterate', __name__)

INPUT_TOOLS_URL = "https://inputtools.google.com/request"
ITC = {
    "ja-Hira|ja": "ja-t-ja-hira-i0-und",
    "en|zh": "zh-t-i0-pinyin",
}


@lru_cache(maxsize=512)
def _lookup(itc, text, num):
    r = requests.get(
        INPUT_TOOLS_URL,
        params={"text": text, "itc": itc, "num": num, "cp": 0, "cs": 1,
                "ie": "utf-8", "oe": "utf-8", "app": "riivivetube"},
        timeout=5,
    )
    r.raise_for_status()
    return r.json()


def to_client_format(payload):
    if not payload or payload[0] != "SUCCESS" or not payload[1]:
        return None
    entry = payload[1][0]
    return [entry[0], entry[1], []]


def _to_katakana(text):
    return "".join(chr(ord(c) + 0x60) if "\u3041" <= c <= "\u3096" else c for c in text)


def ensure_kana(text, cands, pos=3):
    out = list(cands)
    for extra in (_to_katakana(text), text):
        if extra and extra not in out:
            out.insert(min(pos, len(out)), extra)
            pos += 1
    return out


@bp.route('/api/transliterate', methods=['GET', 'POST'])
def transliterate():
    langpair = request.values.get("langpair", "ja-Hira|ja")
    text = request.values.get("text", "")
    try:
        num = max(1, min(int(request.values.get("num", 10)), 20))
    except ValueError:
        num = 10
    itc = ITC.get(langpair)
    entry = None
    if itc and text:
        try:
            entry = to_client_format(_lookup(itc, text, num))
        except Exception as e:
            print(f"[transliterate] lookup failed: {e}")
    if entry is None:
        entry = [text, [], []]
    elif langpair == "ja-Hira|ja":
        entry[1] = ensure_kana(entry[0], entry[1])
    return Response(json.dumps(entry), mimetype="application/json")
