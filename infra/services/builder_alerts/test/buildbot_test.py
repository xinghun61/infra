# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import os
import shutil
import tempfile
import time
import unittest

from infra.services.builder_alerts import buildbot


# Unused argument - pylint: disable=W0613


class TestCaseWithDiskCache(unittest.TestCase):
  def setUp(self):
    self.cache_path = tempfile.mkdtemp()
    self.cache = buildbot.DiskCache(self.cache_path)

  def tearDown(self):
    self.cache = None
    shutil.rmtree(self.cache_path, ignore_errors=True)


class DiskCacheTest(TestCaseWithDiskCache):
  def test_build_cache(self):
    def write_garbage(key):
      path = os.path.join(self.cache_path, key)
      with open(path, 'w') as cached:
        cached.write("foo")

    test_key = 'foo/bar'
    self.assertFalse(self.cache.has(test_key))

    test_data = ['test']
    self.cache.set(test_key, test_data)
    # Set it a second time to hit the "already there" case.
    self.cache.set(test_key, test_data)

    self.assertTrue(self.cache.has(test_key))
    self.assertEquals(self.cache.get(test_key), test_data)

    self.assertIsNone(self.cache.get('does_not_exist'))
    self.assertIsNotNone(self.cache.key_age(test_key))

    write_garbage(test_key)
    self.assertIsNone(self.cache.get(test_key))

  def test_latest_builder_info_and_alerts_for_master(self):
    k_example_master_json = {
      "builders": {
        "Win Builder": {
          "basedir": "Win_Builder",
          "cachedBuilds": [
            0,
            1770,
            1771
          ],
          "category": "2windows",
          "currentBuilds": [
            1772
          ],
          "pendingBuilds": 7,
          "slaves": [
            "build2-m1"
          ],
          "state": "building"
        },
        "Not Running Builder": {
          "basedir": "Not_Running_Builder",
          "cachedBuilds": [
          ],
          "category": "2windows",
          "currentBuilds": [
          ],
          "pendingBuilds": 7,
          "slaves": [
            "build2-m1"
          ],
          "state": "idle"
        }
      }
    }

    def mock_fetch_build_json(_cache, _master_url,
                              _builder_name, _build_number):
      k_example_build_json = {
        "blame": [
          "alexhenrie24@gmail.com@0039d316-1c4b-4281-b951-d872f2087c98",
          "yoshiki@chromium.org@0039d316-1c4b-4281-b951-d872f2087c98"
        ],
        "builderName": "Win Builder",
        "currentStep": None,
        "eta": None,
        "number": 1771,
        "pendingBuilds": 7,
        "properties": [
          [
            "build_archive_url",
            ("gs://chromium-win-archive/chromium.win/"
              "Win Builder/full-build-win32_289623.zip"),
            "Annotation(package build)"
          ],
          [
            "buildbotURL",
            "http://build.chromium.org/p/chromium.win/",
            "master.cfg"
          ],
          [
            "buildername",
            "Win Builder",
            "Builder"
          ],
          [
            "buildnumber",
            1771,
            "Build"
          ],
          [
            "git_revision",
            "7ddb6d39574175cdd237eca54537e84fb960d3b8",
            "Change"
          ],
          [
            "got_nacl_revision_cp",
            "refs/heads/master@{#13611}",
            "Annotation(bot_update)"
          ],
          [
            "got_nacl_revision",
            "570e50beb76a2bdf6be4b345cbd47f225caf90af",
            "Annotation(bot_update)"
          ],
          [
            "got_revision_cp",
            "refs/heads/master@{#289623}",
            "Annotation(bot_update)"
          ],
          [
            "got_revision",
            "7ddb6d39574175cdd237eca54537e84fb960d3b8",
            "Annotation(bot_update)"
          ],
          [
            "got_swarming_client_revision",
            "bbf1fcca7932d92cca9d7dab46ea271a7f6d61fb",
            "Annotation(bot_update)"
          ],
          [
            "got_v8_revision_cp",
            "refs/heads/master@{#23117}",
            "Annotation(bot_update)"
          ],
          [
            "got_v8_revision",
            "f284b29e37d97d7ee9128055862179dcbda7e398",
            "Annotation(bot_update)"
          ],
          [
            "got_webkit_revision_cp",
            "refs/heads/master@{#180191}",
            "Annotation(bot_update)"
          ],
          [
            "got_webkit_revision",
            "9df9a9e66fed3921ec1f620f92ea7333a9c18122",
            "Annotation(bot_update)"
          ],
          [
            "got_webrtc_revision_cp",
            "refs/heads/master@{#6886}",
            "Annotation(bot_update)"
          ],
          [
            "got_webrtc_revision",
            "c2ef523233552340785557abce1129a0f61537eb",
            "Annotation(bot_update)"
          ],
          [
            "mastername",
            "chromium.win",
            "master.cfg"
          ]
        ],
        "steps": [
          {
            "eta": None,
            "expectations": [
              [
                "output",
                863225,
                748982.2582168579
              ]
            ],
            "hidden": False,
            "isFinished": True,
            "isStarted": True,
            "logs": [
              [
                "preamble",
                ("http://build.chromium.org/p/chromium.win/builders/"\
                "Win%20Builder/builds/1771/steps/steps/logs/preamble")
              ],
              [
                "stdio",
                ("http://build.chromium.org/p/chromium.win/builders/"\
                "Win%20Builder/builds/1771/steps/steps/logs/stdio")
              ]
            ],
            "name": "steps",
            "results": [
              0,
              []
            ],
            "step_number": 0,
            "text": [
              "running steps via annotated script"
            ],
            "times": [
              3.3,
              4.4
            ],
            "urls": {}
          },
          {
            "eta": None,
            "expectations": [],
            "hidden": False,
            "isFinished": True,
            "isStarted": True,
            "logs": [
              [
                "stdio",
                ("http://build.chromium.org/p/chromium.win/builders/"\
                "Win%20Builder/builds/1771/steps/setup_build/logs/stdio")
              ],
              [
                "run_recipe",
                ("http://build.chromium.org/p/chromium.win/builders/"\
                "Win%20Builder/builds/1771/steps/setup_build/logs/run_recipe")
              ]
            ],
            "name": "setup_build",
            "results": [
              0,
              []
            ],
            "step_number": 3,
            "text": [
              "setup_build",
              "<br/>running recipe: \"chromium\""
            ],
            "times": [
              5.5,
              6.6
            ],
            "urls": {}
          }
        ],
        "text": [
          "build",
          "successful"
        ],
        "times": [
          1.1,
          2.2
        ],
      }
      return k_example_build_json, 'chrome-build-extract'

    old_fetch_build_json = buildbot.fetch_build_json
    try:
      buildbot.fetch_build_json = mock_fetch_build_json

      builder_info = buildbot.latest_builder_info_and_alerts_for_master(
          self.cache,
          'http://build.chromium.org/p/chromium.webkit',
          k_example_master_json)[0]
      expected_builder_info = {
        'chromium.webkit': {
          'Win Builder': {
            'state': 'building',
            'monitor_url': 'https://chrome-monitor.appspot.com/view_graph' +
                '/chromium.webkit Win Builder Times (Last 100 Builds)',
            'build_source': 'chrome-build-extract',
            'lastUpdateTime': 2.2,
            'revisions': {
              'v8': 23117,
              'chromium': 289623,
              'nacl': 13611,
              'blink': 180191
            }
          }
        }
      }
      self.assertEqual(builder_info, expected_builder_info)
    finally:
      buildbot.fetch_build_json = old_fetch_build_json

  def test_create_stale_builder_alert_if_needed(self):
    master_url = "https://build.chromium.org/p/chromium.mac"
    current_time = int(time.time())
    step = "step name"
    latest_build_id = 1

    failing_build_time = current_time - (3.1 * 60 * 60)
    alert = buildbot.create_stale_builder_alert_if_needed(master_url,
        "Linux", "building", 50, failing_build_time, step, latest_build_id)
    self.assertIsNotNone(alert)

    passing_build_time = current_time - (60 * 60)
    alert = buildbot.create_stale_builder_alert_if_needed(master_url,
        "Linux", "building", 50, passing_build_time, step, latest_build_id)
    self.assertIsNone(alert)

    failing_offline_time = current_time - (1.6 * 60 * 60)
    alert = buildbot.create_stale_builder_alert_if_needed(master_url,
        "Linux", "offline", 50, failing_offline_time, step, latest_build_id)
    self.assertIsNotNone(alert)

    passing_offline_time = current_time - (0.3 * 60 * 60)
    alert = buildbot.create_stale_builder_alert_if_needed(master_url,
        "Linux", "offline", 50, passing_offline_time, step, latest_build_id)
    self.assertIsNone(alert)

    alert = buildbot.create_stale_builder_alert_if_needed(master_url,
        "Linux", "idle", 55, current_time, step, latest_build_id)
    self.assertIsNotNone(alert)

    alert = buildbot.create_stale_builder_alert_if_needed(master_url,
        "Linux", "idle", 2, current_time, step, latest_build_id)
    self.assertIsNone(alert)

  def test_latest_update_time_for_builder(self):
    k_example_last_build_times = {
      "times": [
        10,
        11
      ],
      "steps": [
        {
          "name": "earlier",
          "times": [
            20,
            21
          ]
        },
        {
          "name": "later",
          "times": [
            22,
            None
          ]
        }
      ]
    }

    # Test that we use end time when it's present,
    latest_time, step_name = buildbot.latest_update_time_and_step_for_builder(
        k_example_last_build_times)
    self.assertEqual(latest_time, 11)
    self.assertEqual(step_name, 'completed run')

    # And test that we iterate across step start times when it isn't.
    k_example_last_build_times["times"][1] = None
    latest_time, step_name = buildbot.latest_update_time_and_step_for_builder(
        k_example_last_build_times)
    self.assertEqual(latest_time, 22)
    self.assertEqual(step_name, 'later')

  def test_latest_update_time_for_builder_none_values(self):
    # Test that a step that hasn't started yet doesn't throw an error.
    k_example_last_build_times = {
      "times": [
        10,
        None
      ],
      "steps": [
        {
          "name": "later",
          "times": [
            20,
            21
          ]
        },
        {
          "name": "earlier",
          "times": [
            None,
            None
          ]
        }
      ]
    }

    latest_time, step_name = buildbot.latest_update_time_and_step_for_builder(
        k_example_last_build_times)
    self.assertEqual(latest_time, 21)
    self.assertEqual(step_name, 'later')


class BuildbotTest(unittest.TestCase):
  def test_master_name_from_url(self):
    tests = [
      ('https://build.chromium.org/p/chromium.mac', 'chromium.mac'),
      ('https://build.chromium.org/p/tryserver.blink', 'tryserver.blink')
    ]
    for master_url, master_name in tests:
      self.assertEquals(buildbot.master_name_from_url(master_url), master_name)

  def test_build_url(self):
    url = buildbot.build_url('https://foo.com/p/bar', 'baz', '12')
    self.assertEquals(url, 'https://foo.com/p/bar/builders/baz/builds/12')

  def test_cache_key_for_build(self):
    key = buildbot.cache_key_for_build('master', 'builder', 10)
    self.assertEquals(key, 'master/builder/10.json')

  def test_is_in_progress(self):
    self.assertEqual(buildbot.is_in_progress({'results': None}), True)
    self.assertEqual(buildbot.is_in_progress({'results': 2}), False)


class FetchBuildJsonTest(TestCaseWithDiskCache):
  # Note that the self.cache is rebuilt for every test case; no data sharing.

  def test_fetch_from_cache(self):
    # When a build is in the cache, we return that build from the cache.
    cache_key = buildbot.cache_key_for_build('foo', 'bar', 1)
    self.cache.set(cache_key, {'men': 'at work'})
    build, source = buildbot.fetch_build_json(self.cache, 'foo', 'bar', 1)
    self.assertEqual(build, {'men': 'at work'})
    self.assertEqual(source, 'disk cache')

  def test_ignore_expired_cache(self):
    # When a build is in the cache but expired, we hit the network instead.
    cache_key = buildbot.cache_key_for_build('foo', 'bar', 1)
    self.cache.set(cache_key, {'men': 'at work'})

    def _mock_key_age(cache_key):
      return datetime.datetime.now() - datetime.timedelta(seconds=121)
    _real_key_age = self.cache.key_age

    def _mock_fetch_and_cache_build(cache, url, cache_key):
      return {'I come': 'from a land down under'}
    _real_fetch_and_cache_build = buildbot.fetch_and_cache_build

    try:
      self.cache.key_age = _mock_key_age
      buildbot.fetch_and_cache_build = _mock_fetch_and_cache_build
      build, source = buildbot.fetch_build_json(self.cache, 'foo', 'bar', 1)
      self.assertEqual(build, {'I come': 'from a land down under'})
      self.assertEqual(source, 'chrome-build-extract')
    finally:
      self.cache.key_age = _real_key_age
      buildbot.fetch_and_cache_build = _real_fetch_and_cache_build

  def test_fetch_from_cbe(self):
    # If a build is available on chrome-build-extract, use that.
    def _mock_fetch_and_cache_build(cache, url, cache_key):
      if buildbot.CBE_BASE in url:  # pragma: no branch
        return {'I come': 'from a land down under'}
    _real_fetch_and_cache_build = buildbot.fetch_and_cache_build

    try:
      buildbot.fetch_and_cache_build = _mock_fetch_and_cache_build
      build, source = buildbot.fetch_build_json(self.cache, 'foo', 'bar', 1)
      self.assertEqual(build, {'I come': 'from a land down under'})
      self.assertEqual(source, 'chrome-build-extract')
    finally:
      buildbot.fetch_and_cache_build = _real_fetch_and_cache_build

  def test_fetch_from_master(self):
    # If both the cache and CBE fall through, go straight to the master.
    def _mock_fetch_and_cache_build(cache, url, cache_key):
      if buildbot.CBE_BASE in url:
        return None
      if 'build.chromium.org' in url:  # pragma: no branch
        return {'Can you hear': 'the thunder'}
    _real_fetch_and_cache_build = buildbot.fetch_and_cache_build

    try:
      buildbot.fetch_and_cache_build = _mock_fetch_and_cache_build
      build, source = buildbot.fetch_build_json(self.cache, 'foo', 'bar', 1)
      self.assertEqual(build, {'Can you hear': 'the thunder'})
      self.assertEqual(source, 'master')
    finally:
      buildbot.fetch_and_cache_build = _real_fetch_and_cache_build


class RevisionsForMasterTest(TestCaseWithDiskCache):
  def test_builder_info_for_master(self):
    """
    Tests latest_builder_info_and_alerts_for_master.

    We have to pre-fill the build json cache to avoid this test hitting the
    network, which accounts for much of the complexity here.
    """
    def cache_set(master_url, builder, build, value):
      key = buildbot.cache_key_for_build(master_url, builder, build)
      self.cache.set(key, value)
    def build(index):
      commit_position = 'refs/heads/master@{#%d}'
      return {
        'properties': [
          ['got_revision_cp', commit_position % (100 + index)],
          ['got_webkit_revision_cp', commit_position % (200 + index)],
          ['got_v8_revision_cp', commit_position % (300 + index)],
          ['got_nacl_revision_cp', commit_position % (400 + index)]
        ],
        'times': [1.0, 2.0],
        'index': index
      }
    builds = map(build, range(0, 10))
    master0_url = 'http://foo/bar/master0'
    master0 = {
      'builders': {
        'builder0': {
          'cachedBuilds': [0, 1],
          'currentBuilds': [2],
          'state': 'happy',
          "pendingBuilds": 1,
        },
        'builder1': {
          'cachedBuilds': [2, 3, 4, 5, 7],
          'currentBuilds': [4, 5, 6, 7],
          'state': 'sad',
          "pendingBuilds": 1,
        }
      }
    }
    # set up the cache so we don't hit the network
    for b in builds:
      cache_set(master0_url, 'builder0', b['index'], b)
      cache_set(master0_url, 'builder1', b['index'], b)
    latest = buildbot.latest_builder_info_and_alerts_for_master(
        self.cache, master0_url, master0)[0]
    self.assertIn('master0', latest)
    self.assertIn('builder0', latest['master0'])
    self.assertIn('builder1', latest['master0'])
    # b0's latest build is 1
    b0 = latest['master0']['builder0']['revisions']
    self.assertEqual(b0['chromium'], 102)
    self.assertEqual(b0['blink'], 202)
    self.assertEqual(b0['v8'], 302)
    self.assertEqual(b0['nacl'], 402)
    # b1's latest build is 7
    b1 = latest['master0']['builder1']['revisions']
    self.assertEqual(b1['chromium'], 107)
    self.assertEqual(b1['blink'], 207)
    self.assertEqual(b1['v8'], 307)
    self.assertEqual(b1['nacl'], 407)

  def test_builder_info_for_master_no_build(self):
    """Test that we don't crash when the buildbot/CBE both don't have a build
    for a given build ID.
    """
    master0_url = 'http://foo/bar/master0'
    master0 = {
      'builders': {
        'builder0': {
          'cachedBuilds': [0],
          'currentBuilds': [],
          'state': 'happy',
          "pendingBuilds": 1,
        }
      }
    }

    def fetch(_cache, _master_url, _builder_name, _latest_build_id):
      return None, None

    old_fetch = buildbot.fetch_build_json

    try:
      buildbot.fetch_build_json = fetch
      latest = buildbot.latest_builder_info_and_alerts_for_master(
          self.cache, master0_url, master0)[0]
      self.assertEqual(latest, {})
    finally:
      buildbot.fetch_build_json = old_fetch

  # This is a silly test to get 100% code coverage. This
  # never actually happens.
  def test_revisions_from_build_no_properties(self):
    build = {'properties': []}
    self.assertEqual(buildbot.revisions_from_build(build), {
      'v8': None,
      'chromium': None,
      'nacl': None,
      'blink': None,
    })
