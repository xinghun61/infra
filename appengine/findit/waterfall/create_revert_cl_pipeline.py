# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import textwrap

from google.appengine.ext import ndb

from common import constants
from common import rotations
from gae_libs.http.http_client_appengine import HttpClientAppengine
from gae_libs.pipeline_wrapper import BasePipeline
from infra_api_clients.codereview import codereview_util
from libs import analysis_status as status
from libs import time_util
from model.base_suspected_cl import RevertCL
from model.wf_suspected_cl import WfSuspectedCL
from waterfall import buildbot
from waterfall import suspected_cl_util
from waterfall import waterfall_config


CREATED_BY_FINDIT = 0
CREATED_BY_SHERIFF = 1
ERROR = 2
SKIPPED = 3


NEWEST_BUILD_GREEN = 'Newest build is green.'
CULPRIT_OWNED_BY_FINDIT = 'Culprit is a revert created by Findit.'
AUTO_REVERT_OFF = 'Author of the culprit revision has turned off auto-revert.'
REVERTED_BY_SHERIFF = 'Culprit has been reverted by a sheriff or the CL owner.'


@ndb.transactional
def _ShouldRevert(repo_name, revision, pipeline_id):
  culprit = WfSuspectedCL.Get(repo_name, revision)
  assert culprit
  if ((culprit.revert_cl and culprit.revert_status == status.COMPLETED) or
      culprit.revert_status == status.SKIPPED or
      (culprit.revert_status == status.RUNNING and
       culprit.revert_pipeline_id and
       culprit.revert_pipeline_id != pipeline_id)):
    # Revert of the culprit has been created or is being created by another
    # analysis.
    return False

  # Update culprit to ensure only current analysis can revert the culprit.
  culprit.revert_status = status.RUNNING
  culprit.revert_pipeline_id = pipeline_id
  culprit.put()
  return True


@ndb.transactional
def _UpdateCulprit(repo_name, revision, revert_status=None, revert_cl=None,
                   skip_revert_reason=None):
  culprit = WfSuspectedCL.Get(repo_name, revision)

  culprit.should_be_reverted = True

  culprit.revert_status = revert_status or culprit.revert_status
  culprit.revert_cl = revert_cl or culprit.revert_cl
  culprit.skip_revert_reason = skip_revert_reason or culprit.skip_revert_reason

  if culprit.revert_status != status.RUNNING:
    culprit.revert_pipeline_id = None

  if revert_cl:
    culprit.cr_notification_status = status.COMPLETED
    culprit.cr_notification_time = time_util.GetUTCNow()
  culprit.put()
  return culprit


def _LatestBuildFailed(master_name, builder_name, build_number):
  http_client = HttpClientAppengine()
  latest_build_numbers = buildbot.GetRecentCompletedBuilds(
      master_name, builder_name, http_client)

  for checked_build_number in latest_build_numbers:
    if checked_build_number <= build_number:
      return True

    checked_build_data = buildbot.GetBuildDataFromBuildMaster(
        master_name, builder_name, checked_build_number, http_client)

    if not checked_build_data:
      logging.error("Failed to get build data for %s/%s/%d" % (
          master_name, builder_name, checked_build_number))
      return False

    checked_build_result = buildbot.GetBuildResult(
        json.loads(checked_build_data))

    if checked_build_result in [buildbot.SUCCESS, buildbot.WARNINGS]:
      return False

  return True


def _IsOwnerFindit(owner_email):
  return owner_email == constants.DEFAULT_SERVICE_ACCOUNT


def _RevertCulprit(
    master_name, builder_name, build_number, repo_name, revision, pipeline_id):

  if not _ShouldRevert(repo_name, revision, pipeline_id):
    # Either revert is done or skipped, use skipped as general case.
    return SKIPPED

  culprit = _UpdateCulprit(repo_name, revision)
  # 0. Gets information about this culprit.
  culprit_info = (
      suspected_cl_util.GetCulpritInfo(repo_name, revision))

  culprit_commit_position = culprit_info['commit_position']
  culprit_change_id = culprit_info['review_change_id']
  culprit_host = culprit_info['review_server_host']

  codereview = codereview_util.GetCodeReviewForReview(culprit_host)

  if not codereview or not culprit_change_id:  # pragma: no cover
    logging.error('Failed to get change id for %s/%s' % (repo_name, revision))
    _UpdateCulprit(repo_name, revision, revert_status=status.ERROR)
    return ERROR

  culprit_cl_info = codereview.GetClDetails(culprit_change_id)
  if not culprit_cl_info:  # pragma: no cover
    logging.error('Failed to get cl_info for %s/%s' % (repo_name, revision))
    _UpdateCulprit(repo_name, revision, revert_status=status.ERROR)
    return ERROR

  # Checks if the culprit is a revert created by Findit. If yes, bail out.
  if _IsOwnerFindit(culprit_cl_info.owner_email):
    _UpdateCulprit(repo_name, revision, status.SKIPPED,
                   skip_revert_reason=CULPRIT_OWNED_BY_FINDIT)
    return SKIPPED

  if culprit_cl_info.auto_revert_off:
    _UpdateCulprit(repo_name, revision, status.SKIPPED,
                   skip_revert_reason=AUTO_REVERT_OFF)
    return SKIPPED

  # 1. Checks if a revert CL by sheriff has been created.
  reverts = culprit_cl_info.GetRevertCLsByRevision(revision)

  if reverts is None:  # pragma: no cover
    # if no reverts, reverts should be [], only when some error happens it will
    # be None.
    logging.error('Failed to find patchset_id for %s/%s' % (
        repo_name, revision))
    _UpdateCulprit(repo_name, revision, revert_status=status.ERROR)
    return ERROR

  findit_revert = None
  for revert in reverts:
    if _IsOwnerFindit(revert.reverting_user_email):
      findit_revert = revert
      break

  if reverts and not findit_revert:
    # Sheriff(s) created the revert CL(s).
    _UpdateCulprit(repo_name, revision, revert_status=status.SKIPPED,
                   skip_revert_reason=REVERTED_BY_SHERIFF)
    return CREATED_BY_SHERIFF

  # 2. Reverts the culprit.
  if not _LatestBuildFailed(master_name, builder_name, build_number):
    # The latest build didn't fail, skip.
    _UpdateCulprit(repo_name, revision, status.SKIPPED,
                   skip_revert_reason=NEWEST_BUILD_GREEN)
    return SKIPPED

  revert_change_id = None
  if findit_revert:
    revert_change_id = findit_revert.reverting_cl.change_id

  # TODO (chanli): Better handle cases where 2 analyses are trying to revert
  # at the same time.
  if not revert_change_id:
    revert_reason = textwrap.dedent("""
        Findit (https://goo.gl/kROfz5) identified CL at revision %s as the
        culprit for failures in the build cycles as shown on:
        https://findit-for-me.appspot.com/waterfall/culprit?key=%s""") % (
            culprit_commit_position or revision, culprit.key.urlsafe())

    revert_change_id = codereview.CreateRevert(
      revert_reason, culprit_change_id,
      culprit_cl_info.GetPatchsetIdByRevision(revision))

    if not revert_change_id:  # pragma: no cover
      _UpdateCulprit(repo_name, revision, status.ERROR)
      logging.error('Revert for culprit %s/%s failed.' % (repo_name, revision))
      return ERROR

  # Save revert CL info and notification info to culprit.
  if not culprit.revert_cl:
    revert_cl = RevertCL()
    revert_cl.revert_cl_url = codereview.GetCodeReviewUrl(revert_change_id)
    revert_cl.created_time = time_util.GetUTCNow()
    _UpdateCulprit(repo_name, revision, None, revert_cl=revert_cl)

  # 3. Add reviewers.
  sheriffs = rotations.current_sheriffs()
  message = textwrap.dedent("""
      Sheriffs:

      Please confirm and "Quick L-G-T-M & CQ" this revert if it is correct.
      If it is a false positive, please close it.

      Findit (https://goo.gl/kROfz5) identified the original CL as the culprit
      for failures in the build cycles as shown on:
      https://findit-for-me.appspot.com/waterfall/culprit?key=%s""") % (
          culprit.key.urlsafe())
  success = codereview.AddReviewers(revert_change_id, sheriffs, message)

  if not success:  # pragma: no cover
    _UpdateCulprit(repo_name, revision, status.ERROR)
    logging.error('Failed to add reviewers for revert of culprit %s/%s' % (
      repo_name, revision))
    return ERROR

  _UpdateCulprit(repo_name, revision, revert_status=status.COMPLETED)
  return CREATED_BY_FINDIT


class CreateRevertCLPipeline(BasePipeline):
  def __init__(
      self, master_name, builder_name, build_number, repo_name, revision):
    super(CreateRevertCLPipeline, self).__init__(
        master_name, builder_name, build_number, repo_name, revision)
    self.master_name = master_name
    self.builder_name = builder_name
    self.build_number = build_number
    self.repo_name = repo_name
    self.revision = revision

  def _LogUnexpectedAborting(self, was_aborted):
    if not was_aborted:  # pragma: no cover
      return

    culprit = WfSuspectedCL.Get(self.repo_name, self.revision)

    if culprit.revert_pipeline_id == self.pipeline_id:
      if culprit.revert_status and culprit.revert_status != status.COMPLETED:
        culprit.revert_status = status.ERROR
      culprit.revert_pipeline_id = None
      culprit.put()

  def finalized(self):  # pragma: no cover
    self._LogUnexpectedAborting(self.was_aborted)

  # Arguments number differs from overridden method - pylint: disable=W0221
  def run(self, master_name, builder_name, build_number, repo_name, revision):
    if waterfall_config.GetActionSettings().get(
        'revert_compile_culprit', False):
      return _RevertCulprit(
          master_name, builder_name, build_number, repo_name, revision,
          self.pipeline_id)
    return None
