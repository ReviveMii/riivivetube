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
from subtitles import run_yt_dlp, json3_to_text_list, fetch_subtitle_file

bp = Blueprint('timedtext', __name__)


@bp.route('/timedtext') # currently requires cc_load_policy to be set to 1, will be fixed in the future
@limiter.limit("10 per minute")
def timedtext():
    req_type = request.args.get('type')
    video_id = request.args.get('v')
    lang_code = request.args.get('lang', 'de')

    if not video_id:
        return "Missing video_id", 400

    if req_type == 'list':
        subtitles = run_yt_dlp(video_id)

        if not subtitles:
            xml = '''<transcript_list>
  <track id="0" name="" lang_code="en" lang_translated="English"
         kind="" lang_default="true" cantran="false" formats="1"/>
</transcript_list>'''
            return Response(xml, content_type='text/xml')

        track_list_root = ET.Element('transcript_list')
        track_id = 0

        for lang, formats in subtitles.items():
            track_elem = ET.SubElement(track_list_root, 'track')
            track_elem.set('id', str(track_id))
            track_elem.set('name', '')
            track_elem.set('lang_code', lang)
            track_elem.set('lang_translated', lang.upper())
            track_elem.set('kind', '')
            track_elem.set('lang_default', 'true' if track_id == 0 else 'false')
            track_elem.set('cantran', 'true')
            track_elem.set('formats', '1')

            track_id += 1

        xml = ET.tostring(track_list_root, encoding='unicode')
        return Response(xml, content_type='text/xml')

    elif req_type == 'track':
        subtitles = run_yt_dlp(video_id)

        if not subtitles or lang_code not in subtitles:
            xml = '<transcript></transcript>'
            return Response(xml, content_type='text/xml')

        subtitle_file_content = fetch_subtitle_file(video_id, lang_code, 'json3')

        if not subtitle_file_content:
            print(f"Could not fetch subtitle file for {video_id}/{lang_code}")
            xml = '<transcript></transcript>'
            return Response(xml, content_type='text/xml')

        cues = json3_to_text_list(subtitle_file_content)
        root = ET.Element('transcript')
        for cue in cues:
            text_elem = ET.SubElement(root, 'text')
            text_elem.set('start', f"{cue['start']:.1f}")
            text_elem.set('dur', f"{cue['duration']:.1f}")
            text_elem.text = cue['text']
        xml = ET.tostring(root, encoding='unicode')


        print(f"Returning {len(cues)} subtitle cues for {video_id}/{lang_code}")
        return Response(xml, content_type='text/xml')

    else:
        return "Invalid type parameter", 400
