#!/usr/bin/env python
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Fetch the latest results for a pre-selected set of builders we care about.
If we find a 'good' revision -- based on criteria explained below -- we
mark the revision as LKGR, and POST it to the LKGR server:

http://chromium-status.appspot.com/lkgr

We're looking for a sequence in the revision history that looks something
like this:

  Revision        Builder1        Builder2        Builder3
 -----------------------------------------------------------
     12357         green

     12355                                         green

     12352                         green

     12349                                         green

     12345         green


Given this revision history, we mark 12352 as LKGR.  Why?

  - We know 12352 is good for Builder2.
  - Since Builder1 had two green builds in a row, we can be reasonably
    confident that all revisions between the two builds (12346 - 12356,
    including 12352), are also green for Builder1.
  - Same reasoning for Builder3.

To find a revision that meets these criteria, we can walk backward through
the revision history until we get a green build for every builder.  When
that happens, we mark a revision as *possibly* LKGR.  We then continue
backward looking for a second green build on all builders (and no failures).
For all builders that are green on the LKGR candidate itself (12352 in the
example), that revision counts as BOTH the first and second green builds.
Hence, in the example above, we don't look for an actual second green build
of Builder2.

Note that this arrangement is symmetrical; we could also walk forward through
the revisions and run the same algorithm.  Since we are only interested in the
*latest* good revision, we start with the most recent revision and walk
backward.
"""

assert __name__ == '__main__', 'This file cannot be imported as a library.'

import argparse
import datetime
import json
import logging
import multiprocessing
import os
import Queue
import re
import signal
import smtplib
import socket
import subprocess
import sys
import textwrap
import threading
import urllib
import xml.etree.ElementTree as xml

if __name__ == '__main__' and __package__ is None:
  up = os.path.dirname
  sys.path.insert(1, up(up(up(os.path.abspath(__file__)))))
from pylib import git
from third_party import requests


LOGGER = logging.getLogger(__name__)
RUN_LOG = []


GIT_HASH_RE = re.compile('^[a-fA-F0-9]{40}$')


##################################################
# Helper classes
##################################################
class NOTSET(object):
  """Singleton class for argument parser defaults."""
  @staticmethod
  def __str__():
    return '<Not Set>'
NOTSET = NOTSET()


class NOREV(object):
  """Singleton class to represent the wholesale lack of a revision."""
  @staticmethod
  def __str__():
    return '<No Revision>'
NOREV = NOREV()


class STATUS:
  """Enum for holding possible build statuses."""
  UNKNOWN, RUNNING, SUCCESS, FAILURE = range(4)

  @staticmethod
  def tostr(status):
    return ['unknown', 'running', 'success', 'failure'][status]


class RevisionKeyfunc(object):
  def __call__(self, r):
    raise NotImplementedError

  def cache(self, *revs):
    pass


class SvnRevKeyfunc(RevisionKeyfunc):
  def __call__(self, r):
    try:
      return int(r)
    except:
      return None


class GitRevKeyfunc(RevisionKeyfunc):
  def __init__(self, git_repo):
    self._cache = {}
    self._git_repo = git_repo
    # Warm up the git-number ref by numbering all the way to HEAD.
    self._git_repo.number()

  def __call__(self, r):
    if r is NOREV or not GIT_HASH_RE.match(r):
      return None
    if r not in self._cache:
      self.cache(r)
    return self._cache.get(r)

  def cache(self, *revs):
    nums = map(int, self._git_repo.number(*revs))
    self._cache.update(dict(zip(revs, nums)))


class RunLogger(logging.Filter):
  def filter(self, record):
    RUN_LOG.append('%s: %s' % (datetime.datetime.now(), record.getMessage()))
    return True


##################################################
# Status Generators
##################################################
class StatusGenerator(object):
  def master_cb(self, master):
    pass
  def builder_cb(self, builder):
    pass
  def revision_cb(self, revision):
    pass
  def build_cb(self, master, builder, status, build_num=None):
    pass
  def lkgr_cb(self, revision):
    pass


class HTMLStatusGenerator(StatusGenerator):
  def __init__(self):
    self.masters = []
    self.rows = []

  def master_cb(self, master):
    self.masters.append((master, []))

  def builder_cb(self, builder):
    self.masters[-1][1].append(builder)

  def revision_cb(self, revision):
    tmpl = 'https://src.chromium.org/viewvc/chrome?view=rev&revision=%s'
    row = [
        revision,
        '<td class="revision"><a href="%s" target="_blank">%s</a></td>\n' % (
            tmpl % urllib.quote(revision), revision)]
    self.rows.append(row)

  def build_cb(self, master, builder, status, build_num=None):
    stat_txt = STATUS.tostr(status)
    cell = '  <td class="%s">' % stat_txt
    if build_num is not None:
      build_url = 'build.chromium.org/p/%s/builders/%s/builds/%s' % (
          master, builder, build_num)
      cell += '<a href="http://%s" target="_blank">X</a>' % (
          urllib.quote(build_url))
    cell += '</td>\n'
    self.rows[-1].append(cell)

  def lkgr_cb(self, revision):
    row = self.rows[-1]
    row[1] = row[1].replace('class="revision"', 'class="lkgr"', 1)
    for i in range(2, len(row)):
      row[i] = row[i].replace('class="success"', 'class="lkgr"', 1)

  def generate(self):
    html_chunks = [textwrap.dedent("""
        <html>
        <head>
        <style type="text/css">
        table { border-collapse: collapse; }
        th { font-size: xx-small; }
        td, th { text-align: center; }
        .header { border: 1px solid black; }
        .revision { padding-left: 5px; padding-right: 5px; }
        .revision { border-left: 1px solid black; border-right: 1px solid black; }
        .success { background-color: #8d4; }
        .failure { background-color: #e88; }
        .running { background-color: #fe1; }
        .unknown { background-color: #ddd; }
        .lkgr { background-color: #4af; }
        .roll { border-top: 2px solid black; }
        </style>
        </head>
        <body><table>
        """)]
    master_headers = ['<tr class="header"><th></th>\n']
    builder_headers = ['<tr class="header">']
    builder_headers.append('<th>chromium revision</th>\n')
    for master, builders in self.masters:
      master_url = 'build.chromium.org/p/%s' % master
      hdr = '  <th colspan="%d" class="header">' % len(builders)
      hdr += '<a href="%s" target="_blank">%s</a></th>\n' % (
          'http://%s' % urllib.quote(master_url), master)
      master_headers.append(hdr)
      for builder in builders:
        builder_url = 'build.chromium.org/p/%s/builders/%s' % (
            master, builder)
        hdr = '  <th><a href="%s" target="_blank">%s</a></th>\n' % (
            'http://%s' % urllib.quote(builder_url), builder)
        builder_headers.append(hdr)
    master_headers.append('</tr>\n')
    builder_headers.append('</tr>\n')
    html_chunks.extend(master_headers)
    html_chunks.extend(builder_headers)
    for row in self.rows:
      rowclass = ''
      html_chunks.extend(row[1:])
      html_chunks.append('</tr>\n')
    html_chunks.append('</table></body></html>\n')
    return ''.join(html_chunks)


##################################################
# Input Functions
##################################################
def FetchBuilderJson(fetch_q):
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


def FetchBuildData(masters, max_threads=0):
  """Fetch all build data about the builders in the input masters.

  Args:
    @param masters: Dictionary of the form
    { master: {
        base_url: string
        builders: [list of strings]
    } }
    @param max_threads: Maximum number of parallel requests.
    @type max_threads: int
    This dictionary is a subset of the project configuration json.
    @type masters: dict
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


def ReadBuildData(filename):
  """Read all build data from a file or stdin."""
  try:
    fh = sys.stdin if filename == '-' else open(filename, 'r')
    with fh:
      return json.load(fh)
  except (IOError, ValueError), e:
    LOGGER.error('Could not read build data from %s:\n%s\n', filename, repr(e))
    raise


def FetchLKGR(lkgr_url):
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
def IsResultFailure(result_data):
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

  if build_data['currentStep'] is not None:
    status = STATUS.RUNNING
    for step in build_data['steps']:
      if step['isFinished'] is True and IsResultFailure(step.get('results')):
        return STATUS.FAILURE
  elif IsResultFailure(build_data.get('results')):
    status = STATUS.FAILURE

  return status


def CollateRevisionHistory(build_data, lkgr_builders, revkey):
  """Organize complex build data into a simpler form.

  Returns:
    A dict of the following form:
      build_history = {master: {builder: [(revision, bool, build_num), ...]}}
    And a list of revisions:
      revisions = [revision, ...]
    With revisions and build_history[master][builder] sorted by their revkeys.

  Args:
    build_data: json-formatted build data returned by buildbot.
    lkgr_builders: List of interesting builders.
    revkey: Keyfunc to map each revision to a sortable key
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
          if prop[0] == 'got_revision':
            revision = prop[1]
            break
        if not revision:
          revision = this_build_data.get(
              'sourceStamp', {}).get('revision', None)
        if not revision:
          continue
        revisions.add(str(revision))
        status = EvaluateBuildData(this_build_data)
        builder_history.append((revision, status, build_num))
      revkey.cache(*list(revisions))
      master_history[builder] = sorted(
          builder_history, key=lambda x: revkey(x[0]))
  revisions = sorted(revisions, key=revkey)
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
  if not status_gen:
    status_gen = StatusGenerator()
  builders = []
  for master, master_history in build_history.iteritems():
    status_gen.master_cb(master)
    for builder, builder_history in master_history.iteritems():
      status_gen.builder_cb(builder)
      gen = reversed(builder_history)
      prev = []
      try:
        prev.append(gen.next())
      except StopIteration:
        prev.append((NOREV, STATUS.UNKNOWN, -1))
      builders.append((master, builder, gen, prev))
  for revision in reversed(revisions):
    status_gen.revision_cb(revision)
    good_revision = True
    for master, builder, gen, prev in builders:
      try:
        while revkey(revision) < revkey(prev[-1][0]):
          prev.append(gen.next())
      except StopIteration:
        prev.append((NOREV, STATUS.UNKNOWN, -1))

      # current build matches revision
      if revkey(revision) == revkey(prev[-1][0]):
        status = prev[-1][1]
      elif len(prev) == 1:
        assert revkey(revision) > revkey(prev[-1][0])
        # most recent build is behind revision
        status = STATUS.UNKNOWN
      elif prev[-1][1] == STATUS.UNKNOWN:
        status = STATUS.UNKNOWN
      else:
        # We color space between FAILED and INPROGRESS builds as FAILED,
        # since that is what it will eventually become.
        if prev[-1][1] == STATUS.SUCCESS and prev[-2][1] == STATUS.RUNNING:
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


def GetLKGRAge(lkgr, repo):
  """Parse the LKGR revision timestamp from the commit log."""
  lkgr_dt = datetime.datetime.utcnow()
  if isinstance(repo, git.Git):
    # format:%ct gives the Unix epoch timestamp
    ts = repo.show(lkgr, '', '--format=format:%ct').split('\n', 1)[0].strip()
    lkgr_dt = datetime.datetime.utcfromtimestamp(float(ts))
  else:
    cmd = ['svn', 'log', '--non-interactive', '--xml', '-r', str(lkgr), repo]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    stdout = process.communicate()[0]
    if not process.returncode:
      log = xml.fromstring(stdout)
      date = log.find('logentry').find('date').text
      if date:
        lkgr_dt = datetime.datetime.strptime(date, '%Y-%m-%dT%H:%M:%S.%fZ')
  lkgr_age = datetime.datetime.utcnow() - lkgr_dt
  return lkgr_age


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
def SendMail(sender, recipients, subject, message, dry):
  if dry:
    LOGGER.info('Dry-run: Not sending mail with subject: "%s"', subject)
    return
  LOGGER.info('Sending mail with subject: "%s"', subject)
  try:
    body = ['From: %s' % sender]
    body.append('To: %s' % recipients)
    body.append('Subject: %s' % subject)
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


def UpdateTag(new_lkgr, repo, dry):
  """Update the lkgr tag in the repository. Git only.

  Args:
    new_lkgr: the new commit hash for the lkgr tag to point to.
    repo: the path to the on-disk repo.
    dry: if True, don't actually update the tag.
  """
  LOGGER.info('Updating lkgr tag')
  git_repo = git.Git(repo)
  push_cmd = ['push', 'origin', '%s:refs/tags/lkgr' % new_lkgr]

  try:
    if dry:
      LOGGER.debug('Dry-run: Not pushing lkgr: %s', ' '.join(push_cmd))
    else:
      LOGGER.debug('Pushing lkgr: %s', ' '.join(push_cmd))
      repo._retry(push_cmd)
  except subprocess.CalledProcessError:
    LOGGER.error('Failed to push new lkgr tag.')


def PostLKGR(status_url, lkgr, lkgr_alt, vcs, password_file, dry):
  """Posts the LKGR to the status_url.

  Args:
    status_url: the instance of chromium-status to post the lkgr to
    lkgr: the value of the new lkgr to post
    lkgr_alt: an alternate lkgr value (such as the git number for the hash)
    vcs: 'svn' or 'git', determines the parameters to use in the post
    password_file: path to a password file containing the shared secret
    dry: if True, don't actually make the post request
  """
  url = status_url + '/revisions'
  if vcs == 'git':
    url = status_url + '/commits'
  LOGGER.info('Posting to %s', url)

  try:
    with open(password_file, 'r') as f:
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
      'git_hash': lkgr,
      'gen_number': lkgr_alt,
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


def WriteLKGR(lkgr, filename, dry):
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


def WriteHTML(status_gen, filename, dry):
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
# Main program logic
##################################################
def ParseArgs(argv):
  parser = argparse.ArgumentParser()

  log_group = parser.add_mutually_exclusive_group()
  log_group.add_argument('--quiet', '-q', dest='loglevel',
                         action='store_const', const='CRITICAL', default='INFO')
  log_group.add_argument('--verbose', '-v', dest='loglevel',
                         action='store_const', const='DEBUG', default='INFO')


  input_group = parser.add_argument_group('Input data sources')
  input_group.add_argument('--buildbot', action='store_true', default=True,
                           help='Get data from Buildbot JSON (default).')
  input_group.add_argument('--build-data', metavar='FILE',
                           help='Get data from the specified file.')
  input_group.add_argument('--manual', metavar='VALUE',
                           help='Bypass logic and manually specify LKGR.')
  input_group.add_argument('--max-threads', '-j', type=int, default=4,
                           help='Maximum number of parallel json requests. '
                           'A value of zero means full parallelism.')

  output_group = parser.add_argument_group('Output data formats')
  output_group.add_argument('--dry-run', '-n', action='store_true',
                            help='Don\'t actually do any real output actions.')
  output_group.add_argument('--post', action='store_true',
                            help='Post the LKGR to the configured status app.')
  output_group.add_argument('--tag', action='store_true',
                            help='Update the lkgr tag (Git repos only)')
  output_group.add_argument('--write-to-file', metavar='FILE',
                            help='Write the LKGR to the specified file.')
  output_group.add_argument('--dump-build-data', metavar='FILE',
                            help='Dump the build data to the specified file.')
  output_group.add_argument('--html', metavar='FILE',
                            help='Output data in HTML format for debugging.')
  output_group.add_argument('--email-errors', action='store_true',
                            help='Send email to LKGR admins upon error (cron).')

  config_group = parser.add_argument_group('Project configuration overrides')
  config_group.add_argument('--password-file',
                            default=NOTSET,
                            help='File containing password for status app.')
  config_group.add_argument('--error-recipients', metavar='EMAILS',
                            default=NOTSET,
                            help='Send email to these addresses upon error.')
  config_group.add_argument('--update-recipients', metavar='EMAILS',
                            default=NOTSET,
                            help='Send email to these address upon success.')
  config_group.add_argument('--allowed-gap', type=int, metavar='GAP',
                            default=NOTSET,
                            help='How many revisions to allow between head and '
                            'LKGR before it\'s considered out-of-date.')
  config_group.add_argument('--allowed-lag', type=int, metavar='LAG',
                            default=NOTSET,
                            help='How many hours to allow since an LKGR update '
                            'before it\'s considered out-of-date. This is a '
                            'minimum and will be increased when commit '
                            'activity slows.')
  config_arg_names = ['password_file', 'error_recipients', 'update_recipients',
                      'allowed_gap', 'allowed_lag']

  parser.add_argument('--project', required=True,
                      help='Project for which to calculate the LKGR.'
                      'Currently accepted projects are those with a '
                      '<project>.cfg file in this directory.')
  parser.add_argument('--force', action='store_true',
                      help='Force updating the lkgr to the found (or '
                      'manually specified) value. Skips checking for '
                      'validity against the current LKGR.')

  args = parser.parse_args(argv)
  return args, config_arg_names

def main(argv):
  # TODO(agable): Refactor this into multiple sequential helper functions.
  # TODO(agable): Create Git and Svn wrappers so vcs-checking logic can die.
  args, config_arg_names = ParseArgs(argv)

  global LOGGER
  logging.basicConfig(
      # %(levelname)s is formatted to min-width 8 since CRITICAL is 8 letters.
      format='%(asctime)s | %(levelname)8s | %(name)s | %(message)s',
      level=args.loglevel)
  LOGGER = logging.getLogger(__name__)
  LOGGER.addFilter(RunLogger())

  # Combine default, project-specific, and command-line configuration.
  try:
    tmp_namespace = {}
    config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'config', 'default_cfg.py')
    execfile(config_file, tmp_namespace, tmp_namespace)
    config = tmp_namespace.get('CONFIG', {})
  except (IOError, ValueError):
    LOGGER.fatal('Could not read default configuration file.')
    raise
  try:
    config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'config', '%s_cfg.py' % args.project)
    execfile(config_file, tmp_namespace, tmp_namespace)
    config.update(tmp_namespace.get('CONFIG', {}))
  except (IOError, ValueError):
    LOGGER.fatal('Could not read project configuration file. Does it exist?')
    raise
  for name in config_arg_names:
    cmd_line_config = getattr(args, name, NOTSET)
    if cmd_line_config is not NOTSET:
      config[name] = cmd_line_config

  # Error notification setup.
  sender = 'lkgr_finder@%s' % socket.getfqdn()
  error_recipients = config['error_recipients']
  update_recipients = config['update_recipients']
  subject_base = os.path.basename(__file__) + ': '

  # Calculate new candidate LKGR.
  LOGGER.info('Calculating LKGR for project %s', args.project)

  if config['source_vcs'] == 'git':
    LOGGER.debug('Getting git repository for %s', config['source_url'])
    git_repo = git.NewGit(config['source_url'],
                          os.path.join('workdir', args.project))
    if not git_repo:
      LOGGER.fatal('Failed to get working git repository.')
      return 1
    LOGGER.debug('Local git repository located at %s', git_repo.path)
    revkey = GitRevKeyfunc(git_repo)
  else:
    git_repo = None
    revkey = SvnRevKeyfunc()

  if args.manual:
    candidate = args.manual
    LOGGER.info('Using manually specified candidate %s', args.manual)
    try:
      if config['source_vcs'] == 'git':
        assert GIT_HASH_RE.match(candidate)
      else:
        candidate = int(candidate)
    except (AssertionError, ValueError):
      LOGGER.fatal('Manually specified revision %s is not a valid revision '
          'for project %s' % (args.manual, args.project))
      return 1
  else:
    lkgr_builders = config['masters']
    if args.build_data:
      builds = ReadBuildData(args.build_data)
    else:
      builds = FetchBuildData(lkgr_builders, args.max_threads)

    if args.dump_build_data:
      try:
        with open(args.dump_build_data, 'w') as fh:
          json.dump(builds, fh, indent=2)
      except IOError, e:
        LOGGER.warn('Could not dump to %s:\n%s\n' %
            (args.dump_build_data, repr(e)))

    (build_history, revisions) = CollateRevisionHistory(
        builds, lkgr_builders, revkey)

    status_gen = None
    if args.html:
      status_gen = HTMLStatusGenerator()

    candidate = FindLKGRCandidate(build_history, revisions, revkey, status_gen)

    if args.html:
      WriteHTML(status_gen, args.html, args.dry_run)

  LOGGER.info('Candidate LKGR is %s (%s)', candidate, revkey(candidate))

  lkgr = None
  if not args.force:
    # Get old/current LKGR.
    lkgr_url = config['status_url'] + '/lkgr'
    if config['source_vcs'] == 'git':
      lkgr_url = config['status_url'] + '/git-lkgr'
    lkgr = FetchLKGR(lkgr_url)
    if lkgr is None:
      if args.email_errors:
        SendMail(sender, error_recipients,
                 subject_base + 'Failed to fetch %s LKGR' % args.project,
                 '\n'.join(RUN_LOG), args.dry_run)
      return 1
    try:
      if config['source_vcs'] == 'git':
        assert GIT_HASH_RE.match(lkgr)
      else:
        lkgr = int(lkgr)
    except (AssertionError, ValueError):
      if args.email_errors:
        SendMail(sender, error_recipients,
                 subject_base + 'Fetched bad current %s LKGR' % args.project,
                 '\n'.join(RUN_LOG), args.dry_run)
      return 1

    LOGGER.info('Current LKGR is %s (%s)', lkgr, revkey(lkgr))

  if candidate and (args.force or revkey(candidate) > revkey(lkgr)):
    # We found a new LKGR!
    LOGGER.info('Candidate is%snewer than current %s LKGR!', 
        ' (forcefully) ' if args.force else ' ', args.project)

    candidate_alt = candidate
    if git_repo:
      candidate_alt = git_repo.number(candidate)[0]

    if args.write_to_file:
      WriteLKGR(candidate, args.write_to_file, args.dry_run)

    if args.post:
      PostLKGR(config['status_url'], candidate, candidate_alt,
               config['source_vcs'], config['password_file'], args.dry_run)
      if update_recipients:
        subject = 'Updated %s LKGR to %s' % (args.project, candidate)
        message = subject + '.\n'
        SendMail(sender, update_recipients, subject, message, args.dry_run)

    if args.tag and config['source_vcs'] == 'git':
      UpdateTag(candidate, config['source_url'], args.dry_run)

  else:
    # No new LKGR found.
    LOGGER.info('Candidate is not newer than current %s LKGR.', args.project)

    if not args.manual:
      if config['source_vcs'] == 'git':
        rev_nums = map(int, git_repo.number(revisions[-1], lkgr))
        rev_behind = rev_nums[0] - rev_nums[1]
      else:
        rev_behind = int(revisions[-1]) - lkgr
      LOGGER.info('LKGR is %d revisions behind', rev_behind)

      if rev_behind > config['allowed_gap']:
        if args.email_errors:
          SendMail(sender, error_recipients,
                   '%s%s LKGR (%s) > %s revisions behind' %
                   (subject_base, args.project, lkgr, config['allowed_gap']),
                   '\n'.join(RUN_LOG), args.dry_run)
        return 1

      if config['source_vcs'] == 'git':
        time_behind = GetLKGRAge(lkgr, git_repo)
      else:
        time_behind = GetLKGRAge(lkgr, config['source_url'])
      LOGGER.info('LKGR is %s behind', time_behind)

      if not CheckLKGRLag(
          time_behind, rev_behind, config['allowed_lag'], config['allowed_gap']):
        if args.email_errors:
          SendMail(sender, error_recipients,
                   '%s%s LKGR (%s) exceeds lag threshold' %
                   (subject_base, args.project, lkgr),
                   '\n'.join(RUN_LOG), args.dry_run)
        return 1

  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
