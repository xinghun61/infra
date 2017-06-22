# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import math
import re

from decorators import cached_property

_CHROMIUM_REPO = 'https://chromium.googlesource.com/chromium/src/'
_HYPER_BLAME_IGNORE_REVISIONS_PATH = '.git-blame-ignore-revs'

_ROBOT_AUTHOR_REGEXS = [re.compile(r'.*-deps-roller@chromium.org'),
                        re.compile(r'blink-reformat@chromium.org')]


class SuspectFilter(object):
  """Filters a list of suspects."""

  def __call__(self, suspects):
    """Returns a list of suspects with impossible suspects filtered.

    Args:
      suspects (list): A list of ``Suspect``s.

    Return:
      A list of ``Suspect``s.
    """
    raise NotImplementedError()


class FilterLessLikelySuspects(SuspectFilter):
  """Filters less likely suspects.

  The "less likely" means that the suspect has less than half the probability
  of the most likely suspect.

  Note, the pass-in ``suspects`` must have their confidence computed.
  """
  def __init__(self, probability_ratio):
    if probability_ratio < 0:
      raise ValueError('Probability ratio should be non-negative.')

    self.ratio = math.log(
        float(probability_ratio)) if probability_ratio > 0 else -float('inf')

  def __call__(self, suspects):
    confidences = [suspect.confidence for suspect in suspects]
    max_score = max(confidences)
    min_score = max(min(confidences), 0.0)
    # If the probability is equally distributed, it's very possible that none of
    # them is suspect, return empty list.
    if max_score == min_score:
      return []

    filtered_suspects = []
    for suspect in suspects:  # pragma: no cover
      # The ratio of the probabilities of 2 suspects equal to
      # exp(suspect1.confidence)/exp(suspect2.confidence), so
      # suspect1.confidence - suspect2.confidence <= log(0.5) means
      # suspect1 is half as likely than suspect2.
      if (suspect.confidence <= min_score or
          suspect.confidence - max_score <= self.ratio):
        break

      filtered_suspects.append(suspect)

    return filtered_suspects


class FilterIgnoredRevisions(SuspectFilter):
  """Filters revisions in an ignore revision list.

  If there is no ignore list provided, defaults the list to git-hyper-blame
  ignore list.
  """
  def __init__(self, git_repository,
               repo_url=_CHROMIUM_REPO,
               ignore_list_path=_HYPER_BLAME_IGNORE_REVISIONS_PATH):
    self._repository = git_repository(repo_url)
    self._ignore_list_path = ignore_list_path

  @cached_property
  def ignore_revisions(self):
    """Gets a set of ignored revisions."""
    # Get the latest ignore list in master branch.
    content = self._repository.GetSource(self._ignore_list_path, 'master')
    if not content:
      logging.warning('Failed to download ignore list %s from %s',
                      self._ignore_list_path, self._repository.repo_url)
      return None

    # Skip comment lines and empty lines.
    revisions = set()
    for line in content.splitlines():
      if not line or line.startswith('#'):
        continue

      revisions.add(line.strip())

    return revisions

  def __call__(self, suspects):
    """Filters all suspects that are in ignored revisions"""
    return [suspect for suspect in suspects if suspect.changelog.revision
            not in (self.ignore_revisions or set())]


class FilterSuspectFromRobotAuthor(SuspectFilter):
  """Filters those generated cls from robot author.

  For example, dep rolls change from .*-deps-roller@chromium.org or blink
  reformat cls.
  """

  def __init__(self, robot_author_regexs=None):
    self._robot_author_regexs = robot_author_regexs or _ROBOT_AUTHOR_REGEXS

  def _IsSuspectFromRobotAuthor(self, suspect):
    """Checks if the suspect comes from robot author."""
    author = suspect.changelog.author
    for robot_author_regex in self._robot_author_regexs:
      if robot_author_regex.match(author.email):
        return True

    return False

  def __call__(self, suspects):
    """Filters all suspects that are from robot authors."""
    return [suspect for suspect in suspects
            if not self._IsSuspectFromRobotAuthor(suspect)]
