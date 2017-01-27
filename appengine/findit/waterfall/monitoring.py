# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import gae_ts_mon

swarming_tasks = gae_ts_mon.CounterMetric(
    'findit/swarmingtasks', description='Swarming tasks triggered')

outgoing_http_errors = gae_ts_mon.CounterMetric(
    'findit/outgoinghttperrors',
    description='Failed http requests to various servers')

issues = gae_ts_mon.CounterMetric(
    'findit/issues', description='Bugs updated with findings')

flakes = gae_ts_mon.CounterMetric(
    'findit/flakes', description='Flakes requested or analyzed')

try_jobs = gae_ts_mon.CounterMetric(
    'findit/try-jobs', description='Try jobs triggered')

try_job_errors = gae_ts_mon.CounterMetric(
    'findit/try-job-errors', description='Try job errors encountered')
