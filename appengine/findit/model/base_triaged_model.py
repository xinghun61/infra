# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from gae_libs import appengine_util
from libs import time_util
from model import triage_status


class TriageResult(ndb.Model):
  # The user who updated this result.
  user_name = ndb.StringProperty(default=None, indexed=False)

  # The time this triage result was determined.
  triaged_time = ndb.DateTimeProperty(indexed=False, auto_now_add=True)

  # The result of the analysis as correct or not. If the analysis is not yet
  # completed, then the value should be None. Other traige result codes are up
  # to the child class to set.
  triage_result = ndb.IntegerProperty(default=None, indexed=True)

  # The version of findit that generated this result. Should primarily be
  # relevant for entities that are not versioned.
  findit_version = ndb.StringProperty(default=None, indexed=False)

  # The version number of the entity that is being triaged. Should primarily be
  # relevant for versioned entites.
  version_number = ndb.IntegerProperty(default=None, indexed=False)

  # Other information about this result. For example, cl_info for suspected CLs
  # which may contain repo/revision or the suspected range for a flake analysis.
  suspect_info = ndb.JsonProperty(default=None, indexed=False)


class TriagedModel(ndb.Model):
  """The parent class for models that can have triage results."""

  def UpdateTriageResult(self, triage_result, suspect_info, user_name,
                         version_number=None):
    result = TriageResult()
    result.user_name = user_name
    result.triage_result = triage_result
    result.findit_version = appengine_util.GetCurrentVersion()
    result.version_number = version_number
    result.suspect_info = suspect_info
    self.triage_history.append(result)

  def GetTriageHistory(self):
    # Gets the triage history of a triaged model as a list of dicts.
    triage_history = []
    for triage_record in self.triage_history:
      triage_history.append({
          'triaged_time': time_util.FormatDatetime(triage_record.triaged_time),
          'user_name': triage_record.user_name,
          'suspect_info': triage_record.suspect_info,
          'triage_result': (
              triage_status.TRIAGE_STATUS_TO_DESCRIPTION.get(
                  triage_record.triage_result)),
          'findit_version': triage_record.findit_version,
          'version_number': triage_record.version_number
      })

    return triage_history

  # Record the triage result history.
  triage_history = ndb.LocalStructuredProperty(
      TriageResult, repeated=True, indexed=False, compressed=True)
