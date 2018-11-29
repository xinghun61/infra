#!/usr/bin/env python
# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Checks go package imports to ensure they're not too wacky."""

import os
import subprocess
import sys


# This lists the go packages to scan. Can be any package pattern accepted
# by `go list`
PKGS_TO_CHECK = [
  'infra/...',
  'go.chromium.org/...',
]


# We have imports which only occur in some OS-specific .go files, so run
# `go list` under these $GOOS values to catch 'em all.
GOOS_TO_CHECK = (
  'darwin',
  'linux',
  'windows',
)

SCRIPT_DIR = os.path.realpath(os.path.dirname(__file__))

DEVNULL = open(os.devnull, 'wb')


def scan_os_async(goos):
  env = os.environ.copy()
  env['GOOS'] = goos

  FMT = (
    '{{$pkg := .ImportPath}}'
    '{{range .Imports}}'
      '{{printf "%s %s\\n" $pkg .}}'
    '{{end}}'
    '{{range .TestImports}}'
      '{{printf "%s %s\\n" $pkg .}}'
    '{{end}}'
  )
  p = subprocess.Popen(
    ['go', 'list', '-f', FMT] + PKGS_TO_CHECK, env=env,
    stdout=subprocess.PIPE, stderr=DEVNULL)
  return lambda: p.communicate()[0]


def read_and_merge(*go_list_data_func):
  ret = {}
  for fn in go_list_data_func:
    for line in fn().splitlines():
      pkgname, import_pkg = line.split()
      ret.setdefault(import_pkg, set()).add(pkgname)
  return ret


def apply_whitelist(import_to_users, whitelist):
  used_whitelist = set()

  def matches(imp):
    for x in whitelist:
      if imp.startswith(x):
        used_whitelist.add(x)
        return True
    return False

  for imp in import_to_users.keys():
    if matches(imp):
      del import_to_users[imp]
      continue

    # Does it look like stdlib?
    if '.' not in imp.split('/')[0]:
      del import_to_users[imp]
      continue

  return whitelist - used_whitelist


def load_whitelist(path):
  ret = set()
  with open(path, 'r') as f:
    for line in f.readlines():
      line = line.strip()
      if not line or line.startswith('#'):
        continue
      ret.add(line)
  return set(ret)


def main():
  whitelist = load_whitelist(os.path.join(SCRIPT_DIR, 'check_deps.whitelist'))
  import_to_users = read_and_merge(*map(scan_os_async, GOOS_TO_CHECK))

  unused_whitelist = apply_whitelist(import_to_users, whitelist)

  if import_to_users:
    pkg_to_bad_imports = {}
    for bad_import, pkg_users in sorted(import_to_users.items()):
      for pkg in pkg_users:
        pkg_to_bad_imports.setdefault(pkg, []).append(bad_import)

    print 'Invalid Go package dependencies:'
    for pkg, bad_imports in sorted(pkg_to_bad_imports.items()):
      print '  in %s' % pkg
      for imp in bad_imports:
        print '    - %s' % imp
      print

  if unused_whitelist:
    print 'Unused whitelist entries:'
    for entry in sorted(unused_whitelist):
      print '  %s' % entry

  if import_to_users or unused_whitelist:
    sys.exit(1)


if __name__ == '__main__':
  main()
