# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
import logging
import numpy
import re

from google.appengine.ext import ndb

from appengine_module.cr_rev import models


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


GIT_SVN_ID_REGEX = re.compile(r'git-svn-id: (.*)@(\d+) ')
GIT_COMMIT_POSITION_REGEX = re.compile(r'Cr-Commit-Position: (.*)@{#(\d+)}')


def fetch_by_number(number, numbering_type, repo=None, project=None, ref=None):
  """Given a repository and a commit number, fetch the commit."""
  fetch_key = models.NumberingMap.get_key_by_id(
        number, numbering_type, repo=repo, project=project, ref=ref)
  logging.info('looking for %s' % fetch_key)
  fetch_obj = fetch_key.get()
  if fetch_obj:
    logging.info('success: redirect to %s' % fetch_obj.redirect_url)
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
