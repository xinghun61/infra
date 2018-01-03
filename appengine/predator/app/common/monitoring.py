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
