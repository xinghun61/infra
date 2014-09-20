#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Prepares a local hermetic Go installation.

- Downloads and unpacks the Go toolset in ../../golang.
- Downloads and installs goop.
- Fetches code dependencies via goop.
"""

import contextlib
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib
import zipfile


LOGGER = logging.getLogger(__name__)


# /path/to/infra
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Where to install Go toolset to. GOROOT would be <TOOLSET_ROOT>/go.
TOOLSET_ROOT = os.path.abspath(os.path.join(os.path.dirname(ROOT), 'golang'))

# Default workspace with infra go code.
WORKSPACE = os.path.join(ROOT, 'go')

# Platform depended suffix for executable files.
EXE_SFX = '.exe' if sys.platform == 'win32' else ''

# Pinned version of Go toolset to download.
TOOLSET_VERSION = 'go1.3.1'

# Platform dependent portion of a download URL. See http://golang.org/dl/.
TOOLSET_VARIANTS = {
  ('darwin', 'x86-32'): 'darwin-386-osx10.8.tar.gz',
  ('darwin', 'x86-64'): 'darwin-amd64-osx10.8.tar.gz',
  ('linux2', 'x86-32'): 'linux-386.tar.gz',
  ('linux2', 'x86-64'): 'linux-amd64.tar.gz',
  ('win32', 'x86-32'): 'windows-386.zip',
  ('win32', 'x86-64'): 'windows-amd64.zip',
}

# Download URL root.
DOWNLOAD_URL_PREFIX = 'https://storage.googleapis.com/golang'

# Describes how to fetch 'goop' tool, with dependencies.
GOOP_SOURCE = {
  'src/code.google.com/p/go.tools': {
    'url': (
      'https://chromium.googlesource.com/infra/third_party/go/'
      'code.google.com/p/go.tools'
    ),
    'rev': '769e3df57984a798ef0b939485db1d954122c130',
  },
  'src/github.com/nitrous-io/goop': {
    'url': (
      'https://chromium.googlesource.com/infra/third_party/go/'
      'github.com/nitrous-io/goop'
    ),
    'rev': 'a42caf29ee8bf072e981fde447c9348635429ef7',
  },
}


class Failure(Exception):
  """Bootstrap failed."""


def get_toolset_url():
  """URL of a platform specific Go toolset archive."""
  # TODO(vadimsh): Support toolset for cross-compilation.
  arch = {
    'amd64': 'x86-64',
    'x86_64': 'x86-64',
    'i386': 'x86-32',
    'x86': 'x86-32',
  }.get(platform.machine().lower())
  variant = TOOLSET_VARIANTS.get((sys.platform, arch))
  if not variant:
    # TODO(vadimsh): Compile go lang from source.
    raise Failure('Unrecognized platform')
  return '%s/%s.%s' % (DOWNLOAD_URL_PREFIX, TOOLSET_VERSION, variant)


def read_file(path):
  """Returns contents of a given file or None if not readable."""
  assert isinstance(path, (list, tuple))
  try:
    with open(os.path.join(*path), 'rt') as f:
      return f.read()
  except IOError:
    return None


def write_file(path, data):
  """Writes |data| to a file."""
  assert isinstance(path, (list, tuple))
  with open(os.path.join(*path), 'wt') as f:
    f.write(data)


def remove_directory(path):
  """Recursively removes a directory."""
  assert isinstance(path, (list, tuple))
  p = os.path.join(*path)
  if os.path.exists(p):
    LOGGER.info('Removing %s', p)
    shutil.rmtree(p)


def install_toolset(toolset_root, url):
  """Downloads and installs Go toolset.

  GOROOT would be <toolset_root>/go/.
  """
  if not os.path.exists(toolset_root):
    os.makedirs(toolset_root)
  pkg_path = os.path.join(toolset_root, url[url.rfind('/')+1:])

  LOGGER.info('Downloading %s...', url)
  download_file(url, pkg_path)

  LOGGER.info('Extracting...')
  if pkg_path.endswith('.zip'):
    with zipfile.ZipFile(pkg_path, 'r') as f:
      f.extractall(toolset_root)
  elif pkg_path.endswith('.tar.gz'):
    with tarfile.open(pkg_path, 'r:gz') as f:
      f.extractall(toolset_root)
  else:
    raise Failure('Unrecognized archive format')

  LOGGER.info('Validating...')
  if not check_hello_world(toolset_root):
    raise Failure('Something is not right, test program doesn\'t work')


def download_file(url, path):
  """Fetches |url| to |path|."""
  last_progress = [0]
  def report(a, b, c):
    progress = int(a * b * 100.0 / c)
    if progress != last_progress[0]:
      print >> sys.stderr, 'Downloading... %d%%' % progress
      last_progress[0] = progress
  # TODO(vadimsh): Use something less crippled, something that validates SSL.
  urllib.urlretrieve(url, path, reporthook=report)


@contextlib.contextmanager
def temp_dir(path):
  """Creates a temporary directory, then deletes it."""
  tmp = tempfile.mkdtemp(dir=path)
  try:
    yield tmp
  finally:
    shutil.rmtree(tmp)


def check_hello_world(toolset_root):
  """Compiles and runs 'hello world' program to verify that toolset works."""
  with temp_dir(toolset_root) as tmp:
    path = os.path.join(tmp, 'hello.go')
    write_file([path], r"""
        package main
        func main() { println("hello, world\n") }
    """)
    out = subprocess.check_output(
        [get_go_exe(toolset_root), 'run', path],
        env=get_go_environ(toolset_root, tmp, [], []),
        stderr=subprocess.STDOUT)
    if out.strip() != 'hello, world':
      LOGGER.error('Failed to run sample program:\n%s', out)
      return False
    return True


def ensure_toolset_installed(toolset_root):
  """Installs or updates Go toolset if necessary."""
  installed = read_file([toolset_root, 'INSTALLED_TOOLSET'])
  available = get_toolset_url()
  if installed == available:
    LOGGER.debug('Go toolset is up-to-date: %s', TOOLSET_VERSION)
    return

  LOGGER.info('Installing Go toolset.')
  LOGGER.info('  Old toolset is %s', installed)
  LOGGER.info('  New toolset is %s', available)
  remove_directory([toolset_root])
  install_toolset(toolset_root, available)
  LOGGER.info('Go toolset installed: %s', TOOLSET_VERSION)
  write_file([toolset_root, 'INSTALLED_TOOLSET'], available)


def ensure_goop_installed(toolset_root):
  """Installs or updates 'goop' tool."""
  installed_goop = read_file([toolset_root, 'INSTALLED_GOOP'])
  available_goop = json.dumps(GOOP_SOURCE, sort_keys=True)
  if installed_goop == available_goop:
    LOGGER.debug('goop tool is up-to-date')
    return

  LOGGER.info('Installing goop...')
  with temp_dir(toolset_root) as tmp:
    fetch_goop_code(tmp, GOOP_SOURCE)
    subprocess.check_call(
        [get_go_exe(toolset_root), 'install', 'github.com/nitrous-io/goop'],
        cwd=tmp,
        env=get_go_environ(toolset_root, tmp, [], []),
        stdout=sys.stderr)
    os.rename(
        os.path.join(tmp, 'bin', 'goop' + EXE_SFX),
        os.path.join(toolset_root, 'go', 'bin', 'goop' + EXE_SFX))

  LOGGER.info('goop tool is installed')
  write_file([toolset_root, 'INSTALLED_GOOP'], available_goop)


def fetch_goop_code(workspace, spec):
  """Fetches Goop source code with dependencies."""
  def git(cmd, cwd):
    subprocess.check_call(['git'] + cmd, cwd=cwd, stdout=sys.stderr)
  for path, repo in sorted(spec.iteritems()):
    path = os.path.join(workspace, path.replace('/', os.sep))
    os.makedirs(path)
    git(['init', '.'], cwd=path)
    git(['fetch', repo['url'], repo['rev']], cwd=path)
    git(['checkout', 'FETCH_HEAD'], cwd=path)


def update_vendor_packages(toolset_root, workspace):
  """Runs goop to update external pinned packages."""
  installed = read_file([workspace, '.vendor', 'Goopfile.lock'])
  required = read_file([workspace, 'Goopfile.lock'])
  if installed == required:
    LOGGER.debug('Third party dependencies in %s are up-to-date', workspace)
    return

  LOGGER.info('Updating third party dependencies in %s...', workspace)
  remove_directory([workspace, '.vendor'])
  ret_code = call_go_tool(
      toolset_root=toolset_root,
      workspace=workspace,
      go_paths=[],
      vendor_paths=[],
      tool='goop',
      args=['install'],
      cwd=workspace,
      stdout=sys.stderr)
  if ret_code:
    raise Failure('Failed to fetch third party dependencies')
  write_file([workspace, '.vendor', 'Goopfile.lock'], required)


def get_go_environ(toolset_root, workspace, go_paths, vendor_paths):
  """Returns a copy of os.environ with added GO* environment variables.

  Overrides GOROOT, GOPATH and GOBIN. Keeps everything else. Idempotent.

  Args:
    toolset_root: GOROOT would be <toolset_root>/go.
    workspace: main workspace directory.
    go_paths: additional paths to add to GOPATH.
    vendor_paths: directories with .vendor files (created by goop).
  """
  env = os.environ.copy()
  env['GOROOT'] = os.path.join(toolset_root, 'go')
  env['GOBIN'] = os.path.join(workspace, 'bin')

  all_go_paths = [os.path.join(p, '.vendor') for p in vendor_paths]
  all_go_paths.extend(go_paths)
  all_go_paths.append(workspace)
  env['GOPATH'] = os.pathsep.join(all_go_paths)

  # Remove preexisting bin/ paths (including .vendor/bin) pointing to infra
  # or infra_internal Go workspaces. It's important when switching from
  # infra_internal to infra environments: infra_internal bin paths should
  # be removed.
  path = env['PATH'].split(os.pathsep)
  def should_keep(p):
    # TODO(vadimsh): This code knows about gclient checkout layout.
    gclient_root = os.path.dirname(ROOT)
    for d in ['infra', 'infra_internal']:
      if p.startswith(os.path.join(gclient_root, d, 'go')):
        return False
    return True
  path = filter(should_keep, path)

  # Make sure not to add duplicates entries to PATH over and over again when
  # get_go_environ is invoked multiple times.
  def add_path(p):
    if p not in path:
      path.insert(0, p)
  add_path(os.path.join(env['GOROOT'], 'bin'))
  add_path(env['GOBIN'])
  for p in vendor_paths:
    add_path(os.path.join(p, '.vendor', 'bin'))

  env['PATH'] = os.pathsep.join(path)
  return env


def get_go_exe(toolset_root):
  """Returns path to go executable."""
  return os.path.join(toolset_root, 'go', 'bin', 'go' + EXE_SFX)


def call_go_tool(
    toolset_root, workspace, go_paths, vendor_paths, tool, args, **kwargs):
  """Setups environ and invokes some GOROOT/bin/* tool."""
  cmd = [os.path.join(toolset_root, 'go', 'bin', tool + EXE_SFX)] + args
  LOGGER.debug('%s', ' '.join(cmd))
  return subprocess.call(
      cmd,
      env=get_go_environ(toolset_root, workspace, go_paths, vendor_paths),
      **kwargs)


def bootstrap(vendor_paths, logging_level):
  """Installs all dependencies in default locations.

  Supposed to be called at the beginning of some script (it modifies logger).

  Args:
    vendor_paths: list of paths to search for Goopfile.lock, for each path goop
        will install all dependencies in <path>/.vendor.
    logging_level: logging level of bootstrap process.
  """
  logging.basicConfig()
  LOGGER.setLevel(logging_level)
  ensure_toolset_installed(TOOLSET_ROOT)
  ensure_goop_installed(TOOLSET_ROOT)
  for p in vendor_paths:
    update_vendor_packages(TOOLSET_ROOT, p)


def prepare_go_environ():
  """Returns dict with environment variables to set to use Go toolset.

  Installs or updates the toolset if necessary.
  """
  bootstrap([WORKSPACE], logging.INFO)
  return get_go_environ(TOOLSET_ROOT, WORKSPACE, [], [WORKSPACE])


def main(args):
  if args:
    print >> sys.stderr, sys.modules[__name__].__doc__,
    return 2
  bootstrap([WORKSPACE], logging.DEBUG)
  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
