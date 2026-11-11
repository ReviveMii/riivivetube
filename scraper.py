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


from flask import Response

import time
import youtubei
import livestream

class Scraper:
    def generateXML(self, json_data):
        xml_string = '<?xml version=\'1.0\' encoding=\'UTF-8\'?>'
        xml_string += '<feed xmlns:openSearch=\'http://a9.com/-/spec/opensearch/1.1/\' xmlns:media=\'http://search.yahoo.com/mrss/\' xmlns:yt=\'http://www.youtube.com/xml/schemas/2015\'>'
        xml_string += '<title type=\'text\'>Videos</title>'
        xml_string += f'<openSearch:totalResults>{len(json_data)}</openSearch:totalResults>'
        xml_string += '<openSearch:startIndex>1</openSearch:startIndex>'
        xml_string += '<openSearch:itemsPerPage>20</openSearch:itemsPerPage>'

        for item in json_data:
            xml_string += '<entry>'
            xml_string += '<id>http://ytv2.nossl.revivemii.xyz/feeds/api/videos/' + self.escape_xml(item["videoId"]) + '</id>'
            xml_string += '<published>' + self.escape_xml(item.get("publishedText", "")) + '</published>'
            xml_string += '<title type="text">' + self.escape_xml(item.get("title", "")) + '</title>'
            xml_string += '<link rel="http://ytv2.nossl.revivemii.xyz/feeds/api/videos/' + self.escape_xml(item["videoId"]) + '/related"/>'
            xml_string += '<author><name>' + self.escape_xml(item.get("author", "")) + '</name>'
            xml_string += '<uri>http://ytv2.nossl.revivemii.xyz/feeds/api/channels/' + self.escape_xml(item.get("authorId", "")) + '</uri></author>'
            xml_string += '<media:group>'
            xml_string += '<media:thumbnail yt:name="hqdefault" url="http://i.ytimg.com/vi/' + self.escape_xml(item["videoId"]) + '/hqdefault.jpg" height="240" width="320" time="00:00:00"/>'
            if not item.get("liveNow"):
                xml_string += '<yt:duration seconds="' + self.escape_xml(str(item.get("lengthSeconds", 0))) + '"/>'
            xml_string += '<yt:videoid id="' + self.escape_xml(item["videoId"]) + '">' + self.escape_xml(item["videoId"]) + '</yt:videoid>'
            xml_string += '<yt:uploaderId>' + self.escape_xml(item.get("authorId", "")) + '</yt:uploaderId>'
            xml_string += '<media:credit role="uploader" name="' + self.escape_xml(item.get("author", "")) + '">' + self.escape_xml(item.get("author", "")) + '</media:credit>'
            xml_string += '</media:group>'
            xml_string += '<yt:statistics favoriteCount="' + str(item.get("viewCount", 0)) + '" viewCount="' + str(item.get("viewCount", 0)) + '"/>'
            if item.get("liveNow"):
                xml_string += '<yt:hd/>'
            xml_string += '</entry>'

        xml_string += '</feed>'
        return xml_string

    def search(self, query):
        results = youtubei.innertube_search(query)
        return Response(self.generateXML(self._mark_live(results)), mimetype='text/atom+xml')

    @staticmethod
    def _mark_live(results):
        results = results or []
        out = []
        livestream.ensure_starts([r.get("videoId") for r in results if isinstance(r, dict) and r.get("liveNow")])
        for r in results:
            if isinstance(r, dict) and r.get("liveNow"):
                r = dict(r, publishedText=livestream.started_text(r.get("videoId")))
            out.append(r)
        return out

    def trends(self, type_param=None):
        return self.search("YouTube")

    def music(self, type_param=None):
        return self.search("music")

    def gaming(self, type_param=None):
        return self.search("gaming")

    def sports(self, type_param=None):
        return self.search("sports")

    def film_animation(self, type_param=None):
        return self.search("film and animation")

    def entertainment(self, type_param=None):
        return self.search("entertainment")

    def comedy(self, type_param=None):
        return self.search("comedy")

    def news_politics(self, type_param=None):
        return self.search("news")

    def people_blogs(self, type_param=None):
        return self.search("vlog")

    def science_technology(self, type_param=None):
        return self.search("science and technology")

    def howto_style(self, type_param=None):
        return self.search("how to and style")

    def education(self, type_param=None):
        return self.search("education")

    def pets_animals(self, type_param=None):
        return self.search("pets and animals")

    _live_cache = (0, [])

    def live(self, type_param=None):
        import random
        from concurrent.futures import ThreadPoolExecutor
        t, live = Scraper._live_cache
        if not live or time.time() - t > 300:
            def one(q):
                try:
                    return youtubei.innertube_search(q, region="US", params="EgJAAQ==")
                except Exception:
                    return []
            seen, live = set(), []
            with ThreadPoolExecutor(max_workers=6) as ex:
                for res in ex.map(one, ("live", "news live", "gaming live", "music live", "sports live", "live usa")):
                    for r in res:
                        if r.get("liveNow") and r.get("videoId") not in seen:
                            seen.add(r["videoId"])
                            live.append(r)
            random.shuffle(live)
            live = live[:25]
            Scraper._live_cache = (time.time(), live)
        return Response(self.generateXML(self._mark_live(live)), mimetype='text/atom+xml')

    @staticmethod
    def escape_xml(s):
        if s is None:
            return ''
        return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')\
                .replace('"', '&quot;').replace("'", '&apos;')


scrape = Scraper()
