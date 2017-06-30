# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Sets up and starts a Chrome slave."""

import httplib
import httplib2
import json
import os
import sys
import tempfile
import zipfile

from oauth2client import gce

from .util import call, rmtree


IS_WINDOWS = sys.platform.startswith('win')


# This is built via https://build.chromium.org/p/chromium.infra/builders/
# depot_tools%20zip%20uploader
# We assume this is reasonably updated.
DEPOT_TOOLS_URL = (
    'https://storage.googleapis.com/chrome-infra/depot_tools.zip')
SLAVE_DEPS_URL = (
    'https://chrome-internal.googlesource.com/chrome/tools/build/slave.DEPS')
INTERNAL_DEPS_URL = (
    'https://chrome-internal.googlesource.com/chrome/tools/build/internal.DEPS')
GCLIENT_FILE = """
solutions = [
  {
    "name"        : "%s.DEPS",
    "url"         : "%s",
    "deps_file"   : ".DEPS.git",
    "managed"     : True,
  },
]
"""


# TODO(hinoka): Make this an infra virtualenv.  crbug.com/426099.
# Because of various issues (eg. pywin32 not installed in the infra virtualenv)
# We can't use the virtualenv for running buildbot :(.
if IS_WINDOWS:
  PYTHON = 'c:\\setup\\depot_tools\\python276_bin\\python.exe'
  GIT = 'C:\\setup\\depot_tools\\git.exe'
  GCLIENT_BIN = 'gclient.bat'
  TEMP_DEPOT_TOOLS = 'C:\\tmp\\depot_tools'
else:
  PYTHON = '/usr/bin/python'
  GIT = '/usr/bin/git'
  GCLIENT_BIN = 'gclient'
  TEMP_DEPOT_TOOLS = '/tmp/depot_tools'


# TODO(hinoka): Really, we only need this copy of depot_tools for gclient.
# fetching a gclient-only cipd package is going to be more lightweight.
def ensure_depot_tools():
  """Fetches depot_tools to temp dir to use it to fetch the gclient solution."""
  # We don't really want to trust that the existing version of depot_tools
  # is pristine and uncorrupted.  So delete it and re-clone.
  print 'Setting up depot_tools in %s' % TEMP_DEPOT_TOOLS
  rmtree(TEMP_DEPOT_TOOLS)
  parent = os.path.dirname(TEMP_DEPOT_TOOLS)
  if not os.path.exists(parent):
    os.makedirs(parent)
  tmpdir = tempfile.mkdtemp()
  tmpzip = os.path.join(tmpdir, 'depot_tools.zip')
  with open(tmpzip, 'wb') as f:
    http = httplib2.Http()
    response, content = http.request(DEPOT_TOOLS_URL, 'GET')
    if response['status'] != '200':
      # Request did not succeed. Try again.
      print 'response: %s' % response
      print 'content: %s' % content
      print 'Error fetching depot_tools.'
      raise httplib.HTTPException('HTTP status %s != 200' % response['status'])
    f.write(content)
  with zipfile.ZipFile(tmpzip, 'r') as f:
    f.extractall(TEMP_DEPOT_TOOLS)
  rmtree(tmpdir)
  return TEMP_DEPOT_TOOLS


def maybe_clean_rootdir(root_dir):
  """Clean out root_dir if the disk is over 90% full."""
  # TODO(hinoka): Windows support.
  if sys.platform.startswith('win'):
    return
  st = os.statvfs(root_dir)
  percent = st.f_bavail * 100 / st.f_blocks
  if percent > 10:
    return
  # else: Less than 10% disk free.  Delete everything in the root dir.
  print 'Free space less than 10%%, clearing out %s' % root_dir
  for dirname in os.listdir(root_dir):
    fullname = os.path.join(root_dir, dirname)
    print 'Deleting %s' % fullname
    rmtree(fullname)


def inject_path_in_environ(env, path):
  """Appends a directory to PATH env var if it's not there."""
  paths = env.get('PATH', '').split(os.pathsep)
  if path not in paths:
    paths.insert(0, path)
  env['PATH'] = os.pathsep.join(paths)
  return env


def write_gclient_file(root_dir, internal):
  gclient_file = os.path.join(root_dir, '.gclient')
  with open(gclient_file, 'wb') as f:
    f.write(
      GCLIENT_FILE % (('internal', INTERNAL_DEPS_URL) if internal
                      else ('slave', SLAVE_DEPS_URL)))


def ensure_checkout(root_dir, depot_tools, internal):
  """Ensure that /b/.gclient is correct and the build checkout is there."""
  gclient_bin = os.path.join(depot_tools, GCLIENT_BIN)
  env = inject_path_in_environ(os.environ.copy(), depot_tools)
  write_gclient_file(root_dir, internal)
  rc = call([gclient_bin, 'sync'], cwd=root_dir, env=env)
  if rc:
    print 'Gclient sync failed, cleaning and trying again'
    for filename in os.listdir(root_dir):
      full_path = os.path.join(root_dir, filename)
      print 'Deleting %s...' % full_path
      # shutil.rmtree doesn't work on Windows, but ours works.
      rmtree(full_path)
    write_gclient_file(root_dir, internal)
    rc = call([gclient_bin, 'sync'], cwd=root_dir, env=env)
    if rc:
      raise Exception('Could not ensure gclient file is correct.')


def seed_passwords(root_dir, password_file):
  bot_password_path = os.path.join(
      root_dir, 'build', 'site_config', '.bot_password')

  # Already there? Could be put by Puppet (and thus not overridable).
  if os.path.isfile(bot_password_path):
    return

  # Seed buildbot bot password.
  with open(password_file, 'r') as f:
    passwords = json.load(f)
  with open(bot_password_path, 'wb') as f:
    f.write(passwords['bot_password'])


def run_slave(root_dir, slave_name):
  slave_dir = os.path.join(root_dir, 'build', 'slave')
  shutdown_stamp = os.path.join(slave_dir, 'shutdown.stamp')
  if os.path.exists(shutdown_stamp):
    print 'Exiting due to shutdown stamp %s' % shutdown_stamp
    return
  run_slave_path = os.path.join(slave_dir, 'run_slave.py')
  twistd_pid_path = os.path.join(slave_dir, 'twistd.pid')
  env = inject_path_in_environ(
      os.environ.copy(), os.path.join(root_dir, 'depot_tools'))
  if not IS_WINDOWS:
    env['DISPLAY'] = ':0.0'
  env['LANG'] = 'en_US.UTF-8'
  if slave_name:
    # We do this on Windows because the hostname is incorrect.
    env['TESTING_SLAVENAME'] = slave_name

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
  cmd = [PYTHON, run_slave_path, '--no_save', '--no-gclient-sync',
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
      print 'response: %s' % response
      print 'content: %s' % content
      print 'Error requesting bot map.'
      raise httplib.HTTPException('HTTP status %s != 200' % response['status'])
    bot_entry = json.loads(content)
  except Exception as e:
    print 'Error requesting bot map. Host may be missing authentication.'
    print str(e)
    raise
  return bot_entry


def start(root_dir, depot_tools, password_file, slave_name):
  if not depot_tools:
    depot_tools = ensure_depot_tools()
  if IS_WINDOWS:
    # depot_tools msysgit can't find ~/.gitconfig unless we explicitly set HOME
    os.environ['HOME'] = '%s%s' % (
        os.environ.get('HOMEDRIVE'), os.environ.get('HOMEPATH'))
  maybe_clean_rootdir(root_dir)
  bot_entry = get_botmap_entry(slave_name)
  is_internal = bot_entry.get('internal', False)
  ensure_checkout(root_dir, depot_tools, is_internal)
  if password_file:
    seed_passwords(root_dir, password_file)
  run_slave(root_dir, slave_name)
