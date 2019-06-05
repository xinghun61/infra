# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""Tests for MonorailTSMonJSHandler."""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import json
import unittest
from mock import patch

import webapp2
from google.appengine.ext import testbed

from framework.ts_mon_js import MonorailTSMonJSHandler
from services import service_manager


class MonorailTSMonJSHandlerTest(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_user_stub()

  def tearDown(self):
    self.testbed.deactivate()

  @patch('framework.xsrf.ValidateToken')
  @patch('time.time')
  def testSubmitMetrics(self, _mockTime, _mockValidateToken):
    """Test normal case POSTing metrics."""
    _mockTime.return_value = 1537821859
    req = webapp2.Request.blank('/_/ts_mon_js')
    req.body = json.dumps({
      'metrics': [{
        'MetricInfo': {
          'Name': 'monorail/frontend/issue_update_latency',
          'ValueType': 2,
        },
        'Cells': [{
          'value': {
            'sum': 1234,
            'count': 4321,
            'buckets': {
              0: 123,
              1: 321,
              2: 213,
            },
          },
          'fields': {
            'client_id': '789',
            'host_name': 'rutabaga',
            'document_visible': True,
          },
          'start_time': 1537821859 - 60,
        }],
      }],
    })
    res = webapp2.Response()
    ts_mon_handler = MonorailTSMonJSHandler(request=req, response=res)
    class MockApp(object):
      def __init__(self):
        self.config = {'services': service_manager.Services()}
    ts_mon_handler.app = MockApp()

    ts_mon_handler.post()

    self.assertEqual(res.status_int, 201)
    self.assertEqual(res.body, 'Ok.')
