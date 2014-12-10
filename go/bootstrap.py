#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Prepares a local hermetic Go installation.

- Downloads and unpacks the Go toolset in ../../golang.
- Downloads and installs goop and golint.
- Fetches code dependencies via goop.
"""

import contextlib
import json
import logging
import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib
import zipfile

# TODO(vadimsh): Migrate to new golang.org/x/ paths once Golang moves to
# git completely.

LOGGER = logging.getLogger(__name__)


# /path/to/infra
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Where to install Go toolset to. GOROOT would be <TOOLSET_ROOT>/go.
TOOLSET_ROOT = os.path.join(os.path.dirname(ROOT), 'golang')

# Default workspace with infra go code.
WORKSPACE = os.path.join(ROOT, 'go')

# Platform depended suffix for executable files.
EXE_SFX = '.exe' if sys.platform == 'win32' else ''

# Pinned version of Go toolset to download.
TOOLSET_VERSION = 'go1.3.3'

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

# Describes how to fetch 'goop' and 'golint' tools, with dependencies. In theory
# it is possible to fetch golint via goop, but in practice it's not worth it:
# a second copy of go.tools will be fetched, along with _ALL_ dependencies
# (not only ones needed by golint), e.g. go.net and google-api-go-client. Tons
# of unnecessary code that is difficult to mirror to our git repos (since it is
# hosted in Hg currently). Also revisions of go.tools repo in TOOLS_SOURCE and
# Goopfile.lock would have to be kept in sync.
TOOLS_SOURCE = {
  'src/code.google.com/p/go.tools': {
    'url': (
      'https://chromium.googlesource.com/infra/third_party/go/'
      'code.google.com/p/go.tools'
    ),
    'ref': 'refs/heads/master',
    'rev': '769e3df57984a798ef0b939485db1d954122c130',
  },
  'src/github.com/nitrous-io/goop': {
    'url': (
      'https://chromium.googlesource.com/infra/third_party/go/'
      'github.com/nitrous-io/goop'
    ),
    'ref': 'refs/heads/chromium',
    'rev': 'a42caf29ee8bf072e981fde447c9348635429ef7',
  },
  'src/github.com/golang/lint': {
    'url': (
        'https://chromium.googlesource.com/external/'
        'github.com/golang/lint.git'
    ),
    'ref': 'refs/heads/master',
    'rev': '8ca23475bcb43213a55dd8210b69363f6b0e09c1',
  },
}

# The set of directories to copy from the go_appengine SDK's goroot into our
# toolchain's root. See patch_appengine_sdk for more details.
GAE_DIRS = frozenset(('appengine', 'appengine_internal', 'code.google.com'))


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
    with open(os.path.join(*path), 'r') as f:
      return f.read()
  except IOError:
    return None


def write_file(path, data):
  """Writes |data| to a file."""
  assert isinstance(path, (list, tuple))
  with open(os.path.join(*path), 'w') as f:
    f.write(data)


def remove_directory(path):
  """Recursively removes a directory."""
  assert isinstance(path, (list, tuple))
  p = os.path.join(*path)
  if not os.path.exists(p):
    return
  LOGGER.info('Removing %s', p)
  # Crutch to remove read-only file (.git/* in particular) on Windows.
  def onerror(func, path, _exc_info):
    if not os.access(path, os.W_OK):
      os.chmod(path, stat.S_IWUSR)
      func(path)
    else:
      raise
  shutil.rmtree(p, onerror=onerror if sys.platform == 'win32' else None)


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
    remove_directory([tmp])


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


def maybe_patch_appengine_sdk(toolset_root):
  """Copies GAE_DIRS dirs into toolset_root.

  This is necessary to convince go-get/goop to consider the appengine code as
  'system' level. Otherwise simply putting them on GOPATH would have been
  sufficient.

  If Appengine SDK provides a better way to play nice in the go ecosystem at
  some point, we should probably do that instead.
  """
  go_appengine = os.path.join(os.path.dirname(ROOT), 'go_appengine')
  if not os.path.exists(go_appengine):
    raise Failure(
      '%s SDK not present... did you `gclient runhooks`?' % go_appengine)

  sdk_version = read_file([go_appengine, 'VERSION'])
  patched_version = read_file([toolset_root, 'INSTALLED_GAE_SDK'])

  new = None if sdk_version is None else sdk_version.splitlines()[0]
  old = None if patched_version is None else patched_version.splitlines()[0]

  if sdk_version == patched_version:  # compares whole VERSION because why not?
    LOGGER.debug('Appengine code patch up-to-date: %s', old)
    return False
  else:
    LOGGER.info('Patching Appengine code into Go toolset:')
    LOGGER.info('  Old Appengine version is %s', old)
    LOGGER.info('  New Appengine version is %s', new)

    for d in GAE_DIRS:
      sdk_dir = os.path.join(go_appengine, 'goroot', 'src', 'pkg', d)
      tool_dir = os.path.join(toolset_root, 'go', 'src', 'pkg', d)
      remove_directory([tool_dir])
      LOGGER.info('Copying %s -> %s', sdk_dir, tool_dir)
      shutil.copytree(sdk_dir, tool_dir)

    write_file([toolset_root, 'INSTALLED_GAE_SDK'], sdk_version)
    return True


def ensure_toolset_installed(toolset_root):
  """Installs or updates Go toolset if necessary.

  Returns True if new toolset was installed.
  """
  installed = read_file([toolset_root, 'INSTALLED_TOOLSET'])
  available = get_toolset_url()
  if installed == available:
    if maybe_patch_appengine_sdk(toolset_root):
      return True
    LOGGER.debug('Go toolset is up-to-date: %s', TOOLSET_VERSION)
    return False

  LOGGER.info('Installing Go toolset.')
  LOGGER.info('  Old toolset is %s', installed)
  LOGGER.info('  New toolset is %s', available)
  remove_directory([toolset_root])
  install_toolset(toolset_root, available)
  maybe_patch_appengine_sdk(toolset_root)
  LOGGER.info('Go toolset installed: %s', TOOLSET_VERSION)
  write_file([toolset_root, 'INSTALLED_TOOLSET'], available)
  return True


def ensure_tools_installed(toolset_root):
  """Installs or updates 'goop' and 'golint' tools."""
  installed_tools = read_file([toolset_root, 'INSTALLED_TOOLS'])
  available_tools = json.dumps(TOOLS_SOURCE, sort_keys=True)
  if installed_tools == available_tools:
    LOGGER.debug('tools are up-to-date')
    return

  def install(workspace, pkg):
    subprocess.check_call(
        [get_go_exe(toolset_root), 'install', pkg],
        cwd=tmp,
        env=get_go_environ(toolset_root, workspace, [], []),
        stdout=sys.stderr)
    # Windows os.rename doesn't support overwrites.
    name = pkg[pkg.rfind('/')+1:]
    dest = os.path.join(toolset_root, 'go', 'bin', name + EXE_SFX)
    if os.path.exists(dest):
      os.remove(dest)
    os.rename(os.path.join(workspace, 'bin', name + EXE_SFX), dest)

  LOGGER.info('Installing tools...')
  with temp_dir(toolset_root) as tmp:
    fetch_tools_code(tmp, TOOLS_SOURCE)
    install(tmp, 'github.com/nitrous-io/goop')
    install(tmp, 'github.com/golang/lint/golint')

  LOGGER.info('tools are installed')
  write_file([toolset_root, 'INSTALLED_TOOLS'], available_tools)


def fetch_tools_code(workspace, spec):
  """Fetches goop and golint source code with dependencies."""
  git_exe = 'git.bat' if sys.platform == 'win32' else 'git'
  def git(cmd, cwd):
    subprocess.check_call([git_exe] + cmd, cwd=cwd, stdout=sys.stderr)
  for path, repo in sorted(spec.iteritems()):
    path = os.path.join(workspace, path.replace('/', os.sep))
    os.makedirs(path)
    git(['init', '.'], cwd=path)
    git(['fetch', repo['url'], repo['ref']], cwd=path)
    git(['checkout', repo['rev']], cwd=path)


def update_vendor_packages(toolset_root, workspace, force=False):
  """Runs goop to update external pinned packages."""
  required = read_file([workspace, 'Goopfile.lock'])
  if not force:
    installed = read_file([workspace, '.vendor', 'Goopfile.lock'])
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
  updated = ensure_toolset_installed(TOOLSET_ROOT)
  ensure_tools_installed(TOOLSET_ROOT)
  for p in vendor_paths:
    update_vendor_packages(TOOLSET_ROOT, p, force=updated)


def prepare_go_environ(skip_goop_update=False):
  """Returns dict with environment variables to set to use Go toolset.

  Installs or updates the toolset if necessary.
  """
  vendor_paths = [] if skip_goop_update else [WORKSPACE]
  bootstrap(vendor_paths, logging.INFO)
  return get_go_environ(TOOLSET_ROOT, WORKSPACE, [], vendor_paths)


def find_executable(name, workspaces):
  """Returns full path to an executable in some bin/ (in GOROOT or GOBIN)."""
  basename = name
  if EXE_SFX and basename.endswith(EXE_SFX):
    basename = basename[:-len(EXE_SFX)]
  roots = [os.path.join(TOOLSET_ROOT, 'go', 'bin')]
  for path in workspaces:
    roots.extend([
      os.path.join(path, '.vendor', 'bin'),
      os.path.join(path, 'bin'),
    ])
  for root in roots:
    full_path = os.path.join(root, basename + EXE_SFX)
    if os.path.exists(full_path):
      return full_path
  return name


def main(args):
  if args:
    print >> sys.stderr, sys.modules[__name__].__doc__,
    return 2
  bootstrap([WORKSPACE], logging.DEBUG)
  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
