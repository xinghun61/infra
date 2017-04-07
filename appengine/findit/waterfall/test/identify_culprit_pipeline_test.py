# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing

from common.waterfall import failure_type
from gae_libs.pipeline_wrapper import pipeline_handlers
from libs import analysis_status
from model import result_status
from model.wf_analysis import WfAnalysis
from model.wf_suspected_cl import WfSuspectedCL
from waterfall import build_failure_analysis
from waterfall import identify_culprit_pipeline


class IdentifyCulpritPipelineTest(testing.AppengineTestCase):
  app_module = pipeline_handlers._APP

  def testGetResultAnalysisStatusFoundUntriaged(self):
    dummy_result = {
        'failures': [
            {
                'step_name': 'a',
                'first_failure': 98,
                'last_pass': None,
                'suspected_cls': [
                    {
                        'build_number': 99,
                        'repo_name': 'chromium',
                        'revision': 'r99_2',
                        'commit_position': None,
                        'url': None,
                        'score': 1,
                        'hints': {
                            'modified f99_2.cc (and it was in log)': 1,
                        },
                    }
                ],
            },
            {
                'step_name': 'b',
                'first_failure': 98,
                'last_pass': None,
                'suspected_cls': [
                    {
                        'build_number': 99,
                        'repo_name': 'chromium',
                        'revision': 'r99_1',
                        'commit_position': None,
                        'url': None,
                        'score': 5,
                        'hints': {
                            'added x/y/f99_1.cc (and it was in log)': 5,
                        },
                    }
                ],
            }
        ]
    }

    self.assertEqual(result_status.FOUND_UNTRIAGED,
                     identify_culprit_pipeline._GetResultAnalysisStatus(
                         dummy_result))

  def testGetResultAnalysisStatusNotFoundUntriaged(self):
    dummy_result = {
        'failures': [
            {
                'step_name': 'a',
                'first_failure': 98,
                'last_pass': None,
                'suspected_cls': [],
            },
            {
                'step_name': 'b',
                'first_failure': 98,
                'last_pass': None,
                'suspected_cls': [],
            }
        ]
    }

    self.assertEqual(result_status.NOT_FOUND_UNTRIAGED,
                     identify_culprit_pipeline._GetResultAnalysisStatus(
                         dummy_result))

  def testIdentifyCulpritPipeline(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.result = None
    analysis.status = analysis_status.RUNNING
    analysis.put()

    failure_info = {
      'master_name': master_name,
      'builder_name': builder_name,
      'build_number': build_number,
      'failure_type': failure_type.TEST
    }
    change_logs = {}
    deps_info = {}
    signals = {}

    dummy_result = {'failures': []}

    def MockAnalyzeBuildFailure(*_):
      return dummy_result, []

    self.mock(build_failure_analysis,
              'AnalyzeBuildFailure', MockAnalyzeBuildFailure)

    pipeline = identify_culprit_pipeline.IdentifyCulpritPipeline(
        failure_info, change_logs, deps_info, signals, True)
    pipeline.start()
    self.execute_queued_tasks()

    expected_suspected_cls = []

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertTrue(analysis.build_completed)
    self.assertIsNotNone(analysis)
    self.assertEqual(dummy_result, analysis.result)
    self.assertEqual(analysis_status.COMPLETED, analysis.status)
    self.assertIsNone(analysis.result_status)
    self.assertEqual(expected_suspected_cls, analysis.suspected_cls)

  def testSaveSuspectedCLs(self):
    suspected_cls = [
        {
            'repo_name': 'chromium',
            'revision': 'r98_1',
            'commit_position': None,
            'url': None,
            'failures': {
                'b': ['Unittest2.Subtest1', 'Unittest3.Subtest2']
            },
            'top_score': 4
        }
    ]
    master_name = 'm'
    builder_name = 'b'
    build_number = 98
    test_type = failure_type.TEST

    identify_culprit_pipeline._SaveSuspectedCLs(
        suspected_cls, master_name, builder_name, build_number, test_type)

    suspected_cl = WfSuspectedCL.Get('chromium', 'r98_1')
    self.assertIsNotNone(suspected_cl)

  def testGetSuspectedCLsWithOnlyCLInfo(self):
    suspected_cls = [
        {
            'repo_name': 'chromium',
            'revision': 'r98_1',
            'commit_position': None,
            'url': None,
            'failures': {
                'b': ['Unittest2.Subtest1', 'Unittest3.Subtest2']
            },
            'top_score': 4
        }
    ]

    expected_new_suspected_cls = [
        {
            'repo_name': 'chromium',
            'revision': 'r98_1',
            'commit_position': None,
            'url': None
        }
    ]

    self.assertEqual(
        expected_new_suspected_cls,
        identify_culprit_pipeline._GetSuspectedCLsWithOnlyCLInfo(suspected_cls))
