# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from common.diff import ChangeType
from waterfall import build_failure_analysis
from waterfall.failure_signal import FailureSignal


class BuildFailureAnalysisTest(unittest.TestCase):

  def testIsSameFile(self):
    self.assertTrue(build_failure_analysis._IsSameFile('a/b/x.cc', 'x.cc'))
    self.assertTrue(build_failure_analysis._IsSameFile('a/b/x.cc', 'b/x.cc'))
    self.assertTrue(build_failure_analysis._IsSameFile('a/b/x.cc', 'a/b/x.cc'))

    self.assertFalse(
        build_failure_analysis._IsSameFile('a/prefix_x.cc.', 'x.cc'))
    self.assertFalse(
        build_failure_analysis._IsSameFile('prefix_a/x.cc.', 'a/x.cc'))
    self.assertFalse(
        build_failure_analysis._IsSameFile('c/x.cc.', 'a/b/c/x.cc'))
    self.assertFalse(build_failure_analysis._IsSameFile('a/x.cc.', 'a/y.cc'))

  def testNormalizeObjectFile(self):
    cases = {
        'obj/a/T.x.o': 'a/x.o',
        'obj/a/T.x.y.o': 'a/x.y.o',
        'x.o': 'x.o',
        'obj/a/x.obj': 'a/x.obj',
    }
    for obj_file, expected_file in cases.iteritems():
      self.assertEqual(
          expected_file,
          build_failure_analysis._NormalizeObjectFilePath(obj_file))

  def testStripCommonSuffix(self):
    cases = {
        'a_file':
            'a_file_%s.cc' % '_'.join(build_failure_analysis._COMMON_SUFFIXES),
        'src/b_file': 'src/b_file_impl_mac.h',
        'c_file': 'c_file_browsertest.cc',
        'xdtest': 'xdtest.cc',
    }
    for expected_file, file_path in cases.iteritems():
      self.assertEqual(
          expected_file,
          build_failure_analysis._StripExtensionAndCommonSuffix(file_path))

  def testIsRelated(self):
    self.assertTrue(build_failure_analysis._IsRelated('a.py', 'a_test.py'))
    self.assertTrue(
        build_failure_analysis._IsRelated('a.h', 'a_impl_test.o'))
    self.assertTrue(
        build_failure_analysis._IsRelated('a.h', 'target.a_impl_test.obj'))

    self.assertFalse(
        build_failure_analysis._IsRelated('a/x.cc', 'a/b/y.cc'))
    self.assertFalse(
        build_failure_analysis._IsRelated('a/x.cc', 'xdtest.cc'))

  def testCheckFilesAgainstSuspectedCL(self):
    failure_signal_json = {
        'files': {
            'src/a/b/f1.cc': [],
            'd/e/a2_test.cc': [],
            'b/c/f2.cc': [10, 20],
            'd/e/f3.h': [],
            'x/y/f4.py': [],
            'f5_impl.cc': []
        }
    }
    change_log_json = {
        'revision': 'rev',
        'touched_files': [
            {
                'change_type': ChangeType.ADD,
                'old_path': '/dev/null',
                'new_path': 'a/b/f1.cc'
            },
            {
                'change_type': ChangeType.ADD,
                'old_path': '/dev/null',
                'new_path': 'd/e/a2.cc'
            },
            {
                'change_type': ChangeType.MODIFY,
                'old_path': 'a/b/c/f2.h',
                'new_path': 'a/b/c/f2.h'
            },
            {
                'change_type': ChangeType.MODIFY,
                'old_path': 'd/e/f3.h',
                'new_path': 'd/e/f3.h'
            },
            {
                'change_type': ChangeType.DELETE,
                'old_path': 'x/y/f4.py',
                'new_path': '/dev/null'
            },
            {
                'change_type': ChangeType.DELETE,
                'old_path': 'h/f5.h',
                'new_path': '/dev/null'
            },
            {
                'change_type': ChangeType.RENAME,
                'old_path': 't/y/x.cc',
                'new_path': 's/z/x.cc'
            },
        ]
    }
    deps_info = {}

    justification = build_failure_analysis._CheckFiles(
        FailureSignal.FromDict(failure_signal_json), change_log_json, deps_info)
    self.assertIsNotNone(justification)
    # The score is 15 because:
    # +5 added a/b/f1.cc (same file src/a/b/f1.cc in failure_signal log)
    # +1 added d/e/a2.cc (related file a2_test.cc in failure_signal log)
    # +1 modified b/c/f2.h (related file a/b/c/f2.cc in failure_signal log)
    # +2 modified d/e/f3.h (same file d/e/f3.h in failure_signal log)
    # +5 deleted x/y/f4.py (same file x/y/f4.py in failure_signal log)
    # +1 deleted h/f5.h (related file f5_impl.cc in failure_signal log)
    # +0 renamed t/y/x.cc -> s/z/x.cc (no related file in failure_signal log)
    self.assertEqual(15, justification['score'])

  def testCheckFilesAgainstUnrelatedCL(self):
    failure_signal_json = {
        'files': {
            'src/a/b/f.cc': [],
        }
    }
    change_log_json = {
        'revision': 'rev',
        'touched_files': [
            {
                'change_type': ChangeType.ADD,
                'old_path': '/dev/null',
                'new_path': 'a/d/f1.cc'
            },
        ]
    }
    deps_info = {}

    justification = build_failure_analysis._CheckFiles(
        FailureSignal.FromDict(failure_signal_json), change_log_json, deps_info)
    self.assertIsNone(justification)

  def testCheckFilesAgainstDEPSRoll(self):
    failure_signal_json = {
        'files': {
            'src/third_party/dep1/f.cc': [123],
        }
    }
    change_log_json = {
        'revision': 'rev',
        'touched_files': [
            {
                'change_type': ChangeType.MODIFY,
                'old_path': 'DEPS',
                'new_path': 'DEPS'
            },
        ]
    }
    deps_info = {
        'deps_rolls': {
            'rev': [
                {
                    'path': 'src/third_party/dep1/',
                    'repo_url': 'https://url_dep1',
                    'old_revision': '7',
                    'new_revision': '9',
                },
                {
                    'path': 'third_party/dep2',
                    'repo_url': 'https://url_dep2',
                    'old_revision': None,
                    'new_revision': '1',
                },
            ]
        }
    }

    justification = build_failure_analysis._CheckFiles(
        FailureSignal.FromDict(failure_signal_json), change_log_json, deps_info)
    self.assertIsNotNone(justification)
    # The score is 2 because:
    # +2 rolled third_party/dep1/ and src/third_party/dep1/f.cc was in log.
    self.assertEqual(2, justification['score'])

  def testAnalyzeSuccessfulBuild(self):
    failure_info = {
        'failed': False,
    }
    result = build_failure_analysis.AnalyzeBuildFailure(
        failure_info, change_logs=None, deps_info=None, failure_signals=None)
    self.assertEqual(0, len(result['failures']))

  def testAnalyzeBuildFailure(self):
    failure_info = {
        'failed': True,
        'failed_steps': {
            'a': {
                'current_failure': 99,
                'first_failure': 98,
            },
            'b': {
                'current_failure': 99,
                'first_failure': 98,
                'last_pass': 96,
            },
        },
        'builds': {
            '99': {
                'blame_list': ['r99_1', 'r99_2'],
            },
            '98': {
                'blame_list': ['r98_1'],
            },
            '97': {
                'blame_list': ['r97_1'],
            },
            '96': {
                'blame_list': ['r96_1', 'r96_2'],
            },
        }
    }
    change_logs = {
        'r99_1': {
            'revision': 'r99_1',
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'a/b/f99_1.cc',
                    'new_path': 'a/b/f99_1.cc'
                },
            ],
        },
        'r99_2': {
            'revision': 'r99_2',
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'a/b/f99_2.cc',
                    'new_path': 'a/b/f99_2.cc'
                },
            ],
        },
        'r98_1': {
            'revision': 'r98_1',
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'y/z/f98.cc',
                    'new_path': 'y/z/f98.cc'
                },
            ],
        },
        'r97_1': {
            'revision': 'r97_1',
            'touched_files': [
                {
                    'change_type': ChangeType.ADD,
                    'old_path': '/dev/null',
                    'new_path': 'x/y/f99_1.cc'
                },
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'a/b/f99_1.cc',
                    'new_path': 'a/b/f99_1.cc'
                },
            ],
        },
        'r96_1': {
            'revision': 'r96_1',
            'touched_files': [
                {
                    'change_type': ChangeType.MODIFY,
                    'old_path': 'a/b/f96_1.cc',
                    'new_path': 'a/b/f96_1.cc'
                },
            ],
        },
    }
    deps_info = {}
    failure_signals_json = {
        'a': {
          'files': {
              'src/a/b/f99_2.cc': [],
          },
        },
        'b': {
          'files': {
              'x/y/f99_1.cc': [],
          },
        },
    }
    expected_analysis_result = {
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
                        'score': 2,
                        'hints': {
                            'modified f99_2.cc (and it was in log)': 2,
                        },
                    }
                ],
            },
            {
                'step_name': 'b',
                'first_failure': 98,
                'last_pass': 96,
                'suspected_cls': [
                    {
                        'build_number': 97,
                        'repo_name': 'chromium',
                        'revision': 'r97_1',
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

    analysis_result = build_failure_analysis.AnalyzeBuildFailure(
        failure_info, change_logs, deps_info, failure_signals_json)
    self.assertEqual(expected_analysis_result, analysis_result)
