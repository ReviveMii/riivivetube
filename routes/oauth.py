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


import requests
from flask import Blueprint, request, Response

bp = Blueprint('oauth', __name__)


@bp.route('/o/oauth2/device/code', methods=['POST'])
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


@bp.route('/o/oauth2/token', methods=['POST'])
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
