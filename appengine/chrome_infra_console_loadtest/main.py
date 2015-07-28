# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

import endpoints
import random
import webapp2
from apiclient import discovery
from google.appengine.ext import ndb
from oauth2client.client import GoogleCredentials
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from components import auth

CONFIG_DATASTORE_KEY = "CONFIG_DATASTORE_KEY"
API_URL = 'https://chrome-infra-console-loadtest.appspot.com'
API_NAME = 'consoleapp'
API_VERSION = 'v1'
DISCOVERY_URL = '%s/_ah/api/discovery/v1/apis/{api}/{apiVersion}/rest'


class FieldParamsModel(ndb.Model):
  field_key = ndb.StringProperty()
  values = ndb.StringProperty(repeated=True)


class MetricModel(ndb.Model):
  name = ndb.StringProperty(default="")
  minimum = ndb.FloatProperty(default=0)
  maximum = ndb.FloatProperty(default=100)


class ParamsModel(ndb.Model):
  time = ndb.FloatProperty(default=10)
  freq = ndb.FloatProperty(default=1)
  params = ndb.LocalStructuredProperty(FieldParamsModel, repeated=True)
  metrics = ndb.LocalStructuredProperty(MetricModel, repeated=True)


class Field(messages.Message):
  key = messages.StringField(1)
  value = messages.StringField(2)


class Point(messages.Message):
  time = messages.FloatField(1)
  value = messages.FloatField(2)


class FieldParams(messages.Message):
  field_key = messages.StringField(1)
  values = messages.StringField(2, repeated=True)


class Metric(messages.Message):
  name = messages.StringField(1)
  minimum = messages.FloatField(2)
  maximum = messages.FloatField(3)


class Params(messages.Message):
  time = messages.FloatField(1)
  freq = messages.FloatField(2)
  params = messages.MessageField(FieldParams, 3, repeated=True)
  metrics = messages.MessageField(Metric, 4, repeated=True)


class TimeSeries(messages.Message):
  points = messages.MessageField(Point, 1, repeated=True)
  fields = messages.MessageField(Field, 2, repeated=True)
  metric = messages.StringField(3)


class DataPacket(messages.Message):
  timeseries = messages.MessageField(TimeSeries, 1, repeated=True)


@auth.endpoints_api(name='consoleapp', version='v1')
class LoadTestApi(remote.Service):
  """A testing endpoint that receives timeseries data."""

  @auth.endpoints_method(DataPacket, message_types.VoidMessage,
                         name='timeseries.update')
  @auth.require(lambda: auth.is_group_member('metric-generators'))
  def timeseries_update(self, request):
    logging.debug('Datapacket length is %d', len(request.timeseries))
    return message_types.VoidMessage()


@auth.endpoints_api(name='ui', version='v1')
class UIApi(remote.Service):
  """API for the loadtest configuration UI."""

  @auth.endpoints_method(message_types.VoidMessage, Params,
                         name='ui.get')
  @auth.require(lambda: auth.is_group_member('metric-generators'))
  def UI_get(self, _request):
    data = ParamsModel.get_or_insert(CONFIG_DATASTORE_KEY)
    params = [FieldParams(field_key=field.field_key, values=field.values)
              for field in data.params]
    metrics = [Metric(name=metric.name, 
                      minimum=metric.minimum, 
                      maximum=metric.maximum)
              for metric in data.metrics]
    return Params(time=data.time, freq=data.freq,
                  params=params, metrics=metrics)

  @auth.endpoints_method(Params, message_types.VoidMessage,
                         name='ui.set')
  @auth.require(lambda: auth.is_group_member('metric-generators'))
  def UI_set(self, request):
    logging.debug('Got %s', request)
    data = ParamsModel.get_or_insert(CONFIG_DATASTORE_KEY)
    data.time = request.time
    data.freq = request.freq
    data.params = [FieldParamsModel(field_key=field.field_key, 
                                    values=field.values)
                   for field in request.params]
    data.metrics = [MetricModel(name=metric.name, 
                                 minimum=metric.minimum,
                                 maximum=metric.maximum)
                   for metric in request.metrics]
    data.put()
    return message_types.VoidMessage()


def field_generator(dataparams, index, fields):
  if index == len(dataparams):
    return [fields]
  else:
    key = dataparams[index].field_key
    return sum((field_generator(
      dataparams, index+1, fields+[{'key': key, 'value': value}])
                for value in dataparams[index].values), [])


class CronHandler(webapp2.RequestHandler):

  def get(self):
    data = ParamsModel.get_or_insert(CONFIG_DATASTORE_KEY)
    metric_ranges = {}
    for metric in data.metrics:
      metric_ranges[metric.name] = (metric.minimum,metric.maximum)
    datapacket = {'timeseries': []}
    logging.debug('There are %d metrics', len(metric_ranges))
    fieldlist = field_generator(data.params, 0, [])
    for metric in metric_ranges:
      for fields in fieldlist:
        points = []
        for x in xrange(0, int(data.time), int(data.freq)):
          points.append({'time': x,
                         'value': random.uniform(*metric_ranges[metric])})
        timeseries = {'points': points,
                      'fields': fields,
                      'metric': metric}
        datapacket['timeseries'].append(timeseries)
    logging.info('Cron task executed.')
    discovery_url = DISCOVERY_URL % API_URL
    credentials = GoogleCredentials.get_application_default()
    service = discovery.build(API_NAME, API_VERSION,
                              discoveryServiceUrl=discovery_url, 
                              credentials=credentials)
    _response = service.timeseries().update(body=datapacket).execute()


backend_handlers = [
  ('/cron', CronHandler)
]

WEBAPP = webapp2.WSGIApplication(backend_handlers, debug=True)

APPLICATION = endpoints.api_server([LoadTestApi, UIApi])
