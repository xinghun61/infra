# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from common.findit_http_client import FinditHttpClient
from infra_api_clients.swarming.swarming_task_data import SwarmingTaskData
from libs.test_results import test_results_util
from libs.test_results.webkit_layout_test_results import WebkitLayoutTestResults
from model.flake.flake_analysis_request import BuildStep
from services import swarmed_test_util
from services import swarming
from waterfall import buildbot
from waterfall import build_util
from waterfall.flake import step_mapper
from waterfall.test import wf_testcase

_SAMPLE_OUTPUT = {
    'all_tests': ['test1'],
    'per_iteration_data': [{
        'is_dict': True
    }]
}


class StepMapperTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(StepMapperTest, self).setUp()
    self.http_client = FinditHttpClient()
    self.master_name = 'tryserver.m'
    self.wf_master_name = 'm'
    self.builder_name = 'b'
    self.build_number = 123
    self.step_name = 'browser_tests on platform'
    self.build_step = BuildStep.Create(self.master_name, self.builder_name,
                                       self.build_number, self.step_name, None)
    self.build_step.put()

    self.wf_build_step = BuildStep.Create(self.wf_master_name,
                                          self.builder_name, self.build_number,
                                          self.step_name, None)
    self.wf_build_step.put()

  @mock.patch.object(
      step_mapper,
      '_GetMatchingWaterfallBuildStep',
      return_value=('tryserver.m', 'b', 123, 'browser_tests',
                    wf_testcase.SAMPLE_STEP_METADATA))
  @mock.patch.object(
      swarmed_test_util,
      'GetTestResultForSwarmingTask',
      return_value=_SAMPLE_OUTPUT)
  def testFindMatchingWaterfallStep(self, *_):
    step_mapper.FindMatchingWaterfallStep(self.build_step, 'test1')
    self.assertTrue(self.build_step.swarmed)
    self.assertTrue(self.build_step.supported)

  @mock.patch.object(
      step_mapper,
      '_GetMatchingWaterfallBuildStep',
      return_value=('tryserver.m', None, 123, 'browser_tests',
                    wf_testcase.SAMPLE_STEP_METADATA))
  def testFindMatchingWaterfallStepNoMatch(self, _):
    step_mapper.FindMatchingWaterfallStep(self.build_step, 'test1')
    self.assertFalse(self.build_step.swarmed)
    self.assertIsNone(self.build_step.wf_builder_name)

  @mock.patch.object(
      step_mapper,
      '_GetMatchingWaterfallBuildStep',
      return_value=('tryserver.m', 'b', 123, 'browser_tests',
                    wf_testcase.SAMPLE_STEP_METADATA_NOT_SWARMED))
  def testFindMatchingWaterfallStepNotSwarmed(self, _):
    step_mapper.FindMatchingWaterfallStep(self.build_step, 'test1')
    self.assertFalse(self.build_step.swarmed)

  @mock.patch.object(
      step_mapper,
      '_GetMatchingWaterfallBuildStep',
      return_value=('tryserver.m', 'b', 123, 'browser_tests',
                    wf_testcase.SAMPLE_STEP_METADATA))
  @mock.patch.object(
      swarmed_test_util, 'GetTestResultForSwarmingTask', return_value=None)
  def testFindMatchingWaterfallStepNoOutput(self, *_):
    step_mapper.FindMatchingWaterfallStep(self.build_step, 'test1')
    self.assertTrue(self.build_step.swarmed)
    self.assertFalse(self.build_step.supported)

  @mock.patch.object(
      build_util,
      'GetWaterfallBuildStepLog',
      return_value=wf_testcase.SAMPLE_STEP_METADATA)
  @mock.patch.object(buildbot, 'GetRecentCompletedBuilds', return_value=[123])
  @mock.patch.object(
      swarming,
      'ListSwarmingTasksDataByTags',
      return_value=[
          SwarmingTaskData({
              'tags': ['stepname:browser_tests on platform']
          })
      ])
  def testGetMatchingWaterfallBuildStep(self, *_):
    master_name, builder_name, build_number, step_name, step_metadata = (
        step_mapper._GetMatchingWaterfallBuildStep(self.build_step,
                                                   self.http_client))
    self.assertEqual(master_name, self.wf_master_name)
    self.assertEqual(builder_name, self.builder_name)
    self.assertEqual(build_number, self.build_number)
    self.assertEqual(step_name, self.step_name)
    self.assertEqual(step_metadata, wf_testcase.SAMPLE_STEP_METADATA)

  @mock.patch.object(build_util, 'GetWaterfallBuildStepLog', return_value=None)
  def testGetMatchingWaterfallBuildStepNoMetadata(self, _):
    _, _, _, _, step_metadata = step_mapper._GetMatchingWaterfallBuildStep(
        self.build_step, self.http_client)
    self.assertIsNone(step_metadata)

  @mock.patch.object(build_util, 'GetWaterfallBuildStepLog')
  def testGetMatchingWaterfallBuildStepNoWfBuilderName(self, mock_fn):
    mock_fn.return_value = {'waterfall_mastername': self.wf_master_name}
    _, _, _, _, step_metadata = step_mapper._GetMatchingWaterfallBuildStep(
        self.build_step, self.http_client)
    self.assertIsNone(step_metadata)

  @mock.patch.object(build_util, 'GetWaterfallBuildStepLog')
  def testGetMatchingWaterfallBuildStepNoStep(self, mock_fn):
    mock_fn.return_value = {
        'waterfall_mastername': self.wf_master_name,
        'waterfall_buildername': 'b'
    }
    _, _, _, _, step_metadata = step_mapper._GetMatchingWaterfallBuildStep(
        self.build_step, self.http_client)
    self.assertIsNone(step_metadata)

  @mock.patch.object(
      build_util,
      'GetWaterfallBuildStepLog',
      return_value=wf_testcase.SAMPLE_STEP_METADATA)
  @mock.patch.object(buildbot, 'GetRecentCompletedBuilds', return_value=None)
  def testGetMatchingWaterfallBuildStepNoBuild(self, *_):
    master_name, _, _, _, _ = step_mapper._GetMatchingWaterfallBuildStep(
        self.build_step, self.http_client)
    self.assertIsNone(master_name)

  @mock.patch.object(
      build_util,
      'GetWaterfallBuildStepLog',
      return_value=wf_testcase.SAMPLE_STEP_METADATA)
  @mock.patch.object(buildbot, 'GetRecentCompletedBuilds', return_value=[123])
  @mock.patch.object(swarming, 'ListSwarmingTasksDataByTags', return_value=None)
  def testGetMatchingWaterfallBuildStepNoTask(self, *_):
    master_name, _, _, _, _ = step_mapper._GetMatchingWaterfallBuildStep(
        self.build_step, self.http_client)
    self.assertIsNone(master_name)

  @mock.patch.object(build_util, 'GetWaterfallBuildStepLog', return_value={})
  def testFindMatchingWaterfallStepForWfStepNoStepMetadata(self, _):
    step_mapper.FindMatchingWaterfallStep(self.wf_build_step, 'test1')
    self.assertEqual(self.wf_build_step.wf_build_number,
                     self.wf_build_step.build_number)
    self.assertFalse(self.wf_build_step.swarmed)
    self.assertFalse(self.wf_build_step.supported)

  @mock.patch.object(
      swarmed_test_util,
      'GetTestResultForSwarmingTask',
      return_value=_SAMPLE_OUTPUT)
  @mock.patch.object(
      build_util,
      'GetWaterfallBuildStepLog',
      return_value=wf_testcase.SAMPLE_STEP_METADATA)
  def testFindMatchingWaterfallStepForWfStep(self, *_):
    step_mapper.FindMatchingWaterfallStep(self.wf_build_step, 'test1')
    self.assertTrue(self.wf_build_step.swarmed)
    self.assertTrue(self.wf_build_step.supported)

  @mock.patch.object(
      swarmed_test_util,
      'GetTestResultForSwarmingTask',
      return_value=_SAMPLE_OUTPUT)
  @mock.patch.object(
      build_util,
      'GetWaterfallBuildStepLog',
      return_value=wf_testcase.SAMPLE_STEP_METADATA)
  @mock.patch.object(test_results_util, 'GetTestResultObject')
  def testFindMatchingWaterfallStepNotSupportOtherIsolatedScriptTests(
      self, mock_object, *_):
    mock_object.return_value = WebkitLayoutTestResults(None)
    step_mapper.FindMatchingWaterfallStep(self.wf_build_step, 'test1')
    self.assertTrue(self.wf_build_step.swarmed)
    self.assertFalse(self.wf_build_step.supported)
