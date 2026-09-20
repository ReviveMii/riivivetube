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
from flask import Blueprint, send_file, abort

bp = Blueprint('static_files', __name__)


@bp.route("/cookies.txt")
def cookiestxt():
    abort(404)


@bp.route("/webhook.txt")
def webhooktxt():
    abort(404)


@bp.route("/<path:filename>")
def serve_video(filename):
    file_path = os.path.join(filename)
    if not os.path.exists(file_path):
        abort(404)
    return send_file(file_path)
