# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json

from google.appengine.ext import ndb
from google.appengine.ext.ndb import msgprop
from protorpc import messages


from appengine_module.cr_rev.endpoints_proto_datastore.ndb import EndpointsModel


class NumberingType(messages.Enum):
  COMMIT_POSITION = 1
  SVN = 2


class NumberingMap(EndpointsModel):
  numbering_type = msgprop.EnumProperty(NumberingType)
  numbering_identifier = ndb.StringProperty()
  number = ndb.IntegerProperty()
  project = ndb.StringProperty()
  repo = ndb.StringProperty()
  git_sha = ndb.StringProperty()
  redirect_url = ndb.StringProperty()

  @staticmethod
  def svn_unique_id(repo, revision):
    """Return a unique ID for a SVN numbering."""
    return json.dumps({
      'type': 'svn',
      'repo': repo,  #TODO(stip): change to 'ref' to reduce confusion.
      'revision': int(revision)
    }, sort_keys=True)

  @staticmethod
  def git_unique_id(project, repo, ref, commit_pos):
    """Return a unique ID for a git numbering."""
    return json.dumps({
      'type': 'git',
      'project': project,
      'repo': repo,
      'ref': ref,
      'commit_pos': int(commit_pos)
    }, sort_keys=True)

  @classmethod
  def unique_id(cls, number, numbering_type, repo=None, project=None, ref=None):
    """Return a unique ID, either SVN or git."""
    if numbering_type == NumberingType.SVN:
      return cls.svn_unique_id(ref, number)
    elif numbering_type == NumberingType.COMMIT_POSITION:
      return cls.git_unique_id(project, repo, ref, number)
    else:  # pragma: no cover
      raise ValueError('%s is not a valid numbering type' % numbering_type)

  @classmethod
  def get_key_by_id(
      cls, number, numbering_type, repo=None, project=None, ref=None):
    return ndb.Key(cls, cls.unique_id(number, numbering_type, repo=repo,
      project=project, ref=ref))

  def _pre_put_hook(self):
    self.key = ndb.Key(NumberingMap,
        self.unique_id(self.number, self.numbering_type, repo=self.repo,
          project=self.project, ref=self.numbering_identifier))


class Project(EndpointsModel):
  name = ndb.StringProperty()
  canonical_url_template = ndb.StringProperty(
      default='https://%(project)s.googlesource.com/')
  generated = ndb.DateTimeProperty(auto_now_add=True)
  last_scanned = ndb.DateTimeProperty()


class Repo(EndpointsModel):
  repo = ndb.StringProperty()
  project = ndb.StringProperty()
  canonical_url_template = ndb.StringProperty(
      default='https://%(project)s.googlesource.com/%(repo)s/')
  root_commit_scanned = ndb.BooleanProperty()
  first_commit = ndb.StringProperty()
  latest_commit = ndb.StringProperty()
  generated = ndb.DateTimeProperty(auto_now_add=True)
  last_scanned = ndb.DateTimeProperty()
  active = ndb.BooleanProperty()
  real = ndb.BooleanProperty()
  excluded = ndb.BooleanProperty()

  @classmethod
  def get_key_by_id(cls, project, repo):
    """Given a project and a repo, return a Repo ndb.Key()."""
    return ndb.Key(cls, cls.repo_id(project, repo))

  @staticmethod
  def repo_id(project, repo):
    """Given a project and a repo, return a unique id string."""
    return json.dumps({'project': project, 'repo': repo}, sort_keys=True)

  def _pre_put_hook(self):
    self.key = ndb.Key(Repo, self.__class__.repo_id(self.project, self.repo))


class RevisionMap(EndpointsModel):
  numberings = ndb.StructuredProperty(NumberingMap, repeated=True)
  number = ndb.IntegerProperty()
  project = ndb.StringProperty()
  repo = ndb.StringProperty()
  git_sha = ndb.StringProperty()
  redirect_url = ndb.StringProperty()

  def _pre_put_hook(self):
    self.key = ndb.Key(RevisionMap, self.git_sha)


class RedirectType(messages.Enum):
  GIT_FULL = 1
  GIT_SHORT = 2
  GIT_FROM_NUMBER = 3
  RIETVELD = 4


class Redirect(EndpointsModel):
  query = ndb.StringProperty()
  redirect_type = msgprop.EnumProperty(RedirectType)
  redirect_url = ndb.StringProperty()
  project = ndb.StringProperty()
  repo = ndb.StringProperty()
  repo_url = ndb.StringProperty()
  git_sha = ndb.StringProperty()


class RepoExclusion(EndpointsModel):
  project = ndb.StringProperty()
  repo = ndb.StringProperty()


class ExcludedRepoList(EndpointsModel):
  exclusions = ndb.StructuredProperty(RepoExclusion, repeated=True)


class ProjectLagStats(EndpointsModel):
  project = ndb.StringProperty()
  total_active_repos = ndb.IntegerProperty()
  unscanned_repos = ndb.IntegerProperty()
  scanned_repos = ndb.IntegerProperty()
  repos_without_root = ndb.IntegerProperty()
  repos_with_root = ndb.IntegerProperty()
  generated = ndb.DateTimeProperty()
  p50 = ndb.FloatProperty()
  p75 = ndb.FloatProperty()
  p90 = ndb.FloatProperty()
  p95 = ndb.FloatProperty()
  p99 = ndb.FloatProperty()
  max = ndb.FloatProperty()
  min = ndb.FloatProperty()
  most_lagging_repo = ndb.StringProperty()


class ProjectLagList(EndpointsModel):
  projects = ndb.StructuredProperty(ProjectLagStats, repeated=True)
  generated = ndb.DateTimeProperty()
