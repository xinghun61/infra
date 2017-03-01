#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import logging
import os
import platform
import subprocess
import sys
import tempfile


# The path to the "infra/bootstrap/" directory.
BOOTSTRAP_DIR = os.path.dirname(os.path.abspath(__file__))
# The path to the "infra/" directory.
ROOT = os.path.dirname(BOOTSTRAP_DIR)
# The path where CIPD install lists are stored.
CIPD_LIST_DIR = os.path.join(BOOTSTRAP_DIR, 'cipd')
# Default sysroot install root.
DEFAULT_INSTALL_ROOT = os.path.join(ROOT, 'cipd')
# Default CIPD server url
DEFAULT_SERVER_URL='https://chrome-infra-packages.appspot.com'


# function to find the cipd binary. On POSIX this is simple ('cipd'!), but
# for windows this is more complex. depot_tools exposes this as a .bat, but
# buildbot and swarming expose it as an exe. So we have to look for it.
if sys.platform == 'win32':
  def cipd_binary():
    for p in os.environ.get('PATH', '').split(os.pathsep):
      base = os.path.join(p, 'cipd')
      for ext in ('.exe', '.bat'):
        candidate = base+ext
        if os.path.isfile(candidate):
          return candidate
    # if we didn't find it, guess 'cipd.exe'
    return 'cipd.exe'
else:
  def cipd_binary():
    return 'cipd'


# Map of CIPD configuration based on the current architecture/platform. If a
# platform is not listed here, the bootstrap will be a no-op.
#
# This is keyed on the platform's (system, machine).
ARCH_CONFIG_MAP = {
  ('Linux', 'x86_64'): {
    'cipd_install_list': 'cipd_linux_amd64.txt',
  },
  ('Linux', 'x86'): {
    'cipd_install_list': None,
  },
  ('Darwin', 'x86_64'): {
    'cipd_install_list': 'cipd_mac_amd64.txt',
  },
  ('Windows', 'x86_64'): {
    'cipd_install_list': None,
  },
  ('Windows', 'x86'): {
    'cipd_install_list': None,
  },
}


def get_platform_config():
  key = get_platform()
  return key, ARCH_CONFIG_MAP.get(key)


def get_platform():
  machine = platform.machine().lower()
  system = platform.system()
  machine = ({
    'amd64': 'x86_64',
    'i686': 'x86',
  }).get(machine, machine)
  if (machine == 'x86_64' and system == 'Linux' and
      sys.maxsize == (2 ** 31) - 1):
    # This is 32bit python on 64bit CPU on linux, which probably means the
    # entire userland is 32bit and thus we should play along and install 32bit
    # packages.
    machine = 'x86'
  return system, machine


def ensure_directory(path):
  # Ensure the parent directory exists.
  if os.path.isdir(path):
    return
  if os.path.exists(path):
    raise ValueError("Target file's directory [%s] exists, but is not a "
                     "directory." % (path,))
  logging.debug('Creating directory: [%s]', path)
  os.makedirs(path)


def execute(*cmd):
  if not logging.getLogger().isEnabledFor(logging.DEBUG):
    code = subprocess.call(cmd)
  else:
    # Execute the process, passing STDOUT/STDERR through our logger.
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    for line in proc.stdout:
      logging.debug('%s: %s', cmd[0], line.rstrip())
    code = proc.wait()
  if code:
    logging.error('Process failed with exit code: %d', code)
  return code


class CipdError(Exception):
  """Raised by install_cipd_client on fatal error."""


def cipd_ensure(root, ensure_file, cipd_backend_url=None):
  """Invoke `cipd ensure` with the provided ensure_file in the given root.

  Args:
    ensure_file (str) - file containing the packages to ensure
    root (str) - directory to ensure packages in. Will be created if doesn't
      exist.
  """
  cipd_backend_url = cipd_backend_url or DEFAULT_SERVER_URL

  assert os.path.isfile(ensure_file)
  ensure_directory(root)
  logging.debug('Installing CIPD packages from [%s] to [%s]', ensure_file, root)
  args = [
    'ensure',
    '-ensure-file', ensure_file,
    '-root', root,
    '-service-url', cipd_backend_url
  ]
  if execute(cipd_binary(), *args):
    raise CipdError('Failed to execute CIPD client: %s', ' '.join(args))


def cipd_ensure_list(root, ensure_data, cipd_backend_url=None):
  """Invoke `cipd ensure` with the provided ensure_data in the given root.

  Args:
    ensure_data (list(tuple)) - a list of (package_pattern, version). The
      package_patterns may contain the ${platform} and ${arch} directives
      as defined by the cipd client.
    root (str) - directory to ensure packages in
  """
  with tempfile.NamedTemporaryFile(prefix="cipd_ensure", delete=False) as tf:
    for item in ensure_data:
      print >> tf, "%s %s" % item
  try:
    cipd_ensure(root, tf.name, cipd_backend_url)
  finally:
    try:
      os.remove(tf.name)
    except OSError:
      logging.exception("failed to remove tempfile %r", tf.name)


def main(argv):
  parser = argparse.ArgumentParser('Installs CIPD bootstrap packages.')
  parser.add_argument('-v', '--verbose', action='count', default=0,
      help='Increase logging verbosity. Can be specified multiple times.')
  parser.add_argument('--cipd-backend-url', metavar='URL',
      help='Specify the CIPD backend URL (default is %(default)s)')
  parser.add_argument('-d', '--cipd-root-dir', metavar='PATH',
      default=DEFAULT_INSTALL_ROOT,
      help='Specify the root CIPD package installation directory.')

  opts = parser.parse_args(argv)

  # Setup logging verbosity.
  if opts.verbose == 0:
    level = logging.WARNING
  elif opts.verbose == 1:
    level = logging.INFO
  else:
    level = logging.DEBUG
  logging.getLogger().setLevel(level)

  root = os.path.abspath(opts.cipd_root_dir)

  # 2017/02/15 we used to bootstrap the cipd client into <infra.git>/cipd. This
  # deletes it, if it's there. This is important because otherwise the stale
  # client will end up at the front of $PATH and get used instead of the correct
  # one (i.e. the one that depot_tools / swarming / buildbot put there).
  try:
    EXE_SFX = '.exe' if sys.platform == 'win32' else ''
    os.remove(os.path.join(root, 'cipd'+EXE_SFX))
  except OSError:
    pass

  platform_key, config = get_platform_config()
  if not config:
    logging.info('No bootstrap configuration for platform [%s].', platform_key)
    return 0

  # Install the CIPD list for this configuration.
  cipd_install_list = config.get('cipd_install_list')
  if cipd_install_list:
    cipd_ensure(root,
                os.path.join(CIPD_LIST_DIR, cipd_install_list),
                opts.cipd_backend_url)
  return 0


if __name__ == '__main__':
  logging.basicConfig()
  logging.getLogger().setLevel(logging.INFO)
  sys.exit(main(sys.argv[1:]))
