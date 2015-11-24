# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
from google.appengine.ext import ndb

from status import build_result

# Represents a parent for BuildRun objects that are for the same patchset and
# builder. i.e. all win_chromium_rel_swarming runs for
# codereview.chromium.org/123456/#ps1
class PatchsetBuilderRuns(ndb.Model):  # pragma: no cover
  @staticmethod
  def getId(issue, patchset, master, builder):
    return str(issue) + '.' + str(patchset) + '.' + master + '.' + builder

  def getURL(self):
    return ('https://codereview.chromium.org/' + str(self.issue) + '/#ps' +
            str(self.patchset))

  issue = ndb.IntegerProperty(required=True)
  patchset = ndb.IntegerProperty(required=True)
  master = ndb.StringProperty(required=True)
  builder = ndb.StringProperty(required=True)


# Represents a single run of a builder.
# a test_suite:test name (i.e. unit_tests:FooTest), a ninja step in case of
# compile flake, etc... This entity groups together all the instances that this
# flake happened. A PatchsetBuilderRuns is always a parent of a BuildRun entity.
class BuildRun(ndb.Model):  # pragma: no cover
  def getURL(self):
    return ('http://build.chromium.org/p/' + self.key.parent().get().master +
            '/builders/' + self.key.parent().get().builder + '/builds/' +
            str(self.buildnumber))

  buildnumber = ndb.IntegerProperty(required=True)
  result = ndb.IntegerProperty(required=True)
  time_finished = ndb.DateTimeProperty(required=True)
  time_started = ndb.DateTimeProperty(default=datetime.datetime.max)

  is_success = ndb.ComputedProperty(
      lambda self: build_result.isResultSuccess(self.result))
  is_failure = ndb.ComputedProperty(
      lambda self: build_result.isResultFailure(self.result))
