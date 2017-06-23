# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from model.base_build_model import BaseBuildModel
from model.base_try_job import BaseTryJob


class WfTryJob(BaseTryJob, BaseBuildModel):
  """Represents a try job results for a failed build.

  'Wf' is short for waterfall.
  """
  # A list of dict containing results and urls of each try job for compile.
  # For example:
  # [
  #      {
  #           'report': (dict) The 'result' dict of the compile try job,
  #           'url': (str) The url to the try job,
  #           'try_job_id': (str) The try job id,
  #           'culprit': (dict) The culprit info, if identified.
  #      },
  #      ...
  # ]
  compile_results = ndb.JsonProperty(indexed=False, compressed=True)

  # A list of dict containing results and urls of each try job for test.
  # For example:
  # [
  #      {
  #           'report': (dict) The 'result' dict of the test try job,
  #           'url': (str) The url to the try job,
  #           'try_job_id': (str) The try job id,
  #           'culprit': (dict) The culprit info, if identified.
  #      },
  #      ...
  # ]
  test_results = ndb.JsonProperty(indexed=False, compressed=True)

  # TODO(http://crbug.com/676511): Merge compile_results, test_results, and
  # flake_results from FlakeTryJob.py into 1 structure in BaseTryJob.

  # Arguments number differs from overridden method - pylint: disable=W0221
  @staticmethod
  def _CreateKey(master_name, builder_name, build_number):
    return ndb.Key('WfTryJob',
                   BaseBuildModel.CreateBuildId(master_name, builder_name,
                                                build_number))

  @staticmethod
  def Create(master_name, builder_name, build_number):
    try_job = WfTryJob(key=WfTryJob._CreateKey(master_name, builder_name,
                                               build_number))
    try_job.compile_results = try_job.compile_results or []
    try_job.test_results = try_job.test_results or []
    try_job.try_job_ids = try_job.try_job_ids or []
    return try_job

  @staticmethod
  def Get(master_name, builder_name, build_number):
    return WfTryJob._CreateKey(master_name, builder_name, build_number).get()

  @classmethod
  def GetBuildNumber(cls, key):
    return int(key.pairs()[0][1].split('/')[2])

  @ndb.ComputedProperty
  def build_number(self):
    return self.GetBuildNumber(self.key)
