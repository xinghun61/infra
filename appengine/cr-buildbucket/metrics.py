# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

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
  'user_agent'
}
_ATTR_FIELD_NAMES = {
  'bucket',
  'status',
  'result',
  'failure_reason',
  'cancelation_reason'
}
_ALL_FIELD_NAMES = _TAG_FIELD_NAMES | _ATTR_FIELD_NAMES


def _fields_for(build, field_names):
  """Returns field values for a build"""
  if not build:
    return {f: '' for f in field_names}

  tags = None
  result = {}
  for f in field_names:
    if f in _ATTR_FIELD_NAMES:
      result[f] = str(getattr(build, f) or '')
    elif f in _TAG_FIELD_NAMES:
      if tags is None:
        tags = dict(t.split(':', 1) for t in build.tags)
      result[f] = tags.get(f, '')
    else:
      raise ValueError('invalid field %r' % f)
  return result


def _counter_metric_incrementer(name, desc, field_names):
  """Defines a counter metric and returns a function to increment it.

  field_names must be a list of field names.
  See _ALL_FIELD_NAMES for valid names.

  The returned function accepts a build.
  """
  assert all(f in _ALL_FIELD_NAMES for f in field_names)
  metric = gae_ts_mon.CounterMetric(
      name, desc, [gae_ts_mon.StringField(f) for f in field_names])
  return lambda b: metric.increment(   # pragma: no cover
      _fields_for(b, field_names))


inc_created_builds = _counter_metric_incrementer(
    'buildbucket/builds/created',
    'Build creation',
    ['bucket', 'builder', 'user_agent'])
inc_started_builds = _counter_metric_incrementer(
    'buildbucket/builds/started',
    'Build start',
    ['bucket', 'builder'])
inc_completed_builds = _counter_metric_incrementer(
    'buildbucket/builds/completed',
    'Build completion, including success, failure and cancellation',
    ['bucket', 'builder', 'result', 'failure_reason', 'cancelation_reason'])
inc_heartbeat_failures = _counter_metric_incrementer(
    'buildbucket/builds/heartbeats',
    'Failures to extend a build lease',
    ['bucket', 'builder', 'status'])
inc_lease_expirations = _counter_metric_incrementer(
    'buildbucket/builds/lease_expired',
    'Build lease expirations',
    ['bucket', 'builder', 'status'])
inc_leases = _counter_metric_incrementer(
    'buildbucket/builds/leases',
    'Successful build leases or lease extensions',
    ['bucket', 'builder'])

CURRENTLY_PENDING = gae_ts_mon.GaugeMetric(
    'buildbucket/builds/pending',
    'Number of pending builds',
    [gae_ts_mon.StringField('bucket')])
CURRENTLY_RUNNING = gae_ts_mon.GaugeMetric(
    'buildbucket/builds/running',
    'Number of running builds',
    [gae_ts_mon.StringField('bucket')])
LEASE_LATENCY = gae_ts_mon.NonCumulativeDistributionMetric(
    'buildbucket/builds/never_leased_duration',
    'Duration between a build is created and it is leased for the first time',
    [gae_ts_mon.StringField('bucket')],
    # Bucketer for 1s..24h range
    bucketer=gae_ts_mon.GeometricBucketer(growth_factor=10 ** 0.05))
SCHEDULING_LATENCY = gae_ts_mon.NonCumulativeDistributionMetric(
    'buildbucket/builds/scheduling_duration',
    'Duration of a build remaining in SCHEDULED state',
    [gae_ts_mon.StringField('bucket')],
    # Bucketer for 1s..48h range
    bucketer=gae_ts_mon.GeometricBucketer(growth_factor=10**0.053))
SEQUENCE_NUMBER_GEN_DURATION_MS = gae_ts_mon.CumulativeDistributionMetric(
    'buildbucket/sequence_number/gen_duration',
    'Duration of a sequence number generation in ms',
    [gae_ts_mon.StringField('sequence')],
    # Bucketer for 1ms..5s range
    bucketer=gae_ts_mon.GeometricBucketer(growth_factor=10**0.0374))
TAG_INDEX_INCONSISTENT_ENTRIES = gae_ts_mon.NonCumulativeDistributionMetric(
    'buildbucket/tag_index/inconsistent_entries',
    'Number of inconsistent entries encountered during build search',
    [gae_ts_mon.StringField('tag')],
    # Bucketer for 0..1000 range, because we can't have more than 1000 entries
    # in a tag index.
    bucketer=gae_ts_mon.GeometricBucketer(growth_factor=10 ** 0.031))
TAG_INDEX_SEARCH_SKIPPED_BUILDS = gae_ts_mon.NonCumulativeDistributionMetric(
    'buildbucket/tag_index/skipped_builds',
    'Number of builds we fetched, but skipped',
    [gae_ts_mon.StringField('tag')],
    # Bucketer for 0..1000 range, because we can't have more than 1000 entries
    # in a tag index.
    bucketer=gae_ts_mon.GeometricBucketer(growth_factor=10 ** 0.031))


@ndb.tasklet
def set_build_status_metric(metric, bucket, status):
  q = model.Build.query(
      model.Build.bucket == bucket,
      model.Build.status == status)
  value = yield q.count_async()
  metric.set(value, {'bucket': bucket}, target_fields=GLOBAL_TARGET_FIELDS)


@ndb.tasklet
def set_build_latency(metric, bucket, must_be_never_leased):
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
  metric.set(dist, {'bucket': bucket}, target_fields=GLOBAL_TARGET_FIELDS)


# Metrics that are per-app rather than per-instance.
GLOBAL_METRICS = [
  CURRENTLY_PENDING,
  CURRENTLY_RUNNING,
  LEASE_LATENCY,
  SCHEDULING_LATENCY,
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
      set_build_latency(LEASE_LATENCY, b.name, True),
      set_build_latency(SCHEDULING_LATENCY, b.name, False),
    ])
  for f in futures:
    f.check_success()
