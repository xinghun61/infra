# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import json
import os
import sys
import unittest

from mock import Mock
from mock import patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

with patch('gae_ts_mon.initialize', Mock()):
  from pylib import cloud_server

from pylib.third_party import cloudstorage
from pylib.ui_catalogue import ScreenshotLoader


TEST_DATA = [
  {
    u'filters': {
      u'Screenshot Name': u'screenshot1',
      u'f1': u'f1_a',
      u'f2': u'f2_a'
    },
    u'tags': [],
    u'metadata': {
      u'm1': u'm1_a'
    },
    u'image_link': u'https://junk',
    u'location': u'NotAFile'
  },
  {
    u'filters': {
      u'Screenshot Name': u'screenshot2',
      u'f1': u'f1_a',
      u'f2': u'f2_b',
      u'f3': u'f3_a'
    },
    u'tags': [u't1'],
    u'metadata': {
      u'm1': u'm1_a'
    },
    u'image_link': u'file://rubbish',
    u'location': u'Dummy'
  }]


class DummyReader(object):
  """Test class to provide data that would be provided by cloud storage."""

  def __enter__(self):
    """Minimal __enter_ member to allow use in 'with' statements."""
    return self

  def __exit__(self, exc_type, exc_val, exc_tb):
    """Minimal __exit_ member to allow use in 'with' statements."""
    pass

  def read(self):
    return json.dumps(TEST_DATA)


def cloudstorage_open(name):
  """Fake open function, return dummy data or generate error, based on name."""

  if name != '/chromium-result-details/good':
    raise cloudstorage.Error
  reader = DummyReader()
  return reader


@patch.object(cloudstorage, 'open', cloudstorage_open)
class RemoteScreenshotLoaderTest(unittest.TestCase):
  """Tests for RemoteScreenshotLoaderClass."""

  def test_good(self):
    loader = cloud_server.RemoteScreenshotLoader()
    expected_data = copy.deepcopy(TEST_DATA)
    expected_data[0][u'location'] = (
        u'https://storage.cloud.google.com/chromium-result-details/NotAFile')
    expected_data[1][u'location'] = (
        u'https://storage.cloud.google.com/chromium-result-details/Dummy')
    self.assertEqual(
        expected_data,
        loader.get_data(
            'https://storage.cloud.google.com/chromium-result-details/good'))

  def test_bad_location(self):
    loader = cloud_server.RemoteScreenshotLoader()
    self.assertRaises(
        ScreenshotLoader.ScreenshotLoaderException,
        loader.get_data,
        'https://storage.cloud.google.com/chromium-result-details/bad')


class StartupTest(unittest.TestCase):
  """Test for server startup."""

  def test_startup(self):
    app = cloud_server.gae_app
    self.assertIsNotNone(app)
    screenshot_loader = app.config['screenshot_loader']
    self.assertIsInstance(screenshot_loader,
                          cloud_server.RemoteScreenshotLoader)
    # There seems to be no documented way of testing that the route list
    # is correct. cloud_server_test.py already checks that all the expected
    # routes exist.
