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
from urllib.parse import urlencode
from flask import Blueprint, send_from_directory, send_file, request, Response, abort

from config import MESSAGES_FOLDER

bp = Blueprint('wiitv', __name__)


@bp.route("/leanbacklite")
@bp.route("/wiitv")
def wiitv():
    get_messages = "action_get_versioned_xlb" in request.args
    get_flashvars = "action_get_flashvars" in request.args
    vendor = request.args.get("vendor","NINTENDO")
    model = request.args.get("model","wii")
    if get_messages:
        locale = request.args.get("hl","en_US")
        messages_path = os.path.join(MESSAGES_FOLDER,f"messages_{locale}.xml")
        fallback_message = os.path.join(MESSAGES_FOLDER,"messages_en_US.xml")
        if not os.path.exists(messages_path):
            return send_file(fallback_message, mimetype="text/xml")
        return send_file(messages_path, mimetype="text/xml")
    if get_flashvars:
        flashvars = {
            "enabled_features": "captions",
            "gdata_url": "http://ytv2.nossl.revivemii.xyz",
            "country": request.args.get("country") or "US",
            "vendor": vendor or "NINTENDO",
            "model": model or "wii",
            "cc_load_policy": "3",
            "captions": "1",
            "base_url": "http://ytv2.nossl.revivemii.xyz",
            "ps": "lbl",
            "el": "leanback",
            "ea": "1",
            "upgrade_notify": "",
            "upgrade_forced": "",
            "upgrade_bg": "http://ytv2.nossl.revivemii.xyz/upgrade_bg"
        }
        return Response(urlencode(flashvars), status=200, headers={"Content-Type": "application/x-www-form-urlencoded"})
    return send_from_directory("assets/swf", "leanbacklite_wii.swf", mimetype='application/x-shockwave-flash')


@bp.get("/upgrade_bg")
def upgrade_bg():
    upgrade_bg_path = os.path.join("assets/img","upgrade_bg.jpg")
    if os.path.exists(upgrade_bg_path):
        return send_file(upgrade_bg_path)
    else:
        return abort(404)


@bp.route("/leanback_ajax")
def leanbackajax():
    return send_from_directory("assets/json", "featured.json", mimetype='application/json')


@bp.route("/set_awesome")
@bp.route('/player_204')
def player():
    return Response(status=204)


@bp.route('/apiplayer-loader')
def loadapi():
    return send_from_directory('assets/swf', 'loader.swf', mimetype='application/x-shockwave-flash')


@bp.route('/videoplayback')
def playback():
    return send_from_directory('assets/swf', 'apiplayer.swf', mimetype='application/x-shockwave-flash')
