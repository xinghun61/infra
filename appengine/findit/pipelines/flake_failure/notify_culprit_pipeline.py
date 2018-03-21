# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Sends a notification to the code review page of a flake culprit."""

from google.appengine.ext import ndb

from gae_libs.pipelines import SynchronousPipeline
from libs.structured_object import StructuredObject
from services.flake_failure import culprit_util


class NotifyCulpritInput(StructuredObject):
  # The urlsafe-key to the MasterFlakeAnalysis that identified the culprit.
  analysis_urlsafe_key = basestring


class NotifyCulpritPipeline(SynchronousPipeline):
  """Pipeline to notify the culprit code review of introducing flakiness."""
  input_type = NotifyCulpritInput
  output_type = bool

  def RunImpl(self, parameters):
    """Returns whether or not a notification was sent."""
    # This pipeline should only be called on an existing analysis with an
    # existing culprit.
    analysis = ndb.Key(urlsafe=parameters.analysis_urlsafe_key).get()
    assert analysis

    culprit_urlsafe_key = analysis.culprit_urlsafe_key
    assert culprit_urlsafe_key

    culprit = ndb.Key(urlsafe=culprit_urlsafe_key).get()
    assert culprit

    # Bail out if the identified culprit doesn't meet the minimum requirements
    # to be sent.
    if not culprit_util.ShouldNotifyCulprit(analysis):
      return False

    # Notify the culprit if it hasn't already been notified by another analysis.
    if culprit_util.PrepareCulpritForSendingNotification(culprit_urlsafe_key):
      success = culprit_util.NotifyCulprit(culprit)
      if success:
        analysis.Update(has_commented_on_cl=True)
      return success

    return False
