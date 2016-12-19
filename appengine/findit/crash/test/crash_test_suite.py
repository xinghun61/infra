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

  def _VerifyTwoSuspectEqual(self, suspect1, suspect2):
    """Assert that two ``Suspect`` objects are equal."""
    self._VerifyTwoChangeLogsEqual(suspect1.changelog, suspect2.changelog)
    self.assertEqual(suspect1.dep_path, suspect2.dep_path)
    self.assertEqual(suspect1.confidence, suspect2.confidence)
    self.assertEqual(suspect1.reasons, suspect2.reasons)

    self.assertEqual(suspect1.file_to_analysis_info,
                     suspect2.file_to_analysis_info)

    self.assertEqual(suspect1.file_to_stack_infos.keys(),
                     suspect2.file_to_stack_infos.keys())
    for file_path in suspect1.file_to_stack_infos.keys():
      self._VerifyTwoStackInfosEqual(suspect1.file_to_stack_infos[file_path],
                                     suspect2.file_to_stack_infos[file_path])

    self.assertEqual(suspect1.file_to_analysis_info,
                     suspect2.file_to_analysis_info)

  def _VerifyTwoSuspectsEqual(self, suspects1, suspects2):
    """Assert that two ``Suspects`` objects are equal."""
    self.assertEqual(suspects1._ignore_cls, suspects2._ignore_cls)

    self.assertEqual(len(suspects1), len(suspects2))
    for revision1, suspect1 in suspects1.iteritems():
      self.assertTrue(revision1 in suspects2)
      self._VerifyTwoSuspectEqual(suspect1, suspects2[revision1])
