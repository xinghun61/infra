# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from components import metrics
from components import utils

import config
import model


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


def set_gauge(buf, bucket, metric, value):
  logging.info('Bucket %s: %s = %d', bucket, metric.name, value)
  buf.set_gauge(metric, value, {LABEL_BUCKET: bucket})


@ndb.tasklet
def send_build_status_metric(buf, bucket, metric, status):
  q = model.Build.query(
      model.Build.bucket == bucket,
      model.Build.status == status)
  value = yield q.count_async()
  set_gauge(buf, bucket, metric, value)


@ndb.tasklet
def send_build_lease_latency(buf, bucket):
  q = model.Build.query(
      model.Build.bucket == bucket,
      model.Build.status == model.BuildStatus.SCHEDULED,
      model.Build.never_leased == True,
  )
  now = utils.utcnow()

  avg_latency = 0.0
  count = 0
  for e in q.iter(projection=[model.Build.create_time]):
    avg_latency += (now - e.create_time).total_seconds()
    count += 1
  if count > 0:
    avg_latency /= count
    set_gauge(buf, bucket, METRIC_LEASE_BUILD_LATENCY, avg_latency)


def send_all_metrics():
  buf = metrics.Buffer()
  futures = []
  for b in config.get_buckets_async().get_result():
    futures.extend([
        send_build_status_metric(
            buf, b.name, METRIC_PENDING_BUILDS, model.BuildStatus.SCHEDULED),
        send_build_status_metric(
            buf, b.name, METRIC_RUNNING_BUILDS, model.BuildStatus.STARTED),
        send_build_lease_latency(buf, b.name),
    ])
  ndb.Future.wait_all(futures)
  buf.flush()
  for f in futures:
    f.check_success()
