# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import unittest

from infra.tools.builder_alerts import alert_builder


# Unused argument - pylint: disable=W0613


class AlertBuilderTest(unittest.TestCase):
  def test_compute_transition_and_failure_count_failure_to_failing_build(self):
    '''Tests that a failure that started in a run after there were already
    failures gets the correct builds'''
    old_reasons_for_failure = alert_builder.reasons_for_failure

    # TODO(ojan): Is there a better way to do this? Should this test just
    # include the fields that compute_transition_and_failure_count uses?
    # Should there be a directory of jsons that we can pull this from?
    k_example_failing_build = {
      'slave': 'build75-a1',
      'logs': [
        [
          'stdio',
          'http://build.chromium.org/p/chromium.lkgr/builders/'
          'Mac%20ASAN%20Release/builds/4120/steps/foo_tests/logs/stdio'
        ],
      ],
      'builderName': 'Win Release',
      'text': ['failed', 'foo_tests'],
      'number': 4120,
      'currentStep': None,
      'results': 2,
      'blame': ['urlpoller'],
      'reason': 'scheduler',
      'eta': None,
      'steps': [
        {
          'statistics': {},
          'logs': [
            [
              'stdio',
              'http://build.chromium.org/p/chromium.lkgr/builders/'
              'Mac%20ASAN%20Release/builds/4120/steps/foo_tests/logs/stdio'
            ]
          ],
          'isFinished': True,
          'step_number': 0,
          'expectations': [['output', 6510, 8063.161993041647]],
          'isStarted': True,
          'results': [2, []],
          'eta': None,
          'urls': {},
          'text': ['foo_tests'],
          'hidden': False,
          'times': [1407827417.345656, 1407827435.034846],
          'name': 'foo_tests'
        },
      ],
      'sourceStamp': {
        'repository': '',
        'hasPatch': False,
        'project': '',
        'branch': None,
        'changes': [
            {
              'category': '6d999da6-cdb9-44c0-8928-cc57764edfb7',
              'files': [],
              'repository': '',
              'rev': '288872',
              'who': 'urlpoller',
              'when': 1407827009,
              'number': 10096,
              'comments': 'subject line here',
              'project': '', 'at': 'Tue 12 Aug 2014 00:03:29',
              'branch': None,
              'revlink': '',
              'properties': [],
              'revision': '288872'
            }
          ],
        'revision': '288872'
      },
      'times': [1407827417.345451, 1407827665.556783],
      'properties': [
        ['blamelist', ['urlpoller'], 'Build'],
        ['branch', None, 'Build'],
        ['buildbotURL', 'http://build.chromium.org/p/chromium.lkgr/',
            'master.cfg'],
        ['buildername', 'Mac ASAN Release', 'Builder'],
        ['buildnumber', 4120, 'Build'],
        ['got_nacl_revision', '13599', 'Annotation(bot_update)'],
        ['got_nacl_revision_git', 'asdf', 'Annotation(bot_update)'],
        ['got_revision', '288872', 'Annotation(bot_update)'],
        ['got_revision_git', 'asdf', 'Annotation(bot_update)'],
        ['got_swarming_client_revision', 'asdf', 'Annotation(bot_update)'],
        ['got_v8_revision', '23036', 'Annotation(bot_update)'],
        ['got_v8_revision_git', 'asdf', 'Annotation(bot_update)'],
        ['got_webkit_revision', '179989', 'Annotation(bot_update)'],
        ['got_webkit_revision_git', 'asdf', 'Annotation(bot_update)'],
        ['got_webrtc_revision', '6825', 'Annotation(bot_update)'],
        ['got_webrtc_revision_git', 'asdf', 'Annotation(bot_update)'],
        ['gtest_filter', None, 'BuildFactory'],
        ['mastername', 'chromium.lkgr', 'master.cfg'],
        ['primary_repo', '', 'Source'],
        ['project', '', 'Build'],
        ['repository', '', 'Build'],
        ['revision', '288872', 'Build'],
        ['scheduler', 'chromium_lkgr', 'Scheduler'],
        ['slavename', 'build75-a1', 'BuildSlave'],
        ['warnings-count', 0, 'WarningCountingShellCommand'],
        ['workdir', '/b/build/slave/Mac_ASAN_Release', 'slave']
      ]
    }

    def mock_reasons_for_failure(step, build, builder_name,
        master_url):  # pragma: no cover
      if build['number'] == 4120:
        return ['Foo.NewFailure', 'Foo.OldFailure']
      return ['Foo.OldFailure']

    try:
      alert_builder.reasons_for_failure = mock_reasons_for_failure

      failure = {
        'last_result_time': 1407827665.556039,
        'latest_revisions': {
          'v8': '23036',
          'chromium': '288872',
          'nacl': '13599',
          'blink': '179989'
        },
        'builder_name': 'Win Release',
        'last_failing_build': 4120,
        'reason': 'Foo.NewFailure',
        'master_url': 'https://build.chromium.org/p/chromium.lkgr',
        'step_name': 'foo_tests'
      }

      previous_build = copy.deepcopy(k_example_failing_build)
      previous_build['number'] = 4119
      previous_builds = [previous_build]

      last_pass, first_fail, fail_count = (
          alert_builder.compute_transition_and_failure_count(failure,
              k_example_failing_build, previous_builds))
      self.assertEqual(last_pass['number'], 4119)
      self.assertEqual(first_fail['number'], 4120)
      self.assertEqual(fail_count, 1)
    finally:
      alert_builder.reasons_for_failure = old_reasons_for_failure


  def test_find_current_step_failures_no_recent_build_ids(self):
    '''Silly test to get coverage of scenario that never happens, i.e.
    padding in an empty list of recent build ids.
    '''
    step_failures = alert_builder.find_current_step_failures(None, [])
    self.assertEqual(step_failures, [])


  def test_find_current_step_failures_in_progress(self):
    '''Test that failing steps from the previous completed build
    get included if the in-progress build hasn't run this test step yet.
    '''
    def fetch(build_id):
      results = None
      if build_id == 4119:
        results = 2

      return {
        'number': build_id,
        'results': results,
      }

    def mock_complete_steps_by_type(build):
      passing = []
      if build['number'] == 4119:
        failing = [{'name': 'foo_tests'}]
      else:
        failing = []
      return passing, failing

    old_complete_steps_by_type = alert_builder.complete_steps_by_type
    try:
      alert_builder.complete_steps_by_type = mock_complete_steps_by_type

      step_failures = alert_builder.find_current_step_failures(fetch,
          [4120, 4119])

      expected_step_failures = [
        {'build_number': 4119, 'step_name': 'foo_tests'}
      ]
      self.assertEqual(step_failures, expected_step_failures)
    finally:
      alert_builder.complete_steps_by_type = old_complete_steps_by_type


  def test_find_current_step_failures_in_progress_still_failing(self):
    '''Test that only the last failing step gets included if the test step
    failed in both the in-progress build and the last completed build.
    '''
    def fetch(build_id):
      results = None
      if build_id == 4119:
        results = 2

      return {
        'number': build_id,
        'results': results,
      }

    def mock_complete_steps_by_type(build):
      passing = []
      if build['number'] == 4119:
        failing = [{'name': 'foo_tests'}]
      else:
        failing = [{'name': 'foo_tests'}]
      return passing, failing

    old_complete_steps_by_type = alert_builder.complete_steps_by_type
    try:
      alert_builder.complete_steps_by_type = mock_complete_steps_by_type

      step_failures = alert_builder.find_current_step_failures(fetch,
          [4120, 4119])

      expected_step_failures = [
        {'build_number': 4120, 'step_name': 'foo_tests'}
      ]
      self.assertEqual(step_failures, expected_step_failures)
    finally:
      alert_builder.complete_steps_by_type = old_complete_steps_by_type

  def test_find_current_step_failures_in_progress_now_passing(self):
    '''Test that a passing run for the in-progress build overrides a failing
    run from the previous complete build.
    '''
    def fetch(build_id):
      results = None
      if build_id == 4119:
        results = 2

      return {
        'number': build_id,
        'results': results,
      }

    def mock_complete_steps_by_type(build):
      passing = [{'name': 'foo_tests'}]
      if build['number'] == 4119:
        failing = [{'name': 'foo_tests'}]
      else:
        failing = []
      return passing, failing

    old_complete_steps_by_type = alert_builder.complete_steps_by_type
    try:
      alert_builder.complete_steps_by_type = mock_complete_steps_by_type

      step_failures = alert_builder.find_current_step_failures(fetch,
          [4120, 4119])

      expected_step_failures = []
      self.assertEqual(step_failures, expected_step_failures)
    finally:
      alert_builder.complete_steps_by_type = old_complete_steps_by_type
