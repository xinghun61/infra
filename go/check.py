#!/usr/bin/env vpython
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Python wrapper for various Go tools.

Intended to be used from a PRESUBMIT check.
"""

import os
import subprocess
import sys

WORKSPACE_ROOT = os.path.dirname(os.path.abspath(__file__))


def group_by_dir(filestream):
  """Generates directories of the files in the given filestream.

  If the filestream has paths in sorted order, then directories
  shouldn't be repeated.
  """
  prefix = None
  group = []
  for fname in filestream:
    dirname = os.path.dirname(fname)
    if dirname != prefix:
      if group:
        yield prefix
      prefix = dirname
      group = []
    group.append(fname)
  if group:
    yield prefix


def mk_checker(*tool_name):
  """Creates and returns a "main" function.

  The returned function invokes the tool and returns the retcode-style result.
  """
  tool_cmd = list(tool_name)

  def _inner(_verbose, filestream):
    found_errs = []
    retcode = 0

    for dpath in group_by_dir(filestream):
      proc = subprocess.Popen(
          tool_cmd + [dpath],
          stdout=subprocess.PIPE,
          stderr=subprocess.STDOUT)
      out = proc.communicate()[0].strip()
      if out or proc.returncode:
        found_errs.append(out or 'Unrecognized error')
        retcode = proc.returncode or 1

    for err in found_errs:
      print err
    return retcode
  return _inner


def gofmt_main(verbose, filestream):
  """Reads list of paths from stdin.

  Expects go toolset to be in PATH (use ./env.py to set this up).
  """
  def check_file(path):
    proc = subprocess.Popen(
        ['gofmt', '-s', '-d', path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    out, err = proc.communicate()
    if proc.returncode:
      print err,
      return False
    if out:
      if verbose:
        print out,
      return False
    return True

  bad = []
  for fpath in filestream:
    if not check_file(fpath):
      bad.append(fpath)
  if bad:
    root = WORKSPACE_ROOT.rstrip(os.sep) + os.sep
    print 'Badly formated Go files:'
    for p in bad:
      if p.startswith(root):
        p = p[len(root):]
      print '  %s' % p
    print
    print 'Consider running \'gofmt -s -w /path/to/infra\''
  return 0 if not bad else 1


def show_help():
  print 'Usage: check.py [--verbose] <tool>'
  print 'List of file paths to operate is read from stdin.'
  print 'Available tools:'
  for x in TOOL_FUNC:
    print "  *", x
  sys.exit(1)


def main(args):
  if len(args) < 1 or args[0] not in TOOL_FUNC:
    show_help()

  verbose = '--verbose' in args

  def filestream():
    for path in sys.stdin:
      path = path.rstrip()
      if path:
        yield path

  return TOOL_FUNC[args[0]](verbose, filestream())


TOOL_FUNC = {
  "govet": mk_checker("go", "vet"),
  "golint": mk_checker("golint"),
  "gofmt": gofmt_main,
}


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
