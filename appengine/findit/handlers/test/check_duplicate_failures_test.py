# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import datetime
import json
import webapp2

from testing_utils import testing

from handlers import check_duplicate_failures
from model.wf_analysis import WfAnalysis
from model import wf_analysis_result_status


class CheckDuplicateFailuresTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication(
      [('/check-duplicate-failures',
      check_duplicate_failures.CheckDuplicateFailures),], debug=True)

  def _CreateAnalyses(self, master_name, builder_name, count):
    analyses = []
    for i in range(0, count):
      analysis = WfAnalysis.Create(master_name,  builder_name, i)
      analysis.result = {
          'failures': [
              {
                  'step_name': 'a',
                  'first_failure': 3,
                  'last_pass': None,
                  'suspected_cls': [{
                      'repo_name': 'chromium',
                      'revision': 'r99_1',
                      'commit_position': 123,
                      'url': None,
                      'score': 5,
                      'hints': {
                          'added x/y/f99_1.cc (and it was in log)': 5,
                      }
                  }],
              },
              {
                  'step_name': 'b',
                  'first_failure': 2,
                  'last_pass': None,
                  'suspected_cls': [],
              }
          ]
      }
      analysis.suspected_cls = [{
          'repo_name': 'chromium',
          'revision': 'r99_1',
          'commit_position': 123,
          'url': None
      }]
      analysis.result_status = wf_analysis_result_status.FOUND_UNTRIAGED
      analysis.put()
      analyses.append(analysis)
    return analyses

  def testCheckDuplicateFailuresHandler(self):
    self._CreateAnalyses('m', 'b', 5)
    self.mock_current_user(user_email='test@google.com', is_admin=True)
    response = self.test_app.get('/check-duplicate-failures')
    self.assertEqual(200, response.status_int)

  def testGetFailedStepsForEachCL(self):
    analysis = WfAnalysis.Create('m', 'b', 0)
    analysis.result = {
        'failures': [
            {
                'step_name': 'a',
                'first_failure': 3,
                'last_pass': None,
                'suspected_cls': [{
                    'repo_name': 'chromium',
                    'revision': 'r99_1',
                    'commit_position': 123,
                    'url': None,
                    'score': 5,
                    'hints': {
                        'added x/y/f99_1.cc (and it was in log)': 5,
                    }
                }],
            },
            {
                'step_name': 'b',
                'first_failure': 2,
                'last_pass': None,
                'suspected_cls': [],
            }
        ]
    }

    expected_failed_steps = {
        'chromium,r99_1': ['a']
    }
    failed_steps = check_duplicate_failures._GetFailedStepsForEachCL(analysis)
    self.assertEqual(expected_failed_steps, failed_steps)

  def testGetFailedStepsForEachCLNoFailures(self):
    analysis = WfAnalysis.Create('m', 'b', 0)
    analysis.result = {
        'failures': []
    }
    analysis.result_status = wf_analysis_result_status.FOUND_UNTRIAGED
    analysis.put()
    failed_steps = check_duplicate_failures._GetFailedStepsForEachCL(analysis)

    self.assertEqual({}, failed_steps)

  def testGetFailedStepsForEachCLMultipleFailures(self):
    analysis = WfAnalysis.Create('m', 'b', 0)
    analysis.result = {
        'failures': [
            {
                'step_name': 'a',
                'first_failure': 3,
                'last_pass': None,
                'suspected_cls': [{
                    'repo_name': 'chromium',
                    'revision': 'r99_1',
                    'commit_position': 123,
                    'url': None,
                    'score': 5,
                    'hints': {
                        'added x/y/f99_1.cc (and it was in log)': 5,
                    }
                }],
            },
            {
                'step_name': 'b',
                'first_failure': 2,
                'last_pass': None,
                'suspected_cls': [{
                    'repo_name': 'chromium',
                    'revision': 'r99_1',
                    'commit_position': 123,
                    'url': None,
                    'score': 5,
                    'hints': {
                        'added x/y/f99_1.cc (and it was in log)': 5,
                    }
                }],
            }
        ]
    }

    expected_failed_steps = {
        'chromium,r99_1': ['a', 'b']
    }
    failed_steps = check_duplicate_failures._GetFailedStepsForEachCL(analysis)
    self.assertEqual(expected_failed_steps, failed_steps)

  def testAnalysesForDuplicateFailuresTrue(self):
    analyses = []
    for i in range(0, 2):
      analysis = WfAnalysis.Create('m', 'b', i)
      analysis.result = {
          'failures': [
              {
                  'step_name': 'a',
                  'first_failure': 3,
                  'last_pass': None,
                  'suspected_cls': [{
                      'repo_name': 'chromium',
                      'revision': 'r99_1',
                      'commit_position': 123,
                      'url': None,
                      'score': 5,
                      'hints': {
                          'added x/y/f99_1.cc (and it was in log)': 5,
                      }
                  }],
              },
              {
                  'step_name': 'b',
                  'first_failure': 2,
                  'last_pass': None,
                  'suspected_cls': [],
              }
          ]
      }
      analysis.suspected_cls = [{
          'repo_name': 'chromium',
          'revision': 'r99_1',
          'commit_position': 123,
          'url': None
      }]
      analyses.append(analysis)

    self.assertTrue(check_duplicate_failures._AnalysesForDuplicateFailures(
        analyses[0], analyses[1]))

  def testAnalysesForDuplicateFailuresFalseDifferentSteps(self):
    analysis_one = WfAnalysis.Create('m', 'b', 0)
    analysis_one.result = {
        'failures': [
            {
                'step_name': 'a',
                'first_failure': 3,
                'last_pass': None,
                'suspected_cls': [{
                    'repo_name': 'chromium',
                    'revision': 'r99_1',
                    'commit_position': 123,
                    'url': None,
                    'score': 5,
                    'hints': {
                        'added x/y/f99_1.cc (and it was in log)': 5,
                    }
                }],
            },
            {
                'step_name': 'b',
                'first_failure': 2,
                'last_pass': None,
                'suspected_cls': [{
                    'repo_name': 'chromium',
                    'revision': 'r99_1',
                    'commit_position': 123,
                    'url': None,
                    'score': 5,
                    'hints': {
                        'added x/y/f99_1.cc (and it was in log)': 5,
                    }
                }],
            }
        ]
    }
    analysis_one.suspected_cls = [{
        'repo_name': 'chromium',
        'revision': 'r99_1',
        'commit_position': 123,
        'url': None
    }]

    analysis_two = WfAnalysis.Create('m', 'b', 1)
    analysis_two.result = {
        'failures': [
            {
                'step_name': 'not a',
                'first_failure': 3,
                'last_pass': None,
                'suspected_cls': [{
                    'repo_name': 'chromium',
                    'revision': 'r99_1',
                    'commit_position': 123,
                    'url': None,
                    'score': 5,
                    'hints': {
                        'added x/y/f99_1.cc (and it was in log)': 5,
                    }
                }],
            },
            {
                'step_name': 'b',
                'first_failure': 2,
                'last_pass': None,
                'suspected_cls': [{
                    'repo_name': 'chromium',
                    'revision': 'r99_1',
                    'commit_position': 123,
                    'url': None,
                    'score': 5,
                    'hints': {
                        'added x/y/f99_1.cc (and it was in log)': 5,
                    }
                }],
            }
        ]
    }
    analysis_two.suspected_cls = [{
        'repo_name': 'chromium',
        'revision': 'r99_1',
        'commit_position': 123,
        'url': None
    }]

    self.assertFalse(check_duplicate_failures._AnalysesForDuplicateFailures(
        analysis_one, analysis_two))

  def testAnalysesForDuplicateFailuresFalseDifferentCLs(self):
    analysis_one = WfAnalysis.Create('m', 'b', 0)
    analysis_one.result = {
        'failures': [
            {
                'step_name': 'a',
                'first_failure': 3,
                'last_pass': None,
                'suspected_cls': [{
                    'repo_name': 'chromium',
                    'revision': 'r99_1',
                    'commit_position': 123,
                    'url': None,
                    'score': 5,
                    'hints': {
                        'added x/y/f99_1.cc (and it was in log)': 5,
                    }
                }],
            },
            {
                'step_name': 'b',
                'first_failure': 2,
                'last_pass': None,
                'suspected_cls': [],
            }
        ]
    }
    analysis_one.suspected_cls = [{
        'repo_name': 'chromium',
        'revision': 'r99_1',
        'commit_position': 123,
        'url': None
    }]

    analysis_two = WfAnalysis.Create('m', 'b', 1)
    analysis_two.result = {
        'failures': [
            {
                'step_name': 'a',
                'first_failure': 3,
                'last_pass': None,
                'suspected_cls': [{
                    'repo_name': 'chromium',
                    'revision': 'another revision',
                    'commit_position': 123,
                    'url': None,
                    'score': 5,
                    'hints': {
                        'added x/y/f99_1.cc (and it was in log)': 5,
                    }
                }],
            },
            {
                'step_name': 'b',
                'first_failure': 2,
                'last_pass': None,
                'suspected_cls': [],
            }
        ]
    }
    analysis_two.suspected_cls = [{
        'repo_name': 'chromium',
        'revision': 'another revision',
        'commit_position': 123,
        'url': None
    }]

    self.assertFalse(check_duplicate_failures._AnalysesForDuplicateFailures(
        analysis_one, analysis_two))

  def testModifyStatusIfDuplicateSuccess(self):
    analyses = self._CreateAnalyses('m', 'b', 3)

    analyses[0].result_status = wf_analysis_result_status.FOUND_INCORRECT
    analyses[0].put()
    analyses[2].result_status = wf_analysis_result_status.FOUND_INCORRECT
    analyses[2].put()

    check_duplicate_failures._ModifyStatusIfDuplicate(analyses[1])

    # Use data in datastore rather than in memory.
    analysis_two =  WfAnalysis.Get('m', 'b', 1)
    self.assertEqual(wf_analysis_result_status.FOUND_INCORRECT_DUPLICATE,
                     analysis_two.result_status)

  def testModifyStatusIfDuplicateModifiedMultipleAnalyses(self):
    analyses = self._CreateAnalyses('m', 'b', 4)

    analyses[0].result_status = wf_analysis_result_status.FOUND_CORRECT
    analyses[0].put()
    analyses[3].result_status = wf_analysis_result_status.FOUND_CORRECT
    analyses[3].put()

    check_duplicate_failures._ModifyStatusIfDuplicate(analyses[1])
    for i in range(1, 3):
      analysis = WfAnalysis.Get('m', 'b', i)
      self.assertEqual(wf_analysis_result_status.FOUND_CORRECT_DUPLICATE,
                       analysis.result_status)

  def testModifyStatusIfDuplicateSingleAnalysisResult(self):
    analyses = self._CreateAnalyses('m', 'b', 1)

    check_duplicate_failures._ModifyStatusIfDuplicate(analyses[0])

    analysis = WfAnalysis.Get('m', 'b', 0)
    self.assertEqual(wf_analysis_result_status.FOUND_UNTRIAGED,
                     analysis.result_status)

  def testModifyStatusIfDuplicateCheckForTriagedResult(self):
    analyses = self._CreateAnalyses('m', 'b', 1)

    analyses[0].result_status = wf_analysis_result_status.NOT_FOUND_UNTRIAGED
    check_duplicate_failures._ModifyStatusIfDuplicate(analyses[0])

    analysis = WfAnalysis.Get('m', 'b', 0)
    self.assertEqual(wf_analysis_result_status.NOT_FOUND_UNTRIAGED,
                     analysis.result_status)

  def testModifyStatusIfDuplicateFirstResultUntriaged(self):
    analyses = self._CreateAnalyses('m', 'b', 3)
    check_duplicate_failures._ModifyStatusIfDuplicate(analyses[1])

    analysis_one = WfAnalysis.Get('m', 'b', 1)
    self.assertEqual(wf_analysis_result_status.FOUND_UNTRIAGED,
                     analysis_one.result_status)

  def testModifyStatusIfDuplicateDifferentStatuses(self):
    analyses = self._CreateAnalyses('m', 'b', 4)

    analyses[0].result_status = wf_analysis_result_status.FOUND_CORRECT
    analyses[0].put()
    analyses[3].result_status = wf_analysis_result_status.FOUND_INCORRECT
    analyses[3].put()

    check_duplicate_failures._ModifyStatusIfDuplicate(analyses[1])

    for i in range(1, 3):
      analysis = WfAnalysis.Get('m', 'b', i)
      self.assertEqual(wf_analysis_result_status.FOUND_UNTRIAGED,
                       analysis.result_status)

  def testModifyStatusIfDuplicateOnlyOneTriagedEnd(self):
    analyses = self._CreateAnalyses('m', 'b', 4)

    analyses[0].result_status = wf_analysis_result_status.FOUND_CORRECT
    analyses[0].put()

    check_duplicate_failures._ModifyStatusIfDuplicate(analyses[1])
    for i in range(1, 3):
      analysis = WfAnalysis.Get('m', 'b', i)
      self.assertEqual(wf_analysis_result_status.FOUND_UNTRIAGED,
                       analysis.result_status)

  def testModifyStatusIfDuplicateExtraFlakyFailure(self):
    analyses = self._CreateAnalyses('m', 'b', 5)

    analyses[0].result_status = wf_analysis_result_status.FOUND_CORRECT
    analyses[0].put()
    analyses[4].result_status = wf_analysis_result_status.FOUND_CORRECT
    analyses[4].put()

    flaky_failure = {
        'step_name': 'flaky',
        'first_failure': 2,
        'last_pass': 1,
        'suspected_cls': [],
    }
    analyses[2].result['failures'].append(flaky_failure)
    analyses[2].put()

    check_duplicate_failures._ModifyStatusIfDuplicate(analyses[1])

    for i in range(1, 4):
      analysis = WfAnalysis.Get('m', 'b', i)
      self.assertEqual(wf_analysis_result_status.FOUND_CORRECT_DUPLICATE,
                       analysis.result_status)

  def testModifyStatusIfDuplicateNotContinuousFailures(self):
    analyses = self._CreateAnalyses('m', 'b', 5)

    analyses[0].result_status = wf_analysis_result_status.FOUND_CORRECT
    analyses[0].put()
    analyses[4].result_status = wf_analysis_result_status.FOUND_CORRECT
    analyses[4].put()

    analyses[2].result['failures'][0]['step_name'] = 'not_a'
    analyses[2].put()

    check_duplicate_failures._ModifyStatusIfDuplicate(analyses[1])

    analysis_one = WfAnalysis.Get('m', 'b', 1)
    self.assertEqual(wf_analysis_result_status.FOUND_UNTRIAGED,
                     analysis_one.result_status)

  def testModifyStatusIfDuplicateDifferentStatusInBetween(self):
    analyses = self._CreateAnalyses('m', 'b', 5)

    analyses[0].result_status = wf_analysis_result_status.FOUND_CORRECT
    analyses[0].put()
    analyses[4].result_status = wf_analysis_result_status.FOUND_CORRECT
    analyses[4].put()

    analyses[2].result_status = wf_analysis_result_status.NOT_FOUND_UNTRIAGED
    analyses[2].put()

    check_duplicate_failures._ModifyStatusIfDuplicate(analyses[1])

    analysis_one = WfAnalysis.Get('m', 'b', 1)
    self.assertEqual(wf_analysis_result_status.FOUND_UNTRIAGED,
                     analysis_one.result_status)

  def testModifyStatusIfDuplicateDuplicateStatusInBetween(self):
    analyses = self._CreateAnalyses('m', 'b', 5)

    analyses[0].result_status = wf_analysis_result_status.FOUND_CORRECT
    analyses[0].put()
    analyses[4].result_status = wf_analysis_result_status.FOUND_CORRECT
    analyses[4].put()

    analyses[2].result_status = (
        wf_analysis_result_status.FOUND_CORRECT_DUPLICATE)
    analyses[2].put()

    check_duplicate_failures._ModifyStatusIfDuplicate(analyses[1])

    analysis_one = WfAnalysis.Get('m', 'b', 1)
    analysis_three = WfAnalysis.Get('m', 'b', 3)
    self.assertEqual(wf_analysis_result_status.FOUND_CORRECT_DUPLICATE,
                     analysis_one.result_status)
    self.assertEqual(wf_analysis_result_status.FOUND_CORRECT_DUPLICATE,
                     analysis_three.result_status)

  def testModifyStatusIfDuplicateDifferentCLs(self):
    analyses = self._CreateAnalyses('m', 'b', 5)

    analyses[0].result_status = wf_analysis_result_status.FOUND_CORRECT
    analyses[0].put()
    analyses[4].result_status = wf_analysis_result_status.FOUND_CORRECT
    analyses[4].put()

    analyses[2].result['failures'][0]['suspected_cls'][0]['revision'] = 'rev'
    analyses[2].suspected_cls[0]['revision'] = 'rev'
    analyses[2].put()

    check_duplicate_failures._ModifyStatusIfDuplicate(analyses[1])

    for i in range(1, 4):
      analysis = WfAnalysis.Get('m', 'b', i)
      self.assertEqual(wf_analysis_result_status.FOUND_UNTRIAGED,
                       analysis.result_status)

  def testFetchAndSortUntriagedAnalyses(self):
    self._CreateAnalyses('m3', 'b3', 3)
    self._CreateAnalyses('m2', 'b1', 3)
    self._CreateAnalyses('m1', 'b2', 5)
    expected_results = [
        ('m1', 'b2', 0),
        ('m1', 'b2', 1),
        ('m1', 'b2', 2),
        ('m1', 'b2', 3),
        ('m1', 'b2', 4),
        ('m2', 'b1', 0),
        ('m2', 'b1', 1),
        ('m2', 'b1', 2),
        ('m3', 'b3', 0),
        ('m3', 'b3', 1),
        ('m3', 'b3', 2)
    ]

    analyses = (
        check_duplicate_failures.CheckDuplicateFailures.
        _FetchAndSortUntriagedAnalyses())
    for analysis, expected_result in zip(analyses, expected_results):
      self.assertEqual(expected_result,(
          analysis.master_name, analysis.builder_name, analysis.build_number))
