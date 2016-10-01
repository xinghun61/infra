# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64

from google.appengine.ext import ndb

from common import time_util
from model import analysis_status
from model.base_analysis import BaseAnalysis
from model.base_build_model import BaseBuildModel
from model.flake.flake_swarming_task import FlakeSwarmingTaskData
from model.versioned_model import VersionedModel


class DataPoint(ndb.Model):
  build_number = ndb.IntegerProperty(indexed=False)
  pass_rate = ndb.FloatProperty(indexed=False)


class MasterFlakeAnalysis(BaseAnalysis, BaseBuildModel, VersionedModel):
  """Represents an analysis of a flaky test in a Chromium Waterfall."""

  @ndb.ComputedProperty
  def step_name(self):
    return self.key.pairs()[0][1].split('/')[3]

  @ndb.ComputedProperty
  def test_name(self):
    return base64.urlsafe_b64decode(self.key.pairs()[0][1].split('/')[4])

  @staticmethod
  def _CreateAnalysisId(
      master_name, builder_name, build_number, step_name, test_name):
    encoded_test_name = base64.urlsafe_b64encode(test_name)
    return '%s/%s/%s/%s/%s' % (
        master_name, builder_name, build_number, step_name, encoded_test_name)

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

  def Reset(self):
    self.created_time = time_util.GetUTCNow()
    self.status = analysis_status.PENDING
    self.completed_time = None
    self.swarming_rerun_results = []
    self.error = None
    self.correct_regression_range = None
    self.correct_culprit = None
    self.algorithm_parameters = None
    self.suspected_flake_build_number = None
    self.data_points = []

  # The UTC timestamp this analysis was requested.
  created_time = ndb.DateTimeProperty(indexed=True)

  # The UTC timestamp this analysis was completed.
  completed_time = ndb.DateTimeProperty(indexed=True)

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
