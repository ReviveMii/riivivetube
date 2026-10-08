import re
import html
import requests
import xml.etree.ElementTree as ET

from .client import _fetch_visitor_data
from subtitles import (run_yt_dlp, json3_to_text_list, fetch_subtitle_file, clean_caption_text,
                       dedupe_cues, describe_nonascii, caption_log, filter_supported_tracks)

_PLAYER_URL = "https://www.youtube.com/youtubei/v1/player"
_ANDROID_UA = "com.google.android.youtube/21.26.364 (Linux; U; Android 11) gzip"


def _player_request(video_id, visitor_data):
    payload = {
        "videoId": video_id,
        "context": {
            "client": {
                "clientName": "ANDROID",
                "clientVersion": "21.26.364",
                "androidSdkVersion": 30,
                "userAgent": _ANDROID_UA,
                "osName": "Android",
                "osVersion": "11",
                "hl": "en",
                "gl": "US",
                "visitorData": visitor_data,
            }
        },
        "contentCheckOk": True,
        "racyCheckOk": True,
    }
    headers = {
        "Content-Type": "application/json",
        "User-Agent": _ANDROID_UA,
        "X-Goog-Visitor-Id": visitor_data,
    }
    resp = requests.post(_PLAYER_URL, json=payload, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _innertube_tracks(video_id):
    try:
        visitor_data = _fetch_visitor_data()
        data = _player_request(video_id, visitor_data)
        tracks = (
            data.get("captions", {})
            .get("playerCaptionsTracklistRenderer", {})
            .get("captionTracks", [])
        )
        if not tracks:
            ps = data.get("playabilityStatus", {})
            caption_log(f"[captions] {video_id}: innertube gave no caption tracks "
                  f"(playability={ps.get('status')} {ps.get('reason', '')})")
        result = []
        for t in tracks:
            base_url = t.get("baseUrl", "")
            if not base_url:
                continue
            name = t.get("name", {})
            if "runs" in name and name["runs"]:
                label = name["runs"][0].get("text", "")
            else:
                label = name.get("simpleText", "")
            result.append({
                "languageCode": t.get("languageCode", ""),
                "name": label or t.get("languageCode", ""),
                "kind": t.get("kind", ""),
                "baseUrl": base_url,
            })
        return result
    except Exception as e:
        caption_log(f"[youtubei] Error fetching caption tracks: {e}")
        return []

def get_caption_tracks(video_id):
    raw = _innertube_tracks(video_id)
    if raw:
        tracks = filter_supported_tracks(raw)
        caption_log(f"[captions] {video_id}: {len(raw)} track(s) from innertube, {len(tracks)} usable")
        return tracks
    caption_log(f"[captions] {video_id}: trying yt-dlp fallback")
    tracks = filter_supported_tracks(run_yt_dlp(video_id) or [])
    caption_log(f"[captions] {video_id}: {len(tracks)} usable track(s) from yt-dlp")
    return tracks

def _clean_text(raw):
    text = re.sub(r"<br\s*/?>", "\n", raw)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(html.unescape(text))
    return clean_caption_text(text)


def _fetch_xml_cues(base_url):
    try:
        resp = requests.get(
            base_url,
            headers={"User-Agent": _ANDROID_UA, "X-Goog-Visitor-Id": _fetch_visitor_data()},
            timeout=10,
        )
        resp.raise_for_status()
        body = resp.text
        if not body:
            return []

        cues = []
        root = ET.fromstring(body)
        for el in root.iter():
            if el.tag == "p":
                start = int(el.get("t", "0")) / 1000.0
                dur = int(el.get("d", "0")) / 1000.0
            elif el.tag == "text":
                start = float(el.get("start", "0"))
                dur = float(el.get("dur", "0"))
            else:
                continue
            inner = ET.tostring(el, encoding="unicode", method="xml")
            inner = re.sub(r"^<[^>]+>", "", inner, count=1)
            inner = re.sub(r"</[^>]+>\s*$", "", inner)
            text = _clean_text(inner)
            if text:
                cues.append({
                    "text": text,
                    "start": start,
                    "duration": dur if dur > 0 else 2.5,
                })
        return dedupe_cues(cues)
    except Exception as e:
        caption_log(f"[youtubei] Error fetching caption cues: {e}")
        return []

def fetch_caption_cues(video_id, track):
    cues = []
    if track.get("baseUrl"):
        cues = _fetch_xml_cues(track["baseUrl"])
        if not cues:
            caption_log(f"{video_id}: baseUrl returned no cues, back to yt-dlp")
    if not cues:
        lang = track.get("ytdlpLang") or track["languageCode"]
        content = fetch_subtitle_file(video_id, lang, "json3")
        if content:
            cues = json3_to_text_list(content)
    caption_log(f"[captions] {video_id}: {len(cues)} cue(s) for '{track['languageCode']}'")
    odd = describe_nonascii(cues)
    if odd:
        caption_log(f"[captions] {video_id}: non-ASCII characters in cues: {odd}")
    return cues
