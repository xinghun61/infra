# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Example containing all metrics, all with descriptions.

Tests assume the description contains the name of the metric, without
the prefix.
"""
from infra_libs import ts_mon

metric1 = ts_mon.BooleanMetric('/my/metric1', description='metric1')
metric2 = ts_mon.CounterMetric('/my/metric2', description='metric2')
metric3 = ts_mon.CumulativeDistributionMetric('/my/metric3',
                                              description='metric3')
metric4 = ts_mon.CumulativeMetric('/my/metric4', description='metric4')


# Add a wrapping function to check that we're finding those as well.
def nice_function():
  # Checking that we really ignore comments.
  # ts_mon.FloatMetric('/my/metric11', description='metric11')

  metric6 = ts_mon.FloatMetric('/my/metric6', description='metric6')
  metric7 = ts_mon.GaugeMetric('/my/metric7', description='metric7')
  metric8 = ts_mon.NonCumulativeDistributionMetric('/my/metric8',
                                                   description='metric8')
  metric9 = ts_mon.StringMetric('/my/metric9', description='metric9')
  # Use all variables to silence pylint.
  print metric6, metric7, metric8, metric9


# Some unrelated code to add noise
if __name__ == '__main__':
  pass
