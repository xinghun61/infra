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
HEURISTIC = 'heuristic analysis'
TRY_JOB =  'try job'

SAMPLE_RESULT = {
    'failures': [
        {
            'tests': [{
                'last_pass': 120,
                'first_failure': 121,
                'suspected_cls': [{
                    'build_number': 121,
                    'repo_name': 'chromium',
                    'url': 'https://codereview.chromium.org/123',
                    'score': 5,
                    'commit_position': 123,
                    'hints': {
                        'modified a.cc[253] (and it was in log)': 4,
                        'modified a_unittest.cc (a.cc was in log)': 1
                    },
                    'revision': 'revison_123'
                }],
                'test_name': 'test1'
            }],
            'first_failure': 121,
            'supported': True,
            'suspected_cls': [{
                'build_number': 121,
                'repo_name': 'chromium',
                'url': 'https://codereview.chromium.org/123',
                'score': 5,
                'commit_position': 123,
                'hints': {
                    'modified a.cc[253] (and it was in log)': 4,
                    'modified a_unittest.cc (a.cc was in log)': 1
                },
                'revision': 'revison_123'
            }],
            'step_name': 'a_tests',
            'last_pass': 120
        },
        {
            'suspected_cls':[],
            'last_pass':120,
            'supported':True,
            'first_failure':121,
            'step_name':'b_tests'
        },
        {
            'tests': [
                {
                    'last_pass': 120,
                    'first_failure': 121,
                    'suspected_cls': [{
                        'build_number': 121,
                        'repo_name': 'chromium',
                        'url': 'https://codereview.chromium.org/123',
                        'score': 5,
                        'commit_position': 123,
                        'hints': {
                            'modified a.cc[253] (and it was in log)': 4,
                            'modified a_unittest.cc (a.cc was in log)': 1
                        },
                        'revision': 'revison_123'
                    }],
                    'test_name': 'test1'
                },
                {
                    'last_pass': 120,
                    'first_failure': 121,
                    'suspected_cls': [{
                        'build_number': 121,
                        'repo_name': 'chromium',
                        'url': 'https://codereview.chromium.org/123',
                        'score': 5,
                        'commit_position': 123,
                        'hints': {
                            'modified a.cc[253] (and it was in log)': 4,
                            'modified a_unittest.cc (a.cc was in log)': 1
                        },
                        'revision': 'revison_123'
                    }],
                    'test_name': 'test2'
                },
                {
                    'last_pass': 120,
                    'first_failure': 121,
                    'suspected_cls': [{
                        'build_number': 121,
                        'repo_name': 'chromium',
                        'url': 'https://codereview.chromium.org/123',
                        'score': 5,
                        'commit_position': 123,
                        'hints': {
                            'modified a.cc[253] (and it was in log)': 4,
                            'modified a_unittest.cc (a.cc was in log)': 1
                        },
                        'revision': 'revison_123'
                    }],
                    'test_name': 'test3'
                }
            ],
            'first_failure': 121,
            'supported': True,
            'suspected_cls': [{
                'build_number': 121,
                'repo_name': 'chromium',
                'url': 'https://codereview.chromium.org/123',
                'score': 5,
                'commit_position': 123,
                'hints': {
                    'modified a.cc[253] (and it was in log)': 4,
                    'modified a_unittest.cc (a.cc was in log)': 1
                },
                'revision': 'revison_123'
            }],
            'step_name': 'c_tests',
            'last_pass': 120
        },
        {
            'suspected_cls':[],
            'last_pass':120,
            'supported':True,
            'first_failure':121,
            'step_name':'d_tests'
        }
    ]
}


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
                   re.MULTILINE | re.DOTALL),
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
                                 params={'url': build_url})
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
                   re.MULTILINE | re.DOTALL),
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

  def testUpdateAnalysisResultWithSwarmingTask(self):
    result = SAMPLE_RESULT
    task_info = {
        'a_tests': {
            'swarming_tasks': [
                {
                    'status': 'Pending'
                }
            ],
            'tests': {
                'test1': {
                    'status': 'Pending'
                }
            }
        },
        'c_tests': {
            'swarming_tasks': [
                {
                    'status': 'Pending'
                },
                {
                    'status': 'Completed',
                    'task_id': 'task1',
                    'task_url': (
                        'https://chromium-swarm.appspot.com/user/task/task1')
                }
            ],
            'tests': {
                'test1': {
                    'status': 'Pending'
                },
                'test2': {
                    'status': 'Completed',
                    'task_id': 'task1',
                    'task_url': (
                        'https://chromium-swarm.appspot.com/user/task/task1')
                }
            }
        }
    }

    build_failure._UpdateAnalysisResultWithSwarmingTask(result, task_info)

    expected_updated_result = {
        'failures': [
            {
                'tests': [{
                    'last_pass': 120,
                    'first_failure': 121,
                    'suspected_cls': [{
                        'build_number': 121,
                        'repo_name': 'chromium',
                        'url': 'https://codereview.chromium.org/123',
                        'score': 5,
                        'commit_position': 123,
                        'hints': {
                            'modified a.cc[253] (and it was in log)': 4,
                            'modified a_unittest.cc (a.cc was in log)': 1
                        },
                        'revision': 'revison_123'
                    }],
                    'test_name': 'test1',
                    'swarming_task': {
                        'status': 'Pending'
                    }
                }],
                'first_failure': 121,
                'supported': True,
                'suspected_cls': [{
                    'build_number': 121,
                    'repo_name': 'chromium',
                    'url': 'https://codereview.chromium.org/123',
                    'score': 5,
                    'commit_position': 123,
                    'hints': {
                        'modified a.cc[253] (and it was in log)': 4,
                        'modified a_unittest.cc (a.cc was in log)': 1
                    },
                    'revision': 'revison_123'
                }],
                'step_name': 'a_tests',
                'last_pass': 120,
                'swarming_task': {
                    'status': 'Pending'
                }
            },
            {
                'suspected_cls':[],
                'last_pass':120,
                'supported':True,
                'first_failure':121,
                'step_name':'b_tests'
            },
            {
                'tests': [
                    {
                        'last_pass': 120,
                        'first_failure': 121,
                        'suspected_cls': [{
                            'build_number': 121,
                            'repo_name': 'chromium',
                            'url': 'https://codereview.chromium.org/123',
                            'score': 5,
                            'commit_position': 123,
                            'hints': {
                                'modified a.cc[253] (and it was in log)': 4,
                                'modified a_unittest.cc (a.cc was in log)': 1
                            },
                            'revision': 'revison_123'
                        }],
                        'test_name': 'test1',
                        'swarming_task': {
                            'status': 'Pending'
                        }
                    },
                    {
                        'last_pass': 120,
                        'first_failure': 121,
                        'suspected_cls': [{
                            'build_number': 121,
                            'repo_name': 'chromium',
                            'url': 'https://codereview.chromium.org/123',
                            'score': 5,
                            'commit_position': 123,
                            'hints': {
                                'modified a.cc[253] (and it was in log)': 4,
                                'modified a_unittest.cc (a.cc was in log)': 1
                            },
                            'revision': 'revison_123'
                        }],
                        'test_name': 'test2',
                        'swarming_task': {
                            'status': 'Completed',
                            'task_id': 'task1',
                            'task_url': ('https://chromium-swarm.appspot.com/'
                                         'user/task/task1')
                        }
                    },
                    {
                        'last_pass': 120,
                        'first_failure': 121,
                        'suspected_cls': [{
                            'build_number': 121,
                            'repo_name': 'chromium',
                            'url': 'https://codereview.chromium.org/123',
                            'score': 5,
                            'commit_position': 123,
                            'hints': {
                                'modified a.cc[253] (and it was in log)': 4,
                                'modified a_unittest.cc (a.cc was in log)': 1
                            },
                            'revision': 'revison_123'
                        }],
                        'test_name': 'test3'
                    }
                ],
                'first_failure': 121,
                'supported': True,
                'suspected_cls': [{
                    'build_number': 121,
                    'repo_name': 'chromium',
                    'url': 'https://codereview.chromium.org/123',
                    'score': 5,
                    'commit_position': 123,
                    'hints': {
                        'modified a.cc[253] (and it was in log)': 4,
                        'modified a_unittest.cc (a.cc was in log)': 1
                    },
                    'revision': 'revison_123'
                }],
                'step_name': 'c_tests',
                'last_pass': 120,
                'swarming_task': 'multiple'
            },
            {
                'suspected_cls':[],
                'last_pass':120,
                'supported':True,
                'first_failure':121,
                'step_name':'d_tests'
            }
        ]
    }

    self.assertEqual(result, expected_updated_result)

  def testUpdateAnalysisResultWithTryJob(self):
    result = SAMPLE_RESULT
    try_jobs_info = {
        'a_tests-test1': {
            'step': 'a_tests',
            'test': 'test1',
            'try_job_key': 'm/b/121',
            'try_job_build_number': 121,
            'status': 'Completed',
            'try_job_url': 'url/121',
            'revision': 'revison_122',
            'commit_position': 122,
            'review_url': 'https://codereview.chromium.org/122'
        },
        'b_tests': {
            'step': 'b_tests',
            'test': 'N/A',
            'try_job_key': 'm/b/121',
            'try_job_build_number': 121,
            'status': 'Completed',
            'try_job_url': 'url/121',
            'revision': 'revison_123',
            'commit_position': 123,
            'review_url': 'https://codereview.chromium.org/123'
        },
        'c_tests-test1': {
            'step': 'c_tests',
            'test': 'test1',
            'try_job_key': 'm/b/122',
            'status': 'Running',
            'try_job_build_number': 122,
            'try_job_url': 'url/122'
        },
        'c_tests-test2': {
            'step': 'c_tests',
            'test': 'test2',
            'try_job_key': 'm/b/121',
            'try_job_build_number': 121,
            'status': 'Completed',
            'try_job_url': 'url/121',
            'revision': 'revison_123',
            'commit_position': 123,
            'review_url': 'https://codereview.chromium.org/123'
        }
    }

    build_failure._UpdateAnalysisResultWithTryJob(result, try_jobs_info)

    expected_updated_result = {
        'failures': [
            {
                'tests': [
                    {
                        'last_pass': 120,
                        'first_failure': 121,
                        'suspected_cls': [
                            {
                                'build_number': 121,
                                'repo_name': 'chromium',
                                'url': 'https://codereview.chromium.org/123',
                                'score': 5,
                                'commit_position': 123,
                                'hints': {
                                    'modified a.cc[253] (and it was in log)': 4,
                                    'modified a_unittest.cc (a.cc was in log)':
                                        1
                                },
                                'revision': 'revison_123',
                                'result_source': [HEURISTIC]
                            },
                            {
                                'step': 'a_tests',
                                'test': 'test1',
                                'try_job_key': 'm/b/121',
                                'try_job_build_number': 121,
                                'status': 'Completed',
                                'try_job_url': 'url/121',
                                'revision': 'revison_122',
                                'commit_position': 122,
                                'review_url': (
                                    'https://codereview.chromium.org/122'),
                                'hints': {
                                    ('found by try job <a href="url/121"> 121 '
                                     '</a>'): 5
                                },
                                'score': 5,
                                'build_number': 121,
                                'repo_name': 'chromium',
                                'result_source': [TRY_JOB]
                            }
                        ],
                        'test_name': 'test1'
                    }
                ],
                'first_failure': 121,
                'supported': True,
                'suspected_cls': [
                    {
                        'build_number': 121,
                        'repo_name': 'chromium',
                        'url': 'https://codereview.chromium.org/123',
                        'score': 5,
                        'commit_position': 123,
                        'hints': {
                            'modified a.cc[253] (and it was in log)': 4,
                            'modified a_unittest.cc (a.cc was in log)':
                                1
                        },
                        'revision': 'revison_123',
                        'result_source': [HEURISTIC]
                    },
                    {
                        'step': 'a_tests',
                        'test': 'test1',
                        'try_job_key': 'm/b/121',
                        'try_job_build_number': 121,
                        'status': 'Completed',
                        'try_job_url': 'url/121',
                        'revision': 'revison_122',
                        'commit_position': 122,
                        'review_url': 'https://codereview.chromium.org/122',
                        'hints': {
                            'found by try job <a href="url/121"> 121 </a>': 5
                        },
                        'score': 5,
                        'build_number': 121,
                        'repo_name': 'chromium',
                        'result_source': [TRY_JOB]
                    }
                ],
                'step_name': 'a_tests',
                'last_pass': 120
            },
            {
                'suspected_cls':[{
                    'step': 'b_tests',
                    'test': 'N/A',
                    'try_job_key': 'm/b/121',
                    'try_job_build_number': 121,
                    'status': 'Completed',
                    'try_job_url': 'url/121',
                    'revision': 'revison_123',
                    'commit_position': 123,
                    'review_url': 'https://codereview.chromium.org/123',
                    'repo_name': 'chromium',
                    'score': 5,
                    'hints': {
                        'found by try job <a href="url/121"> 121 </a>': 5
                    },
                    'result_source': [TRY_JOB],
                    'build_number': 121
                }],
                'last_pass':120,
                'supported':True,
                'first_failure':121,
                'step_name':'b_tests'
            },
            {
                'tests': [
                    {
                        'last_pass': 120,
                        'first_failure': 121,
                        'suspected_cls': [
                            {
                                'build_number': 121,
                                'repo_name': 'chromium',
                                'url': 'https://codereview.chromium.org/123',
                                'score': 5,
                                'commit_position': 123,
                                'hints': {
                                    'modified a.cc[253] (and it was in log)': 4,
                                    'modified a_unittest.cc (a.cc was in log)':
                                        1
                                },
                                'revision': 'revison_123',
                                'result_source': [HEURISTIC]
                            },
                            {
                                'step': 'c_tests',
                                'test': 'test1',
                                'try_job_key': 'm/b/122',
                                'status': 'Running',
                                'try_job_build_number': 122,
                                'try_job_url': 'url/122',
                                'result_source': [TRY_JOB]
                            }
                        ],
                        'test_name': 'test1'
                    },
                    {
                        'last_pass': 120,
                        'first_failure': 121,
                        'suspected_cls': [{
                            'build_number': 121,
                            'repo_name': 'chromium',
                            'url': 'https://codereview.chromium.org/123',
                            'score': 10,
                            'commit_position': 123,
                            'hints': {
                                'modified a.cc[253] (and it was in log)': 4,
                                'modified a_unittest.cc (a.cc was in log)': 1,
                                'found by try job <a href="url/121"> 121 </a>':
                                    5
                            },
                            'revision': 'revison_123',
                            'result_source': [HEURISTIC, TRY_JOB],
                            'status': 'Completed',
                            'try_job_build_number': 121,
                            'try_job_url': 'url/121',
                            'try_job_key': 'm/b/121'
                        }],
                        'test_name': 'test2'
                    },
                    {
                        'last_pass': 120,
                        'first_failure': 121,
                        'suspected_cls': [{
                            'build_number': 121,
                            'repo_name': 'chromium',
                            'url': 'https://codereview.chromium.org/123',
                            'score': 5,
                            'commit_position': 123,
                            'hints': {
                                'modified a.cc[253] (and it was in log)': 4,
                                'modified a_unittest.cc (a.cc was in log)': 1
                            },
                            'revision': 'revison_123',
                            'result_source': [HEURISTIC]
                        }],
                        'test_name': 'test3'
                    }
                ],
                'first_failure': 121,
                'supported': True,
                'suspected_cls': [
                    {
                        'build_number': 121,
                        'repo_name': 'chromium',
                        'url': 'https://codereview.chromium.org/123',
                        'score': 10,
                        'commit_position': 123,
                        'hints': {
                            'modified a.cc[253] (and it was in log)': 4,
                            'modified a_unittest.cc (a.cc was in log)': 1,
                            'found by try job <a href="url/121"> 121 </a>': 5
                        },
                        'revision': 'revison_123',
                        'result_source': [HEURISTIC, TRY_JOB],
                        'status': 'Completed',
                        'try_job_build_number': 121,
                        'try_job_url': 'url/121',
                        'try_job_key': 'm/b/121'
                    },
                    {
                        'step': 'c_tests',
                        'test': 'test1',
                        'try_job_key': 'm/b/122',
                        'status': 'Running',
                        'try_job_build_number': 122,
                        'try_job_url': 'url/122',
                        'result_source': [TRY_JOB]
                    }
                ],
                'step_name': 'c_tests',
                'last_pass': 120
            },
            {
                'suspected_cls':[],
                'last_pass':120,
                'supported':True,
                'first_failure':121,
                'step_name':'d_tests'
            }
        ]
    }
    self.assertEqual(result, expected_updated_result)

  def testUpdateAnalysisResultWithSwarmingTaskEmptyTaskInfo(self):
    result = SAMPLE_RESULT
    task_info = {
        'a_tests': {
            'tests': {},
            'swarming_tasks': []
        }
    }

    build_failure._UpdateAnalysisResultWithSwarmingTask(result, task_info)

    self.assertEqual(result, SAMPLE_RESULT)

  def testGenerateTryJobHintNoUrl(self):
    self.assertIsNone(build_failure._GenerateTryJobHint(None, None))
