# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from testing_support import auto_stub

from infra.libs.service_utils import outer_loop

from infra_libs.ts_mon import interface
from infra_libs.ts_mon.test import stubs


class TestOuterLoop(auto_stub.TestCase):

  class MyTime():
    def __init__(self):
      self.sleeps = []
      self.now = 0
    def sleep(self, t):
      self.sleeps.append(t)
      self.now += t
    def time(self):
      return self.now

  def setUp(self):
    super(TestOuterLoop, self).setUp()
    self.time_mod = TestOuterLoop.MyTime()

  def testLongUnsuccessfulJobStillFails(self):
    ret = outer_loop.loop(lambda: self.time_mod.sleep(100),
                          sleep_timeout=lambda: 1, duration=1, max_errors=5,
                          time_mod=self.time_mod)
    self.assertEqual(outer_loop.LoopResults(False, 1), ret)
    self.assertEqual([100], self.time_mod.sleeps)

  def testUntilCtrlC(self):
    tasks = [None, None, None]
    def task():
      if not tasks:
        raise KeyboardInterrupt()
      tasks.pop(0)
      return True
    ret = outer_loop.loop(task, sleep_timeout=lambda: 1, time_mod=self.time_mod)
    self.assertEqual(outer_loop.LoopResults(True, 0), ret)
    self.assertEqual([1, 1, 1], self.time_mod.sleeps)

  def testUntilDeadlineFastTask(self):
    calls = []
    def task():
      calls.append(1)
      return True
    ret = outer_loop.loop(task, sleep_timeout=lambda: 3, duration=10,
                          time_mod=self.time_mod)
    self.assertEqual(outer_loop.LoopResults(True, 0), ret)
    self.assertEqual(4, len(calls))
    self.assertEqual([3, 3, 3], self.time_mod.sleeps)

  def testUntilDeadlineSlowTask(self):
    # This test exists mostly to satisfy 100% code coverage requirement.
    def task():
      self.time_mod.sleep(6)
      return True
    ret = outer_loop.loop(task, sleep_timeout=lambda: 1, duration=5,
                          time_mod=self.time_mod)
    self.assertEqual(outer_loop.LoopResults(True, 0), ret)
    self.assertEqual([6], self.time_mod.sleeps)

  def testUntilCtrlCWithErrors(self):
    tasks = [None, None, None]
    def task():
      if not tasks:
        raise KeyboardInterrupt()
      tasks.pop(0)
      raise Exception('Error')
    ret = outer_loop.loop(task, sleep_timeout=lambda: 1, time_mod=self.time_mod)
    self.assertEqual(outer_loop.LoopResults(True, 3), ret)
    self.assertEqual([1, 1, 1], self.time_mod.sleeps)

  def testMaxErrorCount(self):
    tasks = ['ok', 'err', 'false', 'ok', 'err', 'false', 'err', 'skipped']
    def task():
      t = tasks.pop(0)
      if t == 'err':
        raise Exception('Horrible error')
      if t == 'false':
        return False
      return True
    ret = outer_loop.loop(task, sleep_timeout=lambda: 1, max_errors=3,
                          time_mod=self.time_mod)
    self.assertEqual(outer_loop.LoopResults(False, 5), ret)
    self.assertEqual(['skipped'], tasks)
    self.assertEqual([1, 1, 1, 1, 1, 1], self.time_mod.sleeps)
