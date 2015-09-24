# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

try:
  from infra_libs.ts_mon.common.metrics import CumulativeDistributionMetric
  from infra_libs.ts_mon.common.metrics import CounterMetric
except ImportError: # pragma: no cover
  from common.metrics import CumulativeDistributionMetric
  from common.metrics import CounterMetric

request_bytes = CumulativeDistributionMetric(
    'http/request_bytes',
    description='Bytes sent per http request (body only).')
response_bytes = CumulativeDistributionMetric(
    'http/response_bytes',
    description='Bytes received per http requests (content only).')
durations = CumulativeDistributionMetric(
    'http/durations',
    description='Time elapsed between sending a request and getting a'
                ' response (including parsing) in milliseconds.')
response_status = CounterMetric('http/response_status')


def _reset_for_testing():  # pragma: no cover
  for metric in (request_bytes, response_bytes, durations, response_status):
    metric.reset()
