# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import textwrap
import unittest

from waterfall.extractor import Extractor
from waterfall import extractors
from waterfall.failure_signal import FailureSignal


class ExtractorsTest(unittest.TestCase):
  def _RunTest(self, failure_log, extractor_class, expected_signal_json):
    signal = extractor_class().Extract(
        failure_log, 'suite.test', 'step', 'bot', 'master')
    self.assertEqual(expected_signal_json, signal.ToJson())

  def testGeneralExtractor(self):
    failure_log = textwrap.dedent("""
        blabla WARNING: bla bla a/b/c.cc:20

        blabla d/e/f.cc:30
        blabla""")
    expected_signal_json = {
        'files': {
            'd/e/f.cc': [30]
        },
        'tests': [],
        'keywords': {}
    }

    self._RunTest(
        failure_log, extractors.GeneralExtractor, expected_signal_json)

  def testExpectedCrashIsIgnored(self):
    failure_log = textwrap.dedent("""
        #0 0x113bb76d3 in content::(anonymous namespace)::CrashIntentionally()
        #1 0x113b8521c in MaybeHandleDebugURL render_frame_impl.cc:341:5
        #2 0x113b8521c in ... render_frame_impl.cc:4561:0
        #3 0x113b7d0c4 in ... render_frame_impl.cc:1084:8
        #4 0x113bb7b2d in ... base/tuple.h:246:3
        ...

        Only this file should be extracted: a/b/c.h:90""")
    expected_signal_json = {
        'files': {
            'a/b/c.h': [90]
        },
        'tests': [],
        'keywords': {}
    }

    self._RunTest(
        failure_log, extractors.GeneralExtractor, expected_signal_json)

  def testNontopFramesInCrashAreIgnored(self):
    failure_log = textwrap.dedent("""
        #0 0x113bb76d0 in function0 a.cc:1
        #1 0x113bb76d1 in function1 b.cc:2
        #2 0x113bb76d2 in function2 c.cc:3
        #3 0x113bb76d3 in function3 d.cc:4
        #4 0x113bb76d4 in function4 e.cc:5
        #5 0x113bb76d5 in function5 f.cc:6
        ...

        But this file should be extracted: a/b/c.h:90""")
    expected_signal_json = {
        'files': {
            'a.cc': [1],
            'b.cc': [2],
            'c.cc': [3],
            'd.cc': [4],
            'a/b/c.h': [90],
        },
        'tests': [],
        'keywords': {}
    }

    self._RunTest(
        failure_log, extractors.GeneralExtractor, expected_signal_json)

  def testNontopFramesInDisorderedCrashStackTraceAreIgnored(self):
    failure_log = textwrap.dedent("""
        #5 0x113bb76d5 in function5 f.cc:6
        #1 0x113bb76d1 in function1 b.cc:2
        #4 0x113bb76d4 in function4 e.cc:5
        #3 0x113bb76d3 in function3 d.cc:4
        #2 0x113bb76d2 in function2 c.cc:3
        #0 0x113bb76d0 in function0 a.cc:1
        ...

        But this file should be extracted: a/b/c.h:90""")
    expected_signal_json = {
        'files': {
            'a.cc': [1],
            'b.cc': [2],
            'c.cc': [3],
            'd.cc': [4],
            'a/b/c.h': [90],
        },
        'tests': [],
        'keywords': {}
    }

    self._RunTest(
        failure_log, extractors.GeneralExtractor, expected_signal_json)

  def testCompileStepExtractor(self):
    failure_log = textwrap.dedent("""
        [1832/2467 | 117.498] CXX obj/a/b/test.file.o
        blabla...
        FAILED: /b/build/goma/gomacc ... ../../a/b/c.cc -o obj/a/b/test.c.o
        ../../a/b/c.cc:307:44: error: no member 'kEnableExtensionInfoDialog' ...
        blabla...
        1 error generated.
        ninja: build stopped: subcommand failed.

        /b/build/goma/goma_ctl.sh stat
        blabla...""")
    expected_signal_json = {
        'files': {
            'a/b/c.cc': [307],
            'obj/a/b/test.c.o': []
        },
        'tests': [],
        'keywords': {}
    }

    self._RunTest(
        failure_log, extractors.CompileStepExtractor, expected_signal_json)

  def testCompileStepNinjaErrorExtractor(self):
    """Test ninja error extraction in compile step."""
    failure_log = textwrap.dedent("""
        ninja -C /a/b/c/ all -j50
        ninja: Entering directory `../da/b/build/sl/M/'
        ninja: error: '../../r/w/c/sess.js', needed by 'ob/r/w/h.stamp', 
        missing and no known rule to make it""")
    expected_signal_json = {
        'files': {
            'r/w/c/sess.js' : []
        },
        'tests': [],
        'keywords': {}
    }

    self._RunTest(
        failure_log, extractors.CompileStepExtractor, expected_signal_json)

  def testCheckPermExtractor(self):
    failure_log = textwrap.dedent("""
        a/b/c.py
        ...
        FAILED whitespace.txt
        d/e/f.py
        ...""")
    expected_signal_json = {
        'files': {
            'd/e/f.py': []
        },
        'tests': [],
        'keywords': {}
    }

    self._RunTest(
        failure_log, extractors.CheckPermExtractor, expected_signal_json)

  def testExtractSignal(self):
    class _DummyGeneralExtractor(Extractor):
      def Extract(self, *_):
        return '0'

    class _DummyExtractor1(Extractor):
      def Extract(self, *_):
        return '1'

    class _DummyExtractor2(Extractor):
      def Extract(self, *_):
        return '2'

    original_GeneralExtractor = extractors.GeneralExtractor
    original_EXTRACTORS = extractors.EXTRACTORS
    try:
      extractors.GeneralExtractor = _DummyGeneralExtractor
      extractors.EXTRACTORS = {
          '1': _DummyExtractor1,
          '2': _DummyExtractor2
      }

      cases = {
          # step_name: result
          '1': '1',
          '2': '2',
          '32434': '0'
      }

      for step_name, expected_result in cases.iteritems():
        result = extractors.ExtractSignal(
            'master', 'bot', step_name, 'test', '')
        self.assertEqual(expected_result, result)
    finally:
      extractors.GeneralExtractor = original_GeneralExtractor
      extractors.EXTRACTORS = original_EXTRACTORS
