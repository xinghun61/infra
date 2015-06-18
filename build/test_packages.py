#!/usr/bin/env python
# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests generated CIPD packages.

Supposed to be invoked after build.py has run. Uses packages from out/*.cipd and
tests from tests/*.py.

Assumes cipd client is built in ../go/bin/cipd (true after build.py has run).
"""

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile


# Root of infra.git repository.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# .exe on Windows.
EXE_SUFFIX = '.exe' if sys.platform == 'win32' else ''


class TestException(Exception):
  pass


def print_title(title):
  """Pretty prints a banner to stdout."""
  sys.stdout.flush()
  sys.stderr.flush()
  print
  print '-' * 80
  print title
  print '-' * 80


def get_docstring(test_script):
  """Hacky way to grab a first line of a module docstring using regexps."""
  with open(test_script, 'rt') as f:
    text = f.read()
  m = re.match(r'^.*"""(.*?)"""', text, re.DOTALL)
  if not m:
    return None
  return m.group(1).strip().splitlines()[0]


def run_test(cipd_client, package, work_dir, test_script):
  """Extracts a package to a dir and runs test_script with cwd == work_dir."""
  print_title('Deploying %s' % os.path.basename(package))
  cmd_line = ['cipd', 'pkg-deploy', '-root', work_dir, package]
  print ' '.join(cmd_line)
  if subprocess.call(args=cmd_line, executable=cipd_client):
    raise TestException('Failed to install %s, see logs' % package)

  print_title(get_docstring(test_script) or 'Running tests...')
  cmd_line = ['python', test_script]
  print '%s in %s' % (' '.join(cmd_line), work_dir)
  env = os.environ.copy()
  env.pop('PYTHONPATH', None)
  ret = subprocess.call(
      args=cmd_line, executable=sys.executable, env=env, cwd=work_dir)
  if ret:
    raise TestException('Non zero exit code (%d)' % ret)


def run(
    cipd_client,
    package_out_dir,
    package_tests_dir,
    work_dir,
    packages):
  """Deployes build *.cipd package locally and runs tests against them.

  Used to verify the packaged code works when installed as CIPD package, it is
  important for infra_python package that has non-trivial structure.

  Args:
    cipd_client: path to cipd client executable.
    package_out_dir: where to search for built packages.
    work_dir: where to install/update packages into.
    packages: names of *.cipd files in package_out_dir or [] for all.

  Returns:
    0 on success, 1 or error.
  """
  if not os.access(cipd_client, os.X_OK):
    print >> sys.stderr, (
        'CIPD client at %s doesn\'t exist or not runnable. Run build.py to '
        'build it.' % cipd_client)
    return 1

  # Discover what to test.
  paths = []
  if not packages:
    paths = glob.glob(os.path.join(package_out_dir, '*.cipd'))
  else:
    for name in packages:
      abs_path = os.path.join(package_out_dir, name)
      if not os.path.isfile(abs_path):
        raise TestException('No such package file: %s' % name)
      paths.append(abs_path)
  paths = sorted(paths)

  # Run all tests sequentially. There're like 2 of them tops.
  nuke_temp = False
  if not work_dir:
    work_dir = tempfile.mkdtemp(suffix='cipd_test')
    nuke_temp = True
  work_dir = os.path.abspath(work_dir)
  try:
    fail = False
    for path in paths:
      name = os.path.splitext(os.path.basename(path))[0]
      test_script = os.path.join(package_tests_dir, '%s.py' % name)
      if not os.path.isfile(test_script):
        print 'Skipping tests for %s - no such file: %s' % (name, test_script)
        continue
      try:
        run_test(
            cipd_client=cipd_client,
            package=path,
            work_dir=os.path.join(work_dir, name),
            test_script=test_script)
        print ''
        print 'PASS'
      except TestException as exc:
        print >> sys.stderr, ''
        print >> sys.stderr, 'FAILED! ' * 10
        print >> sys.stderr, 'Tests for %s failed: %s' % (name, exc)
        fail = True
    return 1 if fail else 0
  finally:
    if nuke_temp:
      try:
        shutil.rmtree(work_dir, ignore_errors=True)
      except OSError as exc:
        print >> sys.stderr, 'Failed to delete %s: %s' % (work_dir, exc)


def main(
    args,
    go_workspace=os.path.join(ROOT, 'go'),
    package_out_dir=os.path.join(ROOT, 'build', 'out'),
    package_tests_dir=os.path.join(ROOT, 'build', 'tests')):
  parser = argparse.ArgumentParser(description='Tests infra CIPD packages')
  parser.add_argument(
      'packages', metavar='NAME', type=str, nargs='*',
      help='name of a build package file in build/out/* to deploy and test')
  parser.add_argument(
      '--work-dir', metavar='DIR', dest='work_dir',
      help='directory to deploy packages into (temporary dir by default)')
  args = parser.parse_args(args)
  return run(
      os.path.join(go_workspace, 'bin', 'cipd' + EXE_SUFFIX),
      package_out_dir,
      package_tests_dir,
      args.work_dir,
      args.packages)


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
