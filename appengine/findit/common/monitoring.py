# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import gae_ts_mon

swarming_tasks = gae_ts_mon.CounterMetric(
    'findit/swarmingtasks', 'Swarming tasks triggered',
    [gae_ts_mon.StringField('category'),
     gae_ts_mon.StringField('operation')])

outgoing_http_errors = gae_ts_mon.CounterMetric(
    'findit/outgoinghttperrors', 'Failed http requests to various servers',
    [gae_ts_mon.StringField('host'),
     gae_ts_mon.StringField('exception')])

outgoing_http_statuses = gae_ts_mon.CounterMetric(
    'findit/outgoinghttpstatuses', 'Http requests to external services',
    [gae_ts_mon.StringField('host'),
     gae_ts_mon.StringField('status_code')])

issues = gae_ts_mon.CounterMetric(
    'findit/issues', 'Bugs updated with findings',
    [gae_ts_mon.StringField('category'),
     gae_ts_mon.StringField('operation')])

flakes = gae_ts_mon.CounterMetric('findit/flakes',
                                  'Flakes requested or analyzed', [
                                      gae_ts_mon.StringField('source'),
                                      gae_ts_mon.StringField('operation'),
                                      gae_ts_mon.StringField('trigger')
                                  ])

try_jobs = gae_ts_mon.CounterMetric('findit/try-jobs', 'Try jobs triggered', [
    gae_ts_mon.StringField('operation'),
    gae_ts_mon.StringField('type'),
    gae_ts_mon.StringField('master_name'),
    gae_ts_mon.StringField('builder_name')
])

try_job_errors = gae_ts_mon.CounterMetric(
    'findit/try-job-errors', 'Try job errors encountered', [
        gae_ts_mon.StringField('error'),
        gae_ts_mon.IntegerField('type'),
        gae_ts_mon.StringField('master_name'),
        gae_ts_mon.StringField('builder_name')
    ])

analysis_durations = gae_ts_mon.CumulativeDistributionMetric(
    'findit/analysis-durations', 'Durations of analyses performed', [
        gae_ts_mon.StringField('type'),
        gae_ts_mon.StringField('result'),
    ])

culprit_found = gae_ts_mon.CounterMetric(
    'findit/culprits',
    'Culprits identified by findit',
    [
        gae_ts_mon.StringField('type'),
        # Valid values:
        #   revert_created, revert_committed, revert_confirmed,
        #   revert_status_error, commit_error, culprit_notified.
        gae_ts_mon.StringField('action_taken')
    ])

flake_analyses = gae_ts_mon.CounterMetric(
    'findit/flake-analyses', 'Flake analyses completed by findit', [
        gae_ts_mon.StringField('result'),
        gae_ts_mon.StringField('action_taken'),
        gae_ts_mon.StringField('reason'),
    ])
