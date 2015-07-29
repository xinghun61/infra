# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from main import ConsoleAppApi
from main import UIApi
from main import Config
from components import auth
from components import config
from google.appengine.ext import ndb
from testing_utils import testing
import main
import mock


class ConsoleAppApiTest(testing.EndpointsTestCase):

  api_service_cls = ConsoleAppApi

  def testTimeseriesUpdate(self):
    # TODO(norulez): Verify timeseries is correctly overwritten when UI 
    # endpoints are implemented.
    points = [{'time': 1.0,
               'value': 10.0}]
    fields = [{'key': 'project_id',
               'value': 'chromium'}]
    request = {'timeseries': [
        {'points': points,
         'fields': fields,
         'metric': 'disk_used'}]}
    self.mock(auth, 'is_group_member', lambda _: True)
    response = self.call_api('timeseries_update', request).json_body
    self.assertEquals(response, {})
    # Calling the function a second time in order to test that the console
    # updates existing data in the datastore.
    self.call_api('timeseries_update', request)
    # Calling the function with an empty fields list tests for anonymous graphs.
    request = {'timeseries': [
        {'points': [],
         'fields': [],
         'metric': ''}]}
    self.call_api('timeseries_update', request)


class UIApiTest(testing.EndpointsTestCase):

  api_service_cls = UIApi

  def testGetProjects(self): 
    self.mock(config, 'get_project_configs', mock.Mock())
    self.mock(auth, 'get_current_identity', mock.Mock())
    self.mock(auth, 'is_group_member', mock.Mock(return_value=False))
    auth.get_current_identity.return_value = auth.Identity('user', 'a@a.com')
    configs = {
        "infra": ("888", mock.Mock(
            access=['group:all','a@a.com','user:b@a.com'])), 
        "v8": ("888666", mock.Mock(access=['group:all','a@a.com']))
    }
    config.get_project_configs.return_value = configs
    response = self.call_api('get_projects').json_body
    self.assertEquals(len(response['configs']), 2)

    auth.get_current_identity.return_value = auth.Identity('user', 'b@b.com')
    response = self.call_api('get_projects').json_body
    self.assertEquals(len(response.keys()), 0)


    auth.is_group_member.side_effect = lambda name: name == 'all'
    response = self.call_api('get_projects').json_body
    self.assertEquals(len(response['configs']), 2)
