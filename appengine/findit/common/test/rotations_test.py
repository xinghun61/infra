# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import mock

from testing_utils import testing
from libs.http import retry_http_client

from common import rotations


class DummyHttpClient(retry_http_client.RetryHttpClient):

  def __init__(self, *args, **kwargs):
    super(DummyHttpClient, self).__init__(*args, **kwargs)
    self.responses = {}
    self.requests = []

  def SetResponse(self, url, result):
    self.responses[url] = result

  def GetBackoff(self, *_):  # pragma: no cover
    """Override to avoid sleep."""
    return 0

  def _Get(self, url, _, headers):
    self.requests.append((url, None, headers))
    return self.responses.get(url, (404, 'Not Found'))

  def _Post(self, *_):  # pragma: no cover
    pass

  def _Put(self, *_):  # pragma: no cover
    pass


class RotationsTest(testing.AppengineTestCase):

  def setUp(self):
    super(RotationsTest, self).setUp()
    self.http_client = DummyHttpClient()
    self.http_patcher = mock.patch(
        'common.rotations.HTTP_CLIENT', self.http_client)
    self.date_patcher = mock.patch(
        'libs.time_util.GetPSTNow', lambda: datetime.datetime(2017, 1, 1))
    self.http_patcher.start()
    self.date_patcher.start()

  def tearDown(self):
    self.http_patcher.stop()
    self.date_patcher.stop()

  def testCurrentSheriffs(self):
    response = json.dumps({
        'calendar': [
            {'date': '2016-12-31', 'participants': [[], ['foo', 'bar']]},
            {'date': '2017-01-01', 'participants': [['ham', 'eggs'], []]},
        ],
        'rotations': ['dummy1', 'dummy2']
    })
    self.http_client.SetResponse(rotations.ROTATIONS_URL, (200, response))
    self.assertIn('ham@google.com', rotations.current_sheriffs('dummy1'))

  def testCurrentSheriffsMissingSheriff(self):
    response = json.dumps({
        'calendar': [
            {'date': '2016-12-31', 'participants': [[], ['foo', 'bar']]},
            {'date': '2017-01-01', 'participants': [['ham', 'eggs'], []]},
        ],
        'rotations': ['dummy1', 'dummy2']
    })
    self.http_client.SetResponse(rotations.ROTATIONS_URL, (200, response))
    self.assertFalse(rotations.current_sheriffs('dummy2'))

  def testCurrentSheriffsBadRotationName(self):
    response = json.dumps({
        'calendar': [
            {'date': '2016-12-31', 'participants': [[], ['foo', 'bar']]},
            {'date': '2017-01-01', 'participants': [['ham', 'eggs'], []]},
        ],
        'rotations': ['dummy1', 'dummy2']
    })
    self.http_client.SetResponse(rotations.ROTATIONS_URL, (200, response))
    self.assertFalse(rotations.current_sheriffs('memegen-rotation'))

  def testCurrentSheriffsMissingDate(self):
    response = json.dumps({
        'calendar': [
            {'date': '2016-12-31', 'participants': [[], ['foo', 'bar']]},
        ],
        'rotations': ['dummy1', 'dummy2']
    })
    self.http_client.SetResponse(rotations.ROTATIONS_URL, (200, response))
    with self.assertRaises(Exception):
      rotations.current_sheriffs('dummy2')

  def testCurrentSheriffsBadHttp(self):
    self.http_client.SetResponse(rotations.ROTATIONS_URL, (403, 'forbidden'))
    with self.assertRaises(Exception):
      rotations.current_sheriffs('dummy2')
