# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from testing_support import auto_stub

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

  def testUntilCtrlC(self):
    tasks = [None, None, None]
    def task():
      if not tasks:
        raise KeyboardInterrupt()
      tasks.pop(0)
    ret = outer_loop.loop(task, sleep_timeout=1)
    self.assertTrue(ret)
    self.assertEqual([1, 1, 1], self.sleeps)

  def testUntilDeadlineFastTask(self):
    calls = []
    ret = outer_loop.loop(lambda: calls.append(1), sleep_timeout=3, duration=10)
    self.assertTrue(ret)
    self.assertEqual(4, len(calls))
    self.assertEqual([3, 3, 3], self.sleeps)

  def testUntilDeadlineSlowTask(self):
    # This test exists mostly to satisfy 100% code coverage requirement.
    ret = outer_loop.loop(lambda: time.sleep(6), sleep_timeout=1, duration=5)
    self.assertTrue(ret)
    self.assertEqual([6], self.sleeps)

  def testUntilCtrlCWithErrors(self):
    tasks = [None, None, None]
    def task():
      if not tasks:
        raise KeyboardInterrupt()
      tasks.pop(0)
      raise Exception('Error')
    ret = outer_loop.loop(task, sleep_timeout=1)
    self.assertFalse(ret)
    self.assertEqual([1, 1, 1], self.sleeps)

  def testMaxErrorCount(self):
    tasks = ['ok', 'err', 'ok', 'err', 'err', 'err', 'skipped']
    def task():
      t = tasks.pop(0)
      if t == 'err':
        raise Exception('Horrible error')
    ret = outer_loop.loop(task, sleep_timeout=1, max_errors=3)
    self.assertFalse(ret)
    self.assertEqual(['skipped'], tasks)
    self.assertEqual([1, 1, 1, 1, 1], self.sleeps)
