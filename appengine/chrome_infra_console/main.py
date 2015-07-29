# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

import endpoints
from google.appengine.api import namespace_manager
from google.appengine.ext import ndb
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from components import auth
from components import config
from proto import project_config_pb2

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


class PointModel(ndb.Model):
  time = ndb.FloatProperty()
  value = ndb.FloatProperty()


class FieldModel(ndb.Model):
  field_key = ndb.StringProperty()
  value = ndb.StringProperty()


class TimeSeriesModel(ndb.Model):
  points = ndb.StructuredProperty(PointModel, repeated=True)
  fields = ndb.StructuredProperty(FieldModel, repeated=True)
  metric = ndb.StringProperty()


class Config(messages.Message):
  id = messages.StringField(1, required=True)
  revision = messages.StringField(2)
  access = messages.StringField(3, repeated=True)


class Configs(messages.Message):
  configs = messages.MessageField(Config, 1, repeated=True)

 
def _has_access(access_list):
  cur_ident = auth.get_current_identity().to_bytes()
  for ac in access_list:
    if ac.startswith('group:'):
      if auth.is_group_member(ac.split(':', 2)[1]):
        return True
    else:
      identity_str = ac
      if ':' not in identity_str:
        identity_str = 'user:%s' % identity_str
      if cur_ident == identity_str:
        return True
  return False


@auth.endpoints_api(name='consoleapp', version='v1')
class ConsoleAppApi(remote.Service):
  """API that receives projects timeseries data from Borg job."""

  @auth.endpoints_method(DataPacket, message_types.VoidMessage,
                         name='timeseries.update')
  @auth.require(lambda: auth.is_group_member('metric-generators'))
  def timeseries_update(self, request):
    for timeseries in request.timeseries:
      project_id = list(field.value for field in timeseries.fields if
                        field.key == 'project_id')
      if not project_id:
        continue
      project_id = project_id[0]
      namespace_manager.set_namespace('projects.%s' % project_id)
      query = TimeSeriesModel.query()
      fieldmodels = []
      for field in timeseries.fields:
        fieldmodels.append(FieldModel(field_key=field.key, value=field.value))
      for fieldmodel in fieldmodels:
        query = query.filter(TimeSeriesModel.fields == fieldmodel)
      query = query.filter(TimeSeriesModel.metric == timeseries.metric)
      ts = query.get()
      if ts == None:
        ts = TimeSeriesModel(
            points=[], fields=fieldmodels, metric=timeseries.metric)
      ts.points = [PointModel(time=point.time, value=point.value)
                   for point in timeseries.points]
      ts.put()
    return message_types.VoidMessage()


@auth.endpoints_api(name='ui', version='v1')
class UIApi(remote.Service):
  """API for the console configuration UI."""

  @auth.endpoints_method(message_types.VoidMessage, Configs)
  def get_projects(self, _request):
    project_configs = config.get_project_configs(
        'project.cfg', project_config_pb2.ProjectCfg) 
    configList = []
    for project_id, (revision, project_cfg) in project_configs.iteritems():
      if _has_access(project_cfg.access):
        configList.append(Config(id=project_id, 
                                 revision=revision, 
                                 access=project_cfg.access[:]))
    return Configs(configs=configList)
      

APPLICATION = endpoints.api_server([ConsoleAppApi, UIApi, config.ConfigApi])
