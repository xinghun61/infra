# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from gae_libs.model.versioned_model import VersionedModel
from libs.time_util import GetUTCNow


class ConfidenceInformation(ndb.Model):
  correct = ndb.IntegerProperty()
  total = ndb.IntegerProperty()
  confidence = ndb.FloatProperty()

  # score is specific for confidence of heuristic results.
  score = ndb.IntegerProperty(default=None)

  def ToDict(self):
    dict_format = {
        'correct': self.correct,
        'total': self.total,
        'confidence': self.confidence
    }
    return dict_format


class SuspectedCLConfidence(VersionedModel):
  """Stores confidence data of different types of suspected CLs.

  Confidence data includes confidence scores and the numbers we used to get
  those scores.

  The types of suspected CLs are:
  1. CLs for compile failures found by Heuristic approach.
      a. The score has been further refined by the top score of hints.
  2. CLs for compile failures found by Try Job approach.
  3. CLs for compile failures found by both approaches.
  4. CLs for test failures found by Heuristic approach.
      a. The score has been further refined by the top score of hints.
  5. CLs for test failures found by Try Job approach.
  6. CLs for test failures found by both approaches.
  """

  # Start date of querying suspected CLs.
  # Note: the start date will be 6 months before end date.
  start_date = ndb.DateTimeProperty(indexed=False)

  # End date of querying suspected CLs.
  end_date = ndb.DateTimeProperty(indexed=True)

  # Time when the instance is updated.
  updated_time = ndb.DateTimeProperty(indexed=True)

  # Confidence scores for CLs for compile failures found by Heuristic approach.
  compile_heuristic = ndb.LocalStructuredProperty(
      ConfidenceInformation, repeated=True)

  # Confidence score for CLs for compile failures found by Try Job approach.
  compile_try_job = ndb.LocalStructuredProperty(ConfidenceInformation)

  # Confidence score for CLs for compile failures found by both approaches.
  compile_heuristic_try_job = ndb.LocalStructuredProperty(ConfidenceInformation)

  # Confidence scores for CLs for test failures found by Heuristic approach.
  test_heuristic = ndb.LocalStructuredProperty(
      ConfidenceInformation, repeated=True)

  # Confidence score for CLs for test failures found by Try Job approach.
  test_try_job = ndb.LocalStructuredProperty(ConfidenceInformation)

  # Confidence score for CLs for test failures found by both approaches.
  test_heuristic_try_job = ndb.LocalStructuredProperty(ConfidenceInformation)

  @classmethod
  def Get(cls, version=None):
    confidences = cls.GetVersion(version=version)
    return (confidences or SuspectedCLConfidence.Create()
            if version is None else confidences)

  def Update(self, start_date, end_date, compile_heuristic, compile_try_job,
             compile_heuristic_try_job, test_heuristic, test_try_job,
             test_heuristic_try_job):

    self.start_date = start_date
    self.end_date = end_date
    self.updated_time = GetUTCNow()
    self.compile_heuristic = compile_heuristic
    self.compile_try_job = compile_try_job
    self.compile_heuristic_try_job = compile_heuristic_try_job
    self.test_heuristic = test_heuristic
    self.test_try_job = test_try_job
    self.test_heuristic_try_job = test_heuristic_try_job

    self.Save()
