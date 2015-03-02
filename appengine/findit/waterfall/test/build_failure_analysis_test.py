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
            'b/c/f2.h': [10, 20],
            'd/e/f3_test.cc': [],
            'x/y/f4.py': [],
            'f5_impl.cc': []
        }
    }
    change_log_json = {
        'touched_files': [
            {
                'change_type': ChangeType.ADD,
                'old_path': '/dev/null',
                'new_path': 'a/b/f1.cc'
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

    justification = build_failure_analysis._CheckFiles(
        FailureSignal.FromJson(failure_signal_json), change_log_json)
    self.assertIsNotNone(justification)
    self.assertEqual(2, justification['suspect_points'])
    self.assertEqual(13, justification['score'])

  def testCheckFilesAgainstUnrelatedCL(self):
    failure_signal_json = {
        'files': {
            'src/a/b/f.cc': [],
        }
    }
    change_log_json = {
        'touched_files': [
            {
                'change_type': ChangeType.ADD,
                'old_path': '/dev/null',
                'new_path': 'a/d/f1.cc'
            },
        ]
    }

    justification = build_failure_analysis._CheckFiles(
        FailureSignal.FromJson(failure_signal_json), change_log_json)
    self.assertIsNone(justification)

  def testAnalyzeSuccessfulBuild(self):
    failure_info = {
        'failed': False,
    }
    result = build_failure_analysis.AnalyzeBuildFailure(
        failure_info, None, None)
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
            },
        },
        'builds': {
            '99': {
                'blame_list': ['r99_1', 'r99_2'],
            },
            '98': {
                'blame_list': ['r98_1'],
            },
        }
    }
    change_logs = {
        'r99_1': {
            'revision': 'r99_1',
            'touched_files': [
                {
                    'change_type': ChangeType.ADD,
                    'old_path': '/dev/null',
                    'new_path': 'x/y/f99_1.cc'
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
    }
    failure_signals_json = {
        'a': {
          'files': {
              'src/a/b/f99_2.cc': [],
          },
        },
        'b': {
          'files': {
              'f.cc': [],
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
                        'dependency_name': 'chromium',
                        'revision': 'r99_2',
                        'commit_position': None,
                        'code_review_url': None,
                        'suspect_points': 0,
                        'score': 1,
                        'hints': [
                            'modified f99_2.cc (and it was in log)'
                        ],
                    }
                ],
            },
            {
                'step_name': 'b',
                'first_failure': 98,
                'last_pass': None,
                'suspected_cls': [],
            }
        ]
    }

    analysis_result = build_failure_analysis.AnalyzeBuildFailure(
        failure_info, change_logs, failure_signals_json)
    self.assertEqual(expected_analysis_result, analysis_result)
