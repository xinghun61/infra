#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Runs Go unit tests verifying 100% code coverage.

Expects Go toolset to be in PATH, GOPATH and GOROOT correctly set. Use ./env.py
to set them up.

Usage:
  test.py [root package path]

By default runs all tests for infra/*.
"""

import collections
import errno
import os
import re
import shutil
import subprocess
import sys


# infra/go/
INFRA_GO_DIR = os.path.dirname(os.path.abspath(__file__))


# Packages to skip completely.
BLACKLIST = [
  'infra/hello_world',
]


# Packages with not 100% code coverage, to exclude from code coverage check.
COVER_BLACKLIST = [
]


# Return value of run_package_tests.
TestResults = collections.namedtuple('TestResults', [
  # Name of the package being tested.
  'package',
  # True if all unit tests pass.
  'tests_pass',
  # Percentage of source code covered, or None if not available.
  'coverage_percent',
  # True if coverage report is enabled and coverage is at 100%.
  'coverage_pass',
  # Path to HTML file with coverage report.
  'coverage_html',
  # Std output of the tests.
  'stdout',
  # Std error of the tests.
  'stderr',
])


def check_go_available():
  """Returns True if go executable is in the PATH."""
  try:
    subprocess.check_output(['go', 'version'], stderr=subprocess.STDOUT)
    return True
  except subprocess.CalledProcessError:
    return False
  except OSError as err:
    if err.errno == errno.ENOENT:
      return False
    raise


def makedirs(path):
  """Same as os.makedirs, but doesn't fail if path exists."""
  try:
    os.makedirs(path)
  except OSError as err:
    if err.errno != errno.EEXIST:
      raise


def list_packages(package_root):
  """Returns a list of Go packages under |package_root| package path."""
  out = subprocess.check_output(['go', 'list', '%s/...' % package_root])
  return filter(bool, out.splitlines())


def run_package_tests(package, coverage_file):
  """Runs unit tests for a single package.

  Optionally perform code coverage check for that package. Package tests should
  cover 100% of package code. Tests from other packages do not contribute to
  total code coverage for the package.

  Args:
    package: package name (e.g. infra/package).
    coverage_file: prefix for code coverage files (*.out and *.html), or None to
        disable code coverage report.

  Returns:
    TestResults tuple.
  """
  assert coverage_file is None or os.path.isabs(coverage_file), coverage_file

  # Ask go test to collect coverage to a file, to convert it to HTML later.
  cmd = ['go', 'test', package]
  if coverage_file:
    makedirs(os.path.dirname(coverage_file))
    coverage_out = '%s.out' % coverage_file
    cmd.extend(['-coverprofile', coverage_out])
  else:
    coverage_out = None

  # Run the test.
  proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  out, err = proc.communicate()
  if proc.returncode:
    return TestResults(
        package=package,
        tests_pass=False,
        coverage_percent=None,
        coverage_pass=False,
        coverage_html=None,
        stdout=out,
        stderr=err)

  # Convert coverage report to fancy HTML. Coverage report may be missing if
  # package has no tests at all.
  if os.path.exists(coverage_out):
    coverage_html = '%s.html' % coverage_file
    subprocess.check_output(
        ['go', 'tool', 'cover', '-html', coverage_out, '-o', coverage_html],
        stderr=subprocess.STDOUT)
  else:
    coverage_html = None

  # TODO: figure out how to parse coverage.out to extract coverage % and
  # uncovered lines.
  coverage = None
  if coverage_file:
    match = re.search('coverage: ([\d\.]+)% of statements', out)
    coverage = float(match.group(1)) if match else None
  return TestResults(
      package=package,
      tests_pass=True,
      coverage_percent=coverage,
      coverage_pass=not coverage_file or coverage == 100.0,
      coverage_html=coverage_html,
      stdout=out,
      stderr=err)


def run_tests(package_root, coverage_dir, blacklist, cover_blacklist):
  """Runs an equivalent of 'go test <package_root>/...'.

  Collects code coverage. Prints reports about failed tests or non 100% covered
  packages to stdout.

  Args:
    package_root: base go package path to run test on.
    coverage_dir: base directory to put coverage reports to, will be completely
        overwritten.
    blacklist: list of packages to skip.
    cover_blacklist: list of packages not to check for coverage.

  Returns:
    0 if all tests pass with 100% coverage, 1 otherwise.
  """
  if not check_go_available():
    print 'Can\'t find Go executable in PATH.'
    print 'Use ./env.py python test.py'
    return 1

  # Coverage dir is always overwritten with new coverage reports.
  if os.path.exists(coverage_dir):
    shutil.rmtree(coverage_dir)
    makedirs(coverage_dir)

  # Code coverage report requires tests to be run against a single package, so
  # discover all individual packages.
  packages = [p for p in list_packages(package_root) if p not in blacklist]
  if not packages:
    print 'No tests to run'
    return 0

  # TODO: Run tests in parallel, basically implement parallel
  # map(run_package_tests, package). run_package_tests already captures all
  # output.
  failed = []
  bad_cover = []
  for pkg in packages:
    coverage_file = None
    if pkg not in cover_blacklist:
      coverage_file = os.path.join(coverage_dir, pkg.replace('/', os.sep))
    result = run_package_tests(pkg, coverage_file)
    if result.tests_pass and result.coverage_pass:
      sys.stdout.write('.')
    elif not result.tests_pass:
      sys.stdout.write('F')
      failed.append(result)
    else:
      sys.stdout.write('C')
      bad_cover.append(result)
  print

  if bad_cover:
    print
    print 'Not 100% code coverage! Fix it.'
    for i, r in enumerate(bad_cover):
      coverage_str = 'missing, no tests?'
      if r.coverage_percent is not None:
        coverage_str = '%.1f%%' % r.coverage_percent
      report_url = 'none'
      if r.coverage_html:
        report_url = 'file://%s' % r.coverage_html
      print '-' * 80
      print 'PACKAGE: %s' % r.package
      print '-' * 80
      print '  coverage: %s' % coverage_str
      print '  report:   %s' % report_url
      print '-' * 80
      if i != len(bad_cover) - 1:
        print

  if failed:
    print
    for i, r in enumerate(failed):
      print '-' * 80
      print 'PACKAGE: %s' % r.package
      print '-' * 80
      print r.stdout,
      if r.stderr.strip():
        print r.stderr.strip()
      print '-' * 80
      if i != len(failed) - 1:
        print

  return int(bool(bad_cover or failed))


def main(args):
  if not args:
    package_root = 'infra'
  elif len(args) == 1:
    package_root = args[0]
  else:
    print >> sys.stderr, sys.modules['__main__'].__doc__.strip()
    return 1
  return run_tests(
      package_root=package_root,
      coverage_dir=os.path.join(INFRA_GO_DIR, 'coverage'),
      blacklist=BLACKLIST,
      cover_blacklist=COVER_BLACKLIST)


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
