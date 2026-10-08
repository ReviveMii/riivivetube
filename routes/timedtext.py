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


import xml.etree.ElementTree as ET
from flask import Blueprint, request, Response

from extensions import limiter
from youtubei import get_caption_tracks, fetch_caption_cues
from subtitles import caption_log
from config import subtitle_cache

bp = Blueprint('timedtext', __name__)

def _tracks(video_id):
    key = f"tracks_{video_id}"
    if key not in subtitle_cache:
        tracks = get_caption_tracks(video_id)
        if tracks:
            subtitle_cache[key] = tracks
        return tracks
    return subtitle_cache[key]


def _pick_track(tracks, lang_code):
    for t in tracks:
        if t['languageCode'] == lang_code and t['kind'] != 'asr':
            return t
    for t in tracks:
        if t['languageCode'] == lang_code:
            return t
    return None


@bp.route('/timedtext')
@limiter.limit("60 per minute")
def timedtext():
    req_type = request.args.get('type')
    video_id = request.args.get('v')
    lang_code = request.args.get('lang', 'de')

    if not video_id:
        return "Missing video_id", 400

    if req_type == 'list':
        tracks = _tracks(video_id)

        if not tracks:
            return Response('<transcript_list></transcript_list>', content_type='text/xml; charset=utf-8')

        track_list_root = ET.Element('transcript_list')
        for track_id, t in enumerate(tracks):
            track_elem = ET.SubElement(track_list_root, 'track')
            track_elem.set('id', str(track_id))
            track_elem.set('name', '')
            track_elem.set('lang_code', t['languageCode'])
            track_elem.set('lang_translated', t['name'])
            track_elem.set('kind', t['kind'])
            track_elem.set('lang_default', 'true' if track_id == 0 else 'false')
            track_elem.set('cantran', 'false')
            track_elem.set('formats', '1')

        xml = ET.tostring(track_list_root, encoding='unicode')
        return Response(xml, content_type='text/xml; charset=utf-8')

    elif req_type == 'track':
        track = _pick_track(_tracks(video_id), lang_code)

        if not track:
            return Response('<transcript></transcript>', content_type='text/xml; charset=utf-8')

        cache_key = f"cues_{video_id}_{track['languageCode']}_{track['kind']}"
        cues = subtitle_cache.get(cache_key)
        if cues is None:
            cues = fetch_caption_cues(video_id, track)
            if cues:
                subtitle_cache[cache_key] = cues

        root = ET.Element('transcript')
        for cue in cues:
            text_elem = ET.SubElement(root, 'text')
            text_elem.set('start', f"{cue['start']:.3f}")
            text_elem.set('dur', f"{cue['duration']:.3f}")
            text_elem.text = cue['text']
        xml = ET.tostring(root, encoding='unicode')

        caption_log(f"Returning {len(cues)} subtitle cues for {video_id}/{lang_code}")
        return Response(xml, content_type='text/xml; charset=utf-8')

    else:
        return "Invalid type parameter", 400
