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


from . import video, oauth, users, wiitv, feeds, timedtext, static


def register_blueprints(app):
    app.register_blueprint(video.bp)
    app.register_blueprint(oauth.bp)
    app.register_blueprint(users.bp)
    app.register_blueprint(wiitv.bp)
    app.register_blueprint(feeds.bp)
    app.register_blueprint(timedtext.bp)
    app.register_blueprint(static.bp)
