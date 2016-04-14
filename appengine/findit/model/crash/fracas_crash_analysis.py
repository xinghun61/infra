# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib

from google.appengine.ext import ndb

from model.crash.crash_analysis import CrashAnalysis


class FracasCrashAnalysis(CrashAnalysis):
  """Represents an analysis of a Chrome crash."""
  # Data of crash per million page loads for each Chrome version.
  versions_to_cpm = ndb.JsonProperty(indexed=False)

  def Reset(self):
    super(FracasCrashAnalysis, self).Reset()
    self.versions_to_cpm = None

  @ndb.ComputedProperty
  def channel(self):
    return self.key.pairs()[0][1].split('/')[0]

  @ndb.ComputedProperty
  def platform(self):
    return self.key.pairs()[0][1].split('/')[1]

  @staticmethod
  def _CreateKey(channel, platform, signature):
    # Use sha1 hex digest of signature to avoid char conflict with '/'.
    return ndb.Key('FracasCrashAnalysis', '%s/%s/%s' % (
        channel, platform, hashlib.sha1(signature).hexdigest()))

  @classmethod
  def Get(cls, channel, platform, signature):
    return cls._CreateKey(channel, platform, signature).get()

  @classmethod
  def Create(cls, channel, platform, signature):
    analysis = cls(key=cls._CreateKey(channel, platform, signature))
    analysis.signature = signature
    return analysis
