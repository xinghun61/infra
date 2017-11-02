# Copyright 2008 Google Inc.
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

"""App Engine data model (schema) definition for Chromium port of Rietveld."""

import json
import logging
import sys

from google.appengine.api import memcache
from google.appengine.api import urlfetch
from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import ndb

from codereview import buildbucket
from codereview import models


class UrlMap(ndb.Model):
  """Mapping between base url and source code viewer url."""

  base_url_template = ndb.StringProperty(required=True)
  source_code_url_template = ndb.StringProperty(required=True)

  @staticmethod
  def user_can_edit(user):
    return models.is_privileged_user(user)


class Key(ndb.Model):
  """Hash to be able to push data from a server."""
  hash = ndb.StringProperty()


def to_dict(self):
  """Converts an ndb.Model instance into a dict.

  Useful for json serialization.
  """
  def convert(item):
    if isinstance(item, (int, float, None.__class__, bool)):
      return item
    elif isinstance(item, (list, tuple)):
      return [convert(i) for i in item]
    elif isinstance(item, users.User):
      return item.email()
    else:
      return unicode(item)
  result = dict([(p, convert(getattr(self, p)))
                 for p in self._properties]) #pylint: disable=W0212
  try:
    result['key'] = self.key.urlsafe()
  except db.NotSavedError:
    pass
  return result

# Monkey-patch ndb.Model to make it easier to JSON-serialize it.
ndb.Model.to_dict = to_dict


class TryserverBuilders(ndb.Model):
  MASTERS = [
    'client.gyp',
    'client.skia',
    'client.skia.android',
    'client.skia.compile',
    'client.skia.fyi',
    'tryserver.blink',
    'tryserver.chromium.android',
    'tryserver.chromium.mac',
    'tryserver.chromium.linux',
    'tryserver.chromium.win',
    'tryserver.client.mojo',
    'tryserver.client.syzygy',
    'tryserver.libyuv',
    'tryserver.v8',
    'tryserver.webrtc',
  ]

  MEMCACHE_KEY = 'default_builders'
  MEMCACHE_TRYSERVERS_KEY = 'tryservers'
  MEMCACHE_TIME = 3600 * 24

  # Dictionary mapping tryserver names like tryserver.chromium to a list
  # of builders.
  json_contents = ndb.TextProperty(default='{}')

  @classmethod
  def get_instance(cls):
    return cls.get_or_insert('one instance')

  @classmethod
  def get_builders(cls):
    data = memcache.get(cls.MEMCACHE_KEY)
    if data is not None:
      return data

    data = json.loads(cls.get_instance().json_contents)
    memcache.add(cls.MEMCACHE_KEY, data, cls.MEMCACHE_TIME)
    return data

  @classmethod
  def get_curated_tryservers(cls):
    """Returns an array of sorted tryservers to ease client consumption.

    The structure of the array is:
    [
      { tryserver: buildbucket_bucket_name,
        builders: [
          { builder: builder_name1, category: category_name1 },
          { builder: builder_name2, category: category_name2 },
          ...
        ]
      },
      ...
    ]
    """
    tryserver_json = memcache.get(cls.MEMCACHE_TRYSERVERS_KEY)
    if tryserver_json is not None:
      return tryserver_json
    tryserver_dict = json.loads(cls.get_instance().json_contents)
    return cls._prepare_and_cache_curated_tryservers(tryserver_dict)

  @classmethod
  def _prepare_and_cache_curated_tryservers(cls, tryserver_dict):
    tryserver_json = []
    for tryserver in sorted(tryserver_dict):
      categories = tryserver_dict[tryserver]
      builders_arr = []
      for category in sorted(categories):
        builders = categories[category]
        for builder in sorted(builders):
          builders_arr.append({'builder': builder, 'category': category})
      tryserver_json.append({'tryserver': tryserver, 'builders': builders_arr})

    memcache.add(cls.MEMCACHE_TRYSERVERS_KEY, tryserver_json, cls.MEMCACHE_TIME)
    return tryserver_json
