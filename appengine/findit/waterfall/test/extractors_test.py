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
        'keywords': {}
    }

    self._RunTest(
        failure_log, extractors.GeneralExtractor, expected_signal_json)

  def testIndirectLeakCrashIsIgnored(self):
    failure_log = textwrap.dedent("""
        ==14537==ERROR: LeakSanitizer: detected memory leaks

        Direct leak of 104 byte(s) in 1 object(s) allocated from:
          #0 0x67ed4b in operator new(unsigned long) (browser_tests+0x67ed4b)
          #1 0xe560961 in method1 path/to/a.cc:1
          #2 0xe5600ef in method2 path/to/b.cc:2
          ...

        Indirect leak of 4080 byte(s) in 1 object(s) allocated from:
          #0 0x67ed4b in operator new(unsigned long) (browser_tests+0x67ed4b)
          #1 0x2f91118 in method3 path/to/c.cc:3
          #2 0x2f91218 in method3 path/to/d.cc:4
          #3 0x2f91518 in method3 path/to/e.cc:5
          ...

        ...
        This file should be extracted: path/to/f.cc:90""")
    expected_signal_json = {
        'files': {
            'path/to/a.cc': [1],
            'path/to/b.cc': [2],
            'path/to/f.cc': [90],
        },
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
        'keywords': {}
    }

    self._RunTest(
        failure_log, extractors.GeneralExtractor, expected_signal_json)

  def testCompileStepExtractor(self):
    failure_log = textwrap.dedent("""
        [1832/2467 | 117.498] CXX obj/a/b/test.file.o
        blabla...
        FAILED: /b/build/goma/gomacc ... ../../a/b/c.cc ... obj/a/b/test.c.o
        ../../a/b/c.cc:307:44: error: no member 'kEnableExtensionInfoDialog' ...
        1 error generated.
        x/y/not_in_signal.cc
        FAILED: /b/build/goma/gomacc ... ../../a/b/x.cc ... obj/a/b/test.c.o
        ../../a/b/d.cc:123:44: error: no member 'kEnableExtensionInfoDialog' ...
        blabla...
        FAILED: /b/build/goma/gomacc ... ../../a/b/x.cc ... obj/a/b/test.c.o
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
        'keywords': {}
    }

    self._RunTest(
        failure_log, extractors.CompileStepExtractor, expected_signal_json)

  def testCompileStepExtractorExtractFailedCompileTargetsLinux(self):
    failure_log = textwrap.dedent("""
        [1832/2467 | 117.498] CXX obj/a/b/test.file.o
        blabla...
        FAILED: /b/build/goma/gomacc ... -c ../../a/b/c.cc -o obj/a/b/c.o
        ../../a/b/c.cc:307:44: error: no member 'kEnableExtensionInfoDialog' ...
        1 error generated.
        x/y/not_in_signal.cc
        FAILED: /b/build/goma/gomacc ... -c ../../a/b/x.cc -o obj/a/b/x.o
        ../../a/b/d.cc:123:44: error: no member 'kEnableExtensionInfoDialog' ...
        blabla...
        FAILED: /b/build/goma/gomacc ... -c ../../a/b/x.cc -o obj/a/b/x.o
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
        'keywords': {},
        'failed_targets': [
            {
                'source': '../../a/b/c.cc',
                'target': 'obj/a/b/c.o',
            },
            {
                'source': '../../a/b/x.cc',
                'target': 'obj/a/b/x.o',
            },
        ]
    }

    self._RunTest(
        failure_log, extractors.CompileStepExtractor, expected_signal_json)

  def testCompileStepExtractorExtractFailedTargetsLinuxOutsideFailure(self):
    failure_log = textwrap.dedent("""
        [1780/30023] blabla
        FAILED: blabla
        blabla
        1 error generated.
        FAILED with 1: blabla -c a/b.cc -o c/d.o blabla
        blabla
        Error: FAILED with 1: blabla
        ninja: build stopped: subcommand failed.
        blabla.""")
    expected_signal_json = {
        'files': {},
        'keywords': {},
        'failed_targets': [
            {
                'source': 'a/b.cc',
                'target': 'c/d.o'
            }
        ]
    }

    self._RunTest(
        failure_log, extractors.CompileStepExtractor, expected_signal_json)

  def testCompileStepExtractorExtractFailedLinkTargetsLinux(self):
    failure_log = textwrap.dedent("""
        [5430/5600] blabla
        FAILED: python blabla -o a/b.nexe blabla   
        blabla
        blabla.Error: FAILED with blabla
        ninja: build stopped: subcommand failed.""")
    expected_signal_json = {
        'files': {},
        'keywords': {},
        'failed_targets': [
            {
                'target': 'a/b.nexe'
            }
        ]
    }

    self._RunTest(
        failure_log, extractors.CompileStepExtractor, expected_signal_json)

  def testCompileStepExtractorExtractFailedCompileTargetsWindows(self):
    failure_log = textwrap.dedent("""
        [4576/31353] blabla
        FAILED: ninja blabla /c ..\\..\\a\\b\\c.cc /Foa\\b.c.obj blabla 
        blabla
        FAILED: ninja blabla /c ..\\..\\d\\e\\f.cc /Fod\\e\\f\\a.b.obj blabla 
        blabla
        ninja: build stopped: subcommand failed.""")
    expected_signal_json = {
        'files': {},
        'keywords': {},
        'failed_targets': [
            {
                'source': '..\\..\\a\\b\\c.cc',
                'target': 'a\\b.c.obj',
            },
            {
                'source': '..\\..\\d\\e\\f.cc',
                'target': 'd\\e\\f\\a.b.obj'
            },
        ]
    }

    self._RunTest(failure_log, extractors.CompileStepExtractor,
                  expected_signal_json)

  def testCompileStepExtractorExtractFailedLinkTargetsWindows(self):
    failure_log = textwrap.dedent("""
        [11428/27088] blabla
        FAILED: blabla link.exe /OUT:test.exe @test.exe.rsp blabla
        ninja: build stopped: subcommand failed.""")
    expected_signal_json = {
        'files': {},
        'keywords': {},
        'failed_targets': [
            {
                'target': 'test.exe'
            }
        ]
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
        'keywords': {}
    }

    self._RunTest(
        failure_log, extractors.CheckSizesExtractor, expected_signal_json)

  def testInstrumentationTestExtractor(self):
    failure_log = textwrap.dedent("""
        C 1855.516s Main  at org.chromium.not.this.file.method(file.java:0)
        C 1855.516s Main  ******************************************************
        C 1855.516s Main  Detailed Logs
        C 1855.516s Main  ******************************************************
        C 1855.518s Main  [FAIL] blabla#test1:
        C 1855.518s Main  junit.framework.AssertionFailedError: blabla
        C 1855.518s Main    at org.chromium.a.file1.method1(file1.java:123)
        C 1855.518s Main    at java.lang.reflect.Method.run(Native Method)
        C 1855.519s Main    at org.chromium.b.file2$class.method(file2.java:456)
        C 1855.518s Main    at org.blabla.c.file3.method3(file3.java:789)
        C 1855.519s Main    at org.chromium.d.file4$class.method(file4.java:111)
        C 1855.519s Main    at org.chromium.e.file5$class.method(file5.java:222)
        C 1855.519s Main    at org.chromium.f.file6$class.method(file6.java:333)
        C 1855.519s Main
        C 1855.518s Main  [FAIL] blabla#test2:
        C 1855.518s Main  junit.framework.AssertionFailedError: blabla
        C 1855.518s Main    at org.chromium.g.file7.method1(file7.java:333)
        C 1855.519s Main    at org.chromium.h.file8$class.method(file8.java:444)
        C 1855.519s Main  ******************************************************
        C 1855.519s Main  Summary
        C 1855.519s Main  ******************************************************
        C 1855.516s Main  at org.chromium.not.this.file.method(file.java:0)
        """)

    expected_signal_json = {
        'files': {
            'org/chromium/a/file1.java': [123],
            'org/chromium/b/file2.java': [456],
            'org/chromium/g/file7.java': [333],
            'org/chromium/h/file8.java': [444]
        },
        'keywords': {}
    }
    self._RunTest(failure_log,
                  extractors.InstrumentationTestExtractor,
                  expected_signal_json)

  def testJunitTestExtractor(self):
    failure_log = textwrap.dedent("""
        [----------] Run 3 test cases from org.chromium.a.b.c.test
        [ RUN      ] org.chromium.a.b.c.test
        [       OK ] org.chromium.a.b.c.test (30 ms)
        [----------] Run 13 test cases from org.chromium.a.b.c.test (2831 ms)

        [----------] Run 1 test cases from org.chromium.a.b.file1
        [ RUN      ] org.chromium.a.b.testFile1.test1
        java.lang.SomeError: a/b/c/Class;
            at java.lang.Class.getDeclaredFields0(Native Method)
            at java.lang.Class.privateGetDeclaredFields(Class.java:2397)
            at org.chromium.a.class1.<method1>(file1.java:1)
            at org.chromium.a.class2.method2(file2.java:2)
            at org.chromium.a.class3.method3(file3.java:3)
        Caused by: java.lang.ClassNotFoundException: x.y.z.class
            at java.net.URLClassLoader$1.run(URLClassLoader.java:366)
            at java.net.URLClassLoader$1.run(URLClassLoader.java:355)
            at java.security.AccessController.doPrivileged(Native Method)
            at org.chromium.a.class4.method4(file4.java:4)
            at java.lang.ClassLoader.loadClass(ClassLoader.java:425)
            at sun.misc.Launcher$AppClassLoader.loadClass(Launcher.java:308)
            at java.lang.ClassLoader.loadClass(ClassLoader.java:358)
            ... 27 more
        [   FAILED ] org.chromium.a.b.testFile1.test1 (2 ms)
        [----------] Run 1 test cases from org.chromium.a.b.testFile1.test1

        [ RUN      ] org.chromium.a.b.testFile2.test2
        java.lang.SomeError: a/b/c/Class;
            at java.lang.Class.getDeclaredFields0(Native Method)
            at java.lang.Class.privateGetDeclaredFields(Class.java:2397)
            at org.chromium.a.class5.<method1>(file5.java:5)
            at org.chromium.a.class6.method2(file6.java:6)
            at org.chromium.a.class7.method3(file7.java:7)
        [ RUN      ] org.chromium.a.b.testFile3.test3
        java.lang.SomeError: a/b/c/Class;
            at java.lang.Class.getDeclaredFields0(Native Method)
            at java.lang.Class.privateGetDeclaredFields(Class.java:2397)
            at org.chromium.a.class8.<method8>(file8.java:8)
            at org.chromium.a.class9.method9(file9.java:9)
            at org.chromium.a.class10.method10(file10.java:10)
        [   FAILED ] org.chromium.a.b.testFile3.test3 (2 ms)
        """)

    expected_signal_json = {
        'files': {
            'org/chromium/a/file1.java': [1],
            'org/chromium/a/file2.java': [2],
            'org/chromium/a/file4.java': [4],
            'org/chromium/a/b/testFile1.java': [],
            'org/chromium/a/file8.java': [8],
            'org/chromium/a/file9.java': [9],
            'org/chromium/a/b/testFile3.java': []
        },
        'keywords': {}
    }
    self._RunTest(failure_log,
                  extractors.JunitTestExtractor,
                  expected_signal_json)

  def testRunhooksExtractor(self):
    failure_log = textwrap.dedent("""
        Step info:
        Master name: chromium.chrome
        Builder name: Google Chrome Win
        Build number: 1149
        Step name: gclient runhooks

        Log:
        @@@STEP_CURSOR gclient runhooks@@@

        @@@STEP_STARTED@@@

        python -u c:\\a\\blabla\\gclient.py runhooks
        blabla

        Could Not Find not\\this\\f.lock

        ________ running 'c:\\python.exe blabla1.py' in 'c:\\build'

        ________ running 'c:\\python.exe babla2.py' in 'c:\\build'
        Enabled Psyco JIT.
        Updating projects from gyp files...
        gyp: blabla in c:\\a\\b\\file1.gyp
        Hook ''c:\\a\\b\\c\\file2.exe' src/build/gyp_chromium' took 20.57 secs

        @@@blabla@@@

        @@@blabla blabla blabla@@@""")
    expected_signal_json = {
        'files': {
            'c:/a/b/c/file2.exe': [],
            'c:/a/b/file1.gyp': []
        },
        'keywords': {}
    }

    self._RunTest(
        failure_log, extractors.RunhooksExtractor, expected_signal_json)

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
