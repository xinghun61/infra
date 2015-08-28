# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import textwrap

from testing_utils import testing
from waterfall import extractors
from waterfall.extractor import Extractor


class ExtractorsTest(testing.AppengineTestCase):

  def _RunTest(self, failure_log, extractor_class, expected_signal_json,
               bot='bot', master='master'):
    signal = extractor_class().Extract(
        failure_log, 'suite.test', 'step', bot, master)
    self.assertEqual(expected_signal_json, signal.ToDict())

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
        SUMMARY: AddressSanitizer: x/y/z.cc:123:9
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

  def testNontopFramesInCrashAreIgnoredWhenStackFramesHavePrefixString(self):
    failure_log = textwrap.dedent("""
        @@@test@  #0 0x113bb76d0 in function0 a.cc:1
        @@@test@  #1 0x113bb76d1 in function1 b.cc:2
        @@@test@  #2 0x113bb76d2 in function2 c.cc:3
        @@@test@  #3 0x113bb76d3 in function3 d.cc:4
        @@@test@  #4 0x113bb76d4 in function4 e.cc:5
        @@@test@  #5 0x113bb76d5 in function5 f.cc:6
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

  def testGmockWarningStatementsAreIgnored(self):
    failure_log = """
GMOCK WARNING:
Uninteresting mock function call - taking default action specified at:
x/y/a.cc:45:
Function call: IsManaged()
Returns: false
Note:You can safely ignore the above warning unless this call should not happen.
...
#0 0x113bb76d0 in function0 a.cc:1
#1 0x113bb76d1 in function1 b.cc:2"""

    expected_signal_json = {
        'files': {
            'a.cc': [1],
            'b.cc': [2],
        },
        'tests': [],
        'keywords': {}
    }

    self._RunTest(
        failure_log, extractors.GeneralExtractor, expected_signal_json)

  def testLeastRecentPythonFramesAreIgnored(self):
    failure_log = textwrap.dedent("""
        Traceback (most recent call last):
          method1 at path/a.py:1
            message1
          method2 at path/b.py:2
            message2
          method3 at path/c.py:3
            message3
          method4 at path/d.py:4
            message4
          method5 at path/e.py:5
            message5
        blablaError: blabla...

        blabla

        Traceback (most recent call last):
          File "path/f.py", line 12, in method1
            message1
          File "path/g.py", line 34, in method2
            message2
          File "path/h.py", line 56, in method3
            message3
          File "path/i.py", line 78, in method4
            message4
          File "path/j.py", line 910, in method5
            message5
        blabalError: blabla...

        blabla

        Traceback (most recent call last):
          File "path/k.py", line 123, in method1
            message1
          File "path/l.py", line 456, in method2
            message2
        blablaError: blabla...

        blabla Traceback (most recent call last):
        blabla   File "path/m.py", line 1, in method1
        blabla     message1
        blabla   File "path/n.py", line 2, in method2
        blabla     message2
        blabla   File "path/o.py", line 3, in method3
        blabla     message3
        blabla   File "path/p.py", line 4, in method4
        blabla     message4
        blabla   File "path/q.py", line 5, in method5
        blabla     message5
        blabla   File "path/r.py", line 6, in method6
        blabla     message6
        blabla   File "path/s.py", line 7, in method7
        blabla     message7
        blabla   File "path/t.py", line 8, in method8
        blabla     message8
        blabla blablaError: blabla...

        blabla

        blabla Traceback (most recent call last):
        blabla  method1 at path/u.py:1
        blabla    message1
        blabla  method2 at path/v.py:2
        blabla    message2
        blabla  method3 at path/w.py:3
        blabla    message3
        blabla  method4 at path/x.py:4
        blabla    message4
        blabla  method5 at path/y.py:5
        blabla    message5
        blabla blablaError: blabla...""")
    expected_signal_json = {
        'files': {
            'path/b.py': [2],
            'path/c.py': [3],
            'path/d.py': [4],
            'path/e.py': [5],
            'path/g.py': [34],
            'path/h.py': [56],
            'path/i.py': [78],
            'path/j.py': [910],
            'path/k.py': [123],
            'path/l.py': [456],
            'path/q.py': [5],
            'path/r.py': [6],
            'path/s.py': [7],
            'path/t.py': [8],
            'path/v.py': [2],
            'path/w.py': [3],
            'path/x.py': [4],
            'path/y.py': [5],
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
        1 error generated.
        x/y/not_in_signal.cc
        FAILED: /b/build/goma/gomacc ... ../../a/b/x.cc -o obj/a/b/test.c.o
        ../../a/b/d.cc:123:44: error: no member 'kEnableExtensionInfoDialog' ...
        blabla...
        FAILED: /b/build/goma/gomacc ... ../../a/b/x.cc -o obj/a/b/test.c.o
        ../../a/b/e.cc:79:44: error: no member 'kEnableExtensionInfoDialog' ...
        blabla...
        ninja: build stopped: subcommand failed.

        /b/build/goma/goma_ctl.sh stat
        blabla...""")
    expected_signal_json = {
        'files': {
            'a/b/c.cc': [307],
            'a/b/d.cc': [123],
            'a/b/e.cc': [79]
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
            'r/w/c/sess.js': []
        },
        'tests': [],
        'keywords': {}
    }

    self._RunTest(
        failure_log, extractors.CompileStepExtractor, expected_signal_json)

  def testCompileStepIOSExtractor(self):
    """Test compile step for builder iOS_Simulator_(dbg) and iOS_Device."""
    failure_log = textwrap.dedent("""
        CompileC a/b/not_in_signal_2.cc
            cd a/b
            export LANG=en_US.US-ASCII
            export PATH="x/y/z"
            /a/b/...
        In file included from a/b/in_signal_1.cc
        ../../a/c/in_signal_2.cc
        In file included from a/c/in_signal_3.cc

        2 errors generated.

        a/b/not_in_signal_1.cc
        CompileC a/b/not_in_signal_2.cc
            cd a/b
            export LANG=en_US.US-ASCII
            export PATH="x/y/z"
            /a/b/...
        In file included from a/b/in_signal_4.cc
        In file included from a/c/in_signal_5.cc
        ../../a/c/in_signal_6.cc

        1 error generated.""")
    expected_signal_json = {
        'files': {
            'a/b/in_signal_1.cc': [],
            'a/c/in_signal_2.cc': [],
            'a/c/in_signal_3.cc': [],
            'a/b/in_signal_4.cc': [],
            'a/c/in_signal_5.cc': [],
            'a/c/in_signal_6.cc': []
        },
        'tests': [],
        'keywords': {}
    }

    self._RunTest(
        failure_log, extractors.CompileStepExtractor, expected_signal_json,
        'iOS_Simulator_(dbg)', 'chromium.mac')

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

  def testCheckSizesExtractor(self):
    failure_log = textwrap.dedent("""
        # Static initializers in a/b/c:
        # HINT: blabla a/b/c.py
        # HINT: blabla a/b/c.py
        # a.cc
        # a.cc
        # b.cc
        # Found 1 static initializer in 3 files.

        RESULT x

        # Static initializers in d/e/f:
        # HINT: blabla a/b/c.py
        # HINT: blabla a/b/c.py
        # HINT: blabla a/b/c.py
        # c.cc
        # d.cc
        # d.cc
        # d.cc
        # Found 2 static initializers in 2 files.

        RESULT Y

        # Static initializers in g/h/i:
        # HINT: blabla a/b/c.py
        # e.cc
        # Found 1 static initializer in 1 file.

        RESULT Z

        # Static initializers in j/k/l
        # HINT: blabla a/b/c.py
        # Found 0 static initializers in 0 files.

        RESULT X

        # Static initializers in m/n/o
        # HINT: blabla a/b/c.py
        # f.cc
        # Found 1 static initializer in 2 files.""")
    expected_signal_json = {
        'files': {
            'a.cc': [],
            'b.cc': [],
            'c.cc': [],
            'd.cc': [],
            'e.cc': [],
            'f.cc': []
        },
        'tests': [],
        'keywords': {}
    }

    self._RunTest(
        failure_log, extractors.CheckSizesExtractor, expected_signal_json)

  def testExtractSignal(self):
    class DummyGeneralExtractor(Extractor):

      def Extract(self, *_):
        return '0'

    class DummyExtractor1(Extractor):

      def Extract(self, *_):
        return '1'

    class DummyExtractor2(Extractor):

      def Extract(self, *_):
        return '2'

    DUMMY_EXTRACTORS = {
        '1': DummyExtractor1,
        '2': DummyExtractor2
    }

    self.mock(extractors, 'GeneralExtractor', DummyGeneralExtractor)
    self.mock(extractors, 'EXTRACTORS', DUMMY_EXTRACTORS)

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
