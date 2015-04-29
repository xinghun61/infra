# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Get information about a buildbot master and manipulate it."""


import errno
import os
import json
import re
import requests
import simplejson
import subprocess
import sys

from dateutil.parser import parse

from infra.libs.time_functions import timestamp

######## Getting information about the master.


# Derived from http://stackoverflow.com/a/6940314.
def _pid_is_alive(pid):  # pragma: no cover
  """Determine if the given pid is still running.
  
  Sending a signal of 0 (the 'null signal') does all the checks to send a signal
  without actually sending a signal. Thus it works as a check to see if the pid
  is valid. See http://goo.gl/6M1BoF for details.
  """
  if sys.platform.startswith('win'):
    raise NotImplementedError

  if pid <= 0:
    return False
  try:
    os.kill(pid, 0)
  except OSError as err:
    if err.errno == errno.ESRCH:
      return False
    elif err.errno == errno.EPERM:
      return True
    else:
      raise
  else:
    return True


def buildbot_is_running(directory):
  """Determine if the twisted.pid in a directory is running."""
  pidfile = os.path.join(directory, 'twistd.pid')
  if not os.path.exists(pidfile):
    return False
  with open(pidfile) as f:
    pid = int(f.read().strip())
  return _pid_is_alive(pid)


def _get_last_action(directory, action):
  """Get the last time the given action was run in the actions.log."""
  actions_log_file = os.path.join(directory, 'actions.log')
  if not os.path.exists(actions_log_file):
    return None
  with open(actions_log_file) as f:
    for line in reversed(list(f)):
      if action in line:
        unparsed_date = line.split(action)[0][len('**'):]
        return timestamp.utctimestamp(parse(unparsed_date))
  return None



def get_last_boot(directory):
  """Determine the last time the master was started."""
  return max(
      _get_last_action(directory, 'make restart'),
      _get_last_action(directory, 'make start'))


def get_last_no_new_builds(directory):
  """Determine the last time a *current* make no-new-builds was called.
  
  If a 'make start' or 'make restart' was issued after the no-new-builds, it is
  not valid (since the make start or make restart nullified the no-new-builds).
  """
  last_boot = get_last_boot(directory)
  last_no_new_builds = _get_last_action(directory, 'make no-new-builds')
  if not last_no_new_builds:
    return None
  if last_boot > last_no_new_builds:
    return None
  return last_no_new_builds


def _get_mastermap_data(directory):
  """Get mastermap JSON from a master directory."""

  build_dir = os.path.join(directory, os.pardir, os.pardir, os.pardir, 'build')
  runit = os.path.join(build_dir, 'scripts', 'tools', 'runit.py')
  build_internal_dir = os.path.join(build_dir, os.pardir, 'build_internal')

  script_path = os.path.join(build_dir, 'scripts', 'tools', 'mastermap.py')
  if os.path.exists(build_internal_dir):
    script_path = os.path.join(
         build_internal_dir, 'scripts', 'tools', 'mastermap_internal.py')

  script_data = json.loads(subprocess.check_output(
    [runit, script_path, '-f', 'json']))

  short_dirname = os.path.basename(directory)
  matches = [x for x in script_data if x.get('dirname') == short_dirname]
  assert len(matches) < 2, (
      'Multiple masters were found with the same master directory.')
  if matches:
    return matches[0]
  return None


def _get_master_web_port(directory):
  """Determine the web port of the master running in the given directory."""
  mastermap_data = _get_mastermap_data(directory)
  if mastermap_data:
    return mastermap_data['port']
  return None


def get_accepting_builds(directory, timeout=30):
  """Determine whether the master is accepting new builds or not.
  
  *** This only works for masters running on localhost.***
  """
  port = _get_master_web_port(directory)
  if port is not None:
    try:
      res = requests.get(
          'http://localhost:%d/json/accepting_builds' % port,
          timeout=timeout)
      if res.status_code == 200:
        try:
          return res.json().get('accepting_builds')
        except simplejson.scanner.JSONDecodeError:
          pass
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
      pass
  return None


######## Performing actions on the master.


GclientSync, MakeStop, MakeWait, MakeStart, MakeNoNewBuilds = range(5)


def convert_action_items_to_cli(
    action_items, directory, enable_gclient=False):

  def cmd_dict(cmd, lockfile_prefix):
    # Using the same lockfile prefix for two actions will make them mutually
    # exclusive. So setting 'make' for all the make commands tries to prevent
    # two make actions happening at once in the same master directory.
    lockfile = '%s_%s' % (
        lockfile_prefix,
        re.sub('[^\w]', '_', directory.lower()))
    return {
        'cwd': directory,
        'cmd': cmd,
        'lockfile': lockfile,
    }

  for action_item in action_items:
    if action_item == GclientSync:
      if enable_gclient:
        yield cmd_dict(
            ['gclient', 'sync', '--reset', '--force', '--auto_rebase'],
            'gclient')
    elif action_item == MakeStop:
      yield cmd_dict(['make', 'stop'], 'make')
    elif action_item == MakeWait:
      yield cmd_dict(['make', 'wait'], 'make')
    elif action_item == MakeStart:
      yield cmd_dict(['make', 'start'], 'make')
    elif action_item == MakeNoNewBuilds:
      yield cmd_dict(['make', 'no-new-builds'], 'make')
    else:
      raise ValueError('Invalid action item %s' % action_item)
