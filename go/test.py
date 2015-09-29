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
import time

from multiprocessing.pool import ThreadPool


# infra/go/
INFRA_GO_DIR = os.path.dirname(os.path.abspath(__file__))

# Allowed keys in *.infra_testing dict.
EXPECTED_INFO_KEYS = frozenset([
  'skip_testing',
  'expected_coverage_min',
  'expected_coverage_max',
  'build_tags',
  'skip_checks',
])

MAGIC_FILE_EXT = 'infra_testing'


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


def get_goos():
  """Converts sys.platform to GOOS value."""
  if sys.platform.startswith('win'):
    return 'windows'
  if sys.platform.startswith('darwin'):
    return 'darwin'
  if sys.platform.startswith('linux'):
    return 'linux'
  raise ValueError('Unrecognized platform: %s' % sys.platform)


def parse_info_file(info_file):
  """Returns contents of <package>/<name>.infra_testing file or {} if missing.

  *.infra_testing contains a JSON dict with the following keys:
  {
    // Do not run tests in this package at all. Default 'false'.
    "skip_testing": a list of platforms (GOOS) to skip tests on,
    // Minimum allowed code coverage percentage, see below. Default '100'.
    "expected_coverage_min": number,
    // Maximum allowed code coverage percentage, see below. Default '100'.
    "expected_coverage_max": number
  }

  expected_coverage_min and expected_coverage_max set a boundary on what the
  code coverage percentage of the package is expected to be. test.py will fail
  if code coverage is less than 'expected_coverage_min' (meaning the package
  code has degraded), or larger than 'expected_coverage_max' (meaning the
  package code has improved and expected_coverage_min should probably be
  changed too).

  Setting expected_coverage_min=0 and expected_coverage_max=100 effectively
  disables code coverage checks for a package (test.py still will generate
  HTML coverage reports though).
  """
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


class SkipCache(object):
  """Extremely basic cache for tracking the skipped-ness of files. Used for
  check_*.py scripts in this folder, but since it deals with the infra_testing
  magic files, its implementation belongs here."""

  def __init__(self, check_name):
    """check_name is the name that would show up in the 'skip_checks' field of
    an infra_testing magic file."""
    self.cache = {}
    self.check_name = check_name

  def is_skipped(self, file_or_dirpath):
    dirname = os.path.abspath(file_or_dirpath)
    if os.path.isfile(dirname):
      dirname = os.path.dirname(dirname)
    if dirname not in self.cache:
      base = os.path.basename(dirname)
      fullpath = os.path.join(dirname, base+"."+MAGIC_FILE_EXT)
      info = parse_info_file(fullpath)
      self.cache[dirname] = self.check_name in info.get("skip_checks", ())
    return self.cache[dirname]


class PackageBundle(object):
  """Bunch of packages rooted at a single package."""

  def __init__(self, root):
    out = subprocess.check_output(
        ['go', 'list', '-f', '{{.ImportPath}} {{.Dir}}', '%s/...' % root])
    self.packages = {}
    for line in out.splitlines():
      line = line.strip()
      if not line:
        continue
      pkg, path = line.split(' ', 1)
      self.packages[pkg] = path

  def get_magic_file_path(self, package, extension):
    """Full package name -> path to <package>/<package name>.<extension>."""
    # Name of the package is the last component.
    if '/' not in package:
      name = package
    else:
      name = package.split('/')[-1]
    return os.path.join(self.packages[package], '%s.%s' % (name, extension))

  def get_package_info(self, package):
    return parse_info_file(self.get_magic_file_path(package, MAGIC_FILE_EXT))

  def should_skip(self, package):
    """True to skip package tests, reads 'skip_testing' from *.infra_testing."""
    skip = self.get_package_info(package).get('skip_testing', [])
    if not isinstance(skip, list):
      raise TypeError(
          '%s: "skip_testing" should be a list of platforms to skip tests on, '
          'got %r instead' % (package, skip))
    return get_goos() in skip

  def get_build_tags(self, package):
    """Build tags to use when building a package, read from *.infra_testing."""
    tags = self.get_package_info(package).get('build_tags', ())
    if tags:
      return '-tags='+(','.join(tags))
    return None

  def get_expected_coverage(self, package):
    """Returns allowed code coverage percentage as a pair (min, max)."""
    info = self.get_package_info(package)
    min_cover = info.get('expected_coverage_min', 100.0)
    max_cover = info.get('expected_coverage_max', 100.0)
    if max_cover < min_cover:
      max_cover = min_cover
    return (min_cover, max_cover)

  def get_goconvey_test_flags(self, package):
    """Reads <package>/*.goconvey file with flags for "go test" if it exists."""
    path = self.get_magic_file_path(package, 'goconvey')
    if os.path.exists(path):
      with open(path, 'r') as f:
        return f.read().strip().split()
    return []

  def build_install_package(self, package):
    """Builds+Installs a single package.

    'go install' is used to avoid having it dump superfluous binaries into the
    source tree (e.g. they go to the bin/ folder which is at least marginally
    useful).

    Returns:
      TestResults tuple.
    """
    cmd = ['go', 'install']
    build_tags = self.get_build_tags(package)
    if build_tags:
      cmd.append(build_tags)
    cmd.append(package)

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()
    passed = proc.returncode==0
    return TestResults(
        package=package,
        tests_pass=passed,
        coverage_percent=None,
        coverage_expected=None,
        coverage_pass=passed,
        coverage_html=None,
        stdout=out,
        stderr=err)

  def run_package_tests(self, package, coverage_file):
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
    build_tags = self.get_build_tags(package)
    if build_tags:
      cmd.append(build_tags)
    cmd.extend(self.get_goconvey_test_flags(package))
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
    coverage_expected = self.get_expected_coverage(package)
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


def reinstall_packages(packages, silent=False):
  """Rebuilds and reinstalls all given packages."""
  proc = subprocess.Popen(
      ['go', 'install', '-a'] + sorted(packages),
      stdout=subprocess.PIPE if silent else None,
      stderr=subprocess.PIPE if silent else None)
  proc.communicate()


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

  # PackageBundle is used to batch "go list ..." calls since they are too slow.
  bundle = PackageBundle(package_root)

  # Code coverage report requires tests to be run against a single package, so
  # discover all individual packages.
  skipped = []
  packages = []
  for p in sorted(bundle.packages):
    if bundle.should_skip(p):
      skipped.append(p)
    else:
      packages.append(p)

  # Silently rebuild everything (in particular recursively imported packages
  # from non-main GOPATH). Do not abort here yet on failure, since we want to
  # split failures by packages (it is done below). Note that we issue a full
  # rebuild (not just clean), because otherwise parallel 'go test' calls below
  # will bump into each other while trying to rebuild commonly references
  # dependencies.
  print 'Rebuilding dependencies...'
  started = time.time()
  reinstall_packages(skipped + packages, silent=True)
  print 'Finished in %.1f sec.' % (time.time() - started)
  print

  if skipped:
    print 'Build-only (see "skip_testing" in *.infra_testing):'
    for p in skipped:
      print '    %s' % p
    print

  if packages:
    print 'About to run tests for: '
    for p in packages:
      print '    %s' % p
  print '-' * 80

  # TODO(vadimsh): Windows seems to have problems building & testing go packages
  # in parallel (file locking issues). So don't build stuff in parallel on
  # Windows for now.
  tpool_size = 1 if sys.platform == 'win32' else len(packages)

  failed = []
  bad_cover = []
  tpool = ThreadPool(tpool_size)
  def run((pkg, build_only)):
    if not build_only:
      coverage_file = os.path.join(coverage_dir, pkg.replace('/', os.sep))
      return bundle.run_package_tests(pkg, coverage_file)
    else:
      return bundle.build_install_package(pkg)
  work = [(p, False) for p in packages]+[(p, True) for p in skipped]
  for result in tpool.imap_unordered(run, work):
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
