# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import mock

from analysis.clusterfuzz_data import ClusterfuzzData
from analysis.type_enums import CrashClient
from common.appengine_testcase import AppengineTestCase
from common.model.clusterfuzz_analysis import ClusterfuzzAnalysis
from libs.deps.dependency import Dependency
from libs.deps.dependency import DependencyRoll


class ClusterfuzzAnalysisTest(AppengineTestCase):
  """Tests ``ClusterfuzzAnalysis`` class."""

  def testClusterfuzzAnalysisReset(self):
    """Tests ``Reset`` reset all properties."""
    analysis = ClusterfuzzAnalysis()
    analysis.crash_type = 'check'
    analysis.crash_address = '0x0000'
    analysis.sanitizer = 'ASAN'
    analysis.job_type = 'android_asan_win'
    analysis.security_flag = True
    analysis.Reset()
    self.assertIsNone(analysis.crash_type)
    self.assertIsNone(analysis.crash_address)
    self.assertIsNone(analysis.sanitizer)
    self.assertIsNone(analysis.job_type)
    self.assertFalse(analysis.security_flag)

  def testInitializeWithCrashData(self):
    """Tests ``Initialize`` initialize all properties from crash data."""
    predator = self.GetMockPredatorApp()
    raw_crash_data = self.GetDummyClusterfuzzData()
    class MockClusterfuzzData(ClusterfuzzData):

      def __init__(self, raw_crash_data):
        super(MockClusterfuzzData, self).__init__(raw_crash_data, None)

      @property
      def stacktrace(self):
        return None

      @property
      def regression_range(self):
        return None

      @property
      def dependencies(self):
        return {}

      @property
      def dependency_rolls(self):
        return {}

    predator.GetCrashData = mock.Mock(
        return_value=MockClusterfuzzData(raw_crash_data))

    crash_data = predator.GetCrashData(raw_crash_data)
    analysis = ClusterfuzzAnalysis()
    analysis.Initialize(crash_data)
    self.assertEqual(analysis.crash_type, crash_data.crash_type)
    self.assertEqual(analysis.crash_address, crash_data.crash_address)
    self.assertEqual(analysis.job_type, crash_data.job_type)
    self.assertEqual(analysis.sanitizer, crash_data.sanitizer)
    self.assertEqual(analysis.security_flag, crash_data.security_flag)

  def testProperties(self):
    testcase_id = '1232435'

    analysis = ClusterfuzzAnalysis.Create(testcase_id)
    analysis.identifiers = testcase_id

    self.assertEqual(analysis.identifiers, testcase_id)

  def testToJson(self):
    testcase_id = '1234'
    job_type = 'asan'
    analysis = ClusterfuzzAnalysis.Create(testcase_id)
    analysis.testcase_id = testcase_id
    analysis.job_type = job_type
    analysis.security_flag = True

    expected_json = {
        'regression_range': None,
        'dependencies': None,
        'dependency_rolls': None,
        'crash_type': None,
        'crash_address': None,
        'sanitizer': None,
        'job_type': job_type,
        'testcase_id': testcase_id,
        'security_flag': True,
    }

    self.assertDictEqual(analysis.ToJson(),
                         {'customized_data': expected_json,
                          'platform': None,
                          'stack_trace': None,
                          'crash_revision': None,
                          'signature': None})

  def testToJsonForNonEmptyDependencies(self):
    """Tests ``ToJson`` for non-empty self.dependencies."""
    testcase_id = '1234'
    job_type = 'asan'
    analysis = ClusterfuzzAnalysis.Create(testcase_id)
    analysis.testcase_id = testcase_id
    analysis.job_type = job_type
    analysis.dependencies = {
        'src': Dependency('src', 'https://repo', 'rev'),
        'src/v8': Dependency('src/v8', 'https://repo/v8', 'rev2')
    }

    dependencies_json = [{'dep_path': 'src',
                          'repo_url': 'https://repo',
                          'revision': 'rev'},
                         {'dep_path': 'src/v8',
                          'repo_url': 'https://repo/v8',
                          'revision': 'rev2'}]
    expected_json = {
        'regression_range': None,
        'dependencies': dependencies_json,
        'dependency_rolls': None,
        'crash_type': None,
        'crash_address': None,
        'sanitizer': None,
        'job_type': job_type,
        'security_flag': False,
        'testcase_id': testcase_id,
    }

    self.assertDictEqual(
        analysis.ToJson(),
        {
            'customized_data': expected_json,
            'platform': None,
            'stack_trace': None,
            'crash_revision': None,
            'signature': None
        })

  def testToJsonForNonEmptyDependencyRolls(self):
    """Tests ``ToJson`` for non-empty self.dependency_rolls."""
    testcase_id = '1234'
    job_type = 'asan'
    analysis = ClusterfuzzAnalysis.Create(testcase_id)
    analysis.testcase_id = testcase_id
    analysis.job_type = job_type
    analysis.dependency_rolls = {
        'src/': DependencyRoll('src/', 'https://repo', 'rev1', 'rev2'),
        'src/v8': DependencyRoll('src/v8', 'https://repo/v8', 'rev3', 'rev4')
    }

    dependency_rolls_json = [
        {'dep_path': dep.path, 'repo_url': dep.repo_url,
         'old_revision': dep.old_revision, 'new_revision': dep.new_revision}
        for dep in analysis.dependency_rolls.itervalues()
    ]
    expected_json = {
        'regression_range': None,
        'dependencies': None,
        'dependency_rolls': dependency_rolls_json,
        'crash_type': None,
        'crash_address': None,
        'sanitizer': None,
        'security_flag': False,
        'job_type': job_type,
        'testcase_id': testcase_id
    }

    self.assertDictEqual(analysis.ToJson(),
                         {'customized_data': expected_json,
                          'platform': None,
                          'stack_trace': None,
                          'crash_revision': None,
                          'signature': None})
