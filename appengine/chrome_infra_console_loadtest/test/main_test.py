# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from components import auth
import logging

from main import LoadTestApi
from main import UIApi
from main import ParamsModel
from main import FieldParamsModel
from main import MetricModel
from protorpc import messages
from protorpc import message_types
from oauth2client.client import GoogleCredentials
from testing_utils import testing
import main
import mock
import webapp2
import webtest

class LoadTestApiTest(testing.EndpointsTestCase):

  api_service_cls = LoadTestApi

  def testTimeseriesUpdate(self):
    point = {'time': 0.0,
             'value': 10.0}
    field = {'key': 'project_id',
             'value': 'chromium'}
    request = {'timeseries': [{'points': [point],
               'field': field,
               'metric': 'disk_used'}]}
    self.mock(auth, 'is_group_member', lambda _: True)
    response = self.call_api('timeseries_update', request).json_body
    self.assertEquals(response, {})


class UIApiTest(testing.EndpointsTestCase):

  api_service_cls = UIApi

  def testUIStoreAndRetrieve(self):
    field = {'field_key': 'project_id',
             'values': ['chromium', 'blink', 'v8']}
    metric = {'name': 'a','minimum': 0, 'maximum': 100}
    request = {'time': 10,
               'freq': 1,
               'params': [field],
               'metrics': [metric]}
    self.mock(auth, 'is_group_member', lambda _: True)
    self.call_api('UI_set', request)
    response = self.call_api('UI_get', {}).json_body
    self.assertEquals(response, request)


class CronTest(testing.AppengineTestCase):
  
  @property
  def app_module(self):
    return main.WEBAPP

  @mock.patch('apiclient.discovery.build')
  def test_get(self, build):
    data = ParamsModel.get_or_insert(main.CONFIG_DATASTORE_KEY)
    data.time = 100
    data.freq = 5
    data.params = [FieldParamsModel(field_key='project_id', 
                                    values=['chromium', 'blink'])]
    data.metrics =[MetricModel(name='a', minimum=0, maximum=10)]
    data.put()
    self.test_app.get('/cron')
    build.assert_called_with(
        main.API_NAME, main.API_VERSION,
        discoveryServiceUrl=main.DISCOVERY_URL % main.API_URL,
        credentials=Anything())
    service = build.return_value
    service.timeseries.assert_called_with()
    service.timeseries.return_value.update.assert_called_with(body=Anything())
    request = service.timeseries.return_value.update.return_value
    request.execute.assert_called_with()

  def test_field_generator(self):
    test_dataparams = [FieldParamsModel(field_key='project_id', 
                                        values=['chromium', 'blink']), 
                       FieldParamsModel(field_key='service', values=['blah']),
                       FieldParamsModel(field_key='field_key', values=['Hi'])]
    response = main.field_generator(test_dataparams, 0, [])
    self.assertEquals(response, [[{'key': 'project_id', 'value': 'chromium'},
                                  {'key': 'service', 'value': 'blah'},
                                  {'key': 'field_key', 'value': 'Hi'}],
                                 [{'key': 'project_id', 'value': 'blink'},
                                  {'key': 'service', 'value': 'blah'},
                                  {'key': 'field_key', 'value': 'Hi'}]])
    test_dataparams = [FieldParamsModel(field_key='', values=[''])]
    response = main.field_generator(test_dataparams, 0, [])
    self.assertEquals(response, [[{'key': '', 'value': ''}]])
    test_dataparams = [FieldParamsModel(field_key='', values=[])]
    response = main.field_generator(test_dataparams, 0, [])
    self.assertEquals(response, [])


class Anything(object):
  def __eq__(self, other):
    return True
