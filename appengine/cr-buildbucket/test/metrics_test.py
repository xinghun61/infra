# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging

from google.appengine.api import urlfetch
from google.appengine.ext import ndb

import apiclient
import mock

from components import auth
from components import metrics as metrics_component
from components import utils
from testing_utils import testing


from test import acl_test
import acl
import metrics
import model


class MerticsTest(testing.AppengineTestCase):
  def setUp(self):
    super(MerticsTest, self).setUp()
    self.mock(utils, 'utcnow', lambda: datetime.datetime(2015, 1, 1))

  def test_send_build_status_metric(self):
    buf = mock.Mock()

    ndb.put_multi([
        model.Build(bucket='chromium', status=model.BuildStatus.SCHEDULED),
        model.Build(bucket='chromium', status=model.BuildStatus.SCHEDULED),
        model.Build(bucket='v8', status=model.BuildStatus.SCHEDULED),
        model.Build(bucket='chromium', status=model.BuildStatus.STARTED),
    ])
    future = metrics.send_build_status_metric(
        buf, 'chromium', metrics.METRIC_PENDING_BUILDS,
        model.BuildStatus.SCHEDULED)
    future.get_result()
    buf.set_gauge.assert_called_once_with(
        metrics.METRIC_PENDING_BUILDS, 2,
        {metrics.LABEL_BUCKET: 'chromium'})

  def test_send_all_metrics(self):
    buf = mock.Mock()
    self.mock(metrics_component, 'Buffer', lambda: buf)

    acl.BucketAcl(
        id='x',
        rules=[],
        modified_by=auth.Identity('user', 'x@x.x'),
        modified_time=utils.utcnow(),
    ).put()
    self.mock(metrics, 'send_build_status_metric', mock.Mock())

    metrics.send_all_metrics()

    metrics.send_build_status_metric.assert_any_call(
        buf, 'x', metrics.METRIC_PENDING_BUILDS, model.BuildStatus.SCHEDULED)
    metrics.send_build_status_metric.assert_any_call(
        buf, 'x', metrics.METRIC_RUNNING_BUILDS, model.BuildStatus.STARTED)
