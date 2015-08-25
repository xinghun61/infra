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
  JSON_SOURCES = {
    'tryserver.blink': [
      'http://build.chromium.org/p/tryserver.blink/json/builders'
    ],
    'tryserver.chromium.mac': [
      'http://build.chromium.org/p/tryserver.chromium.mac/json/builders'
    ],
    'tryserver.chromium.linux': [
      'http://build.chromium.org/p/tryserver.chromium.linux/json/builders'
    ],
    'tryserver.chromium.win': [
      'http://build.chromium.org/p/tryserver.chromium.win/json/builders'
    ],
    'client.gyp': [
      'http://build.chromium.org/p/client.gyp/json/builders'
    ],
    'client.skia': [
      'http://build.chromium.org/p/client.skia/json/trybots'
    ],
    'client.skia.android': [
      'http://build.chromium.org/p/client.skia.android/json/trybots'
    ],
    'client.skia.compile': [
      'http://build.chromium.org/p/client.skia.compile/json/trybots'
    ],
    'client.skia.fyi': [
      'http://build.chromium.org/p/client.skia.fyi/json/trybots'
    ],
    'tryserver.v8': [
      'http://build.chromium.org/p/tryserver.v8/json/builders'
    ],
    'tryserver.webrtc': [
      'http://build.chromium.org/p/tryserver.webrtc/json/builders'
    ],
    'tryserver.client.mojo': [
      'http://build.chromium.org/p/tryserver.client.mojo/json/builders'
    ],
    'tryserver.infra': [
      'http://build.chromium.org/p/tryserver.infra/json/builders'
    ],
  }

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
      { tryserver: tryserver_name2,
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

    tryserver_json = []
    tryserver_dict = json.loads(cls.get_instance().json_contents)
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


  @classmethod
  def refresh(cls):
    new_json_contents = {}

    for tryserver, json_urls in cls.JSON_SOURCES.iteritems():
      for json_url in json_urls:
        result = urlfetch.fetch(json_url, deadline=60)
        parsed_json = json.loads(result.content)
        for builder in parsed_json:
          # Exclude triggered bots: they are not to be triggered directly but
          # by another bot.
          if 'triggered' in builder:
            continue

          # Skip bisect bots to declutter the UI.
          if 'bisect' in builder:
            continue

          category = parsed_json[builder].get('category', 'None')
          new_json_contents.setdefault(tryserver, {}).setdefault(
              category, []).append(builder)

    instance = cls.get_instance()
    instance.json_contents = json.dumps(new_json_contents)
    instance.put()
