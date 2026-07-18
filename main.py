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


from flask import Flask, send_from_directory, send_file, request, Response, jsonify, stream_with_context, abort, redirect
import os
import requests
import xml.etree.ElementTree as ET
import subprocess
import time
import youtubei
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import re
import json
import base64
import uuid
from urllib.parse import urlencode, quote
import random
import string
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per minute"],
    storage_uri="memory://",
)
executor = ThreadPoolExecutor(max_workers=10)
CATEGORIES = {
"feeds/api/users/trends/favorites", "feeds/api/standardfeeds/US/most_popular_Music", "feeds/api/standardfeeds/US/most_popular_Games", "feeds/api/standardfeeds/US/most_popular_Sports", "feeds/api/standardfeeds/US/most_popular_News" }

CATEGORY_MAP = {
    "feeds/api/users/trends/favorites": "trending",
    "feeds/api/standardfeeds/US/most_popular_Music": "music",
    "feeds/api/standardfeeds/US/most_popular_Games": "gaming",
    "feeds/api/standardfeeds/US/most_popular_Sports": "sports",
    "feeds/api/standardfeeds/US/most_popular_News": "news"
}

thumbnail_url_cache = {}
FLV_FOLDER = "./flvcache"
_transcode_jobs_guard = threading.Lock()
_transcode_jobs = {}
TARGET_BITRATE_BPS = 500_000 + 96_000
SIZE_ESTIMATE_MARGIN = 1.30
SIZE_ESTIMATE_OVERHEAD = 200_000
subtitle_cache = {}

if not os.path.exists(FLV_FOLDER):
    os.makedirs(FLV_FOLDER)


def get_first_video_id_from_route(category):
    try:
        url = f"http://127.0.0.1:5005/{category}"
        response = requests.get(url)
        if response.status_code != 200:
            print(f"[{category}] Error fetching: HTTP {response.status_code}")
            return None
        ns = {
            'yt': 'http://www.youtube.com/xml/schemas/2015'
        }

        root = ET.fromstring(response.content)
        entry = root.find('entry')
        if entry is None:
            print(f"[{category}] <entry> not found")
            return None
        videoid_el = entry.find('.//yt:videoid', ns)
        if videoid_el is None:
            print(f"[{category}] <yt:videoid> not found")
            return None
        return videoid_el.text.strip()
    except Exception as e:
        print(f"[{category}] XML parsing error: {e}")
        return None

def cache_thumbnail_url(video_id, category_name):
    url = f"http://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    thumbnail_url_cache[category_name] = url
    print(f"[{category_name}] Cached thumbnail URL: {url}")

def thumbnail_scheduler():
    time.sleep(5)
    while True:
        for category in CATEGORIES:
            video_id = get_first_video_id_from_route(category)
            if video_id:
                name = CATEGORY_MAP.get(category, category)
                cache_thumbnail_url(video_id, name)
            else:
                print(f"[{category}] video id missing")
        time.sleep(60)

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


@app.route('/get_video_info', methods=['GET'])
@limiter.limit("60 per minute")
def get_video_info():
    video_id = request.args.get('video_id')
    if not video_id:
        return jsonify({"error": "video id is missing"}), 400

    video_info = GetVideoInfo().build(video_id)
    return video_info


def channelPfp(channel_id):
    try:
        url = f"https://www.youtube.com/channel/{channel_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        cookies = {
            "SOCS": "CAISNQgDEitib3FfaWRlbnRpdHlmcm9udGVuZHVpc2VydmVyXzIwMjYwNzE0LjA3X3AwGgJkZSACGgYIgL7g0gY",
            "PREF": "f6=40000000&tz=Europe.Berlin"
        }
        resp = requests.get(url, headers=headers, cookies=cookies, timeout=5)
        resp.raise_for_status()
        pattern = r'<meta property="og:image" content="([^"]+)"'
        match = re.search(pattern, resp.text)
        return match.group(1) if match else None

    except Exception:
        return None



@app.route('/feeds/api/users/<user_id>/icon')
def user_icon(user_id):
    avatar_url = channelPfp(user_id)
    if avatar_url:
        try:
            r = requests.get(avatar_url, timeout=5)
            if r.status_code == 200:
                return Response(r.content, mimetype=r.headers.get('Content-Type', 'image/jpeg'))
        except Exception:
            pass

    abort(404)




# TODO: implement pair/lounge proxy in the future...




@app.route('/o/oauth2/device/code', methods=['POST'])
def oauth2_device_code():
    try:
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()

        # open devtools on https://www.youtube.com/tv with Useragent Mozilla/5.0 (SMART-TV; Linux; Tizen 6.5) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/5.0 Chrome/108.0.5359.1 TV Safari/537.36 and look for token and code requests and look into the payload to get these values
        modern_data = {
            "client_id": "861556708454-d6dlm3lh05idd8npek18k6be8ba3oc68.apps.googleusercontent.com",
            "scope": "http://gdata.youtube.com https://www.googleapis.com/auth/youtube-paid-content",
            "device_id": data.get("device_id", "7e6b59dc-dbdb-4dcd-bfa0-c566bc213e14"),
            "device_model": data.get("device_model", "ytlr:samsung:smarttv")
        }
        for key in data:
            if key not in modern_data:
                modern_data[key] = data[key]

        headers = {key: value for key, value in request.headers if key.lower() != 'host'}
        headers['Content-Type'] = 'application/json' if request.is_json else 'application/x-www-form-urlencoded'

        if request.is_json:
            resp = requests.post(f"https://www.youtube.com/o/oauth2/device/code", json=modern_data, headers=headers, timeout=10)
        else:
            resp = requests.post(f"https://www.youtube.com/o/oauth2/device/code", data=modern_data, headers=headers, timeout=10)
        excluded = ['content-encoding', 'transfer-encoding', 'connection', 'keep-alive']
        headers_to_forward = [(k, v) for k, v in resp.headers.items() if k.lower() not in excluded]
        return Response(resp.content, resp.status_code, headers_to_forward)

    except Exception as e:
        print(f"oauth2 device/code error: {e}")
        return f"oauth2 device/code error: {e}", 500


@app.route('/o/oauth2/token', methods=['POST'])
def oauth2_device_token():
    try:
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()

        modern_data = {
            "client_id": "861556708454-d6dlm3lh05idd8npek18k6be8ba3oc68.apps.googleusercontent.com",
            "client_secret": "SboVhoG9s0rNafixCSGGKXAT",
            "grant_type": data.get("grant_type", "http://oauth.net/grant_type/device/1.0")
        }

        for key in data:
            if key not in modern_data or not modern_data.get(key):
                modern_data[key] = data[key]

        if modern_data.get("grant_type") == "http://oauth.net/grant_type/device/1.0":
            if not modern_data.get("code") and not modern_data.get("refresh_token"):
                print("Invalid Request was made to oauth token")

        headers = {key: value for key, value in request.headers if key.lower() != 'host'}
        headers['Content-Type'] = 'application/json' if request.is_json else 'application/x-www-form-urlencoded'
        if request.is_json:
            resp = requests.post(f"https://www.youtube.com/o/oauth2/token", json=modern_data, headers=headers, timeout=10)
        else:
            resp = requests.post(f"https://www.youtube.com/o/oauth2/token", data=modern_data, headers=headers, timeout=10)
        excluded = ['content-encoding', 'transfer-encoding', 'connection', 'keep-alive']
        headers_to_forward = [(k, v) for k, v in resp.headers.items() if k.lower() not in excluded]
        return Response(resp.content, resp.status_code, headers_to_forward)

    except Exception as e:
        print(f"oauth2 device/token error: {e}")
        return f"oauth2 device/token error: {e}", 500

@app.route('/feeds/api/videos/<video_id>')
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



@app.route("/feeds/api/users/default/watch_later", methods=["GET"])
def feeds_watch_later_default():
    oauth_token = request.args.get("oauth_token", "")
    if not oauth_token:
        return Response(status=401)
    xml_data, status = youtubei.fetch_watch_later(oauth_token)
    if xml_data is None:
        return Response(status=status)
    return Response(xml_data, mimetype="text/atom+xml")


@app.route("/feeds/api/users/default/favorites", methods=["GET"])
def feeds_favorites_default():
    oauth_token = request.args.get("oauth_token", "")
    if not oauth_token:
        return Response(status=401)
    xml_data, status = youtubei.fetch_favorites(oauth_token)
    if xml_data is None:
        return Response(status=status)
    return Response(xml_data, mimetype="text/atom+xml")



@app.route("/wiitv")
def wiitv():
    return send_from_directory("assets", "leanbacklite_wii.swf", mimetype='application/x-shockwave-flash')

@app.route("/leanback_ajax")
def leanbackajax():
    return send_from_directory("assets", "leanback_ajax.json", mimetype='application/json')


@app.route('/player_204')
def player():
    return ""

@app.route('/complete/search')
def completesearch():
    query = request.args.get('q')
    if not query:
        return jsonify({"error": "Missing query"}), 400

    suggest_url = (
        "https://suggestqueries-clients6.youtube.com/complete/search?ds=yt&hl=en&gl=us&client=youtube&gs_ri=youtube&q=" + query
    )

    try:
        response = requests.get(suggest_url)
        if response.status_code != 200:
            return jsonify({"error": f"Failed to fetch suggestions: HTTP {response.status_code}"}), 500
        jsonp = response.text
        json_str = re.search(r'\[.*\]', jsonp).group(0)
        data = json.loads(json_str)
        suggestions = [item[0] for item in data[1]]
        root = ET.Element("toplevel")
        for suggestion in suggestions:
            complete_suggestion = ET.SubElement(root, "CompleteSuggestion")
            suggestion_elem = ET.SubElement(complete_suggestion, "suggestion")
            suggestion_elem.set("data", suggestion)
        xml_string = ET.tostring(root, encoding="utf-8", method="xml").decode("utf-8")
        xml_string = '<?xml version="1.0" encoding="UTF-8"?>' + xml_string

        return Response(xml_string, mimetype='text/xml')

    except Exception as e:
        return jsonify({"error": f"Error processing suggestions: {str(e)}"}), 500




def _start_transcode_job(video_id, flv_path):
    with _transcode_jobs_guard:
        if os.path.exists(flv_path):
            return None
        job = _transcode_jobs.get(video_id)
        if job is not None:
            return job

        job = {
            "done": threading.Event(),
            "ready": threading.Event(),
            "error": [],
            "written": 0,
            "total_size": None,
            "tmp_path": flv_path + ".part",
        }
        _transcode_jobs[video_id] = job

        thread = threading.Thread(
            target=_run_transcode_job,
            args=(video_id, flv_path, job),
            daemon=True
        )
        thread.start()
        return job

def _run_transcode_job(video_id, flv_path, job):
    tmp_path = job["tmp_path"]
    try:
        ytdlp_cmd = [
            'yt-dlp',
            f'https://www.youtube.com/watch?v={video_id}',
            '-f', '5/18/best[ext=mp4]/best[height<=240]',
            '--cookies', 'cookies.txt',
            '-g'
        ]
        result = subprocess.run(ytdlp_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"yt-dlp error: {result.stderr}")
        video_url = result.stdout.strip()
        if not video_url:
            raise RuntimeError("No video URL found")

        duration = None
        try:
            info = youtubei.get_video_info(video_id)
            if info:
                n = int(info.get("lengthSeconds", 0))
                duration = n if n > 0 else None
        except Exception:
            pass
        if not duration:
            job["ready"].set()
            duration = None
        else:
            bytes_per_second = TARGET_BITRATE_BPS / 8
            total_size = int(bytes_per_second * duration * SIZE_ESTIMATE_MARGIN) + SIZE_ESTIMATE_OVERHEAD
            with open(tmp_path, 'wb') as f:
                f.truncate(total_size)
            job["total_size"] = total_size
            job["ready"].set()

        ffmpeg_cmd = [
            'ffmpeg', '-y', '-i', video_url,
            '-c:v', 'flv1', '-b:v', '500k', '-vf', 'scale=-1:240',
            '-c:a', 'mp3', '-b:a', '96k',
            '-r', '24', '-g', '24',
            '-f', 'flv', 'pipe:1' if duration else tmp_path
        ]

        if duration:
            proc = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            written = 0
            with open(tmp_path, 'r+b', buffering=0) as out_f:
                while True:
                    chunk = proc.stdout.read(65536)
                    if not chunk:
                        break
                    out_f.write(chunk)
                    os.fsync(out_f.fileno())
                    written += len(chunk)
                    job["written"] = written
            proc.wait()
            if proc.returncode != 0:
                stderr = proc.stderr.read().decode(errors='ignore')
                raise RuntimeError(f"ffmpeg error: {stderr}")
        else:
            print("WARNING: no duration found, maybe youtube changed something???")
            proc = subprocess.run(ffmpeg_cmd, capture_output=True)
            if proc.returncode != 0 or not os.path.exists(tmp_path):
                raise RuntimeError(f"ffmpeg error: {proc.stderr.decode(errors='ignore')}")
            written = os.path.getsize(tmp_path)

        # fixes somes crashes, DONT ASK WHY THIS WORKS
        try:
            corrupt_bytes = int((TARGET_BITRATE_BPS / 8) * 2)
            corrupt_start = max(0, written - corrupt_bytes)
            with open(tmp_path, 'r+b') as f:
                f.seek(corrupt_start)
                f.write(os.urandom(written - corrupt_start))
        except Exception:
            pass

        os.replace(tmp_path, flv_path)
    except Exception as e:
        job["error"].append(str(e))
        job["ready"].set()
    finally:
        job["done"].set()
        with _transcode_jobs_guard:
            _transcode_jobs.pop(video_id, None)


def _serve_cached_flv(flv_path, safe_id):
    return send_file(
        flv_path,
        mimetype='video/x-flv',
        as_attachment=True,
        download_name=f"{safe_id}.flv",
        conditional=True
    )


def _stream_known_length(path, job, range_start, range_end):
    with open(path, 'rb', buffering=0) as f:
        pos = range_start
        while pos <= range_end:
            available = job["written"] if not job["done"].is_set() else job["total_size"]
            if pos >= available:
                time.sleep(0.15)
                continue
            f.seek(pos)
            to_read = min(65536, available - pos, range_end - pos + 1)
            chunk = f.read(to_read)
            if not chunk:
                time.sleep(0.05)
                continue
            pos += len(chunk)
            yield chunk


@app.route('/get_video', methods=['GET'])
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

def run_yt_dlp(video_id):
    cache_key = f"yt_{video_id}"
    if cache_key in subtitle_cache:
        print(f"Returning cached subtitles for {video_id}")
        return subtitle_cache[cache_key]

    try:
        cmd = [
            "yt-dlp",
            "--skip-download",
            "--write-info-json",
            "--sub-format", "json3",
            "--write-auto-sub",
            "--write-sub",
            f"https://www.youtube.com/watch?v={video_id}",
            "-o", "/tmp/%(id)s"
        ]

        print(f"Running yt-dlp for {video_id}...")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            print(f"yt-dlp error: {result.stderr}")
            return None

        info_file = f"/tmp/{video_id}.info.json"
        with open(info_file, 'r', encoding='utf-8') as f:
            info = json.load(f)

        subtitles_dict = {}
        if 'subtitles' in info:
            for lang, formats in info['subtitles'].items():
                subtitles_dict[lang] = formats

        print(f"Found {len(subtitles_dict)} subtitle tracks for {video_id}")
        subtitle_cache[cache_key] = subtitles_dict
        return subtitles_dict

    except subprocess.TimeoutExpired:
        print(f"yt-dlp timeout for {video_id}")
        return None
    except Exception as e:
        print(f"Error running yt-dlp: {e}")
        return None


def json3_to_text_list(json3_subtitle_data):
    cues = []
    try:
        if isinstance(json3_subtitle_data, str):
            data = json.loads(json3_subtitle_data)
        else:
            data = json3_subtitle_data

        events = data.get('events', [])

        for event in events:
            start_ms = event.get('tStartMs', 0)
            duration_ms = event.get('dDurationMs', 0)
            text_parts = []
            for seg in event.get('segs', []):
                if 'utf8' in seg:
                    text_parts.append(seg['utf8'])

            text = ''.join(text_parts).strip()

            if text:
                cues.append({
                    'text': text,
                    'start': start_ms / 1000.0,
                    'duration': duration_ms / 1000.0
                })
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON3: {e}")
        return []

    return cues


def fetch_subtitle_file(video_id, lang_code, format_name='vtt'):
    try:
        cmd = [
            "yt-dlp",
            "--skip-download",
            "--write-subs",
            "--sub-lang", lang_code,
            "--sub-format", format_name,
            f"https://www.youtube.com/watch?v={video_id}",
            "-o", f"/tmp/{video_id}"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            import glob
            files = glob.glob(f"/tmp/{video_id}*.{format_name}")
            if files:
                with open(files[0], 'r', encoding='utf-8') as f:
                    return f.read()

        return None
    except Exception as e:
        print(f"Error fetching subtitle file: {e}")
        return None


@app.route('/timedtext') # currently requires cc_load_policy to be set to 1, will be fixed in the future
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

@app.route('/apiplayer-loader')
def loadapi():
    return send_from_directory('assets', 'loader.swf', mimetype='application/x-shockwave-flash')

@app.route('/videoplayback')
def playback():
    return send_from_directory('assets', 'apiplayer.swf', mimetype='application/x-shockwave-flash')


class Invidious:
    def generateXML(self, json_data):
        xml_string = '<?xml version=\'1.0\' encoding=\'UTF-8\'?>'
        xml_string += '<feed xmlns:openSearch=\'http://a9.com/-/spec/opensearch/1.1/\' xmlns:media=\'http://search.yahoo.com/mrss/\' xmlns:yt=\'http://www.youtube.com/xml/schemas/2015\'>'
        xml_string += '<title type=\'text\'>Videos</title>'
        xml_string += f'<openSearch:totalResults>{len(json_data)}</openSearch:totalResults>'
        xml_string += '<openSearch:startIndex>1</openSearch:startIndex>'
        xml_string += '<openSearch:itemsPerPage>20</openSearch:itemsPerPage>'

        for item in json_data:
            xml_string += '<entry>'
            xml_string += '<id>http://127.0.0.1/api/videos/' + self.escape_xml(item["videoId"]) + '</id>'
            xml_string += '<published>' + self.escape_xml(item.get("publishedText", "")) + '</published>'
            xml_string += '<title type="text">' + self.escape_xml(item.get("title", "")) + '</title>'
            xml_string += '<link rel="http://127.0.0.1/api/videos/' + self.escape_xml(item["videoId"]) + '/related"/>'
            xml_string += '<author><name>' + self.escape_xml(item.get("author", "")) + '</name>'
            xml_string += '<uri>http://127.0.0.1/api/channels/' + self.escape_xml(item.get("authorId", "")) + '</uri></author>'
            xml_string += '<media:group>'
            xml_string += '<media:thumbnail yt:name="hqdefault" url="http://i.ytimg.com/vi/' + self.escape_xml(item["videoId"]) + '/hqdefault.jpg" height="240" width="320" time="00:00:00"/>'
            xml_string += '<yt:duration seconds="' + self.escape_xml(str(item.get("lengthSeconds", 0))) + '"/>'
            xml_string += '<yt:videoid id="' + self.escape_xml(item["videoId"]) + '">' + self.escape_xml(item["videoId"]) + '</yt:videoid>'
            xml_string += '<yt:uploaderId>' + self.escape_xml(item.get("authorId", "")) + '</yt:uploaderId>'
            xml_string += '<media:credit role="uploader" name="' + self.escape_xml(item.get("author", "")) + '">' + self.escape_xml(item.get("author", "")) + '</media:credit>'
            xml_string += '</media:group>'
            xml_string += '<yt:statistics favoriteCount="' + str(item.get("viewCount", 0)) + '" viewCount="' + str(item.get("viewCount", 0)) + '"/>'
            xml_string += '</entry>'

        xml_string += '</feed>'
        return xml_string

    def search(self, query):
        results = youtubei.innertube_search(query)
        return Response(self.generateXML(results), mimetype='text/atom+xml')

    def trends(self, type_param=None):
        results = youtubei.innertube_trending(type_param)
        return Response(self.generateXML(results), mimetype='text/atom+xml')

    def music(self, type_param=None):
        return self.search("music")

    def gaming(self, type_param=None):
        return self.search("gaming")

    def sports(self, type_param=None):
        return self.search("sports")

    def news(self, type_param=None):
        return self.search("news")

    @staticmethod
    def escape_xml(s):
        if s is None:
            return ''
        return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')\
                .replace('"', '&quot;').replace("'", '&apos;')

inv = Invidious()

@app.route("/feeds/api/users/default", methods=["GET"])
def feeds_users_default():
    oauth_token = request.args.get("oauth_token", "")
    if not oauth_token:
        return Response(status=401)

    xml_data, status = youtubei.fetch_user_info(oauth_token)
    if xml_data is None:
        return Response(status=status)

    return Response(xml_data, mimetype="text/atom+xml")

@app.route('/pfpproxy/<path:url>', methods=['GET', 'HEAD'])
def pfp_proxy(url):
    if 'yt3.ggpht.com' not in url:
        return "Invalid URL", 400

    if not url.startswith('http://') and not url.startswith('https://'):
        url = 'https://' + url

    try:
        response = requests.request(
            method=request.method,
            url=url,
            headers={key: value for key, value in request.headers if key != 'Host'},
            allow_redirects=True,
            timeout=10
        )

        return Response(
            response.content,
            status=response.status_code,
            headers=dict(response.headers)
        )
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route("/feeds/api/users/default/watch_history", methods=["GET"])
def feeds_watch_history_default():
    oauth_token = request.args.get("oauth_token", "")
    if not oauth_token:
        return Response(status=401)

    xml_data, status = youtubei.fetch_watch_history(oauth_token)
    if xml_data is None:
        return Response(status=status)

    return Response(xml_data, mimetype="text/atom+xml")

@app.route("/feeds/api/users/default/river", methods=["GET"])
def feeds_river_default():
    oauth_token = request.args.get("oauth_token", "")
    if not oauth_token:
        return Response(status=401)
    xml_data, status = youtubei.fetch_river_tv(oauth_token)
    if xml_data is None:
        return Response(status=status)

    return Response(xml_data, mimetype="text/atom+xml")

@app.route('/feeds/api/videos')
def api_videos():
    query = request.args.get('q')
    if not query:
        return jsonify({"error": "Missing 'q' parameter"}), 400
    try:
        return inv.search(query)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/feeds/api/users/trends/favorites')
def trending():
    try:
        return inv.trends()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/feeds/api/standardfeeds/US/most_popular_Music')
def trending_music():
    try:
        return inv.music()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/feeds/api/standardfeeds/US/most_popular_Games')
def trending_gaming():
    try:
        return inv.gaming()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/feeds/api/standardfeeds/US/most_popular_Sports')
def trending_sports():
    try:
        return inv.sports()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/feeds/api/standardfeeds/US/most_popular_News')
def trending_news():
    try:
        return inv.news()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/dl/<category>.jpg')
def serve_thumbnail(category):
    allowed = {"trending", "music", "gaming", "sports", "news"}
    if category not in allowed:
        abort(404)

    url = thumbnail_url_cache.get(category)
    if not url:
        for cat, name in CATEGORY_MAP.items():
            if name == category:
                video_id = get_first_video_id_from_route(cat)
                if video_id:
                    url = f"http://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                    thumbnail_url_cache[category] = url
                    break

    if not url:
        abort(404)

    return redirect(url, code=302)

@app.route("/cookies.txt")
def cookiestxt():
    abort(404)

@app.route("/<path:filename>")
def serve_video(filename):
    file_path = os.path.join(filename)
    if not os.path.exists(file_path):
        abort(404)
    return send_file(file_path)
@app.errorhandler(429)
def ratelimit_handler(e):
    xml = f'<?xml version="1.0"?><error>Rate limit exceeded. Retry after {e.description}</error>'
    return Response(xml, status=429, mimetype='text/xml')
@app.errorhandler(404)
def notfound_handler(e):
    xml = f'<?xml version="1.0"?><error>404 Not Found. If you see this, you are not a wii >:[</error>'
    return Response(xml, status=404, mimetype='text/xml')

if __name__ == "__main__":
    threading.Thread(target=thumbnail_scheduler, daemon=True).start()
    app.run(host="0.0.0.0", port=5005)
