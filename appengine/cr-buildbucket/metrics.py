# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import time

from google.appengine.api import app_identity
from google.appengine.api import urlfetch
from google.appengine.ext import ndb

from components import decorators
from components import utils

import acl
import model


MONITORING_SCOPE = 'https://www.googleapis.com/auth/monitoring'

LABEL_PREFIX = 'custom.cloudmonitoring.googleapis.com/buildbucket/'
LABEL_BUCKET = {
    'key': LABEL_PREFIX + 'bucket',
    'description': 'Bucket',
}
METRIC_NAME_PREFIX = 'custom.cloudmonitoring.googleapis.com/buildbucket/'
METRIC_PENDING_BUILDS = {
    'name': METRIC_NAME_PREFIX + 'builds/pending',
    'description': 'Number of pending builds',
    'labels': [LABEL_BUCKET],
    'typeDescriptor': {
        'metricType': 'gauge',
        'valueType': 'int64',
    },
}
METRIC_RUNNING_BUILDS = {
    'name': METRIC_NAME_PREFIX + 'builds/running',
    'description': 'Number of running builds',
    'labels': [LABEL_BUCKET],
    'typeDescriptor': {
        'metricType': 'gauge',
        'valueType': 'int64',
    },
}

ALL_METRICS = [
    METRIC_PENDING_BUILDS,
    METRIC_RUNNING_BUILDS,
]

CLOUD_MON_ENDPOINT = (
    'https://www.googleapis.com/cloudmonitoring/v2beta2'
    '/projects/{project}/{path}')


class Error(Exception):
  pass


@ndb.tasklet
def call_mon_api_async(method, path, body=None):
  app_id = app_identity.get_application_id()
  url = CLOUD_MON_ENDPOINT.format(project=app_id, path=path)
  payload = json.dumps(body) if body is not None else None
  access_token, _ = app_identity.get_access_token([MONITORING_SCOPE])
  headers = {
      'Authorization': 'OAuth %s' % access_token,
  }
  if body:
    headers['Content-Type'] ='application/json'
  logging.debug('urlfetch request: %s %s', method, url)

  attempts = 5
  while attempts > 0:
    attempts -= 1
    try:
      res = yield ndb.get_context().urlfetch(
          url, method=method, payload=payload, headers=headers,
          follow_redirects=False, validate_certificate=True, deadline=15)
      if res.status_code < 500:
        break
    except urlfetch.DeadlineExceededError:
      if attempts == 0:
        raise
  if res.status_code >= 300:
    raise Error(
        'Unexpected status code: %s. Content: %s' %
        (res.status_code, res.content))
  raise ndb.Return(json.loads(res.content))


def call_mon_api(*args, **kwargs):
  return call_mon_api_async(*args, **kwargs).get_result()


@ndb.tasklet
@decorators.silence(urlfetch.DeadlineExceededError)
def write_timeseries_value(bucket, metric, value):
  now = utils.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
  logging.info(
      'Sending metric %s for bucket %s: %d', metric['name'], bucket, value)

  timeseries = {
    'timeseriesDesc': {
        'metric': metric['name'],
        'labels': {
            LABEL_BUCKET['key']: bucket,
        }
      },
      'point': {
          'start': now,
          'end': now,
          'int64Value': value,
      },
  }

  yield call_mon_api_async(
      'POST', 'timeseries:write', {'timeseries': [timeseries]})


@ndb.tasklet
def send_build_status_metric(bucket, metric, status):
  try:
    q = model.Build.query(
        model.Build.bucket == bucket, model.Build.status == status)
    value = yield q.count_async()
    yield write_timeseries_value(bucket, metric, value)
  except Exception:
    logging.exception('Could not sent metric: %s', metric['name'])


def iter_all_buckets():
  keys = acl.BucketAcl.query().iter(keys_only=True)
  for key in keys:
    yield key.id()


def send_all_metrics():
  futures = []
  for b in iter_all_buckets():
    futures.extend([
        send_build_status_metric(
            b, METRIC_PENDING_BUILDS, model.BuildStatus.SCHEDULED),
        send_build_status_metric(
            b, METRIC_RUNNING_BUILDS, model.BuildStatus.STARTED),
    ])
  ndb.Future.wait_all(futures)


def ensure_metrics_exist():
  existing_metrics_res = call_mon_api('GET', 'metricDescriptors')
  existing_metrics = existing_metrics_res.get('metrics', [])
  existing_metric_names = set(m['name'] for m in existing_metrics)

  for metric in ALL_METRICS:
    if metric['name'] not in existing_metric_names:
      logging.info('Creating metric: %s', metric['name'])
      call_mon_api('POST', 'metricDescriptors', metric)
