# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import webapp2

from testing_utils import testing

from handlers import try_job_result
from model.wf_analysis import WfAnalysis
from model import wf_analysis_status
from model.wf_try_job import WfTryJob
from waterfall import buildbot


class TryJobResultTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication([
      ('/try-job-result', try_job_result.TryJobResult),], debug=True)

  def setUp(self):
    super(TryJobResultTest, self).setUp()
    self.master_name = 'm'
    self.builder_name = 'b'
    self.build_number = 121
    self.mock_current_user(user_email='test@chromium.org', is_admin=True)

  def testGetTryJobResultReturnNoneIfNoFailureResultMap(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.put()

    result = try_job_result._GetAllTryJobResults(
        self.master_name, self.builder_name, self.build_number)

    self.assertEqual({}, result)

  def testGetTryJobResultReturnNoneIfNoTryJob(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.failure_result_map = {
        'compile': 'm/b/121'
    }
    analysis.put()

    result = try_job_result._GetAllTryJobResults(
        self.master_name, self.builder_name, self.build_number)

    expected_result = {
        'compile': {
            'step': 'compile',
            'test': 'N/A',
            'try_job_key': 'm/b/121'
        }
    }

    self.assertEqual(expected_result, result)

  def testGetTryJobResultOnlyReturnStatusIfPending(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.failure_result_map = {
        'compile': 'm/b/121'
    }
    analysis.put()

    try_job = WfTryJob.Create(
        self.master_name, self.builder_name, self.build_number)
    try_job.put()

    result = try_job_result._GetAllTryJobResults(
        self.master_name, self.builder_name, self.build_number)

    expected_result = {
        'compile': {
            'step': 'compile',
            'test': 'N/A',
            'try_job_key': 'm/b/121',
            'status': 'Pending'
        }
    }

    self.assertEqual(expected_result, result)

  def testGetTryJobResultOnlyReturnUrlIfStarts(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.failure_result_map = {
        'compile': 'm/b/121'
    }
    analysis.put()

    try_job = WfTryJob.Create(
        self.master_name, self.builder_name, self.build_number)
    try_job.status = wf_analysis_status.ANALYZING
    try_job.compile_results = [
        {
            'result': None,
            'url': ('http://build.chromium.org/p/tryserver.chromium.linux/'
                    'builders/linux_chromium_variable/builds/121')
        }
    ]
    try_job.put()

    result = try_job_result._GetAllTryJobResults(
        self.master_name, self.builder_name, self.build_number)

    expected_result = {
        'compile': {
            'step': 'compile',
            'test': 'N/A',
            'try_job_key': 'm/b/121',
            'status': 'Running',
            'try_job_build_number': 121,
            'try_job_url': ('http://build.chromium.org/p/tryserver.chromium.'
                            'linux/builders/linux_chromium_variable/builds/121')
        }
    }
    self.assertEqual(expected_result, result)

  def testGetTryJobResultOnlyReturnStatusIfError(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.failure_result_map = {
        'compile': 'm/b/121'
    }
    analysis.put()

    try_job = WfTryJob.Create(
        self.master_name, self.builder_name, self.build_number)
    try_job.status = wf_analysis_status.ERROR
    try_job.compile_results = [
        {
            'try_job_id': '1'
        }
    ]
    try_job.put()

    result = try_job_result._GetAllTryJobResults(
        self.master_name, self.builder_name, self.build_number)

    expected_result = {
        'compile': {
            'step': 'compile',
            'test': 'N/A',
            'try_job_key': 'm/b/121',
            'status': 'Error'
        }
    }

    self.assertEqual(expected_result, result)

  def testGetTryJobResultWhenTryJobCompleted(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.failure_result_map = {
        'compile': 'm/b/121'
    }
    analysis.put()

    try_job = WfTryJob.Create(
        self.master_name, self.builder_name, self.build_number)
    try_job.status = wf_analysis_status.ANALYZED
    try_job.compile_results = [
        {
            'result': [
                ['rev1', 'passed'],
                ['rev2', 'failed']
            ],
            'url': ('http://build.chromium.org/p/tryserver.chromium.linux/'
                    'builders/linux_chromium_variable/builds/121'),
            'try_job_id': '1',
            'culprit': {
                'compile': {
                    'revision': 'rev2',
                    'commit_position': '2',
                    'review_url': 'url_2'
                }
            }
        }
    ]
    try_job.put()

    result = try_job_result._GetAllTryJobResults(
        self.master_name, self.builder_name, self.build_number)

    expected_result = {
        'compile': {
            'step': 'compile',
            'test': 'N/A',
            'try_job_key': 'm/b/121',
            'try_job_build_number': 121,
            'status': 'Completed',
            'try_job_url': (
                'http://build.chromium.org/p/tryserver.chromium.linux/'
                'builders/linux_chromium_variable/builds/121'),
            'revision': 'rev2',
            'commit_position': '2',
            'review_url': 'url_2'
        }
    }

    self.assertEqual(expected_result, result)

  def testGetTryJobResultWhenTryJobCompletedAllPassed(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.failure_result_map = {
        'compile': 'm/b/121'
    }
    analysis.put()

    try_job = WfTryJob.Create(
        self.master_name, self.builder_name, self.build_number)
    try_job.status = wf_analysis_status.ANALYZED
    try_job.compile_results = [
        {
            'result': [
                ['rev1', 'passed'],
                ['rev2', 'passed']
            ],
            'url': ('http://build.chromium.org/p/tryserver.chromium.linux/'
                    'builders/linux_chromium_variable/builds/121')
        }
    ]
    try_job.put()

    result = try_job_result._GetAllTryJobResults(
        self.master_name, self.builder_name, self.build_number)

    expected_result = {
        'compile': {
            'step': 'compile',
            'test': 'N/A',
            'try_job_key': 'm/b/121',
            'try_job_build_number': 121,
            'status': 'Completed',
            'try_job_url': (
                'http://build.chromium.org/p/tryserver.chromium.linux/'
                'builders/linux_chromium_variable/builds/121')
        }
    }

    self.assertEqual(expected_result, result)

  def testTryJobResultHandler(self):
    build_url = buildbot.CreateBuildUrl(
        self.master_name, self.builder_name, self.build_number)
    response = self.test_app.get('/try-job-result', params={'url': build_url})
    expected_results = {}

    self.assertEqual(200, response.status_int)
    self.assertEqual(expected_results, response.json_body)

  def testGetTryJobResultWhenTryJobForTestCompleted(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.failure_result_map = {
        'a_test': {
            'a_test1': 'm/b/121',
            'a_test2': 'm/b/121',
            'a_test3': 'm/b/120'
        },
        'b_test': {
            'b_test1': 'm/b/121'
        },
        'c_test': 'm/b/121',
        'd_test': 'm/b/122'
    }
    analysis.put()

    try_job_120 = WfTryJob.Create(
        self.master_name, self.builder_name, 120)
    try_job_120.status = wf_analysis_status.ANALYZED
    try_job_120.test_results = [
        {
            'result': {
                'rev0': {
                    'a_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['a_test3']
                    }
                }
            },
            'url': ('http://build.chromium.org/p/tryserver.chromium.linux/'
                    'builders/linux_chromium_variable/builds/120'),
            'try_job_id': '0',
            'culprit': {
                'a_test': {
                    'tests': {
                        'a_test3': {
                            'revision': 'rev0',
                            'commit_position': '0',
                            'review_url': 'url_0'
                        }
                    }
                }
            }
        }
    ]
    try_job_120.put()

    try_job_121 = WfTryJob.Create(
        self.master_name, self.builder_name, self.build_number)
    try_job_121.status = wf_analysis_status.ANALYZED
    try_job_121.test_results = [
        {
            'result': {
                'rev1': {
                    'a_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['a_test1']
                    },
                    'b_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['b_test1']
                    },
                    'c_test': {
                        'status': 'passed',
                        'valid': True
                    }
                },
                'rev2': {
                    'a_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['a_test1']
                    },
                    'b_test': {
                        'status': 'passed',
                        'valid': True
                    },
                    'c_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': []
                    }
                }
            },
            'url': ('http://build.chromium.org/p/tryserver.chromium.linux/'
                    'builders/linux_chromium_variable/builds/121'),
            'try_job_id': '1',
            'culprit': {
                'a_test': {
                    'tests': {
                        'a_test1': {
                            'revision': 'rev1',
                            'commit_position': '1',
                            'review_url': 'url_1'
                        }
                    }
                },
                'b_test': {
                    'tests': {
                        'b_test1': {
                            'revision': 'rev1',
                            'commit_position': '1',
                            'review_url': 'url_1'
                        }
                    }
                },
                'c_test': {
                    'revision': 'rev2',
                    'commit_position': '2',
                    'review_url': 'url_2',
                    'tests': {}
                }
            }
        }
    ]
    try_job_121.put()

    try_job_122 = WfTryJob.Create(
        self.master_name, self.builder_name, 122)
    try_job_122.status = wf_analysis_status.ANALYZED
    try_job_122.test_results = [
        {
            'result': {
                'rev3': {
                    'd_test': {
                        'status': 'passed',
                        'valid': True,
                        'failures': []
                    }
                }
            },
            'url': ('http://build.chromium.org/p/tryserver.chromium.linux/'
                    'builders/linux_chromium_variable/builds/122'),
            'try_job_id': '2'
        }
    ]
    try_job_122.put()

    result = try_job_result._GetAllTryJobResults(
        self.master_name, self.builder_name, self.build_number)

    expected_result = {
        'a_test-a_test1': {
            'step': 'a_test',
            'test': 'a_test1',
            'try_job_key': 'm/b/121',
            'try_job_build_number': 121,
            'status': 'Completed',
            'try_job_url': (
                'http://build.chromium.org/p/tryserver.chromium.linux/'
                'builders/linux_chromium_variable/builds/121'),
            'revision': 'rev1',
            'commit_position': '1',
            'review_url': 'url_1'
        },
        'a_test-a_test2': {
            'step': 'a_test',
            'test': 'a_test2',
            'try_job_key': 'm/b/121',
            'status': 'Completed',
            'try_job_build_number': 121,
            'try_job_url': (
                'http://build.chromium.org/p/tryserver.chromium.linux/'
                'builders/linux_chromium_variable/builds/121'),
        },
        'a_test-a_test3': {
            'step': 'a_test',
            'test': 'a_test3',
            'try_job_key': 'm/b/120',
            'try_job_build_number': 120,
            'status': 'Completed',
            'try_job_url': (
                'http://build.chromium.org/p/tryserver.chromium.linux/'
                'builders/linux_chromium_variable/builds/120'),
            'revision': 'rev0',
            'commit_position': '0',
            'review_url': 'url_0'
        },
        'b_test-b_test1': {
            'step': 'b_test',
            'test': 'b_test1',
            'try_job_key': 'm/b/121',
            'try_job_build_number': 121,
            'status': 'Completed',
            'try_job_url': (
                'http://build.chromium.org/p/tryserver.chromium.linux/'
                'builders/linux_chromium_variable/builds/121'),
            'revision': 'rev1',
            'commit_position': '1',
            'review_url': 'url_1'
        },
        'c_test': {
            'step': 'c_test',
            'test': 'N/A',
            'try_job_key': 'm/b/121',
            'try_job_build_number': 121,
            'status': 'Completed',
            'try_job_url': (
                'http://build.chromium.org/p/tryserver.chromium.linux/'
                'builders/linux_chromium_variable/builds/121'),
            'revision': 'rev2',
            'commit_position': '2',
            'review_url': 'url_2'
        },
        'd_test': {
            'step': 'd_test',
            'test': 'N/A',
            'try_job_key': 'm/b/122',
            'try_job_build_number': 122,
            'status': 'Completed',
            'try_job_url': (
                'http://build.chromium.org/p/tryserver.chromium.linux/'
                'builders/linux_chromium_variable/builds/122')
        }
    }
    print json.dumps(result, indent=4, sort_keys=True)
    print json.dumps(expected_result, indent=4, sort_keys=True)
    self.assertEqual(expected_result, result)
