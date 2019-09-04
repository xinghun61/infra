#!/usr/bin/env vpython
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Prepares a local hermetic Go installation.

- Downloads and unpacks the Go toolset in ../../golang.
- Downloads and installs Glide (used by deps.py).
- Fetches code dependencies via deps.py.
"""

import argparse
import collections
import contextlib
import json
import logging
import os
import shutil
import stat
import subprocess
import sys
import tempfile


LOGGER = logging.getLogger(__name__)


# /path/to/infra
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Directory with .gclient file.
GCLIENT_ROOT = os.path.dirname(ROOT)

# The current overarching Infra version. If this changes, everything will be
# updated regardless of its version.
INFRA_VERSION = 1

# Where to install Go toolset to. GOROOT would be <TOOLSET_ROOT>/go.
TOOLSET_ROOT = os.path.join(os.path.dirname(ROOT), 'golang')

# Default workspace with infra go code.
WORKSPACE = os.path.join(ROOT, 'go')

# Platform depended suffix for executable files.
EXE_SFX = '.exe' if sys.platform == 'win32' else ''

# On Windows we use git from depot_tools.
GIT_EXE = 'git.bat' if sys.platform == 'win32' else 'git'

# Version of Go toolset CIPD package (infra/go/${platform}) to install.
TOOLSET_VERSION = '1.13'

# Describes how to fetch 'glide'.
GLIDE_SOURCE = {
  'src/github.com/Masterminds/glide': {
    'url': (
        'https://chromium.googlesource.com/external/github.com/'
        'Masterminds/glide.git'),
    'rev': 'refs/tags/v0.13.2',
  },
}

# Layout is the layout of the bootstrap installation.
_Layout = collections.namedtuple('Layout', (
    # The path where the Go toolset is checked out at.
    'toolset_root',

    # The workspace path.
    'workspace',

    # The list of vendor directories. Each will have a Glide "deps.yaml" in it.
    'vendor_paths',

    # List of paths to append to GOPATH (in additional to `workspace`).
    'go_paths',

    # The list of DEPS'd in paths that contain Go sources. This is used to
    # determine when our vendored tools need to be re-installed.
    'go_deps_paths',

    # Go package paths of tools to install into the bootstrap environment.
    'go_install_tools',
))

class Layout(_Layout):

  @property
  def go_repo_versions_path(self):
    """The path where the latest installed Go repository versions are recorded.
    """
    return os.path.join(self.workspace, '.deps_repo_versions.json')


# A base empty Layout.
_EMPTY_LAYOUT = Layout(
    toolset_root=None,
    workspace=None,
    vendor_paths=None,
    go_paths=None,
    go_deps_paths=None,
    go_install_tools=None)


# Infra standard layout.
LAYOUT = Layout(
    toolset_root=TOOLSET_ROOT,
    workspace=WORKSPACE,
    vendor_paths=[WORKSPACE],
    go_paths=[],
    go_deps_paths=[os.path.join(WORKSPACE, _p) for _p in (
        'src/go.chromium.org/gae',
        'src/go.chromium.org/luci',
    )],
    go_install_tools=[
        # Note: please add only tools that really should be in PATH in default
        # dev environment.
        'github.com/golang/mock/mockgen',
        'go.chromium.org/gae/tools/proto-gae',
        'go.chromium.org/luci/grpc/cmd/...',
        'go.chromium.org/luci/luci_notify/cmd/...',
        'go.chromium.org/luci/tools/cmd/...',
        'infra/cmd/bqexport',
        'infra/cmd/cloudsqlhelper',
    ],
)


# Describes a modification of os.environ, see get_go_environ_diff(...).
EnvironDiff = collections.namedtuple('EnvironDiff', [
    'env',          # {k:v} with vars to set or delete (if v == None)
    'env_prefixes', # {k: [path]} with entries to prepend
])


class Failure(Exception):
  """Bootstrap failed."""


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
  # Crutch to remove read-only file (.git/* in particular) on Windows.
  def onerror(func, path, _exc_info):
    if not os.access(path, os.W_OK):
      os.chmod(path, stat.S_IWUSR)
      func(path)
    else:
      raise
  shutil.rmtree(p, onerror=onerror if sys.platform == 'win32' else None)


def install_toolset(toolset_root, version):
  """Downloads and installs Go toolset from CIPD.

  GOROOT would be <toolset_root>/go/.
  """
  cmd = subprocess.Popen(
    [
      'cipd.bat' if sys.platform == 'win32' else 'cipd',
      'ensure', '-ensure-file', '-', '-root', toolset_root,
    ],
    stdin=subprocess.PIPE)
  cmd.communicate(
    '@Subdir go\n'
    'infra/go/${platform} version:%s\n' % version
  )
  if cmd.returncode:
    raise Failure('CIPD call failed, exit code %d' % cmd.returncode)
  LOGGER.info('Validating...')
  check_hello_world(toolset_root)


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
        import "fmt"
        func main() { fmt.Println("hello, world") }
    """)
    out = call_bare_go(toolset_root, tmp, ['run', path])
    if out != 'hello, world':
      raise Failure('Unexpected output from the sample program:\n%s' % out)


def call_bare_go(toolset_root, workspace, args):
  """Calls 'go <args>' in the given workspace scrubbing all other Go env vars.

  Args:
    toolset_root: where Go is installed at.
    workspace: value for GOPATH, all other Go-specific env vars are scrubbed.
    args: command line arguments for 'go' tool.

  Returns:
    Captured stripped stdout+stderr.

  Raises:
    Failure if the call failed. All details are logged in this case.
  """
  cmd = [get_go_exe(toolset_root)] + args
  env = get_go_environ(_EMPTY_LAYOUT._replace(
      toolset_root=toolset_root,
      workspace=workspace))
  proc = subprocess.Popen(
      cmd,
      env=env,
      cwd=workspace,
      stdout=subprocess.PIPE,
      stderr=subprocess.STDOUT)
  out, _ = proc.communicate()
  if proc.returncode:
    LOGGER.error('Failed to run %s: exit code %d', cmd, proc.returncode)
    LOGGER.error('Environment:')
    for k, v in sorted(env.items()):
      LOGGER.error('  %s = %s', k, v)
    LOGGER.error('Output:\n\n%s', out)
    raise Failure('Go invocation failed, see the log')
  return out.strip()


def infra_version_outdated(root):
  infra = read_file([root, 'INFRA_VERSION'])
  if not infra:
    return True
  return int(infra.strip()) < INFRA_VERSION


def write_infra_version(root):
  write_file([root, 'INFRA_VERSION'], str(INFRA_VERSION))


def ensure_toolset_installed(toolset_root, version):
  """Installs or updates Go toolset if necessary.

  Returns True if new toolset was installed.
  """
  installed = read_file([toolset_root, 'INSTALLED_TOOLSET'])
  if infra_version_outdated(toolset_root):
    LOGGER.info('Infra version is out of date.')
  elif installed == version:
    LOGGER.debug('Go toolset is up-to-date: %s', installed)
    return False

  LOGGER.info('Installing Go toolset.')
  LOGGER.info('  Old toolset is %s', installed)
  LOGGER.info('  New toolset is %s', version)
  remove_directory([toolset_root])
  install_toolset(toolset_root, version)
  LOGGER.info('Go toolset installed: %s', version)
  write_file([toolset_root, 'INSTALLED_TOOLSET'], version)
  write_infra_version(toolset_root)
  return True


def ensure_glide_installed(toolset_root):
  """Installs or updates 'glide' tool."""
  installed_tools = read_file([toolset_root, 'INSTALLED_TOOLS'])
  available_tools = json.dumps(GLIDE_SOURCE, sort_keys=True)
  if installed_tools == available_tools:
    LOGGER.debug('Glide is up-to-date')
    return

  def install(workspace, pkg):
    call_bare_go(toolset_root, workspace, ['install', pkg])
    # Windows os.rename doesn't support overwrites.
    name = pkg[pkg.rfind('/')+1:]
    dest = os.path.join(toolset_root, 'go', 'bin', name + EXE_SFX)
    if os.path.exists(dest):
      os.remove(dest)
    os.rename(os.path.join(workspace, 'bin', name + EXE_SFX), dest)
    LOGGER.info('Installed %s', dest)

  LOGGER.info('Installing Glide...')
  with temp_dir(toolset_root) as tmp:
    fetch_glide_code(tmp, GLIDE_SOURCE)
    install(tmp, 'github.com/Masterminds/glide')

  LOGGER.info('Glide is installed')
  write_file([toolset_root, 'INSTALLED_TOOLS'], available_tools)


def fetch_glide_code(workspace, spec):
  """Fetches glide source code."""
  def git(cmd, cwd):
    subprocess.check_call([GIT_EXE] + cmd, cwd=cwd, stdout=sys.stderr)
  for path, repo in sorted(spec.iteritems()):
    path = os.path.join(workspace, path.replace('/', os.sep))
    os.makedirs(path)
    git(['clone', repo['url'], '.'], cwd=path)
    git(['checkout', repo['rev']], cwd=path)


def get_git_repository_head(path):
  head = subprocess.check_output([GIT_EXE, '-C', path, 'rev-parse', 'HEAD'])
  return head.strip()


def get_deps_repo_versions(layout):
  """Loads the repository version object stored at GO_REPO_VERSIONS.

  If no version object exists, an empty dictionary will be returned.
  """
  if not os.path.isfile(layout.go_repo_versions_path):
    return {}
  with open(layout.go_repo_versions_path, 'r') as fd:
    return json.load(fd)


def save_deps_repo_versions(layout, v):
  """Records the repository version object, "v", as JSON at GO_REPO_VERSIONS."""
  with open(layout.go_repo_versions_path, 'w') as fd:
    json.dump(v, fd, indent=2, sort_keys=True)


def install_deps_tools(layout, force):
  if not layout.go_install_tools:
    return False

  # Load the current HEAD for our Go dependency paths.
  current_versions = {}
  for path in (layout.go_deps_paths or ()):
    current_versions[path] = get_git_repository_head(path)

  # Only install the tools if our checkout versions have changed.
  if not force and get_deps_repo_versions(layout) == current_versions:
    return False

  # (Re)install all of our Go packages.
  LOGGER.info('Installing Go tools: %s', layout.go_install_tools)
  env = get_go_environ(layout)
  subprocess.check_call([get_go_exe(layout.toolset_root), 'install'] +
                        list(layout.go_install_tools),
                        stdout=sys.stderr, stderr=sys.stderr, env=env)
  save_deps_repo_versions(layout, current_versions)
  return True


def update_vendor_packages(workspace, toolset_root, force=False):
  """Runs deps.py to fetch and install pinned packages.

  Returns (bool): True if the dependencies were actually updated, False if they
      were already at the correct version.
  """
  if not os.path.isfile(os.path.join(workspace, 'deps.lock')):
    return False

  # We will pass "deps.py" the "--update-out" argument, which will create a
  # file at a temporary path if the deps were actually updated. We use this to
  # derive our return value.
  with temp_dir(workspace) as tdir:
    update_out_path = os.path.join(tdir, 'deps_updated.json')
    cmd = [
      sys.executable, '-u', os.path.join(ROOT, 'go', 'deps.py'),
      '--workspace', workspace,
      '--goroot', os.path.join(toolset_root, 'go'),
      'install',
      '--update-out', update_out_path,
    ]
    if force:
      cmd.append('--force')
    env = os.environ.copy()
    env['PATH'] = os.pathsep.join([
        os.path.join(ROOT, 'cipd'), env.get('PATH', '')
    ])
    subprocess.check_call(cmd, stdout=sys.stderr, env=env)
    return os.path.isfile(update_out_path)


def get_go_environ_diff(layout):
  """Returns what modifications must be applied to the environ to enable Go.

  Pure function of 'layout', doesn't depend on current os.environ or state on
  disk.

  Args:
    layout: The Layout to derive the environment from.

  Returns:
    EnvironDiff.
  """
  # Paths to search Go code for. Order is important.
  vendor_paths = layout.vendor_paths or ()
  all_go_paths = []
  all_go_paths.extend(os.path.join(p, '.vendor') for p in vendor_paths)
  if layout.go_paths:
    all_go_paths.extend(layout.go_paths)
  all_go_paths.append(layout.workspace)

  # New PATH entries. Order is important.
  paths_to_add = [
      os.path.join(layout.toolset_root, 'go', 'bin'),
      os.path.join(ROOT, 'cipd'),
      os.path.join(ROOT, 'cipd', 'bin'),
      os.path.join(ROOT, 'luci', 'appengine', 'components', 'tools'),
  ]
  paths_to_add.extend(os.path.join(p, '.vendor', 'bin') for p in vendor_paths)
  paths_to_add.append(os.path.join(layout.workspace, 'bin'))

  return EnvironDiff(
      env={
          'GOROOT': os.path.join(layout.toolset_root, 'go'),
          'GOBIN': os.path.join(layout.workspace, 'bin'),
          'GOPATH': os.pathsep.join(all_go_paths),

          # Don't use default cache in '~'.
          'GOCACHE': os.path.join(layout.workspace, '.cache'),

          # Infra Go workspace is not ready for modules yet, attempting to use
          # them will cause pain.
          'GOPROXY': 'off',
          'GO111MODULE': 'off',
      },
      env_prefixes={'PATH': paths_to_add},
  )


def get_go_environ(layout):
  """Returns a copy of os.environ with mutated GO* environment variables.

  This function primarily targets environ on workstations. It assumes
  the developer may be constantly switching between infra and infra_internal
  go environments and it has some protection against related edge cases.

  Args:
    layout: The Layout to derive the environment from.
  """
  diff = get_go_environ_diff(layout)

  env = os.environ.copy()
  for k, v in diff.env.items():
    if v is not None:
      env[k] = v
    else:
      env.pop(k, None)

  path = env['PATH'].split(os.pathsep)
  paths_to_add = diff.env_prefixes['PATH']

  # Remove preexisting bin/ paths (including .vendor/bin) pointing to infra
  # or infra_internal Go workspaces. It's important when switching from
  # infra_internal to infra environments: infra_internal bin paths should
  # be removed.
  def should_keep(p):
    if p in paths_to_add:
      return False  # we'll move this entry to the front below
    # TODO(vadimsh): This code knows about gclient checkout layout.
    for d in ['infra', 'infra_internal']:
      if p.startswith(os.path.join(GCLIENT_ROOT, d, 'go')):
        return False
    return True
  path = filter(should_keep, path)

  # Prepend paths_to_add to PATH.
  env['PATH'] = os.pathsep.join(paths_to_add + path)

  # Add a tag to the prompt
  infra_prompt_tag = env.get('INFRA_PROMPT_TAG')
  if infra_prompt_tag is None:
    infra_prompt_tag = '[cr go] '
  if infra_prompt_tag:
    prompt = env.get('PS1')
    if prompt and infra_prompt_tag not in prompt:
      env['PS1'] = infra_prompt_tag + prompt

  return env


def get_go_exe(toolset_root):
  """Returns path to go executable."""
  return os.path.join(toolset_root, 'go', 'bin', 'go' + EXE_SFX)


def bootstrap(layout, logging_level, args=None):
  """Installs all dependencies in default locations.

  Supposed to be called at the beginning of some script (it modifies logger).

  Args:
    layout: instance of Layout describing what to install and where.
    logging_level: logging level of bootstrap process.
    args: positional arguments of bootstrap.py (if any).

  Raises:
    Failure if bootstrap fails.
  """
  logging.basicConfig()
  LOGGER.setLevel(logging_level)

  # One optional positional argument is a path to write JSON with env diff to.
  # This is used by recipes which use it in `with api.context(env=...): ...`.
  json_output = None
  if args is not None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'json_output',
        nargs='?',
        metavar='PATH',
        help='Where to write JSON with necessary environ adjustments')
    json_output = parser.parse_args(args=args).json_output

  # We need to build and run some Go binaries during bootstrap (e.g. glide), so
  # make sure cross-compilation mode is disabled during bootstrap. Restore it
  # back once bootstrap is finished.
  prev_environ = {}
  for k in ('GOOS', 'GOARCH', 'GOARM'):
    prev_environ[k] = os.environ.pop(k, None)

  try:
    toolset_updated = ensure_toolset_installed(
        layout.toolset_root, TOOLSET_VERSION)
    ensure_glide_installed(layout.toolset_root)
    vendor_updated = toolset_updated
    for p in layout.vendor_paths:
      vendor_updated |= update_vendor_packages(
          p, layout.toolset_root, force=toolset_updated)
    if toolset_updated:
      # GOPATH/pkg may have binaries generated with previous version of toolset,
      # they may not be compatible and "go build" isn't smart enough to rebuild
      # them.
      for p in layout.vendor_paths:
        remove_directory([p, 'pkg'])
    install_deps_tools(layout, vendor_updated)
  finally:
    # Restore os.environ back. Have to do it key-by-key to actually modify the
    # process environment (replacing os.environ object as a whole does nothing).
    for k, v in prev_environ.iteritems():
      if v is not None:
        os.environ[k] = v

  output = get_go_environ_diff(layout)._asdict()
  output['go_version'] = TOOLSET_VERSION

  json_blob = json.dumps(
      output,
      sort_keys=True,
      indent=2,
      separators=(',', ': '))

  if json_output == '-':
    print json_blob
  elif json_output:
    with open(json_output, 'w') as f:
      f.write(json_blob)


def prepare_go_environ():
  """Returns dict with environment variables to set to use Go toolset.

  Installs or updates the toolset and vendored dependencies if necessary.
  """
  bootstrap(LAYOUT, logging.INFO)
  return get_go_environ(LAYOUT)


def find_executable(name, workspaces):
  """Returns full path to an executable in some bin/ (in GOROOT or GOBIN)."""
  basename = name
  if EXE_SFX and basename.endswith(EXE_SFX):
    basename = basename[:-len(EXE_SFX)]
  roots = [os.path.join(LAYOUT.toolset_root, 'go', 'bin')]
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
  bootstrap(LAYOUT, logging.DEBUG, args)
  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
