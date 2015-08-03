# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import logging

from components import auth
from components import config
from google.appengine.api import namespace_manager
from google.appengine.ext import ndb
from testing_utils import testing

import main
import mock

class ConsoleAppApiTest(testing.EndpointsTestCase):

  api_service_cls = main.ConsoleAppApi

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

  api_service_cls = main.UIApi

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

  def testGetGraphs(self):
    self.mock(config, 'get_project_config', mock.Mock())
    self.mock(auth, 'get_current_identity', mock.Mock())
    self.mock(auth, 'is_group_member', mock.Mock(return_value=False))

    cfg = ("888", mock.Mock(access=['group:all','a@a.com','user:b@a.com']))
    config.get_project_config.return_value = cfg

    auth.get_current_identity.return_value = auth.Identity('user', 'a@a.com')
    
    namespace_manager.set_namespace('projects.infra')
    points = [main.PointModel(time = 1.0,
               value= 10.0)]
    fields = [main.FieldModel(field_key='project_id', value='infra')]
    ts = main.TimeSeriesModel(
            points=points, fields=fields, metric='disk_used')

    ts.put()
  
    response = self.call_api('get_graphs', {"project_id":'infra'}).json_body
    self.assertEquals(len(response['timeseries']), 1)

    # User doesn't have access to the project.
    auth.get_current_identity.return_value = auth.Identity('user', 'b@b.com')
    response = self.call_api('get_graphs', {"project_id":'infra'}).json_body
    self.assertEquals(len(response.keys()), 0)

    auth.is_group_member.return_value = True
    response = self.call_api('get_graphs', {"project_id":'infra'}).json_body
    self.assertEquals(len(response['timeseries']), 1)

    auth.is_group_member.return_value = True
    response = self.call_api('get_graphs', {"project_id":'v8'}).json_body
    self.assertEquals(len(response.keys()), 0)
    
    # Project does not exist.
    auth.is_group_member.return_value = True
    config.get_project_config.return_value = (None, None)
    response = self.call_api('get_graphs', {"project_id":'123'}).json_body
    self.assertEquals(len(response.keys()), 0)
    
