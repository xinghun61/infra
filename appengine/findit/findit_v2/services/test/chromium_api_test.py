# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from mock import patch
import unittest

from buildbucket_proto.step_pb2 import Step

from findit_v2.services.chromium_api import ChromiumProjectAPI
from findit_v2.services.failure_type import StepTypeEnum
from services.compile_failure import compile_failure_analysis
from services.test_failure import test_failure_analysis


class ChromiumProjectAPITest(unittest.TestCase):

  def testCompileStep(self):
    step = Step()
    step.name = 'compile'
    log = step.logs.add()
    log.name = 'stdout'
    self.assertEqual(StepTypeEnum.COMPILE,
                     ChromiumProjectAPI().ClassifyStepType(None, step))

  def testTestStep(self):
    step = Step()
    step.name = 'browser_tests'
    log = step.logs.add()
    log.name = 'step_metadata'
    self.assertEqual(StepTypeEnum.TEST,
                     ChromiumProjectAPI().ClassifyStepType(None, step))

  def testInfraStep(self):
    step = Step()
    step.name = 'infra'
    log = step.logs.add()
    log.name = 'report'
    self.assertEqual(StepTypeEnum.INFRA,
                     ChromiumProjectAPI().ClassifyStepType(None, step))

  @patch.object(test_failure_analysis, 'AnalyzeTestFailure')
  def testTestHeuristicAnalysis(self, mock_analyze):
    self.maxDiff = None
    mock_analyze.return_value = ({
        'failures': [
            {
                'step_name':
                    'test_a',
                'supported':
                    True,
                'first_failure':
                    230,
                'last_pass':
                    229,
                'suspected_cls': [{
                    'build_number': 230,
                    'repo_name': 'chromium',
                    'revision': 'a_git_hash',
                    'commit_position': 56789,
                    'score': 11,
                    'hints': {
                        'add a/b/x.cc': 5,
                        'delete a/b/y.cc': 5,
                        'modify e/f/z.cc': 1,
                    }
                },],
                'tests': [{
                    'first_failure':
                        230,
                    'last_pass':
                        229,
                    'test_name':
                        'test_a1',
                    'suspected_cls': [{
                        'build_number': 230,
                        'repo_name': 'chromium',
                        'revision': 'a_git_hash',
                        'commit_position': 56789,
                        'score': 11,
                        'hints': {
                            'add a/b/x.cc': 5,
                            'delete a/b/y.cc': 5,
                            'modify e/f/z.cc': 1,
                        }
                    },]
                }],
            },
            {
                'step_name':
                    'test_b',
                'supported':
                    True,
                'first_failure':
                    230,
                'last_pass':
                    229,
                'suspected_cls': [{
                    'build_number': 230,
                    'repo_name': 'chromium',
                    'revision': 'b_git_hash',
                    'commit_position': 56788,
                    'score': 5,
                    'hints': {
                        'add odd/path/f.cc': 5,
                    },
                }],
                'tests': [
                    {
                        'first_failure':
                            230,
                        'last_pass':
                            229,
                        'test_name':
                            'test_b1',
                        'suspected_cls': [{
                            'build_number': 230,
                            'repo_name': 'chromium',
                            'revision': 'b_git_hash',
                            'commit_position': 56788,
                            'score': 5,
                            'hints': {
                                'add odd/path/f.cc': 5,
                            }
                        },]
                    },
                    {
                        'first_failure':
                            230,
                        'last_pass':
                            229,
                        'test_name':
                            'test_b2',
                        'suspected_cls': [{
                            'build_number': 230,
                            'repo_name': 'chromium',
                            'revision': 'b_git_hash',
                            'commit_position': 56788,
                            'score': 5,
                            'hints': {
                                'add odd/path/f.cc': 5,
                            }
                        },]
                    },
                ],
            },
        ]
    }, None)
    self.assertEqual(
        {
            ('test_a', frozenset(['test_a1'])): [{
                'commit_position': 56789,
                'hints': {
                    'add a/b/x.cc': 5,
                    'delete a/b/y.cc': 5,
                    'modify e/f/z.cc': 1
                },
                'revision': 'a_git_hash'
            }],
            ('test_b', frozenset(['test_b1', 'test_b2'])): [{
                'commit_position': 56788,
                'hints': {
                    'add odd/path/f.cc': 5,
                },
                'revision': 'b_git_hash'
            }]
        },
        ChromiumProjectAPI().HeuristicAnalysisForTest(
            # These are passed as-is to the compile_failure_analysis module,
            # tested elsewhere.
            None,
            None,
            None,
            None))

  @patch.object(compile_failure_analysis, 'AnalyzeCompileFailure')
  def testCompileHeuristicAnalysis(self, mock_analyze):
    # Ensure that the output of this api is in the following format:
    # map from ('step', frozenset['target1']) -> {'revision', 'commit_position',
    # 'hints': {'hint' -> score}
    mock_analyze.return_value = ({
        'failures': [{
            'step_name':
                'compile',
            'supported':
                True,
            'first_failure':
                230,
            'last_pass':
                229,
            'suspected_cls': [{
                'build_number': 230,
                'repo_name': 'chromium',
                'revision': 'a_git_hash',
                'commit_position': 56789,
                'score': 11,
                'hints': {
                    'add a/b/x.cc': 5,
                    'delete a/b/y.cc': 5,
                    'modify e/f/z.cc': 1,
                }
            },],
        },]
    }, None)
    self.assertEqual(
        {
            ('compile', frozenset([])): [{
                'commit_position': 56789,
                'hints': {
                    'add a/b/x.cc': 5,
                    'delete a/b/y.cc': 5,
                    'modify e/f/z.cc': 1
                },
                'revision': 'a_git_hash'
            }]
        },
        ChromiumProjectAPI().HeuristicAnalysisForCompile(
            # These are passed as-is to the compile_failure_analysis module,
            # tested elsewhere.
            None,
            None,
            None,
            None))
