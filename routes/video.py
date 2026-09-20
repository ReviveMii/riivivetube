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
from urllib.parse import quote
from flask import Blueprint, request, Response, jsonify, stream_with_context

import youtubei
from config import FLV_FOLDER
from extensions import limiter
from transcode import _start_transcode_job, _serve_cached_flv, _stream_known_length

bp = Blueprint('video', __name__)


class GetVideoInfo:
    def build(self, videoId):
        info = youtubei.get_video_info(videoId)
        if not info:
            return f"video info error: unable to fetch metadata", 500

        length_seconds = info.get('lengthSeconds', 0)
        title = info.get('title', '')
        author = info.get('author', '')

        fmtList = "43/854x480/9/0/115"
        fmtStreamMap = f"43|"
        fmtMap = "43/0/7/0/0"
        thumbnailUrl = f"http://i.ytimg.com/vi/{videoId}/mqdefault.jpg"

        response_str = (
            f"status=ok&"
            f"length_seconds={length_seconds}&"
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
            f"cc_module=http://ytv2.nossl.revivemii.xyz/assets/subtitle_module.swf&"
            f"cc_load_policy=3&" # set to 1 to force subtitles if you want subtitles. currently disabled because you cant disable the subtitles, will be fixed someday
            f"{quote('http://ytv2.nossl.revivemii.xyz/timedtext?', safe='')}"
        )
        return Response(response_str, content_type='text/plain')


@bp.route('/get_video_info', methods=['GET'])
@limiter.limit("60 per minute")
def get_video_info():
    video_id = request.args.get('video_id')
    if not video_id:
        return jsonify({"error": "video id is missing"}), 400

    video_info = GetVideoInfo().build(video_id)
    return video_info


@bp.route('/feeds/api/videos/<video_id>')
def video_details(video_id):
    try:
        safe_id = re.sub(r'[^A-Za-z0-9_-]', '', video_id)
        flv_path = os.path.join(FLV_FOLDER, f"{safe_id}.flv")
        if not os.path.exists(flv_path):
            _start_transcode_job(safe_id, flv_path)

        video_info = youtubei.get_video_info(video_id)
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
@limiter.limit("20 per minute")
def get_video():
    video_id = request.args.get('video_id')
    if not video_id:
        return "", 400

    safe_id = re.sub(r'[^A-Za-z0-9_-]', '', video_id)
    flv_path = os.path.join(FLV_FOLDER, f"{safe_id}.flv")

    if os.path.exists(flv_path):
        return _serve_cached_flv(flv_path, safe_id)

    job = _start_transcode_job(safe_id, flv_path)
    if job is None:
        return _serve_cached_flv(flv_path, safe_id)

    ready_deadline = time.time() + 20
    while not job["ready"].is_set():
        if time.time() > ready_deadline:
            return "Timed out preparing transcode", 504
        time.sleep(0.1)

    if job["total_size"] is None:
        print("WARNING: no duration found, maybe youtube changed something???")
        wait_deadline = time.time() + 180
        while not job["done"].is_set():
            if time.time() > wait_deadline:
                return "Timed out waiting for transcode to finish", 504
            time.sleep(0.2)
        if job["error"]:
            return job["error"][0], 500
        if not os.path.exists(flv_path):
            return "Transcode finished but output file is missing", 500
        return _serve_cached_flv(flv_path, safe_id)

    total_size = job["total_size"]

    range_header = request.environ.get('HTTP_RANGE', '')
    range_start = 0
    range_end = total_size - 1
    is_range = False
    if range_header:
        match = re.match(r'bytes=(\d+)-(\d*)', range_header)
        if match:
            is_range = True
            range_start = int(match.group(1))
            range_end = int(match.group(2)) if match.group(2) else total_size - 1
            range_start = min(range_start, total_size - 1)
            range_end = min(range_end, total_size - 1)

    headers = {
        'Content-Type': 'video/x-flv',
        'Content-Disposition': f'attachment; filename="{safe_id}.flv"',
        'Accept-Ranges': 'bytes',
        'Content-Length': str(range_end - range_start + 1),
    }
    status = 200
    if is_range:
        status = 206
        headers['Content-Range'] = f'bytes {range_start}-{range_end}/{total_size}'

    read_path = job["tmp_path"] if not os.path.exists(flv_path) else flv_path

    return Response(
        stream_with_context(_stream_known_length(read_path, job, range_start, range_end)),
        status=status,
        headers=headers
    )
