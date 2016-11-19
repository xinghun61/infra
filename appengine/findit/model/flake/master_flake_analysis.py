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
from model.flake.flake_swarming_task import FlakeSwarmingTaskData


class DataPoint(ndb.Model):
  build_number = ndb.IntegerProperty(indexed=False)
  pass_rate = ndb.FloatProperty(indexed=False)


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
