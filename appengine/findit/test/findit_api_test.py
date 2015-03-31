# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import endpoints

from testing_utils import testing

from findit_api import FindItApi
from model.wf_analysis import WfAnalysis
from model import wf_analysis_status
from waterfall import masters


class FinditApiTest(testing.EndpointsTestCase):
  api_service_cls = FindItApi

  def _MockMasterIsSupported(self, supported):
    def MockMasterIsSupported(*_):
      return supported
    self.mock(masters, 'MasterIsSupported', MockMasterIsSupported)

  def testUnrecognizedMasterUrl(self):
    builds = {
        'builds': [
            {
                'master_url': 'https://not a master url',
                'builder_name': 'a',
                'build_number': 1
            }
        ]
    }
    expected_result = {}

    self._MockMasterIsSupported(supported=True)

    response = self.call_api('AnalyzeBuildFailures', body=builds)
    self.assertEqual(200, response.status_int)
    self.assertEqual(expected_result, response.json_body)

  def testMasterIsNotSupported(self):
    builds = {
        'builds': [
            {
                'master_url': 'https://build.chromium.org/p/a',
                'builder_name': 'a',
                'build_number': 1
            }
        ]
    }
    expected_result = {}

    self._MockMasterIsSupported(supported=False)

    response = self.call_api('AnalyzeBuildFailures', body=builds)
    self.assertEqual(200, response.status_int)
    self.assertEqual(expected_result, response.json_body)

  def testIncompletedAndFailedAnalysisIsNotReturned(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1

    master_url = 'https://build.chromium.org/p/%s' % master_name
    builds = {
        'builds': [
            {
                'master_url': master_url,
                'builder_name': builder_name,
                'build_number': build_number
            }
        ]
    }

    self._MockMasterIsSupported(supported=True)

    for status in (wf_analysis_status.PENDING, wf_analysis_status.ANALYZING,
                   wf_analysis_status.ERROR):
      analysis = WfAnalysis.Create(master_name, builder_name, build_number)
      analysis.status = status
      analysis.put()

      expected_result = {}

      response = self.call_api('AnalyzeBuildFailures', body=builds)
      self.assertEqual(200, response.status_int)
      self.assertEqual(expected_result, response.json_body)

  def testAnalysisFindingNoSuspectedCLsIsNotReturned(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 5

    master_url = 'https://build.chromium.org/p/%s' % master_name
    builds = {
        'builds': [
            {
                'master_url': master_url,
                'builder_name': builder_name,
                'build_number': build_number
            }
        ]
    }

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.status = wf_analysis_status.ANALYZED
    analysis.result = {
        'failures': [
            {
                'step_name': 'test',
                'first_failure': 3,
                'last_pass': 1,
                'suspected_cls': []
            }
        ]
    }
    analysis.put()

    expected_result = {}

    self._MockMasterIsSupported(supported=True)

    response = self.call_api('AnalyzeBuildFailures', body=builds)
    self.assertEqual(200, response.status_int)
    self.assertEqual(expected_result, response.json_body)

  def testAnalysisFindingSuspectedCLsIsReturned(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 5

    master_url = 'https://build.chromium.org/p/%s' % master_name
    builds = {
        'builds': [
            {
                'master_url': master_url,
                'builder_name': builder_name,
                'build_number': build_number
            }
        ]
    }

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.status = wf_analysis_status.ANALYZED
    analysis.result = {
        'failures': [
            {
                'step_name': 'test',
                'first_failure': 3,
                'last_pass': 1,
                'suspected_cls': [
                    {
                        'build_number': 2,
                        'repo_name': 'chromium',
                        'revision': 'git_hash1',
                        'commit_position': 234,
                        'score': 11,
                        'hints': {
                            'add a/b/x.cc': 5,
                            'delete a/b/y.cc': 5,
                            'modify e/f/z.cc': 1,
                        }
                    },
                    {
                        'build_number': 3,
                        'repo_name': 'chromium',
                        'revision': 'git_hash2',
                        'commit_position': 288,
                        'score': 1,
                        'hints': {
                            'modify d/e/f.cc': 1,
                        }
                    }
                ]
            }
        ]
    }
    analysis.put()

    expected_result = {
        'results': [
            {
                'master_url': master_url,
                'builder_name': builder_name,
                'build_number': build_number,
                'step_name': 'test',
                'is_sub_test': False,
                'first_known_failed_build_number': 3,
                'suspected_cls': [
                    {
                        'repo_name': 'chromium',
                        'revision': 'git_hash1',
                        'commit_position': 234,
                    },
                    {
                        'repo_name': 'chromium',
                        'revision': 'git_hash2',
                        'commit_position': 288,
                    }
                ]
            }
        ]
    }

    self._MockMasterIsSupported(supported=True)

    response = self.call_api('AnalyzeBuildFailures', body=builds)
    self.assertEqual(200, response.status_int)
    self.assertEqual(expected_result, response.json_body)
