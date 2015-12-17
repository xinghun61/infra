# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.api import app_identity
from google.appengine.ext import ndb

from components import metrics
from components import utils
import gae_ts_mon

import config
import model

# TODO(nodir): remove Cloud Monitoring and refactor
# when gae_ts_mon is stabilized

# TODO(nodir): move this list to luci-config
TAG_FIELDS = [
  'builder',
  'user_agent',
]

LABEL_BUCKET = 'buildbucket/bucket'
COMMON_LABELS = {
  LABEL_BUCKET: 'Bucket'
}
METRIC_PENDING_BUILDS = metrics.Descriptor(
  name='buildbucket/builds/pending',
  description='Number of pending builds',
  labels=COMMON_LABELS,
)
METRIC_RUNNING_BUILDS = metrics.Descriptor(
  name='buildbucket/builds/running',
  description='Number of running builds',
  labels=COMMON_LABELS,
)
METRIC_LEASE_BUILD_LATENCY = metrics.Descriptor(
  name='buildbucket/builds/lease_latency',
  description=(
    'Average number of seconds for a scheduled build to be leased '
    'for the first time'),
  value_type='double',
  labels=COMMON_LABELS,
)
METRIC_SCHEDULING_LATENCY = metrics.Descriptor(
  name='buildbucket/builds/scheduling_latency',
  description=(
    'Average number of seconds for a scheduled build '
    'to remain in SCHEDULED leased state'
  ),
  value_type='double',
  labels=COMMON_LABELS,
)

# gae_ts_mon
FIELD_BUCKET = 'bucket'
COMMON_FIELDS = {
  'buildbucket_hostname': app_identity.get_default_version_hostname(),
}


def _def_metric(metric_type, name, description):
  return metric_type(
    'buildbucket/%s' % name,
    fields=COMMON_FIELDS,
    description=description)


CREATE_COUNT = _def_metric(
  gae_ts_mon.CounterMetric,
  'builds/created',
  'Build creation',
)
START_COUNT = _def_metric(
  gae_ts_mon.CounterMetric,
  'builds/started',
  'Build start',
)
COMPLETE_COUNT = _def_metric(
  gae_ts_mon.CounterMetric,
  'builds/completed',
  'Build completion, including success, failure and cancellation'
)
HEARTBEAT_COUNT = _def_metric(
  gae_ts_mon.CounterMetric,
  'builds/heartbeats',
  'Failures to extend a build lease'
)
LEASE_COUNT = _def_metric(
  gae_ts_mon.CounterMetric,
  'builds/leases',
  'Successful build lease extension',
)
LEASE_EXPIRATION_COUNT = _def_metric(
  gae_ts_mon.CounterMetric,
  'builds/lease_expired',
  'Build lease expirations'
)
CURRENTLY_PENDING = _def_metric(
  gae_ts_mon.GaugeMetric,
  'builds/pending',
  'Number of pending builds',
)
CURRENTLY_RUNNING = _def_metric(
  gae_ts_mon.GaugeMetric,
  'builds/running',
  'Number of running builds'
)
LEASE_LATENCY = _def_metric(
  gae_ts_mon.NonCumulativeDistributionMetric,
  'builds/never_leased_duration',
  'Duration between a build is created and it is leased for the first time',
)
SCHEDULING_LATENCY = _def_metric(
  gae_ts_mon.NonCumulativeDistributionMetric,
  'builds/scheduling_duration',
  'Duration of a build remaining in SCHEDULED state',
)


GAUGE_OF_CLOUD_METRIC = {
  METRIC_PENDING_BUILDS: CURRENTLY_PENDING,
  METRIC_RUNNING_BUILDS: CURRENTLY_RUNNING,
}
DISTRIBUTION_OF_CLOUD_METRIC = {
  METRIC_LEASE_BUILD_LATENCY: LEASE_LATENCY,
  METRIC_SCHEDULING_LATENCY: SCHEDULING_LATENCY,
}

def fields_for(build, **extra):
  fields = extra
  fields.setdefault(FIELD_BUCKET, build.bucket if build else '<no bucket>')
  if build:  # pragma: no branch
    tags = dict(t.split(':', 1) for t in build.tags)
    for t in TAG_FIELDS:
      fields.setdefault(t, tags.get(t))
  return fields


def increment(metric, build, **fields):  # pragma: no cover
  """Increments a counter metric."""
  metric.increment(fields_for(build, **fields))


def set_gauge(buf, bucket, metric, value):
  logging.info('Bucket %s: %s = %d', bucket, metric.name, value)
  buf.set_gauge(metric, value, {LABEL_BUCKET: bucket})
  gae_ts_mon_metric = GAUGE_OF_CLOUD_METRIC.get(metric)
  if gae_ts_mon_metric:
    gae_ts_mon_metric.set(value, {FIELD_BUCKET: bucket})


@ndb.tasklet
def send_build_status_metric(buf, bucket, metric, status):
  q = model.Build.query(
    model.Build.bucket == bucket,
    model.Build.status == status)
  value = yield q.count_async()
  set_gauge(buf, bucket, metric, value)


@ndb.tasklet
def send_build_latency(buf, metric, bucket, must_be_never_leased):
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
  avg_latency = 0.0
  count = 0
  dist = gae_ts_mon.Distribution(gae_ts_mon.GeometricBucketer())
  for e in q.iter(projection=[model.Build.create_time]):
    latency = (now - e.create_time).total_seconds()
    dist.add(latency)
    avg_latency += latency
    count += 1
  if count > 0:
    avg_latency /= count
  set_gauge(buf, bucket, metric, avg_latency)
  DISTRIBUTION_OF_CLOUD_METRIC[metric].set(dist, {FIELD_BUCKET: bucket})


def send_all_metrics():
  buf = metrics.Buffer()
  futures = []
  for b in config.get_buckets_async().get_result():
    futures.extend([
      send_build_status_metric(
        buf, b.name, METRIC_PENDING_BUILDS, model.BuildStatus.SCHEDULED),
      send_build_status_metric(
        buf, b.name, METRIC_RUNNING_BUILDS, model.BuildStatus.STARTED),
      send_build_latency(buf, METRIC_LEASE_BUILD_LATENCY, b.name, True),
      send_build_latency(buf, METRIC_SCHEDULING_LATENCY, b.name, False),
    ])
  ndb.Future.wait_all(futures)
  buf.flush()
  for f in futures:
    f.check_success()
