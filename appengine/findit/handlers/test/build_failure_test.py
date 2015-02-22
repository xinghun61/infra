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
from model.build_analysis_status import BuildAnalysisStatus
from waterfall import buildbot
from waterfall import masters


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
    self.testbed.init_taskqueue_stub(root_path= ROOT_DIR)
    self.taskqueue_stub = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
    for queue in self.taskqueue_stub.GetQueues():
      self.taskqueue_stub.FlushQueue(queue['name'])

  def testInvalidBuildUrl(self):
    build_url = 'abc'
    self.assertRaisesRegexp(
        webtest.app.AppError,
        re.compile('.*501 Not Implemented.*Url &#34;%s&#34; '
                   'is not pointing to a build.*' % build_url,
                   re.MULTILINE|re.DOTALL),
        self.test_app.get, '/build-failure', params={'url': build_url})

  def testMasterNotSupported(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    build_url = buildbot.CreateBuildUrl(
        master_name, builder_name, build_number)

    def MockMasterIsSupported(*_):
      return False
    self.mock(masters, 'MasterIsSupported', MockMasterIsSupported)

    self.assertRaisesRegexp(
        webtest.app.AppError,
        re.compile('.*501 Not Implemented.*Master &#34;%s&#34; '
                   'is not supported yet.*' % master_name,
                   re.MULTILINE|re.DOTALL),
        self.test_app.get, '/build-failure', params={'url': build_url})

  def testBuildFailureAnalysisScheduled(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    build_url = buildbot.CreateBuildUrl(
        master_name, builder_name, build_number)

    def MockMasterIsSupported(*_):
      return True
    self.mock(masters, 'MasterIsSupported', MockMasterIsSupported)

    response = self.test_app.get('/build-failure', params={'url': build_url})
    self.assertEquals(200, response.status_int)

    self.assertEqual(1, len(self.taskqueue_stub.get_filtered_tasks()))
