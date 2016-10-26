# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from google.appengine.ext import ndb

from crash.findit import Findit
from crash.type_enums import CrashClient

# TODO(katesonia): Implement this class.
class FinditForClusterfuzz(Findit): # pragma: no cover
  @classmethod
  def _ClientID(cls):
    return CrashClient.CLUSTERFUZZ

  def __init__(self, repository, pipeline_cls):
    super(FinditForClusterfuzz, self).__init__(repository, pipeline_cls)
    logging.info('Client %s is not supported by findit right now',
        self.client_id)
    raise NotImplementedError()

  def CreateAnalysis(self, crash_identifiers):
    raise NotImplementedError()

  def GetAnalysis(self, crash_identifiers):
    raise NotImplementedError()

  def _InitializeAnalysis(self, model, crash_data):
    super(FinditForClusterfuzz, self)._InitializeAnalysis(model, crash_data)
    raise NotImplementedError()

  @ndb.transactional
  def _NeedsNewAnalysis(self, crash_data):
    raise NotImplementedError()

  def CheckPolicy(self, crash_data):
    return crash_data

  def FindCulprit(self, model):
    raise NotImplementedError()
