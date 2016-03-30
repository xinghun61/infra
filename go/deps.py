#!/usr/bin/env python
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
import contextlib
import json
import os
import shutil
import stat
import subprocess
import sys


# Whitelist of packages with executables we want to be available in PATH. Will
# be installed via "go install" after Glide fetches all vendored dependencies.
# See 'install' function below.
VENDORED_TOOLS = [
  'github.com/golang/lint/golint',
  'github.com/golang/protobuf/protoc-gen-go',
  'github.com/kisielk/errcheck',
  'github.com/maruel/panicparse/cmd/pp',
  'github.com/maruel/pre-commit-go/cmd/covg',
  'github.com/maruel/pre-commit-go/cmd/pcg',
  'github.com/smartystreets/goconvey',
  'golang.org/x/tools/cmd/callgraph',
  'golang.org/x/tools/cmd/fiximports',
  'golang.org/x/tools/cmd/godex',
  'golang.org/x/tools/cmd/goimports',
  'golang.org/x/tools/cmd/gomvpkg',
  'golang.org/x/tools/cmd/gorename',
  'golang.org/x/tools/cmd/oracle',
  'golang.org/x/tools/cmd/stringer',
  'google.golang.org/api/google-api-go-generator',
  'google.golang.org/appengine/cmd/aedeploy',
]


# infra/go/
WORKSPACE = os.path.dirname(os.path.abspath(__file__))
# infra/
REPO_ROOT = os.path.dirname(WORKSPACE)
# Where Go toolset is installed by bootstrap.py.
TOOLSET_ROOT = os.path.join(os.path.dirname(REPO_ROOT), 'golang')


# Name of a file to put into .vendor/* when all packages there match deps.lock.
APPLIED_LOCK = 'applied.lock'


# Printed to bring attention because users usually ignore walls of text.
BANNER_START = '-'*24 + 'WARNING! WARNING! WARNING!' + '-'*24
BANNER_END   = '-'*24 + '--------------------------' + '-'*24


class CallFailed(Exception):
  """Raised by 'call' on non-zero exit codes."""


def parse_glide_lock(content):
  """Parses deps.lock YAML file content and returns it as python dict."""
  # YAML lib is in venv, not activated here. Do some ugly hacks, they at least
  # don't touch python module import madness. Importing a package from another
  # venv directly into the process space is non-trivial and dangerous.
  oneliner = (
      'import json, sys, yaml; '
      'out = yaml.safe_load(sys.stdin); '
      'out["updated"] = str(out["updated"]); ' # not JSON serializable otherwise
      'json.dump(out, sys.stdout)')
  if sys.platform == 'win32':
    python_venv_path = ('Scripts', 'python.exe')
  else:
    python_venv_path = ('bin', 'python')
  executable = os.path.join(REPO_ROOT, 'ENV', *python_venv_path)
  env = os.environ.copy()
  env.pop('PYTHONPATH', None)
  proc = subprocess.Popen(
      [executable, '-c', oneliner],
      executable=executable,
      stdin=subprocess.PIPE,
      stdout=subprocess.PIPE,
      env=env)
  return json.loads(proc.communicate(content)[0])


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

  # Print a list of what have been bumped.
  def revisions(deps):
    return {p['name']: p['version'] for p in deps['imports']}
  rev_before = revisions(before)
  rev_after = revisions(after)

  bumps = []
  for pkg, rev in rev_after.iteritems():
    if pkg in rev_before and rev != rev_before[pkg]:
      bumps.append((pkg, rev_before[pkg], rev))
  if bumps:
    print '-'*74
    print 'Updated repos:'
    for pkg, sha1_before, sha1_after in sorted(bumps):
      print '%s: %s => %s' % (pkg, sha1_before, sha1_after)
    print '-'*74

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
    workspace: a directory where deps.yaml is located.
  """
  # Make empty .vendor if it didn't exist before. Makes life a bit easier below.
  src_path = os.path.join(workspace, '.vendor', 'src')
  vendor_path = os.path.join(workspace, '.vendor', 'vendor')
  if not os.path.exists(src_path):
    os.makedirs(src_path)

  try:
    # Rename 'src' to 'vendor', so that glide can work with it.
    os.rename(src_path, vendor_path)

    # Glide still demands 'src' for some reason, even if it is empty.
    os.mkdir(src_path)

    # Copy YAMLs used by glide.
    shutil.copy(
        os.path.join(workspace, 'deps.yaml'),
        os.path.join(workspace, '.vendor', 'glide.yaml'))
    shutil.copy(
        os.path.join(workspace, 'deps.lock'),
        os.path.join(workspace, '.vendor', 'glide.lock'))

    lock_before = read_file(os.path.join(workspace, '.vendor', 'glide.lock'))
    deps_before = parse_glide_lock(lock_before)
    yield
    lock_after = read_file(os.path.join(workspace, '.vendor', 'glide.lock'))
    deps_after = parse_glide_lock(lock_after)

    if compare_deps(deps_before, deps_after):
      print 'Run "deps.py install" to reinstall dependencies when ready.'
    else:
      # No changes? Just put glide.lock back as it was, since new glide.lock
      # differs only in not very useful 'updated' timestamp field.
      write_file(os.path.join(workspace, '.vendor', 'glide.lock'), lock_before)

    # Copy modified yamls back only on success.
    shutil.copy(
        os.path.join(workspace, '.vendor', 'glide.yaml'),
        os.path.join(workspace, 'deps.yaml'))
    shutil.copy(
        os.path.join(workspace, '.vendor', 'glide.lock'),
        os.path.join(workspace, 'deps.lock'))

  except Exception:
    # Remove 'applied.lock' to make sure 'deps.py install' reinstalls
    # the packages next time, fixing the state of .vendor/.
    applied_lock = os.path.join(workspace, '.vendor', APPLIED_LOCK)
    if os.path.exists(applied_lock):
      os.remove(applied_lock)

    print >> sys.stderr, BANNER_START
    print >> sys.stderr, (
        '%s was probably left in an inconsistent state!\n' %
        os.path.join(workspace, '.vendor'))
    print >> sys.stderr, (
        'You may want to remove it completely and build it again by running\n'
        '"deps.py install".')
    print >> sys.stderr, BANNER_END
    raise

  finally:
    # Undo everything.
    os.remove(os.path.join(workspace, '.vendor', 'glide.lock'))
    os.remove(os.path.join(workspace, '.vendor', 'glide.yaml'))
    os.rmdir(src_path) # must still be empty
    os.rename(vendor_path, src_path)


def call(workspace, tool, args):
  """Invokes a tool from GOROOT/bin, setting GOPATH to <workspace>/.vendor.

  Note that 'glide' is installed by bootstrap.py into GOROOT/bin too. Raises
  CallFailed exception on errors.

  Args:
    workspace: a directory where deps.yaml is located.
    tool: name of an exectuable to call, e.g. "go" or "glide".
    args: additional command line arguments to pass to it.
  """
  sfx = '.exe' if sys.platform == 'win32' else ''
  cmd = [os.path.join(TOOLSET_ROOT, 'go', 'bin', tool + sfx)] + args

  # Completely replace any existing Go env vars.
  env = os.environ.copy()
  env['GOROOT'] = os.path.join(TOOLSET_ROOT, 'go')
  env['GOPATH'] = os.path.join(workspace, '.vendor')
  env['GOBIN'] = os.path.join(workspace, '.vendor', 'bin')

  # Glide searched for 'go' in PATH. Make it available.
  env['PATH'] = os.path.join(env['GOROOT'], 'bin') + os.pathsep + env['PATH']

  ret_code = subprocess.call(cmd, env=env, cwd=env['GOPATH'])
  if ret_code:
    raise CallFailed(
        '"%s %s" FAILED, see the log' % (tool, ' '.join(args)))


def read_file(path):
  """Returns contents of a given file or None if not readable."""
  try:
    with open(path, 'rb') as f:
      return f.read()
  except IOError:
    return None


def write_file(path, blob):
  """Writes a blob into a file."""
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


def grab_doc(func):
  """Extracts help for CLI from a function doc string."""
  return func.__doc__.splitlines()[0].lower().strip('.')


################################################################################
## Subcommands.


def install(workspace, force=False):
  """Installs all dependencies from deps.lock into .vendor/ GOPATH.

  Args:
    workspace: a directory where deps.yaml is located.
    force: if True, will forcefully rebuild .vendor even if it is up-to-date.
  """
  required = read_file(os.path.join(workspace, 'deps.lock'))
  if not force:
    installed = read_file(os.path.join(workspace, '.vendor', APPLIED_LOCK))
    if installed == required:
      return 0

  # Glide is supposed to delete vendored packages that are no longer specified
  # in glide.lock, but it doesn't (at least in v0.10.1), even if '--delete' and
  # '--force' is used. So nuke entire .vendor/* and refetch everything from
  # scratch. It also helps us to avoid various lingering state corruption in
  # .vendor/*.
  remove_directory(os.path.join(workspace, '.vendor'))

  # Use glide to fetch all the code.
  with unhack_vendor(workspace):
    call(workspace, 'glide', ['install'])

  # Prebuild all packages specified in deps.lock into *.a archives. It should
  # speed up compilation of code that depends on them. Note that doing simple
  # "go install ./src/..." won't work, because it will try to compiled ALL
  # subpackages of vendored repos, not only ones we use. Since we don't use
  # them, their dependencies weren't fetched into .vendor/*, and they won't
  # compile.
  print 'Rebuilding libraries...'
  assert read_file(os.path.join(workspace, 'deps.lock')) == required
  deps = parse_glide_lock(required)
  call(workspace, 'go', ['install', '-v'] + flatten_deps(deps))

  # We will install only interesting subset of executables below. Nuke
  # everything else to avoid polluting PATH with unimportant stuff.
  remove_directory(os.path.join(workspace, '.vendor', 'bin'))

  # Install only stuff that was vendored via glide. That way we can support
  # multiple workspaces with third party code, but keep a single VENDORED_TOOLS
  # whitelist of "important stuff". If a workspace is not interested in having
  # a tool present, it just doesn't list it in deps.yaml.
  to_install = []
  for pkg in VENDORED_TOOLS:
    pkg_path = os.path.join(
        workspace, '.vendor', 'src', pkg.replace('/', os.sep))
    if os.path.isdir(pkg_path):
      to_install.append(pkg)

  print 'Rebuilding tools...'
  call(workspace, 'go', ['install', '-v'] + to_install)

  # Put a marker file that indicates we successfully installed all deps.
  write_file(os.path.join(workspace, '.vendor', APPLIED_LOCK), required)
  return 0


def update(workspace):
  """Updates deps.lock file to point to most recent versions of packages.

  Args:
    workspace: a directory where deps.yaml is located.
  """
  with unhack_vendor(workspace):
    call(workspace, 'glide', ['update', '--force', '--delete'])
  return 0


def add(workspace, packages):
  """Adds a bunch of packages into deps.yaml.

  Args:
    workspace: a directory where deps.yaml is located.
    packages: a list of go packages to add to deps.yaml.
  """
  with unhack_vendor(workspace):
    call(workspace, 'glide', ['get', '--force'] + packages)
  return 0


def remove(workspace, packages):
  """Removes a bunch of packages from deps.yaml.

  Args:
    workspace: a directory where deps.yaml is located.
    packages: a list of go packages to remove from deps.yaml.
  """
  with unhack_vendor(workspace):
    call(workspace, 'glide', ['remove'] + packages)
  return 0


def main(args):
  parser = argparse.ArgumentParser(
      description='Utility to manage go vendored dependencies.')
  parser.add_argument(
      '--workspace', action='store', default=WORKSPACE,
      help='directory with deps.yaml, deps will be installed in .vendor subdir')

  subparsers = parser.add_subparsers()

  parser_install = subparsers.add_parser('install', help=grab_doc(install))
  parser_install.set_defaults(action=install)
  parser_install.add_argument(
      '--force', action='store_true', default=False,
      help='forcefully reinstall all dependencies')

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

  opts = parser.parse_args(args)
  try:
    if opts.action == install:
      return install(opts.workspace, opts.force)
    if opts.action == update:
      return update(opts.workspace)
    if opts.action == add:
      return add(opts.workspace, opts.pkg)
    if opts.action == remove:
      return remove(opts.workspace, opts.pkg)
    assert False, 'Unreachable'
  except CallFailed as exc:
    print >> sys.stderr, str(exc)
    return 1


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
