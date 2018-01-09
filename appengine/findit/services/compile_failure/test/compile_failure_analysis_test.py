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
from services.parameters import CompileFailureInfo
from services.parameters import CompileHeuristicAnalysisOutput
from services.parameters import CompileHeuristicAnalysisParameters
from waterfall import waterfall_config
from waterfall.test import wf_testcase


class CompileFailureAnalysisTest(wf_testcase.WaterfallTestCase):

  def testAnalyzeCompileFailureByDependencies(self):
    failure_info = {
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 123,
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
            CompileFailureInfo.FromSerializable(failure_info), change_logs,
            deps_info, failure_signals_json))

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
            CompileFailureInfo.FromSerializable(failure_info), change_logs,
            deps_info, failure_signals_json))

    self.assertEqual(expected_analysis_result, analysis_result)
    self.assertEqual(sorted(expected_suspected_cl), sorted(suspected_cls))

  @mock.patch.object(logging, 'debug')
  def testAnalyzeCompileFailureNoCompileFailure(self, mock_logging):
    failure_info = {'failed_steps': {'a': {}}}
    analysis_result, _ = compile_failure_analysis.AnalyzeCompileFailure(
        CompileFailureInfo.FromSerializable(failure_info), None, None, None)
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
        'builder_name': 'b',
        'build_number': 123,
        'failed_steps': {
            'compile': {
                'current_failure': 123,
                'first_failure': 121
            }
        },
        'builds': {}
    }
    analysis_result, _ = compile_failure_analysis.AnalyzeCompileFailure(
        CompileFailureInfo.FromSerializable(failure_info), None, None, None)
    self.assertEqual({'failures': []}, analysis_result)

  @mock.patch.object(
      waterfall_config,
      'GetDownloadBuildDataSettings',
      return_value={'use_ninja_output_log': False})
  def testAnalyzeCompileFailureNotUsingNinjaOutput(self, _):
    failure_info = {
        'master_name': 'm',
        'builder_name': 'b',
        'build_number': 123,
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
            CompileFailureInfo.FromSerializable(failure_info), change_logs,
            deps_info, failure_signals_json))

    self.assertEqual(expected_analysis_result, analysis_result)
    self.assertEqual(sorted(expected_suspected_cl), sorted(suspected_cls))

  @mock.patch.object(git, 'PullChangeLogs', return_value={})
  @mock.patch.object(deps, 'ExtractDepsInfo', return_value={})
  @mock.patch.object(build_failure_analysis,
                     'SaveAnalysisAfterHeuristicAnalysisCompletes')
  @mock.patch.object(build_failure_analysis, 'SaveSuspectedCLs')
  @mock.patch.object(ci_failure, 'CheckForFirstKnownFailure')
  @mock.patch.object(extract_compile_signal, 'ExtractSignalsForCompileFailure')
  @mock.patch.object(compile_failure_analysis, 'AnalyzeCompileFailure')
  def testHeuristicAnalysisForCompile(self, mock_result, mock_signals,
                                      mock_failure_info, *_):
    failure_info = {
        'build_number': 213,
        'master_name': 'chromium.win',
        'builder_name': 'WinMSVC64 (dbg)',
        'parent_mastername': None,
        'parent_buildername': None,
        'failed_steps': {
            'compile': {
                'last_pass': 212,
                'current_failure': 213,
                'first_failure': 213
            }
        },
        'builds': {
            '212': {
                'blame_list': [
                    '3045acb501991e37fb2416ab8816d2ff4e66735f',
                ],
                'chromium_revision': 'c7388ba52388421e91c113ed807dec16b830c45b'
            },
            '213': {
                'blame_list': [
                    'e282b48ad7a9715d132c649fe1aff9dde0347b1c',
                ],
                'chromium_revision': '2fefee0825b80ec3ebec5c661526818da9490180'
            }
        },
        'failure_type': 8,
        'failed': True,
        'chromium_revision': '2fefee0825b80ec3ebec5c661526818da9490180',
    }

    signals = {
        'compile': {
            'failed_edges': [{
                'dependencies': [
                    'third_party/webrtc/media/base/codec.h',
                    'third_party/webrtc/rtc_base/sanitizer.h',
                ],
                'output_nodes': ['obj/third_party/webrtc/media//file.obj'],
                'rule':
                    'CXX'
            }],
            'files': {
                'c:/b/c/b/win/src/third_party/webrtc/media/engine/file.cc': [
                    76
                ]
            },
            'failed_targets': [{
                'source': '../../third_party/webrtc/media/engine/target1.cc',
                'target': 'obj/third_party/webrtc/media//file.obj'
            }],
            'failed_output_nodes': [
                'obj/third_party/webrtc/media/rtc_audio_video/fon.obj'
            ],
            'keywords': {}
        }
    }
    mock_signals.return_value = signals

    heuristic_result = {
        'failures': [{
            'first_failure':
                213,
            'supported':
                True,
            'suspected_cls': [{
                'commit_position': 517979,
                'url': 'url/0366f1a82a0d2c4e0b82a3632e1dff5ee0b35690',
                'hints': {
                    'add a.cc': 5
                },
                'score': 5,
                'build_number': 213,
                'revision': '0366f1a82a0d2c4e0b82a3632e1dff5ee0b35690',
                'repo_name': 'chromium'
            }],
            'step_name':
                'compile',
            'last_pass':
                212,
            'new_compile_suspected_cls': [{
                'commit_position': 517979,
                'url': 'url/0366f1a82a0d2c4e0b82a3632e1dff5ee0b35690',
                'hints': {
                    'add a.cc': 5
                },
                'score': 5,
                'build_number': 213,
                'revision': '0366f1a82a0d2c4e0b82a3632e1dff5ee0b35690',
                'repo_name': 'chromium'
            }],
            'use_ninja_dependencies':
                True
        }]
    }
    mock_result.return_value = heuristic_result, []
    mock_failure_info.return_value = CompileFailureInfo.FromSerializable(
        failure_info)

    WfAnalysis.Create('chromium.win', 'WinMSVC64 (dbg)', 213).put()
    heuristic_params = CompileHeuristicAnalysisParameters(
        failure_info=CompileFailureInfo.FromSerializable(failure_info),
        build_completed=True)
    result = compile_failure_analysis.HeuristicAnalysisForCompile(
        heuristic_params)
    expected_result = {
        'failure_info': failure_info,
        'signals': signals,
        'heuristic_result': heuristic_result
    }
    self.assertEqual(
        result,
        CompileHeuristicAnalysisOutput.FromSerializable(expected_result))
