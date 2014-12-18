# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import calendar

from google.appengine.ext import ndb

from model.build_analysis_status import BuildAnalysisStatus


class Build(ndb.Model):
  """Represent a build cycle of a builder in a waterfall."""

  @staticmethod
  def CreateKey(master_name, builder_name, build_number):  # pragma: no cover
    return ndb.Key(
        'Master', master_name, 'Builder', builder_name, 'Build', build_number)

  @staticmethod
  def CreateBuild(master_name, builder_name, build_number):  # pragma: no cover
    """Create a Build instance, but not save it to datastore."""
    return Build(key=Build.CreateKey(master_name, builder_name, build_number),
                 master_name=master_name,
                 builder_name=builder_name,
                 build_number=build_number)

  @staticmethod
  def GetBuild(master_name, builder_name, build_number):  # pragma: no cover
    return Build.CreateKey(master_name, builder_name, build_number).get()

  def Reset(self):
    """Reset to the state as if no analysis is run."""
    self.analysis_status = BuildAnalysisStatus.PENDING
    self.analysis_start_time = None
    self.analysis_updated_time = None

  # Information of the build.
  master_name = ndb.StringProperty(indexed=False)
  builder_name = ndb.StringProperty(indexed=False)
  build_number = ndb.IntegerProperty(indexed=False)

  # Information of analysis processing.
  analysis_status = ndb.IntegerProperty(
      default=BuildAnalysisStatus.PENDING, indexed=False)
  analysis_start_time = ndb.DateTimeProperty(indexed=False)
  analysis_updated_time = ndb.DateTimeProperty(indexed=False)
