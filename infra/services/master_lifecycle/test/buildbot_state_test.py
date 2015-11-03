# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from testing_support import auto_stub

from infra.libs.buildbot import master
from infra_libs.time_functions import timestamp
from infra.services.master_lifecycle import buildbot_state

class TestBuildbotState(auto_stub.TestCase):
  def setUp(self):
    super(TestBuildbotState, self).setUp()
    self.matcher = buildbot_state.construct_pattern_matcher()
    self.utcnow = 2000
    self.last_boot = 1000
    self.last_no_new_builds = 1100
    self.buildbot_is_running = True
    self.accepting_builds = True
    self.current_running_builds = set(('test', d) for d in xrange(10))
    self.desired_buildbot_state = 'running'
    self.desired_transition_time = 900
    self.builder_filters = None

    def utcnow_handler():
      return self.utcnow
    def last_boot_handler(*_args):
      return self.last_boot
    def last_no_new_builds_handler(*_args):
      return self.last_no_new_builds
    def buildbot_is_running_handler(*_args):
      return self.buildbot_is_running
    def buildstate_handler(*_args, **_kwargs):
      return self.accepting_builds, self.current_running_builds

    self.mock(timestamp, 'utcnow_ts', utcnow_handler)
    self.mock(master, 'get_last_boot', last_boot_handler)
    self.mock(master, 'get_last_no_new_builds', last_no_new_builds_handler)
    self.mock(master, 'buildbot_is_running', buildbot_is_running_handler)
    self.mock( master, 'get_buildstate', buildstate_handler)

  def _get_evidence(self):
    evidence = buildbot_state.collect_evidence(
        'fake_dir',
        builder_filters=self.builder_filters)
    evidence['desired_buildbot_state'] = {
        'desired_state': self.desired_buildbot_state,
        'transition_time_utc': self.desired_transition_time,
    }
    return evidence

  def _get_state(self):
    return self.matcher.get_state(self._get_evidence())

  def _get_execution_list(self):
    return self.matcher.execution_list(self._get_evidence())

  def testPatternMatcherIsSane(self):
    self.assertTrue(self.matcher.is_correct)


  #### Tests.

  def testBuildbotIsOffline(self):
    self.buildbot_is_running = False
    state = self._get_state()['buildbot']
    self.assertEqual(state, 'offline')

  def testBuildbotIsStarting(self):
    self.utcnow = self.last_boot + 4 * 60
    self.accepting_builds = None
    state = self._get_state()['buildbot']
    self.assertEqual(state, 'starting')

  def testBuildbotIsRunning(self):
    state = self._get_state()['buildbot']
    self.assertEqual(state, 'running')

  def testBuildbotIsDraining(self):
    self.accepting_builds = False
    self.utcnow = self.last_no_new_builds + 4 * 60
    state = self._get_state()['buildbot']
    self.assertEqual(state, 'draining')

  def testBuildbotIsDrainedNoBuilds(self):
    self.accepting_builds = False
    self.current_running_builds = set()
    self.utcnow = self.last_no_new_builds + 4 * 60
    state = self._get_state()['buildbot']
    self.assertEqual(state, 'drained')

  def testBuildbotIsDrainingWithBuilderFilters(self):
    self.accepting_builds = False
    self.current_running_builds = set([
      ('irrelevant builder', 1),
      ('my special builder', 1337),
      ])
    self.builder_filters = [
        re.compile('.*special.*'),
        ]
    self.utcnow = self.last_no_new_builds + 4 * 60
    state = self._get_state()['buildbot']
    self.assertEqual(state, 'draining')

  def testBuildbotIsDrainedWithBuilderFiltersNoBuilds(self):
    self.accepting_builds = False
    self.current_running_builds = set([
      ('irrelevant builder', 1),
      ])
    self.builder_filters = [
        re.compile('.*special.*'),
        ]
    self.utcnow = self.last_no_new_builds + 4 * 60
    state = self._get_state()['buildbot']
    self.assertEqual(state, 'drained')

  def testBuildbotIsDrainedTimeout(self):
    self.accepting_builds = False
    state = self._get_state()['buildbot']
    self.assertEqual(state, 'drained')

  def testBuildbotIsCrashing(self):
    self.accepting_builds = None
    state = self._get_state()['buildbot']
    self.assertEqual(state, 'crashed')

  def testDesiredOffline(self):
    self.desired_buildbot_state = 'offline'
    state = self._get_state()['desired_buildbot_state']
    self.assertEqual(state, 'offline')

  def testDesiredInvalid(self):
    self.desired_buildbot_state = 'delicious'
    with self.assertRaises(ValueError):
      _ = self._get_state()

  def testDesiredUpToDate(self):
    state = self._get_state()['desired_transition_time']
    self.assertEqual(state, 'hold_steady')

  def testDesiredFuture(self):
    self.desired_transition_time = 3000
    with self.assertRaises(ValueError):
      _ = self._get_state()

  def testDesiredReboot(self):
    self.desired_transition_time = 1100
    state = self._get_state()['desired_transition_time']
    self.assertEqual(state, 'ready_to_fire')

  def testNoLastBoot(self):
    self.last_boot = None
    state = self._get_state()['desired_transition_time']
    self.assertEqual(state, 'ready_to_fire')

  def testOfflineStaysOffline(self):
    self.desired_buildbot_state = 'offline'
    self.buildbot_is_running = False
    _, _, execution_list = self._get_execution_list()
    self.assertEqual(execution_list, [])

  def testRestartKickedOff(self):
    self.desired_transition_time = 1100
    _, _, execution_list = self._get_execution_list()
    self.assertEqual(execution_list, [master.MakeNoNewBuilds])

  def testTurnDown(self):
    self.desired_buildbot_state = 'offline'
    self.accepting_builds = False
    _, _, execution_list = self._get_execution_list()
    self.assertEqual(execution_list, [master.MakeStop])

  def testStartUp(self):
    self.buildbot_is_running = False
    _, _, execution_list = self._get_execution_list()
    self.assertEqual(execution_list, [master.GclientSync, master.MakeStart])

  def testRestart(self):
    self.accepting_builds = False
    _, _, execution_list = self._get_execution_list()
    self.assertEqual(execution_list, [
      master.GclientSync,
      master.MakeStop,
      master.MakeWait,
      master.MakeStart])
