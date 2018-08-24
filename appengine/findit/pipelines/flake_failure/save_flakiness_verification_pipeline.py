# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Saves a DataPoint to a MasterFlakeAnalysis for flakiness verification."""

from google.appengine.ext import ndb

from dto.flakiness import Flakiness
from gae_libs.pipelines import GeneratorPipeline
from libs.structured_object import StructuredObject
from services.flake_failure import data_point_util


class SaveFlakinessVerificationInput(StructuredObject):
  # The urlsafe-key to the analysis to update.
  analysis_urlsafe_key = basestring

  # The flakiness rate with which to create a data point with.
  flakiness = Flakiness


class SaveFlakinessVerificationPipeline(GeneratorPipeline):
  """Updates a MasterFlakeAnalysis' flakiness verification data points."""

  input_type = SaveFlakinessVerificationInput

  def RunImpl(self, parameters):
    analysis = ndb.Key(urlsafe=parameters.analysis_urlsafe_key).get()
    assert analysis, 'Analysis unexpectedly missing!'

    flakiness = parameters.flakiness
    data_point = data_point_util.ConvertFlakinessToDataPoint(flakiness)
    analysis.flakiness_verification_data_points.append(data_point)
    analysis.put()
