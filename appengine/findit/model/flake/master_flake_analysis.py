# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64

from google.appengine.ext import ndb

from model.base_build_model import BaseBuildModel
from model.base_analysis import BaseAnalysis
from model.flake.flake_swarming_task import FlakeSwarmingTask


class MasterFlakeAnalysis(BaseAnalysis, BaseBuildModel):
  """Represents an analysis of a flaky test in a Chromium Waterfall."""

  @staticmethod
  def _CreateAnalysisId(master_name, builder_name,
                       build_number, step_name, test_name):
    encoded_test_name = base64.urlsafe_b64encode(test_name)
    return '%s/%s/%s/%s/%s' % (master_name, builder_name,
                               build_number, step_name, encoded_test_name)

  @ndb.ComputedProperty
  def step_name(self):
    return self.key.pairs()[0][1].split('/')[3]

  @ndb.ComputedProperty
  def test_name(self):
    return base64.urlsafe_b64decode(self.key.pairs()[0][1].split('/')[4])

  @staticmethod
  def _CreateKey(master_name, builder_name, build_number,
                 step_name, test_name):  # pragma: no cover
    return ndb.Key('MasterFlakeAnalysis',
                   MasterFlakeAnalysis._CreateAnalysisId(
                       master_name, builder_name, build_number,
                       step_name, test_name))

  @staticmethod
  def Create(master_name, builder_name, build_number,
             step_name, test_name):  # pragma: no cover
    return MasterFlakeAnalysis(
        key=MasterFlakeAnalysis._CreateKey(
            master_name, builder_name, build_number,
            step_name, test_name))

  @staticmethod
  def Get(master_name, builder_name, build_number,
          step_name, test_name):  # pragma: no cover
    return MasterFlakeAnalysis._CreateKey(
        master_name, builder_name, build_number, step_name, test_name).get()

  # List of tested build_numbers and their corresponding success rates.
  # We need to keep these sorted manually.
  build_numbers = ndb.IntegerProperty(indexed=False, repeated=True)
  success_rates = ndb.FloatProperty(indexed=False, repeated=True)
  suspected_flake_build_number = ndb.IntegerProperty()
