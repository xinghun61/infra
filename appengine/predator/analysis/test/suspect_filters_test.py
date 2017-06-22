# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from analysis import suspect_filters
from analysis.analysis_testcase import AnalysisTestCase
from analysis.suspect import Suspect


def _MockGitRepository(ignore_revisions=None, ignore_text=None):

  class GitRepository(object):
    def __init__(self, repo_url):
      self.repo_url = repo_url

    def GetSource(self, *_):
      if ignore_text:
        return ignore_text

      return '\n'.join(ignore_revisions) if ignore_revisions else ''

  return GitRepository


class FilterLessLikelySuspectsTest(AnalysisTestCase):
  """Tests ``FilterLessLikelySuspects`` class."""

  def testFilterLessLikelySuspectsRaiseValueError(self):
    """Tests ``FilterLessLikelySuspects`` raise ValueError if negative ratio."""
    with self.assertRaises(ValueError):
      suspect_filters.FilterLessLikelySuspects(-3)

  def testFilterLessLikelySuspects(self):
    """Tests ``FilterLessLikelySuspects`` filter."""
    suspect1 = Suspect(self.GetDummyChangeLog(), 'src/')
    suspect2 = Suspect(self.GetDummyChangeLog(), 'src/')
    suspect3 = Suspect(self.GetDummyChangeLog(), 'src/')

    suspect1.confidence = 2
    suspect2.confidence = 2
    self.assertListEqual(
        suspect_filters.FilterLessLikelySuspects(0.5)([suspect1, suspect2]),
        [])

    suspect2.confidence = 1.8
    suspect3.confidence = 1.0
    self.assertListEqual(
        suspect_filters.FilterLessLikelySuspects(0.5)([suspect1, suspect2,
                                                       suspect3]),
        [suspect1, suspect2])


class FilterIgnoredRevisionsTest(AnalysisTestCase):
  """Tests ``FilterIgnoredRevisions`` class."""

  def testIgnoredRevisionsProperty(self):
    """Tests ``ignore_revisions`` property."""
    ignore_revisions = set(['rev1', 'rev2', 'rev3'])
    suspect_filter = suspect_filters.FilterIgnoredRevisions(
        _MockGitRepository(ignore_revisions=ignore_revisions))

    self.assertSetEqual(suspect_filter.ignore_revisions, ignore_revisions)

  def testIgnoredRevisionsPropertySkipCommentLines(self):
    """Tests that ``ignore_revisions`` property skips commend lines."""
    ignore_text = '# comment1\nrev1\n# comment2\nrev2'
    suspect_filter = suspect_filters.FilterIgnoredRevisions(
        _MockGitRepository(ignore_text=ignore_text))

    self.assertSetEqual(suspect_filter.ignore_revisions, set(['rev1', 'rev2']))

  def testIgnoredRevisionsPropertyReturnsNoneIfThereIsNoIgnoreList(self):
    """Tests ``ignore_revisions`` property returns None if no ignore list."""
    suspect_filter = suspect_filters.FilterIgnoredRevisions(
        _MockGitRepository(ignore_revisions=None))

    self.assertIsNone(suspect_filter.ignore_revisions)

  def testCall(self):
    """Tests ``__call__`` of the filter."""
    suspect1 = Suspect(self.GetDummyChangeLog(), 'src/')
    suspect2 = Suspect(self.GetDummyChangeLog(), 'src/')
    suspect3 = Suspect(self.GetDummyChangeLog(), 'src/')

    suspect1.changelog = suspect1.changelog._replace(revision='rev1')
    suspect2.changelog = suspect2.changelog._replace(revision='rev2')
    suspect3.changelog = suspect3.changelog._replace(revision='rev3')

    ignore_revisions = set(['rev1', 'rev2'])
    suspect_filter = suspect_filters.FilterIgnoredRevisions(
        _MockGitRepository(ignore_revisions=ignore_revisions))

    self.assertSetEqual(set(suspect_filter([suspect1, suspect2, suspect3])),
                        set([suspect3]))


class FilterSuspectFromRobotAuthorTest(AnalysisTestCase):
  """Tests ``FilterSuspectFromRobotAuthor`` class."""

  def testIsSuspectFromRobotAuthorReturnFalse(self):
    """Tests that ``_IsSuspectFromRobotAuthor`` method returns False."""
    suspect = Suspect(self.GetDummyChangeLog(), 'src/')
    suspect_filter = suspect_filters.FilterSuspectFromRobotAuthor()
    self.assertFalse(suspect_filter._IsSuspectFromRobotAuthor(suspect))

  def testIsSuspectFromRobotAuthor(self):
    """Tests that ``_IsSuspectFromRobotAuthor`` method returns True."""
    suspect = Suspect(self.GetDummyChangeLog(), 'src/')
    robot_author = suspect.changelog.author._replace(
        email='v8-deps-roller@chromium.org')
    robot_cl = suspect.changelog._replace(author=robot_author)
    suspect.changelog = robot_cl

    suspect_filter = suspect_filters.FilterSuspectFromRobotAuthor()
    self.assertTrue(suspect_filter._IsSuspectFromRobotAuthor(suspect))

  def testCall(self):
    """Tests ``__call__`` method."""
    suspect1 = Suspect(self.GetDummyChangeLog(), 'src/')
    suspect2 = Suspect(self.GetDummyChangeLog(), 'src/')
    robot_author = suspect2.changelog.author._replace(
        email='v8-deps-roller@chromium.org')
    robot_cl = suspect2.changelog._replace(author=robot_author)
    suspect2.changelog = robot_cl

    suspect_filter = suspect_filters.FilterSuspectFromRobotAuthor()
    self.assertListEqual(suspect_filter([suspect1, suspect2]),
                         [suspect1])
