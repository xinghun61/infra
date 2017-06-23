# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utilities for interacting with GoB repositories using various API."""

import datetime
import httplib2
import json
import logging
import netrc
import re
import urllib
import urllib2
import urlparse

from base64 import b64decode
from textwrap import dedent

from infra_libs import httplib2_utils


DEFAULT_LOGGER = logging.getLogger(__name__)
DEFAULT_LOGGER.addHandler(logging.NullHandler())


def ParseAuthenticatedRepo(repo_url):
  """Determine if a repository URL requires authentication.

  Returns:
    None if the URL doesn't require authentication, or else a tuple of
    urlparse.ParseResult objects, where the first element is the
    authenticated URL, and the second is the equivalent unauthenticated URL, if
    there is one.
  """
  urlp = urlparse.urlparse(repo_url)
  # TODO(mmoss): This might not catch all instances that require auth, since
  # restricted repos need it even when not accessed with '/a/'. Maybe it could
  # do a test query to check for "access denied", then try setting up the auth
  # handler. For now, users will just have to specify URLs with '/a/' if they
  # require auth.
  if (urlp.netloc.endswith('.googlesource.com') and
      urlp.path.startswith('/a/')):
    unauth_list = list(urlp)
    # Strip the '/a' to not force authenticaiton.
    unauth_list[2] = unauth_list[2][2:]
    return urlp, urlparse.ParseResult(*unauth_list)
  return None


class GitCommitPath(object):
  """Wrapper class for basic git commit file data."""

  def __init__(self, action, filename, copy_from_path):
    self.action = action
    self.filename = filename
    self.copy_from_path = copy_from_path
    # -- svn_helper.svn_path compatibility --
    self.copy_from_rev = None
    self.kind = 'file'


class GitLogEntry(object):
  """Wrapper class for basic git log data."""

  _full_log_header_fmt = dedent("""\
      commit %s
      Author:     %s <%s>
      AuthorDate: %s
      Commit:     %s <%s>
      CommitDate: %s

      %s
      %s""")

  def __init__(self, commit, parents, author_name, author_email, committer_name,
               committer_email, author_date, committer_date, msg, branch=None,
               repo_url=None, diff=None, ignored=False):
    self.scm = 'git'
    self.commit = commit
    self.parents = parents
    self.author_name = author_name
    self.author_email = author_email
    self.committer_name = committer_name
    self.committer_email = committer_email
    self.__author_date = None
    self.author_date = author_date
    self.__committer_date = None
    self.committer_date = committer_date
    self.msg = msg
    self.branch = branch
    self.repo_url = repo_url
    self.diff = diff
    self.paths = []
    self.ignored = ignored
    # -- Gerrit-only --
    self.__update_date = None
    self.number = 0

  @property
  def author_date(self):
    return self.__author_date.strftime(GitilesHelper.timestamp_format)

  @property
  def committer_date(self):
    return self.__committer_date.strftime(GitilesHelper.timestamp_format)

  @property
  def update_datetime(self):
    # This is really only used for comparisons, so return the datetime object
    # rather than converting to a string like the other dates, which are mostly
    # used as strings in bug messages.
    return self.__update_date

  def _parse_date(self, timestamp):
    parsers = [
        GitilesHelper.ParseTimeStamp,
        GerritHelper.ParseTimeStamp,
        ]
    parsed = None
    for parser in parsers:
      try:
        parsed = parser(timestamp)
        break
      except ValueError:
        continue
    if not parsed:
      raise ValueError('%s: %s' % (self.commit, timestamp))
    return parsed

  @author_date.setter
  def author_date(self, timestamp):
    self.__author_date = self._parse_date(timestamp)

  @committer_date.setter
  def committer_date(self, timestamp):
    self.__committer_date = self._parse_date(timestamp)

  @update_datetime.setter
  def update_date(self, timestamp):
    self.__update_date = self._parse_date(timestamp)

  def full_log_str(self):
    """String rendering based git 'git log --pretty=fuller' output."""
    return dedent("""\
      commit %s
      Author:     %s <%s>
      AuthorDate: %s
      Commit:     %s <%s>
      CommitDate: %s

          %s%s""") % (
          self.commit,
          self.author_name,
          self.author_email,
          self.author_date,
          self.committer_name,
          self.committer_email,
          self.committer_date,
          '\n    '.join(self.msg.splitlines()),
          (('\n\n' + self.diff) if self.diff else ''))

  def __str__(self):
    """Same as full_log_str(), with a diff stat summary at the bottom."""
    rtn = self.full_log_str()
    if self.paths:
      rtn += '\n\n'
      for path in self.paths:
        rtn += '[%s] %s\n' % (path.action, path.filename)
    return rtn

  def __repr__(self):
    """Default object repr, with extra 'git log --oneline'-style output."""
    rtn = super(GitLogEntry, self).__repr__()
    short_hash = self.commit[:8]
    short_msg = self.msg.splitlines()[0]
    short_msg = short_msg[:min(100, len(short_msg))]
    rtn += ' %s %s' % (short_hash, short_msg)
    return rtn

  # -- svn_helper.svn_log_entry compatibility --
  @property
  def revision(self):
    # TODO(mmoss): This could turn out badly if any processing or validation of
    # the revision is attempted, but it should be fine as long as it's just used
    # as a string for logging or such.
    return self.commit

  @property
  def date(self):
    # TODO(mmoss): Maybe reformat this in svn log date string format, in case
    # anything tries to process it?
    return self.committer_date

  @property
  def author(self):
    return self.author_email

  def add_path(self, action, filename, copy_from_path):
    self.paths.append(GitCommitPath(action, filename, copy_from_path))

  # -- svn_helper.svn_log_entry compatibility --

  def GetCommitUrl(self, parent=False, universal=False):
    """Generate a link to the gitiles UI for this commit."""
    url = None
    if universal:
      url = 'https://crrev.com'
    elif self.repo_url:
      url = self.repo_url
      # Strip any forced authentication from the URL, otherwise it can force an
      # unnecessary re-login when users click the link in a browser.
      parsed_urls = ParseAuthenticatedRepo(url)
      if parsed_urls:
        url = parsed_urls[1].geturl()
      url += '/+'
    if url:
      if parent:
        return '%s/%s' % (url, self.parents[0])
      else:
        return '%s/%s' % (url, self.commit)

  def GetPathUrl(self, filepath, parent=False, universal=False):
    """Generate a link to the gitiles UI for the given file from this commit, or
    the parent commit."""
    link = self.GetCommitUrl(parent, universal=universal)
    if link:
      return '%s/%s' % (link, filepath)


def ParseLogEntries(json_dict, repo, branch, paths_dict=None, diffs_dict=None):
  """Convert a dict of json log data into a GitLogEntry list.

  Args:
    json_dict: dict of json data returned from a gitiles log request.
    repo: The repository that the log data came from.
    branch: The branch that the log data was queried for.
    paths_dict: dict of files affected by each commit in the log.
    diffs_dict: dict of commit hash to text diffs for the commit.
  """
  if not paths_dict:
    paths_dict = {}
  if not diffs_dict:
    diffs_dict = {}
  entries = []
  for entry in json_dict['log']:
    author = entry['author']
    committer = entry['committer']
    commit_diff = diffs_dict.get(entry['commit'], None)
    logentry = GitLogEntry(entry['commit'], entry['parents'], author['name'],
                           author['email'], committer['name'],
                           committer['email'], author['time'],
                           committer['time'], entry['message'],
                           branch=branch, repo_url=repo, diff=commit_diff,
                           ignored=entry.get('IGNORED'))
    paths = paths_dict.get(entry['commit'], [])
    for path in paths:
      logentry.add_path(path['type'], path['new_path'], path['old_path'])
    entries.append(logentry)
    DEFAULT_LOGGER.debug('%r', logentry)
  return entries


class RestApiHelper(object):
  """Helper class for interacting with authenticated REST APIs.

  Args:
    api_url: The base url of the REST API.
  """

  def __init__(self, api_url, logger=None):
    self._api_url = api_url
    self.logger = logger or DEFAULT_LOGGER
    self.headers = {}

    # Add a Basic auth handler using credentials from netrc.
    urlp = urlparse.urlparse(self._api_url)
    self.http = httplib2_utils.InstrumentedHttp('gob:%s' % urlp.path)

    try:
      nrc = netrc.netrc()
    except IOError:
      logging.exception('Failed to authenticate REST API client')
    else:
      if urlp.netloc in nrc.hosts:
        self.headers['Authorization'] = 'OAuth %s' % nrc.hosts[urlp.netloc][2]
      else:
        logging.warning('No auth token found for host %s!' % urlp.netloc)


class GitilesHelper(RestApiHelper):
  """Helper class for interacting with gitiles API."""

  timestamp_format = '%a %b %d %H:%M:%S %Y'

  @classmethod
  def ParseTimeStamp(cls, timestamp):
    if isinstance(timestamp, datetime.datetime):
      return timestamp
    # Some repos apparently don't use the UTC format that we've standardized
    # on for the chromium repos, so try to detect if it has a TZ offset, e.g.
    # "Tue Jun 03 10:35:28 2014 -0700" and handle accordingly (unfortunately,
    # strptime doesn't support '%z' like strftime does, so need to parse it out
    # manually).
    delta = datetime.timedelta()
    if timestamp[-5] in ['+', '-']:
      mins = timestamp[-2:]
      hours = timestamp[-4:-2]
      sign = timestamp[-5]
      offset_mins = (int(sign+hours) * 60) + int(sign+mins)
      delta = datetime.timedelta(minutes=offset_mins)
      timestamp = timestamp[:-6]
    return datetime.datetime.strptime(timestamp, cls.timestamp_format) - delta

  @classmethod
  def GenerateTimeStamp(cls, dt):
    return dt.strftime(cls.timestamp_format)

  def GetCommitDetails(self, ref):
    """Get a the details of the given commit ref.

    Args:
      ref: The commit ref to get the details for.

    Returns:
      Dict of gitiles commit details:
        commit, tree, parents, author, committer, message, tree_diff
    """
    commit_url = '%s/+/%s?format=JSON' % (self._api_url, ref)
    self.logger.debug('Commit request: %s', commit_url)
    try:
      resp, content = self.http.request(commit_url, headers=self.headers)
      if resp.status >= 400:
        raise httplib2.HttpLib2Error('Invalid response status %d' %
                                     resp.status)
      # Skip the first 5 bytes of the response due to JSON anti-XSSI prefix.
      json_txt = content[5:]
    except httplib2.HttpLib2Error as e:
      self.logger.exception('Failed Commit request %s: %s', commit_url, str(e))
      return {}
    return json.loads(json_txt)

  def GetCommitDiff(self, commit):
    """Get the text diff introduced by the argument commit."""

    diff_url = '%s/+/%s%%5E%%21/?format=TEXT' % (self._api_url, commit)
    self.logger.debug('Diff request: %s', diff_url)
    try:
      resp, content = self.http.request(diff_url, headers=self.headers)
      if resp.status >= 400:
        raise httplib2.HttpLib2Error('Invalid response status %d' %
                                     resp.status)
      return b64decode(content)
    except httplib2.HttpLib2Error as e:
      self.logger.exception('Failed Diff request %s: %s', diff_url, str(e))
      return None

  def GetLogEntries(self, ref, limit=10, ancestor=None, with_paths=False,
                    with_diffs=False, filter_paths=None, filter_ref=None):
    """Get a git commit log starting at 'ref'.

    This assumes a simple, linear commit history, but that should be reasonable
    for most Chromium repositories where only fast-forward merges are allowed.

    A simple merge history is also supported using "filter_ref", assuming all
    merges only involve parents from "ref" and "filter_ref", and where
    "filter_ref" contains all the history that shouldn't be processed.

    NOTE: The "with_*" and "filter_paths" params are optional because they
    require additional gitiles requests, so could be expensive when processing
    long log lists.

    Args:
      ref: The ref to get the history from.
      limit: Maximum number of log entries to return.
      ancestor: The ref to get the history to.
      with_paths: Whether to add the paths of affected files to each log entry.
      with_diffs: Whether to add the diffs of affected files to each log entry.
      filter_paths: A list of paths regexes to filter entries by (i.e. only
                    commits containing changes to those paths will be returned.)
      filter_ref: A ref whose commit history should not be included in the
                  returned commits (e.g. commits from an upstream repo).

    Returns:
      Tuple of:
      - List of GitLogEntry objects representing the commit log, in reverse
        commit order.
      - The next commit ID, if the log listing could continue, or None.
    """
    def GetLogDict(log_range, limit):
      url = '%s/+log/%s?format=JSON&n=%d' % (self._api_url, log_range, limit)
      self.logger.debug('Log request: %s', url)
      try:
        resp, content = self.http.request(url, headers=self.headers)
        if resp.status >= 400:
          raise httplib2.HttpLib2Error('Invalid response status %d' %
                                       resp.status)
        # Skip the first 5 bytes of the response due to JSON anti-XSSI prefix.
        json_txt = content[5:]
        return json.loads(json_txt)
      except httplib2.HttpLib2Error as e:
        self.logger.exception('Failed log request %s: %s', url, str(e))
        return None

    def_return = [], None

    if ref == ancestor:
      return def_return

    log_range = ref
    if ancestor:
      log_range = '%s..%s' % (ancestor, ref)
    json_dict = GetLogDict(log_range, limit)
    if not json_dict:
      return def_return

    if filter_ref:
      log_range = '%s..%s' % (filter_ref, ref)
      filter_dict = GetLogDict(log_range, limit)
      # If the request failed, don't try to process the default log listing,
      # otherwise it might cause a ton of unwanted updates for merged commits.
      if filter_dict is None:
        return def_return
      # Only allow commits that are in both log listings (i.e. commits that are
      # only in the "ref" branch, and new since the last run).
      filtered_commits = [x['commit'] for x in filter_dict['log']]
      base_count = len([x for x in json_dict['log'] if not x.get('IGNORED')])
      for log_item in json_dict['log']:
        if log_item['commit'] not in filtered_commits:
          log_item['IGNORED'] = True
      filtered_count = base_count - len([x for x in json_dict['log'] if not
                                         x.get('IGNORED')])
      if filtered_count:
        self.logger.info('Ignoring %s commits merged from branch "%s".',
                         filtered_count, filter_ref)

    paths_dict = {}
    if with_paths or filter_paths:
      path_filter = None
      if filter_paths:
        path_filter = re.compile('|'.join(filter_paths))
      for log_item in [x for x in json_dict['log'] if not x.get('IGNORED')]:
        commit = log_item['commit']
        paths = self.GetCommitDetails(commit).get('tree_diff')
        # If this commit doesn't affect the requested path(s), then remove it
        # from the results.
        if (path_filter and
            not any((path_filter.match(p['new_path']) or
                     path_filter.match(p['old_path'])) for p in paths)):
          self.logger.info('Filtering out %s on %s. No changes in %s.', commit,
                           ref, filter_paths)
          log_item['IGNORED'] = True
          continue
        if with_paths:
          paths_dict[commit] = paths
    diffs_dict = {}
    if with_diffs:
      for commit in [log['commit'] for log in json_dict['log']
                     if not log.get('IGNORED')]:
        diffs_dict[commit] = self.GetCommitDiff(commit)
    entries = ParseLogEntries(json_dict, self._api_url, ref, paths_dict,
                              diffs_dict)
    return entries, json_dict.get('next')

  def GetRefs(self, refs_regex=None, filter_regex=None):
    """Get a dict of refs from the given git repo, like ls-remote.

    Args:
      refs_regex: regex list for which refs to monitor.
      filter_regex: List of regex substitutions for matching filter refs (if
        any) to corresponding monitored refs (used to filter unwanted commits
        from monitoring).

    Returns:
      A dict of "ref:commit" and a dict of "ref:filter_ref" mappings.
    """
    refs = {}
    filters = {}
    refs_url = '%s/+refs?format=TEXT' % self._api_url
    self.logger.debug('Refs request: %s', refs_url)
    try:
      resp, content = self.http.request(refs_url, headers=self.headers)
      if resp.status >= 400:
        raise httplib2.HttpLib2Error('Invalid response status %d' %
                                     resp.status)
    except httplib2.HttpLib2Error as e:
      self.logger.exception(
          'Failed refs request: %s (%s). Response: %r',
          refs_url, e, resp)
      return refs, filters

    splitter = re.compile(r'(?P<commit>[0-9a-fA-F]+)\s+(?P<ref>[^\s]+)$')
    ref_res = [(re.compile('.*'), None)]
    if refs_regex:
      ref_res = [[re.compile(ref_reg + '$'), None] for ref_reg in refs_regex]
      for idx, filter_reg in enumerate(filter_regex or []):
        ref_res[idx][1] = filter_reg
    all_refs = []
    for line in content.splitlines():
      m = splitter.match(line)
      if m:
        ref = m.group('ref')
        all_refs.append(ref)
        for ref_re in ref_res:
          if ref_re[0].match(ref):
            refs[ref] = m.group('commit')
            # Try to calculate the corresponding filter ref (if any) based on
            # the name of this monitored ref and the defined substitution, e.g.
            # refs/heads/* => refs/upstream/heads/*).
            if ref_re[1]:
              filters[ref] = re.sub(ref_re[0], ref_re[1], ref)
      else:
        self.logger.debug('Unable to split line:\n%s', line)
    # Remove any bogus filter refs, otherwise using them to specify a commit
    # range will generate an error and not find any commits.
    for key, val in filters.items():
      if not val in all_refs:
        self.logger.debug('Filter ref "%s" not found.' % val)
        filters[key] = None
    return refs, filters


class GerritHelper(RestApiHelper):
  """Helper class for interacting with gerrit API."""

  timestamp_format = '%Y-%m-%d %H:%M:%S.%f'

  def __init__(self, api_url, logger=None, ignore_projects=None):
    self.ignore_projects = ignore_projects or []
    super(GerritHelper, self).__init__(api_url, logger)

  @classmethod
  def ParseTimeStamp(cls, timestamp):
    if isinstance(timestamp, datetime.datetime):
      return timestamp
    # Trim any fractional excess beyond microseconds.
    timestamp = timestamp[:len("YYYY-MM-DD HH:MM:SS.mmmmmm")]
    return datetime.datetime.strptime(timestamp, cls.timestamp_format)

  @classmethod
  def GenerateTimeStamp(cls, dt):
    return dt.strftime(cls.timestamp_format)

  @classmethod
  def ParseChange(cls, change):
    """Convert a Gerrit ChangeInfo dict to a GitLogEntry.

    ChangeInfo spec:
    https://gerrit-review.googlesource.com/Documentation/rest-api-changes.html#change-info
    """
    revision = change['revisions'][change['current_revision']]
    commit_dict = revision['commit']
    files_dict = revision.get('files', {})
    parents = [p['commit'] for p in commit_dict.get('parents', [])]
    author = commit_dict['author']
    committer = commit_dict['committer']
    logentry = GitLogEntry(change['current_revision'], parents,
                           author['name'], author['email'],
                           committer['name'], committer['email'],
                           author['date'], committer['date'],
                           commit_dict['message'],
                           branch=change['branch'],
                           repo_url=revision['fetch']['http']['url']
                          )
    # https://gerrit-review.googlesource.com/Documentation/rest-api-changes.html#file-info
    status_map = {None: 'modify',
                  'D': 'delete',
                  'A': 'add',
                  'R': 'rename',
                  'C': 'copy',
                  'W': 'rewrite'}
    for path, val in files_dict.items():
      logentry.add_path(status_map.get(val.get('status')),
                        path, val.get('old_path', path))

    # Add some gerrit-specific stuff.
    # NOTE: What we really want to know is the datetime that the change status
    # become "MERGED", but gerrit doesn't provide that. The "updated" field is
    # set when that happens, but unfortunately, it's also set for other actions
    # that we don't care about, like adding post-MERGED comments to a change, so
    # this value is only useful to limit which changes we query for on each run,
    # not to determine which of those changes were merged since the last run.
    logentry.update_date = change['updated']
    logentry.number = change['_number']
    return logentry

  def GetLogEntries(self, since=None, limit=25, start=0, fields=None):
    """Get recent gerrit commits as a list of GitLogEntry items.

    See GetMergedChanges() for arg info.
    """
    more = False
    changes = []
    while True:
      next_changes = self.GetMergedChanges(since=since, limit=limit,
                                           start=start, fields=fields)
      if not next_changes:
        break
      start += len(next_changes)
      changes.extend(next_changes)
      more = next_changes[-1].get('_more_changes', False)
      if not more or len(changes) >= limit:
        break

    entries = []
    for change in changes:
      if change['project'] in self.ignore_projects:
        self.logger.info(
            'Skip change %s in ignored git projects', change['id'])
      else:
        entries.append(self.ParseChange(change))
    return entries, more

  def GetMergedChanges(self, since=None, limit=None, start=None, fields=None):
    """Query gerrit for merged changes (i.e. commits).

    API docs:
    https://gerrit-review.googlesource.com/Documentation/rest-api-changes.html#list-changes
    https://gerrit-review.googlesource.com/Documentation/user-search.html

    Args:
      since: Only get commits after this datetime() (UTC assumed).
      limit: Maximum number of results to return.
      start: Offset in the result set to start at.
      fields: A list of additional output fields (cause more database lookups
        and slows down query response time).
    """
    query = '%s/changes/?q=status:merged' % self._api_url
    if since:
      query = '%s+since:{%s}' % (query, urllib.quote(
          '%s' % self.GenerateTimeStamp(since)))
    if start:
      query = '%s&S=%d' % (query, start)
    if limit:
      query = '%s&n=%d' % (query, limit)
    if fields:
      query = '%s&%s' % (query, '&'.join(['o=%s' % p for p in fields]))
    self.logger.debug('Gerrit commits request: %s', query)
    try:
      resp, content = self.http.request(query, headers=self.headers)
      if resp.status >= 400:
        raise httplib2.HttpLib2Error('Invalid response status %d' %
                                     resp.status)
      # Skip the first 5 bytes of the response due to JSON anti-XSSI prefix.
      json_txt = content[5:]
    except httplib2.HttpLib2Error as e:
      self.logger.exception('Failed gerrit request %s: %s', query, str(e))
      return {}
    return json.loads(json_txt)
