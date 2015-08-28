# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from base_handler import BaseHandler
from base_handler import Permission
from common.git_repository import GitRepository
from common.http_client_appengine import HttpClientAppengine as HttpClient
from model.wf_analysis import WfAnalysis
from waterfall import buildbot
from waterfall import build_util


def _GetFirstFailedBuild(master_name, builder_name, build_number):
  """Checks failed_steps for current_build and finds the first failed build."""
  analysis = WfAnalysis.Get(master_name, builder_name, build_number)
  if not analysis or not analysis.result['failures']:
    return None, None

  start_build_number = build_number
  failed_steps = []
  for failure in analysis.result['failures']:
    failed_steps.append(failure['step_name'])
    if failure['last_pass'] and failure['last_pass'] + 1 < start_build_number:
      start_build_number = failure['last_pass'] + 1
      continue
    if failure['first_failure'] < start_build_number:
      start_build_number = failure['first_failure']

  return start_build_number, failed_steps


def _AllFailedStepsPassed(passed_steps, current_failed_steps):
  for current_failed_step in current_failed_steps:
    if current_failed_step not in passed_steps:
      return False
  return True

def GetPossibleRevertInfoFromRevision(revision):
  """Parse message to get information of reverting and reverted cls."""
  git_repo = GitRepository('https://chromium.googlesource.com/chromium/src.git',
                           HttpClient())
  change_log = git_repo.GetChangeLog(revision)
  if not change_log:  # pragma: no cover
    return {}

  reverted_revision = change_log.reverted_revision
  if not reverted_revision:
    return {}

  reverted_cl_change_log = git_repo.GetChangeLog(reverted_revision)

  data = {
      'action': 'Reverted',
      'fixed_revision': reverted_revision,
      'fixed_cl_review_url': (reverted_cl_change_log.code_review_url
          if reverted_cl_change_log else None),
      'fixed_cl_commit_position': (reverted_cl_change_log.commit_position
          if reverted_cl_change_log else None),
      'fixing_revision': revision,
      'fixing_cl_review_url': change_log.code_review_url,
      'fixing_cl_commit_position': change_log.commit_position
  }
  return data

def _CheckReverts(master_name, builder_name, current_build_number):
  """Checks each cl in current build to see if some of them are reverted.

  Returns:
      {
          'c9cc182781484f9010f062859cda048afef': {
              'action': 'Reverted',
              'fixed_cl_commit_position': '341992',
              'fixed_revision': 'c9cc182781484f9010f062859cda048afef',
              'fixed_cl_review_url': (
                 'https://codereview.chromium.org/1278653002'),
              'fixing_build_number': 0,
              'fixing_build_url': (
                  'https://build.chromium.org/p/m/builders/b/builds/0')
              'fixing_revision': '208c65020aecfcf305d524058f7ca89363',
              'fixing_cl_commit_position': '342013',
              'fixing_cl_review_url': (
                 'https://codereview.chromium.org/1278653005'),
              'fixing_build_number': 2,
              'fixing_build_url': (
                  'https://build.chromium.org/p/m/builders/b/builds/2')
          },
          ...
      }
  """
  data = {}
  reverted_cls = {}
  blamed_cls = {}
  steps_pass = False

  build_number, current_failed_steps = _GetFirstFailedBuild(
      master_name, builder_name, current_build_number)
  if not build_number:
    return data

  while not steps_pass:
    # Breaks the loop after the first green build
    # or all the current failed steps pass.
    build = build_util.DownloadBuildData(
        master_name, builder_name, build_number)
    if not build or not build.data:
      return data

    build_info = buildbot.ExtractBuildInfo(
        master_name, builder_name, build_number, build.data)
    if build_number <= current_build_number:
      # All the cls in builds prior to the current build(included)
      # should be checked for reverts.
      for blamed_revision in build_info.blame_list:
        blamed_cls[blamed_revision] = build_number
    if (build_info.result == 0 or
        _AllFailedStepsPassed(build_info.passed_steps, current_failed_steps)):
      steps_pass = True

    for cl_in_blame_list in build_info.blame_list:
      cls_info = GetPossibleRevertInfoFromRevision(cl_in_blame_list)
      if not cls_info:
        continue

      fixed_revision = cls_info['fixed_revision']
      if (fixed_revision in blamed_cls and
          build_number > blamed_cls[fixed_revision] and
          build_number > current_build_number):
          # If a CL and its reverting cl are in the same build,
          # it doesn't have any impact on the build failure.
          # And possible fix should take effect after the current build.
        cls_info['fixed_build_number'] = blamed_cls[fixed_revision]
        cls_info['fixed_build_url'] = (
            buildbot.CreateBuildUrl(
                master_name, builder_name, blamed_cls[fixed_revision]))
        cls_info['fixing_build_number'] = build_number
        cls_info['fixing_build_url'] = (
            buildbot.CreateBuildUrl(master_name, builder_name, build_number))
        reverted_cls[fixed_revision] = cls_info
    build_number += 1
  if reverted_cls:
    data = reverted_cls
  return data


class HelpTriage(BaseHandler):
  PERMISSION_LEVEL = Permission.ADMIN

  def HandleGet(self):  # pragma: no cover
    return self.HandlePost()

  def HandlePost(self):
    """Gets information to help triage the analysis results.

    1. Checks if any CL in current build is reverted in later builds
    up until the first green build(included).
    2. TODO: Checks if any changed file in current build is changed again in
    later builds up until the first green build(included).
    """
    url = self.request.get('url').strip()
    build_keys = buildbot.ParseBuildUrl(url)

    if not build_keys:  # pragma: no cover
      return {'data': {}}

    data = _CheckReverts(*build_keys)

    return {'data': data}
