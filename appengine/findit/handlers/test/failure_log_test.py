# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import re

from google.appengine.ext import testbed
import webapp2
import webtest

from testing_utils import testing

from handlers import failure_log
from waterfall import buildbot
from model.wf_step import WfStep

# Root directory appengine/findit.
ROOT_DIR = os.path.join(os.path.dirname(__file__),
                        os.path.pardir, os.path.pardir)


class FailureLogTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication([
      ('/failure-log', failure_log.FailureLog),
  ], debug=True)
  
  def testInvalidStepUrl(self):
    step_url = 'abcde'
    self.mock_current_user(user_email='test@google.com', is_admin=True)
    self.assertRaisesRegexp(
        webtest.app.AppError,
        re.compile('.*501 Not Implemented.*Url &#34;%s&#34; '
                   'is not pointing to a step.*' % step_url,
                   re.MULTILINE|re.DOTALL),
        self.test_app.get, '/failure-log', params={'url': step_url})

  def testFailureLogNotFound(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    step_name = 'compile'
    step_url = buildbot.CreateStdioLogUrl(
        master_name, builder_name, build_number, step_name)
   
    self.mock_current_user(user_email='test@google.com', is_admin=True)

    self.assertRaisesRegexp(
        webtest.app.AppError,
        re.compile('.*404 Not Found.*No failure log available.*',
                   re.MULTILINE|re.DOTALL),
        self.test_app.get, '/failure-log', params={'url': step_url, 
                                                   'format': 'json'})
 
  def testFailureLogFetched(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    step_name = 'compile'
    step_url = buildbot.CreateStdioLogUrl(
        master_name, builder_name, build_number, step_name)   

    step_log = WfStep.Create(master_name, builder_name, build_number, step_name)
    step_log.log_data = 'Log has been successfully fetched!'
    step_log.put()

    self.mock_current_user(user_email='test@google.com', is_admin=True)

    response = self.test_app.get('/failure-log', params={'url': step_url, 
                                                         'format': 'json'})
    expected_response = {
        'master_name': 'm',
        'builder_name': 'b 1',
        'build_number': 123,
        'step_name': 'compile',
        'step_logs': 'Log has been successfully fetched!'
    }

    self.assertEquals(200, response.status_int)
    self.assertEquals(expected_response, response.json_body)
