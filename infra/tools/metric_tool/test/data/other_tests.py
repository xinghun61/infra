# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This file is meant to exercise weird cases in metric_tool.py"""

import infra_libs

def nice_function():
  # Calling of function as an attribute which is not a *Metric()
  infra_libs.read_json_as_utf8()

  # Wrong type passed to 'description'
  infra_libs.ts_mon.BooleanMetric('/my/metric', description=1)

def other_function():
  # Function call that is not a metric instantiation.
  nice_function()
