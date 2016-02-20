# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import re

from google.appengine.ext import testbed
import webapp2
import webtest

from testing_utils import testing

from model.wf_build import WfBuild
from handlers import trigger_analyses
from waterfall import buildbot
from waterfall import build_util
from waterfall import build_failure_analysis_pipelines
from waterfall.build_info import BuildInfo


class TriggerAnalyseseTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication([
      ('/trigger-analyses', trigger_analyses.TriggerAnalyses),
  ], debug=True)

  def _MockDownloadBuildData(self, build):
    def Mocked_DownloadBuildData(*_):
      return build
    self.mock(build_util, 'DownloadBuildData', Mocked_DownloadBuildData)

  def _MockExtractBuildInfo(self, build_info):
    def Mocked_ExtractBuildInfo(*_):
      return build_info
    self.mock(buildbot, 'ExtractBuildInfo', Mocked_ExtractBuildInfo)

  def _MockScheduleAnalysisIfNeeded(self, requests):
    def Mocked_ScheduleAnalysisIfNeeded(*args, **kwargs):
      requests.append((args, kwargs))
    self.mock(build_failure_analysis_pipelines,
              'ScheduleAnalysisIfNeeded', Mocked_ScheduleAnalysisIfNeeded)

  def testWhenBuildIsNotAvailable(self):
    self._MockDownloadBuildData(None)
    self._MockExtractBuildInfo(None)
    requests = []
    self._MockScheduleAnalysisIfNeeded(requests)

    builds = [
        {
            'master_name': 'm',
            'builder_name': 'b',
            'build_number': 1,
            'failed_steps': [],
        },
    ]

    trigger_analyses._TriggerNewAnalysesOnDemand(builds)
    self.assertEqual(0, len(requests))

  def testWhenBuildDataIsNotAvailable(self):
    build = WfBuild.Create('m', 'b', 1)
    build.data = None
    self._MockDownloadBuildData(build)

    self._MockExtractBuildInfo(None)
    requests = []
    self._MockScheduleAnalysisIfNeeded(requests)

    builds = [
        {
            'master_name': 'm',
            'builder_name': 'b',
            'build_number': 1,
            'failed_steps': [],
        },
    ]

    trigger_analyses._TriggerNewAnalysesOnDemand(builds)
    self.assertEqual(0, len(requests))

  def testWhenBuildDataIsDownloadedSuccessfully(self):
    build = WfBuild.Create('m', 'b', 1)
    build.data = '{}'
    self._MockDownloadBuildData(build)

    build_info = BuildInfo('m', 'b', 1)
    build_info.completed = False
    self._MockExtractBuildInfo(build_info)

    requests = []
    self._MockScheduleAnalysisIfNeeded(requests)

    builds = [
        {
            'master_name': 'm',
            'builder_name': 'b',
            'build_number': 1,
            'failed_steps': [],
        },
    ]
    trigger_analyses._TriggerNewAnalysesOnDemand(builds)
    self.assertEqual(1, len(requests))
    self.assertFalse(requests[0][1]['build_completed'])

  def testNonAdminCanNotSendRequest(self):
    self.assertRaisesRegexp(
        webtest.app.AppError,
        re.compile('.*401 Unauthorized.*'
                   'Error: Either not login or no permission.*',
                   re.MULTILINE | re.DOTALL),
        self.test_app.post, '/trigger-analyses', params={'builds': '[]'})

  def testAdminCanRequestAnalysisOfFailureOnUnsupportedMaster(self):
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)

    build = WfBuild.Create('m', 'b', 1)
    build.data = '{}'
    self._MockDownloadBuildData(build)

    build_info = BuildInfo('m', 'b', 1)
    build_info.completed = True
    self._MockExtractBuildInfo(build_info)

    requests = []
    self._MockScheduleAnalysisIfNeeded(requests)

    builds = [
        {
            'master_name': 'm',
            'builder_name': 'b',
            'build_number': 1,
            'failed_steps': [],
        },
    ]

    response = self.test_app.post(
        '/trigger-analyses', params={'builds': json.dumps(builds)})
    self.assertEquals(200, response.status_int)
    self.assertEqual(1, len(requests))
    self.assertTrue(requests[0][1]['build_completed'])
