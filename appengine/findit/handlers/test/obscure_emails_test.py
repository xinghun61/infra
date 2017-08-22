# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime

import webapp2
import webtest

from handlers import obscure_emails
from libs import time_util
from model.base_triaged_model import TriageResult
from model.flake.master_flake_analysis import MasterFlakeAnalysis
from model.flake.flake_analysis_request import FlakeAnalysisRequest
from model.wf_analysis import WfAnalysis
from waterfall.test import wf_testcase


class ObscureEmailsTest(wf_testcase.WaterfallTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/obscure-emails', obscure_emails.ObscureEmails),
      ], debug=True)

  def testObscureTriageRecordsInWfAnalysis(self):
    mocked_utcnow = datetime(2017, 05, 05, 22, 50, 10)
    self.MockUTCNow(mocked_utcnow)
    valid_record_time = obscure_emails._TimeBeforeNow(
        days=obscure_emails._TRIAGE_RECORD_RENTENSION_DAYS - 10)
    invalid_record_time = obscure_emails._TimeBeforeNow(
        days=obscure_emails._TRIAGE_RECORD_RENTENSION_DAYS + 10)

    old_analysis = WfAnalysis.Create('m', 'b', 1)
    old_analysis.triage_history = [{
        'user_name': 'test1@google.com',
    }]
    old_analysis.triage_email_obscured = False
    old_analysis.triage_record_last_add = invalid_record_time
    old_analysis.put()

    recent_analysis = WfAnalysis.Create('m', 'b', 100000)
    recent_analysis.triage_history = [{
        'user_name': 'test2@google.com',
    }]
    recent_analysis.triage_email_obscured = False
    recent_analysis.triage_record_last_add = valid_record_time
    recent_analysis.put()

    response = self.test_app.get(
        '/obscure-emails',
        params={'format': 'json'},
        headers={'X-AppEngine-Cron': 'true'},
    )
    expected_response = {
        'failure_triage_count': 1,
        'flake_triage_count': 0,
        'flake_request_aggregated_count': 0,
        'flake_request_count': 0,
    }
    self.assertEqual(expected_response, response.json_body)

    old_analysis = WfAnalysis.Get('m', 'b', 1)
    self.assertEqual('xxxxx@google.com',
                     old_analysis.triage_history[0]['user_name'])
    self.assertTrue(old_analysis.triage_email_obscured)

    recent_analysis = WfAnalysis.Get('m', 'b', 100000)
    self.assertEqual('test2@google.com',
                     recent_analysis.triage_history[0]['user_name'])
    self.assertFalse(recent_analysis.triage_email_obscured)

  def testObscureMasterFlakeAnalysis(self):
    mocked_utcnow = datetime(2017, 05, 05, 22, 50, 10)
    self.MockUTCNow(mocked_utcnow)
    valid_record_time = obscure_emails._TimeBeforeNow(days=1)
    valid_request_time = obscure_emails._TimeBeforeNow(days=5)
    invalid_record_time = obscure_emails._TimeBeforeNow(
        days=obscure_emails._TRIAGE_RECORD_RENTENSION_DAYS + 10)
    invalid_request_time = obscure_emails._TimeBeforeNow(
        days=obscure_emails._REQUEST_RECORD_RENTENSION_DAYS + 10)

    old_analysis = MasterFlakeAnalysis.Create('m', 'b', 1, 's', 't')
    old_analysis.triage_history.append(
        TriageResult(user_name='test1@google.com'))
    old_analysis.triage_email_obscured = False
    old_analysis.triage_record_last_add = invalid_record_time
    old_analysis.triggering_user_email = 'test1@google.com'
    old_analysis.triggering_user_email_obscured = False
    old_analysis.request_time = invalid_request_time
    old_analysis.Save()

    recent_analysis = MasterFlakeAnalysis.Create('m', 'b', 1000, 's', 't')
    recent_analysis.triage_history.append(
        TriageResult(user_name='test2@google.com'))
    recent_analysis.triage_email_obscured = False
    recent_analysis.triage_record_last_add = valid_record_time
    recent_analysis.triggering_user_email = 'test2@google.com'
    recent_analysis.triggering_user_email_obscured = False
    recent_analysis.request_time = valid_request_time
    recent_analysis.Save()

    response = self.test_app.get(
        '/obscure-emails',
        params={'format': 'json'},
        headers={'X-AppEngine-Cron': 'true'},
    )
    expected_response = {
        'failure_triage_count': 0,
        'flake_triage_count': 1,
        'flake_request_aggregated_count': 0,
        'flake_request_count': 1,
    }
    self.assertEqual(expected_response, response.json_body)

    old_analysis = MasterFlakeAnalysis.GetVersion('m', 'b', 1, 's', 't')
    self.assertEqual('xxxxx@google.com',
                     old_analysis.triage_history[0].user_name)
    self.assertTrue(old_analysis.triage_email_obscured)
    self.assertEqual('xxxxx@google.com', old_analysis.triggering_user_email)
    self.assertTrue(old_analysis.triggering_user_email_obscured)

    recent_analysis = MasterFlakeAnalysis.GetVersion('m', 'b', 1000, 's', 't')
    self.assertEqual('test2@google.com',
                     recent_analysis.triage_history[0].user_name)
    self.assertFalse(recent_analysis.triage_email_obscured)
    self.assertEqual('test2@google.com', recent_analysis.triggering_user_email)
    self.assertFalse(recent_analysis.triggering_user_email_obscured)

  def testObscureFlakeAnalysisRequest(self):
    mocked_utcnow = datetime(2017, 05, 05, 22, 50, 10)
    self.MockUTCNow(mocked_utcnow)
    valid_request_time = obscure_emails._TimeBeforeNow(days=5)
    invalid_request_time = obscure_emails._TimeBeforeNow(
        days=obscure_emails._REQUEST_RECORD_RENTENSION_DAYS + 10)

    old_request = FlakeAnalysisRequest.Create('flake1', False, 123)
    old_request.user_emails.append('test1@google.com')
    old_request.user_emails_obscured = False
    old_request.user_emails_last_edit = invalid_request_time
    old_request.Save()

    recent_request = FlakeAnalysisRequest.Create('flake2', False, 321)
    recent_request.user_emails.append('test2@google.com')
    recent_request.user_emails_obscured = False
    recent_request.user_emails_last_edit = valid_request_time
    recent_request.Save()

    response = self.test_app.get(
        '/obscure-emails',
        params={'format': 'json'},
        headers={'X-AppEngine-Cron': 'true'},
    )
    expected_response = {
        'failure_triage_count': 0,
        'flake_triage_count': 0,
        'flake_request_aggregated_count': 1,
        'flake_request_count': 0,
    }
    self.assertEqual(expected_response, response.json_body)

    old_request = FlakeAnalysisRequest.GetVersion(key='flake1', version=1)
    self.assertTrue(old_request.user_emails_obscured)
    self.assertEqual(['xxxxx@google.com'], old_request.user_emails)

    recent_request = FlakeAnalysisRequest.GetVersion(key='flake2', version=1)
    self.assertFalse(recent_request.user_emails_obscured)
    self.assertEqual(['test2@google.com'], recent_request.user_emails)
