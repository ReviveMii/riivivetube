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
from config import TARGET_BITRATE_BPS, SIZE_ESTIMATE_MARGIN, SIZE_ESTIMATE_OVERHEAD

_transcode_jobs_guard = threading.Lock()


_transcode_jobs = {}


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
    downloaded_path = f"/tmp/{video_id}_src.mp4"
    try:
        if Path("cookies.txt").exists():
            ytdlp_cmd = [
                'yt-dlp',
                f'https://www.youtube.com/watch?v={video_id}',
                '-f', '18',
                '--extractor-args', 'youtube:player_client=web,web_embedded,tv_simply,android',
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
            'ffmpeg', '-y', '-i', downloaded_path,
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
        try:
            if os.path.exists(downloaded_path):
                os.remove(downloaded_path)
        except Exception:
            pass


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
