# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import json
import os
import requests
import simplejson
import subprocess

from infra.libs.buildbot import master
from testing_support import auto_stub


DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')


class TestMasterInformation(auto_stub.TestCase):
  def setUp(self):
    super(TestMasterInformation, self).setUp()
    self.calls = []
    self.master_data = [{
        'alt_port': 8211,
        'buildbot_url': 'http://build.chromium.org/p/chromium.fyi/',
        'dirname': 'master.chromium.fyi',
        'fullhost': 'master1.golo.chromium.org',
        'host': 'master1.golo',
        'internal': False,
        'name': 'ChromiumFYI',
        'port': 8011,
        'slave_port': 8111
    }]
    def _handle_check_output(*args):
      self.calls.append(args[0])
      return json.dumps(self.master_data)
    self.mock(subprocess, 'check_output', _handle_check_output)

    self.chromium_fyi = os.path.join(DATA_DIR, 'master.chromium.fyi')
    self.chromium_webkit = os.path.join(DATA_DIR, 'master.chromium.webkit')
    self.chromium_linux = os.path.join(DATA_DIR, 'master.chromium.linux')
    self.supersecret = os.path.join(
        DATA_DIR, 'build_internal', 'masters', 'master.chromium.supersecret')

    self.Response = collections.namedtuple('Response', ['status_code', 'json'])
    self.res = self.Response(
        status_code=200,
        json=lambda: {'accepting_builds': True})

    self.requests_handler = lambda *_args, **_kwargs: self.res

  def testPidIsRunning(self):
    self.mock(master, '_pid_is_alive', lambda _x: True)
    self.assertTrue(master.buildbot_is_running(self.chromium_fyi))

  def testPidIsNotRunning(self):
    self.mock(master, '_pid_is_alive', lambda _x: False)
    self.assertFalse(master.buildbot_is_running(self.chromium_fyi))

  def testPidfileNotThere(self):
    # _pid_is_alive should not be called here and it is an error if it is.
    # pylint: disable=redundant-unittest-assert
    self.mock(
        master, '_pid_is_alive',
        lambda _x: self.assertTrue(False))  # pragma: no cover
    # There is no twistd.pid in chromium.webkit.
    self.assertFalse(master.buildbot_is_running(self.chromium_webkit))

  def testNoActionsLog(self):
    last_boot = master.get_last_boot(self.chromium_webkit)
    self.assertIsNone(last_boot)

  def testGetLastBoot(self):
    last_boot = master.get_last_boot(self.chromium_fyi)

    # Apr 23 2015 11:01:40 PDT.
    self.assertEqual(last_boot, 1429812100)

  def testGetLastNoNewBuilds(self):
    last_no_new_builds = master.get_last_no_new_builds(self.chromium_fyi)

    # Apr 23 2015 11:01:50 PDT.
    self.assertEqual(last_no_new_builds, 1429812110)

  def testGetLastNoNewBuildsNotThere(self):
    last_no_new_builds = master.get_last_no_new_builds(self.chromium_webkit)
    self.assertIsNone(last_no_new_builds)

  def testGetLastNoNewBuildsButStarted(self):
    last_no_new_builds = master.get_last_no_new_builds(self.chromium_linux)
    self.assertIsNone(last_no_new_builds)

  def testGetLastBootNotThere(self):
    # 'make wait' is not in the sample actions.log.
    last_make_wait = master._get_last_action(self.chromium_fyi, 'make wait')
    self.assertIsNone(last_make_wait)

  def testMasterWebPort(self):
    master_port = master._get_master_web_port(self.chromium_fyi)
    self.assertEquals(master_port, 8011)
    self.assertEquals(len(self.calls), 1)
    self.assertTrue(any(x.endswith('mastermap.py') for x in self.calls[0]))

  def testNoSuchMaster(self):
    master_port = master._get_master_web_port(self.chromium_webkit)
    self.assertIsNone(master_port)

  def testMasterMapInternal(self):
    master._get_master_web_port(self.supersecret)
    self.assertEquals(len(self.calls), 1)
    self.assertTrue(
        any(x.endswith('mastermap_internal.py') for x in self.calls[0]))

  def testAcceptingBuilds(self):
    self.mock(requests, 'get', self.requests_handler)
    self.assertTrue(master.get_accepting_builds(self.chromium_fyi))

  def testNotAcceptingBuilds(self):
    self.res = self.Response(
        status_code=200,
        json=lambda: {'accepting_builds': False})
    self.mock(requests, 'get', self.requests_handler)
    self.assertFalse(master.get_accepting_builds(self.chromium_fyi))

  def testAcceptingBuildsNoMaster(self):
    self.assertIsNone(master.get_accepting_builds(self.chromium_webkit))

  def testBadStatusCode(self):
    # We shouldn't get to the JSON function since we hit 404.
    # pylint: disable=redundant-unittest-assert
    self.res = self.Response(
        status_code=404,
        json=lambda: self.assertTrue(False))  # pragma: no cover
    self.mock(requests, 'get', self.requests_handler)
    self.assertFalse(master.get_accepting_builds(self.chromium_fyi))

  def testBadJson(self):
    def raiser():
      raise simplejson.scanner.JSONDecodeError('bad json', '', 0)
    self.res = self.Response(
        status_code=200,
        json=raiser)
    self.mock(requests, 'get', self.requests_handler)
    self.assertFalse(master.get_accepting_builds(self.chromium_fyi))

  def testTimeout(self):
    def timeout(*_args, **_kwargs):
      raise requests.exceptions.Timeout('timeout')
    self.mock(requests, 'get', timeout)
    self.assertIsNone(master.get_accepting_builds(self.chromium_fyi))

  def testConnectionErr(self):
    def timeout(*_args, **_kwargs):
      raise requests.exceptions.ConnectionError('error')
    self.mock(requests, 'get', timeout)
    self.assertIsNone(master.get_accepting_builds(self.chromium_fyi))

  def testMastermapHost(self):
    masters = [
        {'fullhost': 'bananas.cool'},
        {'fullhost': 'bananas.cool'},
        {'fullhost': 'bananas_dos.cool'},
    ]
    self.mock(master, '_call_mastermap', lambda _x: masters)

    self.assertEqual(
        len(master.get_mastermap_for_host('fake', 'bananas.cool')),
        2)

class TestMasterManipulation(auto_stub.TestCase):
  def setUp(self):
    super(TestMasterManipulation, self).setUp()
    self.chromium_fyi = os.path.join(DATA_DIR, 'master.chromium.fyi')

  def DISABLED_testWithGclientSyncEnabled(self):  # pragma: no cover
    actions = list(master.convert_action_items_to_cli((
      master.GclientSync,
      master.MakeStop,
      master.MakeWait,
      master.MakeStart,
      master.MakeNoNewBuilds),
      self.chromium_fyi,
      enable_gclient=True))
    self.assertEquals(
        [a['cmd'] for a in actions],
        [
          ['gclient', 'sync', '--reset', '--force', '--auto_rebase'],
          ['make', 'stop'],
          ['make', 'wait'],
          ['make', 'start'],
          ['make', 'no-new-builds'],
        ],
    )

  def testWithGclientSyncDisabled(self):
    actions = list(master.convert_action_items_to_cli((
      master.GclientSync,
      master.MakeStop),
      self.chromium_fyi))

    self.assertEquals(
        [a['cmd'] for a in actions],
        [
          ['make', 'stop'],
        ],
    )

  def testInvalid(self):
    with self.assertRaises(ValueError):
      list(master.convert_action_items_to_cli((-100,), self.chromium_fyi))
