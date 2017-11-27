# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime

from google.appengine.ext import ndb

from components import utils
import gae_ts_mon

import config
import model


# Override default target fields for app-global metrics.
GLOBAL_TARGET_FIELDS = {
  'job_name': '',  # module name
  'hostname': '',  # version
  'task_num': 0,  # instance ID
}

_SOURCE_TAG = 0   # read field the value from a tag
_SOURCE_ATTR = 1  # read field the value from an attr
# tuple item meanings are: value source, gae_ts_mon field type, value type.
_TAG_STR_FIELD = (_SOURCE_TAG, gae_ts_mon.StringField, str)
_ATTR_STR_FIELD = (_SOURCE_ATTR, gae_ts_mon.StringField, str)
_BUILD_FIELDS = {
  'bucket': _ATTR_STR_FIELD,
  'builder': _TAG_STR_FIELD,
  'canary': (_SOURCE_ATTR, gae_ts_mon.BooleanField, bool),
  'cancelation_reason': _ATTR_STR_FIELD,
  'failure_reason': _ATTR_STR_FIELD,
  'result': _ATTR_STR_FIELD,
  'status': _ATTR_STR_FIELD,
  'user_agent': _TAG_STR_FIELD,
}

def _default_field_value(name):
  return _BUILD_FIELDS[name][2]()


BUCKETER_24_HR = gae_ts_mon.GeometricBucketer(growth_factor=10 ** 0.05)
BUCKETER_48_HR = gae_ts_mon.GeometricBucketer(growth_factor=10 ** 0.053)
BUCKETER_5_SEC = gae_ts_mon.GeometricBucketer(growth_factor=10 ** 0.0374)
BUCKETER_1K = gae_ts_mon.GeometricBucketer(growth_factor=10 ** 0.031)


def _fields_for(build, field_names):
  """Returns field values for a build"""
  for f in field_names:
    if f not in _BUILD_FIELDS:
      raise ValueError('invalid field %r' % f)

  tags = None
  result = {}
  for f in field_names:
    src, _, typ = _BUILD_FIELDS[f]
    assert src in (_SOURCE_ATTR, _SOURCE_TAG)
    if src == _SOURCE_ATTR:
      val = getattr(build, f)
    else:
      if tags is None:
        tags = dict(t.split(':', 1) for t in build.tags)
      val = tags.get(f)
    result[f] = typ(val or _default_field_value(f))
  return result


def _fields_for_fn(fields):
  assert all(f.name in _BUILD_FIELDS for f in fields)
  field_names = [f.name for f in fields]
  return lambda b: _fields_for(b, field_names)   # pragma: no cover


def _build_fields(*names):
  return [_BUILD_FIELDS[n][1](n) for n in names]


def _incrementer(metric):
  """Returns a function that increments the metric.

  Metric fields must conform _BUILD_FIELDS.

  The returned function accepts a build, but ignores it if it is experimental.
  """
  fields_for = _fields_for_fn(metric.field_spec)
  def inc(build):  # pragma: no cover
    if not build.experimental:
      metric.increment(fields_for(build))
  return inc


def _adder(metric, value_fn):
  """Returns a function that adds a build value to the distribution metric.

  Metric fields must conform _BUILD_FIELDS.
  value_fn accepts a build.

  The returned function accepts a build, but ignores it if it is experimental.
  """
  fields_for = _fields_for_fn(metric.field_spec)
  def add(build):  # pragma: no cover
    if not build.experimental:
      metric.add(value_fn(build), fields_for(build))
  return add


inc_created_builds = _incrementer(gae_ts_mon.CounterMetric(
    'buildbucket/builds/created',
    'Build creation',
    _build_fields('bucket', 'builder', 'user_agent')))
inc_started_builds = _incrementer(gae_ts_mon.CounterMetric(
    'buildbucket/builds/started',
    'Build start',
    _build_fields('bucket', 'builder', 'canary')))
inc_completed_builds = _incrementer(gae_ts_mon.CounterMetric(
    'buildbucket/builds/completed',
    'Build completion, including success, failure and cancellation',
    _build_fields(
        'bucket', 'builder', 'result', 'failure_reason', 'cancelation_reason',
        'canary')))
inc_lease_expirations = _incrementer(gae_ts_mon.CounterMetric(
    'buildbucket/builds/lease_expired',
    'Build lease expirations',
    _build_fields('bucket', 'builder', 'status')))
inc_leases = _incrementer(gae_ts_mon.CounterMetric(
    'buildbucket/builds/leases',
    'Successful build leases or lease extensions',
    _build_fields('bucket', 'builder')))


inc_heartbeat_failures = gae_ts_mon.CounterMetric(
    'buildbucket/builds/heartbeats',
    'Failures to extend a build lease', []).increment


_BUILD_DURATION_FIELDS = _build_fields(
    'bucket', 'builder', 'result', 'failure_reason', 'cancelation_reason',
    'canary')


# requires the argument to have non-None create_time and complete_time.
add_build_cycle_duration = _adder(  # pragma: no branch
    gae_ts_mon.NonCumulativeDistributionMetric(
        'buildbucket/builds/cycle_durations',
        'Duration between build creation and completion',
        _BUILD_DURATION_FIELDS,
        bucketer=BUCKETER_48_HR,
        units=gae_ts_mon.MetricsDataUnits.SECONDS),
    lambda b: (b.complete_time - b.create_time).total_seconds())


# requires the argument to have non-None start_time and complete_time.
add_build_run_duration = _adder(  # pragma: no branch
    gae_ts_mon.NonCumulativeDistributionMetric(
        'buildbucket/builds/run_durations',
        'Duration between build start and completion',
        _BUILD_DURATION_FIELDS,
        bucketer=BUCKETER_48_HR,
        units=gae_ts_mon.MetricsDataUnits.SECONDS),
    lambda b: (b.complete_time - b.start_time).total_seconds())


# requires the argument to have non-None create_time and start_time.
add_build_scheduling_duration = _adder(  # pragma: no branch
    gae_ts_mon.NonCumulativeDistributionMetric(
        'buildbucket/builds/scheduling_durations',
        'Duration between build creation and start',
        _BUILD_DURATION_FIELDS,
        bucketer=BUCKETER_48_HR,
        units=gae_ts_mon.MetricsDataUnits.SECONDS),
    lambda b: (b.start_time - b.create_time).total_seconds())


CURRENTLY_PENDING = gae_ts_mon.GaugeMetric(
    'buildbucket/builds/pending',
    'Number of pending builds',
    _build_fields('bucket'))
CURRENTLY_RUNNING = gae_ts_mon.GaugeMetric(
    'buildbucket/builds/running',
    'Number of running builds',
    _build_fields('bucket'))
LEASE_LATENCY_SEC = gae_ts_mon.NonCumulativeDistributionMetric(
    'buildbucket/builds/never_leased_duration',
    'Duration between a build is created and it is leased for the first time',
    _build_fields('bucket'),
    bucketer=BUCKETER_24_HR,
    units=gae_ts_mon.MetricsDataUnits.SECONDS)
SCHEDULING_LATENCY_SEC = gae_ts_mon.NonCumulativeDistributionMetric(
    'buildbucket/builds/scheduling_duration',
    'Duration of a build remaining in SCHEDULED state',
    _build_fields('bucket'),
    bucketer=BUCKETER_48_HR,
    units=gae_ts_mon.MetricsDataUnits.SECONDS)
SEQUENCE_NUMBER_GEN_DURATION_MS = gae_ts_mon.CumulativeDistributionMetric(
    'buildbucket/sequence_number/gen_duration',
    'Duration of a sequence number generation in ms',
    [gae_ts_mon.StringField('sequence')],
    # Bucketer for 1ms..5s range
    bucketer=BUCKETER_5_SEC,
    units=gae_ts_mon.MetricsDataUnits.MILLISECONDS)
TAG_INDEX_INCONSISTENT_ENTRIES = gae_ts_mon.NonCumulativeDistributionMetric(
    'buildbucket/tag_index/inconsistent_entries',
    'Number of inconsistent entries encountered during build search',
    [gae_ts_mon.StringField('tag')],
    # We can't have more than 1000 entries in a tag index.
    bucketer=BUCKETER_1K)
TAG_INDEX_SEARCH_SKIPPED_BUILDS = gae_ts_mon.NonCumulativeDistributionMetric(
    'buildbucket/tag_index/skipped_builds',
    'Number of builds we fetched, but skipped',
    [gae_ts_mon.StringField('tag')],
    # We can't have more than 1000 entries in a tag index.
    bucketer=BUCKETER_1K)


@ndb.tasklet
def set_build_status_metric(metric, bucket, status):
  q = model.Build.query(
      model.Build.bucket == bucket,
      model.Build.status == status,
      model.Build.experimental == False,
  )
  value = yield q.count_async()
  metric.set(value, {'bucket': bucket}, target_fields=GLOBAL_TARGET_FIELDS)


@ndb.tasklet
def set_build_latency(metric_sec, bucket, must_be_never_leased):
  q = model.Build.query(
      model.Build.bucket == bucket,
      model.Build.status == model.BuildStatus.SCHEDULED,
      model.Build.experimental == False,
  )
  if must_be_never_leased:
    q = q.filter(model.Build.never_leased == True)
  else:
    # Reuse the index that has never_leased
    q = q.filter(model.Build.never_leased.IN((True, False)))

  now = utils.utcnow()
  dist = gae_ts_mon.Distribution(gae_ts_mon.GeometricBucketer())
  for e in q.iter(projection=[model.Build.create_time]):
    latency = (now - e.create_time).total_seconds()
    dist.add(latency)
  if dist.count == 0:
    dist.add(0)
  metric_sec.set(dist, {'bucket': bucket}, target_fields=GLOBAL_TARGET_FIELDS)


# Metrics that are per-app rather than per-instance.
GLOBAL_METRICS = [
  CURRENTLY_PENDING,
  CURRENTLY_RUNNING,
  LEASE_LATENCY_SEC,
  SCHEDULING_LATENCY_SEC,
]


def update_global_metrics():
  """Updates the metrics in GLOBAL_METRICS."""
  futures = []
  for b in config.get_buckets_async().get_result():
    futures.extend([
      set_build_status_metric(
          CURRENTLY_PENDING, b.name, model.BuildStatus.SCHEDULED),
      set_build_status_metric(
          CURRENTLY_RUNNING, b.name, model.BuildStatus.STARTED),
      set_build_latency(LEASE_LATENCY_SEC, b.name, True),
      set_build_latency(SCHEDULING_LATENCY_SEC, b.name, False),
    ])
  for f in futures:
    f.check_success()
