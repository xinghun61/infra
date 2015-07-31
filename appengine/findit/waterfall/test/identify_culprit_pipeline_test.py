# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from pipeline_utils.appengine_third_party_pipeline_python_src_pipeline \
    import handlers
from testing_utils import testing

from model.wf_analysis import WfAnalysis
from model import wf_analysis_status
from model import wf_analysis_result_status
from waterfall import build_failure_analysis
from waterfall import identify_culprit_pipeline


class IdentifyCulpritPipelineTest(testing.AppengineTestCase):
  app_module = handlers._APP

  def testGetSuspectedCLs(self):
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
                        'revision': 'r99_1',
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
                        'revision': 'r99_2',
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

    expected_suspected_cls = [
        {
            'repo_name': 'chromium',
            'revision': 'r99_1',
            'commit_position': None,
            'url': None
        },
        {
            'repo_name': 'chromium',
            'revision': 'r99_2',
            'commit_position': None,
            'url': None
        }
    ]

    self.assertEqual(expected_suspected_cls,
                     identify_culprit_pipeline._GetSuspectedCLs(dummy_result))

  def testGetSuspectedCLsNoDuplicates(self):
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
                        'revision': 'r99_1',
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

    expected_suspected_cls = [
        {
            'repo_name': 'chromium',
            'revision': 'r99_1',
            'commit_position': None,
            'url': None
        }
    ]

    self.assertEqual(expected_suspected_cls,
                     identify_culprit_pipeline._GetSuspectedCLs(dummy_result))

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

    self.assertEqual(wf_analysis_result_status.FOUND_UNTRIAGED,
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

    self.assertEqual(wf_analysis_result_status.NOT_FOUND_UNTRIAGED,
                     identify_culprit_pipeline._GetResultAnalysisStatus(
                         dummy_result))

  def testIdentifyCulpritPipeline(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 123

    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.result = None
    analysis.status = wf_analysis_status.ANALYZING
    analysis.put()

    failure_info = {
      'master_name': master_name,
      'builder_name': builder_name,
      'build_number': build_number,
    }
    change_logs = {}
    deps_info = {}
    signals = {}

    dummy_result = {'failures': []}

    def MockAnalyzeBuildFailure(*_):
      return dummy_result

    self.mock(build_failure_analysis,
              'AnalyzeBuildFailure', MockAnalyzeBuildFailure)

    pipeline = identify_culprit_pipeline.IdentifyCulpritPipeline(
        failure_info, change_logs, deps_info, signals)
    pipeline.start()
    self.execute_queued_tasks()

    expected_suspected_cls = []

    analysis = WfAnalysis.Get(master_name, builder_name, build_number)
    self.assertIsNotNone(analysis)
    self.assertEqual(dummy_result, analysis.result)
    self.assertEqual(wf_analysis_status.ANALYZED, analysis.status)
    self.assertIsNone(analysis.result_status)
    self.assertEqual(expected_suspected_cls, analysis.suspected_cls)
