# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import requests
import sys
import urllib
import urlparse
import argparse
import re
import os

import requests_cache

from infra.tools.builder_alerts import buildbot

requests_cache.install_cache('reasons')


import infra
infra_module_path = os.path.dirname(os.path.abspath(infra.__file__))
infra_dir = os.path.dirname(infra_module_path)
top_dir = os.path.dirname(infra_dir)
sys.path.insert(0, os.path.join(top_dir, 'build', 'scripts'))

# The air of sophistication of this sys.path hack suffocates poor pylint.
from common import gtest_utils  # pylint: disable=F0401


def stdio_for_step(master_url, builder_name, build, step):  # pragma: no cover
  # FIXME: Should get this from the step in some way?
  base_url = buildbot.build_url(master_url, builder_name, build['number'])
  stdio_url = "%s/steps/%s/logs/stdio/text" % (base_url, step['name'])

  try:
    return requests.get(stdio_url).text
  except requests.exceptions.ConnectionError, e:
    # Some builders don't save logs for whatever reason.
    logging.error('Failed to fetch %s: %s' % (stdio_url, e))
    return None


def fancy_case_master_name(master_url):  # pragma: no cover
  master_name = buildbot.master_name_from_url(master_url)
  return master_name.title().replace('.', '')


# These are reason finders, more than splitters?
class GTestSplitter(object):
  @staticmethod
  def handles_step(step):
    step_name = step['name']
    # Silly heuristic, at least we won't bother processing
    # stdio from gclient revert, etc.
    if step_name.endswith('tests'):
      return True

    KNOWN_STEPS = [
      # There are probably other gtest steps not named 'tests'.
    ]
    return step_name in KNOWN_STEPS

  @staticmethod
  def split_step(step, build, builder_name, master_url):  # pragma: no cover
    params = {
      'name': 'full_results.json',
      'master': fancy_case_master_name(master_url),
      'builder': builder_name,
      'buildnumber': build['number'],
      'testtype': step['name'],
    }
    base_url = 'http://test-results.appspot.com/testfile'
    response = requests.get(base_url, params=params)
    if response.status_code == 200:
      test_results = flatten_test_results(response.json()['tests'])
      return GTestSplitter.failed_tests(test_results)

    logging.warn('test-results missing %s %s %s, using GTestLogParser.' % (
        builder_name, build['number'], step['name']))
    stdio_log = stdio_for_step(master_url, builder_name, build, step)
    # Can't split if we can't get the logs.
    if not stdio_log:
      return None

    # pylint: disable=C0301
    # Lines this fails for:
    #[  FAILED  ] ExtensionApiTest.TabUpdate, where TypeParam =  and GetParam() =  (10907 ms)

    log_parser = gtest_utils.GTestLogParser()
    for line in stdio_log.split('\n'):
      log_parser.ProcessLine(line)

    failed_tests = log_parser.FailedTests()
    if failed_tests:
      return failed_tests
    # Failed to split, just group with the general failures.
    logging.debug('First Line: %s' % stdio_log.split('\n')[0])
    return None

  @staticmethod
  def failed_tests(test_results):
    """Returns any tests that that had actual results and were not expected.

    Args:
      test_results: Map from test name to results, which map the type
        ('expected' or 'actual') to a string containing the results.

    Returns:
      List of tests names that fail expectations.
    """
    names = []
    for name, results in test_results.items():
      expected = set(results['expected'].split(' '))
      actual = set(results['actual'].split(' '))
      # These entries showed up in the actual list but not in expected.
      unexpected = actual - expected
      if len(unexpected) > 0:
        names.append(name)
    return names

# Our Android tests produce very gtest-like output, but not
# quite GTestLogParser-compatible (it parse the name of the
# test as org.chromium).

class JUnitSplitter(object):

  @staticmethod
  def handles_step(step):
    KNOWN_STEPS = [
      'androidwebview_instrumentation_tests',
      'mojotest_instrumentation_tests', # Are these always java?
    ]
    return step['name'] in KNOWN_STEPS

  FAILED_REGEXP = re.compile('\[\s+FAILED\s+\] (?P<test_name>\S+)( \(.*\))?$')

  def failed_tests_from_stdio(self, stdio):  # pragma: no cover
    failed_tests = []
    for line in stdio.split('\n'):
      match = self.FAILED_REGEXP.search(line)
      if match:
        failed_tests.append(match.group('test_name'))
    return failed_tests

  # "line too long" pylint: disable=C0301
  def split_step(self, step, build, builder_name, master_url):  # pragma: no cover
    stdio_log = stdio_for_step(master_url, builder_name, build, step)
    # Can't split if we can't get the logs.
    if not stdio_log:
      return None

    failed_tests = self.failed_tests_from_stdio(stdio_log)
    if failed_tests:
      return failed_tests
    # Failed to split, just group with the general failures.
    logging.debug('First Line: %s' % stdio_log.split('\n')[0])
    return None


def decode_results(results):
  """
  Decode test results and generates failures if any failures exist.

  Each test has an expected result, an actual result, and a flag indicating
  whether the test harness considered the result unexpected. For example, an
  individual test result might look like:

  {
    'actual': 'PASS foobar',
    'expected': 'foobar',
    'is_unexpected': True,
  }

  A result is considered a pass if the actual result is just the string 'PASS'.
  A result is considered a flake if the actual result has a value attached and
  the value appears in the expected values. All other kinds of results are
  considered failures. The test result given above is an example of a flake
  result.
  """
  tests = flatten_test_results(results['tests'])
  failures = {}
  for (test, result) in tests.iteritems():
    if result.get('is_unexpected'):
      actual_results = result['actual'].split()
      expected_results = result['expected'].split()
      if len(actual_results) > 1:
        if actual_results[1] not in expected_results:
          # We report the first failure type back, even if the second
          # was more severe.
          failures[test] = actual_results[0]
      elif actual_results[0] != 'PASS':
        failures[test] = actual_results[0]  # pragma: no cover

  return failures


def flatten_test_results(trie, prefix=None):
  """
  Flattens a trie structure of test results into a single-level map.

  This function flattens a trie to a single-level map, stopping when it reaches
  a nonempty node that has either 'actual' or 'expected' as child keys. For
  example:

  {
    'foo': {
      'bar': {
        'expected': 'something good',
        'actual': 'something bad'
      },
      'baz': {
        'expected': 'something else good',
        'actual': 'something else bad',
        'quxx': 'some other test metadata'
      }
    }
  }

  would flatten to:

  {
    'foo/bar': {
      'expected': 'something good',
      'actual': 'something bad'
    },
    'foo/baz': {
      'expected': 'something else good',
      'actual': 'something else bad',
      'quxx': 'some other test metadata'
    }
  }
  """
  # Cloned from webkitpy.layout_tests.layout_package.json_results_generator
  # so that this code can stand alone.
  result = {}
  for name, data in trie.iteritems():
    if prefix:
      name = prefix + "/" + name

    if len(data) and not "actual" in data and not "expected" in data:
      result.update(flatten_test_results(data, name))
    else:
      result[name] = data

  return result


class LayoutTestsSplitter(object):

  @staticmethod
  def handles_step(step):
    return step['name'] == 'webkit_tests'

  @staticmethod
  def split_step(step, build, builder_name, master_url):  # pragma: no cover
    # WTF?  The android bots call it archive_webkit_results and the
    # rest call it archive_webkit_tests_results?
    archive_names = ['archive_webkit_results', 'archive_webkit_tests_results']
    archive_step = next((step for step in build['steps']
        if step['name'] in archive_names), None)
    url_to_build = buildbot.build_url(master_url, builder_name, build['number'])

    if not archive_step:
      logging.warn('No archive step in %s' % url_to_build)
      # print json.dumps(build['steps'], indent=1)
      return None

    html_results_url = archive_step['urls'].get('layout test results')
    # FIXME: Here again, Android is a special snowflake.
    if not html_results_url:
      html_results_url = archive_step['urls'].get('results')

    if not html_results_url:
      webkit_tests_step = next((step for step in build['steps']
          if step['name'] == 'webkit_tests'), None)
      # Common cause of this is an exception in the webkit_tests step.
      if webkit_tests_step['results'][0] != 5:
        logging.warn('No results url for archive step in %s' % url_to_build)
      # print json.dumps(archive_step, indent=1)
      return None

    # !@?#!$^&$% WTF HOW DO URLS HAVE \r in them!?!
    html_results_url = html_results_url.replace('\r', '')

    jsonp_url = urlparse.urljoin(html_results_url, 'failing_results.json')
    # FIXME: Silly that this is still JSONP.
    jsonp_string = requests.get(jsonp_url).text
    if 'The specified key does not exist' in jsonp_string:
      logging.warn('%s %s %s missing failing_results.json' % (builder_name,
          build['number'], step['name']))
      return None

    json_string = jsonp_string[len('ADD_RESULTS('):-len(');')]
    try:
      results = json.loads(json_string)
      failures = decode_results(results)
      if failures:
        return ['%s:%s' % (name, types) for name, types in failures.items()]
    except ValueError, e:
      print archive_step['urls']
      print html_results_url
      print 'Failed %s, %s at decode of: %s' % (jsonp_url, e, jsonp_string)

    # Failed to split, just group with the general failures.
    return None


class CompileSplitter(object):
  @staticmethod
  def handles_step(step):
    return step['name'] == 'compile'

  # pylint: disable=C0301
  # Compile example:
  # FAILED: /mnt/data/b/build/goma/gomacc ...
  # ../../v8/src/base/platform/time.cc:590:7: error: use of undeclared identifier 'close'

  # Linker example:
  # FAILED: /b/build/goma/gomacc ...
  # obj/chrome/browser/extensions/interactive_ui_tests.extension_commands_global_registry_apitest.o:extension_commands_global_registry_apitest.cc:function extensions::SendNativeKeyEventToXDisplay(ui::KeyboardCode, bool, bool, bool): error: undefined reference to 'gfx::GetXDisplay()'

  @staticmethod
  def split_step(step, build, builder_name, master_url):  # pragma: no cover
    stdio = stdio_for_step(master_url, builder_name, build, step)
    # Can't split if we can't get the logs.
    if not stdio:
      return None

    compile_regexp = re.compile(r'(?P<path>.*):(?P<line>\d+):(?P<column>\d+): error:')

    # FIXME: I'm sure there is a cleaner way to do this.
    next_line_is_failure = False
    for line in stdio.split('\n'):
      if not next_line_is_failure:
        if line.startswith('FAILED: '):
          next_line_is_failure = True
        continue

      match = compile_regexp.match(line)
      if match:
        return ['%s:%s' % (match.group('path'), match.group('line'))]
      break

    return None


STEP_SPLITTERS = [
  CompileSplitter(),
  LayoutTestsSplitter(),
  JUnitSplitter(),
  GTestSplitter(),
]


def splitter_for_step(step):
  return next((splitter for splitter in STEP_SPLITTERS
      if splitter.handles_step(step)), None)


# For testing:
def main(args):  # pragma: no cover
  logging.basicConfig(level=logging.DEBUG)

  parser = argparse.ArgumentParser()
  parser.add_argument('stdio_url', action='store')
  args = parser.parse_args(args)

  # FIXME: This buildbot url parsing code is useful in tests like these
  # we should add a generic way to do this to buildbot.py
  # pylint: disable=C0301
  # https://build.chromium.org/p/chromium.win/builders/XP%20Tests%20(1)/builds/31886/steps/browser_tests/logs/stdio
  url_regexp = re.compile('(?P<master_url>.*)/builders/(?P<builder_name>.*)/'
      'builds/(?P<build_number>.*)/steps/(?P<step_name>.*)/logs/stdio')
  match = url_regexp.match(args.stdio_url)
  if not match:
    print "Failed to parse URL: %s" % args.stdio_url
    return 1

  step = {
    'name': match.group('step_name'),
  }
  build = {
    'number': match.group('build_number'),
  }
  builder_name = urllib.unquote_plus(match.group('builder_name'))
  master_url = match.group('master_url')
  splitter = splitter_for_step(step)
  print splitter.split_step(step, build, builder_name, master_url)


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
