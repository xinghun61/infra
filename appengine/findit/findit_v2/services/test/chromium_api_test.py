# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from mock import patch
import unittest

from buildbucket_proto.build_pb2 import Build
from buildbucket_proto.common_pb2 import Log
from buildbucket_proto.step_pb2 import Step
from common.waterfall import buildbucket_client
from findit_v2.services.chromium_api import ChromiumProjectAPI
from findit_v2.services.failure_type import StepTypeEnum
from infra_api_clients import logdog_util
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

  def _CreateBuildbucketBuild(
      self,
      build_id,
      build_number,
      master='master',
      builder='builder',
      dimensions=None,
  ):
    build = Build(id=build_id, number=build_number)
    build.input.gitiles_commit.host = 'gitiles.host.com'
    build.input.gitiles_commit.project = 'project/name'
    build.input.gitiles_commit.ref = 'ref/heads/master'
    build.input.gitiles_commit.id = 'git_sha'
    build.input.properties['mastername'] = master
    build.builder.builder = builder
    for d in (dimensions or []):
      new_d = build.infra.swarming.task_dimensions.add()
      new_d.key = d['key']
      new_d.value = d['value']
    return build

  @patch.object(logdog_util, 'GetLogFromViewUrl')
  def testGetCompileFailures(self, mock_get_log):
    build_id = 8765432109123
    build_number = 123
    build = self._CreateBuildbucketBuild(build_id, build_number)

    step_name = 'compile'
    log = Log()
    log.name = 'json.output[ninja_info]'
    log.view_url = 'https://dummy/path'
    step = Step()
    step.name = step_name
    step.logs.extend([log])
    build.steps.extend([step])
    mock_get_log.return_value = {
        'failures': [{
            'output': '...some very long \n multi-line \n string',
            'output_nodes': [
                'broken_target1',
                'broken_target2',
            ],
            'rule': 'ACTION',
        }],
    }
    expected_response = {
        'compile': {
            'failures': {
                frozenset(['broken_target1', 'broken_target2']): {
                    'properties': {
                        'rule': 'ACTION'
                    },
                    'first_failed_build': {
                        'commit_id': 'git_sha',
                        'id': 8765432109123,
                        'number': 123,
                    },
                    'last_passed_build': None
                }
            },
            'first_failed_build': {
                'commit_id': 'git_sha',
                'id': 8765432109123,
                'number': 123,
            },
            'last_passed_build': None
        }
    }

    self.assertEqual(expected_response,
                     ChromiumProjectAPI().GetCompileFailures(build, [step]))

  @patch.object(logdog_util, 'GetLogFromViewUrl')
  def testGetCompileFailuresEmptyNinjaInfo(self, mock_get_log):
    build_id = 8765432109123
    build_number = 123
    build = self._CreateBuildbucketBuild(build_id, build_number)

    step_name = 'compile'
    log = Log()
    log.name = 'json.output[ninja_info]'
    log.view_url = 'https://dummy/path'
    step = Step()
    step.name = step_name
    step.logs.extend([log])
    build.steps.extend([step])
    # Cover the case when the retrieval of the log returns a string with
    # json-encoded info.
    mock_get_log.return_value = "{}"
    expected_response = {}
    self.assertEqual(expected_response,
                     ChromiumProjectAPI().GetCompileFailures(build, [step]))

  @patch.object(logdog_util, 'GetLogFromViewUrl')
  def testGetCompileFailuresMultipleFailuresInNinjaInfo(self, mock_get_log):
    build_id = 8765432109123
    build_number = 123
    build = self._CreateBuildbucketBuild(build_id, build_number)

    step_name = 'compile'
    log = Log()
    log.name = 'json.output[ninja_info]'
    log.view_url = 'https://dummy/path'
    step = Step()
    step.name = step_name
    step.logs.extend([log])
    build.steps.extend([step])
    # This is not expected, but should behave correctly nonetheless.
    mock_get_log.return_value = {
        'failures': [
            {
                'output': '...some very long \n multi-line \n string',
                'output_nodes': ['broken_target1',],
                'rule': 'ACTION',
            },
            {
                'output': '...some very long \n multi-line \n string',
                'output_nodes': ['broken_target2',],
                'rule': 'ACTION',
            },
        ],
    }
    expected_response = {
        'compile': {
            'failures': {
                frozenset(['broken_target1']): {
                    'properties': {
                        'rule': 'ACTION'
                    },
                    'first_failed_build': {
                        'commit_id': 'git_sha',
                        'id': 8765432109123,
                        'number': 123,
                    },
                    'last_passed_build': None
                },
                frozenset(['broken_target2']): {
                    'properties': {
                        'rule': 'ACTION'
                    },
                    'first_failed_build': {
                        'commit_id': 'git_sha',
                        'id': 8765432109123,
                        'number': 123,
                    },
                    'last_passed_build': None
                }
            },
            'first_failed_build': {
                'commit_id': 'git_sha',
                'id': 8765432109123,
                'number': 123,
            },
            'last_passed_build': None
        }
    }

    self.assertEqual(expected_response,
                     ChromiumProjectAPI().GetCompileFailures(build, [step]))

  @patch.object(logdog_util, 'GetLogFromViewUrl')
  def testGetCompileFailuresMultipleSteps(self, mock_get_log):
    build_id = 8765432109123
    build_number = 123
    build = self._CreateBuildbucketBuild(build_id, build_number)

    step_name = 'compile'
    log = Log()
    log.name = 'json.output[ninja_info]'
    log.view_url = 'https://dummy/path'
    step = Step()
    step.name = step_name
    step.logs.extend([log])

    step2_name = 'compile-like-step'
    log = Log()
    log.name = 'json.output[ninja_info]'
    log.view_url = 'https://dummy/path'
    step2 = Step()
    step2.name = step2_name
    step2.logs.extend([log])
    build.steps.extend([step, step2])
    mock_get_log.side_effect = [
        {
            'failures': [{
                'output': '...some very long \n multi-line \n string',
                'output_nodes': [
                    'broken_target1',
                    'broken_target2',
                ],
                'rule': 'ACTION',
            }],
        },
        {
            'failures': [{
                'output': '...some very long \n multi-line \n string',
                'output_nodes': [
                    'broken_target3',
                    'broken_target4',
                ],
                'rule': 'ACTION',
            }],
        },
    ]
    expected_response = {
        'compile': {
            'failures': {
                frozenset(['broken_target1', 'broken_target2']): {
                    'first_failed_build': {
                        'commit_id': 'git_sha',
                        'id': 8765432109123,
                        'number': 123,
                    },
                    'properties': {
                        'rule': 'ACTION'
                    },
                    'last_passed_build': None
                }
            },
            'first_failed_build': {
                'commit_id': 'git_sha',
                'id': 8765432109123,
                'number': 123,
            },
            'last_passed_build': None
        },
        'compile-like-step': {
            'failures': {
                frozenset(['broken_target3', 'broken_target4']): {
                    'properties': {
                        'rule': 'ACTION'
                    },
                    'first_failed_build': {
                        'commit_id': 'git_sha',
                        'id': 8765432109123,
                        'number': 123,
                    },
                    'last_passed_build': None
                }
            },
            'first_failed_build': {
                'commit_id': 'git_sha',
                'id': 8765432109123,
                'number': 123,
            },
            'last_passed_build': None
        }
    }

    self.assertEqual(
        expected_response,
        ChromiumProjectAPI().GetCompileFailures(build, [step, step2]))

  @patch.object(buildbucket_client, 'GetV2Build')
  def testGetCompileRerunBuildInputProperties(self, mock_bb):
    mock_bb.return_value = self._CreateBuildbucketBuild(
        800000001234, 1234, 'chromium.linux', 'Linux Builder')
    props = ChromiumProjectAPI().GetCompileRerunBuildInputProperties({
        'compile': ['bad_target1', 'bad_tests']
    }, 800000001234)
    self.assertEqual(props['target_builder'], {
        'master': 'chromium.linux',
        'builder': 'Linux Builder'
    })
    self.assertEqual(props['mastername'], 'chromium.linux')
    self.assertEqual(
        sorted(props['compile_targets']), ['bad_target1', 'bad_tests'])

  @patch.object(buildbucket_client, 'GetV2Build')
  def testGetTestRerunBuildInputProperties(self, mock_bb):
    mock_bb.return_value = self._CreateBuildbucketBuild(
        800000009999, 9999, 'chromium.linux', 'Linux Tests')
    props = ChromiumProjectAPI().GetTestRerunBuildInputProperties({
        'complexitor_tests': {
            'tests': [
                {
                    'name': 'TestTrueNatureOf42',
                    'properties': {
                        'ignored': 'at the moment'
                    }
                },
                {
                    'name': 'ValidateFTLCommunication',
                    'properties': {
                        'ignored': 'also'
                    }
                },
            ],
            'properties': {
                'this is': 'ignored',
            },
        },
    }, 800000009999)
    self.assertEqual(props['target_builder'], {
        'master': 'chromium.linux',
        'builder': 'Linux Tests'
    })
    self.assertEqual(props['mastername'], 'chromium.linux')
    self.assertEqual(props['tests'], {
        'complexitor_tests': ['TestTrueNatureOf42', 'ValidateFTLCommunication']
    })

  @patch.object(buildbucket_client, 'GetV2Build')
  def testGetRerunDimensions(self, mock_bb):
    mock_bb.return_value = self._CreateBuildbucketBuild(
        800000009999,
        9999,
        'chromium.linux',
        'Linux Tests',
        dimensions=[{
            'key': 'os',
            'value': 'Mac',
        }, {
            'key': 'cpu',
            'value': 'x86',
        }, {
            'key': 'ssd',
            'value': '1',
        }],
    )
    dimensions = ChromiumProjectAPI().GetRerunDimensions(800000009999)
    self.assertEqual(dimensions, [{'key': 'os', 'value': 'Mac'}])
