# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from gae_libs.pipeline_wrapper import BasePipeline


class SaveLastAttemptedSwarmingTaskIdPipeline(BasePipeline):

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, urlsafe_analysis_key, last_attempted_task_id,
          last_attempted_build_number):
    """Updates a MasterFlakeAnalysis with the last attempted swarming task.

    Args:
      urlsafe_analysis_key (string): The url-safe key to the MasterFlakeAnalysis
          to update.
      last_attempted_task_id (string): The id of the last-attempted flake
          swarming task.
      last_attempted_build_number (int): The build number corresponding to the
          last-attempted flake swarming task.
    """
    flake_analysis = ndb.Key(urlsafe=urlsafe_analysis_key).get()
    assert flake_analysis

    flake_analysis.last_attempted_build_number = last_attempted_build_number
    flake_analysis.last_attempted_swarming_task_id = last_attempted_task_id
    flake_analysis.put()
