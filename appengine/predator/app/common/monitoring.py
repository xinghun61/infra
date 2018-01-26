# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import gae_ts_mon

reports_processed = gae_ts_mon.CounterMetric(
    'predator/reports_count',
    'Metric counting the number of crash reports that Predator has processed. '
    'Contains fields describing whether Predator was successful at finding a '
    'regression range, a components, or suspect changes for each report.',
    [gae_ts_mon.BooleanField('found_suspects'),
     gae_ts_mon.BooleanField('found_components'),
     gae_ts_mon.BooleanField('has_regression_range'),
     gae_ts_mon.StringField('client_id'),
     gae_ts_mon.BooleanField('success')])


wrong_cls = gae_ts_mon.GaugeMetric(
    'predator/wrong_cls',
    'Number of wrong suspected cls found by Predator per '
    'day. Contains fields describing which client this wrong cl comes from, '
    'can be clusterfuzz or cracas.',
    [gae_ts_mon.StringField('client_id')])


wrong_components = gae_ts_mon.GaugeMetric(
    'predator/wrong_components',
    'Number of wrong suspected components found by '
    'Predator per day. Contains fields describing which client this wrong cl '
    'comes from, can be clusterfuzz or cracas.',
    [gae_ts_mon.StringField('client_id')])


clusterfuzz_reports = gae_ts_mon.CounterMetric(
    'predator/clusterfuzz_reports',
    'Metric counting the number of clusterfuzz crash reports that Predator '
    'has processed. Contains fields that describe the crash',
    [gae_ts_mon.BooleanField('found_suspects'),
     gae_ts_mon.BooleanField('has_regression_range'),
     gae_ts_mon.StringField('crash_type'),
     gae_ts_mon.BooleanField('security'),
     gae_ts_mon.StringField('platform'),
     gae_ts_mon.StringField('job_type')])
