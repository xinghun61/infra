# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging

from components import auth
from components import utils
from google.appengine.api import urlfetch
from google.appengine.ext import ndb
from testing_utils import testing
import apiclient
import mock

from test import acl_test
import acl
import metrics
import model


class MerticsTest(testing.AppengineTestCase):
  def setUp(self):
    super(MerticsTest, self).setUp()
    self.mock(utils, 'utcnow', lambda: datetime.datetime(2015, 1, 1))

  def mock_tasklet(self, result=None, exception=None):
    future = ndb.Future()
    if exception:
      future.set_exception(exception)
    else:
      if result is None:
        result = mock.Mock()
      future.set_result(result)
    return mock.Mock(return_value=future)

  def test_call_mon_api(self):
    get_context = mock.Mock()
    self.mock(ndb, 'get_context', get_context)
    fetch_res = mock.Mock(
        content='{"a": 1}',
        status_code=200,
    )
    get_context.return_value.urlfetch = self.mock_tasklet(fetch_res)
    res = metrics.call_mon_api('GET', 'metricDescriptors')
    self.assertEqual(res, {'a': 1})

    metrics.call_mon_api('POST', 'metricDescriptors', body={'x': 1})

  def test_call_mon_api_fails(self):
    get_context = mock.Mock()
    self.mock(ndb, 'get_context', get_context)
    fetch_res = mock.Mock(
        content='Transient error',
        status_code=500,
    )
    get_context.return_value.urlfetch = self.mock_tasklet(fetch_res)
    with self.assertRaises(metrics.Error):
      metrics.call_mon_api('GET', 'metricDescriptors')

  def test_call_mon_api_deadline_exceeded(self):
    def raise_deadline_exceeded(*_, **__):
      raise urlfetch.DeadlineExceededError()
    get_context = mock.Mock()
    self.mock(ndb, 'get_context', get_context)
    get_context.return_value.urlfetch.side_effect = raise_deadline_exceeded

    with self.assertRaises(urlfetch.DeadlineExceededError):
      metrics.call_mon_api('GET', 'metricDescriptors')

  def test_send_build_status_metric(self):
    call_mon_api_async = self.mock_tasklet()
    self.mock(metrics, 'call_mon_api_async', call_mon_api_async)

    ndb.put_multi([
        model.Build(bucket='chromium', status=model.BuildStatus.SCHEDULED),
        model.Build(bucket='chromium', status=model.BuildStatus.SCHEDULED),
        model.Build(bucket='v8', status=model.BuildStatus.SCHEDULED),
        model.Build(bucket='chromium', status=model.BuildStatus.STARTED),
    ])
    future = metrics.send_build_status_metric(
        'chromium', metrics.METRIC_PENDING_BUILDS, model.BuildStatus.SCHEDULED)
    future.get_result()
    call_mon_api_async.assert_called_once_with(
        'POST', 'timeseries:write',
        {
            'timeseries': [{
                'timeseriesDesc': {
                    'metric': metrics.METRIC_PENDING_BUILDS['name'],
                    'labels': {
                        metrics.LABEL_BUCKET['key']: 'chromium',
                    },
                  },
                  'point': {
                      'start': '2015-01-01T00:00:00Z',
                      'end': '2015-01-01T00:00:00Z',
                      'int64Value': 2,
                  },
            }],
        })

  def test_send_build_status_metric_fails(self):
    call_mon_api_async = self.mock_tasklet(exception=ValueError())
    self.mock(metrics, 'call_mon_api_async', call_mon_api_async)
    self.mock(logging, 'exception', mock.Mock())

    future = metrics.send_build_status_metric(
        'chromium', metrics.METRIC_PENDING_BUILDS, model.BuildStatus.SCHEDULED)
    future.get_result()

    self.assertTrue(logging.exception.called)

  def test_send_all_metrics(self):
    acl.BucketAcl(
        id='x',
        rules=[],
        modified_by=auth.Identity('user', 'x@x.x'),
        modified_time=utils.utcnow(),
    ).put()
    self.mock(metrics, 'send_build_status_metric', mock.Mock())

    metrics.send_all_metrics()

    metrics.send_build_status_metric.assert_any_call(
        'x', metrics.METRIC_PENDING_BUILDS, model.BuildStatus.SCHEDULED)
    metrics.send_build_status_metric.assert_any_call(
        'x', metrics.METRIC_RUNNING_BUILDS, model.BuildStatus.STARTED)

  def test_ensure_metrics_exist(self):
    self.mock(metrics, 'call_mon_api', mock.Mock())
    list_mertics_response = {
        'metrics': [{
            'name': metrics.METRIC_RUNNING_BUILDS['name'],
        }],
    }
    metrics.call_mon_api.side_effect = [list_mertics_response, None]
    metrics.ensure_metrics_exist()
    metrics.call_mon_api.assert_any_call('GET', 'metricDescriptors')
    metrics.call_mon_api.assert_any_call(
        'POST', 'metricDescriptors', metrics.METRIC_PENDING_BUILDS)
