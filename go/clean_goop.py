#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Suggests what Goop file entries can be removed.

Horribly slow, but simple. Evaluates recursive dependencies of all packages
in infra/go/... (including github ones) and compares them against Goopfile.lock
entries.

Supposed to be called under activated go environment.
"""

import os
import subprocess
import sys

# For VENDORED_TOOLS.
import bootstrap


GO_DIR = os.path.dirname(os.path.abspath(__file__))


# List of Goopfile.lock entries we want to keep because they are imported only
# when building on Windows (and thus detected as unused when script is used
# on Linux).
EXCEPTIONS = [
  'github.com/mattn/go-isatty',
  'github.com/olekukonko/ts',
]


def dumbcache(f):
  """Simple cache decorator for functions with hashable args."""
  cache = {}
  def wrapper(*args):
    if args not in cache:
      cache[args] = f(*args)
    return cache[args]
  return wrapper


@dumbcache
def get_deps(pkg_glob):
  """Returns a set of imported dependencies."""
  cmd = ['go', 'list', '-f', '{{ join .Deps "\\n" }}', pkg_glob]
  print 'Running ', cmd
  deps = subprocess.check_output(cmd).strip()
  return sorted(set(deps.splitlines()))


@dumbcache
def get_all_goop():
  """Returns a list of packages specified in Goopfile.lock."""
  with open(os.path.join(GO_DIR, 'Goopfile.lock')) as f:
    return [l.split()[0] for l in f]


def get_used_goop(deps):
  """Returns set of packages in Goopfile.lock that cover a dependency list."""
  used = set()
  for pkg in get_all_goop():
    for dep in deps:
      # If goop pkg covers at least one dependency, it is used.
      if dep == pkg or dep.startswith(pkg + '/'):
        used.add(pkg)
        break
  return used


def main():
  all_deps = set(EXCEPTIONS)

  # We want to enumerate packages in infra/go/src/... and only them (not all
  # packages in GOPATH, since we don't want to enumerate vendored packages).
  # A package glob needs to start with '.' or '..' to be interpreted as file
  # system path. See 'go help packages'.
  go_dir_rel = os.path.relpath(GO_DIR)
  assert go_dir_rel.startswith('.')
  all_deps.update(get_deps(os.path.join(go_dir_rel, 'src', '...')))

  # Tools build by bootstrap script may not be directly referenced by src/ code.
  for tool in bootstrap.VENDORED_TOOLS:
    all_deps.add(tool)
    all_deps.update(get_deps(tool))

  # all_deps is all direct dependencies of infra/go/src code. Find what part of
  # Goopfile.lock covers them. Then recurse into them. Note that Goopfile
  # may specify a parent package of a package used in actual code. So recursing
  # into deps of that parent package may reveal more dependencies.
  goop_deps = set()
  while True:
    new_goop_deps = get_used_goop(all_deps)
    if new_goop_deps == goop_deps:
      break
    goop_deps = new_goop_deps
    for pkg in goop_deps:
      all_deps.update(get_deps(pkg + '/...'))

  # Find what is not used.
  unused = [p for p in get_all_goop() if p not in goop_deps]
  if unused:
    print '-' * 80
    print 'Consider removing from Goopfile the following packages:'
    print '\n'.join(unused)
  else:
    print 'Hooray! All Goopfile packages seem to be in use.'

  return 0


if __name__ == '__main__':
  sys.exit(main())
