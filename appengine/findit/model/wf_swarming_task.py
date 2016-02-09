# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from model.base_build_model import BaseBuildModel
from model import wf_analysis_status


class WfSwarmingTask(BaseBuildModel):
  """Represents a swarming task for a failed step.

  'Wf' is short for waterfall.
  """
  # A dict to keep track of running information for each test:
  # number of total runs, number of each status( such as 'SUCCESS' or 'FAILED')
  tests_statuses = ndb.JsonProperty(default={}, indexed=False, compressed=True)

  # The status of the swarming task.
  status = ndb.IntegerProperty(
      default=wf_analysis_status.PENDING, indexed=False)

  # The revision of the failed build.
  build_revision = ndb.StringProperty(indexed=False)

  @staticmethod
  def _CreateKey(
      master_name, builder_name, build_number, step_name):  # pragma: no cover
    build_id = BaseBuildModel.CreateBuildId(
        master_name, builder_name, build_number)
    return ndb.Key('WfBuild', build_id, 'WfSwarmingTask', step_name)

  @staticmethod
  def Create(
      master_name, builder_name, build_number, step_name):  # pragma: no cover
    return WfSwarmingTask(
        key=WfSwarmingTask._CreateKey(
            master_name, builder_name, build_number, step_name))

  @staticmethod
  def Get(
      master_name, builder_name, build_number, step_name):  # pragma: no cover
    return WfSwarmingTask._CreateKey(
        master_name, builder_name, build_number, step_name).get()
