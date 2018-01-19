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
