# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A collection of helpers to make lkgr_finder's life easier."""


import ast
import datetime
import json
import logging
import os
import Queue
import re
import smtplib
import socket
import subprocess
import sys
import threading
import xml.etree.ElementTree as xml

import requests

from infra.libs import git


class RunLogger(logging.Filter):
  log = []

  def filter(self, record):
    RunLogger.log.append(
        '%s: %s' % (datetime.datetime.now(), record.getMessage()))
    return True


LOGGER = logging.getLogger(__name__)
LOGGER.addFilter(RunLogger())


##################################################
# Helper classes
##################################################
class STATUS(object):
  """Enum for holding possible build statuses."""
  UNKNOWN, RUNNING, SUCCESS, FAILURE = range(4)

  @staticmethod
  def tostr(status):  # pragma: no cover
    return ['unknown', 'running', 'success', 'failure'][status]


class NOREV(object):
  """Singleton class to represent the wholesale lack of a revision."""
  @staticmethod
  def __str__():  # pragma: no cover
    return '<No Revision>'


NOREV = NOREV()


##################################################
# VCS Wrappers
##################################################
class VCSWrapper(object):
  _status_path = None

  @property
  def status_path(self):  # pragma: no cover
    """Return the url component for the appropriate page on the status app."""
    return self._status_path

  def check_rev(self, r):
    """Return True if the input is a valid revisions for this VCS."""
    raise NotImplementedError

  def keyfunc(self, r):
    """Key func to convert a revision to a sortable representation."""
    raise NotImplementedError

  def sort(self, revisions, keyfunc=None):
    """Sort a set of revisions into ascending commit order."""
    raise NotImplementedError

  def get_lag(self, r):
    """Return the lag between now and the commit time of the given rev."""
    raise NotImplementedError

  def get_gap(self, revisions, r):  # pragma: no cover
    """Return the gap between the most recent of revisions and r."""
    latest = self.sort(revisions)[-1]
    return self.keyfunc(latest) - self.keyfunc(r)

  @staticmethod
  def new(vcs, url, path):  # pragma: no cover
    """Factory function to return a GitWrapper or a SvnWrapper."""
    if vcs == 'git':
      return GitWrapper(url, path)
    elif vcs == 'svn':
      return SvnWrapper(url, path)
    else:
      raise NotImplementedError


class GitWrapper(VCSWrapper):
  _status_path = '/git-lkgr'
  _GIT_HASH_RE = re.compile('^[a-fA-F0-9]{40}$')
  _GIT_POS_RE = re.compile('(\S+)@{#(\d+)}')

  def __init__(self, url, path):  # pragma: no cover
    self._git = git.NewGit(url, path)
    self._position_cache = {}
    LOGGER.debug('Local git repository located at %s', self._git.path)

  def check_rev(self, r):  # pragma: no cover
    if r is NOREV:
      return False
    return bool(self._GIT_HASH_RE.match(r))

  def _cache(self, *revs):  # pragma: no cover
    unknown_revs = [r for r in revs if r not in self._position_cache]
    positions = self._git.number(*unknown_revs)
    # We know we only care about revisions along a single branch.
    keys = []
    for pos in positions:
      match = self._GIT_POS_RE.match(pos or '')
      if match:
        key = (int(match.group(2)), match.group(1))
      else:
        key = None
      keys.append(key)
    self._position_cache.update(dict(zip(unknown_revs, keys)))

  def keyfunc(self, r):  # pragma: no cover
    # Returns a tuple (commit-position-number, commit-position-ref).
    if not self.check_rev(r):
      return (-1, '')
    k = self._position_cache.get(r)
    if k is None:
      self._cache(r)
      k = self._position_cache.get(r)
    if k is None:
      return (-1, '')
    return k

  def sort(self, revisions, keyfunc=None):  # pragma: no cover
    keyfunc = keyfunc or (lambda x: x)
    self._cache(*map(keyfunc, revisions))
    return sorted(revisions, key=lambda x: self.keyfunc(keyfunc(x)))

  def get_lag(self, r):  # pragma: no cover
    ts = self._git.show(r, '', '--format=format:%ct').split('\n', 1)[0].strip()
    dt = datetime.datetime.utcfromtimestamp(float(ts))
    return datetime.datetime.utcnow() - dt

  def get_gap(self, revisions, r):  # pragma: no cover
    latest = self.sort(revisions)[-1]
    return self.keyfunc(latest)[0] - self.keyfunc(r)[0]

class SvnWrapper(VCSWrapper):
  _status_path = '/lkgr'

  def __init__(self, url, path):
    self._url = url
    LOGGER.debug('Talking to svn repository located at %s', self._url)

  def check_rev(self, r):
    try:
      int(r)
      return True
    except (ValueError, TypeError):
      return False

  def keyfunc(self, r):
    if self.check_rev(r):
      return int(r)

  def sort(self, revisions, keyfunc=None):
    keyfunc = keyfunc or (lambda x: x)  # pragma: no cover
    return sorted(revisions, key=lambda x: self.keyfunc(keyfunc(x)))

  def get_lag(self, r):  # pragma: no cover
    cmd = ['svn', 'log', '--non-interactive', '--xml', '-r', str(r), self._url]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    stdout = process.communicate()[0]
    if not process.returncode:
      log = xml.fromstring(stdout)
      date = log.find('logentry').find('date').text
      if date:
        dt = datetime.datetime.strptime(date, '%Y-%m-%dT%H:%M:%S.%fZ')
    return datetime.datetime.utcnow() - dt


##################################################
# Input Functions
##################################################
def FetchBuilderJson(fetch_q):  # pragma: no cover
  """Pull build json from buildbot masters.

  Args:
    @param fetch_q: A pre-populated Queue.Queue containing tuples of:
      master_url: Url of the buildbot master to get json from.
      builder: Name of the builder on that master.
      output_builds: Output dictionary of builder to build data.
    @type fetch_q: tuple
  """
  while True:
    try:
      master_url, builder, output_builds = fetch_q.get(False)
    except Queue.Empty:
      return
    url = '%s/json/builders/%s/builds/_all' % (master_url, builder)
    LOGGER.debug('Fetching buildbot json from %s', url)
    try:
      r = requests.get(url, params={'filter': 'false'})
      builder_history = r.json()
      output_builds[builder] = builder_history
    except requests.exceptions.RequestException as e:
      LOGGER.error('RequestException while fetching %s:\n%s', url, repr(e))


def FetchBuildData(masters, max_threads=0):  # pragma: no cover
  """Fetch all build data about the builders in the input masters.

  Args:
    @param masters: Dictionary of the form
    { master: {
        base_url: string
        builders: [list of strings]
    } }
    This dictionary is a subset of the project configuration json.
    @type masters: dict
    @param max_threads: Maximum number of parallel requests.
    @type max_threads: int
  """
  build_data = {master: {} for master in masters}
  fetch_q = Queue.Queue()
  for master, master_data in masters.iteritems():
    master_url = master_data['base_url']
    builders = master_data['builders']
    for builder in builders:
      fetch_q.put((master_url, builder, build_data[master]))
  fetch_threads = set()
  if not max_threads:
    max_threads = fetch_q.qsize()
  for _ in xrange(max_threads):
    th = threading.Thread(target=FetchBuilderJson, args=(fetch_q,))
    th.start()
    fetch_threads.add(th)
  for th in fetch_threads:
    th.join()

  return build_data


def ReadBuildData(filename):  # pragma: no cover
  """Read all build data from a file or stdin."""
  try:
    fh = sys.stdin if filename == '-' else open(filename, 'r')
    with fh:
      return json.load(fh)
  except (IOError, ValueError), e:
    LOGGER.error('Could not read build data from %s:\n%s\n', filename, repr(e))
    raise


def FetchLKGR(lkgr_url):  # pragma: no cover
  """Get the current LKGR from the status app."""
  LOGGER.debug('Fetching current LKGR from %s', lkgr_url)
  try:
    r = requests.get(lkgr_url)
  except requests.exceptions.RequestException:
    LOGGER.error('RequestException while fetching %s', lkgr_url)
    return
  return r.content.strip()


##################################################
# Data Processing
##################################################
def IsResultFailure(result_data):  # pragma: no cover
  """Returns true if result_data indicates a failure."""
  while isinstance(result_data, list):
    result_data = result_data[0]
  if not result_data:
    return False
  # 0 means SUCCESS and 1 means WARNINGS.
  return result_data not in (0, 1, '0', '1')


def EvaluateBuildData(build_data):  # pragma: no cover
  """Determine the status of a build."""
  status = STATUS.SUCCESS

  if build_data['currentStep'] is not None:
    status = STATUS.RUNNING
    for step in build_data['steps']:
      if step['isFinished'] is True and IsResultFailure(step.get('results')):
        return STATUS.FAILURE
  elif IsResultFailure(build_data.get('results')):
    status = STATUS.FAILURE

  return status


def CollateRevisionHistory(build_data, lkgr_builders, repo):  # pragma: no cover
  """Organize complex build data into a simpler form.

  Args:
    build_data: json-formatted build data returned by buildbot.
    lkgr_builders: List of interesting builders.
    repo (VCSWrapper): repository in which the revision occurs.

  Returns:
    A dict of the following form:
    ``build_history =
    {master: {builder: [(revision, status, build_num), ...]}}``, and a list of
    revisions: ``revisions = [revision, ...]``, with revisions and
    ``build_history[master][builder]`` sorted by their revkeys.

  """
  build_history = {}
  revisions = set()
  # TODO(agable): Make build_data stronly typed, so we're not messing with JSON
  for master, master_data in build_data.iteritems():
    if master not in lkgr_builders:
      continue
    LOGGER.debug('Collating master %s', master)
    master_history = build_history.setdefault(master, {})
    for (builder, builder_data) in master_data.iteritems():
      if builder not in lkgr_builders[master]['builders']:
        continue
      LOGGER.debug('Collating builder %s', builder)
      builder_history = []
      for build_num in sorted(builder_data.keys(), key=int):
        this_build_data = builder_data[build_num]
        txt = this_build_data.get('text', [])
        if 'exception' in txt and 'slave' in txt and 'lost' in txt:
          continue
        revision = None
        for prop in this_build_data.get('properties', []):
          # Revision fallthrough:
          # * If there is a got_src_revision, we probably want to use that,
          #   because otherwise it wouldn't be specified.
          # * If we're in Git and there's a got_revision_git, might as well
          #   use that since it is guaranteed to be the righ type.
          # * Finally, just use the default got_revision.
          if prop[0] == 'got_src_revision':
            revision = prop[1]
            break
          if type(repo) is GitWrapper and prop[0] == 'got_revision_git':
            revision = prop[1]
            break
          if prop[0] == 'got_revision':
            revision = prop[1]
            break
        status = EvaluateBuildData(this_build_data)
        if revision is None:
          if status is STATUS.FAILURE or status is STATUS.RUNNING:
            # The build failed too early or is still in early stage even before
            # chromium revision was tagged. If we allow 'revision' fallback it
            # will end up being non-chromium revision for non chromium projects.
            # Or it may end up getting an SVN revision if the build is running.
            continue
        if not revision:
          revision = this_build_data.get(
              'sourceStamp', {}).get('revision', None)
        if not revision:
          continue
        if type(repo) is GitWrapper and len(str(revision)) < 40:
          # Ignore stource stamps that don't contain a proper git hash. This
          # can happen if very old build numbers get into the build data.
          continue
        revisions.add(str(revision))
        builder_history.append((revision, status, build_num))
      master_history[builder] = repo.sort(
          builder_history, keyfunc=lambda x: x[0])
  revisions = repo.sort(revisions)
  return (build_history, revisions)


def FindLKGRCandidate(build_history, revisions, revkey, status_gen=None):
  """Find an lkgr candidate.

  This function performs the meat of the algorithm described in the module
  docstring. It walks backwards through the revisions, searching for a
  revision which has the SUCCESS status on every builder.

  Returns:
    A single revision (string) chosen as the new LKGR candidate.

  Args:
    build_history: A dict of build data, as from CollateRevisionHistory
    revisions: A list of revisions/commits that were built
    revkey: Keyfunc to map each revision to a sortable key
    revcmp: A comparator to sort revisions/commits
    status_gen: An instance of StatusGenerator to output status information
  """
  lkgr = None
  builders = []
  for master, master_history in build_history.iteritems():
    status_gen.master_cb(master)
    for builder, builder_history in master_history.iteritems():
      status_gen.builder_cb(builder)
      gen = reversed(builder_history)
      prev = []
      try:
        prev.append(gen.next())
      except StopIteration:  # pragma: no cover
        prev.append((NOREV, STATUS.UNKNOWN, -1))
      builders.append((master, builder, gen, prev))
  for revision in reversed(revisions):
    status_gen.revision_cb(revision)
    good_revision = True
    for master, builder, gen, prev in builders:
      try:
        while revkey(revision) < revkey(prev[-1][0]):
          prev.append(gen.next())
      except StopIteration:  # pragma: no cover
        prev.append((NOREV, STATUS.UNKNOWN, -1))

      # current build matches revision
      if revkey(revision) == revkey(prev[-1][0]):
        status = prev[-1][1]
      elif len(prev) == 1:
        assert revkey(revision) > revkey(prev[-1][0])
        # most recent build is behind revision
        status = STATUS.UNKNOWN
      elif prev[-1][1] == STATUS.UNKNOWN:  # pragma: no cover
        status = STATUS.UNKNOWN
      else:
        # We color space between FAILED and INPROGRESS builds as FAILED,
        # since that is what it will eventually become.
        if prev[-1][1] == STATUS.SUCCESS and prev[-2][1] == STATUS.RUNNING:  # pragma: no cover
          status = STATUS.RUNNING
        elif prev[-1][1] == prev[-2][1] == STATUS.SUCCESS:
          status = STATUS.SUCCESS
        else:
          status = STATUS.FAILURE
      build_num = None
      if revkey(revision) == revkey(prev[-1][0]):
        build_num = prev[-1][2]
      status_gen.build_cb(master, builder, status, build_num)
      if status != STATUS.SUCCESS:
        good_revision = False
    if not lkgr and good_revision:
      lkgr = revision
      status_gen.lkgr_cb(revision)
  return lkgr


def CheckLKGRLag(lag_age, rev_gap, allowed_lag_hrs, allowed_rev_gap):
  """Determine if the LKGR lag is acceptable for current commit activity.

    Returns True if the lag is within acceptable thresholds.
  """
  # Lag isn't an absolute threshold because when things are slow, e.g. nights
  # and weekends, there could be bad revisions that don't get noticed and
  # fixed right away, so LKGR could go a long time without updating, but it
  # wouldn't be a big concern, so we want to back off the 'ideal' threshold.
  # When the tree is active, we don't want to back off much, or at all, to keep
  # the lag under control.

  if rev_gap == 0:
    return True

  lag_hrs = (lag_age.days * 24) + (lag_age.seconds / 3600)
  if not lag_hrs:
    return True

  rev_rate = rev_gap / lag_hrs

  # This causes the allowed_lag to back off proportionally to how far LKGR is
  # below the gap threshold, roughly throttled by the rate of commits since the
  # last LKGR.
  # Equation arbitrarily chosen to fit the range of 2 to 22 hours when using the
  # default allowed_lag and allowed_gap. Might need tweaking.
  max_lag_hrs = ((1 + max(0, allowed_rev_gap - rev_gap) /
                  min(30, max(15, rev_rate))) * allowed_lag_hrs)

  LOGGER.debug('LKGR is %s hours old (threshold: %s hours)' %
               (lag_hrs, max_lag_hrs))

  return lag_age < datetime.timedelta(hours=max_lag_hrs)


##################################################
# Output Functions
##################################################
def SendMail(recipients, subject, message, dry):  # pragma: no cover
  if dry:
    LOGGER.info('Dry-run: Not sending mail with subject: "%s"', subject)
    return
  LOGGER.info('Sending mail with subject: "%s"', subject)
  try:
    sender = 'lkgr_finder@%s' % socket.getfqdn()
    body = ['From: %s' % sender]
    body.append('To: %s' % recipients)
    body.append('Subject: lkgr_finder: %s' % subject)
    # Default to sending replies to the recipient list, not the account running
    # the script, since that's probably just a role account.
    body.append('Reply-To: %s' % recipients)
    body.append('')
    body.append(message)
    server = smtplib.SMTP('localhost')
    server.sendmail(sender, recipients.split(','), '\n'.join(body))
    server.quit()
  except Exception as e:
    # If smtp fails, just dump the output. If running under cron, that will
    # capture the output and send its own (ugly, but better than nothing) email.
    print message
    print ('\n--------- Exception in %s -----------\n' %
           os.path.basename(__file__))
    raise e


def UpdateTag(new_lkgr, repo, dry):  # pragma: no cover
  """Update the lkgr tag in the repository. Git only.

  Args:
    new_lkgr: the new commit hash for the lkgr tag to point to.
    repo: instance of GitWrapper
    dry: if True, don't actually update the tag.
  """
  LOGGER.info('Updating lkgr tag')
  push_cmd = ['push', 'origin', '%s:refs/tags/lkgr' % new_lkgr]

  try:
    if dry:
      LOGGER.debug('Dry-run: Not pushing lkgr: %s', ' '.join(push_cmd))
    else:
      LOGGER.debug('Pushing lkgr: %s', ' '.join(push_cmd))
      repo._git(push_cmd)  # pylint: disable=W0212
  except subprocess.CalledProcessError:
    LOGGER.error('Failed to push new lkgr tag.')


def PostLKGR(status_url, lkgr, lkgr_alt, vcs, password_file, dry):  # pragma: no cover
  """Posts the LKGR to the status_url.

  Args:
    status_url: the instance of chromium-status to post the lkgr to
    lkgr: the value of the new lkgr to post
    lkgr_alt: the keyfunc representation of the lkgr
    vcs: 'svn' or 'git', determines the parameters to use in the post
    password_file: path to a password file containing the shared secret
    dry: if True, don't actually make the post request
  """
  url = status_url + '/revisions'
  if vcs == 'git':
    url = status_url + '/commits'
  LOGGER.info('Posting to %s', url)

  try:
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           password_file), 'r') as f:
      password = f.read().strip()
  except (IOError, TypeError):
    LOGGER.error('Could not read password file %s, aborting upload' %
                 password_file)
    return

  params = {
      'revision': lkgr,
      'success': 1,
  }
  if vcs == 'git':
    params = {
        'hash': lkgr,
        'position_ref': lkgr_alt[1],
        'position_num': lkgr_alt[0],
    }

  if dry:
    LOGGER.debug('Dry-run: Not posting with params %s', params)
    return
  try:
    LOGGER.debug('Posting with params %s', params)
    params.update({'password': password})
    requests.post(url, params=params)
  except requests.exceptions.RequestException:
    LOGGER.error('RequestException while posting to %s', url)


def WriteLKGR(lkgr, filename, dry):  # pragma: no cover
  """Write the lkgr to a file.

  Args:
    lkgr: the lkgr to write.
    filename: the path to the file to write to.
    dry: if True, don't actually write the file.
  """
  LOGGER.info('Writing lkgr to file.')
  path = os.path.abspath(filename)
  if dry:
    LOGGER.debug('Dry-run: Not writing lkgr to file at %s', path)
    return
  LOGGER.info('Writing lkgr to file at %s', path)
  with open(path, 'w') as f:
    f.write(str(lkgr))


def ReadLKGR(filename):  # pragma: no cover
  """Read the lkgr from a file.

  Args:
    filename: the path to the file to read from.
  """
  path = os.path.abspath(filename)
  LOGGER.info('Reading lkgr from file at %s', path)
  try:
    with open(path, 'r') as f:
      return f.read().strip()
  except:
    return None


def WriteHTML(status_gen, filename, dry):  # pragma: no cover
  """Write the html status to a file.

  Args:
    status_gen: populated instance of HTMLStatusGenerator
    filename: the path to the file to write to.
    dry: if True, don't actually write the file.
  """
  LOGGER.info('Writing html status to file.')
  path = os.path.abspath(filename)
  if dry:
    LOGGER.debug('Dry-run: Not writing html status to file at %s', path)
    return
  LOGGER.info('Writing html status to file at %s', path)
  with open(path, 'w') as f:
    f.write(status_gen.generate())


##################################################
# Processing logic
##################################################

def GetProjectConfig(project):  # pragma: no cover
  """Get and combine default and project-specific configuration."""
  try:
    tmp_namespace = {}
    config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'config', 'default_cfg.pyl')
    config = ast.literal_eval(open(config_file).read())
  except (IOError, ValueError):
    LOGGER.fatal('Could not read default configuration file.')
    raise

  try:
    config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'config', '%s_cfg.pyl' % project)
    config.update(ast.literal_eval(open(config_file).read()))
  except (IOError, ValueError):
    LOGGER.fatal('Could not read project configuration file. Does it exist?')
    raise

  return config
