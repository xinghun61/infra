# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import mock

from common.waterfall import failure_type
from libs.gitiles.diff import ChangeType
from model.wf_analysis import WfAnalysis
from services import build_failure_analysis
from services import ci_failure
from services import deps
from services import git
from services.compile_failure import compile_failure_analysis
from services.compile_failure import extract_compile_signal
from waterfall import waterfall_config
from waterfall.test import wf_testcase


class CompileFailureAnalysisTest(wf_testcase.WaterfallTestCase):

  def testAnalyzeCompileFailureByDependencies(self):
    failure_info = {
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 99,
        'failure_type': failure_type.COMPILE,
        'failed': True,
        'chromium_revision': 'r99_2',
        'failed_steps': {
            'compile': {
                'current_failure': 99,
                'first_failure': 98,
            },
        },
        'builds': {
            99: {
                'blame_list': ['r99_1', 'r99_2'],
            },
            98: {
                'blame_list': ['r98_1'],
            },
        }
    }
    change_logs = {
        'r99_1': {
            'revision':
                'r99_1',
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'a/b/f99_1.cc',
                    'new_path': 'a/b/f99_1.cc'
                },
            ],
            'author': {
                'email': 'author@abc.com'
            }
        },
        'r99_2': {
            'revision':
                'r99_2',
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'a/b/f99_2.cc',
                    'new_path': 'a/b/f99_2.cc'
                },
            ],
            'author': {
                'email': 'author@abc.com'
            }
        },
        'r98_1': {
            'revision':
                'r98_1',
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'y/z/f98.cc',
                    'new_path': 'y/z/f98.cc'
                },
            ],
            'author': {
                'email': 'author@abc.com'
            }
        },
    }
    deps_info = {}
    failure_signals_json = {
        'compile': {
            'files': {},
            'failed_edges': [{
                'dependencies': ['src/a/b/f99_2.cc']
            }]
        },
    }
    expected_analysis_result = {
        'failures': [{
            'step_name':
                'compile',
            'supported':
                True,
            'first_failure':
                98,
            'last_pass':
                None,
            'suspected_cls': [{
                'build_number': 99,
                'repo_name': 'chromium',
                'revision': 'r99_2',
                'commit_position': None,
                'url': None,
                'score': 2,
                'hints': {
                    ('modified f99_2.cc (and it was in'
                     ' dependencies found by ninja)'):
                         2,
                },
            }],
            'new_compile_suspected_cls': [{
                'build_number': 99,
                'repo_name': 'chromium',
                'revision': 'r99_2',
                'commit_position': None,
                'url': None,
                'score': 2,
                'hints': {
                    ('modified f99_2.cc (and it was in'
                     ' dependencies found by ninja)'):
                         2,
                },
            }],
            'use_ninja_dependencies':
                True,
        }]
    }

    expected_suspected_cl = [{
        'repo_name': 'chromium',
        'revision': 'r99_2',
        'commit_position': None,
        'url': None,
        'failures': {
            'compile': []
        },
        'top_score': 2
    }]

    analysis_result, suspected_cls = (
        compile_failure_analysis.AnalyzeCompileFailure(
            failure_info, change_logs, deps_info, failure_signals_json))

    import json
    print json.dumps(expected_analysis_result, indent=2, sort_keys=True)
    print json.dumps(analysis_result, indent=2, sort_keys=True)
    self.assertEqual(expected_analysis_result, analysis_result)
    self.assertEqual(sorted(expected_suspected_cl), sorted(suspected_cls))

  def testAnalyzeTestBuildFailureRecordNewSuspectedCls(self):
    failure_info = {
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 99,
        'failure_type': failure_type.COMPILE,
        'failed': True,
        'chromium_revision': 'r99_2',
        'failed_steps': {
            'compile': {
                'current_failure': 99,
                'first_failure': 98,
            }
        },
        'builds': {
            99: {
                'blame_list': ['r99_1', 'r99_2'],
            },
            98: {
                'blame_list': ['r98_1'],
            }
        }
    }
    change_logs = {
        'r99_1': {
            'revision':
                'r99_1',
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'a/b/f99_1.cc',
                    'new_path': 'a/b/f99_1.cc'
                },
            ],
            'author': {
                'email': 'author@abc.com'
            }
        },
        'r99_2': {
            'revision':
                'r99_2',
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'a/b/f99_2.cc',
                    'new_path': 'a/b/f99_2.cc'
                },
            ],
            'author': {
                'email': 'author@abc.com'
            }
        },
        'r98_1': {
            'revision':
                'r98_1',
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'y/z/f98.cc',
                    'new_path': 'y/z/f98.cc'
                },
            ],
            'author': {
                'email': 'author@abc.com'
            }
        },
    }
    deps_info = {}
    failure_signals_json = {
        'compile': {
            'files': {
                'src/a/b/f99_2.cc': [],
            },
            'failed_edges': [{
                'dependencies': ['src/a/b/f99_2.cc']
            }]
        },
    }
    expected_analysis_result = {
        'failures': [{
            'step_name':
                'compile',
            'supported':
                True,
            'first_failure':
                98,
            'last_pass':
                None,
            'suspected_cls': [{
                'build_number': 99,
                'repo_name': 'chromium',
                'revision': 'r99_2',
                'commit_position': None,
                'url': None,
                'score': 2,
                'hints': {
                    ('modified f99_2.cc (and it was in log)'): 2,
                },
            }],
            'new_compile_suspected_cls': [{
                'build_number': 99,
                'repo_name': 'chromium',
                'revision': 'r99_2',
                'commit_position': None,
                'url': None,
                'score': 2,
                'hints': {
                    ('modified f99_2.cc (and it was in'
                     ' dependencies found by ninja)'):
                         2,
                },
            }],
        }]
    }

    expected_suspected_cl = [{
        'repo_name': 'chromium',
        'revision': 'r99_2',
        'commit_position': None,
        'url': None,
        'failures': {
            'compile': []
        },
        'top_score': 2
    }]

    analysis_result, suspected_cls = (
        compile_failure_analysis.AnalyzeCompileFailure(
            failure_info, change_logs, deps_info, failure_signals_json))

    self.assertEqual(expected_analysis_result, analysis_result)
    self.assertEqual(sorted(expected_suspected_cl), sorted(suspected_cls))

  @mock.patch.object(logging, 'debug')
  def testAnalyzeCompileFailureNoCompileFailure(self, mock_logging):
    failure_info = {'failed_steps': {'a': {}}}
    analysis_result, _ = compile_failure_analysis.AnalyzeCompileFailure(
        failure_info, None, None, None)
    self.assertEqual({'failures': []}, analysis_result)
    mock_logging.assert_has_called_with(
        'No failed compile step when analyzing a compile failure.')

  @mock.patch.object(
      build_failure_analysis,
      'InitializeStepLevelResult',
      return_value={'supported': False})
  def testAnalyzeCompileFailureNotSupported(self, _):
    failure_info = {
        'master_name': 'm',
        'failed_steps': {
            'compile': {
                'current_failure': 123,
                'first_failure': 121
            }
        },
        'builds': {}
    }
    analysis_result, _ = compile_failure_analysis.AnalyzeCompileFailure(
        failure_info, None, None, None)
    self.assertEqual({'failures': []}, analysis_result)

  @mock.patch.object(
      waterfall_config,
      'GetDownloadBuildDataSettings',
      return_value={'use_ninja_output_log': False})
  def testAnalyzeCompileFailureNotUsingNinjaOutput(self, _):
    failure_info = {
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 99,
        'failure_type': failure_type.COMPILE,
        'failed': True,
        'chromium_revision': 'r99_2',
        'failed_steps': {
            'compile': {
                'current_failure': 99,
                'first_failure': 98,
            }
        },
        'builds': {
            99: {
                'blame_list': ['r99_1', 'r99_2'],
            },
            98: {
                'blame_list': ['r98_1'],
            }
        }
    }
    change_logs = {
        'r99_1': {
            'revision':
                'r99_1',
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'a/b/f99_1.cc',
                    'new_path': 'a/b/f99_1.cc'
                },
            ],
            'author': {
                'email': 'author@abc.com'
            }
        },
        'r99_2': {
            'revision':
                'r99_2',
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'a/b/f99_2.cc',
                    'new_path': 'a/b/f99_2.cc'
                },
            ],
            'author': {
                'email': 'author@abc.com'
            }
        },
        'r98_1': {
            'revision':
                'r98_1',
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'y/z/f98.cc',
                    'new_path': 'y/z/f98.cc'
                },
            ],
            'author': {
                'email': 'author@abc.com'
            }
        },
    }
    deps_info = {}
    failure_signals_json = {
        'compile': {
            'files': {
                'src/a/b/f99_2.cc': [],
            },
        },
    }
    expected_analysis_result = {
        'failures': [{
            'step_name':
                'compile',
            'supported':
                True,
            'first_failure':
                98,
            'last_pass':
                None,
            'suspected_cls': [{
                'build_number': 99,
                'repo_name': 'chromium',
                'revision': 'r99_2',
                'commit_position': None,
                'url': None,
                'score': 2,
                'hints': {
                    ('modified f99_2.cc (and it was in log)'): 2,
                },
            }],
        }]
    }

    expected_suspected_cl = [{
        'repo_name': 'chromium',
        'revision': 'r99_2',
        'commit_position': None,
        'url': None,
        'failures': {
            'compile': []
        },
        'top_score': 2
    }]

    analysis_result, suspected_cls = (
        compile_failure_analysis.AnalyzeCompileFailure(
            failure_info, change_logs, deps_info, failure_signals_json))

    self.assertEqual(expected_analysis_result, analysis_result)
    self.assertEqual(sorted(expected_suspected_cl), sorted(suspected_cls))

  @mock.patch.object(
      extract_compile_signal,
      'ExtractSignalsForCompileFailure',
      return_value='signals')
  @mock.patch.object(git, 'PullChangeLogs', return_value={})
  @mock.patch.object(deps, 'ExtractDepsInfo', return_value={})
  @mock.patch.object(
      compile_failure_analysis,
      'AnalyzeCompileFailure',
      return_value=('heuristic_result', []))
  @mock.patch.object(build_failure_analysis,
                     'SaveAnalysisAfterHeuristicAnalysisCompletes')
  @mock.patch.object(build_failure_analysis, 'SaveSuspectedCLs')
  @mock.patch.object(ci_failure, 'CheckForFirstKnownFailure')
  def testHeuristicAnalysisForCompile(self, mock_failure_info, *_):
    failure_info = {
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 99,
        'failure_type': failure_type.COMPILE,
        'failed': True,
        'chromium_revision': 'r99_2',
        'failed_steps': {
            'compile': {
                'current_failure': 99,
                'first_failure': 98,
            }
        },
        'builds': {
            99: {
                'blame_list': ['r99_1', 'r99_2'],
            },
            98: {
                'blame_list': ['r98_1'],
            }
        }
    }
    mock_failure_info.return_value = failure_info

    WfAnalysis.Create('m', 'b', 99).put()
    result = compile_failure_analysis.HeuristicAnalysisForCompile(
        failure_info, True)
    expected_result = {
        'failure_info': failure_info,
        'signals': 'signals',
        'heuristic_result': 'heuristic_result'
    }
    self.assertEqual(result, expected_result)
