# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re
import urlparse

RIETVELD_CODE_REVIEW_URL_PATTERN = re.compile(
    '^(?:Review URL|Review-Url): (?P<url>.*/(?P<change_id>\d+)).*$',
    re.IGNORECASE)
COMMIT_POSITION_PATTERN = re.compile(
    '^Cr-Commit-Position: refs/heads/master@{#(?P<commit_position>\d+)}$',
    re.IGNORECASE)
REVERTED_REVISION_PATTERN = re.compile(
    '^> Committed: https://.+/(?P<revision>[0-9a-fA-F]{40})$', re.IGNORECASE)

GERRIT_CHANGE_ID_PATTERN = re.compile(
    '^Change-Id: (?P<change_id>.*)$', re.IGNORECASE)
GERRIT_REVIEW_URL_PATTERN =re.compile(
    '^Reviewed-on: (?P<url>.*/\d+).*$', re.IGNORECASE)
CHANGE_INFO_PATTERN = re.compile('^.*:.*$', re.IGNORECASE)


def ExtractChangeInfo(message):
  """Returns the commit position and code review url in the commit message.

  A "commit position" is something similar to SVN version ids; i.e.,
  numeric identifiers which are issued in sequential order. The reason
  we care about them is that they're easier for humans to read than
  the hashes that Git uses internally for identifying commits. We
  should never actually use them for *identifying* commits; they're
  only for pretty printing to humans.

  Returns:
    change_info (dict): information about a change. For example:
    Gerrit:
    {
        'commit_position': 12345,
        'code_review_url':
            'https://chromium-review.googlesource.com/54322',
        'host': 'chromium-review.googlesource.com',
        'change_id': 'Iaa1234567fer890'
    }

    Rietveld:
    {
        'commit_position': 12345,
        'code_review_url': 'https://codereview.chromium.org/1234567890',
        'host': 'codereview.chromium.org',
        'change_id': '1234567890'
    }
  """
  change_info = {
      'commit_position': None,
      'code_review_url': None,
      'host': None,
      'change_id': None
  }
  if not message:
    return change_info

  lines = message.strip().split('\n')
  lines.reverse()

  for line in lines:
    if (line != '' and not line.isspace() and
        not CHANGE_INFO_PATTERN.match(line)):
      # Breaks when hit the first first non-empty and non-space line
      # which is not in format "footer-name:value".
      break

    if not change_info['commit_position']:
      match = COMMIT_POSITION_PATTERN.match(line)
      if match:
        change_info['commit_position'] = int(match.group('commit_position'))

    if not change_info['host']:
      match = RIETVELD_CODE_REVIEW_URL_PATTERN.match(line)
      if match:
        change_info['code_review_url'] = match.group('url')
        change_info['host'] = urlparse.urlparse(match.group('url')).netloc
        change_info['change_id'] = match.group('change_id')
      else:
        match = GERRIT_REVIEW_URL_PATTERN.match(line)
        if match:
          change_info['host'] = urlparse.urlparse(match.group('url')).netloc

    if not change_info['change_id']:
      match = GERRIT_CHANGE_ID_PATTERN.match(line)
      if match:
        change_info['change_id'] = match.group('change_id')

  if (not change_info['code_review_url'] and
      change_info['host'] and change_info['change_id']):
    # For code review urls for Gerrit CLs, we want to unify them in
    # 'https://host/q/change_id' format.
    change_info['code_review_url'] = 'https://%s/q/%s' % (
        change_info['host'], change_info['change_id'])
  return change_info


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
