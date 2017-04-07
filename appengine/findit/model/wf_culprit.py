# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from libs import analysis_status as status
from model.base_suspected_cl import BaseSuspectedCL


# Deprecated. Just keep it for legacy data. Will be deleted eventually.
class WfCulprit(BaseSuspectedCL):
  """Represents a culprit that causes a group of failures on Chromium waterfall.

  'Wf' is short for waterfall.
  """
  # The list of builds in which the culprit caused some breakage.
  builds = ndb.JsonProperty(indexed=False)

  # When the code-review of this culprit was notified.
  cr_notification_time = ndb.DateTimeProperty(indexed=True)

  # The status of code-review notification: None, RUNNING, COMPLETED, ERROR.
  cr_notification_status = ndb.IntegerProperty(indexed=True)

  @property
  def cr_notification_processed(self):
    return self.cr_notification_status in (status.COMPLETED, status.RUNNING)

  @property
  def cr_notified(self):
    return self.cr_notification_status == status.COMPLETED

  @classmethod
  def Create(cls, repo_name, revision, commit_position):  # pragma: no cover
    instance = cls(key=cls._CreateKey(repo_name, revision))
    instance.repo_name = repo_name
    instance.revision = revision
    instance.commit_position = commit_position
    instance.builds = []
    return instance
