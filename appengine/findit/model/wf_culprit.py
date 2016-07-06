# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from model import analysis_status as status


class WfCulprit(ndb.Model):
  """Represents a culprit that causes a group of failures on Chromium waterfall.

  'Wf' is short for waterfall.
  """

  # Repo or project name of the culprit, eg: chromium, etc.
  repo_name = ndb.StringProperty(indexed=True)

  # The Git hash revision of the culprit.
  revision = ndb.StringProperty(indexed=False)

  # The commit position of the culprit. Might not be available for some repo.
  commit_position = ndb.IntegerProperty(indexed=False)

  # When the code-review of this culprit was notified.
  cr_notification_time = ndb.DateTimeProperty(indexed=True)

  # The status of code-review notification: None, RUNNING, COMPLETED, ERROR.
  cr_notification_status = ndb.IntegerProperty(indexed=True)

  # The list of builds in which the culprit caused some breakage.
  builds = ndb.JsonProperty(indexed=False)

  @property
  def project_name(self):
    return self.repo_name

  @property
  def cr_notification_processed(self):
    return self.cr_notification_status in (status.COMPLETED, status.RUNNING)

  @property
  def cr_notified(self):
    return self.cr_notification_status == status.COMPLETED

  @classmethod
  def _CreateKey(cls, repo_name, revision):  # pragma: no cover
    return ndb.Key(cls.__name__, '%s/%s' % (repo_name, revision))

  @classmethod
  def Create(cls, repo_name, revision, commit_position):  # pragma: no cover
    instance = cls(key=cls._CreateKey(repo_name, revision))
    instance.repo_name = repo_name
    instance.revision = revision
    instance.commit_position = commit_position
    instance.builds = []
    return instance

  @classmethod
  def Get(cls, repo_name, revision):  # pragma: no cover
    return cls._CreateKey(repo_name, revision).get()
