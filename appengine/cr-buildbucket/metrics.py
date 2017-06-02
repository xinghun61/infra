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


_TAG_FIELD_NAMES = {
  'builder',
  'user_agent',
  'canary_build',
}

_ATTR_FIELD_NAMES = {
  'bucket',
  'status',
  'result',
  'failure_reason',
  'cancelation_reason'
}
_ALL_FIELD_NAMES = _TAG_FIELD_NAMES | _ATTR_FIELD_NAMES


BUCKETER_24_HR = gae_ts_mon.GeometricBucketer(growth_factor=10 ** 0.05)
BUCKETER_48_HR = gae_ts_mon.GeometricBucketer(growth_factor=10 ** 0.053)
BUCKETER_5_SEC = gae_ts_mon.GeometricBucketer(growth_factor=10 ** 0.0374)
BUCKETER_1K = gae_ts_mon.GeometricBucketer(growth_factor=10 ** 0.031)


def _fields_for(build, field_names):
  """Returns field values for a build"""
  if not build:
    return {
      f: False if f == 'canary_build' else ''
      for f in field_names
    }

  tags = None
  result = {}
  for f in field_names:
    if f in _ATTR_FIELD_NAMES:
      result[f] = str(getattr(build, f) or '')
    elif f in _TAG_FIELD_NAMES:
      if tags is None:
        tags = dict(t.split(':', 1) for t in build.tags)
      if f == 'canary_build':
        result[f] = tags.get(f) == 'true'
      else:
        result[f] = tags.get(f, '')
    else:
      raise ValueError('invalid field %r' % f)
  return result


def _fields_for_fn(fields):
  assert all(f.name in _ALL_FIELD_NAMES for f in fields)
  field_names = [f.name for f in fields]
  return lambda b: _fields_for(b, field_names)   # pragma: no cover


def _mkfields(*names):
  field_types = {
    'canary_build': gae_ts_mon.BooleanField,
  }
  return [field_types.get(n, gae_ts_mon.StringField)(n) for n in names]


def _incrementer(metric):
  """Returns a function that increments the metric.

  Fields must be string and one of _ALL_FIELD_NAMES.

  The returned function accepts a build.
  """
  fields_for = _fields_for_fn(metric.field_spec)
  return lambda b: metric.increment(fields_for(b))   # pragma: no cover


def _adder(metric, value_fn):
  """Returns a function that adds a build value to the distribution metric.

  Fields must be string and one of _ALL_FIELD_NAMES.
  value_fn accepts a build.

  The returned function accepts a build.
  """
  fields_for = _fields_for_fn(metric.field_spec)
  return lambda b: metric.add(value_fn(b), fields_for(b))  # pragma: no cover


inc_created_builds = _incrementer(gae_ts_mon.CounterMetric(
    'buildbucket/builds/created',
    'Build creation',
    _mkfields('bucket', 'builder', 'user_agent', 'canary_build')))
inc_started_builds = _incrementer(gae_ts_mon.CounterMetric(
    'buildbucket/builds/started',
    'Build start',
    _mkfields('bucket', 'builder', 'canary_build')))
inc_completed_builds = _incrementer(gae_ts_mon.CounterMetric(
    'buildbucket/builds/completed',
    'Build completion, including success, failure and cancellation',
    _mkfields(
        'bucket', 'builder', 'result', 'failure_reason', 'cancelation_reason',
        'canary_build')))
inc_heartbeat_failures = _incrementer(gae_ts_mon.CounterMetric(
    'buildbucket/builds/heartbeats',
    'Failures to extend a build lease',
    _mkfields('bucket', 'builder', 'status', 'canary_build')))
inc_lease_expirations = _incrementer(gae_ts_mon.CounterMetric(
    'buildbucket/builds/lease_expired',
    'Build lease expirations',
    _mkfields('bucket', 'builder', 'status', 'canary_build')))
inc_leases = _incrementer(gae_ts_mon.CounterMetric(
    'buildbucket/builds/leases',
    'Successful build leases or lease extensions',
    _mkfields('bucket', 'builder', 'canary_build')))


_BUILD_DURATION_FIELDS = _mkfields(
    'bucket', 'builder', 'result', 'failure_reason', 'cancelation_reason',
    'canary_build')


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


CURRENTLY_PENDING = gae_ts_mon.GaugeMetric(
    'buildbucket/builds/pending',
    'Number of pending builds',
    _mkfields('bucket'))
CURRENTLY_RUNNING = gae_ts_mon.GaugeMetric(
    'buildbucket/builds/running',
    'Number of running builds',
    _mkfields('bucket'))
LEASE_LATENCY_SEC = gae_ts_mon.NonCumulativeDistributionMetric(
    'buildbucket/builds/never_leased_duration',
    'Duration between a build is created and it is leased for the first time',
    _mkfields('bucket'),
    bucketer=BUCKETER_24_HR,
    units=gae_ts_mon.MetricsDataUnits.SECONDS)
SCHEDULING_LATENCY_SEC = gae_ts_mon.NonCumulativeDistributionMetric(
    'buildbucket/builds/scheduling_duration',
    'Duration of a build remaining in SCHEDULED state',
    _mkfields('bucket'),
    bucketer=BUCKETER_48_HR,
    units=gae_ts_mon.MetricsDataUnits.SECONDS)
SEQUENCE_NUMBER_GEN_DURATION_MS = gae_ts_mon.CumulativeDistributionMetric(
    'buildbucket/sequence_number/gen_duration',
    'Duration of a sequence number generation in ms',
    _mkfields('sequence'),
    # Bucketer for 1ms..5s range
    bucketer=BUCKETER_5_SEC,
    units=gae_ts_mon.MetricsDataUnits.MILLISECONDS)
TAG_INDEX_INCONSISTENT_ENTRIES = gae_ts_mon.NonCumulativeDistributionMetric(
    'buildbucket/tag_index/inconsistent_entries',
    'Number of inconsistent entries encountered during build search',
    _mkfields('tag'),
    # We can't have more than 1000 entries in a tag index.
    bucketer=BUCKETER_1K)
TAG_INDEX_SEARCH_SKIPPED_BUILDS = gae_ts_mon.NonCumulativeDistributionMetric(
    'buildbucket/tag_index/skipped_builds',
    'Number of builds we fetched, but skipped',
    _mkfields('tag'),
    # We can't have more than 1000 entries in a tag index.
    bucketer=BUCKETER_1K)


@ndb.tasklet
def set_build_status_metric(metric, bucket, status):
  q = model.Build.query(
      model.Build.bucket == bucket,
      model.Build.status == status)
  value = yield q.count_async()
  metric.set(value, {'bucket': bucket}, target_fields=GLOBAL_TARGET_FIELDS)


@ndb.tasklet
def set_build_latency(metric_sec, bucket, must_be_never_leased):
  q = model.Build.query(
      model.Build.bucket == bucket,
      model.Build.status == model.BuildStatus.SCHEDULED,
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
