# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
import json
import re

from common.blame import Blame
from common.blame import Region
from common.change_log import ChangeLog
from common.change_log import FileChangeInfo
from common import diff
from common.repository import Repository


SVN_REVISION_PATTERN = re.compile(
    '^git\-svn\-id: svn://[^@]*@(\d+) [a-z0-9\-]*$')
COMMIT_POSITION_PATTERN = re.compile(
    '^Cr-Commit-Position: refs/heads/master@{#(\d+)}$')
CODE_REVIEW_URL_PATTERN = re.compile('^Review URL: (.*)$')


def ExtractCommitPositionAndCodeReviewUrl(message):
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


def NormalizeEmail(email):
  """Normalizes the email from git repo.

  Some email is like: test@chromium.org@bbb929c8-8fbe-4397-9dbb-9b2b20218538.
  """
  parts = email.split('@')
  return '@'.join(parts[0:2])


class GitRepository(Repository):
  """Represents a git repository on https://chromium.googlesource.com."""

  def __init__(self, repo_url, http_client):
    super(GitRepository, self).__init__()
    self.repo_url = repo_url
    if self.repo_url.endswith('/'):
      self.repo_url = self.repo_url[:-1]
    self.http_client = http_client

  def _SendJsonRequest(self, url):
    # Gerrit prepends )]}' to json-formatted response.
    prefix = ')]}\'\n'

    status_code, content = self.http_client.Get(url, {'format': 'json'})
    if status_code != 200:
      return None
    elif not content or not content.startswith(prefix):
      raise Exception('Response does not begins with %s' % prefix)

    return json.loads(content[len(prefix):])

  def GetChangeLog(self, revision):
    url = '%s/+/%s' % (self.repo_url, revision)

    data = self._SendJsonRequest(url)
    if not data:
      return None

    commit_position, code_review_url = ExtractCommitPositionAndCodeReviewUrl(
        data['message'])

    touched_files = []
    for file_diff in data['tree_diff']:
      change_type = file_diff['type'].lower()
      if not diff.IsKnownChangeType(change_type):
        raise Exception('Unknown change type "%s"' % change_type)
      touched_files.append(
          FileChangeInfo(
              change_type, file_diff['old_path'], file_diff['new_path']))

    return ChangeLog(
        data['author']['name'], NormalizeEmail(data['author']['email']),
        data['author']['time'],
        data['committer']['name'], NormalizeEmail(data['committer']['email']),
        data['committer']['time'], data['commit'], commit_position,
        data['message'], touched_files, url, code_review_url)

  def GetChangeDiff(self, revision):
    """Returns the raw diff of the given revision."""
    url = '%s/+/%s%%5E%%21/' % (self.repo_url, revision)

    status_code, content = self.http_client.Get(url, {'format': 'text'})
    if status_code != 200:
      return None
    return base64.b64decode(content)

  def GetBlame(self, path, revision):
    """Returns blame information of the file at |path| of the given revision."""
    url = '%s/+blame/%s/%s' % (self.repo_url, revision, path)

    data = self._SendJsonRequest(url)
    if not data:
      return None

    blame = Blame(revision, path)
    for region in data['regions']:
      blame.AddRegion(
          Region(region['start'], region['count'], region['commit'],
                 region['author']['name'],
                 NormalizeEmail(region['author']['email']),
                 region['author']['time']))

    return blame

  def GetSource(self, path, revision):
    """Returns the source code of the file at |path| of the given revision."""
    url = '%s/+/%s/%s' % (self.repo_url, revision, path)

    status_code, content = self.http_client.Get(url, {'format': 'text'})
    if status_code != 200:
      return None
    return base64.b64decode(content)
