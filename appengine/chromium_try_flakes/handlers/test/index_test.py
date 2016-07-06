# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import mock

from testing_utils import testing

from handlers import index
import main
from model.flake import Flake, FlakyRun, FlakeOccurrence
from model.build_run import PatchsetBuilderRuns, BuildRun

from time_functions.testing import mock_datetime_utc


class TestIndex(testing.AppengineTestCase):
  app_module = main.app

  def test_filter_none(self):
    self.assertEqual([1, 2], index.filterNone([1, None, 2]))

  def test_smoke(self):
    self.test_app.get('/')

  @staticmethod
  def _create_flakes(ts, tf, ts2, tf2):
    p = PatchsetBuilderRuns(issue=123456, patchset=1, master='tryserver.test',
                            builder='test-builder').put()
    br_f0 = BuildRun(parent=p, buildnumber=0, result=2, time_started=ts2,
                     time_finished=tf2).put()
    br_f1 = BuildRun(parent=p, buildnumber=1, result=2, time_started=ts,
                     time_finished=tf).put()
    br_s1 = BuildRun(parent=p, buildnumber=2, result=0, time_started=ts,
                     time_finished=tf).put()
    br_f2 = BuildRun(parent=p, buildnumber=3, result=4, time_started=ts,
                     time_finished=tf2).put()
    br_s2 = BuildRun(parent=p, buildnumber=4, result=0, time_started=ts,
                     time_finished=tf2).put()
    occ_key1 = FlakyRun(failure_run=br_f0, success_run=br_s2,
                        failure_run_time_started=ts2,
                        failure_run_time_finished=tf2).put()
    occ_key2 = FlakyRun(failure_run=br_f1, success_run=br_s1,
                        failure_run_time_started=ts,
                        failure_run_time_finished=tf).put()
    occ_key3 = FlakyRun(failure_run=br_f2, success_run=br_s2,
                        failure_run_time_started=ts,
                        failure_run_time_finished=tf).put()

    Flake(name='foo', last_hour=True, last_day=True, last_week=True,
          last_month=True).put()
    Flake(name='bar', last_hour=True, last_day=True, last_week=True,
          last_month=True, occurrences=[occ_key1, occ_key2]).put()
    Flake(name='baz', last_hour=True, last_day=True, last_week=True,
          last_month=True, occurrences=[occ_key3]).put()
    Flake(name='zee', last_hour=False, last_day=False, last_week=True,
          last_month=False).put()

  @mock_datetime_utc(2016, 6, 6, 10, 20, 30)
  @mock.patch('handlers.index.MAX_OCCURRENCES_PER_FLAKE_ON_INDEX_PAGE', 1)
  def test_finds_correct_flakes(self):
    tf = datetime.datetime(2016, 6, 6, 6, 20, 30)
    ts = tf - datetime.timedelta(hours=1)
    tf2 = tf - datetime.timedelta(days=5)
    ts2 = tf2 - datetime.timedelta(hours=1)
    self._create_flakes(ts, tf, ts2, tf2)
    data =  index.Index.index('day')
    self.assertEqual(len(data['flakes']), 3)

  @mock_datetime_utc(2016, 6, 6, 10, 20, 30)
  def test_hour_smoke(self):
    tf = datetime.datetime(2016, 6, 6, 10, 10, 30)
    ts = tf - datetime.timedelta(minutes=10)
    tf2 = tf - datetime.timedelta(hours=5)
    ts2 = tf2 - datetime.timedelta(hours=1)
    self._create_flakes(ts, tf, ts2, tf2)
    index.Index.index('hour')

  @mock_datetime_utc(2016, 6, 6, 10, 20, 30)
  def test_week_smoke(self):
    tf = datetime.datetime(2016, 6, 3, 10, 10, 30)
    ts = tf - datetime.timedelta(hours=1)
    tf2 = tf - datetime.timedelta(days=15)
    ts2 = tf2 - datetime.timedelta(hours=1)
    self._create_flakes(ts, tf, ts2, tf2)
    index.Index.index('week')

  @mock_datetime_utc(2016, 6, 6, 10, 20, 30)
  def test_month_smoke(self):
    tf = datetime.datetime(2016, 5, 10, 10, 10, 30)
    ts = tf - datetime.timedelta(hours=1)
    tf2 = tf - datetime.timedelta(days=50)
    ts2 = tf2 - datetime.timedelta(hours=1)
    self._create_flakes(ts, tf, ts2, tf2)
    index.Index.index('month')

  @mock_datetime_utc(2016, 6, 6, 10, 20, 30)
  def test_all_smoke(self):
    tf = datetime.datetime(2015, 6, 10, 10, 10, 30)
    ts = tf - datetime.timedelta(hours=1)
    tf2 = tf - datetime.timedelta(days=300)
    ts2 = tf2 - datetime.timedelta(hours=1)
    self._create_flakes(ts, tf, ts2, tf2)
    index.Index.index('all')
