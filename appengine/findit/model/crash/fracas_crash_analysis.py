# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib
import json

from google.appengine.ext import ndb

from model.crash.crash_analysis import CrashAnalysis


class FracasCrashAnalysis(CrashAnalysis):
  """Represents an analysis of a Chrome crash."""
  # Customized properties for Fracas crash.
  historic_metadata = ndb.JsonProperty(indexed=False)
  channel = ndb.StringProperty(indexed=False)

  def Reset(self):
    super(FracasCrashAnalysis, self).Reset()
    self.historic_metadata = None
    self.channel = None

  @staticmethod
  def _CreateKey(crash_identifiers):
    return ndb.Key('FracasCrashAnalysis', hashlib.sha1(
        json.dumps(crash_identifiers, sort_keys=True)).hexdigest())

  @classmethod
  def Get(cls, crash_identifiers):
    return cls._CreateKey(crash_identifiers).get()

  @classmethod
  def Create(cls, crash_identifiers):
    analysis = cls(key=cls._CreateKey(crash_identifiers))
    return analysis
