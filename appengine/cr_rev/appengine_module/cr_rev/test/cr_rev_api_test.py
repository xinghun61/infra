# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from appengine_module.testing_utils import testing
from appengine_module.cr_rev import controller
from appengine_module.cr_rev import cr_rev_api
from appengine_module.cr_rev import models
from appengine_module.cr_rev.test import model_helpers


class TestCrRevApi(testing.EndpointsTestCase):
  api_service_cls = cr_rev_api.CrRevApi

  def _make_api_call(self, funcname, params=None, status=None):
    return self.call_api(funcname, body=params, status=status)

  def test_get_routes(self):
    """Test that the endpoints webapp2 adapter works."""
    self.assertTrue(cr_rev_api.get_routes())

  def test_get_projects(self):
    """Test that all projects are listed."""
    my_project = model_helpers.create_project()
    my_project.put()

    response = self._make_api_call('get_projects')
    expected = {u'items': [
      my_project.ToMessage(),
    ]}

    resp = model_helpers.convert_items_to_protos(models.Project, response.json)
    self.assertEqual(expected, resp)

  def test_empty_repo(self):
    """Test that calling repo.list yields an empty list with no data."""
    response = self._make_api_call('get_repos')
    expected = {}
    self.assertEqual(expected, response.json)

  def test_repo_list(self):
    """Test that calling repo.list yields an list of scanned repos."""
    my_repo = model_helpers.create_repo()
    my_repo.put()
    second_repo = model_helpers.create_repo()
    second_repo.repo = 'cooler_src'
    second_repo.project = 'the_best_project'
    second_repo.put()

    response = self._make_api_call('get_repos', params={
      'project': second_repo.project})

    expected = {u'items': [
      second_repo.ToMessage(),
    ]}

    resp = model_helpers.convert_items_to_protos(models.Repo, response.json)
    self.assertEqual(expected, resp)

  def test_project_scan_lag(self):
    """Test that the project_scan_lag endpoint properly calculates lag."""
    model_helpers.create_project().put()
    my_repo = model_helpers.create_repo()
    my_repo.put()

    generated_time = u'1970-01-02T00:00:00.000000'

    response = self._make_api_call('get_project_lag_list', params={
      'generated': generated_time})

    expected = {
        u'projects': [
          {u'project': my_repo.project,
            u'total_active_repos': u'1',
            u'repos_without_root': u'1',
            u'repos_with_root': u'0',
            u'scanned_repos': u'1',
            u'unscanned_repos': u'0',
            u'generated': generated_time,
            u'most_lagging_repo': u'%s:%s' % (my_repo.project, my_repo.repo),
            u'max': float(24 * 60 * 60),
            u'min': float(24 * 60 * 60),
            u'p50': float(24 * 60 * 60),
            u'p75': float(24 * 60 * 60),
            u'p90': float(24 * 60 * 60),
            u'p95': float(24 * 60 * 60),
            u'p99': float(24 * 60 * 60),
          }
        ],
        u'generated': generated_time,
    }

    self.assertEqual(expected, response.json)

  def test_excluded_repos(self):
    """Test that the list of excluded repos is correct."""
    response = self._make_api_call('get_excluded_repos')

    expected = {u'exclusions': []}

    for project, repos in controller.REPO_EXCLUSIONS.iteritems():
      for repo in repos:
        expected[u'exclusions'].append({
          u'repo': unicode(repo),
          u'project': unicode(project)
        })

    self.assertEqual(expected, response.json)

  def test_get_repo(self):
    """Test getting an explicit repository."""
    my_repo = model_helpers.create_repo()
    my_repo.put()

    response = self._make_api_call('get_repo', params={
      'project': my_repo.project, 'repo': my_repo.repo})

    expected = my_repo.ToMessage()
    resp = model_helpers.convert_json_to_model_proto(models.Repo, response.json)
    self.assertEqual(expected, resp)

  def test_get_commit(self):
    """Test getting information about a single commit."""
    my_commit = model_helpers.create_commit()
    my_commit.put()


    response = self._make_api_call('get_commit', params={
      'git_sha': my_commit.git_sha})

    expected = my_commit.ToMessage()
    resp = model_helpers.convert_json_to_model_proto(
        models.RevisionMap, response.json)
    self.assertEqual(expected, resp)

  def test_get_numberings(self):
    """Test getting a COMMIT_POSITION  or SVN numbering."""
    my_commit = model_helpers.create_commit()
    my_commit.put()
    my_numberings = model_helpers.create_numberings()

    for numbering in my_numberings:
      numbering.put()

    svn_numbering = my_numberings[0]
    git_numbering = my_numberings[1]

    response = self._make_api_call('get_numbering', params={
      'number': git_numbering.number,
      'numbering_type': 'COMMIT_POSITION',
      'project': git_numbering.project,
      'repo': git_numbering.repo,
      'numbering_identifier': git_numbering.numbering_identifier})

    expected = git_numbering.ToMessage()
    resp = model_helpers.convert_json_to_model_proto(
        models.NumberingMap, response.json)
    self.assertEqual(expected, resp)

    response = self._make_api_call('get_numbering', params={
      'number': svn_numbering.number,
      'numbering_type': 'SVN',
      'numbering_identifier': svn_numbering.numbering_identifier})

    expected = svn_numbering.ToMessage()
    resp = model_helpers.convert_json_to_model_proto(
        models.NumberingMap, response.json)
    self.assertEqual(expected, resp)

  def test_redirect_reitveld(self):
    """Test redirect handling."""
    response = self._make_api_call('get_redirect', params={
      'query': '10000000'})

    expected = {
        u'redirect_type': u'RIETVELD',
        u'redirect_url': 'https://codereview.chromium.org/10000000',
    }
    self.assertEqual(expected, response.json)

  def test_redirect_numbering(self):
    my_repo = model_helpers.create_repo()
    my_repo.put()
    my_commit = model_helpers.create_commit()
    my_commit.put()
    my_numberings = model_helpers.create_numberings()
    my_numberings[0].numbering_identifier = 'svn://svn.chromium.org/chrome'

    for numbering in my_numberings:
      numbering.put()

    response = self._make_api_call('get_redirect', params={
      'query': '100'})
    expected = {
      u'git_sha': unicode(my_commit.git_sha),
      u'repo': unicode(my_commit.repo),
      u'project': unicode(my_commit.project),
      u'redirect_url': unicode(my_commit.redirect_url),
      u'redirect_type': u'GIT_FROM_NUMBER',
      u'repo_url': u'https://cool.googlesource.com/cool_src/',
    }
    self.assertEqual(expected, response.json)

  def test_redirect_git_sha(self):
    my_repo = model_helpers.create_repo()
    my_repo.put()
    my_commit = model_helpers.create_commit()
    my_commit.put()

    response = self._make_api_call('get_redirect', params={
      'query': my_commit.git_sha})
    expected = {
      u'git_sha': unicode(my_commit.git_sha),
      u'repo': unicode(my_commit.repo),
      u'project': unicode(my_commit.project),
      u'redirect_url': unicode(my_commit.redirect_url),
      u'redirect_type': u'GIT_FULL',
      u'repo_url': u'https://cool.googlesource.com/cool_src/',
    }
    self.assertEqual(expected, response.json)

  def test_redirect_short_git_sha(self):
    response = self._make_api_call('get_redirect', params={
      'query': 'deadbeef'})
    expected = {
      u'redirect_url': unicode(
        'https://chromium.googlesource.com/chromium/src/+/deadbeef'),
      u'redirect_type': u'GIT_SHORT',
    }
    self.assertEqual(expected, response.json)

  def test_insert_project_unauthenticated(self):
    self._make_api_call('insert_project', params={
        'name': 'cool',
    }, status=401)

  def test_insert_project_not_admin(self):
    self.mock(
        cr_rev_api.endpoints, 'get_current_user', lambda: 'user@example.com')
    self.mock(cr_rev_api.oauth, 'is_current_user_admin', lambda _: False)
    self._make_api_call('insert_project', params={
        'name': 'cool',
    }, status=403)

  def test_insert_project(self):
    self.mock(
        cr_rev_api.endpoints, 'get_current_user', lambda: 'user@example.com')
    self.mock(cr_rev_api.oauth, 'is_current_user_admin', lambda _: True)
    self._make_api_call('insert_project', params={
        'name': 'cool',
    })
    projects = list(models.Project.query())
    self.assertEqual(1, len(projects))
    self.assertEqual('cool', projects[0].name)
