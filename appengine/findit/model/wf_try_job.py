# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from model.base_build_model import BaseBuildModel
from model import wf_analysis_status


class WfTryJob(BaseBuildModel):
  """Represents a try job results for a failed build.

  'Wf' is short for waterfall.
  """
  # A list of dict containing results and urls of each try job for compile.
  compile_results = ndb.JsonProperty(default=[], indexed=False, compressed=True)

  # A list of dict containing results and urls of each try job for test.
  test_results = ndb.JsonProperty(default=[], indexed=False, compressed=True)

  # The status of the try job.
  status = ndb.IntegerProperty(
      default=wf_analysis_status.PENDING, indexed=False)

  # A list of try job IDs associated with each try job for collecting metadata.
  try_job_ids = ndb.JsonProperty(default=[], indexed=False, compressed=True)

  @staticmethod
  def _CreateKey(master_name, builder_name, build_number):  # pragma: no cover
    return ndb.Key('WfTryJob',
                   BaseBuildModel.CreateBuildId(
                       master_name, builder_name, build_number))

  @staticmethod
  def Create(master_name, builder_name, build_number):  # pragma: no cover
    return WfTryJob(
        key=WfTryJob._CreateKey(master_name, builder_name, build_number))

  @staticmethod
  def Get(master_name, builder_name, build_number):  # pragma: no cover
    return WfTryJob._CreateKey(
        master_name, builder_name, build_number).get()

  @property
  def completed(self):
    return self.status in (
        wf_analysis_status.ANALYZED, wf_analysis_status.ERROR)

  @property
  def failed(self):
    return self.status == wf_analysis_status.ERROR
