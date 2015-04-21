# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import json

from appengine_module.testing_utils import testing

from appengine_module.cr_rev import controller
from appengine_module.cr_rev import models
from appengine_module.pipeline_utils.\
    appengine_third_party_pipeline_src_pipeline \
    import handlers
from appengine_module.pipeline_utils.\
    appengine_third_party_pipeline_src_pipeline \
    import pipeline
from appengine_module.cr_rev.test import model_helpers


class TestController(testing.AppengineTestCase):
  app_module = handlers._APP  # pylint: disable=W0212

  @staticmethod
  def _gitiles_json(data):
    """Return json-encoded data with a gitiles header."""
    return ')]}\'\n' + json.dumps(data)

  def test_get_projects(self):
    my_project = model_helpers.create_project()
    my_project.put()
    self.assertEqual([my_project], controller.get_projects())

  def test_empty_calculate_lag_stats(self):
    my_project = model_helpers.create_project()
    my_project.put()
    generated_time = datetime.datetime(1970, 01, 02)

    expected = models.ProjectLagList(
        generated=generated_time,
        projects=[
          models.ProjectLagStats(
            project=my_project.name,
            total_active_repos=0,
            repos_without_root=0,
            repos_with_root=0,
            scanned_repos=0,
            unscanned_repos=0,
            generated=generated_time,
          ),
        ],
    )

    generated = controller.calculate_lag_stats(generated=generated_time)

    self.assertEqual(expected, generated)

  def test_exclusions(self):
    project = 'test'
    repo = 'test'

    controller.REPO_EXCLUSIONS.setdefault(project, []).append(repo)
    my_repo = model_helpers.create_repo()
    my_repo.project = project
    my_repo.repo = repo
    my_repo.put()

    active_repos = controller.get_active_repos(project)
    self.assertEqual([], active_repos)


  def test_calculate_lag_stats(self):
    model_helpers.create_project().put()
    my_repo = model_helpers.create_repo()
    my_repo.put()
    second_repo = model_helpers.create_repo()
    second_repo.repo = 'cooler'
    second_repo.root_commit_scanned = True
    second_repo.last_scanned = None
    second_repo.put()

    generated_time = datetime.datetime(1970, 01, 02)
    expected = models.ProjectLagList(
        generated=generated_time,
        projects=[
          models.ProjectLagStats(
            project=my_repo.project,
            total_active_repos=2,
            repos_without_root=1,
            repos_with_root=1,
            scanned_repos=1,
            unscanned_repos=1,
            generated=generated_time,
            most_lagging_repo='%s:%s' % (my_repo.project, my_repo.repo),
            max=float(24 * 60 * 60),
            min=float(24 * 60 * 60),
            p50=float(24 * 60 * 60),
            p75=float(24 * 60 * 60),
            p90=float(24 * 60 * 60),
            p95=float(24 * 60 * 60),
            p99=float(24 * 60 * 60)
          ),
        ],
    )

    generated = controller.calculate_lag_stats(generated=generated_time)

    self.assertEqual(expected, generated)

  def test_redirect_rietveld(self):
    query = '10000000'
    generated = controller.calculate_redirect(query)

    expected = models.Redirect(
        redirect_type=models.RedirectType.RIETVELD,
        redirect_url='https://codereview.chromium.org/%s' % query,
    )

    self.assertEquals(generated, expected)

  def test_redirect_svn_numbering(self):
    my_repo = model_helpers.create_repo()
    my_repo.put()
    my_commit = model_helpers.create_commit()
    my_commit.put()
    my_numberings = model_helpers.create_numberings()
    my_numberings[0].numbering_identifier = 'svn://svn.chromium.org/chrome'

    for numbering in my_numberings:
      numbering.put()

    generated = controller.calculate_redirect('100')
    expected = models.Redirect(
        redirect_type=models.RedirectType.GIT_FROM_NUMBER,
        redirect_url=my_commit.redirect_url,
        repo=my_commit.repo,
        project=my_commit.project,
        git_sha=my_commit.git_sha,
        repo_url='https://cool.googlesource.com/cool_src/',
    )

    self.assertEqual(generated, expected)

  def test_redirect_svn_numbering_not_found(self):
    my_repo = model_helpers.create_repo()
    my_repo.put()
    my_commit = model_helpers.create_commit()
    my_commit.put()
    my_numberings = model_helpers.create_numberings()
    my_numberings[0].numbering_identifier = 'svn://svn.chromium.org/chrome'

    for numbering in my_numberings:
      numbering.put()

    generated = controller.calculate_redirect('101')
    self.assertEqual(generated, None)

  def test_redirect_git_numbering(self):
    my_repo = model_helpers.create_repo()
    my_repo.project = 'chromium'
    my_repo.repo = 'chromium/src'
    my_repo.put()
    my_commit = model_helpers.create_commit()
    my_commit.project = my_repo.project
    my_commit.repo = my_repo.repo
    my_commit.put()
    my_numberings = model_helpers.create_numberings()
    my_numberings[1].project = my_repo.project
    my_numberings[1].repo = my_repo.repo

    for numbering in my_numberings:
      numbering.put()

    generated = controller.calculate_redirect('100')
    expected = models.Redirect(
        redirect_type=models.RedirectType.GIT_FROM_NUMBER,
        redirect_url=my_commit.redirect_url,
        repo=my_commit.repo,
        project=my_commit.project,
        git_sha=my_commit.git_sha,
        repo_url='https://chromium.googlesource.com/chromium/src/',
    )

    self.assertEqual(generated, expected)

  def test_redirect_git_sha(self):
    my_repo = model_helpers.create_repo()
    my_repo.put()
    my_commit = model_helpers.create_commit()
    my_commit.put()

    generated = controller.calculate_redirect(my_commit.git_sha)
    expected = models.Redirect(
        redirect_type=models.RedirectType.GIT_FULL,
        redirect_url=my_commit.redirect_url,
        repo=my_commit.repo,
        project=my_commit.project,
        git_sha=my_commit.git_sha,
        repo_url='https://cool.googlesource.com/cool_src/',
    )

    self.assertEqual(expected, generated)

  def test_redirect_short_git_sha(self):
    query = 'deadbeef'
    generated = controller.calculate_redirect(query)

    expected = models.Redirect(
        redirect_type=models.RedirectType.GIT_SHORT,
        redirect_url='https://chromium.googlesource.com/chromium/src/+/%s' % (
          query,),
    )

    self.assertEquals(generated, expected)

  def test_redirect_unknown(self):
    query = 'not_a_git_commit'
    generated = controller.calculate_redirect(query)

    self.assertEquals(generated, None)

  def test_redirect_unknown_full_sha(self):
    query = 'deadbb0b' * 5
    generated = controller.calculate_redirect(query)

    expected = models.Redirect(
        redirect_type=models.RedirectType.GIT_SHORT,
        redirect_url='https://chromium.googlesource.com/chromium/src/+/%s' % (
          query,),
    )

    self.assertEquals(generated, expected)


  def test_redirect_over_breakpoint(self):
    """Test that requesting a number above the SVN->git switch goes to git."""
    my_repo = model_helpers.create_repo()
    my_repo.put()
    my_commit = model_helpers.create_commit()
    my_commit.put()
    my_numberings = model_helpers.create_numberings()
    my_numberings[0].numbering_identifier = 'svn://svn.chromium.org/chrome'
    my_numberings[0].number = 291562

    for numbering in my_numberings:
      numbering.put()

    generated = controller.calculate_redirect('291562')

    self.assertEqual(generated, None)

  def test_gitiles_call(self):
    gitiles_base_url = 'https://chromium.definitely_real_gitiles.com/'
    with self.mock_urlfetch() as urlfetch:
      urlfetch.register_handler(
          gitiles_base_url + '?format=json&n=1000',
          self._gitiles_json({'test': 3}))

    result = controller.make_gitiles_json_call(gitiles_base_url)
    self.assertEqual({'test': 3}, result)

  def test_gitiles_call_error(self):
    gitiles_base_url = 'https://chromium.definitely_real_gitiles.com/'
    with self.mock_urlfetch() as urlfetch:
      urlfetch.register_handler(
          gitiles_base_url + '404',
          self._gitiles_json({'test': 3}),
          status_code=404)

    with self.assertRaises(pipeline.PipelineUserError):
      controller.make_gitiles_json_call(gitiles_base_url)

  def test_gitiles_call_429(self):
    gitiles_base_url = 'https://chromium.definitely_real_gitiles.com/'
    self.mock_sleep()
    with self.mock_urlfetch() as urlfetch:
      urlfetch.register_handler(
          gitiles_base_url + '?format=json&n=1000',
          self._gitiles_json({'test': 3}),
          status_code=429)

    with self.assertRaises(pipeline.PipelineUserError):
      controller.make_gitiles_json_call(gitiles_base_url)

  def test_crawl_log(self):
    gitiles_base_url = 'https://chromium.definitely_real_gitiles.com/'
    log_data = {u'log': [
        {u'commit': u'deadbeef' * 5},
        {u'commit': u'deadbb0b' * 5},
        {u'commit': u'dead3b0b' * 5},
    ]}
    with self.mock_urlfetch() as urlfetch:
      urlfetch.register_handler(
          gitiles_base_url + '+log/master?format=json&n=1000',
          self._gitiles_json(log_data))

    commits, finished = controller.crawl_log(gitiles_base_url)
    self.assertTrue(finished)
    self.assertEqual(log_data['log'], commits)

  def test_crawl_log_until(self):
    gitiles_base_url = 'https://chromium.definitely_real_gitiles.com/'
    log_data = {u'log': [
        {u'commit': u'deadbeef' * 5},
        {u'commit': u'deadbb0b' * 5},
        {u'commit': u'dead3b0b' * 5},
    ]}
    with self.mock_urlfetch() as urlfetch:
      urlfetch.register_handler(
          gitiles_base_url + '+log/master?format=json&n=1000',
          self._gitiles_json(log_data))

    commits, finished = controller.crawl_log(
        gitiles_base_url, until=u'deadbb0b' * 5)
    self.assertTrue(finished)
    self.assertEqual(log_data['log'][0:-2], commits)

  def test_crawl_empty_log(self):
    gitiles_base_url = 'https://chromium.definitely_real_gitiles.com/'
    log_data = {u'log': []}
    with self.mock_urlfetch() as urlfetch:
      urlfetch.register_handler(
          gitiles_base_url + '+log/master?format=json&n=1000',
          self._gitiles_json(log_data))

    commits, finished = controller.crawl_log(gitiles_base_url)
    self.assertTrue(finished)
    self.assertEqual(log_data['log'], commits)

  def test_crawl_log_not_finished(self):
    gitiles_base_url = 'https://chromium.definitely_real_gitiles.com/'
    log_data = {
        u'log': [{u'commit': u'deadbeef' * 5}],
        u'next': 'beefdead' * 5,
    }
    with self.mock_urlfetch() as urlfetch:
      urlfetch.register_handler(
          gitiles_base_url + '+log/master?format=json&n=1000',
          self._gitiles_json(log_data))

    _, finished = controller.crawl_log(gitiles_base_url)
    self.assertFalse(finished)

  def test_conversion_to_commit(self):
    my_repo = model_helpers.create_repo()
    my_repo.put()
    my_commit = model_helpers.create_commit()
    my_commit.put()
    commit_json = {
        'commit': 'deadbeef' * 5,
        'message': 'Cr-Commit-Position: refs/heads/master@{#298664}',
    }

    controller.write_commits_to_db( [commit_json], 'cool', 'cool_src')
    commit = models.NumberingMap.get_key_by_id(
        298664,
        models.NumberingType.COMMIT_POSITION,
        repo='cool_src',
        project='cool',
        ref='refs/heads/master').get()
    self.assertIsNotNone(commit)

  def test_conversion_to_commit_multiple(self):
    my_repo = model_helpers.create_repo()
    my_repo.put()
    my_commit = model_helpers.create_commit()
    my_commit.put()
    commit_json = {
        'commit': 'deadbeef' * 5,
        'message': 'This is a revert\n'
                   'Original message\n'
                   'Cr-Commit-Position: refs/heads/master@{#298664}\n'
                   'More stuff\n'
                   'Cr-Commit-Position: refs/heads/master@{#298668}',
    }

    controller.write_commits_to_db( [commit_json], 'cool', 'cool_src')
    commit = models.NumberingMap.get_key_by_id(
        298668,
        models.NumberingType.COMMIT_POSITION,
        repo='cool_src',
        project='cool',
        ref='refs/heads/master').get()
    self.assertIsNotNone(commit)
    commit = models.NumberingMap.get_key_by_id(
        298664,
        models.NumberingType.COMMIT_POSITION,
        repo='cool_src',
        project='cool',
        ref='refs/heads/master').get()
    self.assertIsNone(commit)

  def test_conversion_to_svn_commit(self):
    my_repo = model_helpers.create_repo()
    my_repo.put()
    my_commit = model_helpers.create_commit()
    my_commit.put()
    commit_json = {
        'commit': 'deadbeef' * 5,
        'message': 'git-svn-id: svn://svn.chromium.org/chrome/trunk/src@200000 '
                   '0039d316-1c4b-4281-b951-d872f2087c98',
    }

    controller.write_commits_to_db( [commit_json], 'cool', 'cool_src')
    for ref in ('svn://svn.chromium.org/chrome',
                'svn://svn.chromium.org/chrome/trunk',
                'svn://svn.chromium.org/chrome/trunk/src'):
      commit = models.NumberingMap.get_key_by_id(
          200000,
          models.NumberingType.SVN,
          ref=ref).get()
      self.assertIsNotNone(commit)

  def test_conversion_to_no_commit(self):
    my_repo = model_helpers.create_repo()
    my_repo.put()
    my_commit = model_helpers.create_commit()
    my_commit.put()
    commit_json = {
        'commit': 'deadbeef' * 5,
        'message': '',
    }
    controller.write_commits_to_db( [commit_json], 'cool', 'cool_src')
    self.assertEqual(0, len(list(models.NumberingMap.query())))

  def test_project_repo_scan(self):
    my_project = model_helpers.create_project()
    my_project.put()
    base_url = my_project.canonical_url_template % {'project': my_project.name}

    repo_data = {'cool_src': {}}
    log_data = {u'log': []}

    with self.mock_urlfetch() as urlfetch:
      urlfetch.register_handler(
          base_url + '?format=json&n=1000',
          self._gitiles_json(repo_data))
      urlfetch.register_handler(
          base_url + 'cool_src/+log/master?format=json&n=1',
          self._gitiles_json(log_data))

    controller.scan_projects_for_repos()
    self.execute_queued_tasks()
    self.assertEquals(1, len(controller.get_active_repos(my_project.name)))

  def test_project_repo_scan_active(self):
    my_project = model_helpers.create_project()
    my_project.put()
    base_url = my_project.canonical_url_template % {'project': my_project.name}

    repo_data = {
      'cool_src': {},
      'cooler_src': {},
      'uncool_src': {},
    }
    log_data = {u'log': []}

    with self.mock_urlfetch() as urlfetch:
      urlfetch.register_handler(
          base_url + '?format=json&n=1000',
          self._gitiles_json(repo_data))
      urlfetch.register_handler(
          base_url + 'cool_src/+log/master?format=json&n=1',
          self._gitiles_json(log_data))
      urlfetch.register_handler(
          base_url + 'cooler_src/+log/master?format=json&n=1',
          self._gitiles_json(log_data))
      # Don't handle uncool_src, making it nonreal.

    controller.scan_projects_for_repos()
    self.execute_queued_tasks()
    self.assertEquals(2, len(controller.get_active_repos(my_project.name)))

    # Now test that active repos are inactive when they go away.
    repo_data = {
      'cooler_src': {},
    }
    with self.mock_urlfetch() as urlfetch:
      urlfetch.register_handler(
          base_url + '?format=json&n=1000',
          self._gitiles_json(repo_data))
      urlfetch.register_handler(
          base_url + 'cooler_src/+log/master?format=json&n=1',
          self._gitiles_json(log_data))

    controller.scan_projects_for_repos()
    self.execute_queued_tasks()
    self.assertEquals(1, len(controller.get_active_repos(my_project.name)))

    # And test that they can come back.
    repo_data = {
      'cool_src': {},
      'cooler_src': {},
    }
    with self.mock_urlfetch() as urlfetch:
      urlfetch.register_handler(
          base_url + '?format=json&n=1000',
          self._gitiles_json(repo_data))
      urlfetch.register_handler(
          base_url + 'cool_src/+log/master?format=json&n=1',
          self._gitiles_json(log_data))
      urlfetch.register_handler(
          base_url + 'cooler_src/+log/master?format=json&n=1',
          self._gitiles_json(log_data))
    controller.scan_projects_for_repos()
    self.execute_queued_tasks()
    self.assertEquals(2, len(controller.get_active_repos(my_project.name)))

  def test_repo_scan_for_commits(self):
    my_project = model_helpers.create_project()
    my_project.put()
    my_repo = model_helpers.create_repo()
    my_repo.put()
    base_url = my_project.canonical_url_template % {'project': my_project.name}

    log_data = {u'log': [
        {
            'commit': 'deadbeef' * 5,
            'message': 'git-svn-id: svn://svn.chromium.org/chrome/trunk/'
                       'src@200000 0039d316-1c4b-4281-b951-d872f2087c98\n'
                       'Cr-Commit-Position: refs/heads/master@{#301813}',
        },
    ]}

    with self.mock_urlfetch() as urlfetch:
      urlfetch.register_handler(
          base_url + 'cool_src/+log/master?format=json&n=1000',
          self._gitiles_json(log_data))
      urlfetch.register_handler(
          base_url + 'cool_src/+log/%s?format=json&n=1000' % ('deadbeef' * 5,),
          self._gitiles_json(log_data))
      urlfetch.register_handler(
          base_url + 'cool_src/+log/%s?format=json&n=1' % ('deadbeef' * 5,),
          self._gitiles_json(log_data))
    controller.scan_repos()
    self.execute_queued_tasks()
    self.assertEqual(1, len(list(models.RevisionMap.query())))
    self.assertEqual(
        'deadbeef' * 5,
        models.RevisionMap.query().fetch()[0].git_sha)
    self.assertEqual(4, len(list(models.NumberingMap.query())))


  def test_repo_scan_for_new_commits(self):
    """Test all forms of new commits, before and after what has been seen."""
    my_project = model_helpers.create_project()
    my_project.put()
    my_repo = model_helpers.create_repo()
    my_repo.put()
    base_url = my_project.canonical_url_template % {'project': my_project.name}

    commits = [
        {
            'commit': 'f007beef' * 5,
            'message': '',
        },
        {
            'commit': '000fbeef' * 5,
            'message': '',
        },
        {
            'commit': '700fbeef' * 5,
            'message': '',
        },
        {
            'commit': 'deadbeef' * 5,
            'message': '',
        },
        {
            'commit': 'feedbeef' * 5,
            'message': '',
        },
        {
            'commit': 'f00fbeef' * 5,
            'message': '',
        },
        {
            'commit': 'f33dbeef' * 5,
            'message': '',
        },
    ]

    log_data = {u'log': [
        commits[3],
    ]}

    with self.mock_urlfetch() as urlfetch:
      urlfetch.register_handler(
          base_url + 'cool_src/+log/master?format=json&n=1000',
          self._gitiles_json(log_data))
      urlfetch.register_handler(
          base_url + 'cool_src/+log/%s?format=json&n=1000' % ('deadbeef' * 5,),
          self._gitiles_json(log_data))
      urlfetch.register_handler(
          base_url + 'cool_src/+log/%s?format=json&n=1' % ('deadbeef' * 5,),
          self._gitiles_json(log_data))

    controller.scan_repos()
    self.execute_queued_tasks()

    log_data = {u'log': [
        commits[3],
    ]}

    with self.mock_urlfetch() as urlfetch:
      urlfetch.register_handler(
          base_url + 'cool_src/+log/master?format=json&n=1000',
          self._gitiles_json(log_data))
      urlfetch.register_handler(
          base_url + 'cool_src/+log/%s?format=json&n=1000' % ('deadbeef' * 5,),
          self._gitiles_json(log_data))
      urlfetch.register_handler(
          base_url + 'cool_src/+log/%s?format=json&n=1' % ('deadbeef' * 5,),
          self._gitiles_json(log_data))

    controller.scan_repos()
    self.execute_queued_tasks()

    my_repo = models.Repo.get_key_by_id(my_project.name, my_repo.repo).get()
    my_repo.root_commit_scanned = False
    my_repo.first_commit = None
    my_repo.put()

    log_data = {
        u'log': commits[0:2],
        'next': '000fbeef' * 5,
    }
    ooofbeef_data = {
        u'log': commits[1:3],
        'next': 'deadbeef',
    }
    deadbeef_data = {
        u'log': commits[3:5],
        'next': 'feedbeef' * 5,
    }
    feedbeef_data = {
        u'log':  commits[-3:-1],
        'next': 'f00fbeef' * 5,
    }
    toofbeef_data = {
        u'log': commits[2:4],
        'next': 'feedbeef' * 5,
    }
    foofbeef_data = {
        u'log': commits[-2:],
    }
    with self.mock_urlfetch() as urlfetch:
      urlfetch.register_handler(
          base_url + 'cool_src/+log/master?format=json&n=1000',
          self._gitiles_json(log_data))
      urlfetch.register_handler(
          base_url + 'cool_src/+log/%s?format=json&n=2' % ('f007beef' * 5,),
          self._gitiles_json(log_data))
      urlfetch.register_handler(
          base_url + 'cool_src/+log/%s?format=json&n=1000' % ('000fbeef' * 5,),
          self._gitiles_json(ooofbeef_data))
      urlfetch.register_handler(
          base_url + 'cool_src/+log/%s?format=json&n=2' % ('000fbeef' * 5,),
          self._gitiles_json(ooofbeef_data))
      urlfetch.register_handler(
          base_url + 'cool_src/+log/%s?format=json&n=1000' % ('deadbeef' * 5,),
          self._gitiles_json(deadbeef_data))
      urlfetch.register_handler(
          base_url + 'cool_src/+log/%s?format=json&n=2' % ('deadbeef' * 5,),
          self._gitiles_json(deadbeef_data))
      urlfetch.register_handler(
          base_url + 'cool_src/+log/%s?format=json&n=1000' % ('700fbeef' * 5,),
          self._gitiles_json(toofbeef_data))
      urlfetch.register_handler(
          base_url + 'cool_src/+log/%s?format=json&n=1' % ('700fbeef' * 5,),
          self._gitiles_json(toofbeef_data))
      urlfetch.register_handler(
          base_url + 'cool_src/+log/%s?format=json&n=2' % ('700fbeef' * 5,),
          self._gitiles_json(toofbeef_data))
      urlfetch.register_handler(
          base_url + 'cool_src/+log/%s?format=json&n=1000' % ('feedbeef' * 5,),
          self._gitiles_json(feedbeef_data))
      urlfetch.register_handler(
          base_url + 'cool_src/+log/%s?format=json&n=2' % ('feedbeef' * 5,),
          self._gitiles_json(feedbeef_data))
      urlfetch.register_handler(
          base_url + 'cool_src/+log/%s?format=json&n=1000' % ('f00fbeef' * 5,),
          self._gitiles_json(foofbeef_data))
      urlfetch.register_handler(
          base_url + 'cool_src/+log/%s?format=json&n=2' % ('f00fbeef' * 5,),
          self._gitiles_json(foofbeef_data))
    controller.scan_repos()
    self.execute_queued_tasks()

    self.assertEqual(7, len(list(models.RevisionMap.query())))
    my_repo = models.Repo.get_key_by_id(my_project.name, my_repo.repo).get()
    self.assertTrue(my_repo.root_commit_scanned)
