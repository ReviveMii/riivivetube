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
import subprocess
import threading
import time
import requests
from pathlib import Path
from flask import send_file

import youtubei

_transcode_jobs_guard = threading.Lock()


_transcode_jobs = {}


def _start_transcode_job(video_id, videofile_path):
    with _transcode_jobs_guard:
        if os.path.exists(videofile_path):
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
            "tmp_path": videofile_path + ".part",
        }
        _transcode_jobs[video_id] = job

        thread = threading.Thread(
            target=_run_transcode_job,
            args=(video_id, videofile_path, job),
            daemon=True
        )
        thread.start()
        return job


def _run_transcode_job(video_id, videofile_path, job):
    tmp_path = job["tmp_path"]
    downloaded_path = f"/tmp/{video_id}_src.mp4"
    try:
        if Path("cookies.txt").exists():
            ytdlp_cmd = [
                'yt-dlp',
                f'https://www.youtube.com/watch?v={video_id}',
                '-f', '18',
                '--extractor-args', 'youtube:player_client=mweb,tv_simply,web,web_embedded',
                '--cookies', 'cookies.txt',
                '-o', downloaded_path
            ]
            result = subprocess.run(ytdlp_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"WARNING: yt-dlp clients with cookies failed, are cookies missing?")
                ytdlp_cmd = [
                    'yt-dlp',
                    f'https://www.youtube.com/watch?v={video_id}',
                    '-f', '18',
                    '--extractor-args', 'youtube:player_client=android',
                    '-o', downloaded_path
                ]
                result = subprocess.run(ytdlp_cmd, capture_output=True, text=True)
        else:
            print(f"WARNING: cookies.txt not found")
            ytdlp_cmd = [
                'yt-dlp',
                f'https://www.youtube.com/watch?v={video_id}',
                '-f', '18',
                '--extractor-args', 'youtube:player_client=android',
                '-o', downloaded_path
            ]
            result = subprocess.run(ytdlp_cmd, capture_output=True, text=True)

        if result.returncode != 0:
            error_msg = f"yt-dlp error: {result.stderr}"
            send_discord_error(video_id, error_msg)
            raise RuntimeError(error_msg)
        if not os.path.exists(downloaded_path):
            raise RuntimeError("Download finished but file missing")

        job["ready"].set()
        duration = None

        ffmpeg_cmd = [
            './scripts/encode_webm.sh', downloaded_path, tmp_path
        ]

        print("WARNING: no duration found, maybe youtube changed something???")
        proc = subprocess.run(ffmpeg_cmd, capture_output=True)
        if proc.returncode != 0 or not os.path.exists(tmp_path):
            raise RuntimeError(f"ffmpeg error: {proc.stderr.decode(errors='ignore')}")
        written = os.path.getsize(tmp_path)


        os.replace(tmp_path, videofile_path)
    except Exception as e:
        job["error"].append(str(e))
        job["ready"].set()
    finally:
        job["done"].set()
        with _transcode_jobs_guard:
            _transcode_jobs.pop(video_id, None)
        try:
            if os.path.exists(downloaded_path):
                os.remove(downloaded_path)
        except Exception:
            pass


def _serve_cached_webm(videofile_path, safe_id):
    return send_file(
        videofile_path,
        mimetype='video/webm',
        as_attachment=True,
        download_name=f"{safe_id}.webm",
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


def get_discord_webhook_url():
    try:
        with open("webhook.txt", "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def send_discord_error(video_id, error_message):
    webhook_url = get_discord_webhook_url()
    if not webhook_url:
        print("ERROR: no webhook")
        return
    try:
        payload = {
            "embeds": [{
                "title": "yt-dlp error occurred in /get_video",
                "color": 15158332,
                "fields": [
                    {"name": "video_id", "value": video_id, "inline": True},
                    {"name": "error", "value": f"```{error_message[:1000]}```", "inline": False}
                ]
            }]
        }
        requests.post(webhook_url, json=payload, timeout=5)
    except Exception as e:
        print(f"webhook error: {e}")
