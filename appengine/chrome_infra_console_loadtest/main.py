# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

import endpoints
import webapp2
from google.appengine.ext import ndb
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from components import auth

CONFIG_DATASTORE_KEY = "CONFIG_DATASTORE_KEY"


class FieldParamsModel(ndb.Model):
  field_key = ndb.StringProperty()
  values = ndb.StringProperty(repeated=True)


class ParamsModel(ndb.Model):
  time = ndb.FloatProperty(default=10)
  freq = ndb.FloatProperty(default=1)
  params = ndb.LocalStructuredProperty(FieldParamsModel, repeated=True)


class Field(messages.Message):
  key = messages.StringField(1)
  value = messages.StringField(2)


class Point(messages.Message):
  time = messages.FloatField(1)
  value = messages.FloatField(2)


class FieldParams(messages.Message):
  key = messages.StringField(1)
  values = messages.StringField(2, repeated = True)


class Params(messages.Message):
  time = messages.FloatField(1)
  freq = messages.FloatField(2)
  params = messages.MessageField(FieldParams, 3, repeated = True)


class TimeSeries(messages.Message):
  points = messages.MessageField(Point, 1, repeated = True)
  fields = messages.MessageField(Field, 2, repeated = True)
  metric = messages.StringField(3)


class DataPacket(messages.Message):
  timeseries = messages.MessageField(TimeSeries, 1, repeated = True)


@auth.endpoints_api(name='loadtestapp', version='v1')
class LoadTestApi(remote.Service):
  """A testing endpoint that receives timeseries data."""

  @auth.endpoints_method(DataPacket, message_types.VoidMessage,
                         name='loadtest.timeseries')
  @auth.require(lambda: auth.is_group_member('metric-generators'))
  def loadtest_timeseries(self, _request):
    return message_types.VoidMessage()


@auth.endpoints_api(name='ui', version='v1')
class UIApi(remote.Service):
  """API for the loadtest configuration UI."""

  @auth.endpoints_method(message_types.VoidMessage, Params,
                         name='ui.get')
  @auth.require(lambda: auth.is_group_member('metric-generators'))
  def UI_get(self, _request):
    data = ParamsModel.get_or_insert(CONFIG_DATASTORE_KEY)
    params = [FieldParams(key=field.field_key, values=field.values)
              for field in data.params]
    return Params(time=data.time, freq=data.freq, params=params)

  @auth.endpoints_method(Params, message_types.VoidMessage,
                         name='ui.set')
  @auth.require(lambda: auth.is_group_member('metric-generators'))
  def UI_set(self, request):
    logging.debug('Got %s', request)
    data = ParamsModel.get_or_insert(CONFIG_DATASTORE_KEY)
    data.time = request.time
    data.freq = request.freq
    data.params = [FieldParamsModel(field_key=field.key, values=field.values)
                   for field in request.params]
    data.put()
    return message_types.VoidMessage()


APPLICATION = endpoints.api_server([LoadTestApi, UIApi])
