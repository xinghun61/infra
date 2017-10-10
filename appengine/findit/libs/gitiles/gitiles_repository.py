# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import base64
from datetime import datetime
import json
import re
import urllib

from libs.gitiles import commit_util
from libs.gitiles import diff
from libs.gitiles.blame import Blame
from libs.gitiles.blame import Region
from libs.gitiles.change_log import ChangeLog
from libs.gitiles.change_log import Contributor
from libs.gitiles.change_log import FileChangeInfo
from libs.gitiles.git_repository import GitRepository
from libs.time_util import TimeZoneInfo

COMMIT_POSITION_PATTERN = re.compile(
    '^Cr-Commit-Position: refs/heads/master@{#(\d+)}$', re.IGNORECASE)
CODE_REVIEW_URL_PATTERN = re.compile('^(?:Review URL|Review-Url): (.*\d+).*$',
                                     re.IGNORECASE)
REVERTED_REVISION_PATTERN = re.compile(
    '^> Committed: https://.+/([0-9a-fA-F]{40})$', re.IGNORECASE)
TIMEZONE_PATTERN = re.compile('[-+]\d{4}$')
CACHE_EXPIRE_TIME_SECONDS = 24 * 60 * 60


class GitilesRepository(GitRepository):
  """Use Gitiles to access a repository on https://chromium.googlesource.com."""

  def __init__(self, http_client, repo_url=None):
    super(GitilesRepository, self).__init__()
    if repo_url and repo_url.endswith('/'):
      self._repo_url = repo_url[:-1]
    else:
      self._repo_url = repo_url

    self._http_client = http_client

  @classmethod
  def Factory(cls, http_client):  # pragma: no cover
    """Construct a factory for creating ``GitilesRepository`` instances.

    Args:
      http_client: the http client to be shared among all created repository
        instances.

    Returns:
      A function from repo urls to ``GitilesRepository`` instances. All
      instances produced by the returned function are novel (i.e., newly
      allocated), but they all share the same underlying ``http_client``.
    """
    return lambda repo_url: cls(http_client, repo_url)

  @property
  def repo_url(self):
    return self._repo_url

  @property
  def identifier(self):  # pragma: no cover
    """This is used by ``_DefaultKeyGenerator`` in cache_decorator.py."""
    return self.repo_url

  @property
  def http_client(self):
    return self._http_client

  def _SendRequestForJsonResponse(self, url, params=None):
    if params is None:  # pragma: no cover
      params = {}
    params['format'] = 'json'

    # Gerrit prepends )]}' to json-formatted response.
    prefix = ')]}\'\n'

    status_code, content = self.http_client.Get(url, params)
    if status_code != 200:
      return None
    elif not content or not content.startswith(prefix):
      raise Exception('Response does not begin with %s' % prefix)

    return json.loads(content[len(prefix):])

  def _SendRequestForTextResponse(self, url):
    status_code, content = self.http_client.Get(url, {'format': 'text'})
    if status_code != 200:
      return None
    return base64.b64decode(content)

  def _GetDateTimeFromString(self,
                             datetime_string,
                             date_format='%a %b %d %H:%M:%S %Y'):
    if TIMEZONE_PATTERN.findall(datetime_string):
      # Need to handle timezone conversion.
      naive_datetime_str, _, offset_str = datetime_string.rpartition(' ')
      naive_datetime = datetime.strptime(naive_datetime_str, date_format)
      return TimeZoneInfo(offset_str).LocalToUTC(naive_datetime)

    return datetime.strptime(datetime_string, date_format)

  def _ContributorFromDict(self, data):
    return Contributor(data['name'],
                       commit_util.NormalizeEmail(data['email']),
                       self._GetDateTimeFromString(data['time']))

  def _ParseChangeLogFromLogData(self, data):
    change_info = commit_util.ExtractChangeInfo(data['message'])

    touched_files = []
    for file_diff in data['tree_diff']:
      change_type = file_diff['type'].lower()
      if not diff.IsKnownChangeType(change_type):
        raise Exception('Unknown change type "%s"' % change_type)
      touched_files.append(
          FileChangeInfo(change_type, file_diff['old_path'], file_diff[
              'new_path']))

    reverted_revision = commit_util.GetRevertedRevision(data['message'])
    url = '%s/+/%s' % (self.repo_url, data['commit'])

    return ChangeLog(
        self._ContributorFromDict(data['author']),
        self._ContributorFromDict(data['committer']), data['commit'],
        change_info.get('commit_position'), data['message'], touched_files, url,
        change_info.get('code_review_url'), reverted_revision,
        change_info.get('host'), change_info.get('change_id'))

  def GetChangeLog(self, revision):
    """Returns the change log of the given revision."""
    url = '%s/+/%s' % (self.repo_url, revision)
    data = self._SendRequestForJsonResponse(url)
    if not data:
      return None

    return self._ParseChangeLogFromLogData(data)

  def _GetChangeLogUrl(self, start_revision, end_revision):
    """Generate url to get changelogs in (start_revision, end_revision]."""
    # We don't support (None, None) range, since it will return everything and
    # that will be a performance burden.
    assert start_revision or end_revision, (
        'At least one of start_revision and end_revision should be non-empty.')

    if not end_revision:
      # Set the end_revision to master to get all the changelogs after the
      # start_revision.
      end_revision = 'master'

    if not start_revision:
      # Url that contains all the changelogs before and including end_revision.
      return '%s/+log/%s' % (self.repo_url, end_revision)

    return '%s/+log/%s..%s' % (self.repo_url, start_revision, end_revision)

  def GetCommitsBetweenRevisions(self, start_revision, end_revision, n=1000):
    """Gets a list of commit hashes between start_revision and end_revision.

    Args:
      start_revision: The oldest revision in the range. If it's None, we will
        return all commits before and including end_revision (since the very
        first commit).
      end_revision: The latest revision in the range. If it's None, we will
        return all commits after the start_revision (till the latest commit).
      n: The maximum number of revisions to request at a time.

    Returns:
      A list of commit hashes made since start_revision through and including
      end_revision in order from most-recent to least-recent. This includes
      end_revision, but not start_revision.
    """
    params = {'n': n}
    next_end_revision = end_revision
    commits = []

    while True:
      url = self._GetChangeLogUrl(start_revision, next_end_revision)
      data = self._SendRequestForJsonResponse(url, params)

      if not data:
        break

      for log in data.get('log', []):
        commit = log.get('commit')
        if commit:
          commits.append(commit)

      if 'next' in data:
        next_end_revision = data['next']
      else:
        break

    return commits

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
      author_time = self._GetDateTimeFromString(region['author']['time'],
                                                '%Y-%m-%d %H:%M:%S')

      blame.AddRegion(
          Region(region['start'], region['count'], region['commit'], region[
              'author']['name'],
                 commit_util.NormalizeEmail(region['author']['email']),
                 author_time))

    return blame

  def GetSource(self, path, revision):
    """Returns source code of the file at ``path`` of the given revision."""
    url = '%s/+/%s/%s' % (self.repo_url, urllib.quote(revision), path)
    return self._SendRequestForTextResponse(url)

  def GetChangeLogs(self, start_revision, end_revision, n=1000):
    """Gets a list of ChangeLogs in revision range by batch.

    Args:
      start_revision: The oldest revision in the range. If it's None, we will
        return all commits before and including end_revision (since the very
        first commit).
      end_revision: The latest revision in the range. If it's None, we will
        return all commits after the start_revision (till the latest commit).
      n (int): The maximum number of revisions to request at a time (default
        to 1000).

    Returns:
      A list of changelogs in (start_revision, end_revision].
    """
    next_end_revision = end_revision
    changelogs = []

    while True:
      url = self._GetChangeLogUrl(start_revision, next_end_revision)
      data = self._SendRequestForJsonResponse(
          url, params={'n': str(n),
                       'name-status': '1'})
      assert data is not None, '_SendRequestForJsonResponse failed unexpectedly'

      for log in data['log']:
        changelogs.append(self._ParseChangeLogFromLogData(log))

      if 'next' in data:
        next_end_revision = data['next']
      else:
        break

    return changelogs
