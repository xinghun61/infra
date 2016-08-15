# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb


class WfSuspectedCL(ndb.Model):
  """Represents suspected cl that causes failures on Chromium waterfall builds.

  'Wf' is short for waterfall.
  """

  # Repo or project name of the suspected CL, eg: chromium, etc.
  repo_name = ndb.StringProperty(indexed=True)

  # The Git hash revision of the suspected CL.
  revision = ndb.StringProperty(indexed=False)

  # The commit position of the suspected CL.
  # Might not be available for some repo.
  commit_position = ndb.IntegerProperty(indexed=False)

  # The list of builds in which the suspected CL caused some breakage.
  builds = ndb.JsonProperty(indexed=False)

  # Is the suspected CL the culprit or not.
  is_culprit = ndb.BooleanProperty(indexed=True, default=None)

  # From which approach do we get this suspected CL: HEURISTIC, TRY_JOB or BOTH.
  approach = ndb.IntegerProperty(indexed=True)

  # Failure type: failure_type.COMPILE or failure_type.TEST.
  failure_type = ndb.IntegerProperty(indexed=True)

  @property
  def project_name(self):
    return self.repo_name

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
