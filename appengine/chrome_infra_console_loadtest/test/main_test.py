# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from components import auth

from main import LoadTestApi
from main import UIApi
from protorpc import messages
from protorpc import message_types
from testing_utils import testing


class LoadTestApiTest(testing.EndpointsTestCase):

  api_service_cls = LoadTestApi

  def testLoadTestSet(self):
    point = {'time': 0.0, 
             'value': 10.0}
    field = {'key': 'project_id',
             'value': 'chromium'}
    request = {'timeseries': [{'points': [point],
               'fields': [field],
               'metric': 'disk_used'}]}
    self.mock(auth, 'is_group_member', lambda _: True)
    response = self.call_api('loadtest_timeseries', request).json_body
    self.assertEquals(response, {})


class UIApiTest(testing.EndpointsTestCase):

  api_service_cls = UIApi

  def testUIGet(self):
    request = {}
    self.mock(auth, 'is_group_member', lambda _: True)
    response = self.call_api('UI_get', request).json_body
    self.assertEquals(response['time'], 0.0)

  def testUISet(self):
    field = {'key': 'project_id',
             'values': ['chromium', 'blink', 'v8']}
    request = {'time': 5.0,
               'freq': 3.0,
               'params': [field]}
    self.mock(auth, 'is_group_member', lambda _: True)
    response = self.call_api('UI_set', request).json_body
    self.assertEquals(response, {})
