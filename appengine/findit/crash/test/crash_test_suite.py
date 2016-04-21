# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from testing_utils import testing
from crash.test.stacktrace_test_suite import StacktraceTestSuite


class CrashTestSuite(StacktraceTestSuite):  # pragma: no cover.

  def _VerifyTwoStackInfosEqual(self, infos1, infos2):
    self.assertEqual(len(infos1), len(infos2))

    for (frame1, priority1), (frame2, priority2) in zip(infos1, infos2):
      self.assertEqual(priority1, priority2)
      self._VerifyTwoStackFramesEqual(frame1, frame2)

  def _VerifyTwoBlamesEqual(self, blame1, blame2):
    self.assertEqual(blame1.revision, blame2.revision)
    self.assertEqual(blame1.path, blame2.path)
    map(self.assertEqual, blame1.ToDict()['regions'],
        blame2.ToDict()['regions'])

  def _VerifyTwoChangeLogsEqual(self, changelog1, changelog2):
    self.assertEqual(changelog1.ToDict(), changelog2.ToDict())

  def _VerifyTwoResultEqual(self, result1, result2):
    self._VerifyTwoChangeLogsEqual(result1.changelog, result2.changelog)
    self.assertEqual(result1.dep_path, result2.dep_path)
    self.assertEqual(result1.component, result2.component)
    self.assertEqual(result1.confidence, result2.confidence)
    self.assertEqual(result1.reason, result2.reason)
    self.assertEqual(len(result1.file_to_stack_infos),
                     len(result2.file_to_stack_infos))

    for (file_path1, stack_infos1), (file_path2, stack_infos2) in zip(
        result1.file_to_stack_infos.iteritems(),
        result2.file_to_stack_infos.iteritems()):
      self.assertEqual(file_path1, file_path2)
      self._VerifyTwoStackInfosEqual(stack_infos1, stack_infos2)

  def _VerifyTwoMatchResultEqual(self, match_result1, match_result2):
    self.assertEqual(match_result1.min_distance, match_result2.min_distance)
    self._VerifyTwoResultEqual(match_result1, match_result2)

  def _VerifyTwoMatchResultsEqual(self, match_results1, match_results2):
    self.assertEqual(match_results1.ignore_cls, match_results2.ignore_cls)

    self.assertEqual(len(match_results1), len(match_results2))
    for revision1, match_result1 in match_results1.iteritems():
      self.assertTrue(revision1 in match_results2)
      self._VerifyTwoMatchResultEqual(match_result1, match_results2[revision1])
