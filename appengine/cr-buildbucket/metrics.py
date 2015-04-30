# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from components import metrics

import acl
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


@ndb.tasklet
def send_build_status_metric(buf, bucket, metric, status):
  q = model.Build.query(
      model.Build.bucket == bucket,
      model.Build.status == status)
  value = yield q.count_async()
  logging.info('Bucket %s: %s = %d', bucket, metric.name, value)
  buf.set_gauge(metric, value, {LABEL_BUCKET: bucket})


def iter_all_buckets():
  keys = acl.BucketAcl.query().iter(keys_only=True)
  for key in keys:
    yield key.id()


def send_all_metrics():
  buf = metrics.Buffer()
  futures = []
  for b in iter_all_buckets():
    futures.extend([
        send_build_status_metric(
            buf, b, METRIC_PENDING_BUILDS, model.BuildStatus.SCHEDULED),
        send_build_status_metric(
            buf, b, METRIC_RUNNING_BUILDS, model.BuildStatus.STARTED),
    ])
  ndb.Future.wait_all(futures)
  buf.flush()
  for f in futures:
    f.check_success()
