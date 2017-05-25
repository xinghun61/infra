# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from testing_utils import testing

from handlers import all_flake_occurrences
import main
from model.flake import Flake, FlakyRun, FlakeOccurrence
from model.build_run import PatchsetBuilderRuns, BuildRun


class TestAllFlakeOccurrences(testing.AppengineTestCase):
  app_module = main.app

  def _create_flake(self):
    tf = datetime.datetime(2016, 8, 6, 10, 20, 30)
    ts = tf - datetime.timedelta(hours=1)
    tf2 = tf - datetime.timedelta(days=5)
    ts2 = tf2 - datetime.timedelta(hours=1)
    p = PatchsetBuilderRuns(issue=123456, patchset=1, master='tryserver.test',
                            builder='test-builder').put()
    br_f0 = BuildRun(parent=p, buildnumber=0, result=2, time_started=ts2,
                     time_finished=tf2).put()
    br_f1 = BuildRun(parent=p, buildnumber=1, result=2, time_started=ts,
                     time_finished=tf).put()
    br_s1 = BuildRun(parent=p, buildnumber=2, result=0, time_started=ts,
                     time_finished=tf).put()
    br_f2 = BuildRun(parent=p, buildnumber=3, result=4, time_started=ts,
                     time_finished=tf).put()
    br_s2 = BuildRun(parent=p, buildnumber=4, result=0, time_started=ts,
                     time_finished=tf).put()
    occ_key1 = FlakyRun(failure_run=br_f0, success_run=br_s2,
                        flakes=[
                          FlakeOccurrence(name='foo (x)', failure='foo.bar'),
                          FlakeOccurrence(name='foo (x)', failure='other')],
                        failure_run_time_started=ts2,
                        failure_run_time_finished=tf2).put()
    occ_key2 = FlakyRun(failure_run=br_f1, success_run=br_s1,
                        flakes=[
                          FlakeOccurrence(name='bar (y)', failure='foo.bar')],
                        failure_run_time_started=ts,
                        failure_run_time_finished=tf).put()
    occ_key3 = FlakyRun(failure_run=br_f2, success_run=br_s2,
                        flakes=[
                          FlakeOccurrence(
                            name='foo (x)', failure='foo.bar', issue_id=100),
                          FlakeOccurrence(
                            name='bar (y)', failure='foo.bar', issue_id=200)],
                        failure_run_time_started=ts,
                        failure_run_time_finished=tf).put()
    return Flake(name='foo.bar', count_day=10, is_step=False,
                 occurrences=[occ_key1, occ_key2, occ_key3])

  def test_filter_none(self):
    self.assertEqual([1, 2], all_flake_occurrences.filterNone([1, None, 2]))

  def test_is_webkit_name(self):
    self.assertFalse(all_flake_occurrences._is_webkit_test_name('foo'))
    self.assertFalse(all_flake_occurrences._is_webkit_test_name('Foo.Bar'))
    self.assertFalse(all_flake_occurrences._is_webkit_test_name('Foo.Bar/1'))
    self.assertFalse(all_flake_occurrences._is_webkit_test_name('Foo.Bar/One'))
    self.assertTrue(all_flake_occurrences._is_webkit_test_name('foo/bar.html'))
    self.assertTrue(all_flake_occurrences._is_webkit_test_name('foo/bar.svg'))

  def test_returns_correct_grouped_runs(self):
    flake = self._create_flake()
    flake.is_step = True  # for coverage
    data = all_flake_occurrences.show_all_flakes(flake, False)

    self.assertEqual(len(data['grouped_runs']), 2)
    self.assertEqual(len(data['grouped_runs'][0]), 2)
    self.assertEqual(len(data['grouped_runs'][1]), 1)
    return [data['grouped_runs'][0][0].__dict__,
            data['grouped_runs'][0][1].__dict__,
            data['grouped_runs'][1][0].__dict__]

  def test_correctly_generates_flakiness_dashboard_urls(self):
    flake = self._create_flake()
    data = all_flake_occurrences.show_all_flakes(flake, False)
    return data['flakiness_dashboard_urls']

  def test_html_output(self):
    flake_key = self._create_flake().put()
    return self.test_app.get(
        '/all_flake_occurrences?key=%s' % flake_key.urlsafe()).body.splitlines()

  def test_html_output_with_issue_id(self):
    flake = self._create_flake()
    flake.issue_id = 123456
    flake_key = flake.put()
    return self.test_app.get(
        '/all_flake_occurrences?key=%s' % flake_key.urlsafe()).body.splitlines()

  def test_no_occurrences(self):
    flake_key = Flake(name='foo.bar').put()
    self.test_app.get('/all_flake_occurrences?key=%s' % flake_key.urlsafe())

  def test_key_with_trailing_period(self):
    flake_key = self._create_flake().put()
    self.test_app.get('/all_flake_occurrences?key=%s.' % flake_key.urlsafe())

  def test_missing_key(self):
    response = self.test_app.get('/all_flake_occurrences?key=', status=400)
    self.assertEqual(response.status, '400 Flake ID is not specified')

  def test_all_flake_occurrences_key_with_invalid_key(self):
    response = self.test_app.get('/all_flake_occurrences?key=foo', status=404)
    self.assertEqual(response.status, '404 Failed to find flake with id "foo"')
