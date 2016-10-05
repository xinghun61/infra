# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb

from common import time_util


class BaseSuspectedCL(ndb.Model):
  """Represents base information about a suspected cl."""

  # Repo or project name of the suspected CL, eg: chromium, etc.
  repo_name = ndb.StringProperty(indexed=True)

  # The Git hash revision of the suspected CL.
  revision = ndb.StringProperty(indexed=False)

  # The commit position of the suspected CL.
  # Might not be available for some repo.
  commit_position = ndb.IntegerProperty(indexed=False)

  # Time when the CL was identified as a suspect for the first time.
  identified_time = ndb.DateTimeProperty(indexed=False)

  # Time when the CL was updated.
  updated_time = ndb.DateTimeProperty(indexed=True)

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
    instance.identified_time = time_util.GetUTCNow()
    return instance

  @classmethod
  def Get(cls, repo_name, revision):  # pragma: no cover
    return cls._CreateKey(repo_name, revision).get()