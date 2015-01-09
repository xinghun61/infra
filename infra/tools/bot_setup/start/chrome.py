# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Sets up and starts a Chrome slave."""

import httplib2
import json
import os
import shutil
import subprocess
import sys
import time

from oauth2client import gce

SLAVE_DEPS_URL = (
    'https://chrome-internal.googlesource.com/chrome/tools/build/slave.DEPS')
INTERNAL_DEPS_URL = (
    'https://chrome-internal.googlesource.com/chrome/tools/build/internal.DEPS')
GCLIENT_FILE = """
solutions = [
  { "name"        : "%s.DEPS",
    "url"         : "%s",
    "deps_file"   : ".DEPS.git",
  },
]
""" % SLAVE_DEPS_URL

# These are urls that we are seeding passwords to.
SVN_URLS = [
    'svn://svn-mirror.chromium.org/chrome-try'
    'svn://svn-mirror.golo.chromium.org/chrome'
    'svn://svn-mirror.golo.chromium.org/chrome-internal'
    'svn://svn.chromium.org/chrome'
    'svn://svn.chromium.org/chrome-internal'
    'svn://svn.chromium.org/chrome-try'
]

# BUG(hinoka): This is a temp fix for crbug.com/426081
# TODO(hinoka): Make this an infra virtualenv.  crbug.com/426099.
SYSTEM_PYTHON = '/usr/bin/python'


def call(args, **kwargs):
  print 'Running %s' % ' '.join(args)
  if kwargs.get('cwd'):
    print '  In %s' % kwargs.get('cwd')
  kwargs.setdefault('stdout', subprocess.PIPE)
  kwargs.setdefault('stderr', subprocess.STDOUT)
  proc = subprocess.Popen(args, **kwargs)
  while True:
    buf = proc.stdout.read(1)
    if not buf:
      break
    sys.stdout.write(buf)
  return proc.wait()


def write_gclient_file(root_dir, internal):
  gclient_file = os.path.join(root_dir, '.gclient')
  with open(gclient_file, 'wb') as f:
    f.write(
      GCLIENT_FILE % (('internal', INTERNAL_DEPS_URL) if internal
                      else ('slave', SLAVE_DEPS_URL)))


def ensure_checkout(root_dir, gclient, internal):
  """Ensure that /b/.gclient is correct and the build checkout is there."""
  write_gclient_file(root_dir, internal)
  rc = call([gclient, 'sync'], cwd=root_dir)
  if rc:
    print 'Gclient sync failed, cleaning and trying again'
    for filename in os.listdir(root_dir):
      full_path = os.path.join(root_dir, filename)
      print 'Deleting %s...' % full_path
      shutil.rmtree(full_path)
    write_gclient_file(root_dir, internal)
    rc = call([gclient, 'sync'], cwd=root_dir)
    if rc:
      raise Exception('Could not ensure gclient file is correct.')


def seed_passwords(root_dir, password_file):
  with open(password_file, 'r') as f:
    passwords = json.load(f)
  for var in ['svn_user', 'svn_password', 'bot_password']:
    assert var in passwords

  # Seed SVN passwords.
  svn_user = passwords['svn_user']
  svn_password = passwords['svn_password']
  for svn_url in SVN_URLS:
    # Use subprocess.call() so that the password doesn't get printed.
    subprocess.call(
        ['svn', 'info', svn_url, '--username', svn_user,
         '--password', svn_password])

  # Seed buildbot bot password.
  bot_password_path = os.path.join(
      root_dir, 'build', 'site_config', '.bot_password')
  with open(bot_password_path, 'wb') as f:
    f.write(passwords['bot_password'])


def run_slave(root_dir):
  slave_dir = os.path.join(root_dir, 'build', 'slave')
  run_slave_path = os.path.join(slave_dir, 'run_slave.py')
  twistd_pid_path = os.path.join(slave_dir, 'twistd.pid')
  env = os.environ.copy()
  env['DISPLAY'] = ':0.0'
  env['LANG'] = 'en_US.UTF-8'

  # Clean up the PID file.
  try:
    os.remove(twistd_pid_path)
  except OSError:
    pass
  else:
    print 'Removed stale pid file %s' % twistd_pid_path

  # Observant infra members will notice that we are not using "make start" to
  # start the run_slave.py process.  We use make start for a couple of reasons:
  #   1. Its a convenient way for a developer to start the process manually
  #      and daemonize the process.
  #   2. It runs ulimit -s 8192 to fix any stack size weirdness.
  # However, in in our fleet:
  #   1. We want all build scripts to be a child of chromebuild-startup.py.
  #      Daemonizing is not a priority.
  #   2. The limits are already set in /etc/security/limits.conf.
  # This is why we can explicitly call run_slave.py
  cmd = [SYSTEM_PYTHON, run_slave_path, '--no_save',
         '--python', 'buildbot.tac', '--nodaemon', '--logfile', 'twistd.log']
  call(cmd, cwd=slave_dir, env=env)
  print 'run_slave.py died'


def get_botmap_entry(slave_name):
  credentials = gce.AppAssertionCredentials(
      scope='https://www.googleapis.com/auth/userinfo.email')
  http = credentials.authorize(httplib2.Http())
  botmap = ('https://chrome-infra-botmap.appspot.com/_ah/api/botmap/v1/bots/'
            '%s' % slave_name)
  try:
    response, content = http.request(botmap)
    if response['status'] != '200':
      # Request did not succeed. Try again.
      response, content = http.request(botmap)
      if response['status'] != '200':
        raise Exception
    bot_entry = json.loads(content)
  except Exception:
    print 'Error requesting bot map. Host may be missing authentication.'
    return None
  return bot_entry


def start(root_dir, depot_tools, password_file, slave_name):
  gclient = os.path.join(depot_tools, 'gclient')
  bot_entry = get_botmap_entry(slave_name)
  is_internal = bot_entry.get('internal', False)
  ensure_checkout(root_dir, gclient, is_internal)
  if password_file:
    seed_passwords(root_dir, password_file)
  run_slave(root_dir)
