# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import re

from google.appengine.ext import testbed

import webapp2
import webtest

from common.waterfall import failure_type
from handlers import build_failure
from handlers import handlers_util
from handlers import result_status
from libs import analysis_status
from model import analysis_approach_type
from model import suspected_cl_status
from model.suspected_cl_confidence import ConfidenceInformation
from model.suspected_cl_confidence import SuspectedCLConfidence
from model.wf_analysis import WfAnalysis
from model.wf_suspected_cl import WfSuspectedCL
from model.wf_try_job import WfTryJob
from waterfall import build_util
from waterfall import buildbot
from waterfall import build_util
from waterfall.test import wf_testcase

# Root directory appengine/findit.
ROOT_DIR = os.path.join(os.path.dirname(__file__),
                        os.path.pardir, os.path.pardir)

SAMPLE_TRY_JOB_INFO = {
    'm/b/119': {
        'step1 on platform': {
            'try_jobs': [
                {
                    'ref_name': 'step1',
                    'try_job_key': 'm/b/119',
                    'task_id': 'task1',
                    'task_url': 'url/task1',
                    'status': analysis_status.COMPLETED,
                    'try_job_url': (
                        'http://build.chromium.org/p/tryserver.chromium.'
                        'linux/builders/linux_variable/builds/121'),
                    'try_job_build_number': 121,
                    'tests': ['test3'],
                    'culprit': {}
                },
                {
                    'ref_name': 'step1',
                    'try_job_key': 'm/b/119',
                    'task_id': 'task1',
                    'task_url': 'url/task1',
                    'status': analysis_status.COMPLETED,
                    'try_job_url': (
                        'http://build.chromium.org/p/tryserver.chromium.'
                        'linux/builders/linux_variable/builds/121'),
                    'try_job_build_number': 121,
                    'culprit': {
                        'revision': 'rev2',
                        'commit_position': '2',
                        'review_url': 'url_2'
                    },
                    'tests': ['test2']
                },
                {
                    'ref_name': 'step1',
                    'try_job_key': 'm/b/119',
                    'status': result_status.FLAKY,
                    'task_id': 'task1',
                    'task_url': 'url/task1',
                    'tests': ['test4']
                },
                {
                    'ref_name': 'step1',
                    'try_job_key': 'm/b/120',
                    'status': result_status.NO_TRY_JOB_REASON_MAP[
                        analysis_status.PENDING],
                    'task_id': 'task2',
                    'task_url': 'url/task2',
                    'tests': ['test1']
                },
                {
                    'ref_name': 'step1',
                    'try_job_key': 'm/b/120',
                    'task_id': 'task2',
                    'task_url': 'url/task2',
                    'tests': ['test5']
                }
            ]
        }
    },
    'm/b/120': {
        'compile': {
            'try_jobs': [
                {
                    'try_job_key': 'm/b/120',
                    'status': analysis_status.COMPLETED,
                    'try_job_build_number': 120,
                    'try_job_url': (
                        'http://build.chromium.org/p/tryserver.chromium.'
                        'linux/builders/linux_variable/builds/120'),
                    'culprit': {
                        'revision': 'rev2',
                        'commit_position': '2',
                        'review_url': 'url_2'
                    }
                }
            ]
        }
    }
}

SAMPLE_HEURISTIC_1 = ConfidenceInformation(
    correct=100, total=100, confidence=1.0, score=5)

SAMPLE_HEURISTIC_2 = ConfidenceInformation(
    correct=90, total=100, confidence=0.9, score=4)

SAMPLE_TRY_JOB = ConfidenceInformation(
    correct=99, total=100, confidence=0.99, score=None)

SAMPLE_HEURISTIC_TRY_JOB = ConfidenceInformation(
    correct=98, total=100, confidence=0.98, score=None)


class BuildFailureTest(wf_testcase.WaterfallTestCase):
  app_module = webapp2.WSGIApplication([
      ('/failure', build_failure.BuildFailure),
  ], debug=True)

  def setUp(self):
    super(BuildFailureTest, self).setUp()

    # Setup clean task queues.
    self.testbed.init_taskqueue_stub(root_path=ROOT_DIR)
    self.taskqueue_stub = self.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)
    for queue in self.taskqueue_stub.GetQueues():
      self.taskqueue_stub.FlushQueue(queue['name'])

    def MockedGetAllTryJobResults(master_name, builder_name, build_number, _):
      build_key = build_util.CreateBuildId(
          master_name, builder_name, build_number)
      return SAMPLE_TRY_JOB_INFO.get(build_key, None)
    self.mock(handlers_util, 'GetAllTryJobResults', MockedGetAllTryJobResults)

    self.cl_confidences = SuspectedCLConfidence.Create()
    self.cl_confidences.compile_heuristic = [
        SAMPLE_HEURISTIC_1, SAMPLE_HEURISTIC_2]
    self.cl_confidences.test_heuristic = [
        SAMPLE_HEURISTIC_2, SAMPLE_HEURISTIC_1]
    self.cl_confidences.compile_try_job = SAMPLE_TRY_JOB
    self.cl_confidences.test_try_job = SAMPLE_TRY_JOB
    self.cl_confidences.compile_heuristic_try_job = SAMPLE_HEURISTIC_TRY_JOB
    self.cl_confidences.test_heuristic_try_job = SAMPLE_HEURISTIC_TRY_JOB
    self.cl_confidences.Save()

  def testGetTriageHistoryWhenUserIsNotAdmin(self):
    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.status = analysis_status.COMPLETED
    analysis.triage_history = [
        {
            'triage_timestamp': 1438380761,
            'user_name': 'test',
            'result_status': 'dummy status',
            'version': 'dummy version',
        }
    ]
    self.assertIsNone(build_failure._GetTriageHistory(analysis))

  def testGetCLDict(self):
    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.suspected_cls = [
        {
            'repo_name': 'chromium',
            'revision': 'rev2',
            'url': 'url',
            'commit_position': 123
        }
    ]
    analysis.put()
    cl_info = 'chromium/rev1'
    self.assertEqual({}, build_failure._GetCLDict(analysis, cl_info))

  def testGetCLDictNone(self):
    self.assertEqual({}, build_failure._GetCLDict(None, None))

  def testGetTriageHistoryWhenUserIsAdmin(self):
    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.status = analysis_status.COMPLETED
    analysis.suspected_cls = [
        {
            'repo_name': 'chromium',
            'revision': 'rev1',
            'url': 'url',
            'commit_position': 123
        }
    ]
    analysis.triage_history = [
        {
            'triage_timestamp': 1438380761,
            'user_name': 'test',
            'result_status': 'dummy status',
            'version': 'dummy version',
            'triaged_cl': 'chromium/rev1'
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
                   re.MULTILINE | re.DOTALL),
        self.test_app.get, '/failure', params={'url': build_url})

  def testNonAdminCanViewAnalysisOfFailureOnUnsupportedMaster(self):
    master_name = 'm2'
    builder_name = 'b 1'
    build_number = 123
    build_url = buildbot.CreateBuildUrl(
        master_name, builder_name, build_number)

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.status = analysis_status.COMPLETED
    analysis.suspected_cls = [
        {
            'repo_name': 'chromium',
            'revision': 'r99_2',
            'commit_position': None,
            'url': None,
        }
    ]
    analysis.put()

    response = self.test_app.get('/failure',
                                 params={'url': build_url})
    self.assertEquals(200, response.status_int)
    self.assertEqual(0, len(self.taskqueue_stub.get_filtered_tasks()))

  def testNonAdminCannotRequestAnalysisOfFailureOnUnsupportedMaster(self):
    master_name = 'm2'
    builder_name = 'b 1'
    build_number = 123
    build_url = buildbot.CreateBuildUrl(
        master_name, builder_name, build_number)

    self.assertRaisesRegexp(
        webtest.app.AppError,
        re.compile('.*501 Not Implemented.*Master &#34;%s&#34; '
                   'is not supported yet.*' % master_name,
                   re.MULTILINE | re.DOTALL),
        self.test_app.get, '/failure', params={'url': build_url})

  def testAdminCanRequestAnalysisOfFailureOnUnsupportedMaster(self):
    master_name = 'm2'
    builder_name = 'b'
    build_number = 123
    build_url = buildbot.CreateBuildUrl(
        master_name, builder_name, build_number)

    self.mock_current_user(user_email='test@chromium.org', is_admin=True)

    response = self.test_app.get('/failure', params={'url': build_url})
    self.assertEquals(200, response.status_int)

    self.assertEqual(1, len(self.taskqueue_stub.get_filtered_tasks()))

  def testAnyoneCanRequestAnalysisOfFailureOnSupportedMaster(self):
    master_name = 'm'
    builder_name = 'b 1'
    build_number = 123
    build_url = buildbot.CreateBuildUrl(
        master_name, builder_name, build_number)

    response = self.test_app.get('/failure', params={'url': build_url})
    self.assertEquals(200, response.status_int)

    self.assertEqual(1, len(self.taskqueue_stub.get_filtered_tasks()))

  def testGetOrganizedAnalysisResultBySuspectedCLNonSwarming(self):
    analysis_result = {
        'failures': [
            {
                'step_name': 'a',
                'first_failure': 98,
                'last_pass': None,
                'supported': True,
                'suspected_cls': [
                    {
                        'build_number': 99,
                        'repo_name': 'chromium',
                        'revision': 'r99_2',
                        'commit_position': None,
                        'url': None,
                        'score': 2,
                        'hints': {
                            'modified f99_2.cc (and it was in log)': 2,
                        },
                    }
                ],
            }
        ]
    }

    result = build_failure._GetOrganizedAnalysisResultBySuspectedCL(
        analysis_result)

    expected_result = {
        'a': [
            {
                'first_failure': 98,
                'last_pass': None,
                'supported': True,
                'suspected_cls': [
                    {
                        'build_number': 99,
                        'repo_name': 'chromium',
                        'revision': 'r99_2',
                        'commit_position': None,
                        'url': None,
                        'score': 2,
                        'hints': {
                            'modified f99_2.cc (and it was in log)': 2,
                        },
                    }
                ],
                'tests': []
            }
        ]
    }
    self.assertEqual(expected_result, result)

  def testGetOrganizedAnalysisResultBySuspectedCLSwarming(self):
    analysis_result = {
        'failures': [
            {
                'step_name': 'b',
                'first_failure': 98,
                'last_pass': 96,
                'supported': True,
                'suspected_cls': [
                    {
                        'build_number': 98,
                        'repo_name': 'chromium',
                        'revision': 'r98_1',
                        'commit_position': None,
                        'url': None,
                        'score': 4,
                        'hints': {
                            'modified f98.cc[123, 456] (and it was in log)': 4,
                        },
                    }
                ],
                'tests': [
                    {
                        'test_name': 'Unittest2.Subtest1',
                        'first_failure': 98,
                        'last_pass': 97,
                        'suspected_cls': [
                            {
                                'build_number': 98,
                                'repo_name': 'chromium',
                                'revision': 'r98_1',
                                'commit_position': None,
                                'url': None,
                                'score': 4,
                                'hints': {
                                    ('modified f98.cc[123] '
                                     '(and it was in log)'): 4,
                                },
                            }
                        ]
                    },
                    {
                        'test_name': 'Unittest3.Subtest2',
                        'first_failure': 98,
                        'last_pass': 96,
                        'suspected_cls': [
                            {
                                'build_number': 98,
                                'repo_name': 'chromium',
                                'revision': 'r98_1',
                                'commit_position': None,
                                'url': None,
                                'score': 4,
                                'hints': {
                                    ('modified f98.cc[456] '
                                     '(and it was in log)'): 4,
                                },
                            }
                        ]
                    },
                    {
                        'test_name': 'Unittest3.Subtest3',
                        'first_failure': 98,
                        'last_pass': 96,
                        'suspected_cls': []
                    }
                ]
            }
        ]
    }

    result = build_failure._GetOrganizedAnalysisResultBySuspectedCL(
        analysis_result)

    expected_result = {
        'b': [
            {
                'supported': True,
                'first_failure': 98,
                'last_pass': 97,
                'suspected_cls': [
                    {
                        'build_number': 98,
                        'repo_name': 'chromium',
                        'revision': 'r98_1',
                        'commit_position': None,
                        'url': None,
                        'score': 4,
                        'hints': {
                            'modified f98.cc[123, 456] (and it was in log)': 4,
                        },
                    }
                ],
                'tests': ['Unittest2.Subtest1', 'Unittest3.Subtest2']
            },
            {
                'first_failure': 98,
                'last_pass': 96,
                'supported': True,
                'suspected_cls': [],
                'tests': ['Unittest3.Subtest3']
            }
        ]
    }
    self.assertEqual(expected_result, result)

  def testGetAnalysisResultWithTryJobInfo(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 119
    organized_results = {
        'step1 on platform': [
            {
                'supported': True,
                'first_failure': 119,
                'last_pass': 118,
                'suspected_cls': [
                    {
                        'build_number': 119,
                        'repo_name': 'chromium',
                        'revision': 'r98_1',
                        'commit_position': None,
                        'url': None,
                        'score': 4,
                        'hints': {
                            'modified f98.cc[123, 456] (and it was in log)': 4,
                        },
                    }
                ],
                'tests': ['test2', 'test3']
            },
            {
                'first_failure': 119,
                'last_pass': 118,
                'supported': True,
                'suspected_cls': [],
                'tests': ['test4']
            },
            {
                'first_failure': 120,
                'last_pass': 119,
                'supported': True,
                'suspected_cls': [],
                'tests': ['test1', 'test5']
            }
        ]
    }

    updated_result = build_failure._GetAnalysisResultWithTryJobInfo(
        False, organized_results, master_name, builder_name, build_number)

    expected_result = {
        'step1 on platform': {
            'results': {
                'reliable_failures': [
                    {
                        'try_job': {
                            'ref_name': 'step1',
                            'try_job_key': 'm/b/119',
                            'task_id': 'task1',
                            'task_url': 'url/task1',
                            'status': analysis_status.COMPLETED,
                            'try_job_url': (
                                'http://build.chromium.org/p/tryserver.chromium'
                                '.linux/builders/linux_variable/builds/121'),
                            'try_job_build_number': 121,
                            'tests': ['test3'],
                            'culprit': {}
                        },
                        'heuristic_analysis': {
                            'suspected_cls': [
                                {
                                    'build_number': 119,
                                    'repo_name': 'chromium',
                                    'revision': 'r98_1',
                                    'commit_position': None,
                                    'url': None,
                                    'score': 4,
                                    'hints': {
                                        ('modified f98.cc[123, 456] '
                                         '(and it was in log)'): 4,
                                    },
                                }
                            ]
                        },
                        'tests': ['test3'],
                        'first_failure': 119,
                        'last_pass': 118,
                        'supported': True
                    },
                    {
                        'try_job': {
                            'ref_name': 'step1',
                            'try_job_key': 'm/b/119',
                            'task_id': 'task1',
                            'task_url': 'url/task1',
                            'status': analysis_status.COMPLETED,
                            'try_job_url': (
                                'http://build.chromium.org/p/tryserver.chromium'
                                '.linux/builders/linux_variable/builds/121'),
                            'try_job_build_number': 121,
                            'culprit': {
                                'revision': 'rev2',
                                'commit_position': '2',
                                'review_url': 'url_2'
                            },
                            'tests': ['test2']
                        },
                        'heuristic_analysis': {
                            'suspected_cls': [
                                {
                                    'build_number': 119,
                                    'repo_name': 'chromium',
                                    'revision': 'r98_1',
                                    'commit_position': None,
                                    'url': None,
                                    'score': 4,
                                    'hints': {
                                        ('modified f98.cc[123, 456] '
                                         '(and it was in log)'): 4,
                                    },
                                }
                            ]
                        },
                        'tests': ['test2'],
                        'first_failure': 119,
                        'last_pass': 118,
                        'supported': True
                    }
                ],
                'flaky_failures': [
                    {
                        'try_job': {
                            'ref_name': 'step1',
                            'try_job_key': 'm/b/119',
                            'status': result_status.FLAKY,
                            'task_id': 'task1',
                            'task_url': 'url/task1',
                            'tests': ['test4']
                        },
                        'heuristic_analysis': {
                            'suspected_cls': []
                        },
                        'tests': ['test4'],
                        'first_failure': 119,
                        'last_pass': 118,
                        'supported': True
                    }
                ],
                'unclassified_failures': [
                    {
                        'try_job': {
                            'ref_name': 'step1',
                            'try_job_key': 'm/b/120',
                            'status': result_status.UNKNOWN,
                            'task_id': 'task2',
                            'task_url': 'url/task2',
                            'tests': ['test5']
                        },
                        'heuristic_analysis': {
                            'suspected_cls': []
                        },
                        'tests': ['test5'],
                        'first_failure': 120,
                        'last_pass': 119,
                        'supported': True
                    },
                    {
                        'try_job': {
                            'ref_name': 'step1',
                            'try_job_key': 'm/b/120',
                            'status': result_status.NO_TRY_JOB_REASON_MAP[
                                analysis_status.PENDING],
                            'task_id': 'task2',
                            'task_url': 'url/task2',
                            'tests': ['test1']
                        },
                        'heuristic_analysis': {
                            'suspected_cls': []
                        },
                        'tests': ['test1'],
                        'first_failure': 120,
                        'last_pass': 119,
                        'supported': True
                    }
                ]
            }
        }
    }

    self.assertEqual(expected_result, updated_result)

  def testGetAnalysisResultWithTryJobInfoNoTryJobInfo(self):
    organized_results = {
        'step1 on platform': {}
    }
    result = build_failure._GetAnalysisResultWithTryJobInfo(
        False, organized_results, 'n', 'b', 120)
    self.assertEqual({}, result)

  def testGetAnalysisResultWithTryJobInfoCompile(self):
    organized_results = {
        'compile': [
            {
                'first_failure': 120,
                'last_pass': 119,
                'supported': True,
                'suspected_cls': [
                    {
                        'build_number': 120,
                        'repo_name': 'chromium',
                        'revision': 'rev2',
                        'commit_position': None,
                        'url': None,
                        'score': 2,
                        'hints': {
                            'modified f99_2.cc (and it was in log)': 2,
                        },
                    }
                ],
                'tests': []
            }
        ]
    }
    result = build_failure._GetAnalysisResultWithTryJobInfo(
        False, organized_results, 'm', 'b', 120)

    expected_result = {
        'compile': {
            'results': {
                'reliable_failures': [
                    {
                        'try_job': {
                            'try_job_key': 'm/b/120',
                            'status': analysis_status.COMPLETED,
                            'try_job_build_number': 120,
                            'try_job_url': (
                                'http://build.chromium.org/p/tryserver.chromium'
                                '.linux/builders/linux_variable/builds/120'),
                            'culprit': {
                                'revision': 'rev2',
                                'commit_position': '2',
                                'review_url': 'url_2'
                            }
                        },
                        'heuristic_analysis': {
                            'suspected_cls': [
                                {
                                    'build_number': 120,
                                    'repo_name': 'chromium',
                                    'revision': 'rev2',
                                    'commit_position': None,
                                    'url': None,
                                    'score': 2,
                                    'hints': {
                                        ('modified f99_2.cc '
                                         '(and it was in log)'): 2
                                    },
                                }
                            ]
                        },
                        'tests': [],
                        'first_failure': 120,
                        'last_pass': 119,
                        'supported': True
                    }
                ]
            }
        }
    }
    self.assertEqual(expected_result, result)

  def testPrepareTryJobDataForCompileFailure(self):
    analysis = WfAnalysis.Create('m', 'b', 123)
    analysis.result = {
        'failures': [
            {
                'step_name': 'compile',
                'first_failure': 122,
                'last_pass': 121,
                'suspected_cls': [],
            },
            {
                'step_name': 'steps',
            },
        ]
    }
    analysis.failure_result_map = {
        'compile': 'm/b/122',
    }

    try_job = WfTryJob.Create('m', 'b', 122)
    try_job.status = analysis_status.COMPLETED
    try_job.compile_results = [
        {
            'url': 'build/url',
            'culprit': {
                'compile': {
                    'revision': 'rev',
                }
            }
        }
    ]
    try_job.put()

    expected_try_job_data = {
        'status': 'completed',
        'url': 'build/url',
        'completed': True,
        'failed': False,
        'culprit': {
            'revision': 'rev',
        }
    }

    try_job_data = (
        build_failure._PrepareTryJobDataForCompileFailure(
            analysis))

    self.assertEqual(expected_try_job_data, try_job_data)

  def testPopulateHeuristicDataForCompileFailure(self):
    analysis = WfAnalysis.Create('m', 'b', 123)
    analysis.result = {
        'failures': [
            {
                'step_name': 'compile',
                'first_failure': 122,
                'last_pass': 121,
                'suspected_cls': [],
            },
            {
                'step_name': 'steps',
            },
        ]
    }
    expected_data = {
        'first_failure': 122,
        'last_pass': 121,
        'suspected_cls_by_heuristic': [],
    }

    data = {}
    build_failure._PopulateHeuristicDataForCompileFailure(
        analysis, data)
    self.assertEqual(expected_data, data)

  def _PercentFormat(self, float_number):
    return '%d%%' % (round(float_number * 100))

  def testGetTryJobResultForCompileFailure(self):
    analysis = WfAnalysis.Create('m', 'b', 123)
    analysis.result = {
        'failures': [
            {
                'step_name': 'compile',
                'first_failure': 122,
                'last_pass': 121,
                'suspected_cls': [],
            },
            {
                'step_name': 'steps',
            },
        ]
    }
    analysis.failure_result_map = {
        'compile': 'm/b/122',
    }
    analysis.status = analysis_status.COMPLETED
    analysis.suspected_cls = [
        {
            'repo_name': 'chromium',
            'revision': 'rev',
            'commit_position': 122,
            'url': None
        }
    ]
    analysis.put()

    try_job = WfTryJob.Create('m', 'b', 122)
    try_job.status = analysis_status.COMPLETED
    try_job.compile_results = [
        {
            'url': 'build/url',
            'culprit': {
                'compile': {
                    'revision': 'rev',
                }
            }
        }
    ]
    try_job.put()

    suspected_cl = WfSuspectedCL.Create('chromium', 'rev', 122)
    suspected_cl.builds = {
        'm/b/123': {
            'failure_type': failure_type.COMPILE,
            'failures': None,
            'status': suspected_cl_status.CORRECT,
            'approaches': [analysis_approach_type.HEURISTIC,
                           analysis_approach_type.TRY_JOB],
            'top_score': 5
        }
    }
    suspected_cl.put()

    expected_try_job_result = {
        'status': 'completed',
        'url': 'build/url',
        'completed': True,
        'culprit': {
            'revision': 'rev',
        },
        'failed': False,
    }

    expected_suspected_cls = [
        {
            'repo_name': 'chromium',
            'revision': 'rev',
            'commit_position': 122,
            'url': None,
            'status': suspected_cl_status.CORRECT,
            'confidence': self._PercentFormat(
                self.cl_confidences.compile_heuristic_try_job.confidence)
        }
    ]

    build_url = buildbot.CreateBuildUrl('m', 'b', 123)
    response = self.test_app.get('/failure',
                                 params={'url': build_url, 'format': 'json'})

    self.assertEquals(200, response.status_int)
    self.assertEqual(expected_try_job_result, response.json_body['try_job'])
    self.assertEqual(
        expected_suspected_cls, response.json_body['suspected_cls'])

  def testGetAllSuspectedCLsAndCheckStatus(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.suspected_cls = [
        {
            'repo_name': 'chromium',
            'revision': 'rev',
            'commit_position': 122,
            'url': None
        }
    ]
    analysis.put()
    suspected_cl = WfSuspectedCL.Create('chromium', 'rev', 122)
    suspected_cl.builds = {
        'm/b/122': {
            'failure_type': failure_type.COMPILE,
            'failures': None,
            'status': suspected_cl_status.CORRECT,
            'approaches': [analysis_approach_type.TRY_JOB],
            'top_score': 5
        }
    }
    suspected_cl.put()

    expected_suspected_cls = [
        {
            'repo_name': 'chromium',
            'revision': 'rev',
            'commit_position': 122,
            'url': None,
            'status': None,
            'confidence': None
        }
    ]

    suspected_cls = build_failure._GetAllSuspectedCLsAndCheckStatus(
        master_name, builder_name, build_number, analysis)
    self.assertEqual(
        expected_suspected_cls, suspected_cls)
