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


import subprocess
import json

from config import subtitle_cache

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
