# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
from datetime import datetime
from datetime import timedelta
import json
import re

from common.blame import Blame
from common.blame import Region
from common.cache_decorator import Cached
from common.change_log import ChangeLog
from common.change_log import FileChangeInfo
from common import diff
from common.repository import Repository


SVN_REVISION_PATTERN = re.compile(
    '^git\-svn\-id: svn://[^@]*@(\d+) [a-z0-9\-]*$')
COMMIT_POSITION_PATTERN = re.compile(
    '^Cr-Commit-Position: refs/heads/master@{#(\d+)}$')
CODE_REVIEW_URL_PATTERN = re.compile('^Review URL: (.*\d+).*$')
REVERTED_REVISION_PATTERN = re.compile(
    '^> Committed: https://crrev.com/([0-9a-z]+)$')
TIMEZONE_PATTERN = re.compile('[-+]\d{4}$')


class GitRepository(Repository):
  """Represents a git repository on https://chromium.googlesource.com."""

  def __init__(self, repo_url, http_client):
    super(GitRepository, self).__init__()
    self.repo_url = repo_url
    if self.repo_url.endswith('/'):
      self.repo_url = self.repo_url[:-1]
    self.http_client = http_client

  @property
  def identifier(self):
    return self.repo_url

  @Cached(namespace='Gitiles-json-view', expire_time=24*60*60)
  def _SendRequestForJsonResponse(self, url):
    # Gerrit prepends )]}' to json-formatted response.
    prefix = ')]}\'\n'

    status_code, content = self.http_client.Get(url, {'format': 'json'})
    if status_code != 200:
      return None
    elif not content or not content.startswith(prefix):
      raise Exception('Response does not begins with %s' % prefix)

    return json.loads(content[len(prefix):])

  @Cached(namespace='Gitiles-text-view', expire_time=24*60*60)
  def _SendRequestForTextResponse(self, url):
    status_code, content = self.http_client.Get(url, {'format': 'text'})
    if status_code != 200:
      return None
    return base64.b64decode(content)

  def ExtractCommitPositionAndCodeReviewUrl(self, message):
    """Returns the commit position and code review url in the commit message.

    Returns:
      (commit_position, code_review_url)
    """
    if not message:
      return (None, None)

    commit_position = None
    code_review_url = None

    # Commit position and code review url are in the last 5 lines.
    lines = message.strip().split('\n')[-5:]
    lines.reverse()

    for line in lines:
      if commit_position is None:
        match = COMMIT_POSITION_PATTERN.match(line)
        if not match:
          match = SVN_REVISION_PATTERN.match(line)
        if match:
          commit_position = int(match.group(1))

      if code_review_url is None:
        match = CODE_REVIEW_URL_PATTERN.match(line)
        if match:
          code_review_url = match.group(1)
    return (commit_position, code_review_url)

  def _NormalizeEmail(self, email):
    """Normalizes the email from git repo.

    Some email is like: test@chromium.org@bbb929c8-8fbe-4397-9dbb-9b2b20218538.
    """
    parts = email.split('@')
    return '@'.join(parts[0:2])

  def _GetDateTimeFromString(self, datetime_string,
      date_format='%a %b %d %H:%M:%S %Y'):
    if TIMEZONE_PATTERN.findall(datetime_string):
      # Need to handle timezone conversion.
      naive_datetime_str, _, offset_str = datetime_string.rpartition(' ')
      naive_datetime = datetime.strptime(naive_datetime_str,
                                         date_format)
      hour_offset = int(offset_str[-4:-2])
      minute_offset = int(offset_str[-2:])
      if(offset_str[0]) == '-':
        hour_offset = -hour_offset
        minute_offset = -minute_offset

      time_delta = timedelta(hours=hour_offset, minutes=minute_offset)

      utc_datetime = naive_datetime - time_delta
      return utc_datetime

    return datetime.strptime(datetime_string, date_format)

  def _DownloadChangeLogData(self, revision):
    url = '%s/+/%s' % (self.repo_url, revision)
    return url, self._SendRequestForJsonResponse(url)

  def GetRevertedRevision(self, message):
    """Parse message to get the reverted revision if there is one."""
    lines = message.strip().splitlines()
    if not lines[0].lower().startswith('revert'):
      return None

    for line in reversed(lines):  # pragma: no cover
      # TODO: Handle cases where no reverted_revision in reverting message.
      reverted_revision_match = REVERTED_REVISION_PATTERN.match(line)
      if reverted_revision_match:
        return reverted_revision_match.group(1)

  def GetChangeLog(self, revision):
    url, data = self._DownloadChangeLogData(revision)
    if not data:
      return None

    commit_position, code_review_url = (
        self.ExtractCommitPositionAndCodeReviewUrl(data['message']))

    touched_files = []
    for file_diff in data['tree_diff']:
      change_type = file_diff['type'].lower()
      if not diff.IsKnownChangeType(change_type):
        raise Exception('Unknown change type "%s"' % change_type)
      touched_files.append(
          FileChangeInfo(
              change_type, file_diff['old_path'], file_diff['new_path']))

    author_time = self._GetDateTimeFromString(data['author']['time'])
    committer_time = self._GetDateTimeFromString(data['committer']['time'])
    reverted_revision = self.GetRevertedRevision(data['message'])

    return ChangeLog(
        data['author']['name'], self._NormalizeEmail(data['author']['email']),
        author_time,
        data['committer']['name'],
        self._NormalizeEmail(data['committer']['email']),
        committer_time, data['commit'], commit_position,
        data['message'], touched_files, url, code_review_url,
        reverted_revision)

  def GetChangeDiff(self, revision):
    """Returns the raw diff of the given revision."""
    url = '%s/+/%s%%5E%%21/' % (self.repo_url, revision)
    return self._SendRequestForTextResponse(url)

  def GetBlame(self, path, revision):
    """Returns blame of the file at ``path`` of the given revision."""
    url = '%s/+blame/%s/%s' % (self.repo_url, revision, path)

    data = self._SendRequestForJsonResponse(url)
    if not data:
      return None

    blame = Blame(revision, path)
    for region in data['regions']:
      author_time = self._GetDateTimeFromString(
          region['author']['time'], '%Y-%m-%d %H:%M:%S')

      blame.AddRegion(
          Region(region['start'], region['count'], region['commit'],
                 region['author']['name'],
                 self._NormalizeEmail(region['author']['email']),author_time))

    return blame

  def GetSource(self, path, revision):
    """Returns source code of the file at ``path`` of the given revision."""
    url = '%s/+/%s/%s' % (self.repo_url, revision, path)
    return self._SendRequestForTextResponse(url)
