# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import unittest

from infra.tools.builder_alerts import alert_builder
from infra.tools.builder_alerts import buildbot


# Unused argument - pylint: disable=W0613


class AlertBuilderTest(unittest.TestCase):
  # TODO(ojan): Is there a better way to do this?
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

  def test_compute_transition_failure_to_failing_build(self):
    '''Tests that a failure that started in a run after there were already
    failures gets the correct builds'''
    old_reasons_for_failure = alert_builder.reasons_for_failure
    old_fetch_build_json = buildbot.fetch_build_json

    def mock_reasons_for_failure(step, build, builder_name,
        master_url):  # pragma: no cover
      if build['number'] == 4120:
        return ['Foo.NewFailure', 'Foo.OldFailure']
      return ['Foo.OldFailure']

    def mock_fetch_build_json(cache, master, builder, num):  # pragma: no cover
      build = copy.deepcopy(AlertBuilderTest.k_example_failing_build)
      build['number'] = num
      return build

    try:
      alert_builder.reasons_for_failure = mock_reasons_for_failure
      buildbot.fetch_build_json = mock_fetch_build_json

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

      cache = {}
      recent_build_ids = [4119, 4120]

      last_pass, first_fail = (
          alert_builder.compute_transition(cache, failure, recent_build_ids))
      self.assertEqual(last_pass['number'], 4119)
      self.assertEqual(first_fail['number'], 4120)
    finally:
      alert_builder.reasons_for_failure = old_reasons_for_failure
      buildbot.fetch_build_json = old_fetch_build_json


  def test_fill_in_transition_uses_old_alerts(self):
    '''Tests that fill_in_transition doesn't fetch data for old alerts'''
    old_compute_transition = alert_builder.compute_transition

    def mock_compute_transition(cache, alert,
        recent_build_ids):  # pragma: no cover
      return AlertBuilderTest.k_example_failing_build, None

    alert_builder.compute_transition = mock_compute_transition

    try:
      cache = {}
      alert = {
        'last_result_time': 1407827665.556039,
        'latest_revisions': {
          'v8': '23036',
          'chromium': '288872',
          'nacl': '13599',
          'blink': '179989'
        },
        'builder_name': 'Win Release',
        'last_failing_build': 4119,
        'reason': 'Foo.NewFailure',
        'master_url': 'https://build.chromium.org/p/chromium.lkgr',
        'step_name': 'foo_tests'
      }
      alert_key = alert_builder.generate_alert_key(alert['master_url'],
          alert['builder_name'], alert['step_name'], alert['reason'])
      recent_build_ids = [4119]
      old_alerts = {}
      expected_alert = {
          'passing_build': 23,
          'failing_build': 42,
          'failing_revisions': 4711,
          'passing_revisions': 31337,
      }
      old_alerts[alert_key] = expected_alert
      expected_alert.update(alert)

      alerts = alert_builder.fill_in_transition(cache, alert, recent_build_ids,
          old_alerts)
      self.assertEqual(alerts, expected_alert)
    finally:
      alert_builder.compute_transition = old_compute_transition


  def test_complete_steps_by_type(self):
    build = {
      'steps': [
        { 'isFinished': True, 'name': 'finished_pass_step', 'results': [0] },
        { 'isFinished': True, 'name': 'finished_fail_step', 'results': [2] },
        { 'isFinished': False, 'name': 'unfinished_pass_step', 'results': [0] },
        { 'isFinished': False, 'name': 'unfinished_fail_step', 'results': [2] },
      ]
    }

    passing, failing = alert_builder.complete_steps_by_type(build)

    self.assertEqual(passing, [
      {'isFinished': True, 'name': 'finished_pass_step', 'results': [0]}
    ])
    self.assertEqual(failing, [
      {'isFinished': True, 'name': 'finished_fail_step', 'results': [2]}
    ])


  def test_find_current_step_failures_no_recent_build_ids(self):
    '''Silly test to get coverage of scenario that never happens, i.e.
    padding in an empty list of recent build ids.
    '''
    step_failures = alert_builder.find_current_step_failures(None, [])
    self.assertEqual(step_failures, [])


  def test_find_current_step_failures_only_ignored_steps(self):
    '''Test that when the only failing steps are ignored steps, we return those
    as the list of step failures.
    '''
    def fetch(build_id):
      return {
        'number': 4119,
        'results': 2,
      }

    def mock_complete_steps_by_type(build):
      passing = []
      failing = [{'name': 'steps'}]
      return passing, failing

    old_complete_steps_by_type = alert_builder.complete_steps_by_type
    try:
      alert_builder.complete_steps_by_type = mock_complete_steps_by_type
      step_failures = alert_builder.find_current_step_failures(fetch, [4119])
      expected_step_failures = [
        {'build_number': 4119, 'step_name': 'steps'}
      ]
      self.assertEqual(step_failures, expected_step_failures)
    finally:
      alert_builder.complete_steps_by_type = old_complete_steps_by_type


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
        failing = [{'name': 'foo_tests'}, {'name': 'steps'}]
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
