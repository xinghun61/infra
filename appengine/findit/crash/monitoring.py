# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import gae_ts_mon

found_suspects = gae_ts_mon.CounterMetric(
    'predator/found_suspects',
    description=('Metric monitoring whether Predator found CLs for the'
                 'crash report. This metric has fields like:'
                 '{found_suspects: True/False,'
                 ' client_id: Cracas/Fracas/Clusterfuzz}'))

has_regression_range = gae_ts_mon.CounterMetric(
    'predator/has_regression_range',
    description=('Metric monitoring whether Predator has regression range '
                 'for the crash report. This metric has fields like:'
                 '{has_regression_range: True/False,'
                 ' client_id: Cracas/Fracas/Clusterfuzz}'))

found_components = gae_ts_mon.CounterMetric(
    'predator/found_components',
    description=('Metric monitoring whether Predator found components for the'
                 'crash report. This metric has fields like:'
                 '{found_components: True/False,'
                 ' client_id: Cracas/Fracas/Clusterfuzz}'))
