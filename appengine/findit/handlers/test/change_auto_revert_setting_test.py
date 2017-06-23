# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import re

import webapp2
import webtest

from gae_libs import token
from handlers import change_auto_revert_setting
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
        'auto_revert_on': True,
        'xsrf_token': response.json_body.get('xsrf_token')
    }
    self.assertEqual(200, response.status_int)
    self.assertEqual(expected_response, response.json_body)

  @mock.patch.object(token, 'ValidateAuthToken', return_value=True)
  def testChangeAutoRevertSettingPost(self, _):
    self.mock_current_user(user_email='test@google.com', is_admin=False)

    params = {'xsrf_token': 'token', 'revert_compile_culprit': 'false'}

    response = self.test_app.post(
        '/change-auto-revert-setting?format=json', params=params)
    redirect_url = '/waterfall/change-auto-revert-setting'
    self.assertTrue(response.headers.get('Location', '').endswith(redirect_url))

  @mock.patch.object(token, 'ValidateAuthToken', return_value=True)
  def testChangeAutoRevertSettingPostFailed(self, _):
    self.mock_current_user(user_email='test@google.com', is_admin=False)

    params = {'xsrf_token': 'token', 'revert_compile_culprit': 'true'}

    self.assertRaisesRegexp(
        webtest.app.AppError,
        re.compile('.*501 Not Implemented.*Auto Revert setting is not changed.'
                   ' Please go back and try again.', re.MULTILINE | re.DOTALL),
        self.test_app.post,
        '/change-auto-revert-setting',
        params=params)
