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


import re
import subprocess
import json
import unicodedata
import glob
import os
import shutil
import sys

from config import subtitle_cache


def caption_log(msg):
    if os.environ.get("CAPTION_DEBUG") == "1":
        print(msg)


LATIN_LANGS = ("en", "fr", "es", "pt", "de", "it", "nl", "ca", "gl", "eu", "sv", "da",
               "no", "nb", "nn", "fi", "is", "id", "ms", "fil", "tl", "af", "sw", "sq")


def _base_lang(track):
    return (track.get("languageCode") or "").lower().replace("_", "-").split("-")[0]


def filter_supported_tracks(tracks):
    ok = [t for t in (tracks or []) if _base_lang(t) in LATIN_LANGS]
    ok.sort(key=lambda t: (0 if _base_lang(t) == "en" else 1, 1 if t.get("kind") == "asr" else 0))
    return ok

_TMP = "/tmp"


def _ytdlp_cmd():
    exe = shutil.which("yt-dlp")
    return [exe] if exe else [sys.executable, "-m", "yt_dlp"]


def _run_ytdlp(args, timeout=45):
    attempts = [[]]
    if os.path.exists("cookies.txt"):
        attempts = [["--cookies", "cookies.txt"], []]
    attempts.append(["--extractor-args", "youtube:player_client=android"])
    last = None
    for extra in attempts:
        try:
            last = subprocess.run(_ytdlp_cmd() + extra + args, capture_output=True,
                                  text=True, encoding="utf-8", errors="replace", timeout=timeout)
        except subprocess.TimeoutExpired:
            caption_log(f"[subtitles] yt-dlp timeout ({' '.join(extra) or 'default'})")
            continue
        except Exception as e:
            caption_log(f"[subtitles] cannot run yt-dlp: {e}")
            return None
        if last.returncode == 0:
            return last
        caption_log(f"[subtitles] yt-dlp failed ({' '.join(extra) or 'default'}): {last.stderr.strip()[-300:]}")
    return None


def _tracks_from_info(info):
    tracks = []
    seen = set()
    for lang, fmts in (info.get("subtitles") or {}).items():
        if lang == "live_chat":
            continue
        name = (fmts[0].get("name") if fmts else None) or lang
        tracks.append({"languageCode": lang, "name": name, "kind": "", "baseUrl": "", "ytdlpLang": lang})
        seen.add(lang)

    auto = info.get("automatic_captions") or {}
    keys = [(k[:-5], k) for k in auto if k.endswith("-orig")]
    if not keys:
        base = (info.get("language") or "").split("-")[0]
        keys = [(k, k) for k in auto if base and k == base]
    if not keys:
        keys = [(k, k) for k in auto if k == "en"]
    for code, key in keys:
        if code in seen:
            continue
        label = ((auto[key] or [{}])[0].get("name") or code)
        tracks.append({"languageCode": code, "name": f"{label} (auto-generated)", "kind": "asr",
                       "baseUrl": "", "ytdlpLang": key})
        seen.add(code)
    return tracks


def run_yt_dlp(video_id):
    cache_key = f"yt_{video_id}"
    if cache_key in subtitle_cache:
        caption_log(f"[subtitles] cached yt-dlp tracks for {video_id}")
        return subtitle_cache[cache_key]

    caption_log(f"[subtitles] running yt-dlp for {video_id}...")
    result = _run_ytdlp(["-J", "--skip-download", "--no-warnings", "--no-playlist",
                         f"https://www.youtube.com/watch?v={video_id}"])
    if not result:
        return None
    try:
        info = json.loads(result.stdout)
    except Exception as e:
        caption_log(f"[subtitles] could not parse yt-dlp output: {e}")
        return None

    tracks = _tracks_from_info(info)
    caption_log(f"[subtitles] yt-dlp found {len(tracks)} track(s) for {video_id}: "
          f"{[t['languageCode'] + ('*' if t['kind'] else '') for t in tracks]}")
    if tracks:
        subtitle_cache[cache_key] = tracks
    return tracks

_ZERO_WIDTH = re.compile('[\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff\u00ad\u180e]')
_ODD_SPACES = re.compile('[\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\t\x0b\x0c]')
_CONTROL = re.compile('[\x00-\x08\x0e-\x1f\x7f-\x9f]')
_ASTRAL = re.compile('[\U00010000-\U0010ffff]')


def clean_caption_text(text):
    text = text.replace('\r', '')
    text = _ZERO_WIDTH.sub('', text)
    text = _ODD_SPACES.sub(' ', text)
    text = _CONTROL.sub('', text)
    text = text.replace('\U0001f3b5', '\u266a').replace('\U0001f3b6', '\u266a')
    text = _ASTRAL.sub('', text)
    lines = [re.sub(r' {2,}', ' ', line).strip() for line in text.split('\n')]
    return '\n'.join(line for line in lines if line)


def dedupe_cues(cues):
    out = []
    seen = set()
    for cue in cues:
        key = (round(cue['start'], 2), cue['text'])
        if key in seen:
            continue
        seen.add(key)
        out.append(cue)
    return out


def describe_nonascii(cues, limit=12):
    counts = {}
    for cue in cues:
        for ch in cue['text']:
            if ord(ch) > 126:
                counts[ch] = counts.get(ch, 0) + 1
    items = sorted(counts.items(), key=lambda kv: -kv[1])[:limit]
    return ", ".join(f"U+{ord(ch):04X} {unicodedata.name(ch, '?')} x{n}" for ch, n in items)


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

            text = clean_caption_text(''.join(text_parts))

            if text:
                cues.append({
                    'text': text,
                    'start': start_ms / 1000.0,
                    'duration': duration_ms / 1000.0
                })
    except json.JSONDecodeError as e:
        caption_log(f"Failed to parse JSON3: {e}")
        return []

    return dedupe_cues(cues)


def fetch_subtitle_file(video_id, lang_code, format_name='json3'):
    try:
        for old in glob.glob(os.path.join(_TMP, glob.escape(video_id) + "*." + format_name)):
            try:
                os.remove(old)
            except OSError:
                pass
        result = _run_ytdlp(["--skip-download", "--no-warnings", "--write-subs", "--write-auto-subs",
                             "--sub-langs", lang_code, "--sub-format", format_name,
                             "-o", os.path.join(_TMP, video_id),
                             f"https://www.youtube.com/watch?v={video_id}"], timeout=60)
        if not result:
            return None
        files = glob.glob(os.path.join(_TMP, glob.escape(video_id) + "*." + format_name))
        if not files:
            caption_log(f"[subtitles] yt-dlp produced no {format_name} file for {video_id} ({lang_code})")
            return None
        with open(files[0], 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        caption_log(f"[subtitles] error fetching subtitle file: {e}")
        return None
