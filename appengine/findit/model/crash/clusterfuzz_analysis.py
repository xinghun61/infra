# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from model.crash.crash_analysis import CrashAnalysis


class ClusterfuzzAnalysis(CrashAnalysis):
  """Represents an analysis of a Clusterfuzz crash."""
  # Customized properties for Fracas crash.
  crashed_type = ndb.StringProperty()
  crashed_address = ndb.StringProperty()
  sanitizer = ndb.StringProperty()
  job_type = ndb.StringProperty()

  def Reset(self):
    super(ClusterfuzzAnalysis, self).Reset()
    self.crashed_type = None
    self.crashed_address = None
    self.sanitizer = None
    self.job_type = None

  def Initialize(self, crash_data):
    """(Re)Initializes a CrashAnalysis ndb.Model from ``ClusterfuzzData``."""
    super(ClusterfuzzAnalysis, self).Initialize(crash_data)
    self.crashed_type = crash_data.crashed_type
    self.crashed_address = crash_data.crashed_address
    self.sanitizer = crash_data.sanitizer
    self.job_type = crash_data.job_type
