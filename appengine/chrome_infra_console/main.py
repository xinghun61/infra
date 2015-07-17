# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import endpoints
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from components import auth

class Field(messages.Message):
  key = messages.StringField(1)
  value = messages.StringField(2)


class Point(messages.Message):
  time = messages.FloatField(1)
  value = messages.FloatField(2)


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
  def timeseries_update(self, _request):
    return message_types.VoidMessage()

APPLICATION = endpoints.api_server([LoadTestApi])
