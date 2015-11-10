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

  def testGetFormattedJsonLogIfSwarming(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    step_name = 'browser_test'
    step_url = buildbot.CreateStdioLogUrl(
        master_name, builder_name, build_number, step_name)

    step_log = WfStep.Create(master_name, builder_name, build_number, step_name)
    step_log.isolated = True
    step_log.log_data = (
        '{"Unittest2.Subtest1": "RVJST1I6eF90ZXN0LmNjOjEyMzQKYS9iL3Uy'
        'czEuY2M6NTY3OiBGYWlsdXJlCkVSUk9SOlsyXTogMjU5NDczNTAwMCBib2dvLW1pY3Jv'
        'c2Vjb25kcwpFUlJPUjp4X3Rlc3QuY2M6MTIzNAphL2IvdTJzMS5jYzo1Njc6IE'
        'ZhaWx1cmUK", '
        '"Unittest3.Subtest2": "YS9iL3UzczIuY2M6MTEwOiBGYWlsdXJlCg=="}')
    step_log.put()

    self.mock_current_user(user_email='test@google.com', is_admin=True)

    response = self.test_app.get('/failure-log', params={'url': step_url, 
                                                         'format': 'json'})
    expected_response = {
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 123,
        'step_name': 'browser_test',
        'step_logs': ('{\n    "Unittest2.Subtest1": "ERROR:x_test.cc:1234'
                      '\n        a/b/u2s1.cc:567: Failure\n        '
                      'ERROR:[2]: 2594735000 bogo-microseconds\n        '
                      'ERROR:x_test.cc:1234\n        a/b/u2s1.cc:567: Failure'
                      '\n        ", \n    "Unittest3.Subtest2": '
                      '"a/b/u3s2.cc:110: Failure\n        "\n}')

    }
    self.assertEquals(200, response.status_int)
    self.assertEquals(expected_response, response.json_body)
