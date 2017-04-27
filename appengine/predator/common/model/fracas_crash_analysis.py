# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from analysis.type_enums import CrashClient
from common.model.chrome_crash_analysis import ChromeCrashAnalysis


class FracasCrashAnalysis(ChromeCrashAnalysis):
  """Represents an analysis of a Chrome crash on Fracas."""

  @property
  def client_id(self):  # pragma: no cover
    return CrashClient.FRACAS

  @property
  def crash_url(self):  # pragma: no cover
    return ''
