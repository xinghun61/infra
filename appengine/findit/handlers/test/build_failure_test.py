# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import re

from google.appengine.ext import testbed
import webapp2
import webtest

from testing_utils import testing

from handlers import build_failure
from model.wf_analysis import WfAnalysis
from model import wf_analysis_status
from waterfall import buildbot
from waterfall import waterfall_config


# Root directory appengine/findit.
ROOT_DIR = os.path.join(os.path.dirname(__file__),
                        os.path.pardir, os.path.pardir)


class BuildFailureTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication([
      ('/build-failure', build_failure.BuildFailure),
  ], debug=True)

  def setUp(self):
    super(BuildFailureTest, self).setUp()

    # Setup clean task queues.
    self.testbed.init_taskqueue_stub(root_path=ROOT_DIR)
    self.taskqueue_stub = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
    for queue in self.taskqueue_stub.GetQueues():
      self.taskqueue_stub.FlushQueue(queue['name'])

  def testGetTriageHistoryWhenUserIsNotAdmin(self):
    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.status = wf_analysis_status.ANALYZED
    analysis.triage_history = [
        {
            'triage_timestamp': 1438380761,
            'user_name': 'test',
            'result_status': 'dummy status',
            'version': 'dummy version',
        }
    ]
    self.assertIsNone(build_failure._GetTriageHistory(analysis))

  def testGetTriageHistoryWhenUserIsAdmin(self):
    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.status = wf_analysis_status.ANALYZED
    analysis.triage_history = [
        {
            'triage_timestamp': 1438380761,
            'user_name': 'test',
            'result_status': 'dummy status',
            'version': 'dummy version',
        }
    ]
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)
    self.assertEqual(1, len(build_failure._GetTriageHistory(analysis)))

  def testInvalidBuildUrl(self):
    build_url = 'abc'
    self.assertRaisesRegexp(
        webtest.app.AppError,
        re.compile('.*501 Not Implemented.*Url &#34;%s&#34; '
                   'is not pointing to a build.*' % build_url,
                   re.MULTILINE|re.DOTALL),
        self.test_app.get, '/build-failure', params={'url': build_url})

  def testNonAdminCanViewAnalysisOfFailureOnUnsupportedMaster(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    build_url = buildbot.CreateBuildUrl(
        master_name, builder_name, build_number)

    def MockMasterIsSupported(*_):
      return False
    self.mock(waterfall_config, 'MasterIsSupported',
              MockMasterIsSupported)

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.status = wf_analysis_status.ANALYZED
    analysis.put()

    response = self.test_app.get('/build-failure',
                                 params={'url': build_url, 'force': '1'})
    self.assertEquals(200, response.status_int)
    self.assertEqual(0, len(self.taskqueue_stub.get_filtered_tasks()))

  def testNonAdminCannotRequestAnalysisOfFailureOnUnsupportedMaster(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    build_url = buildbot.CreateBuildUrl(
        master_name, builder_name, build_number)

    def MockMasterIsSupported(*_):
      return False
    self.mock(waterfall_config, 'MasterIsSupported', MockMasterIsSupported)

    self.assertRaisesRegexp(
        webtest.app.AppError,
        re.compile('.*501 Not Implemented.*Master &#34;%s&#34; '
                   'is not supported yet.*' % master_name,
                   re.MULTILINE|re.DOTALL),
        self.test_app.get, '/build-failure', params={'url': build_url})

  def testAdminCanRequestAnalysisOfFailureOnUnsupportedMaster(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    build_url = buildbot.CreateBuildUrl(
        master_name, builder_name, build_number)

    def MockMasterIsSupported(*_):
      return False
    self.mock(waterfall_config, 'MasterIsSupported', MockMasterIsSupported)

    self.mock_current_user(user_email='test@chromium.org', is_admin=True)

    response = self.test_app.get('/build-failure', params={'url': build_url})
    self.assertEquals(200, response.status_int)

    self.assertEqual(1, len(self.taskqueue_stub.get_filtered_tasks()))

  def testAnyoneCanRequestAnalysisOfFailureOnSupportedMaster(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    build_url = buildbot.CreateBuildUrl(
        master_name, builder_name, build_number)

    def MockMasterIsSupported(*_):
      return True
    self.mock(waterfall_config, 'MasterIsSupported', MockMasterIsSupported)

    response = self.test_app.get('/build-failure', params={'url': build_url})
    self.assertEquals(200, response.status_int)

    self.assertEqual(1, len(self.taskqueue_stub.get_filtered_tasks()))
