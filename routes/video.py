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


import os
import re
import time
import xml.etree.ElementTree as ET
from urllib.parse import quote, quote_plus
from flask import Blueprint, request, Response, jsonify, stream_with_context

import youtubei
from config import VIDEO_FOLDER
from extensions import limiter
from transcode import _start_transcode_job, _get_transcode_job, _serve_cached_webm, send_discord_error
import livestream
import videostream

bp = Blueprint('video', __name__)

MSG_TOO_LONG = "Videos over 45 minutes are currently disabled, due to server load issues."
MSG_LIVE_FAILED = "This livestream could not be started. It may have ended, or the server could not reach it."
MSG_UNAVAILABLE = (
    "This video is unavailable. If this happens too often with regular videos, please report it in our Discord (www.revivemii.xyz/discord)"
)

def _fail(reason, code=150):
    return Response(
        f"status=fail&errorcode={code}&reason={quote_plus(reason)}",
        content_type='text/plain'
    )

_video_durations = {}


class GetVideoInfo:
    def build(self, videoId):
        info = youtubei.get_video_info(videoId)
        if not info:
            return _fail(MSG_UNAVAILABLE)
        is_live = bool(info.get('isLive'))
        length_seconds = info.get('lengthSeconds', 0)
        if is_live:
            livestream.mark_live(videoId)
            livestream.remember_start(videoId, info.get('publishedText'))
            length_seconds = livestream.LIVE_DURATION
            err = livestream.prepare(videoId)
            if err:
                return _fail(MSG_LIVE_FAILED)
        try:
            length_int = int(length_seconds or 0)
        except (TypeError, ValueError):
            length_int = 0
        if length_int > 45 * 60 and not is_live:
            return _fail(MSG_TOO_LONG)
        safe_id = re.sub(r'[^A-Za-z0-9_-]', '', videoId)
        videofile_path = os.path.join(VIDEO_FOLDER, f"{safe_id}.webm")
        streaming = False
        if not is_live and not os.path.exists(videofile_path) and videostream.STREAM_VIDEOS:
            err = videostream.prepare_video(videoId)
            if err:
                send_discord_error(videoId, err)
                return _fail(MSG_UNAVAILABLE)
            _video_durations[safe_id] = length_int
            streaming = True
        elif not is_live and not os.path.exists(videofile_path):
            job = _start_transcode_job(safe_id, videofile_path, max_duration=45 * 60)
            if job is not None:
                if not job["ready"].wait(120):
                    return _fail(MSG_UNAVAILABLE)
                if job["error"]:
                    if job["error_kind"] == "too_long":
                        return _fail(MSG_TOO_LONG)
                    return _fail(MSG_UNAVAILABLE)

        title = info.get('title', '')
        author = info.get('author', '')

        fmtList = "43/854x480/9/0/115"
        fmtStreamMap = f"43|"
        fmtMap = "43/0/7/0/0"
        thumbnailUrl = f"http://i.ytimg.com/vi/{videoId}/mqdefault.jpg"

        response_str = (
            f"status=ok&"
            f"length_seconds={length_seconds}&"
            f"live_playback={1 if is_live or streaming else 0}&"
            f"keywords=a&"
            f"vq=None&"
            f"muted=0&"
            f"avg_rating=5.0&"
            f"thumbnailUrl={thumbnailUrl}&"
            f"allow_ratings=1&"
            f"hl=en&"
            f"ftoken=&"
            f"allow_embed=1&"
            f"fmtMap={fmtMap}&"
            f"fmt_url_map={fmtStreamMap}&"
            f"token=null&"
            f"plid=null&"
            f"track_embed=0&"
            f"author={author}&"
            f"title={title}&"
            f"videoId={videoId}&"
            f"fmtList={fmtList}&"
            f"fmtStreamMap={fmtStreamMap}&"
            #f"cc_module=http://ytv2.nossl.revivemii.xyz/assets/subtitle_module.swf&" # broken
            #f"cc_load_policy=3&" # also broken
            f"{quote('http://ytv2.nossl.revivemii.xyz/timedtext?', safe='')}"
        )
        return Response(response_str, content_type='text/plain')


@bp.route('/get_video_info', methods=['GET'])
@limiter.limit("20 per minute")
def get_video_info():
    video_id = request.args.get('video_id')
    if not video_id:
        return jsonify({"error": "video id is missing"}), 400

    video_info = GetVideoInfo().build(video_id)
    return video_info


@bp.route('/feeds/api/videos/<video_id>')
def video_details(video_id):
    try:
        video_info = youtubei.get_video_info(video_id)
        if video_info and video_info.get('isLive'):
            livestream.remember_start(video_id, video_info.get('publishedText'))
            video_info = dict(video_info, lengthSeconds=livestream.LIVE_DURATION,
                              publishedText=livestream.started_text(video_id))
        if not video_info:
            return Response(
                '<error>Video not found</error>',
                mimetype='text/xml',
                status=404
            )

        ns = {
            'media': 'http://search.yahoo.com/mrss/',
            'yt': 'http://www.youtube.com/xml/schemas/2015'
        }

        root = ET.Element('entry')
        ET.SubElement(root, 'id').text = f"http://ytv2.nossl.revivemii.xyz/feeds/api/videos/{video_id}"
        ET.SubElement(root, 'title').text = video_info.get('title', '')
        ET.SubElement(root, 'published').text = video_info.get('publishedText', '')
        author = ET.SubElement(root, 'author')
        ET.SubElement(author, 'name').text = video_info.get('author', '')
        media_group = ET.SubElement(root, 'media:group')
        ET.SubElement(
            media_group,
            'media:thumbnail',
            attrib={
                'yt:name': 'hqdefault',
                'url': f"http://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                'width': '320',
                'height': '240'
            }
        )
        ET.SubElement(
            media_group,
            'yt:duration',
            attrib={'seconds': str(video_info.get('lengthSeconds', 0))}
        )
        ET.SubElement(media_group, 'yt:videoid').text = video_id
        ET.SubElement(media_group, 'yt:uploaderId').text = video_info.get('authorId', '')
        stats = ET.SubElement(root, 'yt:statistics')
        stats.set('viewCount', str(video_info.get('viewCount', 0)))
        stats.set('likeCount', str(video_info.get('likeCount', 0)))
        xml_str = ET.tostring(root, encoding='utf-8', method='xml').decode()
        xml_str = f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_str}'

        return Response(xml_str, mimetype='text/xml')

    except Exception as e:
        return Response(
            f'<error>{str(e)}</error>',
            mimetype='text/xml',
            status=500
        )


@bp.route('/get_video', methods=['GET'])
@limiter.exempt
def get_video():
    video_id = request.args.get('video_id')
    if not video_id:
        return "", 400

    if livestream.is_live_id(video_id):
        return livestream.stream_response(video_id)

    safe_id = re.sub(r'[^A-Za-z0-9_-]', '', video_id)
    videofile_path = os.path.join(VIDEO_FOLDER, f"{safe_id}.webm")

    if os.path.exists(videofile_path):
        return _serve_cached_webm(videofile_path, safe_id)

    if videostream.has_video_urls(safe_id) and videostream.STREAM_VIDEOS:
        return videostream.stream_video(safe_id, _video_durations.get(safe_id) or livestream.LIVE_DURATION)
    job = _get_transcode_job(safe_id)
    if job is None:
        if os.path.exists(videofile_path):
            return _serve_cached_webm(videofile_path, safe_id)
        return "Video not prepared, call get_video_info first", 404

    if not job["done"].wait(900):
        return "Timed out waiting for transcode to finish", 504
    if job["error"]:
        return job["error"][0], 500
    if not os.path.exists(videofile_path):
        return "Transcode finished but output file is missing", 500
    return _serve_cached_webm(videofile_path, safe_id)
