# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

CODE_REVIEW_URL_PATTERN = re.compile(
    '^(?:Review URL|Review-Url): (.*\d+).*$', re.IGNORECASE)
COMMIT_POSITION_PATTERN = re.compile(
    '^Cr-Commit-Position: refs/heads/master@{#(\d+)}$', re.IGNORECASE)
REVERTED_REVISION_PATTERN = re.compile(
    '^> Committed: https://.+/([0-9a-fA-F]{40})$', re.IGNORECASE)
START_OF_CR_COMMIT_POSITION = -5


def ExtractCommitPositionAndCodeReviewUrl(message):
  """Returns the commit position and code review url in the commit message.

  A "commit position" is something similar to SVN version ids; i.e.,
  numeric identifiers which are issued in sequential order. The reason
  we care about them is that they're easier for humans to read than
  the hashes that Git uses internally for identifying commits. We
  should never actually use them for *identifying* commits; they're
  only for pretty printing to humans.

  Returns:
    (commit_position, code_review_url)
  """
  if not message:
    return (None, None)

  commit_position = None
  code_review_url = None

  # Commit position and code review url are in the last 5 lines.
  lines = message.strip().split('\n')[START_OF_CR_COMMIT_POSITION:]
  lines.reverse()

  for line in lines:
    if commit_position is None:
      match = COMMIT_POSITION_PATTERN.match(line)
      if match:
        commit_position = int(match.group(1))

    if code_review_url is None:
      match = CODE_REVIEW_URL_PATTERN.match(line)
      if match:
        code_review_url = match.group(1)
  return (commit_position, code_review_url)


def NormalizeEmail(email):
  """Normalizes the email from git repo.

  Some email is like: test@chromium.org@bbb929c8-8fbe-4397-9dbb-9b2b20218538.
  """
  parts = email.split('@')
  return '@'.join(parts[0:2])


def GetRevertedRevision(message):
  """Parse message to get the reverted revision if there is one."""
  lines = message.strip().splitlines()
  if not lines[0].lower().startswith('revert'):
    return None

  for line in reversed(lines):  # pragma: no cover
    # TODO: Handle cases where no reverted_revision in reverting message.
    reverted_revision_match = REVERTED_REVISION_PATTERN.match(line)
    if reverted_revision_match:
      return reverted_revision_match.group(1)


# TODO(katesonia): Deprecate this copy (there is a copy in min_distance
# feature), after scorer-based classfier got depecated.
def DistanceBetweenLineRanges((start1, end1), (start2, end2)):
  """Given two ranges, compute the (unsigned) distance between them.

  Args:
    start1 (int): the first line included in the first range.
    end1 (int): the last line included in the first range. Must be
      greater than or equal to ``start1``.
    start2 (int): the first line included in the second range.
    end2 (int): the last line included in the second range. Must be
      greater than or equal to ``start1``.

  Returns:
    If the end of the earlier range comes before the start of the later
    range, then the difference between those points. Otherwise, returns
    zero (because the ranges overlap).
  """
  if end1 < start1:
    raise ValueError('the first range is empty: %d < %d' % (end1, start1))
  if end2 < start2:
    raise ValueError('the second range is empty: %d < %d' % (end2, start2))
  # There are six possible cases, but in all the cases where the two
  # ranges overlap, the latter two differences will be negative.
  return max(0, start2 - end1, start1 - end2)
