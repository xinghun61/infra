# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import calendar
from datetime import datetime
import mock

import webapp2

from handlers import triage_suspected_cl
from libs import time_util
from model import analysis_approach_type
from model import result_status
from model import suspected_cl_status
from model.wf_analysis import WfAnalysis
from model.wf_suspected_cl import WfSuspectedCL
from waterfall import buildbot
from waterfall.test import wf_testcase


class TriageSuspectedClTest(wf_testcase.WaterfallTestCase):
  app_module = webapp2.WSGIApplication([
      ('/triage-suspected-cl', triage_suspected_cl.TriageSuspectedCl),
      ], debug=True)

  def setUp(self):
    super(TriageSuspectedClTest, self).setUp()
    self.master_name = 'm'
    self.builder_name = 'b'
    # self.build_number_incomplete = 120  # Analysis is not completed yet.
    self.build_number_1 = 122
    self.build_number_2 = 123
    self.build_key_1 = '%s/%s/%d' % (
        self.master_name, self.builder_name, self.build_number_1)
    self.build_key_2 = '%s/%s/%d' % (
        self.master_name, self.builder_name, self.build_number_2)

    self.repo_name = 'chromium'
    self.revision_1 = 'r1'
    self.commit_position = 123
    self.suspected_cl_1 = {
        'repo_name': self.repo_name,
        'revision': self.revision_1,
        'commit_position': self.commit_position,
        'url': 'https://codereview.chromium.org/123',
    }

    self.revision_2 = 'r2'
    self.suspected_cl_2 = {
        'repo_name': self.repo_name,
        'revision': self.revision_2,
        'commit_position': 111,
        'url': 'https://codereview.chromium.org/111',
    }

    self.mock_current_user(user_email='test@chromium.org', is_admin=True)

  def testSuccessfulTriage(self):
    build_url = buildbot.CreateBuildUrl(
      self.master_name, self.builder_name, self.build_number_1)
    response = self.test_app.get(
      '/triage-suspected-cl',
      params={
        'url': build_url,
        'status': '0',
        'cl_info': 'chromium/rev1',
        'format': 'json'
      })
    self.assertEquals(200, response.status_int)
    self.assertEquals(
      {
        'success': False
      },
      response.json_body)

  def testUpdateSuspectedCLNonFirstTimeFailure(self):
    suspected_cl = WfSuspectedCL.Create(
        self.repo_name, self.revision_1, self.commit_position)

    suspected_cl.builds = {
        self.build_key_1: {
            'failure_type': 'test',
            'failures': {
                's1': ['t1', 't2']
            },
            'status': None,
            'approaches': [analysis_approach_type.HEURISTIC,
                           analysis_approach_type.TRY_JOB],
            'top_score': None,
            'Confidence': 80.0
        }
    }
    suspected_cl.put()
    self.assertTrue(triage_suspected_cl._UpdateSuspectedCL(
        self.repo_name, self.revision_1, self.build_key_2,None))

  def testUpdateSuspectedCLCorrect(self):
    suspected_cl = WfSuspectedCL.Create(
        self.repo_name, self.revision_1, self.commit_position)

    suspected_cl.builds = {
        self.build_key_1: {
            'failure_type': 'test',
            'failures': {
                's1': ['t1', 't2']
            },
            'status': None,
            'approaches': [analysis_approach_type.HEURISTIC,
                           analysis_approach_type.TRY_JOB],
            'top_score': None,
            'Confidence': 80.0
        }
    }
    suspected_cl.put()

    cl_status = suspected_cl_status.CORRECT
    triage_suspected_cl._UpdateSuspectedCL(
        self.repo_name, self.revision_1, self.build_key_1, cl_status)

    suspected_cl = WfSuspectedCL.Get(self.repo_name, self.revision_1)

    self.assertEqual(
        suspected_cl.builds[self.build_key_1]['status'], cl_status)
    self.assertEqual(suspected_cl.status, cl_status)

  def testUpdateSuspectedCLIncorrect(self):
    suspected_cl = WfSuspectedCL.Create(
      self.repo_name, self.revision_1, self.commit_position)

    suspected_cl.builds = {
      self.build_key_1: {
          'failure_type': 'test',
          'failures': {
              's1': ['t1', 't2']
          },
          'status': None,
          'approaches': [analysis_approach_type.HEURISTIC,
                         analysis_approach_type.TRY_JOB],
          'top_score': None,
          'Confidence': 80.0
      }
    }
    suspected_cl.put()

    cl_status = suspected_cl_status.INCORRECT
    triage_suspected_cl._UpdateSuspectedCL(
        self.repo_name, self.revision_1, self.build_key_1, cl_status)

    suspected_cl = WfSuspectedCL.Get(self.repo_name, self.revision_1)

    self.assertEqual(
        suspected_cl.builds[self.build_key_1]['status'], cl_status)
    self.assertEqual(suspected_cl.status, cl_status)


  def testUpdateSuspectedCLPartially(self):
    suspected_cl = WfSuspectedCL.Create(
        self.repo_name, self.revision_1, self.commit_position)

    suspected_cl.builds = {
      self.build_key_1: {
          'failure_type': 'test',
          'failures': {
              's1': ['t1', 't2']
          },
          'status': None,
          'approaches': [analysis_approach_type.HEURISTIC,
                       analysis_approach_type.TRY_JOB],
          'top_score': None,
          'Confidence': 80.0
      },
      self.build_key_2: {
          'failure_type': 'test',
          'failures': {
              's1': ['t1', 't2']
          },
          'status': None,
          'approaches': [analysis_approach_type.HEURISTIC,
                         analysis_approach_type.TRY_JOB],
          'top_score': None,
          'Confidence': 80.0
      }
    }
    suspected_cl.put()

    triage_suspected_cl._UpdateSuspectedCL(
        self.repo_name, self.revision_1, self.build_key_1,
        suspected_cl_status.CORRECT)

    suspected_cl = WfSuspectedCL.Get(self.repo_name, self.revision_1)

    self.assertEqual(
        suspected_cl.builds[self.build_key_1]['status'],
        suspected_cl_status.CORRECT)
    self.assertEqual(
        suspected_cl.status, suspected_cl_status.PARTIALLY_TRIAGED)

    triage_suspected_cl._UpdateSuspectedCL(
        self.repo_name, self.revision_1, self.build_key_2,
        suspected_cl_status.INCORRECT)

    suspected_cl = WfSuspectedCL.Get(self.repo_name, self.revision_1)

    self.assertEqual(
        suspected_cl.builds[self.build_key_2]['status'],
        suspected_cl_status.INCORRECT)
    self.assertEqual(
        suspected_cl.status, suspected_cl_status.PARTIALLY_CORRECT)

  def testUpdateAnalysisNone(self):
    self.assertFalse(triage_suspected_cl._UpdateAnalysis(
        self.master_name, self.builder_name, self.build_number_1,
        self.repo_name, self.revision_1, None
    ))

  def testUpdateAnalysisPartiallyTriaged(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number_1)

    analysis.suspected_cls = [self.suspected_cl_1, self.suspected_cl_2]
    analysis.result_status = result_status.FOUND_UNTRIAGED
    analysis.put()

    success = triage_suspected_cl._UpdateAnalysis(
      self.master_name, self.builder_name, self.build_number_1,
      self.repo_name, self.revision_1, suspected_cl_status.CORRECT)

    expected_suspected_cls = [
      {
        'repo_name': self.repo_name,
        'revision': self.revision_1,
        'commit_position': self.commit_position,
        'url': 'https://codereview.chromium.org/123',
        'status': suspected_cl_status.CORRECT
      },
      self.suspected_cl_2
    ]

    analysis = WfAnalysis.Get(
        self.master_name, self.builder_name, self.build_number_1)
    self.assertTrue(success)
    self.assertEqual(analysis.result_status, result_status.FOUND_UNTRIAGED)
    self.assertEqual(analysis.suspected_cls, expected_suspected_cls)

  def testUpdateAnalysisAllCorrect(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number_1)

    analysis.suspected_cls = [self.suspected_cl_1, self.suspected_cl_2]
    analysis.result_status = result_status.FOUND_UNTRIAGED
    analysis.put()

    triage_suspected_cl._UpdateAnalysis(
        self.master_name, self.builder_name, self.build_number_1,
        self.repo_name, self.revision_1, suspected_cl_status.CORRECT)

    triage_suspected_cl._UpdateAnalysis(
        self.master_name, self.builder_name, self.build_number_1,
        self.repo_name, self.revision_2, suspected_cl_status.CORRECT)

    analysis = WfAnalysis.Get(
        self.master_name, self.builder_name, self.build_number_1)
    self.assertEqual(analysis.result_status, result_status.FOUND_CORRECT)

  def testUpdateAnalysisAllIncorrect(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number_1)

    analysis.suspected_cls = [self.suspected_cl_1, self.suspected_cl_2]
    analysis.result_status = result_status.FOUND_UNTRIAGED
    analysis.put()

    triage_suspected_cl._UpdateAnalysis(
        self.master_name, self.builder_name, self.build_number_1,
        self.repo_name, self.revision_1, suspected_cl_status.INCORRECT)

    triage_suspected_cl._UpdateAnalysis(
        self.master_name, self.builder_name, self.build_number_1,
        self.repo_name, self.revision_2, suspected_cl_status.INCORRECT)

    analysis = WfAnalysis.Get(
        self.master_name, self.builder_name, self.build_number_1)
    self.assertEqual(analysis.result_status, result_status.FOUND_INCORRECT)

  def testUpdateAnalysisPartiallyCorrect(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number_1)

    analysis.suspected_cls = [self.suspected_cl_1, self.suspected_cl_2]
    analysis.result_status = result_status.FOUND_UNTRIAGED
    analysis.put()

    triage_suspected_cl._UpdateAnalysis(
        self.master_name, self.builder_name, self.build_number_1,
        self.repo_name, self.revision_1, suspected_cl_status.CORRECT)

    triage_suspected_cl._UpdateAnalysis(
        self.master_name, self.builder_name, self.build_number_1,
        self.repo_name, self.revision_2, suspected_cl_status.INCORRECT)

    analysis = WfAnalysis.Get(
        self.master_name, self.builder_name, self.build_number_1)
    self.assertEqual(
        analysis.result_status, result_status.PARTIALLY_CORRECT_FOUND)

  def testAppendTriageHistoryRecordWithHistory(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number_1)
    analysis.version = 'version'
    analysis.triage_history = [{'some_info': True}]
    analysis.put()
    cl_info = '%s/%s' % (self.repo_name, self.revision_1)

    mocked_now = datetime(2017, 05, 01, 10, 10, 10)
    mocked_timestamp = calendar.timegm(mocked_now.timetuple())
    self.MockUTCNow(mocked_now)

    triage_suspected_cl._AppendTriageHistoryRecord(
        self.master_name, self.builder_name, self.build_number_1,
        cl_info, suspected_cl_status.CORRECT, 'test')
    analysis = WfAnalysis.Get(
        self.master_name, self.builder_name, self.build_number_1)

    expected_history = [
        {'some_info': True},
        {
          'triage_timestamp': mocked_timestamp,
          'user_name': 'test',
          'cl_status': suspected_cl_status.CORRECT,
          'version': 'version',
          'triaged_cl': cl_info
        }
    ]
    self.assertEqual(analysis.triage_history, expected_history)
    self.assertFalse(analysis.triage_email_obscured)
    self.assertEqual(mocked_now, analysis.triage_record_last_add)

  @mock.patch.object(time_util, 'GetUTCNowTimestamp')
  def testUpdateSuspectedCLAndAnalysis(self, mock_fn):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number_1)
    analysis.version = 'version'
    analysis.suspected_cls = [
        self.suspected_cl_1
    ]
    analysis.put()

    suspected_cl = WfSuspectedCL.Create(
        self.repo_name, self.revision_1, self.commit_position)
    suspected_cl.builds = {
      self.build_key_1: {
          'failure_type': 'test',
          'failures': {
              's1': ['t1', 't2']
          },
          'status': None,
          'approaches': [analysis_approach_type.HEURISTIC,
                         analysis_approach_type.TRY_JOB],
          'top_score': None,
          'Confidence': 80.0
      }
    }
    suspected_cl.put()

    cl_info = '%s/%s' % (self.repo_name, self.revision_1)

    mocked_timestamp = calendar.timegm(datetime(2016, 7, 1, 00, 00).timetuple())
    mock_fn.return_value = mocked_timestamp

    success = triage_suspected_cl._UpdateSuspectedCLAndAnalysis(
        self.master_name, self.builder_name, self.build_number_1, cl_info,
        suspected_cl_status.CORRECT, 'test')

    self.assertTrue(success)
