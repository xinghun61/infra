# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
from datetime import datetime
import json
import logging
import numpy
import random
import re
import time

from google.appengine.ext import ndb
from google.appengine.api import urlfetch

from appengine_module.cr_rev import models
from appengine_module.cr_rev.appengine_third_party_pipeline_src_pipeline \
    import pipeline


# Repos excluded from scanning.
REPO_EXCLUSIONS = {
    'chromium': [
      'chromium/blink',  # gitiles bug
      'chromium/chromium',  # conflicts with chromium/src
      'chromiumos/third_party/mesa',  # gitiles bug
      'chromiumos/third_party/wayland-demos',  # gitiles bug
      'dart/dartium/src',  # conflicts with chromium/src
      'experimental/chromium/blink',  # conflicts with chromium/blink
      'experimental/chromium/src',  # conflicts with chromium/src
      'experimental/chromium/tools/build',  # conflicts with tools/build
      'experimental/external/gyp',  # conflicts with external/gyp
      'experimental/external/v8',  # conflicts with external/v8
      'external/WebKit_submodule',  # gitiles bug
      'external/Webkit',  # gitiles bug
      'external/naclports',  # gitiles bug
      'external/w3c/csswg-test',  # gitiles bug
      'native_client/nacl-binutils',  # gitiles bug
      'native_client/pnacl-llvm-testsuite',  # gitiles bug
    ]
}


def get_projects():
  return list(models.Project.query())


def calculate_repo_url(repo_obj):
  """Constructs a url to the repository using the project template."""
  return repo_obj.canonical_url_template % {
      'project': repo_obj.project,
      'repo': repo_obj.repo
  }


def get_active_repos(project):
  """Get the repos that are active (have code, weren't deleted)."""
  included_repos = []
  for repo in list(models.Repo.query(
    models.Repo.project == project).filter(
      models.Repo.active == True).filter(
        models.Repo.real == True)):
    if repo.repo not in REPO_EXCLUSIONS.get(project, []):
      included_repos.append(repo)
  return included_repos


def make_gitiles_json_call(url, n=10000):
  """Make a JSON call to gitiles and decode the result.

  This makes a gitiles call with exponential backoff in the case of 429s. When
  it gets a result, it decodes and returns the resulting object. If the
  exponential backoff times out, it raises pipeline.PipelineUserError.

  Args:
    url (str): the url to query
    n (int): the number of items to get (this is appended to the query string)
  """
  full_url = url + '?format=json&n=%d' % n

  backoff = 10
  attempts = 4
  for i in range(attempts):
    logging.info('scanning %s', full_url)
    result = urlfetch.fetch(full_url, deadline=60)
    if result.status_code == 200:
      # Gitiles serves JSONP, so we strip it out here.
      assert result.content[0:5] == ')]}\'\n'
      return json.loads(result.content[5:])
    elif result.status_code != 429:
      raise pipeline.PipelineUserError(
          'urlfetch returned %d' % result.status_code)

    sleep = backoff  * (2 ** i)
    logging.info('got 429, sleeping %d secs...', sleep)
    time.sleep(sleep + random.random())
  raise pipeline.PipelineUserError(
      'urlfetch returned 429 after %d attempts, timing out!' % attempts)


def crawl_log(repo_url, start='master', until=None, n=10000):
  """Crawls the commit log of a specific branch of a repository."""
  crawl_url = repo_url + '+log/%s' % start
  crawl_json = make_gitiles_json_call(crawl_url, n=n)
  commits = []
  finished = False
  for commit in crawl_json.get('log', []):
    if until and commit['commit'] == until:
      finished = True
      break
    commits.append(commit)
  if not commits or 'next' not in crawl_json:
    finished = True

  return commits, finished


GIT_SVN_ID_REGEX = re.compile(r'git-svn-id: (.*)@(\d+) ')
GIT_COMMIT_POSITION_REGEX = re.compile(r'Cr-Commit-Position: (.*)@{#(\d+)}')


def parse_commit_message(msg, project, repo):
  """Take a commit message and parse out any numberings."""
  numberings = []
  lines = msg.split('\n')
  for line in lines:
    git_svn_match = GIT_SVN_ID_REGEX.match(line)
    if git_svn_match:
      full_url = git_svn_match.group(1)
      revision = int(git_svn_match.group(2))

      # SVN folders can be individually checked out, so we add them all here:
      #   svn.chromium.org/chrome
      #   svn.chromium.org/chrome/trunk
      #   svn.chromium.org/chrome/trunk/src
      for i in range(len(full_url.split('/')) - 3):
        url = '/'.join(full_url.split('/')[0:i+4])
        numberings.append(
          models.NumberingMap(
            numbering_type=models.NumberingType.SVN,
            numbering_identifier=url,
            number=revision,
            key=ndb.Key(models.NumberingMap,
              models.NumberingMap.svn_unique_id(url, revision))
          )
        )

    else:
      git_commit_position_match = GIT_COMMIT_POSITION_REGEX.match(line)
      if git_commit_position_match:
        git_ref = git_commit_position_match.group(1)
        commit_position = int(git_commit_position_match.group(2))
        numberings.append(
          models.NumberingMap(
            numbering_type=models.NumberingType.COMMIT_POSITION,
            numbering_identifier=git_ref,
            number=commit_position,
            key=ndb.Key(models.NumberingMap,
              models.NumberingMap.git_unique_id(
                project, repo, git_ref, commit_position))
          )
        )

  return numberings


def convert_commit_json_to_commit(project, repo, commit_json):
  """Take a commit from the gitiles log and return a commit object.

  This function parses out all the numberings present in the commit message,
  writes those numberings to the database, and constructs a models.RevisionMap
  object to be committed representing the commit itself.

  Args:
    project (models.Project): the current project object
    repo (models.Repo): the current repo object
    commit_json (dict): the single commit JSON as returned by gitiles
  """
  commit_pos = None
  git_svn_pos = None

  repo_obj = models.Repo.get_key_by_id(project, repo).get()
  redirect_url = calculate_repo_url(repo_obj)
  redirect_url = redirect_url + '+/%s' % commit_json['commit']

  numberings = parse_commit_message(commit_json['message'], project, repo)
  full_model_numberings = copy.deepcopy(numberings)
  for numbering in full_model_numberings:
    numbering.project = project
    numbering.repo = repo
    numbering.git_sha = commit_json['commit']
    numbering.redirect_url = redirect_url
  map_futures = []
  if full_model_numberings:
    map_futures = ndb.put_multi_async(full_model_numberings)

  for numbering in numberings:
    if numbering.numbering_type == models.NumberingType.COMMIT_POSITION:
      commit_pos = numbering.number
    else:  # SVN numbering.
      git_svn_pos = numbering.number

  number = commit_pos or git_svn_pos or None

  commit = models.RevisionMap(
      numberings=numberings,
      number=number,
      project=project,
      repo=repo,
      git_sha=commit_json['commit'],
      redirect_url = redirect_url,
      key=ndb.Key(models.RevisionMap, commit_json['commit'])
  )

  return commit, map_futures


def write_commits_to_db(commits, project, repo, batch=100):
  """Write provided commits to the database (chunked in batches).

  Args:
    commits (list): a list of commit dictionaries returned by gitiles
    project (models.Project): the current project object
    repo (models.Repo): the current repo object
    batch (int): the number of commits to write at a time
  """

  futures = []
  # Batch our writes so we don't blow our memory limit.
  for chunk in (commits[i:i+batch] for i in range(0, len(commits), batch)):
    converted_tuples = [convert_commit_json_to_commit(project, repo, c)
                   for c in chunk]
    commit_objs, map_futures = zip(*converted_tuples)
    for future_list in map_futures:
      futures.extend(future_list)
    futures.extend(ndb.put_multi_async(commit_objs))
    logging.info('%d commits dispatched for write' % len(commit_objs))
    ndb.get_context().clear_cache()

  ndb.Future.wait_all(futures)
  logging.info('all set.')


def fetch_by_number(number, numbering_type, repo=None, project=None, ref=None):
  """Given a repository and a commit number, fetch the commit."""
  fetch_key = models.NumberingMap.get_key_by_id(
        number, numbering_type, repo=repo, project=project, ref=ref)
  logging.info('looking for %s', fetch_key)
  fetch_obj = fetch_key.get()
  if fetch_obj:
    logging.info('success: redirect to %s', fetch_obj.redirect_url)
  else:
    logging.info('not found')
  return fetch_obj


RIETVELD_REGEX = re.compile(r'\d{8,39}')
NUMBER_REGEX = re.compile(r'\d{1,8}$')
SHORT_GIT_SHA = re.compile(r'[a-fA-F0-9]{6,39}')
FULL_GIT_SHA = re.compile(r'[a-fA-F0-9]{40}')


def fetch_default_number(number):
  """Fetch the 'default' number from chromium/src (or svn.chromium.org)."""
  git_match = fetch_by_number(number, models.NumberingType.COMMIT_POSITION,
      repo='chromium/src',
      project='chromium', ref='refs/heads/master')
  if git_match:
    return git_match

  try:
    # This is the last commit that chromium/src was on svn, so we know not
    # to scan for svn commits higher than this.
    if int(number) < 291561:
      svn_match = fetch_by_number(
          number, models.NumberingType.SVN, ref='svn://svn.chromium.org/chrome')
      if svn_match:
        return svn_match
  except ValueError:  # pragma: no cover
    logging.error('could not convert %d to a number!', number)

  return None


def calculate_redirect(arg):
  """Given a query, return a redirect URL depending on a fixed set of rules."""
  if NUMBER_REGEX.match(arg):
    numbering = fetch_default_number(arg)
    if numbering:
      repo_obj = models.Repo.get_key_by_id(
          numbering.project, numbering.repo).get()
      repo_url = calculate_repo_url(repo_obj)
      return models.Redirect(
          redirect_type=models.RedirectType.GIT_FROM_NUMBER,
          redirect_url=numbering.redirect_url,
          project=numbering.project,
          repo=numbering.repo,
          git_sha=numbering.git_sha,
          repo_url=repo_url,
          )

  if FULL_GIT_SHA.match(arg):
    revision_map = ndb.Key(models.RevisionMap, arg).get()
    if revision_map:
      repo_obj = models.Repo.get_key_by_id(
          revision_map.project, revision_map.repo).get()
      repo_url = calculate_repo_url(repo_obj)
      return models.Redirect(
          redirect_type=models.RedirectType.GIT_FULL,
          redirect_url=revision_map.redirect_url,
          project=revision_map.project,
          repo=revision_map.repo,
          git_sha=revision_map.git_sha,
          repo_url=repo_url,
      )

  if RIETVELD_REGEX.match(arg):
    return models.Redirect(
        redirect_type=models.RedirectType.RIETVELD,
        redirect_url='https://codereview.chromium.org/%s' % arg)

  if SHORT_GIT_SHA.match(arg) and not NUMBER_REGEX.match(arg):
    return models.Redirect(
        redirect_type=models.RedirectType.GIT_SHORT,
        redirect_url='https://chromium.googlesource.com/chromium/src/+/%s' % (
          arg,))

  return None


def calculate_lag_stats(generated=None):
  """Return statistics about the scan times of all repositories."""
  projects = get_projects()
  stats = []
  now = generated or datetime.now()
  for project in projects:
    repos = get_active_repos(project.name)
    lag_stats = models.ProjectLagStats(
        project=project.name,
        generated=now,
        total_active_repos=len(repos),
        unscanned_repos=len([r for r in repos if not r.last_scanned]),
        scanned_repos=len([r for r in repos if r.last_scanned]),
        repos_without_root=len([r for r in repos if not r.root_commit_scanned]),
        repos_with_root=len([r for r in repos if r.root_commit_scanned])
    )

    scan_lag_with_repo = {}
    scan_lag = []
    for repo in repos:
      if repo.last_scanned:
        repo_scan_lag = (now - repo.last_scanned).total_seconds()
        scan_lag.append(repo_scan_lag)
        scan_lag_with_repo[repo_scan_lag] = '%s:%s' % (project.name, repo.repo)
    if scan_lag:
      lag_stats.p50 = numpy.percentile(scan_lag, 50)
      lag_stats.p75 = numpy.percentile(scan_lag, 75)
      lag_stats.p90 = numpy.percentile(scan_lag, 90)
      lag_stats.p95 = numpy.percentile(scan_lag, 95)
      lag_stats.p99 = numpy.percentile(scan_lag, 99)
      lag_stats.max = numpy.max(scan_lag)
      lag_stats.min = numpy.min(scan_lag)
      lag_stats.most_lagging_repo = scan_lag_with_repo[lag_stats.max]

    stats.append(lag_stats)

  return models.ProjectLagList(projects=stats, generated=now)
