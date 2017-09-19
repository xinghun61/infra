# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple
import unittest

from analysis import suspect
from app.common.model import crash_analysis
from app.common.model import triage_status
from libs.gitiles import change_log
from scripts import grade_model
from scripts.grade_model import SuspectCl
from scripts.grade_model import SuspectComponent


class MockCrash(object):

  def __init__(self, culprit_cls=None,
               suspected_cls_triage_status=triage_status.UNTRIAGED,
               culprit_components=None,
               suspected_components_triage_status=triage_status.UNTRIAGED):
    self.culprit_cls = culprit_cls
    self.suspected_cls_triage_status = suspected_cls_triage_status
    self.culprit_components = culprit_components
    self.suspected_components_triage_status = suspected_components_triage_status


class MockCulprit(namedtuple('MockCulprit', ['cls', 'components'])):

  def __new__(cls, suspect_cls=None, components=None):
    return super(MockCulprit, cls).__new__(cls, suspect_cls, components)


def _DummyChangelog(commit_url):
  """Return a ``ChangeLog`` object with the commit_url set."""
  return change_log.ChangeLog(
      'author',
      'committer',
      'revision',
      'commit_position',
      'message',
      ['touched', 'files'],
      commit_url)


class SuspectClTest(unittest.TestCase):
  """Tests ``SuspectCl`` class."""

  def setUp(self):
    self.correct_cl = 'https://chromium.googlesource.com/chromium/src/+/abc'
    self.incorrect_cl_1 = 'https://chromium.googlesource.com/chromium/src/+/xyz'
    self.incorrect_cl_2 = 'https://chromium.googlesource.com/chromium/src/+/123'

  def testIsTruePositiveWithSingleCorrectCl(self):
    """``IsTruePositive`` is True when only the correct CL is suggested."""
    suspects = [
      suspect.Suspect(
          _DummyChangelog(self.correct_cl), 'dep_path/', confidence=3),
    ]
    suspect_entry = grade_model.SuspectCl(
        MockCrash(culprit_cls=[self.correct_cl]),
        MockCulprit(suspect_cls=suspects))

    self.assertTrue(suspect_entry.IsTruePositive())

  def testIsTruePositiveWithCorrectClHavingHighestConfidence(self):
    """``IsTruePositive`` is True when the correct CL has highest confidence."""
    suspects = [
      suspect.Suspect(
          _DummyChangelog(self.correct_cl), 'dep_path/', confidence=3),
      suspect.Suspect(
          _DummyChangelog(self.incorrect_cl_1), 'dep_path/', confidence=3),
      suspect.Suspect(
          _DummyChangelog(self.incorrect_cl_2), 'dep_path/', confidence=1),
    ]
    suspect_entry = grade_model.SuspectCl(
        MockCrash(culprit_cls=[self.correct_cl]),
        MockCulprit(suspect_cls=suspects))

    self.assertTrue(suspect_entry.IsTruePositive())

  def testIsTruePositiveWithIncorrectClWithHigherConfidenceThanCorrectOne(self):
    """``IsTruePositive`` is False when a wrong CL has highest confidence."""
    suspects = [
      suspect.Suspect(
          _DummyChangelog(self.correct_cl), 'dep_path/', confidence=2),
      suspect.Suspect(
          _DummyChangelog(self.incorrect_cl_1), 'dep_path/', confidence=3),
      suspect.Suspect(
          _DummyChangelog(self.incorrect_cl_2), 'dep_path/', confidence=1),
    ]

    suspect_entry = grade_model.SuspectCl(
        MockCrash(culprit_cls=[self.correct_cl]),
        MockCulprit(suspect_cls=suspects))

    self.assertTrue(suspect_entry.IsTruePositive())

  def testIsTruePositiveWithSingleIncorrectCl(self):
    """``IsTruePositive`` is False when a single wrong CL is suggested."""
    suspects = [
      suspect.Suspect(
          _DummyChangelog(self.incorrect_cl_1), 'dep_path/', confidence=3),
    ]
    suspect_entry = grade_model.SuspectCl(
        MockCrash(culprit_cls=[self.correct_cl]),
        MockCulprit(suspect_cls=suspects))
    self.assertFalse(suspect_entry.IsTruePositive())


class SuspectComponentTest(unittest.TestCase):
  """Tests ``SuspectComponent`` class."""

  def testIsTruePositiveWithExactSameComponents(self):
    """``IsTruePositive`` is True.

    When suggested components are the same as correct components."""
    suspect_entry = grade_model.SuspectComponent(
        MockCrash(culprit_components=['Blink>DOM']),
        MockCulprit(components=['Blink>DOM']))

    self.assertTrue(suspect_entry.IsTruePositive())

  def testIsTruePositiveAllCorrectComponentsAreFound(self):
    """``IsTruePositive`` is True when the correct CL has highest confidence.

    If suspect components contains other component, it is true positive only
    when the strict is set to False.
    """
    suspect_entry = grade_model.SuspectComponent(
        MockCrash(culprit_components=['Blink>DOM']),
        MockCulprit(components=['Blink>DOM', 'Blink>Editing']))

    self.assertTrue(suspect_entry.IsTruePositive(strict=False))
    self.assertFalse(suspect_entry.IsTruePositive(strict=True))

  def testIsNotTruePositiveWithIncorrectComponents(self):
    """``IsTruePositive`` is False when a wrong CL has highest confidence."""
    suspect_entry = grade_model.SuspectComponent(
        MockCrash(culprit_components=['Blink>DOM']),
        MockCulprit(components=['Internals>Core']))

    self.assertFalse(suspect_entry.IsTruePositive())

  def testIsNotTruePositiveWhenFailToFindAllCorrectComponents(self):
    """``IsTruePositive`` is False when a wrong CL has highest confidence."""
    suspect_entry = grade_model.SuspectComponent(
        MockCrash(culprit_components=['Blink>DOM', 'Blink>JavaScript']),
        MockCulprit(components=['Blink>Dummy']))

    self.assertFalse(suspect_entry.IsTruePositive())


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

    self.suspect_cl_entries = [
        SuspectCl(
            # True positive
            MockCrash([self.correct_cl], triage_status.TRIAGED_CORRECT),
            MockCulprit(
                [suspect.Suspect(_DummyChangelog(self.correct_cl),
                                 'dep_path/', 3)]),
        ),
        SuspectCl(
            # True negative
            MockCrash([], triage_status.TRIAGED_CORRECT),
            MockCulprit([]),
        ),
        SuspectCl(
            # False positive (CL suggested when there is no correct CL)
            MockCrash([], triage_status.TRIAGED_INCORRECT),
            MockCulprit([suspect.Suspect(_DummyChangelog(self.incorrect_cl_1),
                                         'dep_path/', 2.5)]),
        ),
        SuspectCl(
            # False positive (there is a correct CL, but incorrect one has
            # higher confidence)
            MockCrash([self.correct_cl], triage_status.TRIAGED_INCORRECT),
            MockCulprit([suspect.Suspect(_DummyChangelog(self.correct_cl),
                                         'dep_path/', 2.5),
                         suspect.Suspect(_DummyChangelog(self.incorrect_cl_1),
                                         'dep_path/', 3.0)]),
        ),
        SuspectCl(
            # False negative
            MockCrash([self.correct_cl], triage_status.TRIAGED_INCORRECT),
            MockCulprit([]),
        ),
        SuspectCl(
            # Unsure
            MockCrash([], triage_status.TRIAGED_UNSURE),
            MockCulprit([]),
        ),
        SuspectCl(
            # Untriaged
            MockCrash([], triage_status.UNTRIAGED),
            MockCulprit([]),
        ),
    ]

    self.suspect_component_entries = [
        SuspectComponent(
            # True positive
            MockCrash(
                culprit_components=['Blink'],
                suspected_components_triage_status=(
                    triage_status.TRIAGED_CORRECT)),
            MockCulprit(
                components=['Blink']),
        ),
        SuspectComponent(
            # True negative
            MockCrash(culprit_components=[],
                      suspected_components_triage_status=(
                          triage_status.TRIAGED_CORRECT)),
            MockCulprit(components=[]),
        ),
        SuspectComponent(
            # False positive (Suspected components don't contain all correct
            # components)
            MockCrash(
                culprit_components=['Blink'],
                suspected_components_triage_status=(
                    triage_status.TRIAGED_INCORRECT)),
            MockCulprit(components=['Internals>Core']),
        ),
        SuspectComponent(
            # False negative
            MockCrash(
                culprit_components=['Blink'],
                suspected_components_triage_status=(
                    triage_status.TRIAGED_INCORRECT)),
            MockCulprit(components=[]),
        ),
        SuspectComponent(
          # Unsure
          MockCrash(
              culprit_components=[],
              suspected_components_triage_status=triage_status.TRIAGED_UNSURE),
          MockCulprit(components=[]),
        ),
        SuspectComponent(
          # Untriaged
          MockCrash(
              culprit_components=[],
              suspected_components_triage_status=triage_status.UNTRIAGED),
          MockCulprit(components=[]),
        ),
    ]

  def testGetSuspectEntryClass(self):
    """Tests ``GetSuspectEntryClass`` function."""
    self.assertEqual(grade_model.GetSuspectEntryClass('cls'), SuspectCl)
    self.assertEqual(grade_model.GetSuspectEntryClass('components'),
                     SuspectComponent)
    self.assertIsNone(grade_model.GetSuspectEntryClass('dummy'))

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
        grade_model.GradeWithThreshold(self.suspect_cl_entries, 2.5),
        expected_result)

  def testMaximizeMetricWithThreshold(self):
    """Tests ``MaximizeMetricWithThreshold`` with a simple metric."""
    metric = lambda result: result.true_negatives + result.true_positives
    expected_threshold = 2.5
    expected_max = 3

    self.assertEqual(
        grade_model.MaximizeMetricWithThreshold(self.suspect_cl_entries,
                                                metric, strict=True),
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

  def testGradeModelForSuspectCl(self):
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

    self.assertEqual(
        grade_model.GradeModel(self.suspect_cl_entries, strict=True),
        expected_result)

  def testGradeModelForSuspectComponent(self):
    """Tests running ``GradeModel`` on a set of examples."""
    expected_result = grade_model.SummaryStats(
        total_examples=6,
        true_positives=1,
        true_negatives=1,
        false_positives=1,
        false_negatives=1,
        untriaged=1,
        unsure=1
    )

    self.assertEqual(
        grade_model.GradeModel(self.suspect_component_entries, strict=True),
        expected_result)

  def testDetectionRate(self):
    self.assertAlmostEqual(grade_model.DetectionRate(self.summary_stats), 60.0)
