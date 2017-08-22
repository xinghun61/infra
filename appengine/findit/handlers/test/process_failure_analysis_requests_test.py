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
from handlers import process_failure_analysis_requests
from waterfall import buildbot
from waterfall import build_util
from waterfall import build_failure_analysis_pipelines
from waterfall.build_info import BuildInfo


class ProcessFailureAnalysisRequestsTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/process-failure-analysis-requests',
           process_failure_analysis_requests.ProcessFailureAnalysisRequests),
      ],
      debug=True)

  def _MockGetBuildInfo(self, build_info):

    def MockedGetBuildInfo(*_):
      return build_info

    self.mock(build_util, 'GetBuildInfo', MockedGetBuildInfo)

  def _MockScheduleAnalysisIfNeeded(self, requests):

    def Mocked_ScheduleAnalysisIfNeeded(*args, **kwargs):
      requests.append((args, kwargs))

    self.mock(build_failure_analysis_pipelines, 'ScheduleAnalysisIfNeeded',
              Mocked_ScheduleAnalysisIfNeeded)

  def testWhenBuildDataIsNotAvailable(self):
    self._MockGetBuildInfo(None)
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

    process_failure_analysis_requests._TriggerNewAnalysesOnDemand(builds)
    self.assertEqual(0, len(requests))

  def testWhenBuildDataIsDownloadedSuccessfully(self):
    build_info = BuildInfo('m', 'b', 1)
    build_info.completed = False
    self._MockGetBuildInfo(build_info)

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
    process_failure_analysis_requests._TriggerNewAnalysesOnDemand(builds)
    self.assertEqual(1, len(requests))
    self.assertFalse(requests[0][1]['build_completed'])

  def testTaskQueueCanRequestAnalysis(self):
    build_info = BuildInfo('m', 'b', 1)
    build_info.completed = True
    self._MockGetBuildInfo(build_info)

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
        '/process-failure-analysis-requests',
        params=json.dumps({
            'builds': builds
        }),
        headers = {'X-AppEngine-QueueName': 'task_queue'},
    )
    self.assertEquals(200, response.status_int)
    self.assertEqual(1, len(requests))
    self.assertTrue(requests[0][1]['build_completed'])
