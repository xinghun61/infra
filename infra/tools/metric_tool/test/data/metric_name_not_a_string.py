# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Example containing metrics whose name is set using a variable

Don't do that, it's just to make sure the parsing is robust.
"""
from infra_libs import ts_mon

metric_name = '/my/metric1'
ts_mon.BooleanMetric(metric_name, description='metric1')
