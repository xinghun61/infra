# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from testing_utils import testing

from model.suspected_cl_confidence import ConfidenceInformation
from model.suspected_cl_confidence import SuspectedCLConfidence


class VersionedConfigTest(testing.AppengineTestCase):

  def testConfidenceInformationToDict(self):
    confidence_info = ConfidenceInformation(
        correct=90, total=100, confidence=0.9, score=None)

    expected_dict = {'correct': 90, 'total': 100, 'confidence': 0.9}
    self.assertEqual(expected_dict, confidence_info.ToDict())

  def testCreateNewSuspectedCLConfidenceIfNone(self):
    self.assertIsNotNone(SuspectedCLConfidence.Get())

  def testUpdateSuspectedCLConfidence(self):
    cl_confidence = SuspectedCLConfidence.Get()
    start_date = datetime.datetime(2016, 10, 06, 0, 0, 0)
    end_date = datetime.datetime(2016, 10, 07, 0, 0, 0)
    compile_heuristic = [
        ConfidenceInformation(correct=100, total=100, confidence=1.0, score=5)
    ]
    compile_try_job = ConfidenceInformation(
        correct=99, total=100, confidence=0.99, score=None)
    compile_heuristic_try_job = ConfidenceInformation(
        correct=98, total=100, confidence=0.98, score=None)
    test_heuristic = [
        ConfidenceInformation(correct=97, total=100, confidence=0.97, score=5)
    ]
    test_try_job = ConfidenceInformation(
        correct=96, total=100, confidence=0.96, score=None)
    test_heuristic_try_job = ConfidenceInformation(
        correct=95, total=100, confidence=0.95, score=None)

    cl_confidence.Update(start_date, end_date, compile_heuristic,
                         compile_try_job, compile_heuristic_try_job,
                         test_heuristic, test_try_job, test_heuristic_try_job)
    cl_confidence = SuspectedCLConfidence.Get()

    self.assertEqual(compile_heuristic, cl_confidence.compile_heuristic)
    self.assertEqual(compile_try_job, cl_confidence.compile_try_job)
    self.assertEqual(compile_heuristic_try_job,
                     cl_confidence.compile_heuristic_try_job)
    self.assertEqual(test_heuristic, cl_confidence.test_heuristic)
    self.assertEqual(test_try_job, cl_confidence.test_try_job)
    self.assertEqual(test_heuristic_try_job,
                     cl_confidence.test_heuristic_try_job)
