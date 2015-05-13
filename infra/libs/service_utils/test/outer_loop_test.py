# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from testing_support import auto_stub

from infra.libs import ts_mon
from infra.libs.service_utils import outer_loop


class TestOuterLoop(auto_stub.TestCase):
  def setUp(self):
    super(TestOuterLoop, self).setUp()
    self.sleeps = []
    self.now = 0
    def mocked_sleep(t):
      self.sleeps.append(t)
      self.now += t
    self.mock(time, 'sleep', mocked_sleep)
    self.mock(time, 'time', lambda: self.now)
    # TODO(agable): Switch to using infra.libs.ts_mon.stubs when that exists.
    ts_mon.interface._state.metrics = set()

  def tearDown(self):
    super(TestOuterLoop, self).tearDown()
    ts_mon.interface._state.metrics = set()

  def testLongUnsuccessfulJobStillFails(self):
    ret = outer_loop.loop(
      lambda: time.sleep(100), sleep_timeout=lambda: 1, duration=1,
      max_errors=5)
    self.assertEqual(outer_loop.LoopResults(False, 1), ret)
    self.assertEqual([100], self.sleeps)

  def testUntilCtrlC(self):
    tasks = [None, None, None]
    def task():
      if not tasks:
        raise KeyboardInterrupt()
      tasks.pop(0)
      return True
    ret = outer_loop.loop(task, sleep_timeout=lambda: 1)
    self.assertEqual(outer_loop.LoopResults(True, 0), ret)
    self.assertEqual([1, 1, 1], self.sleeps)

  def testUntilDeadlineFastTask(self):
    calls = []
    def task():
      calls.append(1)
      return True
    ret = outer_loop.loop(task, sleep_timeout=lambda: 3, duration=10)
    self.assertEqual(outer_loop.LoopResults(True, 0), ret)
    self.assertEqual(4, len(calls))
    self.assertEqual([3, 3, 3], self.sleeps)

  def testUntilDeadlineSlowTask(self):
    # This test exists mostly to satisfy 100% code coverage requirement.
    def task():
      time.sleep(6)
      return True
    ret = outer_loop.loop(task, sleep_timeout=lambda: 1, duration=5)
    self.assertEqual(outer_loop.LoopResults(True, 0), ret)
    self.assertEqual([6], self.sleeps)

  def testUntilCtrlCWithErrors(self):
    tasks = [None, None, None]
    def task():
      if not tasks:
        raise KeyboardInterrupt()
      tasks.pop(0)
      raise Exception('Error')
    ret = outer_loop.loop(task, sleep_timeout=lambda: 1)
    self.assertEqual(outer_loop.LoopResults(True, 3), ret)
    self.assertEqual([1, 1, 1], self.sleeps)

  def testMaxErrorCount(self):
    tasks = ['ok', 'err', 'false', 'ok', 'err', 'false', 'err', 'skipped']
    def task():
      t = tasks.pop(0)
      if t == 'err':
        raise Exception('Horrible error')
      if t == 'false':
        return False
      return True
    ret = outer_loop.loop(task, sleep_timeout=lambda: 1, max_errors=3)
    self.assertEqual(outer_loop.LoopResults(False, 5), ret)
    self.assertEqual(['skipped'], tasks)
    self.assertEqual([1, 1, 1, 1, 1, 1], self.sleeps)
