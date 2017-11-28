# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import json
import logging
import mock

from google.appengine.api import taskqueue

from common import exceptions
from common.waterfall import buildbucket_client
from gae_libs.pipelines import pipeline
from libs import analysis_status
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
from pipelines.test_failure.run_test_try_job_pipeline import (
    RunTestTryJobPipeline)
from services import try_job as try_job_service
from services.test_failure import test_try_job
from services.parameters import BuildKey
from services.parameters import RunTestTryJobParameters
from waterfall import buildbot
from waterfall.test import wf_testcase


class RunTestTryJobPipelineTest(wf_testcase.WaterfallTestCase):

  @mock.patch.object(test_try_job, 'ScheduleTestTryJob', return_value='1')
  @mock.patch.object(try_job_service, 'OnTryJobCompleted')
  @mock.patch.object(buildbot, 'GetStepLog')
  @mock.patch.object(buildbucket_client, 'GetTryJobs')
  def testGetTryJobsForTestSuccessSerializedCallback(
      self, mock_buildbucket, mock_report, mock_result, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'
    good_revision = 'rev1'
    bad_revision = 'rev2'
    targeted_tests = {'a': ['test1', 'test2']}

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.try_job_ids = ['1']
    try_job_data = WfTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.try_job_url = (
        'https://build.chromium.org/p/m/builders/b/builds/1234')
    try_job_data.put()
    try_job.test_results = [{
        'report': None,
        'url': 'https://build.chromium.org/p/m/builders/b/builds/1234',
        'try_job_id': '1',
    }]
    try_job.status = analysis_status.RUNNING
    try_job.put()

    build_response = {
        'id': '1',
        'url': 'https://build.chromium.org/p/m/builders/b/builds/1234',
        'status': 'COMPLETED',
        'completed_ts': '1454367574000000',
        'created_ts': '1454367570000000',
        'updated_ts': '1454367574000000',
    }
    report = {
        'result': {
            'rev1': {
                'a_test': {
                    'status': 'passed',
                    'valid': True,
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
                        'swarm_task_ids': ['id1'],
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
        }
    }
    expected_test_result = {
        'report': {
            'culprits': None,
            'flakes': None,
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
                            'swarm_task_ids': ['id1'],
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
    mock_buildbucket.return_value = [
        (None, buildbucket_client.BuildbucketBuild(build_response))
    ]
    mock_report.return_value = report
    mock_result.return_value = expected_test_result

    pipeline_input = RunTestTryJobParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        bad_revision=bad_revision,
        good_revision=good_revision,
        suspected_revisions=[],
        targeted_tests=targeted_tests,
        dimensions=[],
        cache_name=None,
        force_buildbot=False,
        urlsafe_try_job_key=try_job.key.urlsafe())
    try_job_pipeline = RunTestTryJobPipeline(pipeline_input)
    try_job_pipeline.start_test()
    try_job_data = WfTryJobData.Get(try_job_id)
    try_job_data.runner_id = try_job_pipeline.pipeline_id
    try_job_data.put()
    try_job_pipeline.run(pipeline_input)
    try_job_pipeline.callback(
        callback_params=json.dumps(try_job_pipeline.last_params))

    # Reload from ID to get all internal properties in sync.
    try_job_pipeline = RunTestTryJobPipeline.from_id(
        try_job_pipeline.pipeline_id)
    try_job_pipeline.finalized()
    test_result = try_job_pipeline.outputs.default.value

    self.assertEqual(expected_test_result, test_result)

  @mock.patch.object(try_job_service, '_UpdateTryJobResult')
  @mock.patch.object(test_try_job, 'ScheduleTestTryJob', return_value='3')
  @mock.patch.object(try_job_service, 'OnTryJobCompleted')
  @mock.patch.object(buildbot, 'GetStepLog')
  @mock.patch.object(buildbucket_client, 'GetTryJobs')
  def testGetTryJobsForTestMissingTryJobData(self, mock_buildbucket,
                                             mock_report, mock_result, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '3'
    good_revision = 'rev1'
    bad_revision = 'rev2'
    targeted_tests = {'a': ['test1', 'test2']}

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.test_results = [{
        'report': None,
        'url': 'https://build.chromium.org/p/m/builders/b/builds/1234',
        'try_job_id': try_job_id,
    }]
    try_job.status = analysis_status.RUNNING
    try_job.put()

    data = [{
        'build': {
            'id': '3',
            'url': 'https://build.chromium.org/p/m/builders/b/builds/1234',
            'status': 'STARTED'
        }
    }, {
        'error': {
            'reason': 'BUILD_NOT_FOUND',
            'message': 'message',
        }
    }, {
        'build': {
            'id': '3',
            'url': 'https://build.chromium.org/p/m/builders/b/builds/1234',
            'status': 'STARTED'
        }
    }, {
        'error': {
            'reason': 'BUILD_NOT_FOUND',
            'message': 'message',
        }
    }, {
        'build': {
            'id': '3',
            'url': 'https://build.chromium.org/p/m/builders/b/builds/1234',
            'status': 'COMPLETED',
        }
    }]

    get_tryjobs_responses = [
        [(None, buildbucket_client.BuildbucketBuild(data[0]['build']))],
        [(buildbucket_client.BuildbucketError(data[1]['error']), None)],
        [(None, buildbucket_client.BuildbucketBuild(data[2]['build']))],
        [(buildbucket_client.BuildbucketError(data[3]['error']), None)],
        [(None, buildbucket_client.BuildbucketBuild(data[4]['build']))],
    ]
    mock_buildbucket.side_effect = get_tryjobs_responses
    report = {
        'result': {
            'rev1': {
                'a_test': {
                    'status': 'passed',
                    'valid': True,
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
                        'swarm_task_ids': ['id1'],
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
        }
    }
    expected_test_result = {
        'report': {
            'culprits': None,
            'flakes': None,
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
                            'swarm_task_ids': ['id1'],
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
    mock_report.return_value = report
    mock_result.return_value = expected_test_result

    pipeline_input = RunTestTryJobParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        bad_revision=bad_revision,
        good_revision=good_revision,
        suspected_revisions=[],
        targeted_tests=targeted_tests,
        dimensions=[],
        cache_name=None,
        force_buildbot=False,
        urlsafe_try_job_key=try_job.key.urlsafe())
    try_job_pipeline = RunTestTryJobPipeline(pipeline_input)
    try_job_pipeline.start_test()
    try_job_pipeline.run(pipeline_input)
    # Since run() calls callback() immediately, we use -1.
    for _ in range(len(get_tryjobs_responses) - 1):
      try_job_pipeline.callback(callback_params=try_job_pipeline.last_params)

    # Reload from ID to get all internal properties in sync.
    try_job_pipeline = RunTestTryJobPipeline.from_id(
        try_job_pipeline.pipeline_id)
    try_job_pipeline.finalized()
    test_result = try_job_pipeline.outputs.default.value

    self.assertEqual(expected_test_result, test_result)

  @mock.patch.object(test_try_job, 'ScheduleTestTryJob', return_value=None)
  def testReturnNoneIfNoTryJobId(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    pipeline_input = RunTestTryJobParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        bad_revision='rev1',
        good_revision='rev2',
        suspected_revisions=[],
        targeted_tests={},
        dimensions=[],
        cache_name=None,
        force_buildbot=False,
        urlsafe_try_job_key=None)
    try_job_pipeline = RunTestTryJobPipeline(pipeline_input)
    try_job_pipeline.start_test()
    try_job_pipeline.run(pipeline_input)

    # Reload from ID to get all internal properties in sync.
    try_job_pipeline = RunTestTryJobPipeline.from_id(
        try_job_pipeline.pipeline_id)
    try_job_pipeline.finalized()
    test_result = try_job_pipeline.outputs.default.value
    self.assertEqual({}, test_result)

  @mock.patch.object(try_job_service, '_UpdateTryJobResult')
  @mock.patch.object(test_try_job, 'ScheduleTestTryJob', return_value='1')
  @mock.patch.object(try_job_service, 'OnTryJobCompleted')
  @mock.patch.object(buildbot, 'GetStepLog')
  @mock.patch.object(buildbucket_client, 'GetTryJobs')
  def testGetTryJobsForTestSuccessBackwardCompatibleCallback(
      self, mock_buildbucket, mock_report, mock_result, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'
    regression_range_size = 2
    good_revision = 'rev1'
    bad_revision = 'rev2'
    targeted_tests = {'a': ['test1', 'test2']}

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job_data = WfTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.try_job_url = (
        'https://build.chromium.org/p/m/builders/b/builds/1234')
    try_job_data.put()
    try_job.test_results = [{
        'report': None,
        'url': 'https://build.chromium.org/p/m/builders/b/builds/1234',
        'try_job_id': '1',
    }]
    try_job.status = analysis_status.RUNNING
    try_job.put()

    build_response = {
        'id': '1',
        'url': 'https://build.chromium.org/p/m/builders/b/builds/1234',
        'status': 'COMPLETED',
        'completed_ts': '1454367574000000',
        'created_ts': '1454367570000000',
        'updated_ts': '1454367574000000',
    }
    mock_buildbucket.return_value = [
        (None, buildbucket_client.BuildbucketBuild(build_response))
    ]

    report = {
        'result': {
            good_revision: {
                'a_test': {
                    'status': 'passed',
                    'valid': True,
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
            bad_revision: {
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
                        'swarm_task_ids': ['id1'],
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
        }
    }
    expected_test_result = {
        'report': {
            'culprits': None,
            'flakes': None,
            'last_checked_out_revision': None,
            'previously_cached_revision': None,
            'previously_checked_out_revision': None,
            'metadata': {
                'regression_range_size': regression_range_size
            },
            'result': {
                good_revision: {
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
                bad_revision: {
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
                            'swarm_task_ids': ['id1'],
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
    mock_report.return_value = report
    mock_result.return_value = expected_test_result

    pipeline_input = RunTestTryJobParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        bad_revision=bad_revision,
        good_revision=good_revision,
        suspected_revisions=[],
        targeted_tests=targeted_tests,
        dimensions=[],
        cache_name=None,
        force_buildbot=False,
        urlsafe_try_job_key=try_job.key.urlsafe())

    try_job_pipeline = RunTestTryJobPipeline(pipeline_input)
    try_job_pipeline.start_test()
    try_job_pipeline.run(pipeline_input)
    try_job_pipeline.callback(**try_job_pipeline.last_params)

    # Reload from ID to get all internal properties in sync.
    try_job_pipeline = RunTestTryJobPipeline.from_id(
        try_job_pipeline.pipeline_id)
    try_job_pipeline.finalized()
    test_result = try_job_pipeline.outputs.default.value

    self.assertEqual(expected_test_result, test_result)

  @mock.patch.object(logging, 'warning')
  @mock.patch.object(
      RunTestTryJobPipeline,
      'get_callback_task',
      side_effect=taskqueue.TombstonedTaskError)
  def testDelayCallbackException(self, _, mocked_logging):
    pipeline_input = RunTestTryJobParameters(
        build_key=BuildKey(master_name='m', builder_name='b', build_number=123),
        bad_revision='rev1',
        good_revision='rev2',
        suspected_revisions=[],
        targeted_tests={},
        dimensions=[],
        cache_name=None,
        force_buildbot=False,
        urlsafe_try_job_key=None)
    try_job_pipeline = RunTestTryJobPipeline(pipeline_input)
    try_job_pipeline.start_test()
    try_job_pipeline.delay_callback(
        60, try_job_pipeline.last_params, name='name')
    mocked_logging.assert_called()

  @mock.patch.object(test_try_job, 'ScheduleTestTryJob', return_value='1')
  @mock.patch.object(
      try_job_service,
      'OnGetTryJobError',
      side_effect=exceptions.RetryException('error_reason', 'error_message'))
  @mock.patch.object(buildbucket_client, 'GetTryJobs')
  def testMonitorTryJobMaxError(self, mock_buildbucket, *_):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '1'

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.put()
    try_job_data = WfTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.try_job_url = (
        'https://build.chromium.org/p/m/builders/b/builds/1234')
    try_job_data.put()

    error_data = {'reason': 'BUILD_NOT_FOUND', 'message': 'message'}
    error = buildbucket_client.BuildbucketError(error_data)
    mock_buildbucket.return_value = [(error, None)]

    pipeline_input = RunTestTryJobParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        bad_revision='rev1',
        good_revision='rev2',
        suspected_revisions=[],
        targeted_tests={},
        dimensions=[],
        cache_name=None,
        force_buildbot=False,
        urlsafe_try_job_key=None)
    try_job_pipeline = RunTestTryJobPipeline(pipeline_input)
    try_job_pipeline.start_test()
    with self.assertRaises(pipeline.Retry):
      try_job_pipeline.run(pipeline_input)

  @mock.patch.object(
      test_try_job,
      'ScheduleTestTryJob',
      side_effect=exceptions.RetryException('error_reason', 'error_message'))
  def testScheduleNewTryJobForTestRaise(self, _):
    master_name = 'm'
    builder_name = 'b'
    build_number = 223

    pipeline_input = RunTestTryJobParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        bad_revision='rev1',
        good_revision='rev2',
        suspected_revisions=[],
        targeted_tests={},
        dimensions=[],
        cache_name=None,
        force_buildbot=False,
        urlsafe_try_job_key=None)

    try_job_pipeline = RunTestTryJobPipeline(pipeline_input)
    with self.assertRaises(pipeline.Retry):
      try_job_pipeline.run(pipeline_input)
