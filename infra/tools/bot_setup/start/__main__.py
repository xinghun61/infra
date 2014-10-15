# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Sets up and starts a Chrome slave."""

import argparse
import json
import os
import subprocess
import sys


SLAVE_DEPS_URL = (
    'https://chrome-internal.googlesource.com/chrome/tools/build/slave.DEPS')
GCLIENT_FILE = """
solutions = [
  { "name"        : "slave.DEPS",
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


def ensure_checkout(root_dir, gclient):
  """Ensure that /b/.gclient is correct and the build checkout is there."""
  gclient_file = os.path.join(root_dir, '.gclient')
  with open(gclient_file, 'wb') as f:
    f.write(GCLIENT_FILE)
  call([gclient, 'sync'], cwd=root_dir)


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
  env = os.environ.copy()
  env['DISPLAY'] = ':0.0'

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
  cmd = [sys.executable, run_slave_path, '--no_save',
         '--python', 'buildbot.tac', '--nodaemon', '--logfile', 'twistd.log']
  call(cmd, cwd=slave_dir, env=env)
  print 'run_slave.py died'


def parse_args():
  parser = argparse.ArgumentParser()
  parser.add_argument('-b', '--root_dir', default='/b')
  parser.add_argument('-d', '--depot_tools')
  parser.add_argument('-p', '--password_file')
  return parser.parse_args()


def main():
  args = parse_args()
  root_dir = args.root_dir
  gclient = os.path.join(args.depot_tools, 'gclient')
  password_file = args.password_file

  ensure_checkout(root_dir, gclient)
  if args.password_file:
    seed_passwords(root_dir, password_file)
  run_slave(root_dir)


if __name__ == '__main__':
  sys.exit(main())
