# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.appengine.ext import ndb


class GitilesCommit(ndb.Model):
  """A class for a gitiles commit."""

  @classmethod
  def _CreateKey(cls, gitiles_host, gitiles_project, gitiles_ref, gitiles_id):
    return ndb.Key(
        cls.__name__, '{}/{}/{}/{}'.format(gitiles_host, gitiles_project,
                                           gitiles_ref, gitiles_id))

  @classmethod
  def Get(cls, gitiles_host, gitiles_project, gitiles_ref, gitiles_id):
    return cls._CreateKey(gitiles_host, gitiles_project, gitiles_ref,
                          gitiles_id).get()

  @classmethod
  def Create(cls, gitiles_host, gitiles_project, gitiles_ref, gitiles_id,
             commit_position):
    """Creates an entity for a commit."""
    return cls(
        key=cls._CreateKey(gitiles_host, gitiles_project, gitiles_ref,
                           gitiles_id),
        gitiles_host=gitiles_host,
        gitiles_project=gitiles_project,
        gitiles_ref=gitiles_ref,
        gitiles_id=gitiles_id,
        commit_position=commit_position)

  # Gitiles hostname, e.g. 'chromium.googlesource.com'.
  gitiles_host = ndb.StringProperty(required=True)

  # Project name the commit belongs to, e.g. 'chromium/src'.
  gitiles_project = ndb.StringProperty(required=True)

  # Associated git ref of the commit, e.g. 'refs/heads/master'.
  # NOT a branch name: must start with 'refs/'.
  # If not specified when query build, default to 'refs/heads/master'.
  gitiles_ref = ndb.StringProperty(required=True)

  # SHA1 of the change.
  # May be called as 'revision' or 'git_hash' somewhere else.
  gitiles_id = ndb.StringProperty(required=True)

  # Integer identifier of a commit, required to sort commits.
  commit_position = ndb.IntegerProperty(required=True)


class Hint(ndb.Model):
  """Describes a hint produced by heuristic analysis and its score.

  I.e. A fact about a commit that makes it a suspect.
  """

  # A short, human-readable string that concisely describes a fact about the
  # suspect. e.g. 'add a/b/x.cc'
  content = ndb.StringProperty(indexed=False)

  # A score value for the hint, where a higher score means a stronger signal
  # that the suspect is indeed responsible for a given failure.
  score = ndb.IntegerProperty(indexed=False)


class Suspect(GitilesCommit):
  """Identifies a commit that is suspected of being a culprit for a failure."""

  # Facts about this commit that make it a suspect.
  hints = ndb.StructuredProperty(Hint, repeated=True)

  @property
  def score(self):
    return sum(h.score for h in self.hints)

  @classmethod
  def GetOrCreate(cls,
                  gitiles_host,
                  gitiles_project,
                  gitiles_ref,
                  gitiles_id,
                  commit_position=None,
                  hints=None):
    """Gets or Creates a Suspect entity.

    This also updates the entity if needed.
    """
    updated = False
    suspect = cls.Get(gitiles_host, gitiles_project, gitiles_ref, gitiles_id)
    if not suspect:
      suspect = cls.Create(gitiles_host, gitiles_project, gitiles_ref,
                           gitiles_id, commit_position)
      updated = True

    if hints:
      suspect.hints = suspect.hints or []
      for content, score in hints.iteritems():
        new_hint = Hint(content=content, score=score)
        if new_hint not in suspect.hints:
          suspect.hints.append(new_hint)
          updated = True

    if updated:
      suspect.put()
    return suspect


class Culprit(GitilesCommit):
  """Base class for a suspected or culprit commit."""
  # Urlsafe_keys to atom failures this culprit is responsible for.
  # Uses urlsafe_keys so that it can accept both compile and test failures.
  failure_urlsafe_keys = ndb.StringProperty(repeated=True)


  @classmethod
  # pylint: disable=arguments-differ
  def Create(cls,
             gitiles_host,
             gitiles_project,
             gitiles_ref,
             gitiles_id,
             commit_position,
             failure_urlsafe_keys=None):
    """Creates an entity for a culprit."""
    return cls(
        key=cls._CreateKey(gitiles_host, gitiles_project, gitiles_ref,
                           gitiles_id),
        gitiles_host=gitiles_host,
        gitiles_project=gitiles_project,
        gitiles_ref=gitiles_ref,
        gitiles_id=gitiles_id,
        commit_position=commit_position,
        failure_urlsafe_keys=failure_urlsafe_keys or [])

  @classmethod
  def GetOrCreate(cls,
                  gitiles_host,
                  gitiles_project,
                  gitiles_ref,
                  gitiles_id,
                  commit_position=None,
                  failure_urlsafe_keys=None):
    """Gets or Creates a Culprit entity.

    If failure_urlsafe_keys provided, update the culprit as well.
    """
    updated = False
    culprit = cls.Get(gitiles_host, gitiles_project, gitiles_ref, gitiles_id)
    if not culprit:
      culprit = cls.Create(gitiles_host, gitiles_project, gitiles_ref,
                           gitiles_id, commit_position)
      updated = True

    if failure_urlsafe_keys:
      culprit.failure_urlsafe_keys = list(
          set(culprit.failure_urlsafe_keys) | set(failure_urlsafe_keys))
      updated = True

    if updated:
      culprit.put()
    return culprit
