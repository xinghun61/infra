# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import collections
import copy
import datetime
import itertools
import logging
import subprocess
import tempfile
import time
import unittest
import urllib2

import dateutil
import mock

from testing_support import auto_stub

from infra.tools.cq_stats import cq_stats


class Args(object):
  def __init__(self, **kwargs):
    self.project = 'test_project'
    self.path_filter_include = None
    self.path_filter_exclude = None
    self.list_rejections = False
    self.list_false_rejections = False
    self.list_uncategorized_flakes = False
    self.use_logs = False
    self.date = datetime.datetime(2014, 1, 1)
    self.range = 'week'
    self.verbose = 'error'
    self.seq = 'false'
    self.thread_pool = 3
    self.bots = []
    for name, val in kwargs.iteritems():
      self.__dict__[name] = val


class ResponseMock(object):
  """Mock out Response class for urllib2.urlopen()."""
  def __init__(self, lines):
    self.lines = lines

  def __iter__(self):
    return self.lines.__iter__()


def urlopen_mock(lines):
  obj = ResponseMock(lines)
  def func(_):
    return obj
  return func


def ensure_serializable(obj):
  if isinstance(obj, dict):
    return {ensure_serializable(k): ensure_serializable(v)
            for k, v in obj.iteritems()}
  elif isinstance(obj, (list, set)):
    return [ensure_serializable(i) for i in obj]
  elif isinstance(obj, datetime.datetime):
    return obj.isoformat()
  elif isinstance(obj, float):
    # Ensure consistent float results - generally float arithmetic
    # can be slightly different between CPUs and implementations.
    return round(obj, 2)
  else:
    return obj


class TestCQStats(auto_stub.TestCase):
  def setUp(self):
    super(TestCQStats, self).setUp()
    self.expectations = []

  def tearDown(self):
    self.expectations = []
    super(TestCQStats, self).tearDown()

  def print_mock(self, fmt='', *args):
    # Make sure lines are correctly split when \n is in the string.
    # This preserves the expectations when going from
    # print;print('string') to print('\nstring').
    self.expectations += ((fmt + '\n') % args).splitlines()

  def test_output(self):
    cq_stats.output('')

  def test_parse_args(self):
    self.mock(argparse.ArgumentParser, 'parse_args',
              lambda *_: Args(date='2014-01-01'))
    self.assertIsNotNone(cq_stats.parse_args())
    self.mock(argparse.ArgumentParser, 'parse_args',
              lambda *_: Args(date=None))
    self.assertIsNotNone(cq_stats.parse_args())

  def test_date_from_string(self):
    self.assertRaises(ValueError, cq_stats.date_from_string, 'bad time')
    self.assertEqual(cq_stats.date_from_string('2014-10-15'),
                     datetime.datetime(2014, 10, 15))

  def test_date_from_timestamp(self):
    self.assertIs(type(cq_stats.date_from_timestamp(12345678.9)),
                  datetime.datetime)

  def test_date_from_git(self):
    self.assertIsNone(cq_stats.date_from_git(''))
    self.assertIsNone(cq_stats.date_from_git('bad time'))
    self.assertEqual(cq_stats.date_from_git('Tue Oct 21 22:38:39 2014'),
                     datetime.datetime(2014, 10, 21, 22, 38, 39))
    # Test dates with offsets.
    self.assertEqual(cq_stats.date_from_git('Tue Oct 21 22:38:39 2014 +0100'),
                     datetime.datetime(2014, 10, 21, 21, 38, 39))
    self.assertEqual(cq_stats.date_from_git('Tue Oct 21 22:38:39 2014 -0100'),
                     datetime.datetime(2014, 10, 21, 23, 38, 39))
    self.assertEqual(cq_stats.date_from_git('Tue Oct 21 22:38:39 2014 -0111'),
                     datetime.datetime(2014, 10, 21, 23, 49, 39))

  def test_fetch_json(self):
    class MockResponse(object):
      def json(self):
        return {}
    self.mock(cq_stats.session, 'get', lambda url: MockResponse())
    self.assertEqual(cq_stats.fetch_json('foo'), {})

  def test_fetch_git_page(self):
    self.mock(urllib2, 'urlopen', urlopen_mock(['{([bad json']))
    self.assertEqual({}, cq_stats.fetch_git_page('url'))
    self.mock(urllib2, 'urlopen', urlopen_mock([
        ")]}'", '{"json": 1}',
    ]))
    self.assertEqual({'json': 1}, cq_stats.fetch_git_page('url'))
    self.assertEqual({'json': 1},
                     cq_stats.fetch_git_page('url', cursor='cursor'))

  def test_fetch_git_logs(self):
    pages = [
        {'log': [
             {'author': {'email': 'noone@chromium.org'},
              'committer': {'email': 'commit-bot@chromium.org',
                            'time': 'Tue Dec 23 22:38:39 2014'}},
             {'author': {'email': 'noone@chromium.org'},
              'committer': {'email': 'commit-bot@chromium.org',
                            'time': 'Tue Nov 23 22:38:39 2014'},
              'tree_diff': [
                {
                  'old_path': 'cc/trees/layer_tree_impl.cc',
                  'new_path': 'cc/trees/layer_tree_impl.cc',
                },
              ]},
             {'author': {'email': 'someone@chromium.org'},
              'committer': {'email': 'anyone@chromium.org',
                            'time': 'Tue Oct 22 22:38:39 2014'}},
             {'author': {'email': 'blink-deps-roller@chromium.org'},
              'committer': {'email': 'commit-bot@chromium.org',
                            'time': 'Tue Oct 21 23:38:39 2014'}},
             {'author': {'email': 'blink-deps-roller@chromium.org'},
              'committer': {'email': 'blink-deps-roller@chromium.org',
                            'time': 'Tue Oct 21 22:38:39 2014'}}
             ],
         'next': 1,
        },
        {'log': [
             {'author': {'email': 'someone@chromium.org'},
              'committer': {'email': 'anyone@chromium.org'}},
             {'author': {'email': 'nobody@chromium.org'},
              'committer': {'email': 'commit-bot@chromium.org',
                            'time': 'Tue Sep 21 22:38:39 2014'}},
             ],
        },
    ]
    # Unused arguments: pylint: disable=W0613
    def fetch_mock(repo_url, cursor=None, page_size=2000):
      if not cursor:
        cursor = 0
      return pages[int(cursor)]

    self.mock(cq_stats, 'fetch_git_page', fetch_mock)

    data = cq_stats.fetch_git_logs(
        'chromium',
        datetime.datetime(2014, 10, 1),
        datetime.datetime(2014, 12, 1),
        Args())

    included_data = cq_stats.fetch_git_logs(
        'chromium',
        datetime.datetime(2014, 10, 1),
        datetime.datetime(2014, 12, 1),
        Args(path_filter_include=['cc']))

    excluded_data = cq_stats.fetch_git_logs(
        'chromium',
        datetime.datetime(2014, 10, 1),
        datetime.datetime(2014, 12, 1),
        Args(path_filter_exclude=['cc']))

    derived_data = cq_stats.derive_git_stats(
        'chromium',
        datetime.datetime(2014,  9, 1),
        datetime.datetime(2014, 12, 1),
        Args(bots=['blink-deps-roller@chromium.org']))

    return map(ensure_serializable,
               [data, included_data, excluded_data, derived_data])

  def test_fetch_stats(self):
    self.mock(cq_stats, 'fetch_json', lambda _: 'json')
    self.assertEqual('json', cq_stats.fetch_stats(Args()))
    self.assertEqual('json', cq_stats.fetch_stats(Args(date=None)))
    self.assertEqual('json', cq_stats.fetch_stats(
        Args(), datetime.datetime(2014, 10, 15)))
    self.assertEqual('json', cq_stats.fetch_stats(
        Args(), datetime.datetime(2014, 10, 15), 'day'))

  def test_fetch_cq_logs(self):
    def mkresults(series):
      return [{'a': n} for n in series]
    pages_default = [
        {'more': True,
         'cursor': '!@#$%^',
         'results': mkresults(range(1, 3)),
        },
        {'more': False,
         'results': mkresults(range(3, 6)),
        },
    ]
    expected_result = mkresults(range(1, 6))

    start_date = datetime.datetime(2014, 10, 15)
    end_date = datetime.datetime(2014, 10, 20)
    pages = []

    def fetch_json_mock(_):
      return pages.pop(0)

    self.mock(cq_stats, 'fetch_json', fetch_json_mock)
    pages[:] = pages_default
    self.assertEqual(cq_stats.fetch_cq_logs(), expected_result)
    pages[:] = pages_default
    self.assertEqual(cq_stats.fetch_cq_logs(start_date=start_date),
                     expected_result)
    pages[:] = pages_default
    self.assertEqual(cq_stats.fetch_cq_logs(end_date=end_date),
                     expected_result)

  def test_organize_stats(self):
    stats = {'results': [
        {'begin': t,
         'stats': [
             {'count': 3, 'type': 'count',
              'name': 'attempt-count'},
             {'count': 2, 'type': 'count',
              'name': 'trybot-bot-false-reject-count'},
             {'count': 1, 'type': 'count',
              'name': 'trybot-bot-pass-count'},
             {'description': 'Total time spent per CQ attempt.',
              'max': 9999.99999,
              'percentile_25': 2512.34567,
              'percentile_75': 7512.34567,
              'percentile_10': 1012.34567,
              'unit': 'seconds',
              'name': 'attempt-durations',
              'percentile_50': 5012.34567,
              'min': 0.00001,
              'sample_size': 10000,
              'percentile_90': 9012.34567,
              'percentile_95': 9512.34567,
              'percentile_99': 9912.34567,
              'type': 'list',
              'mean': 5555.555555},
         ],
         'interval_minutes': 15,
         'project': 'chromium',
         'key': 5976204561612800,
         'end': t + 900} for t in [1415138400, 1415139300]]}

    result = cq_stats.organize_stats(stats)

    # Test that the result stats have the minimal expected dict keys
    # for print_stats().
    expected_keys = set(cq_stats.default_stats().keys())
    self.assertFalse(expected_keys - set(result.keys()))

    self.assertIsNone(cq_stats.organize_stats({}))

    return ensure_serializable(result)

  def test_derive_list_stats(self):
    series = range(100)
    stats = cq_stats.derive_list_stats(series)
    # Ensure consistent float results - generally float arithmetic
    # can be slightly different between CPUs and implementations.
    stats = {k: round(v, 2) for k, v in stats.iteritems() if k != 'raw'}
    self.assertDictEqual({
      '10': 9.9,
      '25': 24.75,
      '50': 49.5,
      '75': 74.25,
      '90': 89.1,
      '95': 94.05,
      '99': 98.01,
      'max': 99.0,
      'mean': 49.5,
      'min': 0.0,
      'size': 100.0,
    }, stats)

    self.assertEqual(cq_stats.derive_list_stats([])['size'], 1)

  def get_mock_derive_patch_stats(self, supported=True):
    def mock_derive_patch_stats(_args, _begin_date, _end_date, patch_id):
      # The original function expects patch_id to be a 2-tuple.
      self.assertIsInstance(patch_id, tuple)
      self.assertEqual(len(patch_id), 2)
      # Note: these fields are required by derive_stats(). Make sure
      # they are present in the unit tests for derive_patch_stats().
      stats = {
          'attempts': 3,
          'false-rejections': 1,
          'rejections': 2,
          'committed': True,
          'patchset-duration-wallclock': 1234.56,
          'patchset-duration': 999.99,
          'failed-jobs-details': {'tester': 2},
          'tryjob-retries': 0,
          'global-retry-quota': 0,
          'supported': supported,
      }
      return patch_id, stats
    return mock_derive_patch_stats

  def test_derive_stats(self):
    # Unused args: pylint: disable=W0613
    def mock_fetch_cq_logs_0(start_date=None, end_date=None, filters=None):
      return []
    # Unused args: pylint: disable=W0613
    def mock_fetch_cq_logs(start_date=None, end_date=None, filters=None):
      return [
          {'fields': {'issue': 12345, 'patchset': 1},
           'timestamp': 1415150483.18568,
          },
      ]

    self.mock(cq_stats, 'derive_patch_stats', self.get_mock_derive_patch_stats(
        supported=True))
    # Test empty logs.
    self.mock(cq_stats, 'fetch_cq_logs', mock_fetch_cq_logs_0)
    self.assertEqual(dict, type(cq_stats.derive_stats(
        Args(), datetime.datetime(2014, 10, 15))))
    # Non-empty logs.
    self.mock(cq_stats, 'fetch_cq_logs', mock_fetch_cq_logs)
    self.assertEqual(dict, type(cq_stats.derive_stats(
        Args(seq=False), datetime.datetime(2014, 10, 15))))

    self.mock(cq_stats, 'derive_patch_stats', self.get_mock_derive_patch_stats(
        supported=False))
    self.assertEqual(dict, type(cq_stats.derive_stats(
        Args(seq=True), datetime.datetime(2014, 10, 15))))

  def test_stats_by_count_entry(self):
    common = {'failed-jobs-details': 'jobs', 'reason1': 2, 'reason2': 3}
    patch_stats = {'some-count': 5}
    patch_stats.update(common)
    expected = {'count': 5, 'patch_id': 'patch'}
    expected.update(common)
    self.assertEqual(expected, cq_stats.stats_by_count_entry(
        patch_stats, 'some-count', 'patch', ['reason1', 'reason2']))

  def test_parse_json(self):
    self.assertEqual({'a': 5}, cq_stats.parse_json('{"a": 5}'))
    self.assertEqual({'a': 5}, cq_stats.parse_json({'a': 5}))
    self.assertEqual('bad json)}', cq_stats.parse_json('bad json)}'))
    self.assertEqual({}, cq_stats.parse_json('bad json)}', return_type=dict))

  def test_parse_failing_tryjobs(self):
    message = (
        'Try jobs failed on following builders:\n'
        '  try_rel on tryserver.fake (http://url.com/8633)\n'
        '  dont_try_rel on tryserver.fake (http://url.com/8634)')
    self.assertEqual(['try_rel', 'dont_try_rel'],
                     cq_stats.parse_failing_tryjobs(message))
    self.assertEqual([], cq_stats.parse_failing_tryjobs(''))
    self.assertEqual([], cq_stats.parse_failing_tryjobs('single line'))
    self.assertEqual([], cq_stats.parse_failing_tryjobs('empty line\n\n'))

  def test_derive_patch_stats(self):
    time_obj = {'time': 1415150492.4}
    def attempt(message, commit=False, supported=True, reason='', retry=False,
                verifier_pass=True, files=None, job_updates=None):
      time_obj['time'] += 1.37  # Trick python to use global var.
      entries = []
      entries.append({'fields': {'action': 'patch_start', 'files': files},
                      'timestamp': time_obj['time']})
      time_obj['time'] += 1.37
      if not supported:
        entries.append({'fields': {'action': 'verifier_custom_trybots'},
                        'timestamp': time_obj['time']})
      time_obj['time'] += 1.37
      if job_updates:
        for update in job_updates:
          entries.append({
              'fields': {'action': 'verifier_jobs_update', 'jobs': update},
              'timestamp': time_obj['time']
          })
      time_obj['time'] += 1.37
      if retry:
        entries.append({'fields': {'action': 'verifier_retry'},
                        'timestamp': time_obj['time']})
      time_obj['time'] += 1.37
      entries.append({'fields': {
              'action': 'verifier_pass' if verifier_pass else 'verifier_fail',
              'verifier': 'try job',
          },
          'timestamp': time_obj['time']})
      time_obj['time'] += 1.37
      if commit:
        entries.append({'fields': {'action': 'patch_committed'},
                        'timestamp': time_obj['time']})
      else:
        details = [] if not supported else [{
            'master': 'master', 'builder': 'builder'
        }]
        entries.append({'fields': {'action': 'patch_failed',
                                   'reason': {'fail_type': reason,
                                              'fail_details': details}},
                        'timestamp': time_obj['time']})
      time_obj['time'] += 1.37
      entries.append({'fields': {'action': 'patch_stop', 'message': message},
                      'timestamp': time_obj['time']})
      return entries

    attempts = [
        attempt('CQ bit was unchecked on CL'),
        attempt('No LGTM from valid reviewers', reason='reviewer-lgtm'),
        attempt('A disapproval has been posted', reason='not-lgtm'),
        attempt('Transient error: Invalid delimiter',
                reason='invalid-delimiter'),
        attempt('Failed to commit', reason='failed-commit'),
        attempt('Failed to apply patch', reason='failed-patch'),
        attempt('Presubmit check', reason='failed-presubmit-check'),
        attempt('webkit CL', files=['third_party/WebKit/Source/config.h']),
        attempt('infra CL', files=['infra/config/cq.cfg']),
        attempt('other CL', files=['OWNERS']),
        # This also checks for the combination of failed-jobs and no
        # failed jobs list supplied.
        attempt('Custom trybots', supported=False, reason='failed-jobs'),
        attempt('job timeout', job_updates=[{'JOB_TIMED_OUT': [{}]}]),
        attempt('job failure', job_updates=[{'JOB_FAILED': [{'result': 2}]}]),
        attempt('job failure reason', job_updates=[{'JOB_FAILED': [
            {'result': 2, 'build_properties': {'failure_type': 'TEST_FAILURE'}}
        ]}]),
        attempt('job exception', job_updates=[{'JOB_FAILED': [{'result': 4}]}]),
        attempt('Retrying', retry=True),
        attempt('CLs for remote refs other than refs/heads/master'),
        attempt('Try jobs failed:\n test_dbg', reason='failed-jobs',
                verifier_pass=False),
        attempt('Try jobs failed:\n chromium_presubmit',
                verifier_pass=False, reason='failed-jobs'),
        attempt('Exceeded time limit waiting for builds to trigger',
                reason='failed-to-trigger'),
        attempt('Some totally random unknown reason') + [
            {'fields': {'action': 'random garbage'},
             'timestamp': time_obj['time'] + 0.5}],
        attempt('', commit=True),
    ]

    # Dangerous default value, unused args: pylint: disable=W0102,W0613
    def mock_fetch_cq_logs(start_date=None, end_date=None, filters=[]):
      entries = list(itertools.chain(*attempts))
      entries.reverse()
      return entries

    # Dangerous default value, unused args: pylint: disable=W0102,W0613
    def mock_fetch_cq_logs_0(start_date=None, end_date=None, filters=[]):
      return []

    # Dangerous default value, unused args: pylint: disable=W0102,W0613
    def mock_fetch_cq_logs_junk(start_date=None, end_date=None, filters=[]):
      return [{'fields': {'action': 'cq_start'}, 'timestamp': 1415150662.3}]

    self.mock(cq_stats, 'fetch_cq_logs', mock_fetch_cq_logs)

    patch_id = ('pid', 5)
    args = mock.Mock()
    args.path_filter_include = None
    args.path_filter_exclude = None
    args.use_message_parsing = True
    pid, stats = cq_stats.derive_patch_stats(
        args,
        datetime.datetime(2014, 10, 15),
        datetime.datetime(2014, 10, 15),
        patch_id)
    self.assertEqual(patch_id, pid)
    # Check required fields in the result.
    mock_derive_patch_stats = self.get_mock_derive_patch_stats()
    for k in mock_derive_patch_stats(None, None, None, patch_id)[1]:
      self.assertIsNotNone(stats.get(k))
    # A few sanity checks.
    self.assertEqual(stats['attempts'], len(attempts))
    self.assertEqual(stats['committed'], True)
    self.assertGreater(stats['false-rejections'], 0)

    # Test path filters.
    args.path_filter_include = ['infra']
    args.path_filter_exclude = ['third_party/WebKit']
    pid, stats = cq_stats.derive_patch_stats(
        args,
        datetime.datetime(2014, 10, 15),
        datetime.datetime(2014, 10, 15),
        patch_id)
    self.assertEqual(patch_id, pid)

    self.mock(cq_stats, 'fetch_cq_logs', mock_fetch_cq_logs_0)
    pid, stats = cq_stats.derive_patch_stats(
        args,
        datetime.datetime(2014, 10, 15),
        datetime.datetime(2014, 10, 15),
        patch_id)
    # Cover the case when there are actions, but no CQ attempts.
    self.mock(cq_stats, 'fetch_cq_logs', mock_fetch_cq_logs_junk)
    pid, stats = cq_stats.derive_patch_stats(
        args,
        datetime.datetime(2014, 10, 15),
        datetime.datetime(2014, 10, 15),
        patch_id)

  def test_print_attempt_counts(self):
    self.mock(cq_stats, 'output', self.print_mock)

    stats = cq_stats.default_stats()
    stats['patch_stats'] = {
        (123, 1): {
            'attempts': 1,
            'false-rejections': 0,
            'rejections': 1,
            'committed': False,
            'patchset-duration': 3600,
            'patchset-duration-wallclock': 3600,
            'failed-jobs-details': {
                'builder_a': 1,
            },
        },
    }
    cq_stats._derive_stats_from_patch_stats(stats)

    cq_stats.print_attempt_counts(
        stats, 'rejections', 'were unsuccessful',
        item_name=None, committed=False, details=True)

    cq_stats.print_attempt_counts(
        stats, 'rejections', 'failed jobs',
        item_name=None, committed=False)

    return self.expectations

  def test_print_usage(self):
    self.mock(cq_stats, 'output', self.print_mock)

    stats = cq_stats.default_stats()
    stats['usage'] = cq_stats.derive_log_stats([])
    cq_stats.print_usage(stats)

    return self.expectations

  def test_print_flakiness_stats(self):
    self.mock(cq_stats, 'output', self.print_mock)
    args = Args()
    stats_set = cq_stats.default_stats()
    stats_set['begin'] = args.date
    stats_set['end'] = args.date + datetime.timedelta(days=7)

    stats_set['patch_stats'].update({
        (123, 1): {
            'attempts': 1,
            'false-rejections': 0,
            'rejections': 1,
            'committed': False,
            'patchset-duration': 3600,
            'patchset-duration-wallclock': 3600,
            'failed-jobs-details': {
                'builder_a': 1,
            },
        },
    })

    self.mock(cq_stats, 'fetch_json', lambda _: [{
      'master': 'tryserver.chromium.linux',
      'builder': 'chromium_presubmit',
      'result': 0,
      'url': 'https://build.chromium.org/10',
    }, {
      'master': 'tryserver.chromium.linux',
      'builder': 'chromium_presubmit',
      'result': -1,
      'url': 'https://build.chromium.org/20',
    }, {
      'master': 'tryserver.chromium.linux',
      'builder': 'chromium_presubmit',
      'result': 2,
      'url': 'https://build.chromium.org/30',
    }, {
      'master': 'tryserver.chromium.linux',
      'builder': 'linux_chromium_rel_ng',
      'result': 2,
      'build_properties': '{"failure_type": "COMPILE_FAILURE"}',
      'url': 'https://build.chromium.org/40',
    }, {
      'master': 'tryserver.chromium.linux',
      'builder': 'linux_chromium_rel_ng',
      'result': 2,
      'build_properties': '{"failure_type": "TEST_FAILURE"}',
      'url': 'https://build.chromium.org/50',
    }, {
      'master': 'tryserver.chromium.linux',
      'builder': 'linux_chromium_rel_ng',
      'result': 2,
      'build_properties': '{"failure_type": "INVALID_TEST_RESULTS"}',
      'url': 'https://build.chromium.org/50',
    }, {
      'master': 'tryserver.chromium.linux',
      'builder': 'linux_chromium_rel_ng',
      'result': 2,
      'build_properties': '{"failure_type": "PATCH_FAILURE"}',
      'url': 'https://build.chromium.org/50',
    }, {
      'master': 'tryserver.chromium.linux',
      'builder': 'chromium_presubmit',
      'result': 4,
      'url': 'https://build.chromium.org/60',
    }])

    cq_stats.print_flakiness_stats(args, stats_set)

    args.seq = False
    args.list_uncategorized_flakes = True
    self.mock(cq_stats, 'fetch_json', lambda _: [{
      'master': 'tryserver.chromium.linux',
      'builder': 'chromium_presubmit',
      'result': 0,
      'url': 'https://build.chromium.org/70',
    }, {
      'master': 'tryserver.chromium.linux',
      'builder': 'chromium_presubmit',
      'result': 2,
      'url': 'https://build.chromium.org/75',
    }, {
      'master': 'tryserver.chromium.linux',
      'builder': 'linux_chromium_rel_ng',
      'result': 2,
      'build_properties': '{"failure_type": "COMPILE_FAILURE"}',
      'url': 'https://build.chromium.org/80',
    }])
    cq_stats.print_flakiness_stats(args, stats_set)

    return self.expectations

  # Expectation: must print stats in a certain format.
  # Assumption: input stats at minimum have the keys from
  # default_stats(). This is verified in test_organize_stats().
  def test_print_stats(self):
    self.mock(cq_stats, 'output', self.print_mock)
    args = Args()
    stats_set = cq_stats.default_stats()
    stats_set['begin'] = args.date
    stats_set['end'] = args.date + datetime.timedelta(days=7)

    stats_set['patch_stats'].update({
        (123, 1): {
            'attempts': 1,
            'false-rejections': 0,
            'rejections': 1,
            'committed': False,
            'patchset-duration': 3600,
            'patchset-duration-wallclock': 3600,
            'failed-jobs-details': {
                'builder_a': 1,
            },
        },
        (456, 1): {
            'attempts': 1,
            'false-rejections': 0,
            'rejections': 1,
            'committed': False,
            'patchset-duration': 7200,
            'patchset-duration-wallclock': 7200,
            'failed-jobs-details': {
                'builder_a': 1,
            },
        },
    })

    swapped_stats = copy.deepcopy(stats_set)
    swapped_stats['begin'], swapped_stats['end'] = (
        swapped_stats['end'], swapped_stats['begin'])

    cq_stats.print_stats(args, None)
    cq_stats.print_stats(args, stats_set)
    cq_stats.print_stats(args, swapped_stats)

    args = Args()
    args.path_filter_include = ['third_party/WebKit']
    cq_stats.print_stats(args, stats_set)

    args = Args()
    args.path_filter_exclude = ['third_party/WebKit']
    cq_stats.print_stats(args, stats_set)

    return self.expectations

  def test_print_log_stats(self):
    self.mock(cq_stats, 'output', self.print_mock)
    args = Args(use_logs=True)
    stats_set = cq_stats.default_stats()
    stats_set['begin'] = args.date
    stats_set['end'] = args.date + datetime.timedelta(days=7)

    cq_stats.print_stats(args, stats_set)
    return self.expectations

  def test_acquire_stats(self):
    self.mock(cq_stats, 'fetch_json', lambda _: 'json')
    self.mock(cq_stats, 'organize_stats',
        lambda *_args, **_kwargs: {
            'latest': cq_stats.default_stats(),
            'previous': cq_stats.default_stats()})
    self.mock(cq_stats, 'derive_stats', lambda *_args, **_kwargs: {})
    self.mock(cq_stats, 'derive_git_stats', lambda *_: {})

    cq_stats.acquire_stats(Args(project='chromium', bots=[]),
                           add_tree_stats=False)
    cq_stats.acquire_stats(Args(
        project='chromium', bots=[], use_logs=True, range='week'))
    cq_stats.acquire_stats(Args(
        project='chromium', bots=[], use_logs=True, range='day'))
    cq_stats.acquire_stats(Args(
        project='chromium', bots=[], use_logs=True, range='hour'))

  def test_main(self):
    self.mock(cq_stats, 'output', self.print_mock)
    self.mock(cq_stats, 'parse_args', lambda: Args(
        project='chromium', log_level=logging.CRITICAL, logs_black_list=None,
        logs_directory=tempfile.gettempdir(),
        logs_program_name='cq_stats_test', logs_debug_file=False))
    self.mock(cq_stats, 'acquire_stats', lambda _: cq_stats.default_stats())
    cq_stats.main()
    return self.expectations
