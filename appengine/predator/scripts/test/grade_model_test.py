# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from analysis import suspect
from app.common.model import crash_analysis
from app.common.model import triage_status
from libs.gitiles import change_log
from scripts import grade_model


class GradeModelTest(unittest.TestCase):
  def setUp(self):
    self.summary_stats = grade_model.SummaryStats(
        total_examples=12,
        true_positives=2,
        true_negatives=3,
        false_positives=1,
        false_negatives=4,
        untriaged=0,
        unsure=2,
    )

    self.correct_cl = 'https://chromium.googlesource.com/chromium/src/+/abc'
    self.incorrect_cl_1 = 'https://chromium.googlesource.com/chromium/src/+/xyz'
    self.incorrect_cl_2 = 'https://chromium.googlesource.com/chromium/src/+/123'

    def DummyCrashAnalysis(culprit_cls, cls_triage_status):
      """Make a CrashAnalysis entity with culprit_cls and triage_status set."""
      analysis = crash_analysis.CrashAnalysis()
      analysis.culprit_cls = culprit_cls
      analysis.suspected_cls_triage_status = cls_triage_status
      return analysis

    self.input_output_pairs = [
      (
        # True positive
        DummyCrashAnalysis([self.correct_cl], triage_status.TRIAGED_CORRECT),
        [suspect.Suspect(self._DummyChanglog(self.correct_cl), 'dep_path/', 3)],
      ),
      (
        # True negative
        DummyCrashAnalysis([], triage_status.TRIAGED_CORRECT),
        [],
      ),
      (
        # False positive (CL suggested when there is no correct CL)
        DummyCrashAnalysis([], triage_status.TRIAGED_INCORRECT),
        [suspect.Suspect(self._DummyChanglog(self.incorrect_cl_1), 'dep_path/',
                         2.5)],
      ),
      (
        # False positive (there is a correct CL, but incorrect one has higher
        # confidence)
        DummyCrashAnalysis([self.correct_cl], triage_status.TRIAGED_INCORRECT),
        [suspect.Suspect(self._DummyChanglog(self.correct_cl), 'dep_path/',
                         2.5),
         suspect.Suspect(self._DummyChanglog(self.incorrect_cl_1), 'dep_path/',
                         3.0)],
      ),
      (
        # False negative
        DummyCrashAnalysis([self.correct_cl], triage_status.TRIAGED_INCORRECT),
        [],
      ),
      (
        # Unsure
        DummyCrashAnalysis([], triage_status.TRIAGED_UNSURE),
        [],
      ),
      (
        # Untriaged
        DummyCrashAnalysis([], triage_status.UNTRIAGED),
        [],
      ),
    ]

  def testCommitUrlEquals(self):
    self.assertTrue(grade_model.CommitUrlEquals(
        ('https://chromium.googlesource.com/angle/angle.git/+/'
         'cccf2b0029b3e223f111594bbd4af054fb0b1fad'),
        ('https://chromium.googlesource.com/angle/angle.git/+/'
         'cccf2b0029b3e223f111594bbd4af054fb0b1fad')))

    self.assertTrue(grade_model.CommitUrlEquals(
        ('https://chromium.googlesource.com/chromium/src.git/+/'
         'ff0a4a3f4f165290c3da7902a67d98434a49e7e3'),
        ('https://chromium.googlesource.com/chromium/src/+/'
         'ff0a4a3f4f165290c3da7902a67d98434a49e7e3')))

    self.assertFalse(grade_model.CommitUrlEquals(
        ('https://chromium.googlesource.com/chromium/src/+/'
         'ff0a4a3f4f165290c3da7902a67d98434a49e7e3'),
        ('https://chromium.googlesource.com/chromium/src/+/'
         '7b1c46d4cb2783c9f12982b199a2ecfce334bb35')))

    self.assertFalse(grade_model.CommitUrlEquals(
        ('https://chromium.googlesource.com/chromium/src/+/'
         'ff0a4a3f4f165290c3da7902a67d98434a49e7e3'),
        ('https://chromium.googlesource.com/angle/src/+/'
         'ff0a4a3f4f165290c3da7902a67d98434a49e7e3')))

  def _DummyChanglog(self, commit_url):
    """Return a ``ChangeLog`` object with the commit_url set."""
    return change_log.ChangeLog(
        'author',
        'committer',
        'revision',
        'commit_position',
        'message',
        ['touched', 'files'],
        commit_url
    )

  def testIsTruePositiveWithSingleCorrectCl(self):
    """``IsTruePositive`` is True when only the correct CL is suggested."""
    suspects = [
      suspect.Suspect(
          self._DummyChanglog(self.correct_cl), 'dep_path/', confidence=3),
    ]

    self.assertTrue(grade_model.IsTruePositive(self.correct_cl, suspects))

  def testIsTruePositiveWithCorrectClHavingHighestConfidence(self):
    """``IsTruePositive`` is True when the correct CL has highest confidence."""
    suspects = [
      suspect.Suspect(
          self._DummyChanglog(self.correct_cl), 'dep_path/', confidence=3),
      suspect.Suspect(
          self._DummyChanglog(self.incorrect_cl_1), 'dep_path/', confidence=3),
      suspect.Suspect(
          self._DummyChanglog(self.incorrect_cl_2), 'dep_path/', confidence=1),
    ]

    self.assertTrue(grade_model.IsTruePositive(self.correct_cl, suspects))

  def testIsTruePositiveWithIncorrectClWithHigherConfidenceThanCorrectOne(self):
    """``IsTruePositive`` is False when a wrong CL has highest confidence."""
    suspects = [
      suspect.Suspect(
          self._DummyChanglog(self.correct_cl), 'dep_path/', confidence=2),
      suspect.Suspect(
          self._DummyChanglog(self.incorrect_cl_1), 'dep_path/', confidence=3),
      suspect.Suspect(
          self._DummyChanglog(self.incorrect_cl_2), 'dep_path/', confidence=1),
    ]

    self.assertFalse(grade_model.IsTruePositive(self.correct_cl, suspects))

  def testIsTruePositiveWithSingleIncorrectCl(self):
    """``IsTruePositive`` is False when a single wrong CL is suggested."""
    suspects = [
      suspect.Suspect(
          self._DummyChanglog(self.incorrect_cl_1), 'dep_path/', confidence=3),
    ]
    self.assertFalse(grade_model.IsTruePositive(self.correct_cl, suspects))

  def testGradeModel(self):
    """Tests running ``GradeModel`` on a set of examples."""
    expected_result = grade_model.SummaryStats(
        total_examples=7,
        true_positives=1,
        true_negatives=1,
        false_positives=2,
        false_negatives=1,
        untriaged=1,
        unsure=1
    )

    self.assertEqual(grade_model.GradeModel(self.input_output_pairs),
                     expected_result)

  def testGradeWithThreshold(self):
    """Tests that ``GradeWithThreshold`` filters suspects correctly."""
    # Setting the confidence threshold at 2.5 will filter out one of the false
    # positive CLs, turning that case into a true negative
    expected_result = grade_model.SummaryStats(
        total_examples=7,
        true_positives=1,
        true_negatives=2,
        false_positives=1,
        false_negatives=1,
        untriaged=1,
        unsure=1
    )

    self.assertEqual(
        grade_model.GradeWithThreshold(self.input_output_pairs, 2.5),
        expected_result)

  def testMaximizeMetricWithThreshold(self):
    """Tests ``MaximizeMetricWithThreshold`` with a simple metric."""
    metric = lambda result: result.true_negatives + result.true_positives
    expected_threshold = 2.5
    expected_max = 3

    self.assertEqual(
        grade_model.MaximizeMetricWithThreshold(self.input_output_pairs,
                                                metric),
        (expected_threshold, expected_max)
    )

  def testPercent(self):
    self.assertEqual(grade_model.Percent(10, 100), 10.0)
    self.assertAlmostEqual(grade_model.Percent(1, 3), 33.3333333)
    self.assertIsNone(grade_model.Percent(5, 0))

  def testPrecision(self):
    self.assertAlmostEqual(grade_model.Precision(self.summary_stats),
                           66.66666666)

  def testRecall(self):
    self.assertAlmostEqual(grade_model.Recall(self.summary_stats), 33.3333333)

  def testAccuracy(self):
    self.assertEqual(grade_model.Accuracy(self.summary_stats), 50.0)

  def testFbetaScore(self):
    self.assertAlmostEqual(grade_model.FbetaScore(self.summary_stats),
                           0.55555555)

  def testDetectionRate(self):
    self.assertAlmostEqual(grade_model.DetectionRate(self.summary_stats),
                           60.0)
