# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from model import result_status
from model.wf_analysis import WfAnalysis
from waterfall import update_analysis_with_flake_info_pipeline
from waterfall.test import wf_testcase
from waterfall.update_analysis_with_flake_info_pipeline import (
    UpdateAnalysisWithFlakeInfoPipeline)

class UpdateAnalysisWithFlakeInfoPipelineTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(UpdateAnalysisWithFlakeInfoPipelineTest, self).setUp()
    self.master_name = 'm'
    self.builder_name = 'b'
    self.build_number = 123

  def testAllTestsFlaky(self):
    task_results = ['a on platform', ['a', [], ['t1', 't2']]]

    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.result = {
        'failures': [
            {
                'step_name': 'a on platform',
                'tests': [
                    {
                        'test_name': 't1'
                    },
                    {
                        'test_name': 't2'
                    }
                ]
            }
        ]
    }
    analysis.put()

    pipeline = UpdateAnalysisWithFlakeInfoPipeline()
    pipeline.run(
        self.master_name, self.builder_name, self.build_number, task_results)

    expected_result = {
        'failures': [
            {
                'step_name': 'a on platform',
                'flaky': True,
                'tests': [
                    {
                        'test_name': 't1',
                        'flaky': True
                    },
                    {
                        'test_name': 't2',
                        'flaky': True
                    }
                ]
            }
        ]
    }
    analysis = WfAnalysis.Get(
        self.master_name, self.builder_name, self.build_number)
    self.assertEqual(result_status.FLAKY, analysis.result_status)
    self.assertEqual(expected_result, analysis.result)

  def testGetFlakyTestsNoFlaky(self):
    task_results = {
        'a on platform': ('a', [], [])
    }

    self.assertEqual(
        {}, update_analysis_with_flake_info_pipeline._GetFlakyTests(
            task_results))

  def testUpdateAnalysisWithFlakeInfoNoFlaky(self):
    self.assertFalse(
        update_analysis_with_flake_info_pipeline._UpdateAnalysisWithFlakeInfo(
            self.master_name, self.builder_name, self.build_number, None))

  def testUpdateAnalysisWithFlakeInfoNoanalysis(self):
    self.assertFalse(
        update_analysis_with_flake_info_pipeline._UpdateAnalysisWithFlakeInfo(
            self.master_name, self.builder_name, self.build_number,
            {'a': ['b']}))

  def testUpdateAnalysisWithFlakeInfo(self):
    flaky_tests = {
        'a_test': ['test1'],
        'b_test': ['test1']
    }

    analysis = WfAnalysis.Create(
        self.master_name, self.builder_name, self.build_number)
    analysis.result = {
        'failures': [
            {
                'step_name': 'a_test',
                'tests': [
                    {
                        'test_name': 'test1'
                    },
                    {
                        'test_name': 'test2'
                    }
                ]
            },
            {
                'step_name': 'b_test',
                'tests': [
                    {
                      'test_name': 'test1'
                    }
                ]
            },
            {
                'step_name': 'c_test',
                'flaky': True
            },
            {
                'step_name': 'd_test'
            }
        ]
    }
    analysis.put()

    expected_result = {
        'failures': [
            {
                'step_name': 'a_test',
                'flaky': False,
                'tests': [
                    {
                        'test_name': 'test1',
                        'flaky': True
                    },
                    {
                        'test_name': 'test2'
                    }
                ]
            },
            {
                'step_name': 'b_test',
                'flaky': True,
                'tests': [
                    {
                      'test_name': 'test1',
                      'flaky': True
                    }
                ]
            },
            {
                'step_name': 'c_test',
                'flaky': True
            },
            {
                'step_name': 'd_test'
            }
        ]
    }

    self.assertTrue(
        update_analysis_with_flake_info_pipeline._UpdateAnalysisWithFlakeInfo(
            self.master_name, self.builder_name, self.build_number,
            flaky_tests))
    analysis = WfAnalysis.Get(
        self.master_name, self.builder_name, self.build_number)
    self.assertEqual(expected_result, analysis.result)