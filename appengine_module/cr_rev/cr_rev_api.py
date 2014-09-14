# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import endpoints
from google.appengine.ext import ndb
from protorpc import remote

from appengine_module.cr_rev import controller
from appengine_module.cr_rev import models

# pylint: disable=R0201,C0322

package = 'CrRev'


### Api methods.

@endpoints.api(name='crrev', version='v1')
class CrRevApi(remote.Service):
  """CrRev API v1."""

  @models.Project.query_method(path='projects', name='projects.list',
      query_fields=('limit', 'pageToken',))
  def get_projects(self, query):
    """List all scanned projects."""
    return query

  @models.Repo.query_method(path='repos', name='repos.list',
    query_fields=('limit', 'project', 'pageToken'))
  def get_repos(self, query):
    """List all scanned repositories for a project."""
    return query

  @models.Repo.method(request_fields=('project', 'repo'),
                      path='repos/{project}/{repo}', http_method='GET',
                      name='repo.get')
  def get_repo(self, repo):
    """Return information about a repository.

    parameters:
      project:  the googlecode project the repo is under.
      repo: the repository name.

    return values:
      repo:  the repository name.
      project:  the googlecode project the repo resides under.
      canonical_url_template:  the URL template used to construct the repo's URL
      root_commit_scanned:  if the root commit has been found, indicating
                            the repo has been fully scanned.
      first_commit:  the earliest commit in the repository.
      latest_commit:  the last commit seen in the repository.
      generated:  when the repository was first found under the project.
      last_scanned:  the last time a successful scan of the repository occurred.
      active:  whether the repository is actively served or merely archived.
      real:  whether the repository contains commits.
      excluded:  whether the repository has been excluded from scanning.
    """
    repo_obj = models.Repo.get_key_by_id(repo.project, repo.repo).get()
    if not repo_obj:
      raise endpoints.NotFoundException('repo not found.')  # pragma: no cover

    repo_obj.excluded = repo_obj.repo in controller.REPO_EXCLUSIONS.get(
        repo.project, [])

    return repo_obj

  @models.RevisionMap.method(request_fields=('git_sha',),
                      path='commit/{git_sha}', http_method='GET',
                      name='commit.get')
  def get_commit(self, commit):
    """Get information about a specific git sha.

    parameters:
      git_sha:  the full git sha to request information about.

    return values:
      numberings:  any subversion or git commit position numbers associated with
                   the commit.
      number:  the canonical number for this commit.
      project:  the googlecode project which the commit is under.
      repo:  the repository the commit is in.
      git_sha:  the full git sha.
      redirect_url:  the canonical googlecode URL for this commit.
    """
    commit_key = ndb.Key(models.RevisionMap, commit.git_sha)
    commit_obj = commit_key.get()
    if not commit_obj:
      raise endpoints.NotFoundException('commit not found.')  # pragma: no cover
    return commit_obj


  @models.NumberingMap.method(
      request_fields=('number', 'numbering_type', 'project', 'repo',
        'numbering_identifier'),
      http_method='GET', name='numbering.get')
  def get_numbering(self, numbering):
    """Look up a specific git commit position or svn revision number.

    parameters:
      numbering_type:  whether this is a git commit position or svn revision.
      project:  the project the commit is in (only needed for git).
      repo:  the repository the commit it in (only needed for git).
      numbering_identifier:  git ref (refs/heads/master) for commit position,
                             svn URL (svn://svn.chromium.org/chrome) for svn.
      number:  the number to look up

    return values:
      number:  the number looked up
      numbering_type:  whether this is a git commit position or svn revision
      numbering_identifier:  git ref (refs/heads/master) for commit position,
                             svn URL (svn://svn.chromium.org/chrome) for svn.
      project:  the googlecode project the repository is under.
      repo:  the repository the commit is in.
      git_sha:  the git sha of the referenced commit.
      redirect_url:  the googlecode URL for the git sha.
    """
    numbering_obj = models.NumberingMap.get_key_by_id(
        numbering.number, numbering.numbering_type, repo=numbering.repo,
        project=numbering.project, ref=numbering.numbering_identifier).get()
    if not numbering_obj:
      raise endpoints.NotFoundException('commit not found.')  # pragma: no cover
    return numbering_obj


  @models.Redirect.method(request_fields=('query',),
                      path='redirect/{query}', http_method='GET',
                      name='redirect.get')
  def get_redirect(self, redirect):
    """Performs a 4-way redirect based on a query string.

    parameters:
      query:  a svn revision / git commit position, full git sha, short git sha,
              or a rietveld issue number.

    return values:
      query: the query specified.
      redirect_type:  whether this is a full git sha, short git sha, numbering,
                      or rietveld issue.
      redirect_url:  where to redirect the user.

      ---- the following only appear for full git shas and numbering redirects
      project:  the googlecode project the repository is under.
      repo:  the repository the commit it in.
      repo_url:  the url to the repo (useful for constructing range queries).
      git_sha:  the git sha of the commit.
    """
    redirect = controller.calculate_redirect(redirect.query)
    if not redirect:
      raise endpoints.NotFoundException('commit not found.')  # pragma: no cover
    return redirect


  @models.ExcludedRepoList.method(request_fields=(),
                      path='excluded_repos', http_method='GET',
                      name='excluded_repos.get')
  def get_excluded_repos(self, _request):
    """Gets the list of repositories excluded from the commit scan."""
    exclusions = []
    for project, repos in controller.REPO_EXCLUSIONS.iteritems():
      for repo in repos:
        exclusions.append(models.RepoExclusion(
          project=project,
          repo=repo
        ))
    return models.ExcludedRepoList(exclusions=exclusions)


  @models.ProjectLagList.method(request_fields=('generated',),
      path='project_scan_lag', http_method='GET',
      name='project_scan_lag.get')
  def get_project_lag_list(self, request):
    """Calculates per-project repository scanning lag.

    Per-project, returns:
      project:  the googlecode project
      total_active_repos:  all active repos under the project
      unscanned_repos:  the number of repositories which have not yet been
                        scanned.
      scanned_repos:  the number of repositories which have at least been
                      partially scanned.
      repos_without_root:  the number of repositories which have not yet been
                           fully scanned.
      repos_with_root:  the number of repositories which have been fully
                        scanned.
      generated:  when the statistic was generated.
      p50-99: 50th, 75th, 90th, 95th, and 99th percentile seconds since
              repositories were last scanned.
      min, max:  minimum/maximum seconds since a repository was last scanned.
      most_lagging_repo:  the project:repo that has the most scan lag.
    """
    return controller.calculate_lag_stats(generated=request.generated)



APPLICATION = endpoints.api_server([CrRevApi])
