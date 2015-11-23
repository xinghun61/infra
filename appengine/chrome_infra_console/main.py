# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json
import logging

import endpoints
import webapp2
from google.appengine.api import namespace_manager
from google.appengine.ext import ndb
from google.appengine.ext.appstats import recording
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from components import auth
from components import config
from components.config.proto import project_config_pb2


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


class TimeSeriesPacket(messages.Message):
  timeseries = messages.MessageField(TimeSeries, 1, repeated=True)
  project_name = messages.StringField(2)

class PointModel(ndb.Model):
  time = ndb.FloatProperty()
  value = ndb.FloatProperty()


class FieldModel(ndb.Model):
  field_key = ndb.StringProperty()
  value = ndb.StringProperty()


class TimeSeriesModel(ndb.Model):
  timestamp = ndb.DateTimeProperty()
  points = ndb.StructuredProperty(PointModel, repeated=True)
  fields = ndb.StructuredProperty(FieldModel, repeated=True)
  metric = ndb.StringProperty()

  def update_timestamp(self):
    self.timestamp = time_now()


def time_now():
  """This is for mocking in test."""
  return datetime.datetime.utcnow()


class Config(messages.Message):
  id = messages.StringField(1, required=True)
  revision = messages.StringField(2)
  access = messages.StringField(3, repeated=True)


class Configs(messages.Message):
  configs = messages.MessageField(Config, 1, repeated=True)


class GetGraphsRequest(messages.Message):
  project_id = messages.StringField(1, required=True)


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

  @auth.endpoints_method(TimeSeriesPacket, message_types.VoidMessage,
                         name='timeseries.update')
  @auth.require(lambda: auth.is_group_member(
      'chrome-infra-console-update-access'))
  def timeseries_update(self, request):
    futures = [timeseries_query(t) for t in request.timeseries]
    ndb.Future.wait_all(futures)
    for future in futures:
      future.get_result()
    return message_types.VoidMessage()


@ndb.tasklet
def timeseries_query(timeseries):
  project_id = list(field.value for field in timeseries.fields if
                    field.key == 'project_id')
  if not project_id:
    raise ndb.Return()
  project_id = project_id[0]
  namespace_manager.set_namespace('projects.%s' % project_id)
  query = TimeSeriesModel.query()
  fieldmodels = []
  for field in timeseries.fields:
    fieldmodels.append(FieldModel(field_key=field.key, value=field.value))
  for fieldmodel in fieldmodels:
    query = query.filter(TimeSeriesModel.fields == fieldmodel)
  query = query.filter(TimeSeriesModel.metric == timeseries.metric)
  ts = yield query.get_async()
  if ts == None:
    ts = TimeSeriesModel(
      points=[], fields=fieldmodels, metric=timeseries.metric)
  ts.update_timestamp()
  ts.points = [PointModel(time=point.time, value=point.value)
               for point in timeseries.points]
  yield ts.put_async()
  raise ndb.Return()


@auth.endpoints_api(name='ui', version='v1')
class UIApi(remote.Service):
  """API for the console configuration UI."""

  @auth.endpoints_method(message_types.VoidMessage, Configs)
  @auth.public
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

  @auth.endpoints_method(GetGraphsRequest, TimeSeriesPacket)
  @auth.public
  def get_graphs(self, request):
    logging.debug('Got %s', request)
    project_id = request.project_id
    revision, project_cfg = config.get_project_config(
        project_id, 'project.cfg', project_config_pb2.ProjectCfg)

    if revision is None:
      logging.warning('Project %s does not have project.cfg', project_id)
      return TimeSeriesPacket()

    graph_list = []
    if not _has_access(project_cfg.access):
      logging.warning('Access to %s is denied for user %s',
                  project_id, auth.get_current_identity())
      return TimeSeriesPacket()

    namespace_manager.set_namespace('projects.%s' % project_id)
    for graph in TimeSeriesModel.query():
      field_list = [Field(key=field.field_key, value=field.value)
                    for field in graph.fields]
      point_list = [Point(time=point.time, value=point.value)
                    for point in graph.points]
      graph_list.append(TimeSeries(points=point_list,
                                   fields=field_list,
                                   metric=graph.metric))

    return TimeSeriesPacket(timeseries=graph_list,
                            project_name=project_cfg.name)


def add_appstats(app):
  return recording.appstats_wsgi_middleware(app)


class CronHandler(webapp2.RequestHandler):

  def get(self):
    for ns in ndb.metadata.get_namespaces():
      namespace_manager.set_namespace(ns)
      cut_off = time_now() - datetime.timedelta(hours=24)
      query = TimeSeriesModel.query()
      query = query.filter(TimeSeriesModel.timestamp <= cut_off)
      query = query.order(TimeSeriesModel.timestamp)
      for key in query.iter(keys_only=True):
        key.delete()


class TimeSeriesHandler(auth.AuthenticatingHandler):

  @auth.require(lambda: auth.is_group_member(
      'chrome-infra-console-update-access'))
  def post(self):
    data = json.loads(self.request.body)
    tsList = []
    for timeseries in data['timeseries']:
      points = []
      fields = []
      for point in timeseries['points']:
        points.append(Point(time=float(point['time']),
                            value=float(point['value'])))
      for field in timeseries['fields']:
        fields.append(Field(key=field['key'], value=field['value']))
      tsList.append(TimeSeries(points=points, fields=fields,
                               metric=timeseries['metric']))
    futures = [timeseries_query(t) for t in tsList]
    ndb.Future.wait_all(futures)
    for future in futures:
      future.get_result()
    return message_types.VoidMessage()


handlers = [
  ('/tasks/clean_outdated_graphs', CronHandler),
  ('/timeseries_update', TimeSeriesHandler),
]

WEBAPP = add_appstats(webapp2.WSGIApplication(handlers, debug=True))

APPLICATION = add_appstats(ndb.toplevel(endpoints.api_server([
    ConsoleAppApi, UIApi, config.ConfigApi])))
