# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import datetime
import mock

import webapp2

from common.waterfall import failure_type
from handlers import calculate_confidence_scores
from libs import time_util
from model import analysis_approach_type
from model import suspected_cl_status
from model.suspected_cl_confidence import ConfidenceInformation
from model.wf_suspected_cl import WfSuspectedCL
from waterfall.test import wf_testcase

APPROACH_MAP = {
    0: [analysis_approach_type.HEURISTIC],
    1: [analysis_approach_type.TRY_JOB],
    2: [analysis_approach_type.HEURISTIC, analysis_approach_type.TRY_JOB]
}

HEURISTIC_RESULTS = {
    failure_type.COMPILE: {
        1: {
            suspected_cl_status.INCORRECT: 1
        },
        2: {
            suspected_cl_status.CORRECT: 2
        }
    },
    failure_type.TEST: {
        3: {
            suspected_cl_status.INCORRECT: 1
        },
        4: {
            suspected_cl_status.CORRECT: 1
        },
        5: {
            suspected_cl_status.CORRECT: 2
        }
    }
}

TRY_JOB_RESULTS = {
    failure_type.COMPILE: {
        suspected_cl_status.CORRECT: 3
    },
    failure_type.TEST: {
        suspected_cl_status.CORRECT: 2,
        suspected_cl_status.INCORRECT: 1
    }
}

BOTH_RESULTS = {
    failure_type.COMPILE: {
        suspected_cl_status.CORRECT: 1
    },
    failure_type.TEST: {
        suspected_cl_status.CORRECT: 1,
        suspected_cl_status.INCORRECT: 1
    }
}

EXPECTED_CONFIDENCE = [
    ConfidenceInformation(correct=0, total=1, confidence=0, score=1),
    ConfidenceInformation(correct=2, total=2, confidence=1, score=2)
]


class CalculateConfidenceScoresTest(wf_testcase.WaterfallTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/calculate-confidence-scores',
           calculate_confidence_scores.CalculateConfidenceScores),
      ],
      debug=True)

  def setUp(self):
    super(CalculateConfidenceScoresTest, self).setUp()
    self.start_date = datetime.datetime(2016, 11, 11, 0, 0, 0)
    self.end_date = datetime.datetime(2016, 11, 12, 0, 0, 0)
    self._AddDummyCLs()

  def _AddCL(self, index):
    # Uses index as revision and build number.
    cl = WfSuspectedCL.Create('chromium', str(index), None)
    cl.approaches = APPROACH_MAP[index % 3]
    cl.status = (suspected_cl_status.CORRECT
                 if index % 5 else suspected_cl_status.INCORRECT)
    build_key = 'm/b/%d' % index
    cl.builds = {
        build_key: {
            'failure_type':
                failure_type.COMPILE if index < 5 else failure_type.TEST,
            'approaches':
                APPROACH_MAP[index % 3],
            'top_score':
                index / 2 + 1,
            'failures': ['Test%d' % index],
            'status': (suspected_cl_status.CORRECT
                       if index % 5 else suspected_cl_status.INCORRECT)
        }
    }
    cl.updated_time = self.start_date + datetime.timedelta(hours=index)
    cl.put()
    return cl

  def _AddDummyCLs(self):
    suspected_cls = []

    for i in xrange(0, 10):
      cl = self._AddCL(i)
      suspected_cls.append(cl)

    # Adds a cl with no builds.
    cl10 = WfSuspectedCL.Create('chromium', '10', None)
    cl10.approaches = APPROACH_MAP[2]
    cl10.status = suspected_cl_status.CORRECT
    cl10.updated_time = self.start_date + datetime.timedelta(hours=10)
    cl10.put()
    suspected_cls.append(cl10)

    # Adds a build with the same failure for a heuristic result.
    new_value = copy.deepcopy(suspected_cls[3].builds['m/b/3'])
    suspected_cls[3].builds['new_key'] = new_value
    suspected_cls[3].put()

    # Adds a build with the same failure for a try job result.
    new_value = copy.deepcopy(suspected_cls[4].builds['m/b/4'])
    suspected_cls[4].builds['new_key'] = new_value
    suspected_cls[4].put()

    return suspected_cls

  def testGetCLDataForHeuristic(self):
    result = calculate_confidence_scores._GetCLDataForHeuristic(
        self.start_date, self.end_date)
    self.assertEqual(HEURISTIC_RESULTS, result)

  def testGetCLDataForTryJob(self):
    try_job_result, both_result = (
        calculate_confidence_scores._GetCLDataForTryJob(self.start_date,
                                                        self.end_date))
    self.assertEqual(TRY_JOB_RESULTS, try_job_result)
    self.assertEqual(BOTH_RESULTS, both_result)

  def testCalculateConfidenceLevelsForHeuristic(self):
    result = calculate_confidence_scores._CalculateConfidenceLevelsForHeuristic(
        HEURISTIC_RESULTS[failure_type.COMPILE])
    self.assertEqual(EXPECTED_CONFIDENCE, result)

  @mock.patch.object(time_util, 'GetUTCNow')
  @mock.patch.object(calculate_confidence_scores, '_GetCLDataForHeuristic')
  @mock.patch.object(calculate_confidence_scores, '_GetCLDataForTryJob')
  def testSavesNewCLConfidence(self, mock_fn_t, mock_fn_h, mock_fn):
    mock_fn_t.return_value = (TRY_JOB_RESULTS, BOTH_RESULTS)
    mock_fn_h.return_value = HEURISTIC_RESULTS
    mock_fn.return_value = self.end_date

    confidence_object = calculate_confidence_scores._SavesNewCLConfidence()
    self.assertEqual(EXPECTED_CONFIDENCE, confidence_object.compile_heuristic)

  @mock.patch.object(calculate_confidence_scores, '_SavesNewCLConfidence')
  def testGet(self, mock_fn):
    mock_fn.return_value = None

    response = self.test_app.get('/calculate-confidence-scores',
                                 headers={'X-AppEngine-Cron': 'true'})
    self.assertEqual(200, response.status_int)
    mock_fn.assert_called_once_with()
