# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from handlers import handlers_util
from handlers import result_status
from libs import analysis_status
from model.wf_analysis import WfAnalysis
from model.wf_swarming_task import WfSwarmingTask
from model.wf_try_job import WfTryJob
from waterfall.test import wf_testcase


class HandlersUtilResultTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(HandlersUtilResultTest, self).setUp()
    self.master_name = 'm'
    self.builder_name = 'b'
    self.build_number = 121

  def testGetResultAndFailureResultMapForGroup(self):
    first_analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    first_analysis.result = {
        'failures': []
    }
    first_analysis.failure_result_map = {
        'compile': 'm/b/121'
    }
    first_analysis.put()

    second_analysis = WfAnalysis.Create(
        'm2', self.builder_name, self.build_number)
    second_analysis.failure_group_key = [self.master_name, self.builder_name,
                                         self.build_number]
    second_analysis.put()

    result, failure_result_map = handlers_util._GetResultAndFailureResultMap(
        'm2', self.builder_name, self.build_number)

    self.assertEqual(result, first_analysis.result)
    self.assertEqual(failure_result_map, first_analysis.failure_result_map)

  def testGetSwarmingTaskInfoNoAnalysis(self):
    data = handlers_util.GetSwarmingTaskInfo(
        self.master_name, self.builder_name, self.build_number)
    self.assertEqual({}, data)

  def testGetSwarmingTaskInfoReturnEmptyIfNoFailureMap(self):
    WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number).put()

    data = handlers_util.GetSwarmingTaskInfo(
        self.master_name, self.builder_name, self.build_number)

    self.assertEqual({}, data)

  def testGetSwarmingTaskInfoNoSwarmingTasks(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.failure_result_map = {
        'step1': {
            'test1': '%s/%s/%s' % (self.master_name, self.builder_name, 120),
            'test2': '%s/%s/%s' % (self.master_name, self.builder_name, 120),
            'test3': '%s/%s/%s' % (self.master_name, self.builder_name, 119),
        }
    }
    analysis.put()

    data = handlers_util.GetSwarmingTaskInfo(
        self.master_name, self.builder_name, self.build_number)

    expected_data = {
        'step1': {
            'swarming_tasks': {
                'm/b/119': {
                    'task_info': {
                        'status': result_status.NO_SWARMING_TASK_FOUND
                    },
                    'all_tests': ['test3']
                },
                'm/b/120': {
                    'task_info': {
                        'status': result_status.NO_SWARMING_TASK_FOUND
                    },
                    'all_tests': ['test1', 'test2']
                }
            }
        }
    }

    self.assertEqual(expected_data, data)

  def testGetSwarmingTaskInfoReturnIfNonSwarming(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.failure_result_map = {
        'step1': '%s/%s/%s' % (self.master_name, self.builder_name, 120)
    }
    analysis.put()

    data = handlers_util.GetSwarmingTaskInfo(
        self.master_name, self.builder_name, self.build_number)

    expected_data = {
        'step1': {
            'swarming_tasks': {
                'm/b/120': {
                    'task_info': {
                        'status': result_status.NON_SWARMING_NO_RERUN
                    }
                }
            }
        }
    }

    self.assertEqual(expected_data, data)

  def testGetSwarmingTaskInfoIfNoSwarmingTask(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.failure_result_map = {
        'step1': {
            'test1': '%s/%s/%s' % (self.master_name, self.builder_name, 120),
            'test2': '%s/%s/%s' % (self.master_name, self.builder_name, 120),
            'test3': '%s/%s/%s' % (self.master_name, self.builder_name, 119),
        }
    }
    analysis.put()

    data = handlers_util.GetSwarmingTaskInfo(
        self.master_name, self.builder_name, self.build_number)

    expected_data = {
        'step1': {
            'swarming_tasks': {
                'm/b/119': {
                    'task_info': {
                        'status': result_status.NO_SWARMING_TASK_FOUND
                    },
                    'all_tests': ['test3']
                },
                'm/b/120': {
                    'task_info': {
                        'status': result_status.NO_SWARMING_TASK_FOUND
                    },
                    'all_tests': ['test1', 'test2']
                }
            }
        }
    }
    self.assertEqual(expected_data, data)

  def testGetSwarmingTaskInfo(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.failure_result_map = {
        'step1 on platform': {
            'PRE_test1': '%s/%s/%s' % (
                self.master_name, self.builder_name, 120),
            'PRE_PRE_test2': '%s/%s/%s' % (
                self.master_name, self.builder_name, self.build_number),
            'test3': '%s/%s/%s' % (
                self.master_name, self.builder_name, self.build_number),
            'test4': '%s/%s/%s' % (
                self.master_name, self.builder_name, self.build_number)
        },
        'step2': {
            'test1': '%s/%s/%s' % (
                self.master_name, self.builder_name, self.build_number)
        }
    }
    analysis.put()

    task0 = WfSwarmingTask.Create(
        self.master_name, self.builder_name, 120, 'step1 on platform')
    task0.task_id = 'task0'
    task0.status = analysis_status.COMPLETED
    task0.parameters = {
        'tests': ['test1']
    }
    task0.tests_statuses = {
        'test1': {
            'total_run': 2,
            'SKIPPED': 2
        },
        'PRE_test1': {
            'total_run': 2,
            'FAILURE': 2
        }
    }
    task0.put()

    task1 = WfSwarmingTask.Create(
        self.master_name, self.builder_name, self.build_number,
        'step1 on platform')
    task1.task_id = 'task1'
    task1.status = analysis_status.COMPLETED
    task1.parameters = {
        'tests': ['test2', 'test3', 'test4']
    }
    task1.tests_statuses = {
        'PRE_PRE_test2': {
            'total_run': 2,
            'FAILURE': 2
        },
        'PRE_test2': {
            'total_run': 2,
            'SKIPPED': 2
        },
        'test2': {
            'total_run': 2,
            'SKIPPED': 2
        },
        'test3': {
            'total_run': 4,
            'SUCCESS': 2,
            'FAILURE': 2
        },
        'test4': {
            'total_run': 6,
            'SUCCESS': 6
        }
    }
    task1.put()

    task2 = WfSwarmingTask.Create(
        self.master_name, self.builder_name, self.build_number, 'step2')
    task2.put()

    data = handlers_util.GetSwarmingTaskInfo(
        self.master_name, self.builder_name, self.build_number)

    expected_data = {
        'step1 on platform': {
            'swarming_tasks': {
                'm/b/121': {
                    'task_info': {
                        'status': analysis_status.COMPLETED,
                        'task_id': 'task1',
                        'task_url': ('https://chromium-swarm.appspot.com/user'
                                     '/task/task1')
                    },
                    'all_tests': ['PRE_PRE_test2', 'test3', 'test4'],
                    'reliable_tests': ['PRE_PRE_test2'],
                    'flaky_tests': ['test3', 'test4'],
                    'ref_name': 'step1'
                },
                'm/b/120': {
                    'task_info': {
                        'status': analysis_status.COMPLETED,
                        'task_id': 'task0',
                        'task_url': ('https://chromium-swarm.appspot.com/user/'
                                     'task/task0')
                    },
                    'all_tests': ['PRE_test1'],
                    'reliable_tests': ['PRE_test1'],
                    'flaky_tests': [],
                    'ref_name': 'step1'
                }
            }
        },
        'step2': {
            'swarming_tasks': {
                'm/b/121': {
                    'task_info': {
                        'status': analysis_status.PENDING
                    },
                    'all_tests': ['PRE_test1'],
                    'ref_name': 'step2'
                }
            }
        }
    }
    self.assertEqual(sorted(expected_data), sorted(data))

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

  def testGetTryJobResultReturnNoneIfNoFailureResultMapWithResult(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.result = {
        'failures': [
            {
                'step_name': 'a',
                'first_failure': 121,
                'last_pass': 120,
                'supported': True,
                'suspected_cls': [],
                'tests': [
                    {
                        'test_name': 'Unittest1.Subtest1',
                        'first_failure': 121,
                        'last_pass': 120,
                        'suspected_cls': []
                    }
                ]
            }
        ]
    }
    analysis.put()

    result = handlers_util.GetAllTryJobResults(
        self.master_name, self.builder_name, self.build_number)

    expected_result = {
        'a': {
            'try_jobs': [
                {
                    'status': result_status.NO_FAILURE_RESULT_MAP,
                    'tests': ['Unittest1.Subtest1']
                }
            ]
        }
    }
    self.assertEqual(expected_result, result)

  def testGetTryJobResultForCompileReturnNoneIfNoTryJob(self):
    result = handlers_util._GetTryJobResultForCompile({'compile': 'm/b/121'})

    self.assertEqual({}, result)

  def testGetTryJobResultForCompileOnlyReturnStatusNoResult(self):
    WfTryJob.Create(
        self.master_name, self.builder_name, self.build_number).put()

    result = handlers_util._GetTryJobResultForCompile({'compile': 'm/b/121'})

    expected_result = {
        'compile': {
            'try_jobs': [
                {
                    'try_job_key': 'm/b/121',
                    'status': analysis_status.PENDING
                }
            ]
        }
    }

    self.assertEqual(expected_result, result)

  def testGetTryJobResultForCompileOnlyReturnUrlIfStarts(self):
    try_job = WfTryJob.Create(
        self.master_name, self.builder_name, self.build_number)
    try_job.status = analysis_status.RUNNING
    try_job.compile_results = [
        {
            'result': None,
            'url': ('http://build.chromium.org/p/tryserver.chromium.linux/'
                    'builders/linux_chromium_variable/builds/121')
        }
    ]
    try_job.put()

    result = handlers_util._GetTryJobResultForCompile({'compile': 'm/b/121'})

    expected_result = {
        'compile': {
            'try_jobs': [
                {
                    'try_job_key': 'm/b/121',
                    'status': analysis_status.RUNNING,
                    'try_job_build_number': 121,
                    'try_job_url': (
                        'http://build.chromium.org/p/tryserver.chromium.'
                        'linux/builders/linux_chromium_variable/builds/121')
                }
            ]
        }
    }
    self.assertEqual(expected_result, result)

  def testGetTryJobResultForCompileOnlyReturnStatusIfError(self):
    try_job = WfTryJob.Create(
        self.master_name, self.builder_name, self.build_number)
    try_job.status = analysis_status.ERROR
    try_job.compile_results = [
        {
            'try_job_id': '1'
        }
    ]
    try_job.put()

    result = handlers_util._GetTryJobResultForCompile({'compile': 'm/b/121'})

    expected_result = {
        'compile': {
            'try_jobs': [
                {
                    'try_job_key': 'm/b/121',
                    'status': analysis_status.ERROR
                }
            ]
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
    try_job.status = analysis_status.COMPLETED
    try_job.compile_results = [
        {
            'report': {
                'result': {
                    'rev1': 'passed',
                    'rev2': 'failed'
                }
            },
            'try_job_id': 'm/b/121',
            'url': ('http://build.chromium.org/p/tryserver.chromium.'
                    'linux/builders/linux_chromium_variable/builds/121'),
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
            'try_jobs': [
                {
                    'try_job_key': 'm/b/121',
                    'status': analysis_status.COMPLETED,
                    'try_job_build_number': 121,
                    'try_job_url': (
                        'http://build.chromium.org/p/tryserver.chromium.'
                        'linux/builders/linux_chromium_variable/builds/121'),
                    'culprit': {
                        'revision': 'rev2',
                        'commit_position': '2',
                        'review_url': 'url_2'
                    }
                }
            ]
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
    try_job.status = analysis_status.COMPLETED
    try_job.compile_results = [
        {
            'report': {
                'result': {
                    'rev1': 'passed',
                    'rev2': 'failed'
                },
            },
            'url': ('http://build.chromium.org/p/tryserver.chromium.linux/'
                    'builders/linux_chromium_variable/builds/121')
        }
    ]
    try_job.put()

    result = handlers_util.GetAllTryJobResults(
        self.master_name, self.builder_name, self.build_number)

    expected_result = {
        'compile': {
            'try_jobs': [
                {
                    'try_job_key': 'm/b/121',
                    'status': analysis_status.COMPLETED,
                    'try_job_build_number': 121,
                    'try_job_url': (
                        'http://build.chromium.org/p/tryserver.chromium.'
                        'linux/builders/linux_chromium_variable/builds/121')
                }
            ]
        }
    }

    self.assertEqual(expected_result, result)

  def testGetAllTryJobResultsTestFailureNoTaskInfo(self):
    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.failure_result_map = {
        'step1': {
            'test1': 'm/b/118'
        }
    }
    analysis.put()

    result = handlers_util.GetAllTryJobResults(
        self.master_name, self.builder_name, self.build_number)

    expected_result = {
        'step1': {
            'try_jobs': [
                {
                    'try_job_key': 'm/b/118',
                    'status': (
                        result_status.NO_TRY_JOB_REASON_MAP.get(
                            result_status.NO_SWARMING_TASK_FOUND)),
                    'tests': ['test1']
                }
            ]
        }
    }

    self.assertEqual(expected_result, result)

  def testGetAllTryJobResultsForTestNonSwarming(self):
    tasks_info = {
        'step1': {
            'swarming_tasks': {
                'm/b/119': {
                    'task_info': {
                        'status': result_status.NON_SWARMING_NO_RERUN
                    },
                    'all_tests': ['test1']
                },
            }
        }
    }
    result = handlers_util._GetAllTryJobResultsForTest(
        {'step1': 'm/b/119'}, tasks_info)

    expected_result = {
        'step1': {
            'try_jobs': [
                {
                    'try_job_key': 'm/b/119',
                    'status': result_status.NO_TRY_JOB_REASON_MAP.get(
                        result_status.NON_SWARMING_NO_RERUN),
                    'tests': ['test1']
                }
            ]
        }
    }
    self.assertEqual(expected_result, result)

  def testGetAllTryJobResultsForTestNonSwarmingForcedTryJob(self):
    tasks_info = {
        'step1': {
            'swarming_tasks': {
                'm/b/119': {
                    'task_info': {
                        'status': result_status.NON_SWARMING_NO_RERUN
                    },
                    'all_tests': ['test1']
                },
            }
        }
    }
    result = handlers_util._GetAllTryJobResultsForTest(
        {'step1': 'm/b/119'}, tasks_info, True)

    expected_result = {
        'step1': {
            'try_jobs': [
                {
                    'try_job_key': 'm/b/119',
                    'ref_name': 'step1',
                    'can_force': True,
                    'status': result_status.NON_SWARMING_NO_RERUN,
                    'tests': ['test1']
                }
            ]
        }
    }

    self.assertEqual(expected_result, result)

  def testGetAllTryJobResultsForTestNoSwarmingTaskInfo(self):
    failure_result_map = {
        'step1': {
            'test3': 'm/b/119'
        }
    }

    tasks_info = {}

    result = handlers_util._GetAllTryJobResultsForTest(
        failure_result_map, tasks_info)

    self.assertEqual({}, result)

  def testGetAllTryJobResultsForTestSwarmingTaskNotComplete(self):
    failure_result_map = {
        'step1': {
            'test1': 'm/b/118',
            'test3': 'm/b/119'
        }
    }

    tasks_info = {
        'step1': {
            'swarming_tasks': {
                'm/b/118': {
                    'task_info': {
                        'status': analysis_status.PENDING
                    },
                    'all_tests': ['test1']
                },
                'm/b/119': {
                    'task_info': {
                        'status': analysis_status.RUNNING,
                        'task_id': 'task3',
                        'task_url': 'task3_url'
                    },
                    'all_tests': ['test3']
                }
            }
        }
    }

    result = handlers_util._GetAllTryJobResultsForTest(
        failure_result_map, tasks_info)

    expected_result = {
        'step1': {
            'try_jobs': [
                {
                    'try_job_key': 'm/b/118',
                    'status': result_status.NO_TRY_JOB_REASON_MAP[
                        analysis_status.PENDING],
                    'tests': ['test1']
                },
                {
                    'try_job_key': 'm/b/119',
                    'status': result_status.NO_TRY_JOB_REASON_MAP[
                        analysis_status.RUNNING],
                    'task_id': 'task3',
                    'task_url': 'task3_url',
                    'tests': ['test3']
                }
            ]
        }
    }

    self.assertEqual(expected_result, result)

  def testUpdateTryJobInfoBasedOnSwarmingAllFlaky(self):
    step_tasks_info = {
        'swarming_tasks': {
            'm/b/119': {
                'task_info': {
                    'status': analysis_status.COMPLETED,
                    'task_id': 'task1',
                    'task_url': 'task_url'
                },
                'all_tests': ['test2', 'test3'],
                'reliable_tests': [],
                'flaky_tests': ['test2', 'test3'],
                'ref_name': 'step1'
            }
        }
    }

    try_jobs = [
        {
            'try_job_key': 'm/b/119'
        }
    ]

    handlers_util._UpdateTryJobInfoBasedOnSwarming(
        step_tasks_info, try_jobs)

    expected_try_jobs = [
        {
            'try_job_key': 'm/b/119',
            'ref_name': 'step1',
            'tests': ['test2', 'test3'],
            'status': result_status.FLAKY,
            'task_id': 'task1',
            'task_url': 'task_url'
        }
    ]
    self.assertEqual(expected_try_jobs, try_jobs)

  def testGetAllTryJobResultsForTestHasCulprit(self):
    failure_result_map = {
        'step1 on platform': {
            'test3': 'm/b/119'
        }
    }

    tasks_info = {
        'step1 on platform': {
            'swarming_tasks': {
                'm/b/119': {
                    'task_info': {
                        'status': analysis_status.COMPLETED,
                        'task_id': 'task1',
                        'task_url': ('https://chromium-swarm.appspot.com/user'
                                     '/task/task1')
                    },
                    'all_tests': ['test3'],
                    'reliable_tests': ['test3'],
                    'flaky_tests': [],
                    'ref_name': 'step1'
                }
            }
        }
    }

    try_job = WfTryJob.Create('m', 'b', 119)
    try_job.status = analysis_status.COMPLETED
    try_job.test_results = [
        {
            'report': {
                'result': {
                    'rev1': {
                        'step1': {
                            'status': 'passed',
                            'valid': True
                        }
                    },
                    'rev2': {
                        'step1': {
                            'status': 'failed',
                            'valid': True,
                            'failures': ['test3']
                        }
                    }
                }
            },
            'url': ('http://build.chromium.org/p/tryserver.chromium.'
                    'linux/builders/linux_chromium_variable/builds/121'),
            'try_job_id': 'try_job_id',
            'culprit': {
                'step1': {
                    'tests': {
                        'test3': {
                            'revision': 'rev2',
                            'commit_position': '2',
                            'review_url': 'url_2'
                        }
                    }
                }
            }
        }
    ]
    try_job.put()

    result = handlers_util._GetAllTryJobResultsForTest(
        failure_result_map, tasks_info)

    expected_result = {
        'step1 on platform': {
            'try_jobs': [
                {
                    'ref_name': 'step1',
                    'try_job_key': 'm/b/119',
                    'status': analysis_status.COMPLETED,
                    'try_job_url': (
                        'http://build.chromium.org/p/tryserver.chromium.'
                        'linux/builders/linux_chromium_variable/builds/121'),
                    'try_job_build_number': 121,
                    'culprit': {
                        'revision': 'rev2',
                        'commit_position': '2',
                        'review_url': 'url_2'
                    },
                    'task_id': 'task1',
                    'task_url': ('https://chromium-swarm.appspot.com/user'
                                 '/task/task1'),
                    'tests': ['test3']
                }
            ]
        }
    }
    self.assertEqual(expected_result, result)

  def testGetAllTryJobResultsForTest(self):
    failure_result_map = {
        'step1 on platform': {
            'test1': 'm/b/118',
            'test2': 'm/b/119',
            'test3': 'm/b/119',
            'test4': 'm/b/119'
        }
    }

    tasks_info = {
        'step1 on platform': {
            'swarming_tasks': {
                'm/b/119': {
                    'task_info': {
                        'status': analysis_status.COMPLETED,
                        'task_id': 'task1',
                        'task_url': 'url/task1'
                    },
                    'all_tests': ['test2', 'test3', 'test4'],
                    'reliable_tests': ['test2', 'test3'],
                    'flaky_tests': ['test4'],
                    'ref_name': 'step1'
                },
                'm/b/118': {
                    'task_info': {
                        'status': result_status.NO_SWARMING_TASK_FOUND
                    },
                    'all_tests': ['test1']
                }
            }
        }
    }

    try_job = WfTryJob.Create('m', 'b', 119)
    try_job.status = analysis_status.COMPLETED
    try_job.test_results = [
        {
            'report': {
                'result': {
                    'rev1': {
                        'step1': {
                            'status': 'passed',
                            'valid': True
                        }
                    },
                    'rev2': {
                        'step1': {
                            'status': 'failed',
                            'valid': True,
                            'failures': ['test2']
                        }
                    }
                }
            },
            'url': ('http://build.chromium.org/p/tryserver.chromium.'
                    'linux/builders/linux_chromium_variable/builds/121'),
            'try_job_id': 'try_job_id',
            'culprit': {
                'step1': {
                    'tests': {
                        'test2': {
                            'revision': 'rev2',
                            'commit_position': '2',
                            'review_url': 'url_2'
                        }
                    }
                }
            }
        }
    ]
    try_job.put()

    result = handlers_util._GetAllTryJobResultsForTest(
        failure_result_map, tasks_info)

    expected_result = {
        'step1 on platform': {
            'try_jobs': [
                {
                    'try_job_key': 'm/b/118',
                    'status': result_status.NO_TRY_JOB_REASON_MAP.get(
                        result_status.NO_SWARMING_TASK_FOUND),
                    'tests': ['test1']
                },
                {
                    'ref_name': 'step1',
                    'try_job_key': 'm/b/119',
                    'task_id': 'task1',
                    'task_url': 'url/task1',
                    'status': analysis_status.COMPLETED,
                    'try_job_url': (
                        'http://build.chromium.org/p/tryserver.chromium.'
                        'linux/builders/linux_chromium_variable/builds/121'),
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
                        'linux/builders/linux_chromium_variable/builds/121'),
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
                }
            ]
        }
    }
    self.assertEqual(set(expected_result), set(result))

  def testOrganizeTryJobResultByCulpritsNoCulprits(self):
    self.assertEqual({}, handlers_util._OrganizeTryJobResultByCulprits({}))

  def testOrganizeTryJobResultByCulprits(self):
    try_job_culprits = {
        'tests': {
            'a_test1': {
                'revision': 'rev1',
                'commit_position': '1',
                'review_url': 'url_1'
            },
            'a_test2': {
                'revision': 'rev1',
                'commit_position': '1',
                'review_url': 'url_1'
            }
        }
    }

    result = handlers_util._OrganizeTryJobResultByCulprits(try_job_culprits)
    expected_result = {
        'rev1': {
            'revision': 'rev1',
            'commit_position': '1',
            'review_url': 'url_1',
            'failed_tests': ['a_test2', 'a_test1']
        }
    }
    self.assertEqual(expected_result, result)

  def testGetCulpritInfoForTryJobResultForTestTryJobNoResult(self):
    try_job_key = 'm/b/119'
    culprits_info = {
        'step1 on platform': {
            'try_jobs': [
                {
                    'ref_name': 'step1',
                    'try_job_key': try_job_key,
                    'tests': ['test2', 'test3']
                }
            ]
        }
    }
    WfTryJob.Create('m', 'b', '119').put()
    handlers_util._GetCulpritInfoForTryJobResultForTest(
        try_job_key, culprits_info)

    expected_culprits_info = {
        'step1 on platform': {
            'try_jobs': [
                {
                    'ref_name': 'step1',
                    'try_job_key': try_job_key,
                    'tests': ['test2', 'test3'],
                    'status': analysis_status.PENDING
                }
            ]
        }
    }
    self.assertEqual(expected_culprits_info, culprits_info)

  def testGetCulpritInfoForTryJobResultForTestTryJobRunning(self):
    try_job_key = 'm/b/119'
    culprits_info = {
        'step1 on platform': {
            'try_jobs': [
                {
                    'ref_name': 'step1',
                    'try_job_key': try_job_key,
                    'tests': ['test2', 'test3']
                }
            ]
        }
    }
    try_job = WfTryJob.Create('m', 'b', '119')
    try_job.status = analysis_status.RUNNING
    try_job.test_results = [
        {
            'url': ('http://build.chromium.org/p/tryserver.chromium.'
                    'linux/builders/linux_chromium_variable/builds/121'),
            'try_job_id': '121'
        }
    ]
    try_job.put()
    handlers_util._GetCulpritInfoForTryJobResultForTest(
        try_job_key, culprits_info)

    expected_culprits_info = {
        'step1 on platform': {
            'try_jobs': [
                {
                    'ref_name': 'step1',
                    'try_job_key': try_job_key,
                    'tests': ['test2', 'test3'],
                    'status': analysis_status.RUNNING,
                    'try_job_url': (
                        'http://build.chromium.org/p/tryserver.chromium.'
                        'linux/builders/linux_chromium_variable/builds/121'),
                    'try_job_build_number': 121
                }
            ]
        }
    }
    self.assertEqual(expected_culprits_info, culprits_info)
