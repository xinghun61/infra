# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from infra_libs.ts_mon import metrics

request_bytes = metrics.DistributionMetric('http/request_bytes')
response_bytes = metrics.DistributionMetric('http/response_bytes')
durations = metrics.DistributionMetric('http/durations')
response_status = metrics.CounterMetric('http/response_status')


def _reset_for_testing():  # pragma: no cover
  for metric in (request_bytes, response_bytes, durations, response_status):
    metric.reset()
