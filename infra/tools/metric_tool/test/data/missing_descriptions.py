# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Example containing metrics with and without descriptions."""
from infra_libs import ts_mon

metric1 = ts_mon.BooleanMetric('/my/metric1', description='metric1')
metric2 = ts_mon.CounterMetric('/my/metric2', description='metric2')
metric3 = ts_mon.CumulativeDistributionMetric('/my/metric3',
                                              description='metric3')
metric4 = ts_mon.CumulativeMetric('/my/metric4', description='metric4')

metric6 = ts_mon.FloatMetric('/my/metric6')
metric7 = ts_mon.GaugeMetric('/my/metric7')
metric8 = ts_mon.CumulativeDistributionMetric('/my/metric8')
metric9 = ts_mon.NonCumulativeDistributionMetric('/my/metric9')
metric10 = ts_mon.StringMetric('/my/metric10')
