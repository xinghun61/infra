# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from model.crash.crash_analysis import CrashAnalysis


class ChromeCrashAnalysis(CrashAnalysis):  # pylint: disable=W0223
  """Represents an analysis of a Chrome Crash (Cracas or Fracas)."""
  # Customized properties for Fracas crash.
  historical_metadata = ndb.JsonProperty(indexed=False)
  channel = ndb.StringProperty(indexed=False)

  def Reset(self):
    super(ChromeCrashAnalysis, self).Reset()
    self.historical_metadata = None
    self.channel = None

  def Initialize(self, crash_data):
    """(Re)Initializes a CrashAnalysis ndb.Model from ``ChromeCrashData``."""
    super(ChromeCrashAnalysis, self).Initialize(crash_data)
    self.channel = crash_data.channel
    self.historical_metadata = crash_data.historical_metadata

  @property
  def customized_data(self):
    return {'historical_metadata': self.historical_metadata,
            'channel': self.channel}
