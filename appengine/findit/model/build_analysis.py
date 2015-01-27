# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from model.base_build_model import BaseBuildModel
from model.build_analysis_status import BuildAnalysisStatus


class BuildAnalysis(BaseBuildModel):
  """Represents an analysis of a build cycle of a builder in a waterfall."""

  @staticmethod
  def CreateKey(master_name, builder_name, build_number):  # pragma: no cover
    return ndb.Key('BuildAnalysis',
                   BaseBuildModel.CreateBuildId(
                       master_name, builder_name, build_number))

  @staticmethod
  def CreateBuildAnalysis(
      master_name, builder_name, build_number):  # pragma: no cover
    return BuildAnalysis(
        key=BuildAnalysis.CreateKey(master_name, builder_name, build_number))

  @staticmethod
  def GetBuildAnalysis(
      master_name, builder_name, build_number):  # pragma: no cover
    return BuildAnalysis.CreateKey(
        master_name, builder_name, build_number).get()

  @property
  def completed(self):
    return self.status in (
        BuildAnalysisStatus.ANALYZED, BuildAnalysisStatus.ERROR)

  @property
  def failed(self):
    return self.status == BuildAnalysisStatus.ERROR

  def Reset(self):  # pragma: no cover
    """Reset to the state as if no analysis is run."""
    self.pipeline_url = None
    self.status = BuildAnalysisStatus.PENDING
    self.start_time = None

  # Information of the analyzed build.
  build_start_time = ndb.DateTimeProperty(indexed=True)

  # Information of analysis processing.
  pipeline_url = ndb.StringProperty(indexed=False)
  status = ndb.IntegerProperty(
      default=BuildAnalysisStatus.PENDING, indexed=False)
  start_time = ndb.DateTimeProperty(indexed=False)
  updated_time = ndb.DateTimeProperty(indexed=False, auto_now=True)
