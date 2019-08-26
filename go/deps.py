#!/usr/bin/env vpython
# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A tool to prepare a GOPATH with vendored Go dependenies.

We abuse Glide by using it for GOPATH-based vendoring, while it is supposed to
be used for "Vendor Experiment"-based vendoring.

It knows only how to install packages into $GOPATH/src/vendor (assuming
glide.yaml is in $GOPATH/src/glide.yaml), yet we need packages in a separate
$GOPATH, so that this separate $GOPATH can be reused by infra_internal
workspace.

infra/go/src/vendor/* doesn't work for infra_internal packages because it is in
a different $GOPATH, and infra_internal packages can't find dependencies
vendored there.

Making separate infra_internal/go/src/vendor/* leads to a bigger mess where
there are multiple copies of packages imported via infra/* and infra_internal/*
code in a single binary.

So instead we let glide do its thing, but then rudely convert vendor/* directory
it produces into a new completely separate $GOPATH (in <workspace>/.vendor).

To remove a temptation to use "glide update" directly (it won't work as
expected), we rename glide.yaml and glide.lock into deps.yaml and deps.lock.
"""

import argparse
import collections
import contextlib
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time

import yaml


# Whitelist of packages with executables we want to be available in PATH. Will
# be installed via "go install" after Glide fetches all vendored dependencies.
# See 'install' function below.
VENDORED_TOOLS = [
  'github.com/golang/mock/mockgen',
  'github.com/golang/protobuf/protoc-gen-go',
  'github.com/kisielk/errcheck',
  'github.com/maruel/panicparse/cmd/pp',
  'github.com/smartystreets/goconvey',
  'golang.org/x/lint/golint',
  'golang.org/x/mobile/cmd/gomobile',
  'golang.org/x/tools/cmd/callgraph',
  'golang.org/x/tools/cmd/fiximports',
  'golang.org/x/tools/cmd/godex',
  'golang.org/x/tools/cmd/goimports',
  'golang.org/x/tools/cmd/gomvpkg',
  'golang.org/x/tools/cmd/gorename',
  'golang.org/x/tools/cmd/guru',
  'golang.org/x/tools/cmd/stringer',
  'google.golang.org/api/google-api-go-generator',
  'google.golang.org/appengine/cmd/aedeploy',
]


# By default we drop all non-source code files from the vendored packages to
# make the bundle with dependencies smaller and simpler. Some packages don't
# like that.
PACKAGES_TO_VENDOR_COMPLETELY = [
  'github.com/smartystreets/goconvey',  # needs *.css etc for Web UI
  'go.starlark.net',                    # needs *.star files
]


# Paths (relative to src/) to avoid including in the bundle because they contain
# very nested directory trees that break MAX_PATH limit on Windows. When adding
# a path here, verify that all code still builds without it.
BLACKLISTED_PATHS = [
  'github.com/docker/docker/' +
    'vendor/github.com/google/certificate-transparency/cpp',
]


# infra/
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


_Workspace = collections.namedtuple('_Workspace', (
    # Path of the directory containing "deps", default: infra/go
    'gobase',
    # Path of the vendor root directory, default: infra/go/.vendor
    'vendor_root',
    # Path of the Go runtime root, default: golang/go
    'goroot',
    # Name of a CIPD package with prefetched deps, default: infra/go-deps
    'deps_cipd_pkg',
    # URL of a CIPD package repository to use, default: chrome-infra-packages
    'cipd_service_url',
    # Path to a service account key to use when talking to CIPD, default: None
    'service_account_json',
))


WORKSPACE = _Workspace(
    gobase=os.path.join(REPO_ROOT, 'go'),
    vendor_root=os.path.join(REPO_ROOT, 'go', '.vendor'),
    goroot=os.path.join(os.path.dirname(REPO_ROOT), 'golang', 'go'),
    deps_cipd_pkg='infra/go-deps',
    cipd_service_url='https://chrome-infra-packages.appspot.com',
    service_account_json=None,  # usually set via CLI args
)


# Name of a Glide lock file to put into .vendor/* when all packages there are
# fully installed. Acts as a marker of successful installation.
APPLIED_LOCK = 'applied.lock'

# Name of a Glide lock file to put in a CIPD package with bundled dependencies.
# Descrbies what's there.
BUNDLED_LOCK = 'bundled.lock'

# Name of a CIPD package tag that specifies the version of bundled deps.
BUNDLE_FORMAT_TAG = 'go_deps_lock'


# Printed to bring attention because users usually ignore walls of text.
BANNER_START = '-'*24 + 'WARNING! WARNING! WARNING!' + '-'*24
BANNER_END   = '-'*24 + '--------------------------' + '-'*24


class CallFailed(Exception):
  """Raised by 'call' on non-zero exit codes."""


def flatten_deps(deps):
  """Converts deps.lock dict into a list of go packages specified there."""
  out = []
  for p in deps['imports']:
    # Each 'p' here have a form similar to:
    #
    # - name: golang.org/x/net
    #   version: 31df19d69da8728e9220def59b80ee577c3e48bf
    #   repo: https://go.googlesource.com/net.git
    #   subpackages:
    #   - context
    #   - context/ctxhttp
    #
    # where empty 'subpackages' means an entire repo is used.
    sub = p.get('subpackages')
    if not sub:
      out.append(p['name'])
    else:
      out.extend(p['name'] + '/' + subpkg for subpkg in sub)
  return sorted(out)


def contains_subpackages(workspace, path):
  stdout, _ = call(workspace, 'go', ['list', path + '...'], capture_output=True)
  return stdout != ''


def is_googlesource(url):
  return re.match(r'https\://.*\.googlesource\.com/', url)


def compare_deps(before, after):
  """Analyzes a difference in old and new deps, and prints some helpful stuff.

  Returns True if deps changed, False if not.

  Args:
    before: dict with deps.lock content before an update.
    after: dict with deps.lock content after the update.
  """
  # Print a list of what has been added or removed.
  flatten_before = set(flatten_deps(before))
  flatten_after = set(flatten_deps(after))

  new_deps = flatten_after - flatten_before
  if new_deps:
    print '-'*74
    print 'Dependencies added to deps.lock:'
    for p in sorted(new_deps):
      print '  * %s' % p
    print '-'*74

  rem_deps = flatten_before - flatten_after
  if rem_deps:
    print '-'*74
    print 'Dependencies removed from deps.lock:'
    for p in sorted(rem_deps):
      print '  * %s' % p
    print '-'*74

  # Package name => mirror repo URL (usually on *.googlesource.com) or '' if
  # no mirror defines.
  mirrors = {p['name']: p.get('repo') or '' for p in after['imports']}

  # Print a list of what have been bumped.
  def revisions(deps):
    return {p['name']: p['version'] for p in deps['imports']}
  rev_before = revisions(before)
  rev_after = revisions(after)

  bumps = []
  for pkg, rev in rev_after.iteritems():
    if pkg in rev_before and rev != rev_before[pkg]:
      bumps.append((pkg, rev_before[pkg], rev))
  bumps.sort()
  if bumps:
    print '-'*74
    print 'Updated repos:'
    gs = [v for v in bumps if is_googlesource(mirrors[v[0]])]
    rest = [v for v in bumps if not is_googlesource(mirrors[v[0]])]
    for pkg, sha1_before, sha1_after in gs:
      print '%s/+log/%s..%s' % (mirrors[pkg], sha1_before[:12], sha1_after[:12])
    for pkg, sha1_before, sha1_after in rest:
      print '%s: %s -> %s' % (pkg, sha1_before, sha1_after)
    print '-'*74
    print
    print (
        'IMPORTANT: Please include the above updated repos report in the '
        'commit message.')
    print

  # Print a list of packages that need git mirrors. All of them do, so it just
  # prints a list of packages without 'repo' field set.

  bad_ones = []
  for pkg in after['imports']:
    if not pkg.get('repo'):
      bad_ones.append(pkg)
  if bad_ones:
    bad_ones.sort(key=lambda p: p['name'])
    print BANNER_START
    print (
        'Some packages that have been added to deps.yaml directly or pulled\n'
        'as transitive dependencies of packages specified in deps.yaml don\'t\n'
        'have mirror repositories specified. It means CI builders will pull\n'
        'dependencies directly from source-of-truth repos. This is usually\n'
        'a bad idea. We\'d have to update deps.yaml with information about\n'
        'the mirrors.')
    print
    print (
        'First setup the following git mirrors (you may need to file an\n'
        '"Infra-Git" ticket to do that):')
    for p in bad_ones:
      print '  * https://chromium.googlesource.com/external/%s.git' % p['name']
    print
    print (
        'Once all mirrors are up, make sure deps.yaml has the following\n'
        'records (by putting them there or modifying existing ones) and\n'
        'rerun "deps.py update" again:')
    print
    for p in bad_ones:
      print '- package: %s' % p['name']
      print (
          '  repo: https://chromium.googlesource.com/external/%s.git' %
          p['name'])
      print '  version: master'
      if p.get('subpackages'):
        print '  subpackages:'
        for subpkg in p['subpackages']:
          print '  - %s' % subpkg
    print BANNER_END

  # Did 'after' change in a meaningful way? Glide likes to touch 'updated' field
  # no matter what. We ignore it when comparing deps.
  before = before.copy()
  before.pop('updated')
  after = after.copy()
  after.pop('updated')
  return before != after


@contextlib.contextmanager
def unhack_vendor(workspace):
  """Renames .vendor/src into .vendor/vendor, copies YAMLs into .vendor/.

  Basically, makes .vendor/* look like it is glide-managed directory, and not
  some horrible abomination it, in fact, is.

  It also tracks changes done by glide to glide.lock and prints various helpful
  stuff (see 'compare_deps').

  Args:
    workspace: an initialized _Workspace object.
  """
  # Make empty .vendor if it didn't exist before. Makes life a bit easier below.
  src_path = os.path.join(workspace.vendor_root, 'src')
  vendor_path = os.path.join(workspace.vendor_root, 'vendor')
  if not os.path.exists(src_path):
    os.makedirs(src_path)

  try:
    # Rename 'src' to 'vendor', so that glide can work with it.
    os.rename(src_path, vendor_path)

    # Glide still demands 'src' for some reason, even if it is empty.
    os.mkdir(src_path)

    # Copy YAMLs used by glide.
    shutil.copy(
        os.path.join(workspace.gobase, 'deps.yaml'),
        os.path.join(workspace.vendor_root, 'glide.yaml'))
    shutil.copy(
        os.path.join(workspace.gobase, 'deps.lock'),
        os.path.join(workspace.vendor_root, 'glide.lock'))

    lock_before = read_file(os.path.join(workspace.vendor_root, 'glide.lock'))
    deps_before = yaml.safe_load(lock_before)
    yield
    lock_after = read_file(os.path.join(workspace.vendor_root, 'glide.lock'))
    deps_after = yaml.safe_load(lock_after)

    if compare_deps(deps_before, deps_after):
      print 'Run "deps.py install" to reinstall dependencies when ready.'
    else:
      # No changes? Just put glide.lock back as it was, since new glide.lock
      # differs only in not very useful 'updated' timestamp field.
      write_file(os.path.join(workspace.vendor_root, 'glide.lock'), lock_before)

    # Copy modified yamls back only on success.
    shutil.copy(
        os.path.join(workspace.vendor_root, 'glide.yaml'),
        os.path.join(workspace.gobase, 'deps.yaml'))
    shutil.copy(
        os.path.join(workspace.vendor_root, 'glide.lock'),
        os.path.join(workspace.gobase, 'deps.lock'))

  except Exception:
    # Remove 'applied.lock' to make sure 'deps.py install' reinstalls
    # the packages next time, fixing the state of .vendor/.
    applied_lock = os.path.join(workspace.vendor_root, APPLIED_LOCK)
    if os.path.exists(applied_lock):
      os.remove(applied_lock)

    print >> sys.stderr, BANNER_START
    print >> sys.stderr, (
        '%s was probably left in an inconsistent state!\n' % (
            workspace.vendor_root,))
    print >> sys.stderr, (
        'You may want to remove it completely and build it again by running\n'
        '"deps.py install".')
    print >> sys.stderr, BANNER_END
    raise

  finally:
    # Undo everything.
    os.remove(os.path.join(workspace.vendor_root, 'glide.lock'))
    os.remove(os.path.join(workspace.vendor_root, 'glide.yaml'))
    os.rmdir(src_path) # must still be empty
    os.rename(vendor_path, src_path)


def call(workspace, tool, args, capture_output=False):
  """Invokes a tool from GOROOT/bin, setting GOPATH to <workspace>/.vendor.

  Note that 'glide' is installed by bootstrap.py into GOROOT/bin too. Raises
  CallFailed exception on errors.

  Args:
    workspace: an initialized _Workspace object.
    tool: name of an executable to call, e.g. "go" or "glide".
    args: additional command line arguments to pass to it.
    capture_output: whether to capture return the child process' stdout and
      stderr.

  Returns:
    A string containing the child process' stdout if capture_output was True.
  """
  sfx = '.exe' if sys.platform == 'win32' else ''
  cmd = [os.path.join(workspace.goroot, 'bin', tool + sfx)] + args

  # Completely replace any existing Go env vars.
  env = os.environ.copy()
  env['GOROOT'] = workspace.goroot
  env['GOPATH'] = workspace.vendor_root
  env['GOBIN'] = os.path.join(workspace.vendor_root, 'bin')

  # Glide searches for 'go' in PATH. Make it available.
  env['PATH'] = os.path.join(env['GOROOT'], 'bin') + os.pathsep + env['PATH']

  # Forbid Glide to mess with global ~/.glide or system temp.
  # TODO(vadimsh): .glide/cache can have really long paths, may be problematic
  # on Windows.
  env['GLIDE_HOME'] = os.path.join(workspace.gobase, '.glide')
  env['GLIDE_TMP'] = os.path.join(workspace.gobase, '.glide')

  kwargs = {
      'env': env,
      'cwd': env['GOPATH'],
  }
  if capture_output:
    kwargs['stdout'] = subprocess.PIPE
    kwargs['stderr'] = subprocess.PIPE

  proc = subprocess.Popen(cmd, **kwargs)
  stdout, stderr = proc.communicate()

  if proc.returncode:
    raise CallFailed(
        '"%s %s" FAILED, see the log' % (tool, ' '.join(args)))
  return stdout, stderr


def read_file(path):
  """Returns contents of a given file or None if not readable."""
  try:
    with open(path, 'rb') as f:
      return f.read()
  except IOError:
    return None


def write_file(path, blob):
  """Writes a blob into a file."""
  # Files originally installed from CIPD packages are read-only, need to make
  # them writable before overwriting.
  try:
    st = os.stat(path)
    os.chmod(path, st.st_mode | stat.S_IWUSR)
  except OSError:
    pass # doesn't exist yet probably
  with open(path, 'wb') as f:
    return f.write(blob)


def remove_directory(p):
  """Recursively removes a directory if it exists (works on Windows!)."""
  if not os.path.exists(p):
    return
  # One does not simply remove a directory on Windows... Read-only files
  # (.git/* in particular) need special treatment.
  def onerror(func, path, _exc_info):
    if not os.access(path, os.W_OK):
      os.chmod(path, stat.S_IWUSR)
      func(path)
    else:
      raise
  shutil.rmtree(p, onerror=onerror if sys.platform == 'win32' else None)


@contextlib.contextmanager
def temp_file(body=None, root=None):
  """Creates a temp file and returns path to it."""
  fd, tmp = tempfile.mkstemp(suffix='go_deps_py', dir=root)
  try:
    if body:
      with os.fdopen(fd, 'wb') as f:
        f.write(body)
    else:
      os.close(fd)
    yield tmp
  finally:
    os.remove(tmp)


def purify_directory(root, path):
  """Removes all non-important files from a directory.

  Also drops +x bit on remaining regular files.

  Works recursively. For each file calls 'is_source_or_license(rel_path)'
  to detect whether it is important or not, and deletes the file if not.

  Returns True if 'path' still has direct children.
  """
  # Note: recursively removing empty directories is not trivial with os.walk.
  # Doing the recursion directly is simpler.
  has_files = False
  for name in os.listdir(os.path.join(root, path)):
    rel_path = os.path.join(path, name)
    full_path = os.path.join(root, rel_path)
    mode = os.lstat(full_path).st_mode
    if stat.S_ISDIR(mode):
      if not purify_directory(root, rel_path):
        # The child directory is empty now, can be removed.
        os.rmdir(full_path)
        continue
    elif not is_source_or_license(rel_path):
      os.remove(full_path)
      continue
    elif mode & stat.S_IXUSR:
      # Some *.go files inexplicably have +x bit. Drop it.
      os.chmod(full_path, 0644)
    has_files = True
  return has_files


def is_source_or_license(path):
  """Returns True if 'path' point to a file we want to keep.

  The path is given relative to GOPATH/src.
  """
  pkg = os.path.dirname(path).replace('\\', '/')
  name = os.path.basename(path)

  def in_list(l):
    return any(pkg == p or pkg.startswith(p+'/') for p in l)

  if in_list(PACKAGES_TO_VENDOR_COMPLETELY):
    return True
  if in_list(BLACKLISTED_PATHS):
    return False

  return (
      name.startswith('LICENSE') or
      name.endswith(('.c', '.h', '.go', '.s')) and
      not name.endswith('_test.go'))


def cipd(workspace, args, silent=False):
  """Calls 'cipd' tool (from PATH), returns the process exit code."""
  cmd = ['cipd.bat' if sys.platform == 'win32' else 'cipd']
  cmd += args
  if args[0] not in ['pkg-build']:  # non-local op?
    if workspace.service_account_json:
      cmd += ['-service-account-json', workspace.service_account_json]
    cmd += ['-service-url', workspace.cipd_service_url]
  proc = subprocess.Popen(
      cmd,
      stdout=subprocess.PIPE if silent else None,
      stderr=subprocess.PIPE if silent else None)
  proc.communicate()
  return proc.returncode


def get_bundle_ver(lock_file_body):
  """Returns a version with a CIPD bundle corresponding to this lock file."""
  # There's a "hash" field in glide.lock. It is a trap. It doesn't change when
  # version of the dependencies change. So instead just hash the (sanitized)
  # manifest itself.
  glide_lock = yaml.safe_load(lock_file_body)
  glide_lock.pop('hash', None)
  glide_lock.pop('updated', None)
  sha1 = hashlib.sha1(json.dumps(glide_lock, sort_keys=True)).hexdigest()
  return '%s:%s' % (BUNDLE_FORMAT_TAG, sha1)


def get_cipd_pkg_url(name, ver):
  """Returns URL to a package in CIPD web UI."""
  return 'https://chrome-infra-packages.appspot.com/p/%s/+/%s' % (name, ver)


def is_existing_bundle(workspace, pkg, ver):
  """Returns True if there exists a bundle with given version."""
  return cipd(workspace, ['resolve', pkg, '-version', ver], silent=True) == 0


def grab_doc(func):
  """Extracts help for CLI from a function doc string."""
  return func.__doc__.splitlines()[0].lower().strip('.')


def obliterate_glide_cache(workspace):
  """Deletes .glide cache directory.

  For some mysterious reasons Glide sometimes skips fetching commits for
  repos in its cache. Delete the cache. We are not really benefiting from
  it, since it is used only when updating deps.lock, which is rare.
  """
  remove_directory(os.path.join(workspace.gobase, '.glide'))


################################################################################
## Subcommands.


GLIDE_INSTALL_RETRIES = 4


def install(workspace, force=False, update_out=None, skip_bundle=False):
  """Installs all dependencies from deps.lock into .vendor/ GOPATH.

  Will try to use a CIPD bundle with dependencies if it exists. See 'bundle'
  command.

  Args:
    workspace: an initialized _Workspace object.
    force: if True, will forcefully rebuild .vendor even if it is up-to-date.
    update_out: path to write deps.lock to if did install something.
    skip_bundle: if True, fetch everything from git, not from CIPD bundle.

  Returns:
    Exit code.
  """
  required = read_file(os.path.join(workspace.gobase, 'deps.lock'))
  if not force:
    installed = read_file(os.path.join(workspace.vendor_root, APPLIED_LOCK))
    if installed == required:
      return 0

  # Glide is supposed to delete vendored packages that are no longer specified
  # in glide.lock, but it doesn't (at least in v0.10.1), even if '--delete' and
  # '--force' is used. So nuke entire .vendor/* and refetch everything from
  # scratch. It also helps us to avoid various lingering state corruption in
  # .vendor/*.
  remove_directory(workspace.vendor_root)

  # Now we need to fetch all the source code into empty 'vendor_root'. There
  # are two choices: either we use Glide (and clone each deps repo one by one),
  # or we fetch a single CIPD package with all deps bundled already.
  use_bundle = False
  pkg = workspace.deps_cipd_pkg
  ver = get_bundle_ver(required)
  if not skip_bundle:
    print 'Searching for a bundle with dependencies in CIPD...'
    print 'CIPD package: %s' % get_cipd_pkg_url(pkg, ver)
    use_bundle = is_existing_bundle(workspace, pkg, ver)
    if not use_bundle:
      print 'Not found, falling back to using "glide install".'

  if use_bundle:
    # Don't retry, cipd does retries itself.
    ensure_spec = '%s %s' % (pkg, ver)
    with temp_file(body=ensure_spec, root=workspace.gobase) as tmp:
      ret = cipd(workspace, ['ensure', '-ensure-file', tmp, '-root',
                              workspace.vendor_root])
    if ret:
      print 'Failed to install dependencies from the bundle. See logs.'
      return ret

    # Double check we've got what we requested.
    bundled = read_file(os.path.join(workspace.vendor_root, BUNDLED_LOCK))
    if get_bundle_ver(bundled) != ver:
      print (
          'deps.lock in repo doesn\'t match bundled.lock in CIPD bundle.\n'
          'Possibly the bundle was built from a corrupted checkout.\n'
          'Build a new version.')
      return 1

  else:
    with unhack_vendor(workspace):
      for retry in xrange(GLIDE_INSTALL_RETRIES):
        try:
          call(workspace, 'glide', ['install'])
          break
        except CallFailed as e:
          if retry < GLIDE_INSTALL_RETRIES - 1:
            delay = 2 ** retry
            print(
                'Failed to install dependencies. Deleting Glide cache and '
                'retrying after %d sec.' % delay)
            obliterate_glide_cache(workspace)
            time.sleep(delay)
          else:
            raise e
    # Remove all garbage, we need only non-test source code to use dependencies.
    print 'Removing non-source code files...'
    purify_directory(os.path.join(workspace.vendor_root, 'src'), '')

  # We will install only interesting subset of executables below. Nuke
  # everything else to avoid polluting PATH with unimportant stuff.
  remove_directory(os.path.join(workspace.vendor_root, 'bin'))

  # Install only stuff that was vendored via glide. That way we can support
  # multiple workspaces with third party code, but keep a single VENDORED_TOOLS
  # whitelist of "important stuff". If a workspace is not interested in having
  # a tool present, it just doesn't list it in deps.yaml.
  to_install = []
  for pkg in VENDORED_TOOLS:
    pkg_path = os.path.join(
        workspace.vendor_root, 'src', pkg.replace('/', os.sep))
    if not os.path.isdir(pkg_path):
      print 'No Go package for vendored tool [%s] at: %s' % (pkg, pkg_path)
      continue
    to_install.append(pkg)

  print 'Rebuilding tools...'
  call(workspace, 'go', ['install', '-v'] + to_install)

  # Put a marker file that indicates we successfully installed all deps.
  write_file(os.path.join(workspace.vendor_root, APPLIED_LOCK), required)
  if update_out:
    write_file(update_out, required)
  return 0


def update(workspace):
  """Updates deps.lock file to point to most recent versions of packages.

  Args:
    workspace: an initialized _Workspace object.
  """
  lock_path = os.path.join(workspace.vendor_root, 'glide.lock')
  with unhack_vendor(workspace):
    # Glide cache is buggy. We need no cache.
    obliterate_glide_cache(workspace)
    # For a mysterious reason Glide doesn't update all dependencies on a first
    # try. Run it until it reports there's nothing to update.
    deps = yaml.safe_load(read_file(lock_path))
    while True:
      call(workspace, 'glide', ['update', '--force'])
      deps_after = yaml.safe_load(read_file(lock_path))
      if deps == deps_after:
        break
      print 'One more time...'
      deps = deps_after
  return 0


def add(workspace, packages):
  """Adds a bunch of packages into deps.yaml.

  Args:
    workspace: an initialized _Workspace object.
    packages: a list of go packages to add to deps.yaml.
  """
  with unhack_vendor(workspace):
    obliterate_glide_cache(workspace)
    call(workspace, 'glide', ['get', '--force'] + packages)
  return 0


def remove(workspace, packages):
  """Removes a bunch of packages from deps.yaml.

  Args:
    workspace: an initialized _Workspace object.
    packages: a list of go packages to remove from deps.yaml.
  """
  with unhack_vendor(workspace):
    obliterate_glide_cache(workspace)
    call(workspace, 'glide', ['remove'] + packages)
  return 0


def bundle(workspace, out_file=None):
  """Builds and uploads a CIPD package with all vendored dependencies.

  This CIPD package is then used by 'deps.py install' to speed up the
  installation. Uses a digest of deps.lock as a version identifier for the CIPD
  package.

  Expects 'cipd' tool to be in PATH.
  """
  lock_file = read_file(os.path.join(workspace.gobase, 'deps.lock'))

  pkg = workspace.deps_cipd_pkg
  ver = get_bundle_ver(lock_file)
  print 'CIPD package: %s' % get_cipd_pkg_url(workspace.deps_cipd_pkg, ver)

  if not out_file:
    print 'Checking whether the bundle is already uploaded...'
    if is_existing_bundle(workspace, pkg, ver):
      print 'Yep, no need to upload it.'
      return 0
    print 'Nope. Uploading it...'

  # Make sure we have all deps installed for git.
  if install(workspace, force=True, skip_bundle=True):
    return 1

  # Put a description of what's there in the bundle.
  write_file(os.path.join(workspace.vendor_root, BUNDLED_LOCK), lock_file)

  # Bundle only the source code (no 'pkg' and 'bin').
  pkg_def = {
    'package': pkg,
    'root': '.',  # assumes temp_file() creates files in vendor_root
    'install_mode': 'copy',
    'data': [
      {
        'dir': 'src',
      },
      {
        'file': BUNDLED_LOCK,
      },
      {
        'version_file': 'CIPD_VERSION.json',
      },
    ],
  }
  with temp_file(body=json.dumps(pkg_def), root=workspace.vendor_root) as tmp:
    if out_file:
      cmd = ['pkg-build', '-pkg-def', tmp, '-out', out_file]
    else:
      cmd = ['create', '-pkg-def', tmp, '-tag', ver, '-ref', 'latest']
    cmd.extend(['-hash-algo', 'sha256'])
    if cipd(workspace, cmd):
      print 'FAILED! See logs.'
      return 1

  print 'Done!'
  return 0


def main(args):
  parser = argparse.ArgumentParser(
      description='Utility to manage go vendored dependencies.')
  parser.add_argument(
      '--workspace', action='store', default=WORKSPACE.gobase,
      help='directory with deps.yaml, deps will be installed in .vendor subdir')
  parser.add_argument(
      '--goroot', action='store', default=WORKSPACE.goroot,
      help='Go installation GOROOT directory')

  subparsers = parser.add_subparsers()

  parser_install = subparsers.add_parser('install', help=grab_doc(install))
  parser_install.set_defaults(action=install)
  parser_install.add_argument(
      '--service-account-json', action='store', default=None,
      help='path to a service account key to pass to CIPD client')
  parser_install.add_argument(
      '--force', action='store_true', default=False,
      help='forcefully reinstall all dependencies')
  parser_install.add_argument(
      '--update-out', action='store', default=None,
      help='if supplied, the updated list of Go packages will be written here '
           'if an update occurred.')

  parser_update = subparsers.add_parser('update', help=grab_doc(update))
  parser_update.set_defaults(action=update)

  parser_add = subparsers.add_parser('add', help=grab_doc(add))
  parser_add.set_defaults(action=add)
  parser_add.add_argument(
      'pkg', nargs='+', help='a go package to add to deps.yaml')

  parser_remove = subparsers.add_parser('remove', help=grab_doc(remove))
  parser_remove.set_defaults(action=remove)
  parser_remove.add_argument(
      'pkg', nargs='+', help='a go package to remove from deps.yaml')

  parser_bundle = subparsers.add_parser('bundle', help=grab_doc(bundle))
  parser_bundle.set_defaults(action=bundle)
  parser_bundle.add_argument(
      '--service-account-json', action='store', default=None,
      help='path to a service account key to pass to CIPD client')
  parser_bundle.add_argument(
      '--to-file', action='store', default=None,
      help='if given, will not contact CIPD backend and will dump the bundle '
           'as a file on disk at the specified location')

  opts = parser.parse_args(args)

  workspace = WORKSPACE
  if opts.workspace != workspace.gobase:
    workspace = workspace._replace(gobase=opts.workspace)
  if opts.goroot:
    workspace = workspace._replace(goroot=opts.goroot)
  if getattr(opts, 'service_account_json', None):
    workspace = workspace._replace(
        service_account_json=opts.service_account_json)

  try:
    if opts.action == install:
      return install(workspace, opts.force, opts.update_out)
    if opts.action == update:
      return update(workspace)
    if opts.action == add:
      return add(workspace, opts.pkg)
    if opts.action == remove:
      return remove(workspace, opts.pkg)
    if opts.action == bundle:
      return bundle(workspace, opts.to_file)
    assert False, 'Unreachable'
  except CallFailed as exc:
    print >> sys.stderr, str(exc)
    return 1


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
