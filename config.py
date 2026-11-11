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

CATEGORIES = {
    "feeds/api/users/trends/favorites", "feeds/api/standardfeeds/US/most_popular_Music", "feeds/api/standardfeeds/US/most_popular_Games", "feeds/api/standardfeeds/US/most_popular_Sports", "feeds/api/standardfeeds/US/most_popular_FilmAnimation", "feeds/api/standardfeeds/US/most_popular_Entertainment", "feeds/api/standardfeeds/US/most_popular_Comedy", "feeds/api/standardfeeds/US/most_popular_NewsPolitics", "feeds/api/standardfeeds/US/most_popular_PeopleBlogs", "feeds/api/standardfeeds/US/most_popular_ScienceTech", "feeds/api/standardfeeds/US/most_popular_HowtoStyle", "feeds/api/standardfeeds/US/most_popular_Education", "feeds/api/standardfeeds/US/most_popular_PetsAnimals", "feeds/api/standardfeeds/US/most_popular_Live",
}
CATEGORY_MAP = {
    "feeds/api/users/trends/favorites": "trending",
    "feeds/api/standardfeeds/US/most_popular_Music": "music",
    "feeds/api/standardfeeds/US/most_popular_Games": "gaming",
    "feeds/api/standardfeeds/US/most_popular_Sports": "sports",
    "feeds/api/standardfeeds/US/most_popular_FilmAnimation": "film_animation",
    "feeds/api/standardfeeds/US/most_popular_Entertainment": "entertainment",
    "feeds/api/standardfeeds/US/most_popular_Comedy": "comedy",
    "feeds/api/standardfeeds/US/most_popular_NewsPolitics": "news_politics",
    "feeds/api/standardfeeds/US/most_popular_PeopleBlogs": "people_blogs",
    "feeds/api/standardfeeds/US/most_popular_ScienceTech": "science_technology",
    "feeds/api/standardfeeds/US/most_popular_HowtoStyle": "howto_style",
    "feeds/api/standardfeeds/US/most_popular_Education": "education",
    "feeds/api/standardfeeds/US/most_popular_PetsAnimals": "pets_animals",
    "feeds/api/standardfeeds/US/most_popular_Live": "live",
}
thumbnail_url_cache = {}
VIDEO_FOLDER = "./cache"
MESSAGES_FOLDER = "./assets/messages"
subtitle_cache = {}

if not os.path.exists(VIDEO_FOLDER):
    os.makedirs(VIDEO_FOLDER)
