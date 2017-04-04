# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock

from crash.crash_data import CrashData
from crash.crash_report import CrashReport
from crash.stacktrace import CallStack
from crash.stacktrace import StackFrame
from crash.stacktrace import Stacktrace
from crash.test.predator_testcase import PredatorTestCase
from crash.test.stacktrace_test_suite import StacktraceTestSuite
from libs.deps.chrome_dependency_fetcher import ChromeDependencyFetcher
from libs.deps.dependency import Dependency
from libs.deps.dependency import DependencyRoll


class CrashDataTest(PredatorTestCase):
  """Tests ``CrashData`` class."""

  def testProperties(self):
    """Tests all properties."""
    raw_crash_data = self.GetDummyChromeCrashData()
    crash_data = CrashData(raw_crash_data)

    self.assertEqual(crash_data.identifiers,
                     raw_crash_data['crash_identifiers'])
    self.assertEqual(crash_data.crashed_version,
                     raw_crash_data['chrome_version'])
    self.assertEqual(crash_data.signature,
                     raw_crash_data['signature'])
    self.assertEqual(crash_data.platform,
                     raw_crash_data['platform'])

    crash_data.platform = 'new platform'
    self.assertEqual(crash_data.platform, 'new platform')
