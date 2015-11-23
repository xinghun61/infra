# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import endpoints

from testing_utils import testing

from findit_api import FindItApi
from model.wf_analysis import WfAnalysis
from model import wf_analysis_status
from waterfall import waterfall_config


class FinditApiTest(testing.EndpointsTestCase):
  api_service_cls = FindItApi

  def _MockMasterIsSupported(self, supported):
    def MockMasterIsSupported(*_):
      return supported
    self.mock(waterfall_config, 'MasterIsSupported',
              MockMasterIsSupported)

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
    expected_results = []

    self._MockMasterIsSupported(supported=True)

    response = self.call_api('AnalyzeBuildFailures', body=builds)
    self.assertEqual(200, response.status_int)
    self.assertEqual(expected_results, response.json_body.get('results', []))

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
    expected_results = []

    self._MockMasterIsSupported(supported=False)

    response = self.call_api('AnalyzeBuildFailures', body=builds)
    self.assertEqual(200, response.status_int)
    self.assertEqual(expected_results, response.json_body.get('results', []))

  def testFailedAnalysisIsNotReturnedEvenWhenItHasResults(self):
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
    analysis.status = wf_analysis_status.ERROR
    analysis.result = {
        'failures': [
            {
                'step_name': 'test',
                'first_failure': 3,
                'last_pass': 1,
                'suspected_cls': [
                    {
                        'repo_name': 'chromium',
                        'revision': 'git_hash',
                        'commit_position': 123,
                    }
                ]
            }
        ]
    }
    analysis.put()

    expected_result = []

    self._MockMasterIsSupported(supported=True)

    response = self.call_api('AnalyzeBuildFailures', body=builds)
    self.assertEqual(200, response.status_int)
    self.assertEqual(expected_result, response.json_body.get('results', []))

  def testNoResultIsReturnedWhenNoAnalysisIsCompleted(self):
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
    analysis.status = wf_analysis_status.ANALYZING
    analysis.result = None
    analysis.put()

    expected_result = []

    self._MockMasterIsSupported(supported=True)

    response = self.call_api('AnalyzeBuildFailures', body=builds)
    self.assertEqual(200, response.status_int)
    self.assertEqual(expected_result, response.json_body.get('results', []))

  def testPreviousAnalysisResultIsReturnedWhileANewAnalysisIsRunning(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1

    master_url = 'https://build.chromium.org/p/%s' % master_name
    builds = {
        'builds': [
            {
                'master_url': master_url,
                'builder_name': builder_name,
                'build_number': build_number,
                'failed_steps': ['a', 'b']
            }
        ]
    }

    self._MockMasterIsSupported(supported=True)

    analysis_result = {
        'failures': [
            {
                'step_name': 'a',
                'first_failure': 23,
                'last_pass': 22,
                'suspected_cls': [
                    {
                        'repo_name': 'chromium',
                        'revision': 'git_hash',
                        'commit_position': 123,
                    }
                ]
            }
        ]
    }
    expected_results = [
        {
            'master_url': master_url,
            'builder_name': builder_name,
            'build_number': build_number,
            'step_name': 'a',
            'is_sub_test': False,
            'first_known_failed_build_number': 23,
            'suspected_cls': [
                {
                    'repo_name': 'chromium',
                    'revision': 'git_hash',
                    'commit_position': 123,
                }
            ]
        },
    ]

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.status = wf_analysis_status.ANALYZING
    analysis.result = analysis_result
    analysis.put()

    response = self.call_api('AnalyzeBuildFailures', body=builds)
    self.assertEqual(200, response.status_int)
    self.assertEqual(expected_results, response.json_body['results'])

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

    expected_result = []

    self._MockMasterIsSupported(supported=True)

    response = self.call_api('AnalyzeBuildFailures', body=builds)
    self.assertEqual(200, response.status_int)
    self.assertEqual(expected_result, response.json_body.get('results', []))

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

    expected_results = [
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

    self._MockMasterIsSupported(supported=True)

    response = self.call_api('AnalyzeBuildFailures', body=builds)
    self.assertEqual(200, response.status_int)
    self.assertEqual(expected_results, response.json_body.get('results'))

  def testTestLevelResultIsReturned(self):
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
                'step_name': 'a',
                'first_failure': 4,
                'last_pass': 3,
                'suspected_cls': [
                    {
                        'build_number': 4,
                        'repo_name': 'chromium',
                        'revision': 'r4_2',
                        'commit_position': None,
                        'url': None,
                        'score': 2,
                        'hints': {
                            'modified f4_2.cc (and it was in log)': 2,
                        },
                    }
                ],
            },
            {
                'step_name': 'b',
                'first_failure': 3,
                'last_pass': 2,
                'suspected_cls': [
                    {
                        'build_number': 3,
                        'repo_name': 'chromium',
                        'revision': 'r3_1',
                        'commit_position': None,
                        'url': None,
                        'score': 5,
                        'hints': {
                            'added x/y/f3_1.cc (and it was in log)': 5,
                        },
                    },
                    {
                        'build_number': 4,
                        'repo_name': 'chromium',
                        'revision': 'r4_1',
                        'commit_position': None,
                        'url': None,
                        'score': 2,
                        'hints': {
                            'modified f4.cc (and it was in log)': 2,
                        },
                    }
                ],
                'tests': [
                    {
                        'test_name': 'Unittest1.Subtest1',
                        'first_failure': 3,
                        'last_pass': 2,
                        'suspected_cls': [
                            {
                                'build_number': 2,
                                'repo_name': 'chromium',
                                'revision': 'r2_1',
                                'commit_position': None,
                                'url': None,
                                'score': 5,
                                'hints': {
                                    'added x/y/f99_1.cc (and it was in log)': 5,
                                },
                            }
                        ]
                    },
                    {
                        'test_name': 'Unittest2.Subtest1',
                        'first_failure': 4,
                        'last_pass': 2,
                        'suspected_cls': [
                            {
                                'build_number': 2,
                                'repo_name': 'chromium',
                                'revision': 'r2_1',
                                'commit_position': None,
                                'url': None,
                                'score': 5,
                                'hints': {
                                    'added x/y/f99_1.cc (and it was in log)': 5,
                                },
                            }
                        ]
                    },
                    {
                        'test_name': 'Unittest3.Subtest1',
                        'first_failure': 4,
                        'last_pass': 2,
                        'suspected_cls': []
                    }
                ]
            }
        ]
    }
    analysis.put()

    expected_results = [
        {
            'master_url': master_url,
            'builder_name': builder_name,
            'build_number': build_number,
            'step_name': 'a',
            'is_sub_test': False,
            'first_known_failed_build_number': 4,
            'suspected_cls': [
                {
                    'repo_name': 'chromium',
                    'revision': 'r4_2',
                }
            ]
        },
        {
            'master_url': master_url,
            'builder_name': builder_name,
            'build_number': build_number,
            'step_name': 'b',
            'is_sub_test': True,
            'test_name': 'Unittest1.Subtest1',
            'first_known_failed_build_number': 3,
            'suspected_cls': [
                {
                    'repo_name': 'chromium',
                    'revision': 'r2_1',
                }
            ]
        },
        {
            'master_url': master_url,
            'builder_name': builder_name,
            'build_number': build_number,
            'step_name': 'b',
            'is_sub_test': True,
            'test_name': 'Unittest2.Subtest1',
            'first_known_failed_build_number': 4,
            'suspected_cls': [
                {
                    'repo_name': 'chromium',
                    'revision': 'r2_1',
                }
            ]
        }
    ]

    self._MockMasterIsSupported(supported=True)

    response = self.call_api('AnalyzeBuildFailures', body=builds)
    self.assertEqual(200, response.status_int)
    self.assertEqual(expected_results, response.json_body.get('results'))
