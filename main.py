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


import threading
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, Response
from werkzeug.middleware.proxy_fix import ProxyFix

from extensions import limiter
from routes import register_blueprints
from thumbnails import thumbnail_scheduler
from thumbnails import standby_worker

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
limiter.init_app(app)
executor = ThreadPoolExecutor(max_workers=10)
register_blueprints(app)


@app.errorhandler(429)
def ratelimit_handler(e):
    xml = f'<?xml version="1.0"?><error>Rate limit exceeded. Retry after {e.description}</error>'
    return Response(xml, status=429, mimetype='text/xml')
@app.errorhandler(404)
def notfound_handler(e):
    xml = f'<?xml version="1.0"?><error>404 Not Found. If you see this, you are not a wii >:[</error>'
    return Response(xml, status=404, mimetype='text/xml')

if __name__ == "__main__":
    threading.Thread(target=standby_worker, daemon=True).start()
    app.run(host="0.0.0.0", port=5005)
