# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64

from google.appengine.ext import ndb

from gae_libs.model.versioned_model import VersionedModel
from model import result_status
from model import triage_status
from model.base_analysis import BaseAnalysis
from model.base_build_model import BaseBuildModel
from model.base_triaged_model import TriagedModel
from model.flake.flake_culprit import FlakeCulprit
from model.flake.flake_swarming_task import FlakeSwarmingTaskData


class DataPoint(ndb.Model):
  # The build number corresponding to this data point. Only relevant for
  # analysis at the build level.
  build_number = ndb.IntegerProperty(indexed=False)

  # The pass rate of the test when run against this commit.
  pass_rate = ndb.FloatProperty(indexed=False)

  # The ID of the swarming task responsible for generating this data.
  task_id = ndb.StringProperty(indexed=False)

  # The commit position of this data point.
  commit_position = ndb.IntegerProperty(indexed=False)

  # The git hash of this data point.
  git_hash = ndb.StringProperty(indexed=False)

  # The commit position of the build preceding this one. Only relevant if this
  # data point is generated at the build level.
  previous_build_commit_position = ndb.IntegerProperty(indexed=False)

  # The git hash of the data point 1 build before this one. Only relevant if
  # this data point is generated as the result of a flake swarming task.
  previous_build_git_hash = ndb.StringProperty(indexed=False)

  # The list of revisions between this build and the previous build. Only
  # relevant if this data point is generated as the result of a flake swarming
  # task.
  blame_list = ndb.StringProperty(repeated=True)
  try_job_url = ndb.StringProperty(indexed=False)

  # The URL to the try job that generated this data point, if any.
  try_job_url = ndb.StringProperty(indexed=False)

  def GetCommitPosition(self, revision):
    """Gets the commit position of a revision within blame_list.

    Args:
      revision (str): The revision to search for.

    Returns:
      commit_position (int): The calculated commit position of revision.
    """
    assert revision in self.blame_list

    for i in range(0, len(self.blame_list)):  # pragma: no branch
      if revision == self.blame_list[i]:
        return i + self.previous_build_commit_position + 1

  def GetRevisionAtCommitPosition(self, commit_position):
    """Gets the corresponding revision to commit_position.

    Args:
      commit_position (int): The commit position for which to find the
          corresponding revision within self.blame_list.

    Returns:
      revision (str): The git revision corresponding to commit_position.
    """
    length = len(self.blame_list)
    assert (commit_position > self.commit_position - length and
            commit_position <= self.commit_position)
    return self.blame_list[
        length - (self.commit_position - commit_position) - 1]


class MasterFlakeAnalysis(
    BaseAnalysis, BaseBuildModel, VersionedModel, TriagedModel):
  """Represents an analysis of a flaky test on a Waterfall test cycle."""

  @ndb.ComputedProperty
  def step_name(self):
    return self.key.pairs()[0][1].split('/')[3]

  @ndb.ComputedProperty
  def test_name(self):
    return base64.urlsafe_b64decode(self.key.pairs()[0][1].split('/')[4])

  @property
  def error_message(self):
    if not self.error:
      return None
    return self.error.get('message')

  @property
  def iterations_to_rerun(self):
    if not self.algorithm_parameters:
      return -1
    return self.algorithm_parameters.get('iterations_to_rerun')

  @staticmethod
  def _CreateAnalysisId(
      master_name, builder_name, build_number, step_name, test_name):
    encoded_test_name = base64.urlsafe_b64encode(test_name)
    return '%s/%s/%s/%s/%s' % (
        master_name, builder_name, build_number, step_name, encoded_test_name)

  @staticmethod
  def GetBuildConfigurationFromKey(master_flake_analysis_key):
    """Extracts master_name and builder_name from key."""
    if not master_flake_analysis_key:
      return None, None

    components = master_flake_analysis_key.pairs()[0][1].split('/')
    master_name = components[0]
    builder_name = components[1]
    return master_name, builder_name

  # Arguments number differs from overridden method - pylint: disable=W0221
  @classmethod
  def Create(cls, master_name, builder_name, build_number, step_name,
             test_name):  # pragma: no cover.
    return super(MasterFlakeAnalysis, cls).Create(
        MasterFlakeAnalysis._CreateAnalysisId(
            master_name, builder_name, build_number, step_name, test_name))

  # Arguments number differs from overridden method - pylint: disable=W0221
  @classmethod
  def GetVersion(cls, master_name, builder_name, build_number, step_name,
                 test_name, version=None):  # pragma: no cover.
    return super(MasterFlakeAnalysis, cls).GetVersion(
        key=MasterFlakeAnalysis._CreateAnalysisId(
            master_name, builder_name, build_number, step_name, test_name),
        version=version)

  def UpdateTriageResult(self, triage_result, suspect_info, user_name,
                         version_number=None):
    super(MasterFlakeAnalysis, self).UpdateTriageResult(
        triage_result, suspect_info, user_name, version_number=version_number)

    if triage_result == triage_status.TRIAGED_CORRECT:
      self.result_status = result_status.FOUND_CORRECT
    else:
      self.result_status = result_status.FOUND_INCORRECT

  def GetDataPointOfSuspectedBuild(self):
    """Gets the corresponding data point to the suspected flake build."""
    if self.suspected_flake_build_number is not None:
      for data_point in self.data_points:
        if data_point.build_number == self.suspected_flake_build_number:
          return data_point

    return None

  def Reset(self):
    super(MasterFlakeAnalysis, self).Reset()
    self.original_master_name = None
    self.original_builder_name = None
    self.original_build_number = None
    self.original_step_name = None
    self.original_test_name = None
    self.bug_id = None
    self.swarming_rerun_results = []
    self.error = None
    self.correct_regression_range = None
    self.correct_culprit = None
    self.algorithm_parameters = None
    self.suspected_flake_build_number = None
    self.culprit = None
    self.try_job_status = None
    self.data_points = []
    self.result_status = None

  # The original build/step/test in which a flake actually occurred.
  # A CQ trybot step has to be mapped to a Waterfall buildbot step.
  # A gtest suite.PRE_PRE_test has to be normalized to suite.test.
  original_master_name = ndb.StringProperty(indexed=True)
  original_builder_name = ndb.StringProperty(indexed=True)
  original_build_number = ndb.IntegerProperty(indexed=True)
  original_step_name = ndb.StringProperty(indexed=True)
  original_test_name = ndb.StringProperty(indexed=True)

  # The bug id in which this flake is reported.
  bug_id = ndb.IntegerProperty(indexed=True)

  # A list of dicts containing information about each swarming rerun's results
  # that were involved in this analysis. The contents of this list will be used
  # for metrics, such as the number of cache hits this analysis benefited from,
  # the number of swarming tasks that were needed end-to-end to find the
  # regressed build number (if any), etc. See FlakeSwarmingTaskData for exact
  # fields.
  swarming_rerun_results = ndb.LocalStructuredProperty(
      FlakeSwarmingTaskData, repeated=True, compressed=True)

  # Error code and message, if any.
  error = ndb.JsonProperty(indexed=False)

  # Boolean whether the suspected regression range/build number is correct.
  correct_regression_range = ndb.BooleanProperty(indexed=True)

  # Boolean whether the suspected CL for found in the regression range
  # is correct.
  correct_culprit = ndb.BooleanProperty(indexed=True)

  # The look back algorithm parameters that were used, as specified in Findit's
  # configuration. For example,
  # {
  #     'iterations_to_rerun': 100,
  #     'lower_flake_threshold': 0.02,
  #     'max_build_numbers_to_look_back': 500,
  #     'max_flake_in_a_row': 4,
  #     'max_stable_in_a_row': 4,
  #     'upper_flake_threshold': 0.98
  # }
  algorithm_parameters = ndb.JsonProperty(indexed=False)

  # The suspected build number to have introduced the flakiness.
  suspected_flake_build_number = ndb.IntegerProperty()

  # The culprit CL associated with the try job results, if any.
  culprit = ndb.LocalStructuredProperty(FlakeCulprit)

  # The status of try jobs, if any. None if try jobs have not been triggered.
  # Status should be PENDING or STARTED when the first try job is triggered,
  # and COMPLETED when the last one finishes. If any try job ends in error,
  # status will be ERROR.
  try_job_status = ndb.IntegerProperty(indexed=False)

  # The data points used to plot the flakiness graph build over build.
  data_points = ndb.LocalStructuredProperty(
      DataPoint, repeated=True, compressed=True)

  # Whether the analysis was triggered by a manual request through check flake,
  # Findit's automatic analysis upon detection, or Findit API.
  triggering_source = ndb.IntegerProperty(default=None, indexed=True)

  # Who triggered the analysis. Used for differentiating between manual and
  # automatic runs, and determining the most active users to gather feedback.
  triggering_user_email = ndb.StringProperty(default=None, indexed=False)

  # Overall conclusion of analysis result for the flake. Found untriaged, Found
  # Correct, etc. used to filter what is displayed on the check flake dashboard.
  result_status = ndb.IntegerProperty(indexed=True)
