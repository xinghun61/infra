# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A collection of helpers to make lkgr_finder's life easier."""

# pylint: disable=line-too-long
# pylint: disable=unused-argument

import Queue
import ast
import base64
import collections
import datetime
import httplib2
import json
import logging
import os
import re
import requests
import smtplib
import socket
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as xml

import google.protobuf.message
import infra_libs
from infra_libs import luci_auth
from infra.libs import git
from infra.libs.buildbucket.proto import common_pb2
from infra.libs.buildbucket.proto import rpc_pb2


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
class GitWrapper(object):
  _status_path = '/git-lkgr'
  _GIT_HASH_RE = re.compile('^[a-fA-F0-9]{40}$')
  _GIT_POS_RE = re.compile('(\S+)@{#(\d+)}')

  def __init__(self, url, path):  # pragma: no cover
    self._git = git.NewGit(url, path)
    self._position_cache = {}
    LOGGER.debug('Local git repository located at %s', self._git.path)

  @property
  def status_path(self):  # pragma: no cover
    return self._status_path

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


##################################################
# Input Functions
##################################################


Build = collections.namedtuple(
    'Build', ['number', 'result', 'revision'])


MILO_JSON_ENDPOINT = (
    'https://luci-milo.appspot.com/prpc/milo.Buildbot/GetBuildbotBuildsJSON')


OAUTH_SCOPES = ['https://www.googleapis.com/auth/userinfo.email']


def _FetchBuilderJsonFromMilo(master, builder, limit=100,
                             service_account_file=None): # pragma: no cover
  LOGGER.debug('Fetching buildbot json for %s/%s from milo', master, builder)
  body = {
      'master': master,
      'builder': builder,
      'limit': limit
  }
  headers = {
    'Accept': 'application/json',
    'Content-Type': 'application/json',
  }
  http = httplib2.Http(timeout=300)
  creds = None
  if service_account_file:
    creds = infra_libs.get_signed_jwt_assertion_credentials(
        service_account_file, scope=OAUTH_SCOPES)
  elif luci_auth.available():
    creds = luci_auth.LUCICredentials(scopes=OAUTH_SCOPES)

  if creds:
    creds.authorize(http)

  resp, content = http.request(
      MILO_JSON_ENDPOINT, method='POST', headers=headers, body=json.dumps(body))
  if resp.status != 200:
    raise httplib2.HttpLib2Error('Invalid response status: %s\n%s' % (
        resp.status, content))
  # Strip off jsonp header.
  data = json.loads(content[4:])
  builds = [
      json.loads(base64.b64decode(build['data'])) for build in data['builds']]
  return {build['number']: build for build in builds}


def _FetchBuildbotJson(master, builder, service_account_file=None):
  limits = [100, 50, 25, 10]
  sleep = 1
  try:
    for i in xrange(len(limits)):  # pragma: no branch
      try:
        return _FetchBuilderJsonFromMilo(
            master, builder, limit=limits[i],
            service_account_file=service_account_file)
      except httplib2.HttpLib2Error:
        if i == len(limits) - 1:
          raise
        LOGGER.warning(
            'HTTP Error when fetching past %d builds of %s. Will try '
            'fetching %d builds after a %d second sleep.',
            limits[i], builder, limits[i+1], sleep)
        time.sleep(sleep)
        sleep *= 2
  except httplib2.HttpLib2Error as e:
    LOGGER.error(
        'RequestException while fetching %s/%s:\n%s',
        master, builder, repr(e))
    return None


def FetchBuildbotBuildsForBuilder(
    master, builder, service_account_file=None):
  builder_data = _FetchBuildbotJson(
      master, builder, service_account_file=service_account_file)

  if builder_data is None:
    return None

  builds = []
  for build_number, build_data in builder_data.iteritems():
    build_properties = {
      prop[0]: prop[1]
      for prop in build_data.get('properties') or []
    }
    # Revision fallthrough:
    revision = (
        # * If there is a got_src_revision, we probably want to use that,
        #   because otherwise it wouldn't be specified.
        build_properties.get('got_src_revision')
        # * If we're in Git and there's a got_revision_git, might as well
        #   use that since it is guaranteed to be the right type.
        or build_properties.get('got_revision_git')
        # * Finally, just use the default got_revision.
        or build_properties.get('got_revision')
        or None)
    status = EvaluateBuildData(build_data)
    if revision is None:
      if status is STATUS.FAILURE or status is STATUS.RUNNING:
        # The build failed too early or is still in early stage even before
        # chromium revision was tagged. If we allow 'revision' fallback it
        # will end up being non-chromium revision for non chromium projects.
        continue
    if not revision:
      revision = build_data.get(
          'sourceStamp', {}).get('revision', None)
    if not revision:
      continue
    if len(str(revision)) < 40:
      # Ignore stource stamps that don't contain a proper git hash. This
      # can happen if very old build numbers get into the build data.
      continue
    builds.append(Build(build_number, status, revision))

  return builds


_BUILDBUCKET_SEARCH_ENDPOINT_V2 = (
    'https://{buildbucket_instance}/prpc/buildbucket.v2.Builds/SearchBuilds')
_DEFAULT_BUILDBUCKET_INSTANCE = 'cr-buildbucket.appspot.com'


def _FetchFromBuildbucketImpl(
    project, bucket_name, builder,
    service_account_file=None):  # pragma: no cover
  request_pb = rpc_pb2.SearchBuildsRequest()
  request_pb.predicate.builder.project = project
  request_pb.predicate.builder.bucket = bucket_name
  request_pb.predicate.builder.builder = builder
  request_pb.predicate.status = common_pb2.ENDED_MASK
  request_pb.fields.paths.extend([
    'builds.*.number',
    'builds.*.status',
    'builds.*.input.gitiles_commit.id',
  ])

  headers = {
    'Accept': 'application/prpc; encoding=binary',
    'Content-Type': 'application/prpc; encoding=binary',
  }

  http = httplib2.Http(timeout=300)
  creds = None
  if service_account_file:
    creds = infra_libs.get_signed_jwt_assertion_credentials(
        service_account_file, scope=OAUTH_SCOPES)
  elif luci_auth.available():
    creds = luci_auth.LUCICredentials(scopes=OAUTH_SCOPES)
  if creds:
    creds.authorize(http)

  resp, content = http.request(
      _BUILDBUCKET_SEARCH_ENDPOINT_V2.format(
          buildbucket_instance=_DEFAULT_BUILDBUCKET_INSTANCE),
      method='POST',
      headers=headers,
      body=request_pb.SerializeToString())
  grpc_code = resp.get('X-Prpc-Grpc-Code'.lower())
  if grpc_code != '0':
    raise httplib2.HttpLib2Error('Invalid GRPC exit code: %s\n%s' % (
        grpc_code, content))
  response_pb = rpc_pb2.SearchBuildsResponse()
  response_pb.ParseFromString(content)

  return response_pb


_BUILDBUCKET_STATUS = {
  common_pb2.CANCELED: STATUS.UNKNOWN,
  common_pb2.FAILURE: STATUS.FAILURE,
  common_pb2.INFRA_FAILURE: STATUS.FAILURE,
  common_pb2.SUCCESS: STATUS.SUCCESS,
}


def FetchBuildbucketBuildsForBuilder(
    bucket, builder, service_account_file=None):
  LOGGER.debug('Fetching builds for %s/%s from buildbucket', bucket, builder)

  if not '/' in bucket:
    LOGGER.error(
        'Unexpected bucket "%s". '
        + 'Buckets should be specified as $PROJECT/$BUCKET_NAME.',
        bucket)
    return None

  project, bucket_name = bucket.split('/', 1)

  try:
    response_pb = _FetchFromBuildbucketImpl(
        project, bucket_name, builder,
        service_account_file=service_account_file)
  except httplib2.HttpLib2Error as e:
    LOGGER.error(
        'RequestException while fetching %s/%s/%s:\n%s',
        project, bucket_name, builder, repr(e))
    return None
  except google.protobuf.message.Error as e:
    LOGGER.error(
        'Unknown protobuf error while fetching %s/%s/%s:\n%s',
        project, bucket_name, builder, repr(e))
    return None

  builds = []
  for build_pb in response_pb.builds:
    number = build_pb.number
    result = _BUILDBUCKET_STATUS.get(build_pb.status)
    revision = build_pb.input.gitiles_commit.id
    if bool(number) and bool(revision) and result is not None:
      builds.append(Build(number, result, revision))
  return builds


def FetchBuildsWorker(fetch_q, fetch_fn):  # pragma: no cover
  """Pull build json from buildbot masters.

  Args:
    @param fetch_q: A pre-populated Queue.Queue containing tuples of:
      master: buildbot master to get json from.
      builder: Name of the builder on that master.
      output_builds: Output dictionary of builder to build data.
    @type fetch_q: tuple
  """
  while True:
    try:
      master, builder, service_account, output_builds = fetch_q.get(False)
    except Queue.Empty:
      return

    output_builds[builder] = fetch_fn(
        master, builder, service_account_file=service_account)


def FetchBuildbotBuilds(
    masters, max_threads=0, service_account=None):  # pragma: no cover
  """Fetch all build data about the builders in the input masters.

  Args:
    @param masters: Dictionary of the form
    { master: {
        builders: [list of strings]
    } }
    This dictionary is a subset of the project configuration json.
    @type masters: dict
    @param max_threads: Maximum number of parallel requests.
    @type max_threads: int
  """
  return _FetchBuilds(
      masters, FetchBuildbotBuildsForBuilder,
      max_threads=max_threads, service_account=service_account)


def FetchBuildbucketBuilds(
    buckets, max_threads=0, service_account=None):  # pragma: no cover
  """Fetch all build data about the builders from the given buckets.

  Args:
    @param buckets: Dictionary of the form
    { bucket: {
        builders: [list of strings]
    } }
    This dictionary is a subset of the project configuration json.
    @type buckets: dict
    @param max_threads: Maximum number of parallel requests.
    @type max_threads: int
  """
  return _FetchBuilds(
      buckets, FetchBuildbucketBuildsForBuilder,
      max_threads=max_threads, service_account=service_account)


def _FetchBuilds(
    config, fetch_fn, max_threads=0, service_account=None):  # pragma: no cover
  build_data = {key: {} for key in config}
  fetch_q = Queue.Queue()
  for key, config_data in config.iteritems():
    builders = config_data['builders']
    for builder in builders:
      fetch_q.put((key, builder, service_account, build_data[key]))
  fetch_threads = set()
  if not max_threads:
    max_threads = fetch_q.qsize()
  for _ in xrange(max_threads):
    th = threading.Thread(target=FetchBuildsWorker,
                          args=(fetch_q, fetch_fn))
    th.start()
    fetch_threads.add(th)
  for th in fetch_threads:
    th.join()

  failures = 0
  for key, builders in build_data.iteritems():
    for builder, builds in builders.iteritems():
      if builds is None:
        failures += 1
        LOGGER.error('Failed to fetch builds for %s:%s' % (key, builder))

  return build_data, failures


_BUILD_DATA_VERSION = 2


def LoadBuilds(filename):
  """Read all build data from a file or stdin."""
  fh = sys.stdin if filename == '-' else open(filename, 'r')
  with fh:
    wrapped_builds = json.load(fh)

  if wrapped_builds.get('version') != _BUILD_DATA_VERSION:
    return None

  builds = wrapped_builds.get('builds', {})
  for key, val in builds.iteritems():
    for builder, builder_data in val.iteritems():
      builds[key][builder] = [Build(*b) for b in builder_data]

  return builds


def DumpBuilds(builds, filename):
  """Dump all build data to a file."""
  wrapped_builds = {
    'builds': builds,
    'version': _BUILD_DATA_VERSION,
  }
  with open(filename, 'w') as fh:
    json.dump(wrapped_builds, fh, indent=2)


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


def EvaluateBuildData(build_data):
  """Determine the status of a build."""
  status = STATUS.SUCCESS

  if build_data.get('currentStep') is not None:
    status = STATUS.RUNNING
    for step in build_data['steps']:
      if step['isFinished'] is True and IsResultFailure(step.get('results')):
        return STATUS.FAILURE
  elif IsResultFailure(build_data.get('results')):
    status = STATUS.FAILURE

  return status


def CollateRevisionHistory(builds, repo):
  """Sorts builds and revisions in repository order.

  Args:
    builds: a dict of the form:

    ```
    builds := {
      master: {
        builder: [Build, ...],
        ...,
      },
      ...
    }
    ```

    repo (GitWrapper): repository in which the revision occurs.

  Returns:
    A 2-tuple of (build_history, revisions), where:

    ```
    build_history := {
      master: {
        builder: [Build, ...],
        ...,
      },
      ...
    }
    ```

    and

    ```
    revisions := [revision, ...]
    ```
  """
  build_history = {}
  revisions = set()
  for category, category_data in builds.iteritems():
    LOGGER.debug('Collating category %s', category)
    category_history = build_history.setdefault(category, {})
    for builder, builder_data in category_data.iteritems():
      LOGGER.debug('Collating builder %s', builder)
      for build in builder_data:
        revisions.add(str(build.revision))
      category_history[builder] = repo.sort(
          builder_data, keyfunc=lambda b: b.revision)
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
  def lowercase_key(item_pair):
    return item_pair[0].lower()

  lkgr = None
  builders = []
  for category, category_history in sorted(build_history.items(),
                                           key=lowercase_key):
    status_gen.category_cb(category)
    for builder, builder_history in sorted(category_history.items(),
                                           key=lowercase_key):
      status_gen.builder_cb(builder)
      gen = reversed(builder_history)
      prev = []
      try:
        prev.append(gen.next())
      except StopIteration:
        prev.append(Build(-1, STATUS.UNKNOWN, NOREV))
      builders.append((category, builder, gen, prev))
  for revision in reversed(revisions):
    status_gen.revision_cb(revision)
    good_revision = True
    for category, builder, gen, prev in builders:
      try:
        while revkey(revision) < revkey(prev[-1].revision):
          prev.append(gen.next())
      except StopIteration:  # pragma: no cover
        prev.append(Build(-1, STATUS.UNKNOWN, NOREV))

      # current build matches revision
      if revkey(revision) == revkey(prev[-1].revision):
        status = prev[-1].result
      elif len(prev) == 1:
        assert revkey(revision) > revkey(prev[-1].revision)
        # most recent build is behind revision
        status = STATUS.UNKNOWN
      elif prev[-1].result == STATUS.UNKNOWN:  # pragma: no cover
        status = STATUS.UNKNOWN
      else:
        # We color space between FAILED and INPROGRESS builds as FAILED,
        # since that is what it will eventually become.
        if (prev[-1].result == STATUS.SUCCESS
            and prev[-2].result == STATUS.RUNNING):  # pragma: no cover
          status = STATUS.RUNNING
        elif prev[-1].result == prev[-2].result == STATUS.SUCCESS:
          status = STATUS.SUCCESS
        else:
          status = STATUS.FAILURE
      build_num = None
      if revkey(revision) == revkey(prev[-1].revision):
        build_num = prev[-1].number
      status_gen.build_cb(category, builder, status, build_num)
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
    # TODO(pgervais,crbug.com/455436): send this to sheriff-o-matic instead.
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
  except IOError:
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
