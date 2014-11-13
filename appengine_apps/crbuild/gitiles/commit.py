# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Defines GitilesCommit, a Git commit served from a Gitiles server."""

import re

from google.appengine.ext import ndb

from gitiles.client import GitilesClient
from util import RegexIdMixin


class GitContributor(ndb.Model):
  """A model for git commit author or committer.

  Used as a structured property.
  """
  name = ndb.StringProperty(indexed=False)
  email = ndb.StringProperty()
  time = ndb.DateTimeProperty(indexed=False)

  @classmethod
  def from_client_contributor(cls, contributor):
    """Converts from gitiles.client.GitContributor."""
    if contributor is None:
      return None
    return cls(
        name=contributor.name,
        email=contributor.email,
        time=contributor.time,
    )


class GitilesCommit(ndb.Model, RegexIdMixin):
  """GitilesCommit is a Git commit hosted on a Gitiles server.

  The entity is immutable. It should not be modified.

  Entity key:
    Matches pattern "gitiles~<hostname>~<project>~<revision>". No parents.

  Attributes:
    hostname (str): hostname of the Gitiles server where the commit is hosted.
      Stored as a part of key.
    project (str): Gitiles project that the commit belongs to. Stored as a part
      of key.
    revision (str): commit sha. Stored as a part of key.
    author (GitContributor): the person who originally wrote the code.
    committer (GitContributor): the person who committed the code.
    viewable_url (str): points out to a Gitiles commit page. Not stored.
    repo_url (str): points out to a Gitiles project page. Not stored.
  """

  REVISION_REGEX = re.compile('[a-f0-9]{40}')
  # Entity id pattern is enforced by mixing in RegexIdMixin.
  ID_REGEX = re.compile(r'gitiles~([^~]+)~([^~]+)~([a-f0-9]{40})')

  message = ndb.TextProperty()
  author = ndb.StructuredProperty(GitContributor, indexed=False)
  committer = ndb.StructuredProperty(GitContributor)

  @property
  def hostname(self):
    return self.get_key_component(0)

  @property
  def project(self):
    return self.get_key_component(1)

  @property
  def revision(self):
    return self.get_key_component(2)

  @property
  def repo_url(self):
    return 'https://%s/%s' % (self.hostname, self.project)

  @property
  def viewable_url(self):
    return '%s/+/%s' % (self.repo_url, self.revision)

  @classmethod
  def make_id(cls, hostname, project, revision):
    """Generates an entity id."""
    assert hostname, 'Hostname is empty'
    assert project, 'Project is empty'
    assert revision, 'Revision is empty'
    assert cls.REVISION_REGEX.match(revision), ('Revision is malformed: %s' %
                                                revision)
    return 'gitiles~%s~%s~%s' % (hostname, project, revision)

  def guess_gerrit_hostname(self):
    """Tries to guess Gerrit hostname."""
    parts = self.host.split('.')
    parts[0] += '-review'
    return '.'.join(parts)

  @classmethod
  def fetch(cls, hostname, project, revision,
            client_factory=None):
    """Gets or creates a GitilesCommit identified by hostname, project and sha.

    If GitilesCommit does not exist, fetch fetches commit info from Gitiles
    server. If commit is not found on the server, None is returned.
    """
    client_factory = client_factory or GitilesClient
    entity_id = cls.make_id(hostname, project, revision)
    commit = cls.get_by_id(entity_id)
    if commit is not None:
      return commit

    client = client_factory(hostname)
    commit = client.get_commit(project, revision)
    if not commit:
      return None

    return cls.get_or_insert(
        entity_id,
        author=GitContributor.from_client_contributor(commit.author),
        committer=GitContributor.from_client_contributor(commit.committer),
        message=commit.message,
    )
