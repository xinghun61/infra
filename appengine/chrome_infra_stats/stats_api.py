# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
from datetime import timedelta

import endpoints # pylint: disable=F0401
from protorpc import messages
from protorpc import message_types
from protorpc import remote

import controller  # pylint: disable=W0403


package = 'Stats'


class MasterCollection(messages.Message):
  masters = messages.StringField(1, repeated=True)


class Builder(messages.Message):
  name = messages.StringField(1)
  first_seen = message_types.DateTimeField(2)


class BuilderCollection(messages.Message):
  builders = messages.MessageField(Builder, 1, repeated=True)


def builder_from_ndb(builder):
  b = Builder()
  b.name = builder.name
  b.first_seen = builder.generated
  return b


class Record(messages.Message):
  master = messages.StringField(1)
  builder = messages.StringField(2)
  buildnumber = messages.IntegerField(3)
  revision = messages.StringField(4)
  stepname = messages.StringField(5)
  step_start = message_types.DateTimeField(6)
  step_time = messages.FloatField(7)
  result = messages.IntegerField(8)
  generated = message_types.DateTimeField(9)


def convert_record_from_ndb(record):
  r = Record()
  r.master = record.master
  r.builder = record.builder
  r.buildnumber = record.buildnumber
  r.revision = record.revision
  r.stepname = record.stepname
  r.step_start = record.step_start
  r.step_time = record.step_time
  r.result = record.result
  r.generated = record.generated
  return r


class RecordList(messages.Message):
  step_records = messages.MessageField(Record, 1, repeated=True)


class AggregateType(messages.Enum):
  TIME = 1
  BUILDNUM = 2
  REVISION = 3


class Statistic(messages.Message):
  count = messages.IntegerField(1)
  median = messages.FloatField(2)
  seventyfive = messages.FloatField(3)
  ninety = messages.FloatField(4)
  ninetynine = messages.FloatField(5)
  maximum = messages.FloatField(6)
  mean = messages.FloatField(7)
  stddev = messages.FloatField(8)
  failure_count = messages.IntegerField(9)
  failure_rate = messages.FloatField(10)
  step = messages.StringField(11)
  generated = message_types.DateTimeField(12)
  center = messages.StringField(13)
  aggregation_range = messages.FloatField(14)
  aggregate_type = messages.EnumField(AggregateType, 15)
  start = messages.StringField(16)


class StatisticList(messages.Message):
  statistics = messages.MessageField(Statistic, 1, repeated=True)
  run_url = messages.StringField(16)
  generated = message_types.DateTimeField(17)


class PureStepList(messages.Message):
  steps = messages.StringField(1, repeated=True)


class BuilderList(messages.Message):
  master = messages.StringField(1, required=True)
  builders = messages.StringField(2, repeated=True)


class MasterBuilderList(messages.Message):
  masters = messages.MessageField(BuilderList, 1, repeated=True)


class StepList(messages.Message):
  steps = messages.StringField(1, repeated=True)
  window_hours = messages.FloatField(2)
  window_threshold = messages.IntegerField(3)


def statistic_from_ndb(stat):
  s = Statistic()
  s.count = stat.stats.count
  if s.count > 0:
    s.median = stat.stats.median
    s.seventyfive = stat.stats.seventyfive
    s.ninety = stat.stats.ninety
    s.ninetynine = stat.stats.ninetynine
    s.maximum = stat.stats.maximum
    s.mean = stat.stats.mean
    s.stddev = stat.stats.stddev
    s.failure_count = int(stat.stats.failure_count)
    s.failure_rate = stat.stats.failure_rate
  return s


@endpoints.api(name='stats', version='v1')
class StatsApi(remote.Service):
  """Stats API v1."""

  MASTER_RESOURCE = endpoints.ResourceContainer(
      message_types.VoidMessage,
      master=messages.StringField(1, required=True),
  )

  STEP_RESOURCE = endpoints.ResourceContainer(
      message_types.VoidMessage,
      step=messages.StringField(1, required=True),
      hour=messages.StringField(2, required=True)
  )

  PURE_STEP_RESOURCE = endpoints.ResourceContainer(
      message_types.VoidMessage,
      step=messages.StringField(1, required=True)
  )

  BUILDER_STEP_RESOURCE = endpoints.ResourceContainer(
      message_types.VoidMessage,
      master=messages.StringField(1, required=True),
      builder=messages.StringField(2, required=True)
  )

  LAST_STEP_RESOURCE = endpoints.ResourceContainer(
      message_types.VoidMessage,
      step=messages.StringField(1, required=True),
      limit=messages.IntegerField(2, required=True)
  )

  MASTER_LAST_STEP_RESOURCE = endpoints.ResourceContainer(
      message_types.VoidMessage,
      master=messages.StringField(1, required=True),
      step=messages.StringField(2, required=True),
      limit=messages.IntegerField(3, required=True)
  )

  MASTER_STEP_RESOURCE = endpoints.ResourceContainer(
      message_types.VoidMessage,
      master=messages.StringField(1, required=True),
      step=messages.StringField(2, required=True),
      hour=messages.StringField(3, required=True)
  )

  MASTER_BUILDER_STEP_RESOURCE = endpoints.ResourceContainer(
      message_types.VoidMessage,
      master=messages.StringField(1, required=True),
      builder=messages.StringField(2, required=True),
      step=messages.StringField(3, required=True),
      hour=messages.StringField(4, required=True)
  )

  MASTER_LAST_BUILDER_STEP_RESOURCE = endpoints.ResourceContainer(
      message_types.VoidMessage,
      master=messages.StringField(1, required=True),
      builder=messages.StringField(2, required=True),
      step=messages.StringField(3, required=True),
      limit=messages.IntegerField(4, required=True)
  )


  STEP_AGGREGATE_RESOURCE = endpoints.ResourceContainer(
      step=messages.StringField(1, required=True),
      master = messages.StringField(2),
      builder = messages.StringField(3),
      window = messages.FloatField(4, default=(60 * 60.0)),
      slide = messages.FloatField(5, default=(60 * 60.0)),
      end = messages.StringField(6),
      limit = messages.IntegerField(7, default=24),
      aggregate_type = messages.EnumField(
        AggregateType, 8, default=AggregateType.TIME)
  )


  def _date_parser(self, date):  # pylint: disable=R0201
    try:
      return datetime.strptime(date, '%Y-%m-%dT%H:%MZ')
    except ValueError as e:
      raise endpoints.BadRequestException('can\'t parse date: %s' % e)

  # pylint: disable=C0322
  @endpoints.method(message_types.VoidMessage, StepList,
                    path='steps', http_method='GET',
                    name='steps.list')
  # pylint: disable=R0201
  def get_steps(self, _request):
    result = StepList()
    result.window_hours = float(controller.WORTH_IT_HOUR_WINDOW)
    result.window_threshold = controller.WORTH_IT_THRESH
    result.steps = [s[0] for s in controller.get_cleaned_steps()]
    return result

  # pylint: disable=C0322
  @endpoints.method(message_types.VoidMessage, MasterCollection,
                    path='masters', http_method='GET',
                    name='masters.list')
  # pylint: disable=R0201
  def get_masters(self, _request):
    return MasterCollection(masters=controller.masters)

  # pylint: disable=C0322
  @endpoints.method(MASTER_RESOURCE, BuilderCollection,
                    path='masters/{master}', http_method='GET',
                    name='masters.listBuilders')
  # pylint: disable=R0201
  def get_builders_for_master(self, request):
    return BuilderCollection(builders=list(builder_from_ndb(b) for b in
      controller.get_builders_cached(request.master)))

  # pylint: disable=C0322
  @endpoints.method(BUILDER_STEP_RESOURCE, PureStepList,
                    path='masters/{master}/{builder}', http_method='GET',
                    name='masters.getStepsForBuilder')
  # pylint: disable=R0201
  def get_steps_for_builder(self, request):
    result = PureStepList()
    result.steps = list(controller.get_steps_from_builder(
        request.master, request.builder))
    return result


  # pylint: disable=C0322
  @endpoints.method(PURE_STEP_RESOURCE, MasterBuilderList,
                    path='steps/{step}', http_method='GET',
                    name='steps.getBuildersForStep')
  # pylint: disable=R0201
  def get_builders_for_step(self, request):
    result = MasterBuilderList()
    result.masters = [BuilderList(master=master, builders=builders)
        for master, builders in controller.get_builders_from_step(
          request.step).iteritems()]
    return result

  # pylint: disable=C0322
  @endpoints.method(STEP_RESOURCE, RecordList,
                    path='steps/{step}/{hour}', http_method='GET',
                    name='steps.getForHour')
  # pylint: disable=R0201
  def list_records_for_step(self, request):
    hour = self._date_parser(request.hour)
    hour = hour.replace(minute=0, second=0, microsecond=0)
    end = hour + timedelta(hours=1)
    return RecordList(step_records=list(
      convert_record_from_ndb(r) for r in
      controller.get_step_record_iterator(request.step, hour, end)))

  # pylint: disable=C0322
  @endpoints.method(LAST_STEP_RESOURCE, RecordList,
                    path='steps/last/{step}/{limit}', http_method='GET',
                    name='steps.getLast')
  # pylint: disable=R0201
  def list_last_for_step(self, request):
    return RecordList(step_records=list(
      convert_record_from_ndb(r) for r in
      controller.get_step_last_iterator(request.step, request.limit)))

  # pylint: disable=C0322
  @endpoints.method(MASTER_STEP_RESOURCE, RecordList,
                    path='steps/{master}/{step}/{hour}', http_method='GET',
                    name='steps.getForHourForMaster')
  # pylint: disable=R0201
  def list_records_for_master_step(self, request):
    hour = self._date_parser(request.hour)
    hour = hour.replace(minute=0, second=0, microsecond=0)
    end = hour + timedelta(hours=1)
    return RecordList(step_records=list(
      convert_record_from_ndb(r) for r in
      controller.get_step_master_iterator(request.master,
        request.step, hour, end)))

  # pylint: disable=C0322
  @endpoints.method(MASTER_LAST_STEP_RESOURCE, RecordList,
                    path='steps/last/{master}/{step}/{limit}',
                    http_method='GET', name='steps.getLastForMaster')
  # pylint: disable=R0201
  def list_last_for_master_step(self, request):
    return RecordList(step_records=list(
      convert_record_from_ndb(r) for r in
      controller.get_step_master_last_iterator(request.master,
        request.step, request.limit)))

  # pylint: disable=C0322
  @endpoints.method(MASTER_BUILDER_STEP_RESOURCE, RecordList,
                    path='steps/{master}/{builder}/{step}/{hour}',
                    http_method='GET', name='steps.getForHourForMasterBuilder')
  # pylint: disable=R0201
  def list_records_for_builder_step(self, request):
    hour = self._date_parser(request.hour)
    hour = hour.replace(minute=0, second=0, microsecond=0)
    end = hour + timedelta(hours=1)
    return RecordList(step_records=list(
      convert_record_from_ndb(r) for r in
      controller.get_step_builder_iterator(request.master,
        request.builder, request.step, hour, end)))

  # pylint: disable=C0322
  @endpoints.method(MASTER_LAST_BUILDER_STEP_RESOURCE, RecordList,
                    path='steps/last/{master}/{builder}/{step}/{limit}',
                    http_method='GET', name='steps.getLastForMasterBuilder')
  # pylint: disable=R0201
  def list_records_for_builder_step_last_x(self, request):
    record_iterator = (convert_record_from_ndb(r) for r in
        controller.get_step_builder_last_iterator(
          request.master, request.builder, request.step, request.limit))
    return RecordList(step_records=list(
      convert_record_from_ndb(r) for r in
      record_iterator))

  # pylint: disable=C0322
  @endpoints.method(STEP_RESOURCE, Statistic,
                    path='stats/{step}/{hour}', http_method='GET',
                    name='stats.getForHour')
  # pylint: disable=R0201
  def stats_for_step(self, request):
    hour = self._date_parser(request.hour)
    hour = hour.replace(minute=0, second=0, microsecond=0)
    end = hour + timedelta(hours=1)
    record_iterator = (convert_record_from_ndb(r) for r in
        controller.get_step_record_iterator(request.step, hour, end))
    stat_ndb = controller.get_step_records_internal(request.step, hour, end,
        record_iterator)
    stat_obj = statistic_from_ndb(stat_ndb)
    stat_obj.step = request.step
    stat_obj.generated = datetime.now()
    stat_obj.center = str(hour.replace(minute=30))
    stat_obj.aggregation_range = 60 * 60.0
    stat_obj.aggregate_type = AggregateType.TIME
    return stat_obj

  # pylint: disable=C0322
  @endpoints.method(LAST_STEP_RESOURCE, Statistic,
                    path='stats/last/{step}/{limit}', http_method='GET',
                    name='stats.getLast')
  # pylint: disable=R0201
  def stats_for_last_step(self, request):
    record_iterator = (convert_record_from_ndb(r) for r in
        controller.get_step_last_iterator(request.step, request.limit))
    stat_ndb = controller.get_step_records_internal(request.step,
        datetime.now(), datetime.now(), record_iterator)
    stat_obj = statistic_from_ndb(stat_ndb)
    stat_obj.step = request.step
    stat_obj.generated = datetime.now()
    stat_obj.aggregation_range = float(request.limit)
    stat_obj.aggregate_type = AggregateType.BUILDNUM
    return stat_obj

  # pylint: disable=C0322
  @endpoints.method(MASTER_STEP_RESOURCE, Statistic,
                    path='stats/{master}/{step}/{hour}', http_method='GET',
                    name='stats.getForHourForMaster')
  # pylint: disable=R0201
  def stats_for_master_step(self, request):
    hour = self._date_parser(request.hour)
    hour = hour.replace(minute=0, second=0, microsecond=0)
    end = hour + timedelta(hours=1)
    record_iterator = (convert_record_from_ndb(r) for r in
        controller.get_step_master_iterator(request.master,
          request.step, hour, end))
    stat_ndb = controller.get_step_records_internal('/'.join(
      [request.master, request.step]), hour, end, record_iterator)
    stat_obj = statistic_from_ndb(stat_ndb)
    stat_obj.step = '%s/%s' % (request.master, request.step)
    stat_obj.generated = datetime.now()
    stat_obj.center = str(hour.replace(minute=30))
    stat_obj.aggregation_range = 60 * 60.0
    stat_obj.aggregate_type = AggregateType.TIME
    return stat_obj

  # pylint: disable=C0322
  @endpoints.method(MASTER_LAST_STEP_RESOURCE, Statistic,
                    path='stats/last/{master}/{step}/{limit}',
                    http_method='GET', name='stats.getLastForMaster')
  # pylint: disable=R0201
  def stats_for_last_master_step(self, request):
    record_iterator = (convert_record_from_ndb(r) for r in
        controller.get_step_master_last_iterator(request.master,
          request.step, request.limit))
    stat_ndb = controller.get_step_records_internal('/'.join(
      [request.master, request.step]), datetime.now(), datetime.now(),
      record_iterator)
    stat_obj = statistic_from_ndb(stat_ndb)
    stat_obj.step = '%s/%s' % (request.master, request.step)
    stat_obj.generated = datetime.now()
    stat_obj.aggregation_range = float(request.limit)
    stat_obj.aggregate_type = AggregateType.BUILDNUM
    return stat_obj

  # pylint: disable=C0322
  @endpoints.method(MASTER_BUILDER_STEP_RESOURCE, Statistic,
                    path='stats/{master}/{builder}/{step}/{hour}',
                    http_method='GET', name='stats.getForHourForMasterBuilder')
  # pylint: disable=R0201
  def stats_for_builder_step(self, request):
    hour = self._date_parser(request.hour)
    hour = hour.replace(minute=0, second=0, microsecond=0)
    end = hour + timedelta(hours=1)
    record_iterator = (convert_record_from_ndb(r) for r in
        controller.get_step_builder_iterator(request.master,
          request.builder, request.step, hour, end))
    stat_ndb = controller.get_step_records_internal('/'.join(
      [request.master, request.builder, request.step]),
      hour, end, record_iterator)
    stat_obj = statistic_from_ndb(stat_ndb)
    stat_obj.step = '%s/%s/%s' % (request.master, request.builder, request.step)
    stat_obj.generated = datetime.now()
    stat_obj.center = str(hour.replace(minute=30))
    stat_obj.aggregation_range = 60 * 60.0
    stat_obj.aggregate_type = AggregateType.TIME
    return stat_obj

  # pylint: disable=C0322
  @endpoints.method(MASTER_LAST_BUILDER_STEP_RESOURCE, Statistic,
                    path='stats/last/{master}/{builder}/{step}/{limit}',
                    http_method='GET', name='stats.getLastForMasterBuilder')
  # pylint: disable=R0201
  def stats_for_builder_step_last_x(self, request):
    record_iterator = (convert_record_from_ndb(r) for r in
        controller.get_step_builder_last_iterator(
          request.master, request.builder, request.step, request.limit))
    stat_ndb = controller.get_step_records_internal('/'.join(
      [request.master, request.builder, request.step]),
      datetime.now(), datetime.now(), record_iterator, finalize=False)
    stat_obj = statistic_from_ndb(stat_ndb)
    stat_obj.step = '%s/%s/%s' % (request.master, request.builder, request.step)
    stat_obj.generated = datetime.now()
    stat_obj.aggregation_range = float(request.limit)
    stat_obj.aggregate_type = AggregateType.BUILDNUM
    return stat_obj

  # pylint: disable=C0322
  @endpoints.method(STEP_AGGREGATE_RESOURCE, StatisticList,
                    path='aggregate/{step}', http_method='GET',
                    name='aggregate.get')
  # pylint: disable=R0201
  def get_aggregate(self, request):
    raise endpoints.InternalServerErrorException('Not yet implemented')


APPLICATION = endpoints.api_server([StatsApi])
