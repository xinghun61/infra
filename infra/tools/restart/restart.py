# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import contextlib
import datetime
import dateutil.tz
import distutils.util
import json
import logging
import os
import pytz
import re
import shutil
import subprocess
import sys
import tempfile


from infra_libs.time_functions import zulu
from infra.services.master_lifecycle import buildbot_state
from infra.services.master_manager_launcher import desired_state_parser


LOGGER = logging.getLogger(__name__)

MM_REPO = 'https://chrome-internal.googlesource.com/infradata/master-manager'

DEFAULT_RESTART_MINUTES = 15

class MasterNotFoundException(Exception):
  pass


RestartSpec = collections.namedtuple('RestartSpec',
    ('name', 'desired_state_name', 'message', 'restart_time'))


_MASTER_CONFIGS = {
  'chromiumos': {'ref': 'chromeos'},
  'chromeos': {
    'message': """\
A %(master)s master restart is *almost always* accompanied by a Chromite
"master" branch pin bump. This should be performed RIGHT BEFORE the time the
master is scheduled to restart so slaves don't prematurely load the new
parameters.

For example:
$ cit cros_pin update master

DO NOT PROCEED unless you have either performed a pin bump or are sure you don't
need one.

See: go/chrome-infra-doc-cros for more information.
""",
  },

  'chromeos_release': {
    'message': """\
A %(master)s master restart is *almost always* accompanied by a Chromite
pin bump for the current release branch. This should be performed RIGHT BEFORE
the time the master is scheduled to restart so slaves don't prematurely load the
new parameters.

For example (replacing #'s with the branch whose pin needs updating):
$ cit cros_pin update release-R##-####.B

DO NOT PROCEED unless you have either performed a pin bump or are sure you don't
need one. If a branch was not specified in the restart request, follow up with
the filer to determine which release branch needs updating.

See: go/chrome-infra-doc-cros for more information.
""",
  },
}


def add_argparse_options(parser):
  parser.add_argument(
      'masters', nargs='*',
      help='Master(s) to restart. "master." prefix can be omitted.')
  parser.add_argument(
      '-x', '--masters-regex', default='',
      help='Regex for names of masters to restart. Result of regex will be '
           'concatentated with any masters provided at the end of the command. '
           '"master." prefix can be omitted.')
  parser.add_argument(
      '-m', '--minutes-in-future', default=DEFAULT_RESTART_MINUTES, type=int,
      help='how many minutes in the future to schedule the restart. '
           'use 0 for "now." default %(default)d')
  parser.add_argument(
      '-o', '--rolling', default=0, type=int,
      help='Do a rolling restart with specified number of minutes between '
           'each master.')
  parser.add_argument(
      '--eod', action='store_true',
      help='Deprecated flag - all restarts should be attended')
  parser.add_argument(
      '-b', '--bug', default=None,
      help='Bug containing master restart request.')
  parser.add_argument(
      '-r', '--reviewer', action='append',
      help=('Reviewer (ldap or ldap@google.com) to TBR the CL to. '
            'If not specified, chooses a random reviewer from OWNERS file'))
  parser.add_argument(
      '-f', '--force', action='store_true',
      help='don\'t ask for confirmation, just commit')
  parser.add_argument(
      '-n', '--no-commit', action='store_true',
      help='update the file, but refrain from performing the actual commit')
  parser.add_argument(
      '-s', '--desired-state', default='running',
      choices=buildbot_state.STATES['desired_buildbot_state'],
      help='which desired state to put the buildbot master in '
           '(default %(default)s)')
  parser.add_argument(
      '-e', '--reason', default='',
      help='reason for restarting the master')


def get_master_names(desired_master_state, name_regex):
  """Returns masters found in <desired_master_state> that match <name_regex>.

  Args:
    desired_master_state: A "desired_master_state" object, e.g. as returned by
        desired_state_parser

  Returns:
    [str1, str2, ...] All masters found in <desired_master_state>
  """
  # Modify regex to allow for optional "master." prefix
  name_regex = r'(master\.)?' + name_regex
  master_matcher = re.compile(name_regex)
  return [m for m in desired_master_state["master_states"].keys()
                 if master_matcher.match(m)]

def get_restart_spec(name, restart_time):
  """Creates a new RestartSpec for master named <name> at <restart_time>.

  _MASTER_CONFIGS is consulted to see if there is a "message" value
  for the given master. If those config settings aren't found, defaults are
  used.

  If the <name> provided does not start with "master.", then it will be added
  in the resulting RestartSpec

  Args:
    name: (string) name of master to create a RestartSpec for. "master."
        prefix is optional, but will be present in the returned RestartSpec
        object.
    restart_time: (datetime.datetime) When to schedule the restart.

  Returns:
    RestartSpec object
  """
  def _trim_prefix(v, prefix):
    if v.startswith(prefix):
      return v[len(prefix):]
    return v
  name = _trim_prefix(name, 'master.')

  def _get_restart_config(name, seen):
    if name in seen:
      raise ValueError('Master config reference loop for "%s"' % (name,))
    seen.add(name)

    d = _MASTER_CONFIGS.get(name, {}).copy()
    if d.get('ref'):
      cur = d
      d = _get_restart_config(d['ref'], seen)
      d.update(cur)
    return d
  d = _get_restart_config(name, set())

  if d.get('message'):
    d['message'] = d['message'] % {'master': name}

  if restart_time is None:
    restart_time = get_restart_time_delta(DEFAULT_RESTART_MINUTES)

  return RestartSpec(
      name=name,
      desired_state_name='master.%s' % (name,),
      message=d.get('message'),
      restart_time=restart_time,
  )


def get_restart_time_delta(mins):
  return datetime.datetime.utcnow() + datetime.timedelta(minutes=mins)


@contextlib.contextmanager
def get_master_state_checkout():
  target_dir = tempfile.mkdtemp()
  try:
    LOGGER.info('Cloning %s into %s' % (MM_REPO, target_dir))
    subprocess.call(['git', 'clone', MM_REPO, target_dir])
    LOGGER.info('done')
    yield target_dir
  finally:
    shutil.rmtree(target_dir)


def autocomplete_and_partition(reviewers):
  """Autocompletes ldap to ldap@google.com.

  Returns partitions the list into google.com emails and others.
  """
  google, other = [], []
  for r in reviewers:
    if '@' in r:
      _, domain = r.split('@', 1)
      if domain != 'google.com':
        other.append(r)
      else:
        google.append(r)
    else:
      google.append('%s@google.com' % r)
  return google, other

def commit(
    target, specs, reviewers, bug, force, no_commit, desired_state, reason):
  """Commits the local CL via the CQ."""
  if desired_state == 'running':
    action = 'Restarting'
  else:
    action = desired_state.title() + 'ing'

  desc = '%(action)s master%(plural)s %(names)s\n\n%(reason)s\n' % {
      'action': action,
      'plural': 's' if len(specs) > 1 else '',
      'names': ', '.join([s.name for s in specs]),
      'reason': reason,
  }
  tbr_whom = 'an owner'
  if reviewers:
    google, other = autocomplete_and_partition(reviewers)
    if other:
      print
      print 'Error: not @google.com email(s) for reviewers found:'
      print '  %s' % ('\n  '.join(other))
      print 'Hint: save your fingertips - use just ldap: -r <ldap>'
      return 1

    tbr_whom = ', '.join(google)
    desc += '\nTBR=%s' % tbr_whom
  if bug:
    desc += '\n\nBug: %s' % bug
  subprocess.check_call(
      ['git', 'commit', '--all', '--message', desc], cwd=target)


  print
  print 'Actions for the following masters:'
  max_name_len = max(len(s.name) for s in specs)
  for s in specs:
    delta = s.restart_time - datetime.datetime.utcnow()
    restart_time_str = zulu.to_zulu_string(s.restart_time)
    local_time = s.restart_time.replace(tzinfo=dateutil.tz.tzutc())
    local_time = local_time.astimezone(dateutil.tz.tzlocal())

    print '\t- %s %-*s in %d minutes (UTC: %s, Local: %s)' % (
      action, max_name_len, s.name, delta.total_seconds() / 60,
      restart_time_str, local_time)

  for s in specs:
    if not s.message:
      continue
    print
    print '=== %s ===' % (s.name,)
    print s.message
  print

  print 'This will upload a CL for master_manager.git, TBR %s, and ' % tbr_whom
  if no_commit:
    print 'wait for you to manually commit.'
  else:
    print 'commit the CL through the CQ.'
  print

  if not force:
    if no_commit:
      print 'Upload CL? (will not set CQ bit) [Y/n]:',
    else:
      print 'Commit? [Y/n]:',
    input_string = raw_input()
    if input_string != '' and not distutils.util.strtobool(input_string):
      print 'Aborting.'
      return

  print 'To cancel, edit desired_master_state.json in %s.' % MM_REPO
  print

  LOGGER.info('Uploading to Rietveld and CQ.')
  upload_cmd = [
      'git', 'cl', 'upload',
      '-m', desc,
      '-f',
  ]
  if not reviewers:
    upload_cmd.append('--tbr-owners')
  if not no_commit:
    upload_cmd.append('-c')
  else:
    LOGGER.info('CQ bit not set, please commit manually. (--no-commit)')
  subprocess.check_call(upload_cmd, cwd=target)


def _configure_git_name_and_email(cwd):
  try:
    name = subprocess.check_output(['git', 'config', 'user.name'],
                                   cwd=cwd).strip()
  except subprocess.CalledProcessError:
    name = ''
  if not name:
    print
    print 'No default name configured in git. Hint: '
    print '   $ git config --global user.name "My Name"'
    name = raw_input('Please provide your name: ').strip()
    if not name:
      return False
    subprocess.call(['git', 'config', '--local', 'user.name', name], cwd=cwd)

  try:
    email = subprocess.check_output(['git', 'config', 'user.email'],
                                    cwd=cwd).strip()
  except subprocess.CalledProcessError:
    email = ''
  if not email:
    print
    print 'No default email configured in git. Hint: '
    print '   $ git config --global user.email my@email.com'
  if not email.endswith('@google.com'):
    print
    print 'Master restart requires @google.com email.'
    print 'Currently configured git user is "%s <%s>"' % (name, email)
    prompt = 'Please provide username or full email in google.com domain'
    if '@' in email:
      default_email = email.split('@')[0] + '@google.com'
      prompt += ' [%s]: ' % default_email
    else:
      default_email = None
      prompt += ': '
    s = raw_input(prompt).strip()
    if '@' in s:
      email = s
    elif s:
      email = s + '@google.com'
    else:
      email = default_email
    if not email or not email.endswith('@google.com'):
      print 'no email provided or not a @google.com email'
      return False
    subprocess.call(['git', 'config', '--local', 'user.email', email], cwd=cwd)
  print
  print 'Configured git to use "%s <%s>" as author.' % (name, email)
  return True

def run(masters, masters_regex, restart_time, rolling, reviewers, bug, force,
        no_commit, desired_state, reason):
  """Schedules a restart of each master in <masters> and <masters_regex>.

  Args:
    masters - a list(str) of masters to restart
    masters_regex - a regex string of master names to restart
    restart_time - a datetime in UTC of when to restart them. If None, restart
                   at a predefined "end of day".
    rolling - delay (in mins) to add between restart time of each master
    reviewers - a list(str) of reviewers for the CL (may be empty)
    bug - an integer bug number to include in the review or None
    force - a bool which causes commit not to prompt if true
    no_commit - doesn't set the CQ bit on upload
    desired_state - nominally 'running', picks which desired_state
                    to put the buildbot in
    reason - a short message saying why the master is being restarted
  """

  # Step 1: Acquire a clean master state checkout.
  # This repo is too small to consider caching.
  with get_master_state_checkout() as master_state_dir:
    # Step 1.5: make sure email of committer is @google.com.
    if not _configure_git_name_and_email(master_state_dir):
      return 0

    # Step 2: Modify the master state json file.
    master_state_json = os.path.join(
        master_state_dir, 'desired_master_state.json')

    LOGGER.info('Reading %s' % master_state_json)
    with open(master_state_json, 'r') as f:
      desired_master_state = json.load(f)
    LOGGER.info('Loaded')

    # Validate the current master state file.
    try:
      desired_state_parser.validate_desired_master_state(desired_master_state)
    except desired_state_parser.InvalidDesiredMasterState:
      LOGGER.exception('Failed to validate current master state JSON.')
      return 1

    if masters_regex:
      masters.extend(get_master_names(desired_master_state,
                                      name_regex=masters_regex))

    masters = sorted(set(masters))

    if rolling:
      rolling_offsets = range(0, len(masters)*rolling, rolling)
      rolling_restarts = [restart_time + datetime.timedelta(minutes=offset)
                          for offset in rolling_offsets]
      masters = [get_restart_spec(master, time)
                 for master, time in zip(masters, rolling_restarts)]
    else:
      masters = [get_restart_spec(m, restart_time) for m in masters]

    # <masters> is now a list of <RestartSpec>s

    reason = reason.strip()
    if not reason:
      default_reason = ''
      if bug:
        default_reason = 'Restart for https://crbug.com/%s' % bug
      prompt = 'Please provide a reason for this restart'
      if default_reason:
        prompt += ' [%s]: ' % default_reason
      else:
        prompt += ': '
      reason = raw_input(prompt).strip()
      if not reason:
        if default_reason:
          reason = default_reason
        else:
          print 'No reason provided, exiting'
          return 0

    # Update desired_master_state according to list of RestartSpecs in <masters>
    master_states = desired_master_state.get('master_states', {})
    entries = 0
    for master in masters:
      if master.desired_state_name not in master_states:
        msg = '%s not found in master state' % master.desired_state_name
        LOGGER.error(msg)
        raise MasterNotFoundException(msg)

      master_states.setdefault(master.desired_state_name, []).append({
          'desired_state': desired_state,
          'transition_time_utc': zulu.to_zulu_string(master.restart_time),
      })
      entries += 1

    LOGGER.info('Writing back to JSON file, %d new entries' % (entries,))
    desired_state_parser.write_master_state(
        desired_master_state, master_state_json,
        prune_only_masters=set(m.desired_state_name for m in masters))

    # Step 3: Send the patch to Rietveld and commit it via the CQ.
    LOGGER.info('Committing back into repository')
    commit(master_state_dir, masters, reviewers, bug, force, no_commit,
           desired_state, reason)
