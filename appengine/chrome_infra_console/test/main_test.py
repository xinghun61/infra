# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from main import ConsoleAppApi
from main import UIApi
from main import Project
from components import auth
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
    request = {'timeseries': [{'points': points,
               'fields': fields,
               'metric': 'disk_used'}]}
    self.mock(auth, 'is_group_member', lambda _: True)
    response = self.call_api('timeseries_update', request).json_body
    self.assertEquals(response, {})
    # Calling the function a second time in order to test that the console
    # updates existing data in the datastore.
    self.call_api('timeseries_update', request)

class UIApiTest(testing.EndpointsTestCase):

  api_service_cls = UIApi
  @mock.patch('components.config.get_projects')
  def testGetProjects(self, get_projects): 
    projects = [Project(repo_type="uu", 
                        id="infra", 
                        repo_url="a.com", 
                        name="infra"),
                Project(repo_type="uu", 
                        id="chromium", 
                        repo_url="a.com", 
                        name="chromium")] 
    get_projects.return_value = projects
    response = self.call_api('get_projects').json_body
    self.assertEquals(len(response['projects']), 2)
