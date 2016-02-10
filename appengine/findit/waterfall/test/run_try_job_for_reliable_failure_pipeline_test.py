# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

from model import wf_analysis_status
from waterfall import run_try_job_for_reliable_failure_pipeline
from waterfall.run_try_job_for_reliable_failure_pipeline import (
    RunTryJobForReliableFailurePipeline)
from waterfall.try_job_type import TryJobType


_SAMPLE_TARGETED_TESTS = {
    'step1': ['step1_test1', 'step1_test2'],
    'step2': ['step2_test1', 'step2_test2', 'step2_test3'],
    'step3': []
}

_SAMPLE_STEPS_STATUSES = {
    '1': {
        'step1': {
            'step1_test1': {
                'total_run': 2,
                'SUCCESS': 2
            },
            'step1_test2': {
                'total_run': 4,
                'SUCCESS': 0,
                'FAILURE': 4
            },
            'step1_test3': {
                'total_run': 4,
                'SUCCESS': 0,
                'FAILURE': 4
            }
        },
        'step2': {
            'step2_test1': {
                'total_run': 2,
                'SUCCESS': 2
            },
            'step2_test2': {
                'total_run': 4,
                'SUCCESS': 2,
                'FAILURE': 2
            },
            'step2_test3': {
                'total_run': 4,
                'SUCCESS': 1,
                'FAILURE': 3
            }
        }
    },
    '2': {
        'step1': {
            'step1_test1': {
                'total_run': 2,
                'SUCCESS': 2
            },
            'step1_test2': {
                'total_run': 4,
                'SUCCESS': 4,
                'FAILURE': 0
            }
        },
        'step2': {
            'step2_test1': {
                'total_run': 2,
                'SUCCESS': 2
            }
        }
    }
}


class _MockTryJobPipeline(object):
  STARTED = False

  def __init__(self, *_):
    pass

  def start(self, *_):
    _MockTryJobPipeline.STARTED = True

  @property
  def pipeline_status_path(self):
    return 'path'


class RunTryJobForReliableFailurePipelineTest(testing.AppengineTestCase):

  def setUp(self):
    super(RunTryJobForReliableFailurePipelineTest, self).setUp()
    self.master_name = 'm'
    self.builder_name = 'b'
    self.build_number = 121
    self.good_revision = 'rev0'
    self.bad_revision = 'rev2'
    self.blame_list = ['rev1', 'rev2']

  def testGetReliableTargetedTests(self):
    reliable_tests = (
        run_try_job_for_reliable_failure_pipeline._GetReliableTargetedTests(
            _SAMPLE_TARGETED_TESTS, _SAMPLE_STEPS_STATUSES['1']))

    expected_reliable_tests = {
        'step1': ['step1_test2'],
        'step3': []
    }

    self.assertEqual(expected_reliable_tests, reliable_tests)

  def testGetReliableTargetedTestsAllFlaky(self):
    reliable_tests = (
        run_try_job_for_reliable_failure_pipeline._GetReliableTargetedTests(
            {'step1': ['step1_test1']}, _SAMPLE_STEPS_STATUSES['2']))

    expected_reliable_tests = {}

    self.assertEqual(expected_reliable_tests, reliable_tests)

  def testSuccessfullyScheduleNewTryJobForCompile(self):
    self.mock(
        run_try_job_for_reliable_failure_pipeline.try_job_pipeline,
        'TryJobPipeline', _MockTryJobPipeline)
    _MockTryJobPipeline.STARTED = False

    pipeline = RunTryJobForReliableFailurePipeline()
    pipeline.run(
        self.master_name, self.builder_name, self.build_number, 'rev1', 'rev2',
        ['rev2'], TryJobType.COMPILE, [], None, {})

    self.assertTrue(_MockTryJobPipeline.STARTED)

  def testSuccessfullyScheduleNewTryJobForTest(self):
    self.mock(
        run_try_job_for_reliable_failure_pipeline.try_job_pipeline,
        'TryJobPipeline', _MockTryJobPipeline)
    _MockTryJobPipeline.STARTED = False

    pipeline = RunTryJobForReliableFailurePipeline()
    pipeline.run(
        self.master_name, self.builder_name, self.build_number, 'rev1', 'rev2',
        ['rev2'], TryJobType.TEST, None, _SAMPLE_TARGETED_TESTS,
        _SAMPLE_STEPS_STATUSES['1'])

    self.assertTrue(_MockTryJobPipeline.STARTED)
