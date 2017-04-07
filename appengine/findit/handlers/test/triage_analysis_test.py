# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
from datetime import timedelta

from testing_utils import testing
import webapp2

from handlers import triage_analysis
from libs import analysis_status
from model import result_status
from model.wf_analysis import WfAnalysis
from waterfall import buildbot


class TriageAnalysisTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication([
      ('/triage-analysis', triage_analysis.TriageAnalysis),
  ], debug=True)

  def setUp(self):
    super(TriageAnalysisTest, self).setUp()
    self.master_name = 'm'
    self.builder_name = 'b'
    self.build_number_incomplete = 120  # Analysis is not completed yet.
    self.build_number_found = 122  # Suspected CLs are found for this build.
    self.build_number_not_found = 123  # No suspected CLs found.
    self.suspected_cls = [{
        'repo_name': 'chromium',
        'revision': 'r1',
        'commit_position': 123,
        'url': 'https://codereview.chromium.org/123',
    }]

    self.build_start_time = (datetime.utcnow() - timedelta(3)).replace(
        hour=12, minute=0, second=0, microsecond=0)  # Three days ago, UTC Noon.

    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number_incomplete)
    analysis.status = analysis_status.RUNNING
    analysis.put()

    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number_found)
    analysis.status = analysis_status.COMPLETED
    analysis.suspected_cls = self.suspected_cls
    analysis.build_start_time = self.build_start_time
    analysis.put()

    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number_not_found)
    analysis.status = analysis_status.COMPLETED
    analysis.put()

    self.mock_current_user(user_email='test@chromium.org', is_admin=True)

  def testUpdateAnalysisResultStatusWhenAnalysisIsIncomplete(self):
    success, _ = triage_analysis._UpdateAnalysisResultStatus(
        self.master_name, self.builder_name, self.build_number_incomplete, True)
    self.assertFalse(success)
    analysis = WfAnalysis.Get(
        self.master_name, self.builder_name, self.build_number_found)
    self.assertIsNone(analysis.result_status)

  def testUpdateAnalysisResultStatusWhenFoundAndCorrect(self):
    success = triage_analysis._UpdateAnalysisResultStatus(
        self.master_name, self.builder_name, self.build_number_found, True)
    self.assertTrue(success)
    analysis = WfAnalysis.Get(
        self.master_name, self.builder_name, self.build_number_found)
    self.assertEquals(result_status.FOUND_CORRECT,
                      analysis.result_status)
    self.assertEquals(self.suspected_cls, analysis.culprit_cls)

  def testUpdateAnalysisResultStatusWhenFoundButIncorrect(self):
    success = triage_analysis._UpdateAnalysisResultStatus(
        self.master_name, self.builder_name, self.build_number_found, False)
    self.assertTrue(success)
    analysis = WfAnalysis.Get(
        self.master_name, self.builder_name, self.build_number_found)
    self.assertEquals(result_status.FOUND_INCORRECT,
                      analysis.result_status)
    self.assertIsNone(analysis.culprit_cls)

  def testUpdateAnalysisResultStatusWhenNotFoundAndCorrect(self):
    success = triage_analysis._UpdateAnalysisResultStatus(
        self.master_name, self.builder_name, self.build_number_not_found, True)
    self.assertTrue(success)
    analysis = WfAnalysis.Get(
        self.master_name, self.builder_name, self.build_number_not_found)
    self.assertEquals(result_status.NOT_FOUND_CORRECT,
                      analysis.result_status)
    self.assertIsNone(analysis.culprit_cls)

  def testUpdateAnalysisResultStatusWhenNotFoundButIncorrect(self):
    success = triage_analysis._UpdateAnalysisResultStatus(
        self.master_name, self.builder_name, self.build_number_not_found, False)
    self.assertTrue(success)
    analysis = WfAnalysis.Get(
        self.master_name, self.builder_name, self.build_number_not_found)
    self.assertEquals(result_status.NOT_FOUND_INCORRECT,
                      analysis.result_status)
    self.assertIsNone(analysis.culprit_cls)

  def testUpdateAnalysisResultStatusAlsoRecordTriageHistory(self):
    success = triage_analysis._UpdateAnalysisResultStatus(
        self.master_name, self.builder_name, self.build_number_found, True)
    self.assertTrue(success)
    success = triage_analysis._UpdateAnalysisResultStatus(
        self.master_name, self.builder_name, self.build_number_found, False)
    self.assertTrue(success)
    analysis = WfAnalysis.Get(
        self.master_name, self.builder_name, self.build_number_found)
    self.assertEquals(2, len(analysis.triage_history))
    self.assertEquals(result_status.FOUND_CORRECT,
                      analysis.triage_history[0]['result_status'])
    self.assertEquals(result_status.FOUND_INCORRECT,
                      analysis.triage_history[1]['result_status'])

  def testInvalidBuildUrl(self):
    build_url = 'http://invalid/build/url'
    response = self.test_app.get(
        '/triage-analysis',
        params={
            'url': build_url,
            'correct': True,
            'format': 'json'
        })
    self.assertEquals(200, response.status_int)
    self.assertEquals({'success': False}, response.json_body)

  def testSuccessfulTriage(self):
    build_url = buildbot.CreateBuildUrl(
        self.master_name, self.builder_name, self.build_number_found)
    response = self.test_app.get(
        '/triage-analysis',
        params={
            'url': build_url,
            'correct': True,
            'format': 'json'
        })
    self.assertEquals(200, response.status_int)
    self.assertEquals(
        {
            'success': True,
            'num_duplicate_analyses': 0
        },
        response.json_body)

  def testIncompleteTriage(self):
    build_url = buildbot.CreateBuildUrl(
        self.master_name, self.builder_name, self.build_number_incomplete)
    response = self.test_app.get(
        '/triage-analysis',
        params={
            'url': build_url,
            'correct': True,
            'format': 'json'
        })
    self.assertEquals(200, response.status_int)
    self.assertEquals(
        {
            'success': False,
            'num_duplicate_analyses': 0
        },
        response.json_body)

  def testAnalysesMatch(self):
    analysis_with_empty_failures = WfAnalysis.Create(
        self.master_name, self.builder_name, 200)
    analysis_with_empty_failures.result = {
        'failures': []
    }
    analysis_with_empty_failures.put()

    analysis_with_no_suspected_cls = WfAnalysis.Create(
        self.master_name, self.builder_name, 201)
    analysis_with_no_suspected_cls.result = {
        'failures': [
            {
                'suspected_cls': []
            },
            {
                'suspected_cls': []
            },
        ]
    }
    analysis_with_no_suspected_cls.put()

    analysis_with_suspected_cls_1 = WfAnalysis.Create(
        self.master_name, self.builder_name, 202)
    analysis_with_suspected_cls_1.result = {
        'failures': [
            {
                'step_name': 'step1',
                'suspected_cls': [
                    {
                        'revision': 'rev1',
                    }
                ],
            }
        ]
    }
    analysis_with_suspected_cls_1.put()

    analysis_with_suspected_cls_2 = WfAnalysis.Create(
        self.master_name, self.builder_name, 203)
    analysis_with_suspected_cls_2.result = {
        'failures': [
            {
                'suspected_cls': [],
                'step_name': 'step2'
            },
            {
                'suspected_cls': [
                    {
                        'revision': 'rev2',
                    }
                ],
                'step_name': 'step3'
            }
        ]
    }
    analysis_with_suspected_cls_2.put()

    analysis_with_suspected_cls_3 = WfAnalysis.Create(
        self.master_name, self.builder_name, 204)
    analysis_with_suspected_cls_3.result = {
        'failures': [
            {
                'suspected_cls': [],
                'step_name': 'step2',
            },
            {
                'suspected_cls': [
                    {
                        'revision': 'rev2',
                    },
                    {
                        'revision': 'rev3',
                    },
                    {
                        'revision': 'rev4',
                    }
                ],
                'step_name': 'step3',
            }
        ]
    }
    analysis_with_suspected_cls_3.result_status = result_status.FOUND_UNTRIAGED
    analysis_with_suspected_cls_3.build_start_time = self.build_start_time
    analysis_with_suspected_cls_3.put()

    analysis_with_suspected_cls_4 = WfAnalysis.Create(
        self.master_name, self.builder_name, 205)
    analysis_with_suspected_cls_4.result = {
        'failures': [
            {
                'suspected_cls': [],
                'step_name': 'step2',
            },
            {
                'suspected_cls': [
                    {
                        'revision': 'rev2',
                    },
                    {
                        'revision': 'rev3',
                    },
                    {
                        'revision': 'rev4',
                    }
                ],
                'step_name': 'step3',
            }
        ]
    }
    analysis_with_suspected_cls_4.result_status = result_status.FOUND_UNTRIAGED
    analysis_with_suspected_cls_4.build_start_time = self.build_start_time
    analysis_with_suspected_cls_4.put()

    analysis_with_tests_1 = WfAnalysis.Create(
        self.master_name, self.builder_name, 206)
    analysis_with_tests_1.result = {
        'failures': [
            {
                'tests': [
                    {
                        'test_name': 'super_test_1',
                        'suspected_cls': [
                            {
                                'revision': 'abc'
                            }
                        ]
                    }, {
                        'test_name': 'super_test_2',
                        'suspected_cls': [
                            {
                                'revision': 'def'
                            },
                            {
                                'revision': 'ghi'
                            }
                        ]
                    }
                ],
                'step_name': 'step1',
                'suspected_cls': [
                    {
                        'revision': 'rev1',
                    }
                ],
            }
        ]
    }
    analysis_with_tests_1.put()

    analysis_with_tests_2 = WfAnalysis.Create(
        self.master_name, self.builder_name, 207)
    analysis_with_tests_2.result = {
        'failures': [
            {
                'tests': [
                    {
                        'test_name': 'super_test_3',
                        'suspected_cls': [
                            {
                                'revision': 'ab'
                            },
                            {
                                'revision': 'cd'
                            },
                            {
                                'revision': 'ef'
                            }
                        ]
                    }
                ],
                'step_name': 'step1',
                'suspected_cls': [
                    {
                        'revision': 'rev1',
                    }
                ],
            }
        ]
    }
    analysis_with_tests_2.put()

    # Empty failures list.
    self.assertFalse(triage_analysis._DoAnalysesMatch(
        analysis_with_empty_failures,
        analysis_with_empty_failures))
    # Zero culprit-tuples.
    self.assertFalse(triage_analysis._DoAnalysesMatch(
        analysis_with_no_suspected_cls,
        analysis_with_no_suspected_cls))
    # Zero culprit-tuples and some culprit-tuples.
    self.assertFalse(triage_analysis._DoAnalysesMatch(
        analysis_with_no_suspected_cls,
        analysis_with_suspected_cls_1))
    # Has step-level culprit-tuples, and should detect match.
    self.assertTrue(triage_analysis._DoAnalysesMatch(
        analysis_with_suspected_cls_2,
        analysis_with_suspected_cls_2))
    # Two different step-level culprit-tuples, and should fail to match.
    self.assertFalse(triage_analysis._DoAnalysesMatch(
        analysis_with_suspected_cls_2,
        analysis_with_suspected_cls_3))
    # Has test-level culprit-tuples, and should detect match.
    self.assertTrue(triage_analysis._DoAnalysesMatch(
        analysis_with_tests_1,
        analysis_with_tests_1))
    # Two different test-level culprit-tuples, and should fail to match.
    self.assertFalse(triage_analysis._DoAnalysesMatch(
        analysis_with_tests_1,
        analysis_with_tests_2))

  def _createAnalysis(self, build_number, build_start_time):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, build_number)
    analysis.result = {
        'failures': [
            {
                'suspected_cls': self.suspected_cls,
                'step_name': 'step_4',
            }
        ]
    }
    analysis.result_status = result_status.FOUND_UNTRIAGED
    analysis.build_start_time = build_start_time
    analysis.status = analysis_status.COMPLETED
    analysis.suspected_cls = self.suspected_cls
    analysis.put()
    return analysis

  def testGetDuplicateAnalysesTooEarly(self):
    # Three days ago, UTC Noon.
    original_time = (datetime.utcnow() - timedelta(days=3)).replace(
        hour=12, minute=0, second=0, microsecond=0)
    analysis_original = self._createAnalysis(300, original_time)

    # An earlier time, outside bounds.
    too_early_time = (original_time - timedelta(
        hours=triage_analysis.MATCHING_ANALYSIS_HOURS_AGO_START*2))
    self._createAnalysis(301, too_early_time)

    self.assertEquals(
        len(triage_analysis._GetDuplicateAnalyses(analysis_original)), 0)

  def testGetDuplicateAnalysesEarlier(self):
    # Three days ago, UTC Noon.
    original_time = (datetime.utcnow() - timedelta(days=3)).replace(
        hour=12, minute=0, second=0, microsecond=0)
    analysis_original = self._createAnalysis(302, original_time)

    # An earlier time, within bounds.
    earlier_time = (original_time - timedelta(
        hours=triage_analysis.MATCHING_ANALYSIS_HOURS_AGO_START/2))
    self._createAnalysis(303, earlier_time)

    self.assertEquals(
        len(triage_analysis._GetDuplicateAnalyses(analysis_original)), 1)

  def testGetDuplicateAnalysesLater(self):
    # Three days ago, UTC Noon.
    original_time = (datetime.utcnow() - timedelta(days=3)).replace(
        hour=12, minute=0, second=0, microsecond=0)
    analysis_original = self._createAnalysis(304, original_time)

    # A later time, within bounds.
    later_time = (original_time + timedelta(
        hours=triage_analysis.MATCHING_ANALYSIS_HOURS_AGO_START/2))
    self._createAnalysis(305, later_time)

    self.assertEquals(
        len(triage_analysis._GetDuplicateAnalyses(analysis_original)), 1)

  def testGetDuplicateAnalysesTooLate(self):
    # Three days ago, UTC Noon.
    original_time = (datetime.utcnow() - timedelta(days=3)).replace(
        hour=12, minute=0, second=0, microsecond=0)
    analysis_original = self._createAnalysis(306, original_time)

    # A later time, outside bounds.
    too_late_time = (original_time + timedelta(
        hours=triage_analysis.MATCHING_ANALYSIS_HOURS_AGO_START*2))
    self._createAnalysis(307, too_late_time)

    self.assertEquals(
        len(triage_analysis._GetDuplicateAnalyses(analysis_original)), 0)

  def testGetDuplicateAnalysesPastEndBoundTime(self):
    # Tomorrow, UTC Noon.
    original_time = (datetime.utcnow() + timedelta(days=1)).replace(
        hour=12, minute=0, second=0, microsecond=0)
    analysis_original = self._createAnalysis(308, original_time)

    # Create another analysis at the same time (also tomorrow).
    self._createAnalysis(309, original_time)

    self.assertEquals(
        len(triage_analysis._GetDuplicateAnalyses(analysis_original)), 0)

  def testTriageDuplicateResultsFoundCorrectDuplicate(self):
    # Three days ago, UTC Noon.
    original_time = (datetime.utcnow() - timedelta(days=3)).replace(
        hour=12, minute=0, second=0, microsecond=0)
    analysis_original = self._createAnalysis(310, original_time)

    # Create another analysis a bit later (also three days ago).
    self._createAnalysis(311, original_time + timedelta(minutes=1))

    triage_analysis._TriageAndCountDuplicateResults(analysis_original,
                                                    is_correct=True)

    second_analysis = WfAnalysis.Get(self.master_name, self.builder_name, 311)

    self.assertEquals(result_status.FOUND_CORRECT_DUPLICATE,
                      second_analysis.result_status)

  def testTriageDuplicateResultsFoundIncorrectDuplicate(self):
    # Three days ago, UTC Noon.
    original_time = (datetime.utcnow() - timedelta(days=3)).replace(
        hour=12, minute=0, second=0, microsecond=0)
    analysis_original = self._createAnalysis(312, original_time)

    # Create another analysis a bit later (also three days ago).
    self._createAnalysis(313, original_time + timedelta(minutes=1))

    triage_analysis._TriageAndCountDuplicateResults(analysis_original,
                                                    is_correct=False)

    second_analysis = WfAnalysis.Get(self.master_name, self.builder_name, 313)

    self.assertEquals(result_status.FOUND_INCORRECT_DUPLICATE,
                      second_analysis.result_status)
