# used code and swf files from liinback and yt2009wii

# work in progress


from flask import Flask, send_from_directory, send_file, request, Response, jsonify, stream_with_context
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

app = Flask(__name__)
stream_cache = {}
CACHE_DURATION = 300
executor = ThreadPoolExecutor(max_workers=10)
CATEGORIES = ["trending", "music", "gaming", "sports", "news"]
DL_FOLDER = "./dl"

if not os.path.exists(DL_FOLDER):
    os.makedirs(DL_FOLDER)

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

def download_thumbnail(video_id, category):
    url = f"http://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            os.makedirs(DL_FOLDER, exist_ok=True)
            filepath = os.path.join(DL_FOLDER, f"{category}.jpg")
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            print(f"[{category}] Thumbnail saved: {filepath}")
        else:
            print(f"[{category}] HTTP ERROR: HTTP {response.status_code}")
    except Exception as e:
        print(f"[{category}] Error: {e}")

def thumbnail_scheduler():
    while True:
        for category in CATEGORIES:
            video_id = get_first_video_id_from_route(category)
            if video_id:
                download_thumbnail(video_id, category)
            else:
                print(f"[{category}] video id missing")
        time.sleep(600)

class GetVideoInfo:
    def build(self, videoId):
        streamUrl = f"https://www.googleapis.com/youtubei/v1/player?videoId={videoId}"
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0',
            'Cookie': 'cookie',
            'X-Goog-Visitor-Id': "id",
            'X-Youtube-Bootstrap-Logged-In': 'false'
        }
        payload = {
            "context": {
                "client": {
                    "hl": "en",
                    "gl": "US",
                    "clientName": "WEB",
                    "clientVersion": "2.20231221"
                }
            },
            "videoId": videoId,
            "params": ""
        }
        response = requests.post(streamUrl, json=payload, headers=headers)
        if response.status_code != 200:
            return f"video info error: {response.status_code}", response.status_code
        
        try:
            json_data = response.json()
    #   debug     print(json_data)
            title = json_data['videoDetails']['title']
            length_seconds = json_data['videoDetails']['lengthSeconds']
            author = json_data['videoDetails']['author']
        except KeyError as e:
            return f"KeyError ): {e}", 400
        
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
            f"fmtStreamMap={fmtStreamMap}"
        )
        return Response(response_str, content_type='text/plain')


@app.route('/get_video_info', methods=['GET'])
def get_video_info():
    video_id = request.args.get('video_id')
    if not video_id:
        return jsonify({"error": "video id is missing"}), 400

    video_info = GetVideoInfo().build(video_id)
    return video_info

@app.route("/wiitv")
def wiitv():
    return send_from_directory(".", "leanbacklite_wii.swf", mimetype='application/x-shockwave-flash')


@app.route("/<path:filename>")
def serve_video(filename):
    file_path = os.path.join(filename)
    if not os.path.exists(file_path):
        return "404 Not found", 404
    return send_file(file_path)

@app.route('/player_204')
def player():
    return ""
    
@app.route('/complete/search')
def completesearch():
    query = request.args.get('q')
    if not query:
        return jsonify({"error": "Missing 'q' parameter"}), 400

    suggest_url = (
        "https://suggestqueries-clients6.youtube.com/complete/search"
        "?ds=yt&hl=en&gl=de&client=youtube&gs_ri=youtube"
        "&sugexp=uqap13ns10_e2,ytpso.bo.me=1,ytpsoso.bo.me=1,"
        "ytpso.bo.bro.mi=51533027,ytpsoso.bo.bro.mi=51533027,"
        "ytpso.bo.bro.vsw=1.0,ytpsoso.bo.bro.vsw=1.0,"
        "ytpso.bo.bro.lsw=0.0,ytpsoso.bo.bro.lsw=0.0"
        "&h=180&w=320&ytvs=1&gs_id=2&q=" + query
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

CONTENT_LENGTH = 50000000

@app.route('/git_video', methods=['GET'])
def git_video():
    video_id = request.args.get('video_id')
    if not video_id:
        return "", 400

    ytdlp_cmd = [
        'yt-dlp',
        f'https://www.youtube.com/watch?v={video_id}',
        '-f', '5/18/best[ext=mp4]/best[height<=240]',
        '--cookies', 'c.txt',
        '-g'
    ]

    try:
        result = subprocess.run(ytdlp_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return f"yt-dlp error: {result.stderr}", 500
        video_url = result.stdout.strip()
        if not video_url:
            return "No video URL found", 500
    except Exception as e:
        return f"yt-dlp error: {e}", 500

    range_header = request.environ.get('HTTP_RANGE', '')
    range_start = 0
    range_end = CONTENT_LENGTH - 1
    status = '200 OK'
    headers = [
        ('Content-Type', 'video/x-flv'),
        ('Content-Disposition', f'attachment; filename="{video_id}.flv"'),
        ('Accept-Ranges', 'bytes'),
        ('Content-Length', str(CONTENT_LENGTH))
    ]

    if range_header:
        match = re.match(r'bytes=(\d+)-(\d*)', range_header)
        if match:
            range_start = int(match.group(1))
            range_end = int(match.group(2)) if match.group(2) else CONTENT_LENGTH - 1
            if range_start >= CONTENT_LENGTH or range_end >= CONTENT_LENGTH:
                return "Range Not Satisfiable", 416
            status = '206 Partial Content'
            headers = [
                ('Content-Type', 'video/x-flv'),
                ('Content-Disposition', f'attachment; filename="{video_id}.flv"'),
                ('Accept-Ranges', 'bytes'),
                ('Content-Range', f'bytes {range_start}-{range_end}/{CONTENT_LENGTH}'),
                ('Content-Length', str(range_end - range_start + 1))
            ]

    total_bitrate = 500000 + 96000
    bytes_per_second = total_bitrate / 8
    start_time = range_start / bytes_per_second
    duration = (range_end - range_start + 1) / bytes_per_second

    ffmpeg_cmd = [
        'ffmpeg', '-i', video_url,
        '-ss', str(start_time),
        '-t', str(duration),
        '-c:v', 'flv1', '-b:v', '500k', '-vf', 'scale=-1:240',
        '-c:a', 'mp3', '-b:a', '96k',
        '-r', '24', '-g', '24',
        '-f', 'flv', 'pipe:1'
    ]

    def generate(environ, start_response):
        start_response(status, headers)
        try:
            process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            while True:
                chunk = process.stdout.read(8192)
                if not chunk:
                    break
                yield chunk

            stderr = process.communicate()[1]
            if process.returncode != 0:
                yield f"ffmpeg error: {stderr.decode()}".encode()
        except Exception as e:
            yield f"ffmpeg error: {str(e)}".encode()

    return generate


@app.route('/get_video', methods=['GET'])
def get_video():
    if not os.path.exists("sigma/videos"):
        os.makedirs("sigma/videos")

    video_id = request.args.get('video_id')
    if not video_id:
        return "", 400

    folder = "sigma/videos"
    mp4_path = os.path.join(folder, f"{video_id}.mp4")
    webm_path = os.path.join(folder, f"{video_id}.webm")

    if os.path.exists(webm_path):
        return send_file(webm_path, as_attachment=True)

    ytdlp_cmd = [
        'yt-dlp',
        f'https://www.youtube.com/watch?v={video_id}',
        '-f', 'best[ext=mp4]/best',
        '-o', mp4_path
    ]

    try:
        result = subprocess.run(ytdlp_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return f"yt-dlp error: {result.stderr}", 500
    except Exception as e:
        return f"{e}", 500

    if not os.path.exists(mp4_path):
        return "Download failed", 500

    vf = 'scale=-1:360'
    ffmpeg_cmd = [
        'ffmpeg', '-i', mp4_path,
        '-vf', vf,
        '-c:v', 'libvpx', '-b:v', '300k', '-cpu-used', '8',
        '-pix_fmt', 'yuv420p', '-c:a', 'libvorbis', '-b:a', '128k',
        '-r', '30', '-g', '30',
        webm_path
    ]

    subprocess.run(ffmpeg_cmd)

    return send_file(webm_path, as_attachment=True)


@app.route('/apiplayer-loader')
def loadapi():
    return send_from_directory('.', 'loader.swf', mimetype='application/x-shockwave-flash')

@app.route('/videoplayback')
def playback():
    return send_from_directory('.', 'apiplayer.swf', mimetype='application/x-shockwave-flash')


class Invidious:
    def generateXML(self, json_data):
        xml_string = '<?xml version=\'1.0\' encoding=\'UTF-8\'?>'
        xml_string += '<feed xmlns:openSearch=\'http://a9.com/-/spec/opensearch/1.1/\' xmlns:media=\'http://search.yahoo.com/mrss/\' xmlns:yt=\'http://www.youtube.com/xml/schemas/2015\'>'
        xml_string += '<title type=\'text\'>Videos</title>'
        xml_string += '<author><name>ReviveMii</name><uri>http://revivemii.xyz</uri></author>'
        xml_string += '<generator ver=\'1.0\' uri=\'http://new.old.errexe.xyz/\'>RiiviveTube</generator>'
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

@app.route('/feeds/api/videos')
def api_videos():
    query = request.args.get('q')
    if not query:
        return jsonify({"error": "Missing 'q' parameter"}), 400
    try:
        return inv.search(query)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/trending')
def trending():
    try:
        return inv.trends()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/music')
def trending_music():
    try:
        return inv.music()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/gaming')
def trending_gaming():
    try:
        return inv.gaming()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/sports')
def trending_sports():
    try:
        return inv.sports()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/news')
def trending_news():
    try:
        return inv.news()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    threading.Thread(target=thumbnail_scheduler, daemon=True).start()
    app.run(host="0.0.0.0", port=5005, debug=True)
