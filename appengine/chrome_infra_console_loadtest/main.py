# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

import endpoints
import webapp2

from components import auth
from protorpc import messages
from protorpc import message_types
from protorpc import remote


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
                         name='UI.get')
  @auth.require(lambda: auth.is_group_member('metric-generators'))
  def UI_get(self, _request):
    param_response = Params(time=0.0, freq=10.0, params=[
        FieldParams(key='project_id', values=['chromium', 'blink'])])
    return param_response

  @auth.endpoints_method(Params, message_types.VoidMessage,
                         name='UI.set')
  @auth.require(lambda: auth.is_group_member('metric-generators'))
  def UI_set(self, request):
    logging.debug('Got %s', request)
    return message_types.VoidMessage()


APPLICATION = endpoints.api_server([LoadTestApi, UIApi])
