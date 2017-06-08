# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from analysis.crash_data import CrashData

# TODO(cweakliam): Rename CrashData to something more generic now that Predator
# deals with regressions as well as crashes

# TODO(cweakliam): This is currently just a skeleton. Implementation will come
# later.
class UMASamplingProfilerData(CrashData):
  """Data about a regression from UMA Sampling Profiler.

  Properties:
      ...
  """

  def __init__(self, regression_data):
    """
    Args:
      regression_data (dict): Dicts sent through Pub/Sub by UMA Sampling
      Profiler.
    """
    super(UMASamplingProfilerData, self).__init__(regression_data)

  @property
  def stacktrace(self):
    """Parses stacktrace and returns parsed ``Stacktrace`` object."""
    raise NotImplementedError()

  @property
  def regression_range(self):
    raise NotImplementedError()

  @property
  def dependencies(self):
    raise NotImplementedError()

  @property
  def dependency_rolls(self):
    raise NotImplementedError()

  @property
  def identifiers(self):
    raise NotImplementedError()
