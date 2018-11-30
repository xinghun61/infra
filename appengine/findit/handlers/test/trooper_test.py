# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

import webapp2

from gae_libs import token
from handlers import trooper
from waterfall import waterfall_config
from waterfall.test import wf_testcase


class TrooperTest(wf_testcase.WaterfallTestCase):
  app_module = webapp2.WSGIApplication([
      ('/trooper', trooper.Trooper),
  ],
                                       debug=True)

  def testTrooperGet(self):
    self.mock_current_user(user_email='test@google.com', is_admin=False)
    response = self.test_app.get('/trooper?format=json')

    expected_response = {
        'is_admin': False,
        'auto_commit_revert_on': True,
        'code_coverage_on': True,
        'xsrf_token': response.json_body.get('xsrf_token'),
    }
    self.assertEqual(200, response.status_int)
    self.assertEqual(expected_response, response.json_body)

  @mock.patch.object(token, 'ValidateAuthToken', return_value=(True, False))
  def testNonAdminCouldTurnOffAutoCommit(self, _):
    self.mock_current_user(user_email='test@google.com', is_admin=False)

    params = {
        'xsrf_token': 'token',
        'auto_commit_revert': 'false',
        'update_reason': 'reason',
    }

    response = self.test_app.post('/trooper?format=json', params=params)
    redirect_url = '/trooper'
    self.assertTrue(response.headers.get('Location', '').endswith(redirect_url))
    self.assertFalse(
        waterfall_config.GetActionSettings().get('auto_commit_revert'))

  @mock.patch.object(token, 'ValidateAuthToken', return_value=(True, False))
  def testNonAdminCouldTurnOffCodeCoverage(self, _):
    self.mock_current_user(user_email='test@google.com', is_admin=False)

    params = {
        'xsrf_token': 'token',
        'code_coverage': 'false',
        'update_reason': 'reason',
    }

    response = self.test_app.post('/trooper?format=json', params=params)
    redirect_url = '/trooper'
    self.assertTrue(response.headers.get('Location', '').endswith(redirect_url))
    self.assertFalse(waterfall_config.GetCodeCoverageSettings().get(
        'serve_presubmit_coverage_data'))

  @mock.patch.object(token, 'ValidateAuthToken', return_value=(True, False))
  def testNonAdminCouldNotTurnOnAutoCommit(self, _):
    self.mock_current_user(user_email='test@google.com', is_admin=False)

    params = {
        'xsrf_token': 'token',
        'auto_commit_revert': 'true',
        'update_reason': 'reason',
        'format': 'json',
    }

    response = self.test_app.post('/trooper', params=params, status=403)
    self.assertEqual('Only admin could turn features on.',
                     response.json_body.get('error_message'))

  @mock.patch.object(token, 'ValidateAuthToken', return_value=(True, False))
  def testNonAdminCouldNotTurnOnCodeCoverage(self, _):
    self.mock_current_user(user_email='test@google.com', is_admin=False)

    params = {
        'xsrf_token': 'token',
        'code_coverage': 'true',
        'update_reason': 'reason',
        'format': 'json',
    }

    response = self.test_app.post('/trooper', params=params, status=403)
    self.assertEqual('Only admin could turn features on.',
                     response.json_body.get('error_message'))

  @mock.patch.object(token, 'ValidateAuthToken', return_value=(True, False))
  def testAdminCouldTurnOnAutoCommit(self, _):
    self.mock_current_user(user_email='test@google.com', is_admin=True)
    self.UpdateUnitTestConfigSettings('action_settings',
                                      {'auto_commit_revert': False})

    params = {
        'xsrf_token': 'token',
        'auto_commit_revert': 'true',
        'update_reason': 'reason',
        'format': 'json',
    }

    response = self.test_app.post('/trooper', params=params, status=302)
    self.assertTrue(response.headers.get('Location', '').endswith('/trooper'))
    self.assertTrue(
        waterfall_config.GetActionSettings().get('auto_commit_revert'))

  @mock.patch.object(token, 'ValidateAuthToken', return_value=(True, False))
  def testAdminCouldTurnOnCodeCoverage(self, _):
    self.mock_current_user(user_email='test@google.com', is_admin=True)
    self.UpdateUnitTestConfigSettings('code_coverage_settings',
                                      {'serve_presubmit_coverage_data': False})

    params = {
        'xsrf_token': 'token',
        'code_coverage': 'true',
        'update_reason': 'reason',
        'format': 'json',
    }

    response = self.test_app.post('/trooper', params=params, status=302)
    self.assertTrue(response.headers.get('Location', '').endswith('/trooper'))
    self.assertTrue(waterfall_config.GetCodeCoverageSettings().get(
        'serve_presubmit_coverage_data'))

  @mock.patch.object(token, 'ValidateAuthToken', return_value=(True, False))
  def testAutoCommitAlreadyTurnedOn(self, _):
    self.mock_current_user(user_email='test@google.com', is_admin=True)
    self.UpdateUnitTestConfigSettings('action_settings',
                                      {'auto_commit_revert': True})

    params = {
        'xsrf_token': 'token',
        'auto_commit_revert': 'true',
        'update_reason': 'reason',
        'format': 'json',
    }

    response = self.test_app.post('/trooper', params=params, status=400)
    self.assertEqual(
        'Failed to update settings. '
        'Please refresh the page and try again.',
        response.json_body.get('error_message'))

  @mock.patch.object(token, 'ValidateAuthToken', return_value=(True, False))
  def testCodeCoverageAlreadyTurnedOn(self, _):
    self.mock_current_user(user_email='test@google.com', is_admin=True)
    self.UpdateUnitTestConfigSettings('code_coverage_settings',
                                      {'serve_presubmit_coverage_data': True})

    params = {
        'xsrf_token': 'token',
        'code_coverage': 'true',
        'update_reason': 'reason',
        'format': 'json',
    }

    response = self.test_app.post('/trooper', params=params, status=400)
    self.assertEqual(
        'Failed to update settings. '
        'Please refresh the page and try again.',
        response.json_body.get('error_message'))

  @mock.patch.object(token, 'ValidateAuthToken', return_value=(True, False))
  def testChangeAutoRevertSettingPostFailedEmptyMessage(self, _):
    self.mock_current_user(user_email='test@google.com', is_admin=False)

    params = {
        'xsrf_token': 'token',
        'auto_commit_revert': 'false',
        'update_reason': '\n',
        'format': 'json',
    }

    response = self.test_app.post('/trooper', params=params, status=400)
    self.assertEqual('Please enter the reason.',
                     response.json_body.get('error_message'))

  @mock.patch.object(token, 'ValidateAuthToken', return_value=(True, False))
  def testCodeCoverageSettingPostFailedEmptyMessage(self, _):
    self.mock_current_user(user_email='test@google.com', is_admin=False)

    params = {
        'xsrf_token': 'token',
        'code_coverage': 'false',
        'update_reason': '\n',
        'format': 'json',
    }

    response = self.test_app.post('/trooper', params=params, status=400)
    self.assertEqual('Please enter the reason.',
                     response.json_body.get('error_message'))
