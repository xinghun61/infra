# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from status import build_result

# The presence of this lets us save the progress of fetched data from
# chromium-cq-status.
class FetchStatus(ndb.Model):
  begin = ndb.StringProperty(default='')
  end = ndb.StringProperty(default='')
  cursor = ndb.StringProperty(default='')
  done = ndb.BooleanProperty(required=True)
