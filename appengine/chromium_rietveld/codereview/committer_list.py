# Copyright 2014 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Retrieve list of Chromium committers from the chromium-committers app.
"""

import logging

from google.appengine.api import memcache, urlfetch

from django.conf import settings

from codereview import common


COMMITTER_LIST_FORMAT = 'https://chromium-committers.appspot.com/lists/%s'
COMMITTER_LIST_MEMCACHE_KEY = 'COMMITTER_LIST_MEMCACHE_KEY'
COMMITTER_LIST_EXPIRY_SECONDS = 1800


def Committers():
    committer_list = memcache.get(key=COMMITTER_LIST_MEMCACHE_KEY)
    if not committer_list:
        committer_list = _FetchCommitters()
        memcache.set(COMMITTER_LIST_MEMCACHE_KEY,
                     committer_list,
                     time=COMMITTER_LIST_EXPIRY_SECONDS)
    return committer_list


def _FetchCommitters():
    if not settings.COMMITTER_LIST_NAME:
        return []  # This instance does not use chromium-comitters.
    if common.IS_DEV:
        return ['committer@example.com']

    url = COMMITTER_LIST_FORMAT % (settings.COMMITTER_LIST_NAME,)
    logging.info('Hitting %r', url)
    try:
      result = urlfetch.fetch(
          url, follow_redirects=False, validate_certificate=True)
    except Exception as e:
        logging.exception(e)
        return []
    if result.status_code != 200:
        logging.error('Unable to retrieve committer list from %s.', url)
        return []
    return result.content.split()
