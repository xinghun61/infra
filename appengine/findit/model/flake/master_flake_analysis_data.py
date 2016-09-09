# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64

from google.appengine.ext import ndb

from model.base_build_model import BaseBuildModel


class CheckFlakeAnalysisData(BaseBuildModel):
  """Represents a check flake task's metadata for a complete run."""
  # The UTC timestamp the check flake task was requested.
  created_time = ndb.DateTimeProperty(indexed=True)

  # The UTC timestamp the check flake task came completed.
  completed_time = ndb.DateTimeProperty(indexed=True)

  # A dict containing information about each swarming rerun's results that can
  # be used for metrics, such as number of cache hits, average run time, etc.
  # Example dict:
  # {
  #     task_id_1: {
  #         'request_time': 2016-09-06 (10:21:26.288) UTC
  #         'start_time': 2016-09-06 (10:21:26.288) UTC,
  #         'end_time': 2016-09-06 (10:21:26.288) UTC,
  #         'build_number': 12345,
  #         'cache_hit': True/False,
  #         'number_of_iterations': 100,
  #         'number_of_passes': 90,
  #     },
  #     task_id_2: {
  #         ...
  #     },
  #     ...
  # }
  swarming_rerun_results = ndb.JsonProperty(indexed=False)

  # Error code and message, if any.
  error = ndb.JsonProperty(indexed=False)

  # Integer representing the suspected build number that regressed.
  regression_build_number = ndb.IntegerProperty(indexed=False)

  # Boolean whether or not the suspected regression range/build is correct.
  correct = ndb.BooleanProperty(indexed=False)

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

  @staticmethod
  def _CreateKey(master_name, builder_name, build_number, step_name, test_name,
                 version):
    encoded_test_name = base64.urlsafe_b64encode(test_name)
    key = '%s/%s/%s/%s/%s/%s' % (master_name, builder_name, build_number,
                                 step_name, encoded_test_name, version)
    return ndb.Key('CheckFlakeAnalysisData', key)

  @staticmethod
  def Create(master_name, builder_name, build_number, step_name, test_name,
             version):
    return CheckFlakeAnalysisData(key=CheckFlakeAnalysisData._CreateKey(
        master_name, builder_name, build_number, step_name, test_name, version))

  @staticmethod
  def Get(master_name, builder_name, build_number, step_name, test_name,
          version):
    return CheckFlakeAnalysisData._CreateKey(
        master_name, builder_name, build_number, step_name, test_name,
        version).get()

  @ndb.ComputedProperty
  def step_name(self):
    return self.key.pairs()[0][1].split('/')[3]

  @ndb.ComputedProperty
  def test_name(self):
    return base64.urlsafe_b64decode(self.key.pairs()[0][1].split('/')[4])

  @ndb.ComputedProperty
  def version(self):
    return self.key.pairs()[0][1].split('/')[5]
