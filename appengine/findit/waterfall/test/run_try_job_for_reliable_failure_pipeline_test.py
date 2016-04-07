# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

from model import analysis_status
from waterfall import run_try_job_for_reliable_failure_pipeline
from waterfall.run_try_job_for_reliable_failure_pipeline import (
    RunTryJobForReliableFailurePipeline)
from waterfall.try_job_type import TryJobType


_SAMPLE_TARGETED_TESTS = {
    'step1 on platform': ['step1_test1', 'step1_test2'],
    'step2 on platform': ['step2_test1', 'step2_test2', 'step2_test3'],
    'step3': [],
    'step4 on platform': ['step4_test1', 'step4_test2']
}


_SAMPLE_CLASSIFIED_TESTS_BY_STEP = {
    '1': {
        'step1 on platform': (
            'step1',
            {
                # Step has reliable failures.
                'flaky_tests': ['step1_test1'],
                'reliable_tests': ['step1_test2', 'step1_test3']
            }),
        'step2 on platform': (
            'step2',
            # All tests are flaky.
            {
                'flaky_tests': ['step2_test1', 'step2_test2', 'step2_test3']
            }),
        'step4 on platform': (
            'step4', {})  # There is something wrong with swarming task.
    },
    '2': {
        # All steps are flaky.
        'step1 on platform': (
            'step1',
            {
                'flaky_tests': ['step1_test1', 'step1_test2']
            }),
        'step2 on platform': (
            'step2',
            {
                'flaky_tests': ['step2_test1']
            })
    }
}


class _MockTryJobPipeline(object):
  STARTED = False

  def __init__(self, *_):
    pass

  def start(self, *_, **__):
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
            _SAMPLE_TARGETED_TESTS, _SAMPLE_CLASSIFIED_TESTS_BY_STEP['1']))

    expected_reliable_tests = {
        'step1': ['step1_test2'],
        'step3': []
    }

    self.assertEqual(expected_reliable_tests, reliable_tests)

  def testGetReliableTargetedTestsAllFlaky(self):
    reliable_tests = (
        run_try_job_for_reliable_failure_pipeline._GetReliableTargetedTests(
            {'step1 on platform': ['step1_test1']},
            _SAMPLE_CLASSIFIED_TESTS_BY_STEP['2']))

    expected_reliable_tests = {}

    self.assertEqual(expected_reliable_tests, reliable_tests)

  def testGetReliableTargetedTestsNoStatuses(self):
    reliable_tests = (
        run_try_job_for_reliable_failure_pipeline._GetReliableTargetedTests(
            {'step1 on platform': ['step1_test1']},
            {'step1 on platform': ('step1',{})}))

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
        ['rev2'], TryJobType.COMPILE, [], None, [])

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
        *tuple(_SAMPLE_CLASSIFIED_TESTS_BY_STEP['1'].iteritems()))

    self.assertTrue(_MockTryJobPipeline.STARTED)


  def testNoNeedToTriggerTryJobIfTargetedTestsEmpty(self):

    self.mock(
        run_try_job_for_reliable_failure_pipeline.try_job_pipeline,
        'TryJobPipeline', _MockTryJobPipeline)
    _MockTryJobPipeline.STARTED = False

    pipeline = RunTryJobForReliableFailurePipeline()
    pipeline.run(
        self.master_name, self.builder_name, self.build_number, 'rev1', 'rev2',
        ['rev2'], TryJobType.TEST, None, {'step1': ['test1']},
        *tuple({'step1': ('step1', {})}.iteritems()))

    self.assertFalse(_MockTryJobPipeline.STARTED)
