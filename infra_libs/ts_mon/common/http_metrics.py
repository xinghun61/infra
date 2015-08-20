# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

try:
  from infra_libs.ts_mon.common.metrics import CumulativeDistributionMetric
  from infra_libs.ts_mon.common.metrics import CounterMetric
except ImportError: # pragma: no cover
  from common.metrics import CumulativeDistributionMetric
  from common.metrics import CounterMetric

access_count = CounterMetric('gae/access/count')
request_bytes = CumulativeDistributionMetric('http/request_bytes')
response_bytes = CumulativeDistributionMetric('http/response_bytes')
durations = CumulativeDistributionMetric('http/durations')
response_status = CounterMetric('http/response_status')


def _reset_for_testing():  # pragma: no cover
  for metric in (access_count, request_bytes, response_bytes,
                 durations, response_status):
    metric.reset()
