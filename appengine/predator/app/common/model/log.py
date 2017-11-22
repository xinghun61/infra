# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a customized logger to log information about Predator analysis.

The logger only logs information that clients are interested in."""

from collections import defaultdict
from collections import namedtuple
import hashlib
import json
import logging

from google.appengine.ext import ndb


class Log(ndb.Model):

  logs = ndb.JsonProperty(indexed=False, default=[])

  @classmethod
  def _CreateKey(cls, identifiers):
    return ndb.Key(cls.__name__, hashlib.sha1(
        json.dumps(identifiers, sort_keys=True)).hexdigest())

  @classmethod
  def Get(cls, identifiers):
    return cls._CreateKey(identifiers).get()

  @classmethod
  def Create(cls, identifiers):
    return cls(key=cls._CreateKey(identifiers))

  def Log(self, name, message, level):
    self.logs.append({'message': message, 'level': level, 'name': name})
    self.put()

  def Reset(self):
    self.logs = []
