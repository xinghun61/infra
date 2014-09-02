# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb
from google.appengine.ext.ndb import msgprop
from protorpc import messages


from endpoints_proto_datastore.ndb import EndpointsModel


class NumberingType(messages.Enum):
  COMMIT_POSITION = 1
  SVN = 2


class Numbering(EndpointsModel):
  numbering_type = msgprop.EnumProperty(NumberingType)
  numbering_identifier = ndb.StringProperty()
  root_number = ndb.IntegerProperty(default=0)


class Repo(EndpointsModel):
  name = ndb.StringProperty()
  project = ndb.StringProperty()
  canonical_url_template = ndb.StringProperty(
      default='https://%(project)s.googlesource.com/%(name)s/+/%(commit)s')
  numberings = ndb.StructuredProperty(Numbering, repeated=True)
  first_commit = ndb.StringProperty()
  latest_commit = ndb.StringProperty()
  generated = ndb.DateTimeProperty(auto_now_add=True)
  last_scanned = ndb.DateTimeProperty()
