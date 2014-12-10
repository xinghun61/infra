#!/usr/bin/env python
# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import gtest_parser

class TestGTestParser(unittest.TestCase):
  def test_empty(self):
    self.assertEqual({}, gtest_parser.parse(''))

  def test_pass(self):
    test_log = """[ RUN      ] SimpleTest.TestCase
[       OK ] SimpleTest.TestCase (42 ms)
"""
    self.assertEqual({
      'SimpleTest.TestCase': {
        'is_successful': True,
        'is_crash_or_hang': False,
        'run_time_ms': 42,
        'test_prefix': '',
        'log': '',
       }
    }, gtest_parser.parse(test_log))

  def test_fail(self):
    test_log = """[ RUN      ] SimpleTest.TestCase
test/test.cc:123: Some Failure
[  FAILED  ] SimpleTest.TestCase (18 ms)
"""
    self.assertEqual({
      'SimpleTest.TestCase': {
        'is_successful': False,
        'is_crash_or_hang': False,
        'run_time_ms': 18,
        'test_prefix': '',
        'log': 'test/test.cc:123: Some Failure',
      }
    }, gtest_parser.parse(test_log))

  def test_crash(self):
    test_log = """[ RUN      ] SimpleTest.TestCase
"""
    self.assertEqual({
      'SimpleTest.TestCase': {
        'is_successful': False,
        'is_crash_or_hang': True,
        'run_time_ms': -1,
        'test_prefix': '',
        'log': '',
      }
    }, gtest_parser.parse(test_log))

  def test_crash_log(self):
    test_log = """[ RUN      ] SimpleTest.TestCase
test/test.cc:123: Some Failure
"""
    self.assertEqual({
      'SimpleTest.TestCase': {
        'is_successful': False,
        'is_crash_or_hang': True,
        'run_time_ms': -1,
        'test_prefix': '',
        'log': 'test/test.cc:123: Some Failure',
      }
    }, gtest_parser.parse(test_log))

  def test_crash_log_not_last(self):
    test_log = """[ RUN      ] SimpleTest.TestCase
test/test.cc:123: Some Failure
Haaaaang! Craaaaaassssshhhhhh!
[ RUN      ] SimpleTest.TestCase2
something
[       OK ] SimpleTest.TestCase2 (9 ms)
"""
    self.assertEqual({
      'SimpleTest.TestCase': {
        'is_successful': False,
        'is_crash_or_hang': True,
        'run_time_ms': -1,
        'test_prefix': '',
        'log': """test/test.cc:123: Some Failure
Haaaaang! Craaaaaassssshhhhhh!""",
      },
      'SimpleTest.TestCase2': {
        'is_successful': True,
        'is_crash_or_hang': False,
        'run_time_ms': 9,
        'test_prefix': '',
        'log': 'something',
      }
    }, gtest_parser.parse(test_log))

  def test_multiple(self):
    test_log = """[ RUN      ] SimpleTest.TestCase1
[       OK ] SimpleTest.TestCase1 (10 ms)
[ RUN      ] SimpleTest.TestCase2
[       OK ] SimpleTest.TestCase2 (9 ms)
[ RUN      ] SimpleTest.TestCase3
[       OK ] SimpleTest.TestCase3 (8 ms)
"""
    self.assertEqual({
      'SimpleTest.TestCase1': {
        'is_successful': True,
        'is_crash_or_hang': False,
        'run_time_ms': 10,
        'test_prefix': '',
        'log': '',
      },
      'SimpleTest.TestCase2': {
        'is_successful': True,
        'is_crash_or_hang': False,
        'run_time_ms': 9,
        'test_prefix': '',
        'log': '',
      },
      'SimpleTest.TestCase3': {
        'is_successful': True,
        'is_crash_or_hang': False,
        'run_time_ms': 8,
        'test_prefix': '',
        'log': '',
      }
    }, gtest_parser.parse(test_log))

  def test_multiple_noise(self):
    test_log = """noise-noise
[ RUN      ] SimpleTest.TestCase1
[       OK ] SimpleTest.TestCase1 (10 ms)
[ RUN      ] SimpleTest.TestCase2
[       OK ] SimpleTest.TestCase2 (9 ms)
[ --  -    ] some more noise
garbagegarbage
[ RUN      ] SimpleTest.TestCase3
real log
second line
[       OK ] SimpleTest.TestCase3 (8 ms)
"""
    self.assertEqual({
      'SimpleTest.TestCase1': {
        'is_successful': True,
        'is_crash_or_hang': False,
        'run_time_ms': 10,
        'test_prefix': '',
        'log': '',
      },
      'SimpleTest.TestCase2': {
        'is_successful': True,
        'is_crash_or_hang': False,
        'run_time_ms': 9,
        'test_prefix': '',
        'log': '',
      },
      'SimpleTest.TestCase3': {
        'is_successful': True,
        'is_crash_or_hang': False,
        'run_time_ms': 8,
        'test_prefix': '',
        'log': 'real log\nsecond line',
      }
    }, gtest_parser.parse(test_log))

# pylint: disable=line-too-long
  def test_android_noise_2(self):
    test_log = '[014E0F500401B017] # 2012-09-28 12:13:19,537: >>> $am force-stop com.google.android.apps.chrome'
    self.assertEqual({}, gtest_parser.parse(test_log))

  def test_info_noise_1(self):
    test_log = '[----------] Global test environment set-up.'
    self.assertEqual({}, gtest_parser.parse(test_log))

  def test_info_noise_2(self):
    test_log = '[ PASSED ] 0 tests. '
    self.assertEqual({}, gtest_parser.parse(test_log))

  def test_gtest_threads_noise(self):
    test_log = '[WARNING] /b/build/slave/cr-mac-rel/build/src/testing/gtest/src/gtest-death-test.cc:827:: Death tests use fork(), which is unsafe particularly in a threaded context. For this test, Google Test detected 4 threads.'
    self.assertEqual({}, gtest_parser.parse(test_log))

  def test_buildbot_noise(self):
    test_log = """<pre><span class="header">python ../../../scripts/slave/runtest.py --target Release --build-dir src/build '--build-properties={"blamelist":"jennb@chromium.org,sreeram@chromium.org","branch":"src","buildername":"Mac10.7 Tests (1)","buildnumber":"2247","got_revision":"159081","mastername":"chromium.mac","parent_builddir":"","parent_buildnumber":"1007","parentname":"Mac Builder","parentslavename":"xserve6-m1","revision":"159081","scheduler":"mac_rel_trigger","slavename":"vm614-m1"}' '--factory-properties={"browser_shard_index":1,"browser_total_shards":3,"gclient_env":{"DEPOT_TOOLS_UPDATE":"0","GYP_DEFINES":" component=static_library","GYP_GENERATOR_FLAGS":""},"generate_gtest_json":true,"sharded_tests":["base_unittests","browser_tests","cc_unittests","content_browsertests","media_unittests","webkit_compositor_bindings_unittests"]}' --annotate=gtest --test-type gpu_unittests --generate-json-file -o gtest-results/gpu_unittests --build-number 2247 --builder-name 'Mac10.7 Tests (1)' gpu_unittests --gmock_verbose=error --gtest_print_time"""
    self.assertEqual({}, gtest_parser.parse(test_log))
  maxDiff = None
  def test_single_params(self):
    test_log = """[ RUN      ] ExtensionDevToolsBrowserTest.FLAKY_TimelineApi
/b/build/slave/chromium-mac-flaky-builder-dbg/build/src/chrome/browser/extensions/extension_devtools_browsertests.cc:90: Failure
Value of: result
  Actual: false
Expected: true
[  FAILED  ] ExtensionDevToolsBrowserTest.FLAKY_TimelineApi, where TypeParam =  and GetParam() =  (814 ms)"""
    self.assertEqual({
      'ExtensionDevToolsBrowserTest.TimelineApi': {
        'is_successful': False,
        'is_crash_or_hang': False,
        'run_time_ms': 814,
        'test_prefix': 'FLAKY',
        'log': """/b/build/slave/chromium-mac-flaky-builder-dbg/build/src/chrome/browser/extensions/extension_devtools_browsertests.cc:90: (truncated by parser)
Value of: result
  Actual: false
Expected: true"""
      }
    }, gtest_parser.parse(test_log))

  def test_line_endings(self):
    test_log = ('[ RUN      ] SimpleTest.TestCase\r\n' +
                '[       OK ] SimpleTest.TestCase (42 ms)\r\n')
    self.assertEqual({
      'SimpleTest.TestCase': {
        'is_successful': True,
        'is_crash_or_hang': False,
        'run_time_ms': 42,
        'test_prefix': '',
        'log': '',
      }
    }, gtest_parser.parse(test_log))

  def test_line_endings2(self):
    test_log = ('[ RUN      ] SimpleTest.TestCase\r\r\n' +
                '[       OK ] SimpleTest.TestCase (42 ms)\r\r\n')
    self.assertEqual({
      'SimpleTest.TestCase': {
        'is_successful': True,
        'is_crash_or_hang': False,
        'run_time_ms': 42,
        'test_prefix': '',
        'log': '',
      }
    }, gtest_parser.parse(test_log))

  def test_truncate(self):
    test_log = '\n'.join(['[ RUN      ] SimpleTest.TestCase'] +
                         ['a' * 5000] +
                         ['[       OK ] SimpleTest.TestCase (42 ms)'])
    self.assertEqual({
      'SimpleTest.TestCase': {
        'is_successful': True,
        'is_crash_or_hang': False,
        'run_time_ms': 42,
        'test_prefix': '',
        'log': 'a' * 120 + ' (truncated by parser)',
      },
    }, gtest_parser.parse(test_log))

  def test_trim(self):
    test_log = '\n'.join(['[ RUN      ] SimpleTest.TestCase'] +
                         [str(x) for x in range(1000)] +
                         ['[       OK ] SimpleTest.TestCase (42 ms)'])
    self.assertEqual({
      'SimpleTest.TestCase': {
        'is_successful': True,
        'is_crash_or_hang': False,
        'run_time_ms': 42,
        'test_prefix': '',
        'log': '\n'.join([str(x) for x in range(22)] +
                         ['', '(trimmed by parser)', ''] +
                         [str(x) for x in range(977, 1000)]),
      }
    }, gtest_parser.parse(test_log))


if __name__ == '__main__':
  unittest.main()
