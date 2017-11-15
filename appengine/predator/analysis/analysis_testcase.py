# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy

from libs.base_testcase import BaseTestCase
from libs.gitiles.change_log import ChangeLog


DUMMY_CHANGELOG = ChangeLog.FromDict({
    'author': {
        'name': 'r@chromium.org',
        'email': 'r@chromium.org',
        'time': 'Thu Mar 31 21:24:43 2016',
    },
    'committer': {
        'name': 'example@chromium.org',
        'email': 'r@chromium.org',
        'time': 'Thu Mar 31 21:28:39 2016',
    },
    'message': 'dummy',
    'commit_position': 175900,
    'touched_files': [
        {
            'change_type': 'add',
            'new_path': 'a.cc',
            'old_path': None,
        },
        {
            'change_type': 'rename',
            'old_path': 'old_name.cc',
            'new_path': 'new_name.cc',
        },
    ],
    'commit_url':
        'https://repo.test/+/1',
    'code_review_url': 'https://codereview.chromium.org/3281',
    'revision': '1',
    'reverted_revision': None
})


class MockLog(object):  # pragma: no cover

  def __init__(self):
    self.logs = []

  def Log(self, name, message, level):
    self.logs.append({'name': name, 'message': message, 'level': level})


class AnalysisTestCase(BaseTestCase):  # pragma: no cover.

  def _VerifyTwoStackFramesEqual(self, frame1, frame2):
    self.assertIsNotNone(frame1, "the first frame is unexpectedly missing")
    self.assertIsNotNone(frame2, "the second frame is unexpectedly missing")
    self.assertEqual(str(frame1), str(frame2))
    self.assertEqual(frame1.dep_path, frame2.dep_path)

  def _VerifyTwoCallStacksEqual(self, stack1, stack2):
    self.assertIsNotNone(stack1, "the first stack is unexpectedly missing")
    self.assertIsNotNone(stack2, "the second stack is unexpectedly missing")
    self.assertEqual(len(stack1.frames), len(stack2.frames))
    self.assertEqual(stack1.priority, stack2.priority)
    self.assertEqual(stack1.format_type, stack2.format_type)
    self.assertEqual(stack1.language_type, stack2.language_type)
    map(self._VerifyTwoStackFramesEqual, stack1.frames, stack2.frames)

  def _VerifyTwoStacktracesEqual(self, trace1, trace2):
    self.assertIsNotNone(trace1, "the first trace is unexpectedly missing")
    self.assertIsNotNone(trace2, "the second trace is unexpectedly missing")
    self.assertEqual(len(trace1.stacks), len(trace2.stacks))
    map(self._VerifyTwoCallStacksEqual, trace1.stacks, trace2.stacks)

  def GetDummyChangeLog(self):
    return copy.deepcopy(DUMMY_CHANGELOG)

  def GetDummyClusterfuzzData(
      self, client_id='mock_client', version='1', signature='signature',
      platform='win', stack_trace=None, regression_range=None,
      testcase_id='213412343', crash_type='check', crash_address='0x0023',
      job_type='android_asan', sanitizer='ASAN', dependencies=None,
      dependency_rolls=None, redo=False, security_flag=False):
    crash_identifiers = {'testcase_id': testcase_id}
    regression_range = regression_range or {
        'dep_path': 'src',
        'repo_url': 'https://chromium.git',
        'old_revision': '3',
        'new_revision': '9',
    }
    customized_data = {
        'crash_type': crash_type,
        'crash_address': crash_address,
        'job_type': job_type,
        'sanitizer': sanitizer,
        'regression_range': regression_range,
        'dependencies': dependencies or [{'dep_path': 'src/',
                                          'repo_url': 'https://repo',
                                          'revision': 'rev'}],
        'dependency_rolls': dependency_rolls or [{'dep_path': 'src/',
                                                  'repo_url': 'https://repo',
                                                  'old_revision': 'rev1',
                                                  'new_revision': 'rev5'}],
        'testcase_id': testcase_id,
        'security_flag': security_flag,
    }

    crash_data = {
        'crash_revision': version,
        'signature': signature,
        'platform': platform,
        'stack_trace': stack_trace,
        'regression_range': regression_range,
        'crash_identifiers': crash_identifiers,
        'customized_data': customized_data
    }
    if redo:
      crash_data['redo'] = True
    # This insertion of client_id is used for debugging ScheduleNewAnalysis.
    if client_id is not None: # pragma: no cover
      crash_data['client_id'] = client_id
    return crash_data

  def GetDummyChromeCrashData(
      self, client_id='mock_client', version='1', signature='signature',
      platform='win', stack_trace=None, regression_range=None, channel='canary',
      historical_metadata=None, process_type='browser'):
    crash_identifiers = {
        'chrome_version': version,
        'signature': signature,
        'channel': channel,
        'platform': platform,
        'process_type': process_type,
    }
    customized_data = {
        'historical_metadata': historical_metadata,
        'channel': channel,
    }

    crash_data = {
        'chrome_version': version,
        'signature': signature,
        'platform': platform,
        'stack_trace': stack_trace,
        'regression_range': regression_range,
        'crash_identifiers': crash_identifiers,
        'customized_data': customized_data
    }
    # This insertion of client_id is used for debugging ScheduleNewAnalysis.
    if client_id is not None: # pragma: no cover
      crash_data['client_id'] = client_id
    return crash_data

  def GetMockLog(self):
    return MockLog()
