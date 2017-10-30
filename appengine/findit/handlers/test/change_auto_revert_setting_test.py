# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import re

import webapp2
import webtest

from gae_libs import token
from handlers import change_auto_revert_setting
from waterfall import waterfall_config
from waterfall.test import wf_testcase


class ChangeAutoRevertSettingTest(wf_testcase.WaterfallTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/change-auto-revert-setting',
           change_auto_revert_setting.ChangeAutoRevertSetting),
      ],
      debug=True)

  def testChangeAutoRevertSettingGet(self):
    self.mock_current_user(user_email='test@google.com', is_admin=False)
    response = self.test_app.get('/change-auto-revert-setting?format=json')

    expected_response = {
        'is_admin': False,
        'auto_commit_revert_compile_on': True,
        'xsrf_token': response.json_body.get('xsrf_token'),
    }
    self.assertEqual(200, response.status_int)
    self.assertEqual(expected_response, response.json_body)

  @mock.patch.object(token, 'ValidateAuthToken', return_value=(True, False))
  def testNonAdminCouldTurnOffAutoCommit(self, _):
    self.mock_current_user(user_email='test@google.com', is_admin=False)

    params = {
        'xsrf_token': 'token',
        'auto_commit_revert_compile': 'false',
        'update_reason': 'reason',
    }

    response = self.test_app.post(
        '/change-auto-revert-setting?format=json', params=params)
    redirect_url = '/waterfall/change-auto-revert-setting'
    self.assertTrue(response.headers.get('Location', '').endswith(redirect_url))
    self.assertFalse(
        waterfall_config.GetActionSettings().get('auto_commit_revert_compile'))

  @mock.patch.object(token, 'ValidateAuthToken', return_value=(True, False))
  def testNonAdminCouldNotTurnOnAutoCommit(self, _):
    self.mock_current_user(user_email='test@google.com', is_admin=False)

    params = {
        'xsrf_token': 'token',
        'auto_commit_revert_compile': 'true',
        'update_reason': 'reason',
        'format': 'json',
    }

    response = self.test_app.post(
        '/change-auto-revert-setting', params=params, status=403)
    self.assertEqual('Only admin could turn auto-commit on.',
                     response.json_body.get('error_message'))

  @mock.patch.object(token, 'ValidateAuthToken', return_value=(True, False))
  def testAdminCouldTurnOnAutoCommit(self, _):
    self.mock_current_user(user_email='test@google.com', is_admin=True)
    self.UpdateUnitTestConfigSettings('action_settings',
                                      {'auto_commit_revert_compile': False})

    params = {
        'xsrf_token': 'token',
        'auto_commit_revert_compile': 'true',
        'update_reason': 'reason',
        'format': 'json',
    }

    response = self.test_app.post(
        '/change-auto-revert-setting', params=params, status=302)
    self.assertTrue(
        response.headers.get('Location', '').endswith(
            '/change-auto-revert-setting'))
    self.assertTrue(
        waterfall_config.GetActionSettings().get('auto_commit_revert_compile'))

  @mock.patch.object(token, 'ValidateAuthToken', return_value=(True, False))
  def testAutoCommitAlreadyTurnedOn(self, _):
    self.mock_current_user(user_email='test@google.com', is_admin=True)
    self.UpdateUnitTestConfigSettings('action_settings',
                                      {'auto_commit_revert_compile': True})

    params = {
        'xsrf_token': 'token',
        'auto_commit_revert_compile': 'true',
        'update_reason': 'reason',
        'format': 'json',
    }

    response = self.test_app.post(
        '/change-auto-revert-setting', params=params, status=400)
    self.assertEqual('Failed to update auto-revert setting. '
                     'Please refresh the page and try again.',
                     response.json_body.get('error_message'))

  @mock.patch.object(token, 'ValidateAuthToken', return_value=(True, False))
  def testChangeAutoRevertSettingPostFailedEmptyMessage(self, _):
    self.mock_current_user(user_email='test@google.com', is_admin=False)

    params = {
        'xsrf_token': 'token',
        'auto_commit_revert_compile': 'false',
        'update_reason': '\n',
        'format': 'json',
    }

    response = self.test_app.post(
        '/change-auto-revert-setting', params=params, status=400)
    self.assertEqual('Please enter the reason.',
                     response.json_body.get('error_message'))
