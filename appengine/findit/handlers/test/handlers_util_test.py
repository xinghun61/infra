# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

from handlers import handlers_util
from model.wf_analysis import WfAnalysis
from model import wf_analysis_status
from model.wf_swarming_task import WfSwarmingTask
from model.wf_try_job import WfTryJob
from waterfall import buildbot
from waterfall import waterfall_config


class HandlersUtilResultTest(testing.AppengineTestCase):

  def setUp(self):
    super(HandlersUtilResultTest, self).setUp()
    self.master_name = 'm'
    self.builder_name = 'b'
    self.build_number = 121

    def MockedGetSwarmingSettings():
      return {'server_host': 'chromium-swarm.appspot.com'}
    self.mock(
        waterfall_config, 'GetSwarmingSettings', MockedGetSwarmingSettings)

  def testGenerateSwarmingTasksDataNoAnalysis(self):
    data = handlers_util.GenerateSwarmingTasksData(
        self.master_name, self.builder_name, self.build_number)

    self.assertEqual({}, data)

  def testGenerateSwarmingTasksDataReturnEmptyIfNoFailureMap(self):
    WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number).put()

    data = handlers_util.GenerateSwarmingTasksData(
        self.master_name, self.builder_name, self.build_number)

    self.assertEqual({}, data)

  def testGenerateSwarmingTasksDataReturnEmptyIfNoSwarmingTests(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.failure_result_map = {
        'step1': '%s/%s/%s' % (self.master_name, self.builder_name, 120),
        'step2': '%s/%s/%s' % (
            self.master_name, self.builder_name, self.build_number)
    }
    analysis.put()

    data = handlers_util.GenerateSwarmingTasksData(
        self.master_name, self.builder_name, self.build_number)

    self.assertEqual({}, data)

  def testGenerateSwarmingTasksDataIfNoSwarmingTask(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.failure_result_map = {
        'step1': {
            'test1': '%s/%s/%s' % (self.master_name, self.builder_name, 120),
            'test2': '%s/%s/%s' % (
                self.master_name, self.builder_name, self.build_number)
        },
        'step2': {
            'test1': '%s/%s/%s' % (self.master_name, self.builder_name, 120)
        }
    }
    analysis.put()

    data = handlers_util.GenerateSwarmingTasksData(
        self.master_name, self.builder_name, self.build_number)

    expected_data = {
        'step1': {
            'swarming_tasks': [],
            'tests': {}
        },
        'step2': {
            'swarming_tasks': [],
            'tests': {}
        }
    }
    self.assertEqual(expected_data, data)

  def testGenerateSwarmingTasksData(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.failure_result_map = {
        'step1': {
            'test1': '%s/%s/%s' % (self.master_name, self.builder_name, 120),
            'test2': '%s/%s/%s' % (
                self.master_name, self.builder_name, self.build_number)
        },
        'step2': {
            'test1': '%s/%s/%s' % (
                self.master_name, self.builder_name, self.build_number)
        }
    }
    analysis.put()

    task0 = WfSwarmingTask.Create(
        self.master_name, self.builder_name, 120, 'step1')
    task0.task_id = 'task0'
    task0.status = wf_analysis_status.ANALYZED
    task0.put()

    task1 = WfSwarmingTask.Create(
        self.master_name, self.builder_name, self.build_number, 'step1')
    task1.task_id = 'task1'
    task1.status = wf_analysis_status.ANALYZED
    task1.put()

    task2 = WfSwarmingTask.Create(
        self.master_name, self.builder_name, self.build_number, 'step2')
    task2.put()

    data = handlers_util.GenerateSwarmingTasksData(
        self.master_name, self.builder_name, self.build_number)

    expected_data = {
        'step1': {
            'swarming_tasks': [
                {
                    'status': 'Completed',
                    'task_id': 'task1',
                    'task_url': (
                        'https://chromium-swarm.appspot.com/user/task/task1')
                },
                {
                    'status': 'Completed',
                    'task_id': 'task0',
                    'task_url': (
                        'https://chromium-swarm.appspot.com/user/task/task0')
                }
            ],
            'tests': {
                'test1': {
                    'status': 'Completed',
                    'task_id': 'task0',
                    'task_url': (
                        'https://chromium-swarm.appspot.com/user/task/task0')
                },
                'test2': {
                    'status': 'Completed',
                    'task_id': 'task1',
                    'task_url': (
                        'https://chromium-swarm.appspot.com/user/task/task1')
                }
            }
        },
        'step2': {
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
        }
    }
    self.assertEqual(expected_data, data)

  def testGetAllTryJobResultsNoAnalysis(self):
    data = handlers_util.GetAllTryJobResults(
        self.master_name, self.builder_name, self.build_number)

    self.assertEqual({}, data)

  def testGetTryJobResultReturnNoneIfNoFailureResultMap(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.put()

    result = handlers_util.GetAllTryJobResults(
        self.master_name, self.builder_name, self.build_number)

    self.assertEqual({}, result)

  def testGetTryJobResultReturnNoneIfNoTryJob(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.failure_result_map = {
        'compile': 'm/b/121'
    }
    analysis.put()

    result = handlers_util.GetAllTryJobResults(
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

    result = handlers_util.GetAllTryJobResults(
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

    result = handlers_util.GetAllTryJobResults(
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

    result = handlers_util.GetAllTryJobResults(
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

    result = handlers_util.GetAllTryJobResults(
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

    result = handlers_util.GetAllTryJobResults(
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

  def testGetTryJobResultWhenTryJobForTestCompleted(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.failure_result_map = {
        'a_test': {
            'a_test1': 'm/b/121',
            'a_test2': 'm/b/121',
            'a_test3': 'm/b/120',
            'a_test4': 'm/b/121'
        },
        'b_test': {
            'b_test1': 'm/b/121'
        },
        'c_test': 'm/b/121',
        'd_test': 'm/b/122'
    }
    analysis.put()

    task_120_a = WfSwarmingTask.Create(
        self.master_name, self.builder_name, 120, 'a_test')
    task_120_a.tests_statuses = {
        'a_test3': {
            'total_run': 1,
            'FAILURE': 1
        }
    }
    task_120_a.put()

    task_121_a = WfSwarmingTask.Create(
        self.master_name, self.builder_name, self.build_number, 'a_test')
    task_121_a.tests_statuses = {
        'a_test1': {
            'total_run': 1,
            'FAILURE': 1
        },
        'a_test2': {
            'total_run': 1,
            'FAILURE': 1
        },
        'a_test4': {
            'total_run': 1,
            'SUCCESS': 1
        }
    }
    task_121_a.put()

    task_121_b = WfSwarmingTask.Create(
        self.master_name, self.builder_name, self.build_number, 'b_test')
    task_121_b.tests_statuses = {
        'b_test1': {
            'total_run': 1,
            'SUCCESS': 1
        }
    }
    task_121_b.put()

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

    result = handlers_util.GetAllTryJobResults(
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
                'builders/linux_chromium_variable/builds/121')
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
        'a_test-a_test4': {
            'step': 'a_test',
            'test': 'a_test4',
            'try_job_key': 'm/b/121',
            'status': 'Flaky'
        },
        'b_test-b_test1': {
            'step': 'b_test',
            'test': 'b_test1',
            'try_job_key': 'm/b/121',
            'status': 'Flaky'
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
    self.assertEqual(expected_result, result)

  def testUpdateFlakinessNoTask(self):
    step_name = 's'
    failure_key_set = ['m/b/1']
    culprits_info = None
    handlers_util._UpdateFlakiness(step_name, failure_key_set, culprits_info)
    self.assertIsNone(culprits_info)

  def testGetCulpritInfoForTryJobResultStep(self):
    try_job_key = 'm/b/120'
    culprits_info = {
        'a_test': {
            'step': 'a_test',
            'test': 'N/A',
            'try_job_key': try_job_key
        }
    }

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

    handlers_util._GetCulpritInfoForTryJobResult(try_job_key, culprits_info)

    expected_culprits_info = {
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
        }
    }

    self.assertEqual(expected_culprits_info, culprits_info)
