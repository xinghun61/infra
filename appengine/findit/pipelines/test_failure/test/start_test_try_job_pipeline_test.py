# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common.waterfall import failure_type
from gae_libs.pipelines import pipeline_handlers
from model.wf_try_job import WfTryJob
from pipelines.test_failure import start_test_try_job_pipeline
from pipelines.test_failure.start_test_try_job_pipeline import (
    StartTestTryJobPipeline)
from services.parameters import BuildKey
from services.parameters import IdentifyTestTryJobCulpritParameters
from services.parameters import RunTestTryJobParameters
from services.parameters import TestTryJobResult
from services.test_failure import test_try_job
from waterfall.test import wf_testcase


class StartTestTryJobPipelineTest(wf_testcase.WaterfallTestCase):
  app_module = pipeline_handlers._APP

  def testNotScheduleTryJobIfBuildNotCompleted(self):
    heuristic_result = {'failure_info': {}, 'heuristic_result': {}}
    pipeline = start_test_try_job_pipeline.StartTestTryJobPipeline()
    result = pipeline.run('m', 'b', 1, heuristic_result, False, False)
    self.assertEqual(list(result), [])

  @mock.patch.object(test_try_job, 'GetParametersToScheduleTestTryJob')
  @mock.patch.object(test_try_job, 'NeedANewTestTryJob')
  def testTestTryJob(self, mock_fn, mock_parameter):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_type = failure_type.TEST
    failure_info = {
        'parent_mastername': None,
        'parent_buildername': None,
        'failure_type': try_job_type,
        'builds': {
            '0': {
                'blame_list': ['r0', 'r1'],
                'chromium_revision': 'r1'
            },
            '1': {
                'blame_list': ['r2'],
                'chromium_revision': 'r2'
            }
        },
        'failed_steps': {
            'a': {
                'first_failure': 1,
                'last_pass': 0,
                'tests': {
                    'test1': {
                        'first_failure': 1,
                        'last_pass': 0
                    },
                    'test2': {
                        'first_failure': 0
                    }
                }
            },
            'b': {
                'first_failure': 0,
                'tests': {
                    'b_test1': {
                        'first_failure': 0
                    }
                }
            }
        }
    }
    good_revision = 'r1'
    bad_revision = 'r2'
    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.put()
    mock_fn.return_value = (True, try_job.key)
    parameters = RunTestTryJobParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        bad_revision=bad_revision,
        good_revision=good_revision,
        suspected_revisions=[],
        targeted_tests={'step': ['test']},
        dimensions=[],
        cache_name=None,
        force_buildbot=False,
        urlsafe_try_job_key='urlsafe_try_job_key')
    mock_parameter.return_value = parameters

    self.MockAsynchronousPipeline(
        start_test_try_job_pipeline.RunTestTryJobPipeline, parameters,
        'try_job_result')

    expected_test_result = {
        'report': {
            'culprits': None,
            'last_checked_out_revision': None,
            'previously_cached_revision': None,
            'previously_checked_out_revision': None,
            'metadata': None,
            'result': {
                'rev1': {
                    'a_test': {
                        'status': 'passed',
                        'valid': True,
                        'failures': None,
                        'step_metadata': {
                            'dimensions': {
                                'gpu': 'none',
                                'os': 'Windows-7-SP1',
                                'cpu': 'x86-64',
                                'pool': 'Chrome'
                            },
                            'waterfall_buildername': 'b',
                            'waterfall_mastername': 'm',
                            'full_step_name': 'a',
                            'canonical_step_name': 'a',
                            'patched': False,
                            'swarm_task_ids': ['id1'],
                        },
                        'pass_fail_counts': {},
                    }
                },
                'rev2': {
                    'a_test': {
                        'status': 'failed',
                        'valid': True,
                        'failures': ['test1', 'test2'],
                        'step_metadata': {
                            'dimensions': {
                                'gpu': 'none',
                                'os': 'Windows-7-SP1',
                                'cpu': 'x86-64',
                                'pool': 'Chrome'
                            },
                            'waterfall_buildername': 'b',
                            'waterfall_mastername': 'm',
                            'full_step_name': 'a',
                            'canonical_step_name': 'a',
                            'patched': False,
                            'swarm_task_ids': ['id2'],
                        },
                        'pass_fail_counts': {
                            'test1': {
                                'pass_count': 0,
                                'fail_count': 20
                            },
                            'test2': {
                                'pass_count': 0,
                                'fail_count': 20
                            }
                        }
                    }
                }
            },
        },
        'url': 'https://build.chromium.org/p/m/builders/b/builds/1234',
        'try_job_id': '1',
        'culprit': None,
    }
    identify_culprit_input = IdentifyTestTryJobCulpritParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        result=TestTryJobResult.FromSerializable(expected_test_result))
    self.MockGeneratorPipeline(
        start_test_try_job_pipeline.IdentifyTestTryJobCulpritPipeline,
        identify_culprit_input, False)

    heuristic_result = {'failure_info': failure_info, 'heuristic_result': {}}
    pipeline = StartTestTryJobPipeline('m', 'b', 1, heuristic_result, True,
                                       False)
    pipeline.start()
    self.execute_queued_tasks()

  @mock.patch.object(test_try_job, 'NeedANewTestTryJob')
  @mock.patch.object(start_test_try_job_pipeline, 'RunTestTryJobPipeline')
  def testNotNeedTestTryJob(self, mock_pipeline, mock_fn):
    failure_info = {'failure_type': failure_type.TEST}
    try_job = WfTryJob.Create('m', 'b', 1)
    try_job.put()
    mock_fn.return_value = (False, try_job.key)
    heuristic_result = {'failure_info': failure_info, 'heuristic_result': {}}
    pipeline = StartTestTryJobPipeline()
    result = pipeline.run('m', 'b', 1, heuristic_result, True, False)
    self.assertEqual(list(result), [])
    mock_pipeline.assert_not_called()

  @mock.patch.object(test_try_job, 'NeedANewTestTryJob')
  @mock.patch.object(test_try_job, 'GetParametersToScheduleTestTryJob')
  @mock.patch.object(start_test_try_job_pipeline, 'RunTestTryJobPipeline')
  def testNoTestTryJobBecauseNoGoodRevision(self, mock_pipeline, mock_parameter,
                                            mock_fn):
    failure_info = {'failure_type': failure_type.TEST}
    mock_parameter.return_value = RunTestTryJobParameters(good_revision=None)
    try_job = WfTryJob.Create('m', 'b', 1)
    try_job.put()
    mock_fn.return_value = (True, try_job.key)
    heuristic_result = {'failure_info': failure_info, 'heuristic_result': {}}
    pipeline = StartTestTryJobPipeline()
    result = pipeline.run('m', 'b', 1, heuristic_result, True, False)
    self.assertEqual(list(result), [])
    mock_pipeline.assert_not_called()

  @mock.patch.object(test_try_job, 'NeedANewTestTryJob')
  @mock.patch.object(test_try_job, 'GetParametersToScheduleTestTryJob')
  @mock.patch.object(start_test_try_job_pipeline, 'RunTestTryJobPipeline')
  def testNoTestTryJobBecauseNoTargetedTests(self, mock_pipeline,
                                             mock_parameter, mock_fn):
    failure_info = {'failure_type': failure_type.TEST}
    try_job = WfTryJob.Create('m', 'b', 1)
    try_job.put()
    mock_fn.return_value = (True, try_job.key)
    mock_parameter.return_value = RunTestTryJobParameters(
        targeted_tests={}, good_revision='rev1')
    heuristic_result = {'failure_info': failure_info, 'heuristic_result': {}}
    pipeline = StartTestTryJobPipeline()
    result = pipeline.run('m', 'b', 1, heuristic_result, True, False)
    self.assertEqual(list(result), [])
    mock_pipeline.assert_not_called()
