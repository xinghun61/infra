# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import shutil
import tempfile
import unittest

from infra.tools.builder_alerts import buildbot


class BuildCacheTest(unittest.TestCase):
  def setUp(self):
    self.cache_path = tempfile.mkdtemp()

  def tearDown(self):
    shutil.rmtree(self.cache_path, ignore_errors=True)

  def test_build_cache(self):
    cache = buildbot.BuildCache(self.cache_path)

    test_key = 'foo/bar'
    self.assertFalse(cache.has(test_key))

    test_data = ['test']
    cache.set(test_key, test_data)
    # Set it a second time to hit the "already there" case.
    cache.set(test_key, test_data)

    self.assertTrue(cache.has(test_key))
    self.assertEquals(cache.get(test_key), test_data)

    self.assertIsNone(cache.get('does_not_exist'))
    self.assertIsNotNone(cache.key_age(test_key))

  def test_latest_builder_info_for_master(self):
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
        }
      }
    }

    def mock_fetch_build_json(cache, master_url, builder_name, build_number):
      k_example_build_json = {
        "blame": [
          "alexhenrie24@gmail.com@0039d316-1c4b-4281-b951-d872f2087c98",
          "yoshiki@chromium.org@0039d316-1c4b-4281-b951-d872f2087c98"
        ],
        "builderName": "Win Builder",
        "currentStep": None,
        "eta": None,
        "number": 1771,
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
            "got_nacl_revision",
            13611,
            "Annotation(bot_update)"
          ],
          [
            "got_nacl_revision_git",
            "570e50beb76a2bdf6be4b345cbd47f225caf90af",
            "Annotation(bot_update)"
          ],
          [
            "got_revision",
            289623,
            "Annotation(bot_update)"
          ],
          [
            "got_revision_git",
            "7ddb6d39574175cdd237eca54537e84fb960d3b8",
            "Annotation(bot_update)"
          ],
          [
            "got_swarming_client_revision",
            "bbf1fcca7932d92cca9d7dab46ea271a7f6d61fb",
            "Annotation(bot_update)"
          ],
          [
            "got_v8_revision",
            23117,
            "Annotation(bot_update)"
          ],
          [
            "got_v8_revision_git",
            "f284b29e37d97d7ee9128055862179dcbda7e398",
            "Annotation(bot_update)"
          ],
          [
            "got_webkit_revision",
            180191,
            "Annotation(bot_update)"
          ],
          [
            "got_webkit_revision_git",
            "9df9a9e66fed3921ec1f620f92ea7333a9c18122",
            "Annotation(bot_update)"
          ],
          [
            "got_webrtc_revision",
            6886,
            "Annotation(bot_update)"
          ],
          [
            "got_webrtc_revision_git",
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
      return k_example_build_json

    cache = buildbot.BuildCache(self.cache_path)
    old_fetch_build_json = buildbot.fetch_build_json
    try:
      buildbot.fetch_build_json = mock_fetch_build_json

      builder_info = buildbot.latest_builder_info_for_master(cache,
          'http://build.chromium.org/p/chromium.webkit', k_example_master_json)
      expected_builder_info = {
        'chromium.webkit': {
          'Win Builder': {
            'state': 'building',
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

  def test_latest_update_time_for_builder(self):
    k_example_last_build_times = {
      "times": [
        10,
        11
      ],
      "steps": [
        {
          "times": [
            20,
            21
          ]
        },
        {
          "times": [
            22
          ]
        }
      ]
    }

    # Test that we use end time when it's present,
    time = buildbot.latest_update_time_for_builder(k_example_last_build_times)
    self.assertEqual(time, 11)

    # And test that we iterate across step start times when it isn't.
    k_example_last_build_times["times"][1] = None
    time = buildbot.latest_update_time_for_builder(k_example_last_build_times)
    self.assertEqual(time, 22)


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
