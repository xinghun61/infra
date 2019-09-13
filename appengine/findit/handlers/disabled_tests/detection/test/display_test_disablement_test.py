# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import mock
import webapp2

from handlers.disabled_tests.detection import display_test_disablement
from libs import time_util
from model.test_inventory import LuciTest
from waterfall.test.wf_testcase import WaterfallTestCase


class DisplayTestDisablementTest(WaterfallTestCase):
  app_module = webapp2.WSGIApplication([
      ('/p/chromium/disabled-tests',
       display_test_disablement.DisplayTestDisablement),
  ],
                                       debug=True)

  def setUp(self):
    super(DisplayTestDisablementTest, self).setUp()
    self.disabled_test1 = LuciTest(
        key=LuciTest.CreateKey('a', 'b', 'd'),
        disabled_test_variants={('os:Mac1234',)},
        last_updated_time=datetime.datetime(2019, 6, 29, 0, 0, 0))
    self.disabled_test1.put()
    self.disabled_test1_dict = self.disabled_test1.to_dict()
    self.disabled_test1_dict['disabled_test_variants'] = [
        [
            'os:Mac',
        ],
    ]

    self.disabled_test2 = LuciTest(
        key=LuciTest.CreateKey('a', 'b', 'c'),
        disabled_test_variants={('os:Mac1234',)},
        last_updated_time=datetime.datetime(2019, 6, 29, 0, 0, 0))
    self.disabled_test2.put()
    self.disabled_test2_dict = self.disabled_test2.to_dict()
    self.disabled_test2_dict['disabled_test_variants'] = [
        [
            'os:Mac',
        ],
    ]

    self.disabled_test3 = LuciTest(
        key=LuciTest.CreateKey('a', 'b', 'e'),
        disabled_test_variants=set(),
        last_updated_time=datetime.datetime(2019, 6, 29, 0, 0, 0))
    self.disabled_test3.put()

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime.datetime(2018, 10, 2, 1))
  def testDisplayTestDisablement(self, _):
    response = self.test_app.get(
        '/p/chromium/disabled-tests', params={
            'format': 'json',
        }, status=200)
    self.assertEqual(
        json.dumps({
            'disabled_tests_data': [
                self.disabled_test2_dict,
                self.disabled_test1_dict,
            ],
            'prev_cursor':
                '',
            'cursor':
                '',
            'page_size':
                '',
            'error_message':
                None,
        },
                   default=str), response.body)
