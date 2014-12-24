#!/usr/bin/env python
# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Runs Go unit tests verifying code coverage.

Expects Go toolset to be in PATH, GOPATH and GOROOT correctly set. Use ./env.py
to set them up.

Usage:
  test.py [root package path]

By default runs all tests for infra/*.
"""

import collections
import errno
import json
import os
import re
import shutil
import subprocess
import sys


# infra/go/
INFRA_GO_DIR = os.path.dirname(os.path.abspath(__file__))

# Allowed keys in *.infra_testing dict.
EXPECTED_INFO_KEYS = frozenset([
  'skip_testing',
  'expected_coverage_min',
  'expected_coverage_max',
])


# Return value of run_package_tests.
TestResults = collections.namedtuple('TestResults', [
  # Name of the package being tested.
  'package',
  # True if all unit tests pass.
  'tests_pass',
  # Percentage of source code covered, or None if not available.
  'coverage_percent',
  # Expected coverage to pass code coverage test, tuple (min, max) or None.
  'coverage_expected',
  # True if coverage report is enabled and coverage is acceptable.
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


_package_info_cache = {}

def get_package_info(package):
  """Returns contents of <package>/<name>.infra_testing file or {} if missing.

  *.infra_testing contains a JSON dict with the following keys:
  {
    // Do not run tests in this package at all. Default 'false'.
    "skip_testing": boolean,
    // Minimum allowed code coverage percentage, see below. Default '100'.
    "expected_coverage_min": number,
    // Maximum allowed code coverage percentage, see below. Default '100'.
    "expected_coverage_max": number
  }

  expected_coverage_min and expected_coverage_max set a boundary on what the
  code coverage percentage of the package is expected to be. test.py will fail
  if code coverage is less than 'expected_coverage_min' (meaning the package
  code has degraded), or larger than 'expected_coverage_max' (meaning the
  package code has improved and expected_coverage_min should probably be changed
  too).

  Setting expected_coverage_min=0 and expected_coverage_max=100 effectively
  disables code coverage checks for a package (test.py still will generate HTML
  coverage reports though).
  """
  # Performs actual reading if the info is not in cache already.
  def do_read():
    # Name of the package is the last component.
    if '/' not in package:
      name = package
    else:
      name = package.split('/')[-1]
    # Resolve package name to a file system directory with source code.
    path = subprocess.check_output(['go', 'list', '-f={{.Dir}}', package])
    info_file = os.path.join(path.strip(), '%s.infra_testing' % name)
    try:
      with open(info_file, 'r') as f:
        info = json.load(f)
      if not isinstance(info, dict):
        print >> sys.stderr, 'Expecting to find dict in %s' % info_file
        return {}
      if not EXPECTED_INFO_KEYS.issuperset(info):
        print >> sys.stderr, 'Unexpected keys found in %s: %s' % (
            info_file, set(info) - EXPECTED_INFO_KEYS)
      return info
    except IOError:
      return {}
    except ValueError:
      print >> sys.stderr, 'Not a valid JSON file: %s' % info_file
      return {}

  if package not in _package_info_cache:
    _package_info_cache[package] = do_read()
  return _package_info_cache[package]


def should_skip(package):
  """True to skip package tests, reads 'skip_testing' from *.infra_testing."""
  return get_package_info(package).get('skip_testing', False)


def get_expected_coverage(package):
  """Returns allowed code coverage percentage as a pair (min, max)."""
  info = get_package_info(package)
  min_cover = info.get('expected_coverage_min', 100.0)
  max_cover = info.get('expected_coverage_max', 100.0)
  if max_cover < min_cover:
    max_cover = min_cover
  return (min_cover, max_cover)


def list_packages(package_root):
  """Returns a list of Go packages under |package_root| package path."""
  out = subprocess.check_output(['go', 'list', '%s/...' % package_root])
  return filter(bool, out.splitlines())


def run_package_tests(package, coverage_file):
  """Runs unit tests for a single package.

  Also perform code coverage check for that package. Tests from other packages
  do not contribute to total code coverage for the package. Required code
  coverage percentage is read from <package>/<name>.infra_testing file.

  Args:
    package: package name (e.g. infra/package).
    coverage_file: prefix for code coverage files (*.out and *.html).

  Returns:
    TestResults tuple.
  """
  assert os.path.isabs(coverage_file), coverage_file

  # Ask go test to collect coverage to a file, to convert it to HTML later.
  cmd = ['go', 'test', package]
  makedirs(os.path.dirname(coverage_file))
  coverage_out = '%s.out' % coverage_file
  cmd.extend(['-coverprofile', coverage_out])

  # Run the test.
  proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  out, err = proc.communicate()
  if proc.returncode:
    return TestResults(
        package=package,
        tests_pass=False,
        coverage_percent=None,
        coverage_expected=None,
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

  # Assume 0% coverage if package does not define any tests.
  match = re.search('coverage: ([\d\.]+)% of statements', out)
  coverage = float(match.group(1)) if match else 0
  coverage_expected = get_expected_coverage(package)
  coverage_pass = (
      coverage >= coverage_expected[0] and coverage <= coverage_expected[1])
  return TestResults(
      package=package,
      tests_pass=True,
      coverage_percent=coverage,
      coverage_expected=coverage_expected,
      coverage_pass=coverage_pass,
      coverage_html=coverage_html,
      stdout=out,
      stderr=err)


def run_tests(package_root, coverage_dir):
  """Runs an equivalent of 'go test <package_root>/...'.

  Collects code coverage. Prints reports about failed tests or non sufficiently
  covered packages to stdout.

  Args:
    package_root: base go package path to run test on.
    coverage_dir: base directory to put coverage reports to, will be completely
        overwritten.

  Returns:
    0 if all tests pass with acceptable code coverage, 1 otherwise.
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
  packages = [p for p in list_packages(package_root) if not should_skip(p)]
  if not packages:
    print 'No tests to run'
    return 0

  # TODO: Run tests in parallel, basically implement parallel
  # map(run_package_tests, package). run_package_tests already captures all
  # output.
  failed = []
  bad_cover = []
  for pkg in packages:
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
    sys.stdout.flush()
  print

  if bad_cover:
    print
    print 'Code coverage is not what it is expected to be.'
    for i, r in enumerate(bad_cover):
      coverage_str = 'missing, no tests?'
      coverage_expected_str = '???'
      if r.coverage_percent is not None:
        if r.coverage_percent == 0.0:
          coverage_str = '0.0% no tests?'
        else:
          coverage_str = '%.1f%%' % r.coverage_percent
      if r.coverage_expected is not None:
        coverage_expected_str = '[%.1f%%, %.1f%%]' % r.coverage_expected
      report_url = 'none'
      if r.coverage_html:
        report_url = 'file://%s' % r.coverage_html
      print '-' * 80
      print 'PACKAGE: %s' % r.package
      print '-' * 80
      print '  coverage: %s' % coverage_str
      print '  expected: %s' % coverage_expected_str
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
  return run_tests(package_root, os.path.join(INFRA_GO_DIR, 'coverage'))


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
